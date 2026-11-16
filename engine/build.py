#!/usr/bin/env python3
"""Fabrique un reel vertical à partir d'un fichier de script.

    python3 engine/build.py content/mon-reel.json            # rendu complet
    python3 engine/build.py content/mon-reel.json --stills   # quelques images de contrôle seulement
    python3 engine/build.py content/mon-reel.json --engine kokoro   # forcer un moteur de voix
"""
import argparse
import json
import subprocess
import sys
import traceback
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402
import tts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def check(reel):
    """Refuse un script incomplet : pas de publication sans sources."""
    errs = []
    for k in ("id", "title", "scenes", "facts", "sources", "captions"):
        if not reel.get(k):
            errs.append(f"champ manquant : {k}")
    if len(reel.get("sources", [])) < 2:
        errs.append("il faut au moins 2 sources indépendantes")
    for i, sc in enumerate(reel.get("scenes", [])):
        if not sc.get("narration"):
            errs.append(f"scène {i + 1} sans narration")
    for k in ("short", "youtube_title", "youtube_description"):
        if not reel.get("captions", {}).get(k):
            errs.append(f"légende manquante : captions.{k}")
    if len(reel.get("captions", {}).get("youtube_title", "")) > 100:
        errs.append("titre YouTube de plus de 100 caractères")
    if errs:
        raise SystemExit("Script refusé :\n - " + "\n - ".join(errs))


def page(reel, timing, outdir):
    data = dict(reel, timing=timing)
    (outdir / "data.js").write_text("window.REEL = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    html = (ROOT / "templates/reel.html").read_text(encoding="utf-8").replace("__ROOT__", ROOT.as_uri())
    (outdir / "index.html").write_text(html, encoding="utf-8")
    return (outdir / "index.html").as_uri()


def build(a, reel, outdir):
    engine = tts.pick_engine(a.engine)
    timing_file, wav = outdir / "timing.json", outdir / "voix.wav"
    cache_key = json.dumps([[[s["narration"], s.get("hold", 0)] for s in reel["scenes"]], engine, tts.voice_config(),
                            reel.get("voice"), reel.get("pronunciations")], ensure_ascii=False, sort_keys=True)
    if timing_file.exists() and wav.exists() and json.loads(timing_file.read_text()).get("_key") == cache_key:
        timing = json.loads(timing_file.read_text())
        print(f"1/3 voix ({engine}) : reprise du cache")
    else:
        print(f"1/3 voix ({engine}) : synthèse…")
        audio, timing = tts.narrate(reel, engine)
        sf.write(wav, audio, tts.SR)
        timing["_key"] = cache_key
        timing_file.write_text(json.dumps(timing, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"   durée totale : {timing['total']:.1f} s")
    if not 20 <= timing["total"] <= 75:
        raise SystemExit(f"Durée hors limites ({timing['total']:.1f} s) : il faut entre 20 et 75 s. Raccourcir ou étoffer le texte.")

    url = page(reel, timing, outdir)

    if a.stills:
        # l'instant le plus chargé de chaque scène : juste avant la coupe
        ends = timing["cuts"] + [timing["total"] - 0.2]
        times = [float(x) for x in a.times.split(",")] if a.times else [round(e - 0.35, 2) for e in ends]
        for p in render.stills(url, times, outdir):
            print("   image :", p)
        return None

    print("2/3 image : tournage scène par scène…")
    files = render.film(url, timing["total"], timing["cuts"], outdir)
    print("3/3 montage…")
    final = render.assemble(files, wav, outdir / f"{reel['id']}.mp4")
    cover_t = max(0.0, timing["cuts"][0] - 0.4) if timing["cuts"] else 1.0
    cover = render.stills(url, [cover_t], outdir)[0]
    cover.rename(outdir / "cover.jpg")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "csv=p=0", str(final)],
                           capture_output=True, text=True).stdout.strip().split(",")
    print(f"Terminé : {final}  ({probe[0]} s, {int(probe[1]) / 1e6:.1f} Mo)")
    return {"duration": round(float(probe[0]), 1), "size": int(probe[1]), "engine": engine}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default=None)
    ap.add_argument("--engine", default=None, choices=["chatterbox", "kokoro"], help="moteur de voix (défaut : config/voice.json)")
    ap.add_argument("--stills", action="store_true", help="images de contrôle uniquement, pas de vidéo")
    ap.add_argument("--times", default=None, help="instants des images de contrôle, ex. 2.5,14")
    a = ap.parse_args()

    reel = json.loads(Path(a.script).read_text(encoding="utf-8"))
    outdir = Path(a.out) if a.out else ROOT / "out" / reel.get("id", Path(a.script).stem)
    outdir.mkdir(parents=True, exist_ok=True)
    status = {"id": reel.get("id", Path(a.script).stem), "title": reel.get("title"), "ok": False}
    try:
        check(reel)
        info = build(a, reel, outdir)
        if info:
            status.update(ok=True, **info)
    except BaseException as e:  # le compte rendu doit exister même en cas d'échec
        status["error"] = (str(e) or e.__class__.__name__)[:1500]
        if not isinstance(e, SystemExit):
            status["trace"] = traceback.format_exc()[-2500:]
        raise
    finally:
        if not a.stills:
            (outdir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
