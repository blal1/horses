# Product Requirement Document (PRD)

## Project: Audio-First Horse Racing Game
**Package:** `horse-racing-audio-first` (`horse_racing_game`)
**Version:** 0.1.0 (prototype)
**Runtime:** Python ≥ 3.10, `pygame-ce` ≥ 2.5
**Status:** Active prototype

---

## 1. Executive Summary & Core Goals

An accessible horse racing game where the entire race is conveyed through **sound** — spoken status, directional sound cues, spatialized opponents, and an obstacle radar — so blind and low-vision players can compete on equal footing. A visual pygame screen mirrors the audio for sighted players.

### Core Engineering Objectives

- **Audio-first design:** Every meaningful race state change emits a typed `RaceEvent` that is turned into speech and/or a positioned sound. Nothing the player needs is visual-only.
- **Deterministic simulation:** The `RaceEngine` is seeded (`AppConfig.seed`, default 42) and advances at a fixed tick. Same inputs → same race. This enables replays, tests, and balance tuning.
- **Layered, testable core:** `domain` and `simulation` are pure (no I/O). Audio and input are abstract backends with fake implementations, so the full game runs headless under pytest.
- **Content as data:** Horses, tracks, weather, stables, rivals, the championship calendar, obstacles, and the sound catalog all live in JSON under `content/` and are validated on load.
- **Accessibility on Windows:** Spoken output is routed through NVDA via `nvdaControllerClient64.dll`, degrading gracefully when NVDA is absent.

---

## 2. Target Persona & Environment Constraints

- **Primary users:** Blind / low-vision players who navigate by screen reader and sound; sighted players who want an audio-driven racer.
- **Accessibility requirement:** The game must be completable with the monitor off. Spoken cues for rank, distance, stamina, turns, opponents, and obstacles are mandatory.
- **System:** Desktop (developed on Windows 11). NVDA speech is Windows-only; positional/2D audio works on any platform pygame supports.

---

## 3. Detailed Functional Requirements

### Feature 01: Deterministic Race Simulation (`simulation/race_engine.py`)

- **Description:** Tick-based engine advancing every runner's distance, speed, stamina, stability, and lane.
- **Inputs per tick:** a `RaceCommand` (throttle delta, lateral delta, push, jump, duck, request_status) and `delta_s`.
- **Physics:** target speed = `max_speed × pace × surface_modifier × weather.speed_modifier × fatigue_modifier × curve_modifier × slope_modifier`, capped by `acceleration × delta_s`. Stamina drains with pace and curve intensity, recovers when coasting.
- **Opponent AI:** opponents shadow the player's pace (pack racing) with chase boost, final-stretch push, back-marker boost, per-horse aggression, and bounded RNG noise — deterministic per seed.
- **Output:** `RaceTickResult(state, events)`.

### Feature 02: Audio Event Pipeline (`audio/`)

- **Description:** Convert race events to speech + sound.
- **Flow:** `AudioEngine.render_events` sorts by priority → `AudioEventPolicy.should_route` enforces per-type cooldowns → `AudioEventRouter.route` speaks a line and plays a cue.
- **Cues (`event_cues.py`):** each event type has a preferred sound id with a category+token fallback resolved against the `SoundCatalog`. Opponents use 3D positional playback (forward/right offsets).
- **Backends:** `AudioBackend` ABC with `play_2d / play_3d / play_loop / stop_sound / speak / stop_all`. `FakeAudioBackend` records `AudioCall`s for tests; `PygameAudioBackend` plays real audio and speaks via `NvdaSpeaker`.

### Feature 03: Spoken Feedback (`audio/voice_feedback.py`)

- **Description:** `VoiceFeedbackController` turns events into `SpokenMessage`s, remembers the last one for **Repeat** (R), and provides **Help** (the full control list).
- **Status line:** rank, distance remaining, stamina, weather — on demand (Tab/Enter) and periodically.

### Feature 04: Obstacles (`ui/obstacles.py`, `content/obstacles.json`)

