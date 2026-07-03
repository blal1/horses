# Design Technique - Moteur de Course, Audio 3D et Assets Generes

## Objectif

Ce document transforme le PRD en architecture implementable. Il couvre le moteur de simulation, les evenements de jeu, le pipeline audio 3D, les interfaces Python et la premiere tranche de developpement.

Le principe central reste le meme : la simulation ne connait pas l'audio, l'UI ou les peripheriques. Elle recoit des commandes abstraites et produit un etat de course plus des evenements structures.

## Decisions Techniques

- Plateforme cible : Windows.
- Python cible : 3.12.
- Experience : audio-first, casque avec spatialisation binaurale.
- Simulation : tick-based, deterministe, testable sans audio.
- Backend audio : interchangeable derriere une interface.
- Persistance MVP : fichiers JSON UTF-8 via `pathlib.Path`.
- Contenu MVP : JSON pour chevaux, pistes, sons, evenements narratifs.
- Contenu v2 : JSON pour meteo, rivaux, ecuries, calendrier championnat, prompts ElevenLabs et pistes personnalisees.
- Interfaces internes : ABC explicites.
- Pas d'I/O, chargement audio ou lecture de configuration au moment des imports.
- Les assets ElevenLabs sont generes hors manifest principal par defaut pour eviter d'ecraser les assets telecharges.

## Architecture Runtime

```text
App Bootstrap
  -> Load Settings
  -> Load Content
  -> Create Input Backend
  -> Create Audio Backend
  -> Create Game Coordinator
  -> Start Main Loop

Main Loop
  -> Poll Input
  -> Map Input to Commands
  -> Tick Simulation
  -> Publish Race Events
  -> Render Audio Frame
  -> Update Menus / Career Flow
```

Runtime actuel : `play_game.py` appelle `horse_racing_game.app.pygame_main.main`. L'UI pygame coordonne menu, course, tutoriel, entrainement, carriere, replay, editeur de pistes et statistiques.

## Modules Principaux

### `app`

Responsabilites :

- Demarrer le jeu.
- Construire les dependances.
- Charger les reglages et le contenu.
- Tenir la boucle principale.
- Gerer les erreurs terminales avec message vocal ou sortie claire.

Fichiers :

- `app/main.py` : point d'entree.
- `app/bootstrap.py` : construction des services.
- `app/game_app.py` : boucle principale et coordination haut niveau.
- `app/config.py` : objets de configuration, pas de lecture fichier a l'import.
- `app/progress.py` : sauvegarde JSON des preferences, progression, stats et dernier replay.
- `app/training.py` : actions d'entrainement et effets sur le cheval.
- `app/career.py` : progression carriere.
- `app/championship.py` : calendrier, points, standings et ecuries rivales.
- `app/stats.py` : agregats de resultats et records.
- `app/replay.py` : resume textuel/vocal du dernier resultat.
- `app/track_editor.py` : modele de piste personnalisee audio-first.

### `domain`

Responsabilites :

- Definir les modeles metier purs.
- Porter les constantes de regles si elles ne dependent pas de l'I/O.
- Garder les donnees serialisables.

Fichiers :

- `domain/horse.py`
- `domain/jockey.py`
- `domain/track.py`
- `domain/weather.py`
- `domain/race.py`
- `domain/career.py`
- `domain/stable.py`
- `domain/rival.py`
- `domain/value_objects.py`

### `simulation`

Responsabilites :

- Calculer le prochain etat de course.
- Recevoir des commandes abstraites.
- Produire des evenements.
- Rester deterministe avec seed explicite.

Fichiers :

- `simulation/race_engine.py`
- `simulation/race_state.py`
- `simulation/race_events.py`
- `simulation/movement.py`
- `simulation/stamina.py`
- `simulation/ai_jockey.py`
- `simulation/collision.py`
- `simulation/ranking.py`

### `audio`

Responsabilites :

- Convertir les evenements en sons, voix et spatialisation.
- Prioriser les sons critiques.
- Maintenir un mix lisible pour casque.
- Isoler le backend concret.

