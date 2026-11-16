"""Voix off : narration -> audio + minutage mot à mot.

Deux moteurs, même interface :
- « chatterbox » : Chatterbox Multilingual V3 (Resemble AI, licence MIT). Voix naturelle, sert au rendu final.
- « kokoro »     : Kokoro (Apache 2.0). Léger et rapide, sert aux contrôles d'images et de secours.

Chaque phrase est synthétisée séparément : ses bornes sont donc exactes.
À l'intérieur d'une phrase, les mots sont répartis au prorata de leur longueur parlée.
"""
import importlib.util
import json
import os
import re
from pathlib import Path

import numpy as np
from num2words import num2words

SR = 24000
NNBSP, NBSP = " ", " "
ROOT = Path(__file__).resolve().parent.parent

# Prononciations forcées (texte parlé uniquement, l'écran garde l'orthographe d'origine).
LEXIQUE = {
    "marks-or": "marks or",
    "1er": "premier",
    "%": " pour cent",
    "&": " et ",
}


def voice_config():
    f = ROOT / "config/voice.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def pick_engine(wanted=None):
    """Moteur demandé, sinon celui du réglage s'il est installé, sinon Kokoro."""
    wanted = wanted or os.environ.get("REEL_VOICE_ENGINE") or voice_config().get("engine", "kokoro")
    if wanted == "chatterbox" and importlib.util.find_spec("chatterbox") is None:
        return "kokoro"
    return wanted


# ---------------------------------------------------------------- texte
def spoken(text, lexique=None):
    """Version « à dire » d'un texte : nombres en lettres, espaces fines retirées."""
    t = re.sub(rf"(?<=\d)[{NNBSP}{NBSP}](?=\d)", "", text)
    t = t.replace(NNBSP, " ").replace(NBSP, " ")
    for k, v in {**LEXIQUE, **(lexique or {})}.items():
        t = re.sub(re.escape(k), v, t, flags=re.IGNORECASE)

    def num(m):
        s = m.group(0)
        return num2words(float(s.replace(",", ".")) if "," in s else int(s), lang="fr")

    return re.sub(r"\d+(?:,\d+)?", num, t)


def split_sentences(text):
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def tokenize(sentence):
    """Mots affichés. Les espaces insécables restent dans le mot (« 4 200 », « possible ? »)."""
    out = []
    for tok in re.split(r"[ \t\n]+", sentence.strip()):
        if not tok:
            continue
        if out and not re.search(r"[\w\d]", tok):  # ponctuation isolée -> collée au mot précédent
            out[-1] += NBSP + tok
        else:
            out.append(tok)
    return out


def letters(text):
    return len(re.findall(r"[^\W\d_]", text))


def weight(tok, lexique=None):
    w = max(1, letters(spoken(tok, lexique)))
    if re.search(r",$", tok):
        w += 3
    if re.search(r"[;:…]$", tok):
        w += 5
    return w


def _trim(x, pad=0.03):
    peak = float(np.abs(x).max()) if len(x) else 0.0
    if peak == 0:
        return x
    idx = np.where(np.abs(x) > 0.02 * peak)[0]
    a = max(0, idx[0] - int(pad * SR))
    b = min(len(x), idx[-1] + int(pad * SR))
    return x[a:b]


# ---------------------------------------------------------------- moteurs
_kokoro = None
_chatterbox = None


def _kokoro_say(text, cfg):
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(ROOT / "models/kokoro-v1.0.onnx"), str(ROOT / "models/voices-v1.0.bin"))
    k = cfg.get("kokoro", {})
    samples, sr = _kokoro.create(text, voice=k.get("name", "ff_siwis"), speed=k.get("speed", 1.05), lang="fr-fr")
    assert sr == SR
    return np.asarray(samples, dtype=np.float32)


def _chatterbox_say(text, cfg, seed):
    global _chatterbox
    import torch
    if _chatterbox is None:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        torch.set_num_threads(os.cpu_count() or 2)
        try:
            _chatterbox = ChatterboxMultilingualTTS.from_pretrained(device="cpu", t3_model="v3")
        except TypeError:  # version du paquet antérieure à V3
            _chatterbox = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    kw = {"language_id": "fr", "exaggeration": cfg.get("exaggeration", 0.5), "cfg_weight": cfg.get("cfg_weight", 0.5)}
    if cfg.get("reference"):
        kw["audio_prompt_path"] = str(ROOT / cfg["reference"])
    torch.manual_seed(seed)
    wav = _chatterbox.generate(text, **kw).squeeze().detach().cpu()
    if _chatterbox.sr != SR:
        import torchaudio
        wav = torchaudio.functional.resample(wav, _chatterbox.sr, SR)
    return wav.numpy().astype(np.float32)


def say(sentence, engine, cfg, lexique=None):
    text = spoken(sentence, lexique)
    if engine == "kokoro":
        return _trim(_kokoro_say(text, cfg))
    # Chatterbox peut, rarement, bafouiller ou s'emballer : on vérifie la durée et on retente.
    expected = max(0.7, letters(text) / 15.0)
    best = None
    for attempt in range(3):
        x = _trim(_chatterbox_say(text, cfg, seed=1923 + 101 * attempt))
        d = len(x) / SR
        score = abs(np.log(max(d, 0.05) / expected))
        if best is None or score < best[0]:
            best = (score, x)
        if 0.55 * expected <= d <= 2.0 * expected:
            break
        print(f"   voix : durée suspecte ({d:.1f} s pour {expected:.1f} s attendues), nouvel essai")
    return best[1]


# ---------------------------------------------------------------- narration complète
def narrate(reel, engine=None, lead=0.30, sentence_gap=0.20, scene_gap=0.65, tail=1.3):
    """Retourne (audio float32 mono, minutage)."""
    engine = pick_engine(engine)
    cfg = voice_config()
    if reel.get("voice"):                       # réglage Kokoro propre au script (facultatif)
        cfg = dict(cfg, kokoro={**cfg.get("kokoro", {}), **reel["voice"]})
    lex = reel.get("pronunciations")
    sil = lambda d: np.zeros(int(round(d * SR)), dtype=np.float32)

    chunks, t, scenes, cuts = [sil(lead)], lead, [], []
    n = len(reel["scenes"])
    for i, sc in enumerate(reel["scenes"]):
        sents = split_sentences(sc["narration"])
        start, words, sentences = t, [], []
        for j, sent in enumerate(sents):
            wav = say(sent, engine, cfg, lex)
            wav = wav / (float(np.abs(wav).max()) or 1.0) * 0.85      # même niveau d'une phrase à l'autre
            d = len(wav) / SR
            toks = tokenize(sent)
            ws = [weight(k, lex) for k in toks]
            total_w, c = sum(ws), 0
            for k, w in zip(toks, ws):
                words.append({"t": k, "s": round(t + d * c / total_w, 3), "e": round(t + d * (c + w) / total_w, 3)})
                c += w
            sentences.append({"s": round(t, 3), "e": round(t + d, 3), "text": sent})
            chunks.append(wav)
            t += d
            if j < len(sents) - 1:
                chunks.append(sil(sentence_gap))
                t += sentence_gap
        scenes.append({"start": round(start, 3), "end": round(t, 3), "words": words, "sentences": sentences})
        gap = sc.get("hold", 0) + (scene_gap if i < n - 1 else tail)
        chunks.append(sil(gap))
        t += gap
        if i < n - 1:
            cuts.append(round(t - scene_gap / 2, 3))

    audio = np.concatenate(chunks).astype(np.float32)
    return audio, {"total": round(len(audio) / SR, 3), "scenes": scenes, "cuts": cuts, "engine": engine}
