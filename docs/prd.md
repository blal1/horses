# Jeu de Course a Cheval Audio-First - PRD v2

## 1. Executive Summary

**Problem Statement**  
Les joueurs aveugles ont peu de jeux de course a cheval qui rendent lisibles la position, la vitesse, les concurrents, la piste et les decisions tactiques sans dependance visuelle.

**Proposed Solution**  
Creer un jeu Python Windows audio-first, jouable au clavier et a la manette, centre sur une simulation realiste de course hippique, une carriere narrative et un sound design 3D binaural au casque.

**Success Criteria**

- 100 % des actions principales sont jouables sans ecran.
- Le joueur peut identifier par audio seul sa position relative, les concurrents proches, les virages, la ligne droite, l'endurance et les evenements critiques.
- Le tutoriel est termine sans aide exterieure par au moins 80 % des testeurs aveugles.
- Les feedbacks critiques ont une latence percue inferieure a 50 ms.
- Une course MVP reste stable avec une simulation deterministe a 60 ticks par seconde ou equivalent.
- Les menus, sauvegardes, reglages et boucles de carriere sont navigables en audio-first.

## 2. User Experience & Functionality

### User Personas

- Joueur aveugle amateur de jeux de sport, de competition et de progression.
- Joueur malvoyant souhaitant une experience audio-first, sans obligation d'interface visuelle.
- Joueur narratif souhaitant incarner un jockey, gerer un cheval et progresser dans une carriere.
- Testeur accessibilite voulant rejouer et analyser les courses uniquement par feedback audio.

### User Stories

- As a blind player, I want spatial audio cues so that I can understand where horses, rails, turns, and the finish line are.
- As a player, I want keyboard-only and gamepad controls so that I can play without a mouse or visual UI.
- As a competitive player, I want realistic stamina, pace, terrain and horse behavior so that races reward skill and planning.
- As a narrative player, I want a career mode with training, rivals and story beats so that progression matters beyond one race.
- As a new player, I want a guided audio tutorial so that I can learn controls, pacing and spatial awareness progressively.

### Acceptance Criteria

- Le menu principal, les reglages, le tutoriel, la carriere et une course complete sont navigables sans ecran.
- Chaque concurrent proche est identifiable par position sonore, intensite, timbre ou annonce contextuelle.
- Le joueur recoit des informations non intrusives sur le rang, la distance restante, l'endurance, les virages, les collisions, les accelerations adverses et le sprint final.
- Les sons critiques sont courts, distincts et priorises dans le mix.
- Les reglages incluent des volumes separes pour voix, ambiance, chevaux, concurrents, UI, musique et alertes.
- Le joueur peut demander un resume vocal a tout moment sans interrompre la simulation.
- Le jeu conserve les sauvegardes de carriere, les preferences audio et les statistiques de course.

### Non-Goals MVP

- Monde ouvert 3D.
- Graphismes avances.
- Multijoueur reseau.
- Systeme de pari reel ou argent reel.
- IA generative en temps reel.
- Simulation veterinaire exhaustive.

## 3. Game Design Scope

### Core Loop

1. Choisir ou continuer une carriere.
2. Ecouter le briefing audio : piste, meteo, distance, cheval, adversaires et objectif narratif.
3. Courir : gerer allure, endurance, trajectoire, timing du sprint et reactions aux concurrents.
4. Recevoir le resultat : classement, temps, penalites, performance, gains et consequences narratives.
5. Entrainer le cheval, ameliorer l'equipement, choisir la prochaine course ou avancer dans l'histoire.

### Modes

- **Tutoriel audio progressif** : controles, repere spatial, rythme, virages, sprint, resume vocal.
- **Course rapide** : lancer une course sans engagement de carriere.
- **Mode entrainement** : depart, virages, endurance, sprint final, lecture des concurrents.
- **Carriere MVP** : saison courte, progression du cheval, rivaux, evenements narratifs.
- **Championnat court** : suite de courses avec classement cumule.
- **Statistiques** : historique de courses, victoires, podiums, meilleur temps, progression par cheval et championnat.
- **Replay audio** : relecture textuelle/vocale du dernier resultat et des moments importants.
- **Editeur de pistes audio-first** : creation d'une piste personnalisee navigable au clavier, sauvegardee localement.