Fichiers :

- `audio/audio_backend.py`
- `audio/audio_engine.py`
- `audio/event_router.py`
- `audio/spatial_mixer.py`
- `audio/voice_announcer.py`
- `audio/accessibility_mix.py`
- `audio/sound_catalog.py`

### `input`

Responsabilites :

- Lire clavier et manette Windows.
- Convertir les entrees physiques en commandes de jeu.
- Permettre des remappings.

Fichiers :

- `input/input_backend.py`
- `input/keyboard_backend.py`
- `input/gamepad_backend.py`
- `input/command_mapper.py`
- `input/commands.py`

### `ui`

Responsabilites :

- Menus audio-first.
- Tutoriel.
- Pause.
- Reglages.
- Demande de resume vocal.
- Ecrans statistiques, replay et editeur de pistes.

Fichiers :

- `ui/audio_menu.py`
- `ui/menu_models.py`
- `ui/settings_menu.py`
- `ui/tutorial_flow.py`
- `ui/pause_menu.py`
- `ui/pygame_menu.py`
- `ui/pygame_game.py`
- `ui/pygame_stats.py`
- `ui/pygame_replay.py`
- `ui/pygame_track_editor.py`

### `scripts`

Responsabilites :

- Automatiser les taches hors runtime.
- Generer les assets audio ElevenLabs a partir d'une spec JSON.
- Produire un manifest genere separe, et fusionner seulement sur option explicite.

Fichiers :

- `scripts/generate_elevenlabs_audio.py` : generation SFX/music ElevenLabs avec `--dry-run`, `--only`, `--kind`, `--force`, `--merge-manifest`.

## Modeles de Donnees

### Horse

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class HorseStats:
    max_speed_mps: float
    acceleration: float
    stamina_capacity: float
    stamina_recovery: float
    handling: float
    nervousness: float

@dataclass(frozen=True)
class Horse:
    horse_id: str
    name: str
    stats: HorseStats
    preferred_surface: str
```

### Track

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TrackSegment:
    start_m: float
    end_m: float
    curve_direction: str
    curve_intensity: float
    surface: str
    slope: float

@dataclass(frozen=True)
class Track:
    track_id: str
    name: str
    length_m: float
    lanes: int
    segments: list[TrackSegment]
```

### RaceState

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RunnerState:
    runner_id: str
    distance_m: float
    lateral_position: float
    speed_mps: float
    stamina: float
    stability: float
    is_player: bool

@dataclass(frozen=True)
class RaceState:
    elapsed_s: float
    runners: list[RunnerState]
    is_finished: bool
```

Le moteur peut utiliser des structures internes mutables pour la performance, mais les snapshots publics doivent etre simples et testables.

## Commandes de Jeu

Les commandes representent l'intention, pas la touche physique.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RaceCommand:
    throttle_delta: float
    lateral_delta: float
    push_requested: bool
    jump_requested: bool
    duck_requested: bool
    request_status: bool
```

Regles :

- `throttle_delta` varie entre `-1.0` et `1.0`.
- `lateral_delta` varie entre `-1.0` et `1.0`.
- `jump_requested` est une action discrete pour franchir un obstacle de type `jump`.
- `duck_requested` est une action discrete pour passer sous un obstacle de type `duck`.
- Le mapper clavier/manette normalise les entrees avant la simulation.
- La simulation applique les limites physiques du cheval.

## Obstacles

Les obstacles sont charges depuis `content/obstacles.json` par piste. Le runtime actuel les gere dans `ObstacleController`, separe du moteur de course pur pour garder la feature testable et facilement remplacable.

```python
@dataclass(frozen=True)
class TrackObstacle:
    obstacle_id: str
    distance_m: float
    lane: int
    kind: str
    label: str
    required_action: str = "dodge"
```

Actions supportees :

