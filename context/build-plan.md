# Build Plan

## Core Principle

The game is built **bottom-up by layer**: pure data types first, then the deterministic simulation, then the audio/input abstractions, then content loading, then the pygame UI, and finally the app orchestration that ties modes together. Each layer is fully testable before the one above it exists — `domain` and `simulation` need no pygame, and audio/input run against fake backends. A feature is "done" when its logic is covered by a pytest in `tests/` and runs headless.

This document maps the current architecture as an ordered build so a contributor can rebuild or extend it phase by phase.

---

## Phase 1 — Domain & Content

### 01 Domain types (`domain/`)
- `Horse` / `HorseStats`, `Track` / `TrackSegment` (+ `segment_at`), `Weather`, `Stable` (+ `apply_stable_boost`), `RivalProfile`. All frozen dataclasses, no I/O.

### 02 Content loaders (`content/loaders.py`)
- Strict JSON parsing helpers (`_string/_number/_integer/_boolean/_object/_list`) that raise typed `ValueError`/`FileNotFoundError` with the offending path.
- `load_horses / load_tracks / load_weather / load_rivals / load_stables / load_sound_catalog`.
- Optional generated ElevenLabs sound assets merged into the catalog when present on disk.
- Content lives in `content/*.json`. **Tests:** `test_content_loading.py`.

---

## Phase 2 — Simulation

### 03 Events & state (`simulation/race_events.py`, `race_state.py`)
- `RaceEvent(event_type, priority, timestamp_s, subject_id, data)`.
- `RaceState` / `RunnerState` immutable snapshots; `RaceState.player()`.

### 04 Race engine (`simulation/race_engine.py`)
- Seeded `RaceEngine.tick(command, delta_s)`: pace update → per-runner physics → event detection.
- Physics: surface/weather/fatigue/curve/slope modifiers, acceleration-capped speed, stamina drain/recovery, stability.
- Opponent AI: shadow player pace + chase/final-stretch/back-marker boosts + aggression + bounded noise.
- Events: started, turn, opponent proximity, stamina thresholds, status, final stretch, finish.
- **Tests:** `test_race_engine.py`, `test_race_balance.py`.

---

## Phase 3 — Input & Audio

### 05 Input (`input/`)
- `RaceCommand` dataclass; `InputBackend` ABC with `KeyboardBackend` and `FakeBackend`.
- **Tests:** `test_input_mapping.py`.

### 06 Sound catalog & cues (`audio/sound_catalog.py`, `event_cues.py`)
- `SoundAsset` / `SoundCatalog` (lookup, category helpers, `missing_files`).
- `SoundCueMap`: preferred sound id per event with category+token fallback.
- **Tests:** `test_sound_catalog.py`.

### 07 Audio pipeline (`audio/audio_engine.py`, `event_policy.py`, `event_router.py`)
- `AudioEngine.render_events`: priority sort → policy → router.
- `AudioEventPolicy`: per-event-type cooldowns (`_EVENT_COOLDOWNS`).
- `AudioEventRouter`: per-event speech + 2D/3D cue playback.
- Backends: `AudioBackend` ABC, `FakeAudioBackend` (records `AudioCall`s), `PygameAudioBackend`, `NvdaSpeaker`, `pygame_music`, `mix_profile`.
- `VoiceFeedbackController`: spoken messages, repeat-last, help text.
- **Tests:** `test_audio_routing.py`, `test_voice_feedback.py`.

---

## Phase 4 — Orchestration & Modes (`app/`)

### 08 Config & bootstrap
- `AppConfig` + `default_config`; `GameServices` + `build_quick_race_services` (load → boost → validate → wire engine + audio).

### 09 Headless game loop
- `GameApp.run_quick_race` drives the engine with scripted/default commands → `QuickRaceResult`.
- **Tests:** `test_app_quick_race.py`, `test_realtime_game.py`.

### 10 Progression systems
- `career.py` (points, titles), `championship.py` (calendar, next race, standings), `training.py` (levels 0–5, boosts), `progress.py` (`GameProgress`, load/record/save to `save/progress.json`).
- **Tests:** `test_career.py`, `test_championship.py`, `test_training.py`, `test_progress.py`.

### 11 Replay, stats, track editor
- `replay.py` (`build_replay_lines`), `stats.py`, `track_editor.py` (`load_available_tracks`, custom tracks).
- **Tests:** `test_replay.py`, `test_stats.py`, `test_track_editor.py`.

---

## Phase 5 — UI (`ui/`)

### 12 Obstacles (`ui/obstacles.py`)
- `TrackObstacle`, `ObstacleController` (radar staging, warning, hit/avoid resolution + penalty).
- **Tests:** `test_obstacles.py`.

### 13 Menu (`ui/pygame_menu.py`, `menu_models.py`)
- `PygameMenuState` (14 rows: 5 selectors + 9 actions), `MenuSelection`.
- **Tests:** `test_pygame_menu_models.py`.

### 14 Screens (`ui/pygame_game.py`, `pygame_stats.py`, `pygame_replay.py`, `pygame_track_editor.py`)
- `PygameRaceGame.run()` real-time loop at 60 Hz; tutorial/training/intro variants.
- **Tests:** `test_pygame_smoke.py`, `test_pygame_game_input.py`, `test_pygame_secondary_screens.py`, `test_pygame_entrypoints.py`.

### 15 Entry points
- `app/pygame_main.py:main` wires menu ↔ modes ↔ progress; launchers `play_game.py`, `c.py`, `PLAY_GAME.bat`, `[project.scripts] horse-racing-game`.

---

## Verification

Before submitting changes:

```bash
pytest                 # full suite
pytest --cov           # coverage must stay ≥ 80% (pyproject: fail_under = 80)
```

Pure layers (`domain`, `simulation`, most of `app` and `audio`) are tested without pygame by using `FakeAudioBackend` and scripted `RaceCommand`s. Pygame screens are exercised via smoke tests with a dummy/headless video driver.

---

## Subsystem Count

| Phase                       | Subsystems |
| --------------------------- | ---------- |
| Phase 1 — Domain & Content  | 2          |
| Phase 2 — Simulation        | 2          |
| Phase 3 — Input & Audio     | 3          |
| Phase 4 — App & Modes       | 4          |
| Phase 5 — UI                | 4          |
| **Total**                   | **15**     |
