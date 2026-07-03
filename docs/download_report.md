# Rapport de Ressources Audio et Contenu

Date : 24 juin 2026

Mise a jour : 25 juin 2026

## Telecharge

### Kenney Interface Sounds

- Source : https://kenney.nl/assets/interface-sounds
- Archive : `assets/downloads/kenney_interface-sounds.zip`
- Extraction : `assets/downloads/kenney_interface-sounds/`
- Fichiers audio extraits : 100 `.ogg`
- Licence : CC0
- Preuves locales :
  - `assets/licenses/kenney_interface-sounds.html`
  - `assets/licenses/kenney_support.html`
  - `assets/downloads/kenney_interface-sounds/License.txt`

### Mixkit Sound Effects

- Source principale : https://mixkit.co/free-sound-effects/
- Dossier : `assets/downloads/mixkit/`
- Fichiers audio telecharges : 48
- Formats : 47 `.wav`, 1 `.mp3`
- Categories :
  - `horse`
  - `crowd`
  - `rain`
  - `wind`
  - `interface`
  - `countdown`
- Journal brut : `assets/downloads/mixkit/downloaded_mixkit_assets.json`
- Licence : Mixkit Free Sound Effects License
- Preuves locales :
  - `assets/licenses/mixkit_game_sfx.html`
  - `assets/licenses/mixkit_license.html`

### OpenGameArt

- Source : https://opengameart.org/content/library-of-game-sounds
- Page sauvegardee : `assets/licenses/opengameart_library_of_game_sounds.html`
- Audio non telecharge automatiquement, car les licences varient par asset.

## Contenu Cree

- `content/horses.json` : 8 chevaux fictifs et calibrables.
- `content/tracks.json` : 2 pistes fictives.
- `content/sound_manifest.json` : 148 sons references avec provenance, licence, categorie et chemin.
- `content/weather.json` : 3 conditions meteo (`clear`, `windy`, `rain`).
- `content/rivals.json` : 4 rivaux narratifs.
- `content/stables.json` : 3 ecuries avec bonus de gameplay.
- `content/championship.json` : 3 manches de championnat avec piste, meteo, briefing et ecuries rivales.
- `content/elevenlabs_audio_prompts.json` : 66 assets audio a generer via ElevenLabs.
- `scripts/generate_elevenlabs_audio.py` : generateur ElevenLabs avec `--dry-run`, `--only`, `--kind`, `--force`, `--merge-manifest`.

## Assets ElevenLabs

Ces fichiers sont des assets planifies et generables avec une cle `ELEVENLABS_API_KEY`. Dans l'etat local actuel, les 59 sound effects existent sur disque et sont charges automatiquement par le jeu depuis la spec si leur fichier est present.

- Sortie audio : `assets/generated/elevenlabs/`.
- Manifest genere : `content/generated_elevenlabs_sound_manifest.json`.
- Fusion dans `content/sound_manifest.json` uniquement via `--merge-manifest`.
- Total planifie : 66 assets.
- Sound effects : 59.
- Musiques : 7.
- Sound effects charges au runtime local : 59.
- Musiques ElevenLabs chargees au runtime : 0, les MP3 telecharges restent utilises via `pygame.mixer.music`.

Categories couvertes :

- UI : navigation, confirmation, annulation, erreur, panel, sauvegarde.
- Course : compte a rebours, depart, adversaires, collisions, virages, final stretch, arrivee.
- Chevaux : loops marche/trot/canter/galop, surfaces turf/dirt/mud/sand, respiration, vocalisations, tack, stumble, saut, freinage, lane change, photo finish.
- Ambiances : foule, vent, pluie, ecuries.
- Progression : entrainement, points carriere, standings championnat.
- Outils : replay audio et editeur de pistes.
- Musiques : menu, course, final stretch, entrainement, briefing championnat, victoire, defaite.

## Bloque ou Non Telecharge

### Pixabay

- Pages visees :
  - https://pixabay.com/sound-effects/search/horse/
  - https://pixabay.com/music/search/horse%20racing/
  - https://pixabay.com/service/license-summary/
- Etat : bloque par challenge Cloudflare depuis PowerShell.
- Decision : ne pas contourner. A recuperer manuellement depuis le navigateur ou via une API autorisee si une cle est fournie.

### Freesound

- Page visee : https://freesound.org/help/faq/
- Etat : 403 depuis PowerShell.
- Decision : ne pas contourner. A utiliser plus tard via compte/API officielle, en filtrant CC0 ou CC BY.

### Sonniss GameAudioGDC

- Source : https://sonniss.com/gameaudiogdc/
- Etat : bloque par challenge Cloudflare depuis PowerShell.
- Decision : ne pas contourner. Les bundles complets sont massifs ; il faudra choisir explicitement les archives a recuperer si tu veux les stocker localement.

### Big Data Derby 2022 / Kaggle

- Source : https://www.kaggle.com/competitions/big-data-derby-2022/data
- Etat : non telecharge.
- Cause : CLI Kaggle absente et dataset probablement soumis a authentification/acceptation des conditions Kaggle.
- Decision : telecharger plus tard avec un compte Kaggle/API token si necessaire pour calibration avancee.

## Verification

- Fichiers audio telecharges references : 148.
- Manifest audio principal : 148 entrees.
- Catalogue audio runtime local : 207 entrees, dont 59 SFX ElevenLabs ajoutes dynamiquement.
- Chevaux JSON : 8 entrees.
- Pistes JSON : 2 entrees.
- Prompts ElevenLabs : JSON valide.
- Dry-run ElevenLabs sound effects : 59 assets planifies.
- Obstacles JSON : actions `dodge`, `jump` et `duck` validees.
- Tests projet apres integration des SFX ElevenLabs generes et obstacles multi-actions : `82 passed, 2 subtests passed`.
