#!/usr/bin/env bash
# Publie les vidéos de out/ sur la branche « media ».
# La branche ne contient qu'un seul commit, réécrit à chaque fois : l'historique ne gonfle pas.
set -euo pipefail
KEEP="${KEEP:-45}"                                   # nombre de vidéos conservées
REMOTE="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
work="$(mktemp -d)"
git clone -q --depth 1 --branch media "$REMOTE" "$work" 2>/dev/null || true
rm -rf "$work/.git"
mkdir -p "$work/status"

shopt -s nullglob
for d in out/*/; do
  id="$(basename "$d")"
  [ -f "$d/$id.mp4" ] && cp "$d/$id.mp4" "$work/$id.mp4"
  [ -f "$d/cover.jpg" ] && cp "$d/cover.jpg" "$work/$id.jpg"
  [ -f "$d/status.json" ] && cp "$d/status.json" "$work/status/$id.json"
done
if [ -d out/voix-essais ]; then mkdir -p "$work/voix-essais"; cp out/voix-essais/*.m4a "$work/voix-essais/"; fi

# Les identifiants commencent par la date : on garde les plus récents.
ls "$work"/*.mp4 2>/dev/null | sort -r | tail -n +"$((KEEP + 1))" | while read -r f; do
  rm -f "$f" "${f%.mp4}.jpg" "$work/status/$(basename "${f%.mp4}").json"
done

cd "$work"
git init -q -b media
git config user.name "reels-bot"
git config user.email "reels-bot@users.noreply.github.com"
git add -A
git commit -q -m "Médias au $(date -u '+%F %H:%M') UTC"
git push -q -f "$REMOTE" media
echo "Branche media mise à jour : $(ls *.mp4 2>/dev/null | wc -l) vidéo(s)."
