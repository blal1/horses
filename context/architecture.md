# Architecture

## Stack

| Layer            | Tool                              | Purpose                                            |
| ---------------- | --------------------------------- | -------------------------------------------------- |
| Language         | Python ≥ 3.10                     | Type-hinted, dataclass-heavy, stdlib-first         |
| Game framework   | `pygame-ce` ≥ 2.5                 | Window, input events, mixer (audio), clock         |
| Speech (Windows) | `nvdaControllerClient64.dll`      | Screen-reader speech via `ctypes` (`NvdaSpeaker`)  |
| Data             | JSON files under `content/`       | Horses, tracks, weather, stables, rivals, sounds   |
| Persistence      | `save/progress.json`             | Player progress / season state                     |
| Tests            | `pytest` + `coverage` (≥80%)      | Headless via fake backends                          |

The only runtime dependency is `pygame-ce`. Everything else is the Python standard library. There is no network, database, or web server.

---

## Folder / File Structure

```
/
├── pyproject.toml              → Package metadata, entry point, pytest + coverage config
├── play_game.py / c.py         → Thin launchers → app.pygame_main:main
├── PLAY_GAME.bat               → Windows launcher
├── nvdaControllerClient64.dll  → NVDA speech client (Windows)
├── content/                    → JSON game data (read-only at runtime)
│   ├── horses.json  tracks.json  weather.json  stables.json  rivals.json
│   ├── championship.json  obstacles.json
│   ├── sound_manifest.json     → SoundCatalog assets
│   └── elevenlabs_audio_prompts.json / *_state.json → optional generated SFX
├── save/progress.json          → Mutable player progress
├── assets/  sfx/               → Audio files referenced by the catalog
├── tests/                      → pytest suite (one file per subsystem)
└── horse_racing_game/
    ├── domain/        → Pure data types: Horse, Track, Weather, Stable, RivalProfile
    ├── content/       → loaders.py: JSON → domain objects (strict parsing)
    ├── simulation/    → race_engine.py, race_state.py, race_events.py (pure, seeded)
    ├── input/         → RaceCommand + input backends (keyboard / fake)
    ├── audio/         → engine, policy, router, cues, catalog, backends, NVDA, mix
    ├── ui/            → pygame screens: game, menu, stats, replay, track editor, obstacles
    └── app/           → orchestration: pygame_main, config, bootstrap, game_app,
                          career, championship, progress, training, replay, stats,
                          track_editor, runtime_log
```

`__main__.py` and the `[project.scripts]` entry both resolve to `app.pygame_main:main`. `app/keyboard_main.py`, `app/main.py`, `app/realtime_game.py`, and `input/command_mapper.py` are thin re-export shims to the same `main`.

---

## Layering Rules

```
domain  ←  simulation  ←  app
   ↑           ↑           ↑
content      input       ui
   ↑                       ↑
 (json)      audio  ←──────┘
```

- **domain** depends on nothing (just dataclasses).
- **simulation** depends on domain + input (`RaceCommand`).
- **audio**, **input**, **content** depend on domain/simulation but not on `ui`/`app`.
- **ui** wires simulation + audio + input into pygame screens.
- **app** is the only orchestration layer; it may import anything below it.

Lower layers must never import upper layers. This keeps `domain` + `simulation` pure and headlessly testable.

---

## Core Types

### Domain (`domain/`, all `@dataclass(frozen=True)`)

- `Horse(horse_id, name, role, preferred_surface, signature_sound, stats: HorseStats, traits)`
- `HorseStats(max_speed_mps, acceleration, stamina_capacity, stamina_recovery, handling, nervousness)`
- `Track(track_id, name, length_m, surface, lanes, handedness, final_stretch_start_m, audio_profile, segments)` + `TrackSegment(start_m, end_m, curve_direction, curve_intensity, slope, audio_marker)`; `Track.segment_at(distance)` returns the active segment.
- `Weather(weather_id, name, speed_modifier, stamina_cost_multiplier, stability_modifier, ambient_sound_id)`
- `Stable(stable_id, name, focus, description, *_modifier)` + `apply_stable_boost(horse, stable)` → boosted `Horse`.
- `RivalProfile(horse_id, display_name, intro_line, approach_line, passing_line)`

