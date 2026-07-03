# Recherche Web - Donnees Chevaux et Ressources Audio

Recherche effectuee le 24 juin 2026.

## Objectif

Identifier des sources utilisables pour :

- donnees de chevaux, pistes et courses ;
- fichiers JSON de contenu pour le jeu ;
- effets sonores de chevaux, sabots, foule, meteo, UI/navigation ;
- musiques libres ou licenciables ;
- contraintes de licence a respecter avant integration.

## Recommandation Courte

Pour le MVP, ne pas bloquer l'implementation sur un gros dataset externe. Construire d'abord nos propres fichiers JSON de gameplay (`horses.json`, `tracks.json`, `sound_manifest.json`) avec valeurs synthetiques mais plausibles, puis utiliser les datasets publics pour calibrer vitesse, rythme, ecarts et comportements.

Pour l'audio, utiliser :

- Kenney pour les sons de navigation UI en CC0.
- Pixabay ou Freesound CC0/CC BY pour sons de chevaux.
- Mixkit ou Sonniss pour foule, meteo, impacts, whooshes et couches supplementaires.
- ElevenLabs pour generer des SFX et musiques specifiques au gameplay audio-first quand les assets libres ne couvrent pas assez finement les besoins.
- Eviter les fichiers Freesound en CC BY-NC ou Sampling+ si le jeu peut etre distribue publiquement ou commercialement.

## Donnees Chevaux et Courses

### Big Data Derby 2022 / Kaggle

Source : https://www.kaggle.com/competitions/big-data-derby-2022/data

Utilite :

- Donnees de course a granularite fine.
- Le papier associe indique que les donnees NYRA/NYTHA incluent du tracking frame-level pour tous les chevaux a environ 4 Hz sur des courses d'un mile.
- Utile pour calibrer les profils de vitesse, les phases de course, l'effet du couloir et les mouvements lateraux.

Contraintes :

- Acces via Kaggle, probablement compte requis.
- Verifier les conditions de competition/dataset avant redistribution.
- A utiliser comme reference de calibration, pas forcement a embarquer dans le jeu.

Decision :

- Recommande pour v1.1+ ou calibration avancee.
- Pas necessaire pour le squelette MVP.

### Donnees encyclopediques / resultats publics

Sources possibles :

- Pages Wikipedia de courses et chevaux.
- Sites officiels de courses selon pays.
- Equibase / JRA / Racing Post selon conditions d'utilisation.

Utilite :

- Noms de courses, distances, surfaces, temps historiques, records.
- Calibration generale des distances : 1200 m, 1600 m, 2000 m, 2400 m.
- Inspiration narrative et structure de championnat.

Contraintes :

- Ne pas scraper automatiquement sans verifier les conditions d'utilisation.
- Les noms reels de chevaux/personnes peuvent compliquer les droits, la moderation et l'authenticite.

Decision :

- Pour le jeu, utiliser des noms fictifs.
- Utiliser les donnees publiques seulement pour inspirer des fourchettes realistes.

## Structure JSON Recommandee

### `content/horses.json`

```json
[
  {
    "horse_id": "ember_stride",
    "name": "Ember Stride",
    "preferred_surface": "turf",
    "signature_sound": "horse_ember_breath",
    "stats": {
      "max_speed_mps": 17.2,
      "acceleration": 7.8,
      "stamina_capacity": 82.0,
      "stamina_recovery": 4.5,
      "handling": 8.0,
      "nervousness": 3.5
    },
    "traits": ["fast_finisher", "calm_in_crowd"]
  }
]
```

### `content/tracks.json`

```json
[
  {
    "track_id": "ashford_oval",
    "name": "Ashford Oval",
    "length_m": 1600.0,
    "surface": "turf",
    "lanes": 8,
    "segments": [
      {
        "start_m": 0.0,
        "end_m": 400.0,
        "curve_direction": "none",
        "curve_intensity": 0.0,
        "slope": 0.0,
        "audio_marker": "grandstand_left"
      }
    ]
  }
]
```