- `dodge` : le joueur doit etre dans une autre voie au moment du contact.
- `jump` : le joueur peut rester dans la voie si `jump_requested` est actif.
- `duck` : le joueur peut rester dans la voie si `duck_requested` est actif.

Resolution :

- autre voie : `obstacle_avoided` avec `resolution=dodge` ;
- meme voie + bonne action : `obstacle_avoided` avec `resolution=jump` ou `resolution=duck` ;
- meme voie + mauvaise action : `obstacle_hit` avec `resolution=hit` et penalite temporaire.

Types de contenu actuels :

- `cone`, `stone`, `mud` : esquive recommandee ;
- `puddle`, `rail`, `barrel` : saut recommande ;
- `low_branch`, `low_banner`, `low_gate`, `low_rope` : passage dessous recommande.

## Moteur de Simulation

### Tick

Le moteur expose une API centrale :

```python
class RaceEngine:
    def tick(self, command: RaceCommand, delta_s: float) -> RaceTickResult:
        ...
```

`RaceTickResult` contient :

- `state` : snapshot courant.
- `events` : evenements produits pendant le tick.

### Ordre de Calcul

1. Valider `delta_s`.
2. Appliquer les commandes joueur.
3. Calculer les decisions IA.
4. Mettre a jour acceleration et vitesse.
5. Calculer consommation et recuperation d'endurance.
6. Mettre a jour distance et position laterale.
7. Detecter contacts, risques et depassements.
8. Mettre a jour classement.
9. Emettre evenements audio/logiques.
10. Detecter fin de course.

### Regles de Realisme MVP

- La vitesse cible depend de l'allure demandee, des stats, de l'endurance et du terrain.
- L'acceleration est limitee par le cheval et la fatigue.
- Le sprint ajoute une impulsion courte avec cout d'endurance eleve.
- La position laterale est bornee par la piste.
- Une trajectoire interieure raccourcit la distance effective en virage, mais augmente le risque de contact.
- Le cheval devient moins stable avec fatigue basse, terrain defavorable ou contact.

## Evenements de Course

### Structure

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RaceEvent:
    event_type: str
    priority: int
    timestamp_s: float
    subject_id: str | None
    data: dict[str, str | int | float | bool]
```

Pour l'implementation finale, `event_type` devra devenir un `Enum`. Le dictionnaire `data` reste acceptable au MVP si les evenements sont valides par tests.

### Priorites

- `100` : danger immediat, collision, sortie de trajectoire.
- `80` : depart, sprint final, arrivee, fatigue critique.
- `60` : depassement, concurrent proche, virage entrant.
- `40` : statut demande par joueur.
- `20` : ambiance, progression narrative, feedback non urgent.

### Evenements MVP

- `race_countdown_started`
- `race_started`
- `turn_incoming`
- `turn_apex`
- `turn_exit`
- `opponent_approaching`
- `opponent_passing`
- `overtake_completed`
- `collision_risk`
- `contact`
- `obstacle_warning`
- `obstacle_hit`
- `obstacle_avoided`
- `low_stamina`
- `critical_stamina`
- `final_stretch`
- `finish_line_crossed`
- `race_finished`
- `status_requested`

## Pipeline Audio 3D

### Objectif Audio

Le joueur doit construire une carte mentale de la course. Les sons ne sont pas decoratifs : ils sont l'interface principale.

### Flux Audio

```text
RaceEvent
  -> Audio Event Router
  -> Accessibility Mix Policy
  -> Voice Announcer / Spatial Mixer / UI Earcon
  -> Audio Backend
  -> Headphones
```

### Spatialisation

Le mixer recoit une position relative :

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RelativeAudioPosition:
    forward_m: float
    right_m: float
    up_m: float
```

Convention :

- `forward_m > 0` : devant le joueur.
- `forward_m < 0` : derriere le joueur.
- `right_m > 0` : droite.
- `right_m < 0` : gauche.

### Couches Sonores

