# Project State Map (Compressed Context)

A token-efficient baseline of the codebase. Use alongside [[architecture]] for full detail.

## 1. File Architecture

```
horse_racing_game/
├── __main__.py                Module entry → app.pygame_main:main
├── domain/
│   ├── horse.py               Horse, HorseStats
│   ├── track.py               Track, TrackSegment, Track.segment_at
│   ├── weather.py             Weather
│   ├── stable.py              Stable, apply_stable_boost
│   └── rival.py               RivalProfile
├── content/
│   └── loaders.py             JSON → domain (strict parse); load_horses/tracks/weather/
│                              rivals/stables/sound_catalog (+ optional ElevenLabs SFX)
├── simulation/
│   ├── race_events.py         RaceEvent
│   ├── race_state.py          RaceState, RunnerState, RaceState.player()
│   ├── race_engine.py         RaceEngine.tick → RaceTickResult; seeded, pure physics + AI
│   └── traits.py              trait_effect(): per-tick speed/stamina/accel from Horse.traits
├── input/
│   ├── commands.py            RaceCommand
│   ├── input_backend.py       InputBackend ABC
│   ├── keyboard_backend.py    Real keyboard backend
│   ├── fake_backend.py        Scripted backend (tests)
│   └── command_mapper.py      (shim → pygame_main:main)
├── audio/
│   ├── audio_backend.py       AudioBackend ABC, RelativeAudioPosition
│   ├── fake_backend.py        FakeAudioBackend, AudioCall (records calls)
│   ├── pygame_backend.py      PygameAudioBackend (mixer + NVDA)
│   ├── debug_backend.py       Logging backend
│   ├── speech.py             Speaker ABC + create_speaker (NVDA/macOS say/Linux spd-say/null)
│   ├── nvda_speaker.py        NvdaSpeaker (Speaker impl; ctypes DLL, graceful failure)
│   ├── sound_catalog.py       SoundAsset, SoundCatalog (lookup, missing_files)
│   ├── event_cues.py          SoundCueMap, _CUE_RULES, cue_sound_requirements()
│   ├── asset_coverage.py      missing_cue_sound_ids / prompt_spec_for_missing (gen-pipeline loop)
│   ├── event_policy.py        AudioEventPolicy (_EVENT_COOLDOWNS)
│   ├── event_router.py        AudioEventRouter.route (speak + 2D/3D cue)
│   ├── audio_engine.py        AudioEngine.render_events (priority sort → policy → route)
│   ├── voice_feedback.py      VoiceFeedbackController, HELP_TEXT, SpokenMessage
│   ├── mix_profile.py         AudioMixProfile, MIX_PROFILES, mix_profile_by_id
│   └── pygame_music.py        play_music / set_music_volume / stop_music
├── ui/
│   ├── menu_models.py         PygameMenuState (16 rows), MenuSelection, MENU_ROW_COUNT
│   ├── pygame_menu.py         PygameMainMenu.run → MenuSelection|None
│   ├── pygame_game.py         PygameRaceGame.run (60 Hz loop), build_pygame_services
│   ├── obstacles.py           TrackObstacle, ObstacleController, load_track_obstacles
│   ├── pygame_stats.py        PygameStatsScreen
│   ├── pygame_replay.py       PygameReplayScreen
│   └── pygame_track_editor.py PygameTrackEditorScreen
└── app/
    ├── pygame_main.py         main(): menu ↔ modes ↔ progress orchestration
    ├── config.py              AppConfig, default_config
    ├── bootstrap.py           GameServices, build_quick_race_services
    ├── game_app.py            GameApp.run_quick_race (headless), QuickRaceResult
    ├── career.py              points_for_rank, career_title, CAREER_LENGTH=3
    ├── difficulty.py          DifficultyTier, DIFFICULTY_TIERS, career_difficulty (opponent_strength)
    ├── championship.py        load_championship_calendar, next_championship_race, standings
    ├── training.py            training levels 0–5, apply_training_boost
    ├── progress.py            GameProgress, load/record/save → save/progress.json
    ├── replay.py              build_replay_lines; RaceReplay + reconstruct_race (seed+command replay)
    ├── stats.py               season stats helpers
    ├── track_editor.py        load_available_tracks, custom tracks
    └── runtime_log.py         write_runtime_log → runtime_debug.log

content/   *.json game data        save/progress.json   mutable state
assets/ sfx/   audio files         tests/   pytest suite (1 file per subsystem)
launchers: play_game.py, c.py, PLAY_GAME.bat, [project.scripts] horse-racing-game
```

