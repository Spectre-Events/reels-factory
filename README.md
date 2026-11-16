# Fabrique de reels

Transforme un script structuré en reel vertical prêt à publier : voix off française, animations, sous-titres mot à mot, montage. Uniquement des outils libres et gratuits.

Pousser un script dans `content/` suffit : GitHub Actions rend la vidéo avec la voix naturelle et la dépose sur la branche `media`.

## Démarrer

```bash
bash setup.sh                                                        # dépendances, polices, modèle de voix (~350 Mo)
python3 engine/build.py content/2026-11-16-pain-200-milliards.json --stills   # images de contrôle
python3 engine/build.py content/2026-11-16-pain-200-milliards.json            # vidéo complète dans out/<id>/
```

Il faut Python 3.10+, Node 18+, ffmpeg et Chromium (installé par Playwright).

## Comment ça marche

| Étape | Fichier | Ce qu'il fait |
|---|---|---|
| Voix | `engine/tts.py` | Chatterbox Multilingual V3 au rendu final, Kokoro pour les contrôles rapides ; une synthèse par phrase, minutage mot à mot |
| Image | `templates/` | Une page HTML dont chaque image est une fonction du temps (GSAP en pause) |
| Tournage | `engine/render.py` | Chrome sans interface filme la page, un fichier par scène, assemblage sans réencodage |
| Chef d'orchestre | `engine/build.py` | Vérifie le script, enchaîne voix, tournage, montage, vignette, compte rendu |
| Rendu automatique | `.github/workflows/rendu.yml` | Rend chaque nouveau script et publie le résultat sur la branche `media` |

## Changer le style

Couleurs, polices et tailles sont dans les premières lignes de `templates/style.css`. La voix se règle dans `config/voice.json` (voir « Changer la voix » dans `PIPELINE.md`).

## Écrire un reel

Voir `PIPELINE.md` : ligne éditoriale, règles de vérification des faits, format du script, étapes de production et de publication.

## Licences des briques

Chatterbox (MIT), Kokoro (Apache 2.0), GSAP (licence standard gratuite), polices Archivo et Playwrite France Moderne (SIL OFL), ffmpeg, Playwright.