- Sabots du cheval joueur : feedback de vitesse et surface.
- Respiration du cheval : endurance et fatigue.
- Adversaires : position relative, approche, depassement.
- Rail interieur : repere de virage et trajectoire.
- Ambiance foule : intensite selon segment important.
- Vent : vitesse et ligne droite.
- UI earcons : navigation, confirmation, erreur.
- Voix : informations critiques ou demandees.

### Politique de Mixage

- Les alertes de danger peuvent duck temporairement ambiance et musique.
- Les voix longues sont interdites pendant collision, virage serre ou sprint final.
- Deux annonces vocales non critiques ne doivent pas se chevaucher.
- Les sons de concurrents proches restent audibles meme si la foule monte.
- Les sons UI utilisent un canal clair et court.

### Profils Audio

- `descriptive` : plus de voix, indices explicites, utile tutoriel et apprentissage.
- `normal` : voix moderee, sons spatiaux principaux.
- `minimal` : voix minimale, sons spatiaux et alertes prioritaires.

### TTS et Musique

- Le backend pygame peut parler via NVDA si `nvdaControllerClient64.dll` est disponible a la racine du projet.
- Les musiques MP3 existantes sont gerees via `pygame.mixer.music` et restent separees du catalogue SFX.
- Les SFX du manifest sont joues via le backend audio court, avec fallback silencieux si le mixer est indisponible.
- Les SFX ElevenLabs deja presents dans `assets/generated/elevenlabs/` sont auto-ajoutes au catalogue depuis `content/elevenlabs_audio_prompts.json` si le fichier existe localement.
- Les entrees `music` de la spec ElevenLabs ne sont pas auto-chargees dans le catalogue SFX ; les musiques de menu/course restent les MP3 telecharges.

## Interfaces Internes

### Audio Backend

```python
from abc import ABC, abstractmethod

class AudioBackend(ABC):
    @abstractmethod
    def play_2d(self, sound_id: str, volume: float) -> None:
        ...

    @abstractmethod
    def play_3d(
        self,
        sound_id: str,
        position: RelativeAudioPosition,
        volume: float,
    ) -> None:
        ...

    @abstractmethod
    def speak(self, text: str, priority: int) -> None:
        ...

    @abstractmethod
    def stop_all(self) -> None:
        ...
```

### Input Backend

```python
from abc import ABC, abstractmethod

class InputBackend(ABC):
    @abstractmethod
    def poll(self) -> list[PhysicalInput]:
        ...
```

### Save Repository

```python
from abc import ABC, abstractmethod

class SaveRepository(ABC):
    @abstractmethod
    def load_career(self, slot_id: str) -> CareerState | None:
        ...

    @abstractmethod
    def save_career(self, slot_id: str, state: CareerState) -> None:
        ...
```

## Contenu MVP

### `content/horses.json`

Contient :

- 8 chevaux fictifs et calibrables.
- Stats lisibles.
- Traits audio ou comportementaux.

### `content/tracks.json`

Contient :

- 2 pistes.
- Segments droits et courbes.
- Surface.
- Points de repere audio.
- Distance de ligne droite finale.

### `content/sound_manifest.json`

Contient :

- ID de son.
- Chemin relatif.
- Categorie.
- Volume par defaut.
- Boucle ou one-shot.
- Priorite par defaut.

Etat actuel : 148 entrees telechargees/referencees. Ce fichier ne doit pas etre ecrase par la generation ElevenLabs sauf demande explicite. Au runtime local actuel, le catalogue expose 207 sons car 59 SFX ElevenLabs generes existent sur disque et sont ajoutes dynamiquement.

### `content/elevenlabs_audio_prompts.json`

Contient :

- `output_dir` : dossier de sortie `assets/generated/elevenlabs`.
- `generated_manifest` : manifest separe `content/generated_elevenlabs_sound_manifest.json`.
- `defaults` : modeles et formats ElevenLabs par type.
- `assets` : liste des sons et musiques a generer.

Etat actuel : 66 assets planifies.

- 59 `sound_effect` : UI, course, chevaux, adversaires, foule, vent, pluie, obstacles, progression, replay, editeur, ecuries.
- 7 `music` : menu, course, final stretch, entrainement, briefing championnat, victoire, defaite.

