#!/usr/bin/env bash
# Prépare une machine neuve : dépendances, polices, modèle de voix. À relancer sans risque.
set -euo pipefail
cd "$(dirname "$0")"
pip install --break-system-packages -q -r requirements.txt 2>/dev/null || pip install -q -r requirements.txt
npm ci --silent 2>/dev/null || npm install --silent
mkdir -p models
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -s "models/$f" ] || curl -sS -L -o "models/$f" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
python3 -c "from playwright.sync_api import sync_playwright as p; b=p().start().chromium.launch(); b.close()" 2>/dev/null || python3 -m playwright install chromium
command -v ffmpeg >/dev/null || { echo "ffmpeg manquant"; exit 1; }
echo "Prêt."