## 2. Data Flow Map

```
keyboard (ui/pygame_game) ──► RaceCommand
        │
        ▼
RaceEngine.tick(command, delta_s) ──► RaceTickResult(state, events)
        │                                       │
        │                          ┌────────────┴───────────────┐
        │                          ▼                            ▼
        │                AudioEngine.render_events      VoiceFeedbackController
        │                  priority sort                 observe / repeat / help
        │                  AudioEventPolicy (cooldowns)
        │                  AudioEventRouter.route
        │                          ▼
        │                AudioBackend (Fake | Pygame→NVDA)
        ▼
ObstacleController.update ──► obstacle_* events ──► (same audio path)

content/*.json ─► loaders ─► domain ─► (stable+training+rival boosts) ─► GameServices
race end ─► app/progress.record_race_result ─► save/progress.json
```

Determinism: `RaceEngine._rng = random.Random(config.seed)` is the only randomness.

## 3. Module Registry & Key Signatures

### `simulation/race_engine.py`
- **Intent:** Deterministic race physics + opponent AI + event emission.
- `RaceEngine(track, horses, player_horse_id, seed, weather)`, `tick(command, delta_s) -> RaceTickResult`.
- Private: `_update_paces`, `_opponent_target_pace`, `_update_runner`, `_detect_*_events`, `_snapshot`, `_rankings`.

### `audio/` pipeline
- `AudioEngine.render_events(events)` — sort by priority → policy → router.
- `AudioEventPolicy.should_route(event) -> bool` — per-type cooldowns.
- `AudioEventRouter.route(event)` — speech + `play_2d/play_3d` cue; positional opponents.
- `SoundCueMap.cue_for(event_type) -> SoundCue|None`; `SoundCatalog.get/first_*`.
- `VoiceFeedbackController.observe_events / repeat_last / speak_help`.

### `app/pygame_main.py`
- **Intent:** Top-level orchestration. `main()`, `_config_for_selection(...)`.
- Menu → mode dispatch (race/tutorial/training/career/obstacle_lab/replay/track_editor/stats) → `PygameRaceGame.run()` → record progress.

### `app/bootstrap.py`
- `GameServices` dataclass; `build_quick_race_services(config, audio_backend=None)` — load → boost → validate → wire `RaceEngine` + `AudioEngine`.

### `app/config.py`
- `AppConfig` (content_root, ids, rival_stable_ids, training_level, seed=42, tick_hz, max_race_seconds; `tick_seconds`), `default_config(project_root)`.

### `app/progress.py`
- `GameProgress` (selections, counts, wins/podiums/best_rank, training levels, rival stats, last_replay_lines); `load_progress`, `record_race_result`, `record_rival_encounter`, `record_rival_championship_result`, `progress_path`.

### `app/career.py` / `championship.py` / `training.py`
- `points_for_rank` (10/7/5/3/1), `CAREER_LENGTH=3`, `career_title`; `ChampionshipRace`, `StandingRow`, `next_championship_race`, `championship_title`; `MAX_TRAINING_LEVEL=5`, `apply_training_boost`, `next_training_level`.

### `ui/menu_models.py`
- `PygameMenuState` (rows 0–4 selectors: horse/track/weather/audio/stable; rows 5–15 actions), `MenuSelection`, `selection(mode)`, `MENU_ROW_COUNT=16`. Career mode opens a dedicated hub with race/training/rest choices.

### `ui/obstacles.py`
- `TrackObstacle`, `ObstacleController.update(...) -> events`, `RADAR_DISTANCES_M=(120,80,45,25,12)`, actions dodge/jump/duck, 1.25 s hit penalty.

## 4. Inter-Module Dependencies

```
app/pygame_main ──► ui/*, app/* (config, bootstrap, career, championship, progress, training, replay)
ui/pygame_game  ──► app/bootstrap, simulation, audio, input, ui/obstacles
app/bootstrap   ──► content/loaders, domain, simulation/race_engine, audio
simulation      ──► domain, input/commands
audio           ──► domain, simulation, app/runtime_log
content/loaders ──► domain, audio/sound_catalog
```

## 5. External Dependencies

`pygame-ce >= 2.5` (runtime) + bundled `nvdaControllerClient64.dll` via `ctypes`. Everything else is standard library. Tests: `pytest` + `coverage` (`fail_under = 80`).