Chargement runtime : seuls les assets `sound_effect` dont le fichier existe sont ajoutes automatiquement. Les musiques restent planifiees mais non utilisees par defaut.

SFX chevaux couverts :

- Loops d'allure : marche, trot, canter, galop turf, dirt, mud, sand, inner rail proche.
- Vocalisations : whinny, neigh, snort, nicker.
- Corps/equipement : respiration fatigue, recuperation, bridle/tack jingle, saddle creak.
- Actions : sprint surge, stumble dirt, stumble mud, jump takeoff, jump landing, hard brake, lane change, photo finish stride.

### `content/championship.json`

Contient :

- calendrier de championnat ;
- piste et meteo imposees par manche ;
- briefing audio ;
- ecuries rivales par course.

### `content/stables.json`

Contient les ecuries, leurs noms, descriptions et bonus de stats.

### Sauvegardes Runtime

- `save/progress.json` : progression, dernier cheval, derniere ecurie, stats et replay.
- `save/custom_tracks.json` : pistes creees dans l'editeur audio-first.

## Tests Prioritaires

### Simulation

- Une course avec la meme seed donne le meme classement.
- L'endurance baisse quand l'allure augmente.
- La fatigue reduit acceleration et stabilite.
- Un virage serre augmente le cout de trajectoire exterieure/interieure selon position.
- Un concurrent proche emet un evenement d'approche avec bonne direction relative.

### Audio Events

- `collision_risk` produit un son prioritaire spatialise.
- `low_stamina` produit un feedback respiration ou alerte discrete.
- `status_requested` produit une annonce vocale avec rang, distance et endurance.
- Les annonces non critiques sont ignorees ou retardees pendant un danger prioritaire.

### Obstacles

- Un obstacle dans une autre voie est resolu par `dodge` sans penalite.
- Un obstacle `jump` dans la meme voie est resolu par `jump` si `jump_requested` est actif.
- Un obstacle `duck` dans la meme voie est resolu par `duck` si `duck_requested` est actif.
- Une mauvaise action sur la meme voie produit `obstacle_hit` et active une penalite temporaire.

### Menus

- Tous les items sont atteignables au clavier.
- Chaque changement de selection est annonce.
- Chaque action destructive demande confirmation.
- Le dernier message important peut etre repete.

### Generation Audio

- La spec ElevenLabs est du JSON valide.
- Le script compile sans importer de configuration runtime.
- `--dry-run` liste les sorties attendues sans appeler l'API.
- Les helpers de manifest filtrent, creent et fusionnent les entrees sans doublons d'ID.

## Premiere Tranche Implementable

### Tranche 1 - Squelette Jouable Muet

- Creer package Python.
- Ajouter modeles `Horse`, `Track`, `RaceState`.
- Ajouter `RaceEngine.tick`.
- Ajouter commandes abstraites.
- Ajouter tests deterministes.
- Pas d'audio reel, seulement collecte d'evenements.

### Tranche 2 - Prototype Audio Minimal

- Ajouter backend audio fake pour tests.
- Ajouter routeur d'evenements audio.
- Ajouter annonces texte via backend temporaire.
- Ajouter sons placeholders si backend disponible.

### Tranche 3 - Course Audio-First

- Boucle principale Windows.
- Input clavier.
- Course rapide.
- Resume vocal.
- Sons spatiaux pour adversaires proches et virages.

### Tranche 4 - Carriere MVP

- Sauvegarde JSON.
- Choix cheval.
- Saison courte.
- Resultats et progression.
- Evenements narratifs courts.

### Tranche 5 - v2 Audio-First

- Statistiques avancees.
- Championnat complet a calendrier JSON.
- Ecuries et bonus appliques au joueur et aux rivaux.
- Replay audio du dernier resultat.
- Editeur de pistes audio-first.
- Generation optionnelle d'assets ElevenLabs avec manifest separe.