### Simulation (`simulation/`)

- `RaceCommand` (in `input/commands.py`) — per-tick intent: `throttle_delta, lateral_delta, push_requested, jump_requested, duck_requested, request_status`.
- `RaceEngine` — holds private `_RunnerRuntime` list, seeded `random.Random`, weather, elapsed time. `tick(command, delta_s) -> RaceTickResult`.
- `RaceState(elapsed_s, runners: tuple[RunnerState], is_finished)` + `RunnerState(...)` — immutable snapshot; `RaceState.player()` returns the player runner.
- `RaceEvent(event_type, priority, timestamp_s, subject_id, data)` — the cross-layer message.

### App config (`app/config.py`)

```python
@dataclass(frozen=True)
class AppConfig:
    content_root: Path
    track_id: str = "ashford_oval"
    player_horse_id: str = "ember_stride"
    weather_id: str = "clear"
    audio_mix_id: str = "normal"
    stable_id: str = "oak_lane"
    rival_stable_ids: dict[str, str] = {}
    horse_training_level: int = 0
    seed: int = 42
    tick_hz: int = 4              # pygame_main overrides to 60 for real-time
    max_race_seconds: float = 240.0
    # tick_seconds = 1 / tick_hz
```

### Services (`app/bootstrap.py`)

`GameServices` bundles the loaded `horses, rivals, stables, track, weather, sound_catalog` plus the constructed `race_engine, audio_engine, audio_backend`. `build_quick_race_services(config)` loads content, applies stable + training boosts, validates ids and sound files, and wires the engine. `ui.pygame_game.build_pygame_services` is the pygame-backed variant.

---

## Runtime Model

`pygame_main.main()`:

```
main()
  ├─ default_config(project_root)              content_root = ./content
  ├─ load_progress(project_root)               save/progress.json → GameProgress
  └─ loop:
       PygameMainMenu(...).run() → MenuSelection | None
       ├─ None        → exit
       ├─ stats/replay/track_editor → open that screen, reload progress, loop
       └─ race-like mode:
            resolve effective selection (career → next championship race;
                 obstacle_lab → fixed track; training → intro line)
            config = _config_for_selection(...)   (tick_hz = 60)
            result = PygameRaceGame(config, build_pygame_services(config), ...).run()
            record_race_result(...) → save progress
            record rival encounters / championship results
            next_action: "restart" → re-run, "menu" → break, else exit
```

The race screen (`ui/pygame_game.PygameRaceGame`) runs the real-time loop at `UI_FRAME_RATE = 60`: read keyboard → build `RaceCommand` → `race_engine.tick` → update obstacles → route events to `AudioEngine` + `VoiceFeedbackController` → draw. The headless `app/game_app.GameApp.run_quick_race` drives the same engine for tests, supplying scripted or default commands.

---

## Data Flow

### Race tick → audio

```
keyboard (ui/pygame_game) ──► RaceCommand
        │
        ▼
RaceEngine.tick(command, delta_s) ──► RaceTickResult(state, events)
        │                                   │
        │                                   ├─► AudioEngine.render_events
        │                                   │      sort by priority
        │                                   │      AudioEventPolicy.should_route (cooldowns)
        │                                   │      AudioEventRouter.route → speak + play_2d/3d
        │                                   │                                   │
        │                                   │                            AudioBackend (Fake | Pygame→NVDA)
        │                                   └─► VoiceFeedbackController.observe_events
        ▼
ObstacleController.update(player, ...) ──► obstacle_* events ──► (same audio path)
```

### Content load (bootstrap)

