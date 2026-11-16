# Mode opératoire de la fabrique

Ce fichier est la consigne suivie à chaque exécution, par une personne ou par une tâche planifiée.
Il y a deux passages distincts : **produire** un reel, puis **publier** les reels validés.

## Qui fait quoi

| Étape | Où | Détail |
|---|---|---|
| Sujet, recherche, script, contrôle des images | session Claude | écrit `content/<id>.json` et le pousse sur `main` |
| Voix naturelle, tournage, montage | GitHub Actions (`.github/workflows/rendu.yml`) | se déclenche tout seul à l'arrivée du script |
| Hébergement de la vidéo | branche `media` du dépôt | `<id>.mp4`, `<id>.jpg`, `status/<id>.json` |
| Validation | tableau « Reels – file de validation » | le propriétaire coche « Validé » |
| Publication | connecteur vidIQ | uniquement les lignes cochées |

## Ligne éditoriale

- Culture générale et faits étonnants : histoire, économie, nouvelles technologies, parfois un sujet plus technique (IA et domaines voisins).
- Public : jeunes actifs et étudiants de M1/M2. Vulgarisation grand public : on apprend quelque chose sans être perdu.
- Un reel = une seule idée, portée par un chiffre ou une date qui surprend.
- Alterner les thèmes d'un reel à l'autre et ne jamais refaire un sujet déjà présent dans la file de validation.

## Règles de vérification (non négociables)

1. Chaque chiffre, date ou fait affirmé est recoupé sur **deux sources indépendantes**, dont au moins une institutionnelle ou primaire (organisme public, musée, article scientifique, publication d'origine).
2. Les faits et leurs sources sont consignés dans le champ `facts` du script. Un fait sans deux sources est retiré ; si l'idée centrale ne tient plus, on change de sujet.
3. Quand deux sources divergent, on prend la plus institutionnelle et on formule prudemment (« moins de quatre jours » plutôt que « 3,7 jours »).
4. Tout calcul affiché à l'écran (multiplication, écart) est refait à partir des chiffres sourcés.
5. Aucune image réaliste générée par IA, aucune photo de personne réelle : le format est typographie, schémas et courbes.
6. Les sources principales sont affichées dans la dernière scène et citées dans la légende.
7. Pas de sujet d'actualité brûlante, pas de prise de position politique, pas de conseil médical, juridique ou financier.

## Format

- Vertical 1080 × 1920, 30 images/s, 35 à 60 secondes, 5 à 7 scènes.
- Première phrase : le fait qui accroche, avec son chiffre. Dernière phrase : ce qu'il faut retenir.
- 100 à 130 mots dits. Phrases courtes, une information par phrase.
- Nombres écrits en chiffres avec une espace fine insécable (U+202F) entre les milliers : `4 200`.

## Le script (`content/AAAA-MM-JJ-sujet.json`)

Champs obligatoires : `id` (identique au nom du fichier, commence par la date), `title`, `theme`, `scenes`, `facts`, `sources` (2 au minimum), `captions` (`short`, `youtube_title` de 100 caractères au plus, `youtube_description`).

Chaque scène a une `narration` (le texte dit) et des `blocks` (ce qui s'écrit à l'écran) :

| `kind` | Rôle | Champs |
|---|---|---|
| `big` | phrase forte | `lines` |
| `txt` | phrase courante | `lines` |
| `num` | nombre géant (réduit automatiquement s'il déborde) | `lines` |
| `small` | mention discrète, sources | `lines` |
| `hand` | annotation manuscrite au stylo rouge (`"blue": true` pour l'encre) | `lines` |
| `timeline` | frise : la marge rouge sert d'axe | `events[]` : `note`, `title`, `sub`, `at` |
| `chart` | courbe tracée sur les carreaux (1 carreau = 1 an, 1 carreau = × 100) | `title`, `hint`, `x`, `y`, `points`, `split`, `spikeAt`, `endLabel`, `endNote` |

Communs à tous les blocs :

- `at` : le bloc apparaît quand la voix prononce ces mots (ex. `"at": "200 milliards"`). C'est le seul repère fiable : la voix finale n'a pas le même débit que la voix de contrôle. N'utiliser `delay` (secondes depuis le début de la scène) qu'en dernier recours.
- `markAt` : moment où partent surligneur et traits de stylo.
- `gap` : espace au-dessus, en carreaux. `note` : date écrite dans la marge (une ou deux lignes courtes).
- Dans une ligne : `==texte==` surligne, `~~texte~~` barre au stylo rouge, `__texte__` souligne.
- `hold` (sur la scène) : secondes de silence ajoutées à la fin, pour laisser lire ce qui vient d'apparaître.
- Une ligne tient dans 800 px : au-delà d'environ 16 caractères en `big`, 28 en `txt`, couper en deux lignes.

Le modèle à suivre est `content/2026-11-16-pain-200-milliards.json`.

## Passage 1 : produire

1. `bash setup.sh` (installe la voix de contrôle et le tournage).
2. Lire la file de validation : sujets déjà traités, lignes dont le statut est « À corriger ».
3. S'il y a une ligne « À corriger », refaire ce reel d'abord : appliquer les corrections, donner au script un nouvel identifiant terminé par `-v2`, `-v3`… Si la correction dit « refusé », ne rien refaire.
4. Sinon choisir un sujet, chercher, recouper, écrire le script.
5. `python3 engine/build.py content/<id>.json --stills` puis **regarder chaque image**. Corriger tout débordement et tout avertissement « repère introuvable » ou « contenu trop haut ». Ce contrôle utilise la voix Kokoro : la mise en page est la même qu'au rendu final.
6. Pousser le script sur `main`. Le rendu final démarre seul sur GitHub (10 à 20 minutes).
7. Attendre le compte rendu : `git fetch -q origin media && git show FETCH_HEAD:status/<id>.json`. Réessayer toutes les deux minutes, 40 minutes au plus.
   - `"ok": true` : la vidéo est à `https://raw.githubusercontent.com/<dépôt>/media/<id>.mp4`.
   - `"ok": false` : lire `error`, corriger le script si c'est lui le fautif, repousser une fois. Au second échec, s'arrêter et le signaler.
8. Importer la vidéo dans vidIQ, créer le brouillon de publication si des comptes sont connectés, puis ajouter la ligne dans la file. La case « Validé » reste décochée.
9. Prévenir que le reel attend sa validation.

## Passage 2 : publier

Un reel n'est publié que si **toutes** ces conditions sont réunies :

- la case « Validé » de sa ligne est cochée par le propriétaire de la chaîne ;
- son brouillon existait déjà au passage précédent et n'a pas changé depuis (même référence) ;
- les réglages de l'onglet « Réglages » sont remplis pour la plateforme concernée (visibilité, commentaires et musique pour TikTok, visibilité pour YouTube). Ces choix appartiennent au créateur : on ne les remplit jamais à sa place.

Après publication : écrire la date et les liens dans la ligne. En cas d'échec, écrire la raison dans « Contrôle avant publication » et ne pas réessayer en boucle.

## Changer la voix

Le réglage est dans `config/voice.json` : moteur, clip de référence (`voices/reference-fr.wav`), expressivité (`exaggeration`) et tenue (`cfg_weight`).
Pour comparer des réglages à l'oreille, modifier `voices/essais.txt` et pousser : les essais arrivent dans `voix-essais/` sur la branche `media`.
Un fichier `voices/ma-voix.wav` (15 secondes de voix propre, sans bruit) ajoute un essai avec cette voix.