### Controls MVP

- Menu : `W/S/A/D`, fleches, `Tab`, `Enter` et `Space` pour naviguer et valider.
- Course : fleche haut, `W` ou `Z` pour augmenter l'allure.
- Course : fleche bas ou `S` pour reduire l'allure.
- Course : fleche gauche, `A` ou `Q` pour aller a gauche ; fleche droite ou `D` pour aller a droite.
- Course : espace ou bouton principal pour pousser le cheval / sprint controle.
- Course : `J` pour sauter un obstacle bas ou horizontal.
- Course : `K` ou `Ctrl` pour passer sous un obstacle bas suspendu.
- Course : `Tab` ou `Enter` pour demander un resume vocal immediat.
- Course : `R` pour repeter le dernier message important.
- Course : `M` pour revenir au menu apres course, `N` pour relancer, `Echap` pour quitter.
- F1 : aide contextuelle vocale.

### Simulation Realiste MVP

- Chaque cheval possede vitesse maximale, acceleration, endurance, recuperation, nervosite, maniabilite et preference de terrain.
- L'allure consomme l'endurance selon vitesse, pente, meteo, terrain et fatigue.
- Le sprint final donne un gain court mais augmente fortement la fatigue.
- La trajectoire influence la distance parcourue et le risque de contact.
- Les adversaires ont des strategies : economiser, partir fort, attendre la ligne droite, bloquer l'interieur.
- Les collisions ou frottements reduisent vitesse, stabilite et concentration.
- La meteo influence adherence, fatigue, ambiance sonore et annonces de briefing.

### Obstacles v2

- Les obstacles ne sont plus uniquement evites par changement de voie.
- Chaque obstacle declare une action recommandee : `dodge`, `jump` ou `duck`.
- `dodge` : changer de voie avant l'impact.
- `jump` : rester dans la voie et appuyer sur `J` au bon moment.
- `duck` : rester dans la voie et appuyer sur `K` ou `Ctrl` pour passer dessous.
- Une mauvaise action ou aucune action sur la meme voie declenche une penalite de vitesse temporaire.
- Les avertissements audio annoncent l'obstacle, la voie et l'action utile.

### Career Narrative MVP

- Le joueur incarne un jockey debutant.
- La carriere contient une ecurie, un cheval principal, un entraineur, des rivaux et des courses clefs.
- Les choix entre entrainement, repos et course modifient la forme du cheval.
- Les resultats debloquent courses, dialogues, reputations et ameliorations.
- La narration reste concise et non intrusive, avec option de repetition.

### Progression v2

- Le championnat utilise un calendrier JSON structure en plusieurs manches.
- Chaque course de carriere peut imposer piste, meteo, briefing et ecuries rivales.
- Les ecuries fournissent des bonus legers et lisibles qui influencent le cheval joueur ou les rivaux.
- Les statistiques persistent les resultats de course et les points de championnat.
- Le dernier replay audio est conserve pour consultation depuis le menu.

## 4. Technical Specifications

### Platform

- Cible principale : Windows.
- Langage : Python 3.12 par defaut.
- Experience : audio-first a 100 %, casque obligatoire recommande pour spatialisation binaurale.
- Interface visuelle : aucune dependance fonctionnelle. Une fenetre minimale de debug pourra exister en developpement, mais pas comme surface de jeu principale.

### Architecture Overview

```text
horse_racing_game/
  app/
    main.py
    config.py
    bootstrap.py
  domain/
    horse.py
    jockey.py
    race.py
    track.py
    weather.py
    career.py
    progression.py
  simulation/
    race_engine.py
    movement.py
    stamina.py
    ai_jockey.py
    collision.py
    race_events.py
    clock.py
  audio/
    audio_engine.py
    spatial_mixer.py
    sound_events.py
    voice_announcer.py
    accessibility_mix.py
    audio_assets.py
  input/
    keyboard.py
    gamepad.py
    command_mapper.py
    commands.py
  ui/
    audio_menu.py
    settings_menu.py
    tutorial_flow.py
    pause_menu.py
  content/
    tracks.json
    horses.json
    career_events.json
    sound_manifest.json
  persistence/
    save_repository.py
    settings_repository.py
  tests/
    simulation/
    audio_events/
    career/
```

