#!/usr/bin/env python3
"""Essais de voix : le même texte dit avec plusieurs réglages, pour choisir à l'oreille.

    python3 engine/voice_lab.py      # écrit out/voix-essais/*.m4a
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts  # noqa: E402

TEXTE = ["En novembre 1923, en Allemagne, un pain coûte 200 milliards de marks.",
         "Dix mois plus tôt, le même pain valait 250 marks.",
         "Comment est-ce possible ?"]
REF = "voices/reference-fr.wav"
ESSAIS = {
    "A-voix-d-origine": {"cfg_weight": 0.0, "exaggeration": 0.5},
    "B-voix-francaise-posee": {"reference": REF, "cfg_weight": 0.5, "exaggeration": 0.5},
    "C-voix-francaise-vivante": {"reference": REF, "cfg_weight": 0.3, "exaggeration": 0.75},
}
perso = tts.ROOT / "voices/ma-voix.wav"          # un enregistrement de 15 s de la voix du propriétaire, s'il existe
if perso.exists():
    ESSAIS["D-ma-voix"] = {"reference": "voices/ma-voix.wav", "cfg_weight": 0.4, "exaggeration": 0.6}

out = tts.ROOT / "out/voix-essais"
out.mkdir(parents=True, exist_ok=True)
gap = np.zeros(int(0.25 * tts.SR), dtype=np.float32)
for nom, cfg in ESSAIS.items():
    parts = []
    for phrase in TEXTE:
        x = tts.say(phrase, "chatterbox", cfg)
        parts += [x / (float(np.abs(x).max()) or 1.0) * 0.85, gap]
    wav = out / f"{nom}.wav"
    sf.write(wav, np.concatenate(parts), tts.SR)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "aac", "-b:a", "128k", str(out / f"{nom}.m4a")], check=True)
    wav.unlink()
    print("essai :", nom)