### `content/sound_manifest.json`

```json
[
  {
    "sound_id": "ui_move",
    "path": "audio/ui/kenney_ui_move.wav",
    "source": "Kenney Interface Sounds",
    "license": "CC0",
    "category": "ui",
    "loop": false,
    "default_volume": 0.65,
    "priority": 40
  }
]
```

## Audio - Sources Recommandees

### Kenney Interface Sounds

Source : https://kenney.nl/assets/interface-sounds

Points utiles :

- Pack dedie aux sons d'interface.
- 100 fichiers.
- Licence Creative Commons CC0 indiquee sur la page.
- Attribution non requise selon la page support de Kenney.

Usage recommande :

- Navigation menu.
- Confirmation.
- Retour/annulation.
- Selection.
- Erreur non critique.

Decision :

- Source prioritaire pour les sons de navigation audio-first.

### Pixabay Sound Effects

Source : https://pixabay.com/sound-effects/search/horse/

Points utiles :

- Recherche "horse" avec plusieurs centaines de sons.
- Resultats pertinents : neigh, galloping, snort, whinny, horse running, walking.
- Licence Pixabay : usage gratuit, attribution non obligatoire, modification autorisee, avec restrictions sur redistribution standalone et autres usages interdits.

Usage recommande :

- Sons de chevaux MVP : hennissement, galop, respiration, passage proche.
- Prototypage rapide.

Decision :

- Bonne source pour placeholders et premiers assets.
- Verifier chaque page d'asset avant inclusion definitive.

### Freesound

Source : https://freesound.org

Points utiles :

- Grande base collaborative de sons sous licences Creative Commons.
- Licences possibles : CC0, CC BY, CC BY-NC, anciennes licences Sampling+.
- Freesound fournit une attribution list pour aider a credit.

Usage recommande :

- Sons specifiques introuvables ailleurs : chevaux sur surfaces variees, foules, exterieurs, meteo.
- Preferer CC0.
- Accepter CC BY seulement si attribution geree dans `CREDITS.md`.

Decision :

- Bonne source secondaire.
- Interdire CC BY-NC et Sampling+ pour le projet distribue.

### Sonniss GameAudioGDC

Source : https://sonniss.com/gameaudiogdc/

Points utiles :

- Archives gratuites GameAudioGDC.
- Sons royalty-free, commercialement utilisables, attribution non requise selon la page.
- La page precise que les sons sont pour media production : games, film, TV, interactive projects.
- Interdiction explicite pour entrainement AI/ML.

Usage recommande :

- Ambiances, impacts, whooshes, foule, meteo, sons de matiere.
- Couche de production plus riche que les packs gratuits simples.

Decision :

- Bonne source pour enrichir le sound design.
- Ne pas utiliser pour entrainement ML.
- Conserver le fichier de licence avec les assets.

### Mixkit

Source : https://mixkit.co/free-sound-effects/game/

Points utiles :

- Sons gratuits `.wav` et `.mp3`.
- Categories utiles : game, interface, crowd, applause, wind, rain, whoosh, countdown.
- Page indique usage commercial/personnel et attribution non requise pour sound effects.

Usage recommande :

- Countdown, crowd, applause, wind, rain, UI alternatifs.
- Bons placeholders pour le prototype.

Decision :

- Source pratique pour sons d'ambiance et feedbacks courts.
- Lire la licence specifique avant redistribution.

### ElevenLabs Sound Effects / Music

Source : https://elevenlabs.io/

Points utiles :

- Generation de sons courts a partir de prompts textuels.
- Generation de musiques instrumentales pour menu, course, entrainement et resultats.
- Permet de creer des cues tres specifiques au gameplay : allures de chevaux, surfaces, alertes accessibles, editeur audio-first, progression et ecuries.

Usage recommande :

- Completer les assets libres quand un son doit etre lisible, court et coherent avec l'interface audio-first.
- Generer plusieurs variantes de sabots/allures pour distinguer vitesse, surface, fatigue et proximite.
- Garder les musiques basses, duckables et desactivables pour ne pas masquer les indices de course.