### Component Responsibilities

- `domain` : modeles purs du jeu, regles metier, donnees de course et progression.
- `simulation` : moteur deterministe, tick-based, sans dependance audio ou UI.
- `audio` : transformation des evenements de jeu en sons 3D, voix, earcons et priorites de mixage.
- `input` : mapping clavier/manette vers commandes abstraites.
- `ui` : menus audio-first, tutoriels, pause et reglages.
- `content` : donnees editables hors code pour pistes, chevaux, sons et evenements de carriere.
- `persistence` : sauvegardes JSON ou SQLite selon complexite finale.
- `tests` : validation deterministic simulation, evenements audio et progression.

### Data Flow

```text
Input Device
  -> Command Mapper
  -> Race Engine
  -> Race Events
  -> Audio Event Bus
  -> Spatial Mixer / Voice Announcer
  -> Headphones

Race Engine
  -> Race Result
  -> Career Progression
  -> Save Repository
```

### Key Architecture Decision

Le moteur de simulation doit etre strictement independant de l'audio, de l'UI et des peripheriques. Il expose un etat lisible et produit des evenements structures. L'audio consomme ces evenements et decide comment les rendre audibles selon priorite, distance, angle et contexte.

### Core Domain Entities

- `Horse` : statistiques, forme, fatigue, traits, historique.
- `Jockey` : experience, style, reputation, relation avec le cheval.
- `Track` : longueur, virages, surface, couloirs, points de repere audio.
- `Race` : participants, meteo, distance, conditions de victoire, seed deterministe.
- `RaceState` : positions, vitesses, endurance, temps, classement courant.
- `RaceEvent` : depart, virage, depassement, fatigue, contact, sprint, arrivee.
- `CareerState` : saison, argent fictif, progression, chevaux, rivaux, evenements narratifs.

### Audio 3D Requirements

- Le listener audio est centre sur le cheval du joueur.
- Les adversaires sont places en 3D relative : avant, arriere, gauche, droite, proche, loin.
- Les rails, la foule, le vent, la respiration, les sabots, les concurrents et la ligne d'arrivee ont des couches separees.
- Les sons critiques sont priorises : danger > controles > position > endurance > ambiance > musique.
- Les annonces vocales ne doivent pas masquer les indices critiques de trajectoire ou de concurrents.
- Le joueur peut choisir densite vocale : minimale, normale, descriptive.
- Le mix doit permettre de jouer au casque sans fatigue auditive excessive.

### Asset Generation Requirements

- Les assets telecharges restent references dans `content/sound_manifest.json`.
- Les assets generes par ElevenLabs sont specifies dans `content/elevenlabs_audio_prompts.json`.
- Les sorties ElevenLabs vont dans `assets/generated/elevenlabs/`.
- Le manifest genere est separe : `content/generated_elevenlabs_sound_manifest.json`.
- La fusion dans `content/sound_manifest.json` doit rester explicite via `--merge-manifest`.
- Les prompts ElevenLabs couvrent UI, course, chevaux, surfaces, meteo, obstacles, progression, replay, editeur, ecuries et musiques.
- Les SFX ElevenLabs dont le fichier existe localement sont charges automatiquement au runtime depuis la spec ; les musiques ElevenLabs ne sont pas auto-chargees.

### Audio Event Examples

- `RaceStarted` : compte a rebours et portail de depart.
- `OpponentApproachingLeft` : sabots lateralises a gauche, intensite progressive.
- `OpponentPassingRight` : mouvement sonore arriere-droite vers avant-droite.
- `TurnIncoming` : annonce courte + repere sonore rail interieur.
- `LowStamina` : respiration du cheval plus lourde + alerte discrete.
- `CollisionRisk` : son court prioritaire positionne dans la direction du risque.
- `FinalStretch` : changement d'ambiance, foule plus presente, annonce courte.
- `FinishLineCrossed` : confirmation, classement, temps.

### Python Architecture Standards