```
content/*.json ──► content/loaders.py (strict parse) ──► domain objects
                                                            │
stables + training + rival stables applied ───────────────┤
                                                            ▼
                                                       GameServices (RaceEngine, AudioEngine)
```

### Progress

```
race result ──► app/progress.record_race_result ──► save/progress.json
career result ─► record_rival_championship_result ─┘
menu start ──► load_progress ──► initial menu selections + training levels
```

---

## Determinism Rules

- The engine's only randomness is `self._rng = random.Random(seed)`. No `time`, no global RNG.
- Opponent pace noise and initial pace/aggression come from `_rng`, so a fixed seed reproduces a race exactly.
- `RaceState` / `RaceEvent` are frozen and rounded at snapshot time for stable comparisons.
- Replays are reconstructed from recorded event lines, not by re-running the engine.

---

## Extension Points

The architecture is built to absorb new work at known seams. Future features (see [[progress-tracker]] → What's Next) plug in here without disturbing the pure core.

### Add a new race event type
1. Emit a `RaceEvent(event_type=..., priority=..., subject_id=..., data=...)` from `RaceEngine` (or `ObstacleController`).
2. Add a branch in `AudioEventRouter.route` for the spoken line + cue.
3. Add a cue rule in `event_cues._CUE_RULES` (preferred id + fallback category/token).
4. If it can fire repeatedly, add a cooldown in `event_policy._EVENT_COOLDOWNS`.
5. Optionally handle it in `VoiceFeedbackController` for repeat/help.

### Add a new audio or speech backend
- Subclass `AudioBackend` for sound. For speech, subclass `Speaker` (`audio/speech.py`) and wire it into `create_speaker`'s platform switch (NVDA / macOS `say` / Linux `spd-say` / null already exist). The engine and router never change — they only call the ABCs. Sound backends are selected in `build_pygame_services` / `PygameAudioBackend`.

### Add a new input source (e.g. network/multiplayer)
- The engine consumes one `RaceCommand` per tick and is fully deterministic per seed. A new source (network peer, AI, recorded command log) feeds commands the same way the keyboard does — see the command-gathering step in `ui/pygame_game.py` and `app/game_app.py`. This is the seam for **lockstep multiplayer** and **true seed+command replay**.

### Add a new game mode
- Add a menu row + `mode` string in `ui/menu_models.py` / `ui/pygame_menu.py`, then a dispatch branch in `app/pygame_main.main`. Modes reuse `PygameRaceGame`; mode-specific setup (track/weather override, intro line) happens in `_config_for_selection` and the surrounding mode block.

### Add content (horses, tracks, weather, stables, rivals)
- Extend the relevant `content/*.json` and the matching `_parse_*` in `content/loaders.py`. No code change is needed to *use* new entries — they appear in the menu selectors automatically. Custom tracks from the editor flow through `app/track_editor.load_available_tracks`.

### Make traits / obstacles affect the sim
- `Horse.traits` and obstacle `kind` are currently mostly descriptive. Map them to modifiers inside `RaceEngine._update_runner` (speed/stamina/handling) and `ObstacleController` resolution — keep changes deterministic.

---

## Invariants

- `domain` and `simulation` perform **no I/O** and import nothing from `ui`/`app`.
- All race state changes flow through `RaceEvent`s — UI and audio never read engine internals.
- The engine is deterministic given `(seed, content, command sequence)`.
- Content is validated on load; unknown ids and missing sound files raise before a race starts.
- Audio is always behind the `AudioBackend` ABC — tests use `FakeAudioBackend`, never real mixer calls.
- NVDA speech degrades gracefully: a missing/failed DLL is logged once and silently skipped, never crashes.
- Player progress is the only mutable on-disk state and lives solely in `save/progress.json`; a corrupt file falls back to defaults.
- Lane spacing (`1.15`) and event thresholds are shared constants — keep simulation, obstacles, and audio positioning consistent.