Contraintes :

- Utiliser uniquement via API officielle et cle `ELEVENLABS_API_KEY`.
- Verifier les conditions du plan ElevenLabs avant distribution publique ou commerciale.
- Documenter la provenance comme `ElevenLabs generated audio` dans le manifest genere.
- Ne pas melanger automatiquement ces assets avec les assets telecharges sans validation humaine.

Decision :

- Maintenir une spec separee dans `content/elevenlabs_audio_prompts.json`.
- Generer vers `assets/generated/elevenlabs/`.
- Ecrire `content/generated_elevenlabs_sound_manifest.json`.
- Fusionner dans `content/sound_manifest.json` seulement avec `--merge-manifest`.

### OpenGameArt

Source : https://opengameart.org/content/library-of-game-sounds

Points utiles :

- Collection de sons de jeu incluant UI, buttons, footsteps, wind, rain/thunder.
- Les licences varient selon asset.
- OpenGameArt peut generer un fichier de credits, mais precise que l'attribution reste la responsabilite du projet.

Usage recommande :

- Completer les sons UI ou meteo si Kenney/Mixkit ne suffisent pas.

Decision :

- Utiliser seulement si la licence de chaque asset est verifiee.
- Preferer CC0.

## Musiques

### Pixabay Music

Source : https://pixabay.com/music/search/horse%20racing/

Points utiles :

- Recherche "horse racing" retourne des musiques royalty-free, dont styles country, cinematic, sport, racing.
- Licence Pixabay : attribution non obligatoire, modification autorisee, restrictions sur redistribution standalone.

Usage recommande :

- Menu principal.
- Ecurie/carriere.
- Resultat de course.

Decision :

- Utiliser la musique avec parcimonie : le jeu repose sur la lisibilite audio, donc la musique doit etre duckable et desactivable.

### Mixkit Music

Source : https://mixkit.co/free-stock-music/

Points utiles :

- Musiques gratuites sous licence Mixkit par type d'item.
- Utile pour themes de menu et transitions.

Usage recommande :

- Musique de menu basse intensite.
- Pas pendant les phases critiques de course, sauf mix tres bas.

Decision :

- Option secondaire apres Pixabay.

## Politique de Licence du Projet

Chaque asset ajoute au jeu doit avoir une entree dans `content/sound_manifest.json` avec :

- `sound_id`
- `path`
- `source`
- `source_url`
- `author`
- `license`
- `license_url`
- `requires_attribution`
- `downloaded_at`
- `allowed_for_commercial_use`
- `notes`

Regles :

- Accepter : CC0, licences commerciales claires, Pixabay License, Mixkit Free License, Sonniss media production license.
- Accepter avec credits : CC BY.
- Eviter/interdire : CC BY-NC, Sampling+, assets sans licence claire, assets avec interdiction d'usage jeu, assets generes ou douteux sans droits clairs.
- Conserver les fichiers de licence dans `assets/licenses/`.
- Generer un `CREDITS.md` des que l'on ajoute un asset non-CC0.
- Pour les assets generes par IA, conserver le prompt, le modele si disponible, la date de generation et les conditions du fournisseur.

## Plan D'Action

1. Conserver `content/sound_manifest.json` comme source des assets telecharges et verifies.
2. Utiliser `content/elevenlabs_audio_prompts.json` pour les assets generes a la demande.
3. Lancer d'abord `python scripts/generate_elevenlabs_audio.py --dry-run`.
4. Generer par petits lots avec `--only` pour valider la qualite sonore avant generation massive.
5. Generer les SFX chevaux en priorite : allures, surfaces, respiration, vocalisations, tack et erreurs de course.
6. Generer les musiques seulement apres validation que le mix ne masque pas les indices critiques.
7. Fusionner le manifest genere seulement apres ecoute et validation licence : `--merge-manifest`.
8. Creer un script interne de validation manifest : chaque fichier reference existe et chaque licence est renseignee.