- Python 3.12.
- Types explicites sur les APIs publiques.
- `pathlib.Path` pour les chemins.
- Interfaces via classes abstraites pour audio, input et persistence.
- Simulation pure et testable sans audio.
- Donnees de contenu separees du code.
- Aucun acces fichier ou initialisation audio au niveau import module.
- Variables declarees pres de leur usage.

## 5. Testing Strategy

### Automated Tests

- Tests unitaires du moteur de course : vitesse, endurance, acceleration, virages, collisions.
- Tests deterministes avec seed fixe pour les courses IA.
- Tests de mapping : commande entree -> intention jeu.
- Tests audio event mapping : chaque evenement critique produit le bon type de feedback.
- Tests de progression : resultats de course, debloquages, sauvegarde et chargement.

### Accessibility Tests

- Scenarios joues ecran eteint : tutoriel, course rapide, pause, reglages, carriere.
- Test de lisibilite audio avec plusieurs concurrents proches.
- Test de fatigue auditive sur sessions de 20 a 30 minutes.
- Test de comprehension des annonces en mode minimal, normal et descriptif.

### Definition of Done MVP

- Lancer le jeu depuis Windows.
- Naviguer le menu principal par audio.
- Terminer le tutoriel de base.
- Jouer une course complete contre IA.
- Comprendre le classement et les evenements principaux par audio.
- Sauvegarder reglages et progression.
- Executer les tests simulation sans backend audio.

## 6. Risks & Roadmap

### Risks

- La spatialisation 3D en Python peut imposer un choix de backend audio plus complexe que prevu.
- Trop de voix peut reduire la lisibilite des sons spatiaux.
- Une simulation trop realiste peut devenir opaque sans aides audio bien calibrees.
- Les sons binauraux peuvent etre perçus differemment selon casque, audition et fatigue.
- Le support manette Windows peut varier selon les peripheriques.

### Mitigations

- Construire d'abord un moteur d'evenements audio abstrait avec backend remplacable.
- Tester tres tot avec des courses sans graphismes.
- Ajouter des profils de mixage : competition, descriptif, apprentissage.
- Garder le tutoriel comme banc de test permanent pour chaque feature.
- Mettre les parametres audio dans des fichiers de configuration faciles a ajuster.

### Phased Rollout

**MVP**

- Course rapide.
- Tutoriel complet.
- 3 chevaux.
- 2 pistes.
- 5 adversaires IA.
- Audio 3D de base.
- Menus audio-first.
- Sauvegarde reglages et progression minimale.

**v1.1**

- Carriere courte.
- Meteo.
- Entrainement cheval.
- Rivaux narratifs.
- Amelioration du mixage et profils audio.

**v2.0**

- Championnat complet.
- Plusieurs ecuries.
- Replays audio.
- Editeur de pistes audio-first.
- Statistiques avancees.
- Option multijoueur a evaluer apres stabilisation du solo.

## 7. Etat d'Implementation Actuel

- Menu audio-first branche dans `horse_racing_game/ui/pygame_menu.py` avec 13 entrees : Horse, Track, Weather, Audio, Stable, Quick Race, Tutorial, Training, Career, Replay, Track Editor, Statistics, Quit.
- Course pygame jouable via `play_game.py`, `PLAY_GAME.bat` et `horse_racing_game.__main__.main`.
- TTS NVDA supporte via `nvdaControllerClient64.dll` a la racine du projet.
- Musiques MP3 existantes gerees separement via `pygame.mixer.music`.
- SFX ElevenLabs generes integres automatiquement dans le catalogue audio court, avec fallback vers les assets Kenney/Mixkit existants.
- Progression sauvegardee dans `save/progress.json`.
- Pistes personnalisees sauvegardees dans `save/custom_tracks.json`.
- Contenu v2 present : `content/weather.json`, `content/rivals.json`, `content/stables.json`, `content/championship.json`.
- Generateur ElevenLabs present : `scripts/generate_elevenlabs_audio.py`.
- Spec de generation : 66 assets planifies, dont 59 sound effects et 7 musiques.
- Catalogue runtime local : 207 sons, dont 59 SFX ElevenLabs generes ; musiques ElevenLabs non utilisees par defaut.
- Tests automatises actuels : `82 passed, 2 subtests passed`.