- **Description:** Per-track hazards the player must dodge (change lane), jump (J), or duck (K/Ctrl).
- **Radar:** staged pings at `RADAR_DISTANCES_M = (120, 80, 45, 25, 12)` m as a hazard nears.
- **Resolution:** within 3.2 m, resolves to `obstacle_avoided` (correct action / clear lane) or `obstacle_hit` (1.25 s speed penalty).

### Feature 05: Game Modes (`app/`, `ui/pygame_menu.py`)

- **Quick race** — single race with chosen horse/track/weather/stable.
- **Tutorial** — timed spoken control lessons (`TUTORIAL_MESSAGES`).
- **Training** — finishing raises the horse's training level (0–5, `app/training.py`), boosting control and stamina.
- **Career** — a 3-race championship (`app/championship.py`, `content/championship.json`) with rival stables and points (`app/career.py`: 10/7/5/3/1).
- **Obstacle lab** — short track with three close hazards for dodge/jump/duck practice.
- **Replay** — replays the last race as spoken event lines (`app/replay.py`).
- **Track editor** — build a custom audio track (`app/track_editor.py`, `ui/pygame_track_editor.py`).
- **Statistics** — season stats and rival standings (`app/stats.py`, `ui/pygame_stats.py`).

### Feature 06: Content & Configuration

- **Content loaders (`content/loaders.py`):** strict JSON parsing with typed errors for horses, tracks, weather, rivals, stables, sound catalog (plus optional generated ElevenLabs assets), segments.
- **Stables (`domain/stable.py`):** apply speed/stamina/handling/calm modifiers to the player and championship rivals.
- **Validation:** unknown horse/track/weather/stable ids raise; missing referenced sound files raise on bootstrap.

### Feature 07: Progress & Persistence (`app/progress.py`)

- **Saved to `save/progress.json`:** last selections, quick/career/finished counts, wins, podiums, best rank, per-horse training levels, rival encounters, rival championship points/races, last replay lines.
- **Tolerant load:** missing or corrupt file → fresh `GameProgress` defaults.

---

## 4. Technical Architecture & Constraints

- **Language/runtime:** Python 3.10+, single dependency `pygame-ce>=2.5`.
- **Layers:** `domain` → `simulation` → `input`/`audio`/`content` → `ui` → `app` (orchestration). Lower layers never import upper layers.
- **Determinism:** seeded `random.Random`; fixed tick (`tick_hz`; pygame UI runs the engine at 60 Hz via `AppConfig`).
- **Persistence:** JSON only (`content/` read-only data, `save/progress.json` mutable state).
- **Testing:** `pytest`, coverage source `horse_racing_game`, `fail_under = 80` (`pyproject.toml`).
- See [[architecture]] for full types and data flow, [[code-standards]] for conventions.

---

## 5. Future Scope

Planned direction beyond the v0.1.0 slice. These are not yet built; each anchors to a code seam (see [[architecture]] → Extension Points and [[progress-tracker]] → What's Next for detail).

- **Multiplayer (local/online):** the deterministic seeded engine supports lockstep racing — peers run the same `RaceEngine(seed)` and exchange a `RaceCommand` per tick.
- **True replay:** record `(seed, per-tick commands)` and re-simulate exact races (today's replay is recorded spoken lines only).
- **Cross-platform speech:** abstract `NvdaSpeaker` behind a `Speaker` interface with VoiceOver (macOS) and speech-dispatcher (Linux) backends; NVDA stays the Windows path.
- **Content expansion:** more tracks/weather/stables/horses via JSON; custom track-editor tracks selectable in race and career.
- **Career depth:** data-driven championship length and difficulty tiers that scale opponent strength.
- **Deeper mechanics:** make `Horse.traits` and obstacle kinds materially affect the simulation.
- **Audio pipeline:** finish the ElevenLabs prompts → generated SFX → catalog flow to cover missing cues.

These remain out of scope for the prototype but the architecture is designed to absorb them without changing the pure `domain`/`simulation` core.
