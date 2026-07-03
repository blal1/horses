# Project Overview

## About the Project

This is an **audio-first horse racing game** built in Python with `pygame-ce`. The whole experience is designed to be playable with sound alone — every race event (turns, opponents, obstacles, stamina, the final stretch, the finish) is announced through spoken feedback and positional sound cues. A visual screen exists, but it is a companion to the audio, not a requirement. Screen-reader users get spoken output via the NVDA controller DLL on Windows.

The player picks a horse, track, weather, audio mix profile, and stable, then races a deterministic simulation against AI opponents. Around the core race loop sit several modes — tutorial, training, a 3-race career championship, an obstacle lab, race replay, a track editor, and a stats screen.

The codebase is a clean **layered architecture**: pure domain + simulation logic with no I/O, content loaded from JSON, audio and input behind swappable backends, and a thin pygame UI on top. Everything below the UI is deterministic and unit-testable headlessly via fake backends.

---

## The Problem It Solves

Mainstream racing games are inaccessible to blind and low-vision players — they encode all state visually. This project is a proof that a racing game can be **fully driven by audio**: spatialized opponent sounds, directional turn warnings, an obstacle "radar" that pings as hazards approach, and continuous spoken status (rank, distance remaining, stamina). The simulation is deterministic per seed so races are reproducible, replayable, and testable.

---

## Surfaces

The game runs as a single pygame window with several screens, but the primary interface is **sound**:

```
Main menu          → Pick horse / track / weather / audio mix / stable, then choose a mode
Race screen        → Real-time race; spoken + spatial audio cues, keyboard control
Stats screen       → Season stats, rival standings
Replay screen      → Re-hear the last race as spoken event lines
Track editor       → Build a custom audio track
NVDA speech (Win)  → Spoken output routed through nvdaControllerClient64.dll
```

---

## Modes (Main Menu)

The menu has 16 rows (`MENU_ROW_COUNT`): 5 option selectors plus 11 actions, including a dedicated career hub entry (see `ui/pygame_menu.py` and `ui/pygame_career_hub.py`).

| Row | Kind | Mode |
| --- | ---- | ---- |
| 0 | Selector | Horse |
| 1 | Selector | Track |
| 2 | Selector | Weather |
| 3 | Selector | Audio profile |
| 4 | Selector | Stable |
| 5 | Action | **Quick race** (`race`) |
| 6 | Action | **Tutorial** (`tutorial`) — guided spoken controls |
| 7 | Action | **Training** (`training`) — finish to boost the selected horse |
| 8 | Action | **Career** (`career`) — next 3-race championship race |
| 9 | Action | **Obstacle lab** (`obstacle_lab`) — dodge/jump/duck drill |
| 10 | Action | **Replay** (`replay`) — re-hear the last race |
| 11 | Action | **Track editor** (`track_editor`) |
| 12 | Action | **Statistics** (`stats`) |
| 13 | Action | **Quit** |

---

## Core Behavior

### The race loop

`pygame_main.main()` runs the menu, then for a chosen race builds an `AppConfig`, builds `GameServices` (via `build_pygame_services`), and runs `PygameRaceGame`. Each frame the UI gathers a `RaceCommand` from the keyboard, advances the `RaceEngine` one tick, feeds the resulting `RaceEvent`s to the `AudioEngine` and `VoiceFeedbackController`, and renders. When the race ends, progress is recorded to `save/progress.json` and the menu returns.

### The simulation (`simulation/race_engine.py`)

A deterministic, seeded engine. Each tick it updates pace, speed, distance, stamina, and stability for every runner from horse stats, track segment (curve/slope/surface), and weather modifiers. The player's pace responds to throttle/push commands; opponents shadow the player's pace (pack racing) with per-horse aggression and bounded noise. The engine emits typed `RaceEvent`s: `race_started`, `turn_incoming`, `opponent_approaching`/`opponent_passing`, `low_stamina`/`critical_stamina`, `status_requested`, `final_stretch`, `finish_line_crossed`, `race_finished`.

### Audio (`audio/`)

`AudioEngine` sorts events by priority and applies an `AudioEventPolicy` (per-event-type cooldowns) before routing. `AudioEventRouter` maps each event to a spoken line plus a sound cue (`event_cues.py`), choosing positional 3D playback for opponents and preferred-then-fallback sound ids from the `SoundCatalog`. Backends are swappable: `FakeAudioBackend` records calls for tests, `PygameAudioBackend` plays real audio and speaks through NVDA.

### Obstacles (`ui/obstacles.py`)

Obstacles are loaded per track from `content/obstacles.json`. The `ObstacleController` emits a multi-stage `obstacle_radar` ping as a hazard approaches (`RADAR_DISTANCES_M`), an `obstacle_warning`, then resolves to `obstacle_hit` (1.25s penalty) or `obstacle_avoided` based on whether the player dodged lane / jumped / ducked.

---

## Features In Scope

- Deterministic seeded race simulation with curves, slope, surface, weather, stamina
- Audio-first feedback: spoken status + spatial/positional sound cues + obstacle radar
- NVDA screen-reader speech on Windows
- 12 horses (5 player, 7 opponent), 4 tracks, 4 weather types, 4 stables, 6 named rivals
- Modes: quick race, tutorial, training (5 levels), 3-race career championship, obstacle lab, replay, track editor, stats
- Stable boosts, training boosts, rival championship standings
- Persistent progress in `save/progress.json`
- Configurable audio mix profiles (normal / descriptive / minimal)
- Swappable audio + input backends for headless testing

## Features Out of Scope

- Online multiplayer or networking
- 3D graphics / rich visuals (the screen is a companion to audio)
- Account system or cloud sync
- Non-Windows screen-reader integration (NVDA path is Windows-only; audio cues still work everywhere)

---

## Running the Game

```bash
python play_game.py        # or c.py, or PLAY_GAME.bat on Windows
# installed entry point:
horse-racing-game          # = horse_racing_game.app.pygame_main:main
```

Python 3.10+, `pygame-ce>=2.5`. Tests via `pytest`; coverage gate is 80% (`pyproject.toml`).

---

## Companion Docs

- [[prd]] — full functional requirements
- [[architecture]] — layers, types, data flow, invariants
- [[build-plan]] — phased build of the system
- [[code-standards]] — engineering conventions
- [[project-state]] — compressed file map
- [[ui-registry]] / [[ui-rules]] / [[ui-tokens]] — interface inventory and conventions
