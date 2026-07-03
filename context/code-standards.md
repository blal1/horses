# Code Standards

Implementation rules and conventions for the audio-first horse racing game. Follow these in every change to keep the codebase layered, deterministic, and testable.

---

## Engineering Mindset

- **Read the code first** — `RaceEngine.tick` (simulation), the audio pipeline (`AudioEngine` → `AudioEventPolicy` → `AudioEventRouter`), and `pygame_main.main` define how everything fits. Verify against them before adding anything.
- **Respect the layers** — `domain` and `simulation` are pure. Never reach "down" into pygame or files from them, and never reach "up" from a lower layer into `ui`/`app`.
- **Determinism is sacred** — the simulation must produce identical results for the same `(seed, content, commands)`. No wall-clock time, no global RNG, no unseeded randomness in the engine.
- **Audio-first** — any new race state the player needs must emit a `RaceEvent` that becomes speech and/or a sound cue. Do not encode game state in visuals only.
- **Clean over clever** — straightforward, type-hinted Python that reads top-to-bottom beats abstraction.
- **Degrade gracefully** — missing sound files, absent NVDA, or a corrupt save must log and continue, never crash a race.

---

## Python

- Target Python ≥ 3.10 (`pyproject.toml`). Use modern syntax: `X | None`, `tuple[Horse, ...]`, structural `match` where it clarifies.
- Prefer `@dataclass(frozen=True)` for data types (domain objects, events, state, config, results). Immutability is the default.
- Type-hint every function signature. Keep functions small and single-purpose.
- Standard library first — the only third-party runtime dependency is `pygame-ce`. Don't add dependencies without strong justification.
- Raise specific exceptions with context (`ValueError(f"Unknown player horse: {id}")`). Loaders point at the offending file path.

---

## Determinism & Simulation

This is the most important rule set — break it and replays, tests, and balance tuning all rot.

- The engine's only randomness is `self._rng = random.Random(seed)`. Never call the module-level `random.*`, `time.*`, or `datetime.now()` inside `simulation/`.
- Keep physics changes in `_update_runner` / `_update_paces`; document non-obvious tuning constants with a short comment (as `_opponent_target_pace` does).
- Snapshots (`_snapshot`) round values so `RaceState` comparisons are stable — preserve that rounding.
- New mechanics emit `RaceEvent`s; they do not mutate UI or audio directly.

---

## Layer Boundaries

| Layer        | May import                          | Must NOT import        |
| ------------ | ----------------------------------- | ---------------------- |
| `domain`     | stdlib only                         | everything else        |
| `simulation` | `domain`, `input.commands`          | `audio`, `ui`, `app`   |
| `content`    | `domain`, `audio.sound_catalog`     | `ui`, `app`            |
| `audio`      | `domain`, `simulation`, `app.runtime_log` | `ui`             |
| `input`      | `input.commands`, stdlib            | `ui`, `app`            |
| `ui`         | all lower layers                    | —                      |
| `app`        | anything                            | —                      |

Keep business logic out of the pygame event loop. A UI screen reads input, calls the engine/services, routes events, and draws — the logic lives in `simulation`/`app`.

---

## Audio

- Always go through the `AudioBackend` ABC (`play_2d / play_3d / play_loop / stop_sound / speak / stop_all`). Never call `pygame.mixer` directly outside `PygameAudioBackend`.
- New event types: add a cooldown in `AudioEventPolicy._EVENT_COOLDOWNS` (if it can spam), a cue in `event_cues._CUE_RULES` (preferred id + fallback category/token), and a branch in `AudioEventRouter.route`.
- Resolve sounds through the `SoundCatalog` with a fallback — never hardcode a raw file path in routing.
- Spoken lines are short, plain sentences (see `voice_feedback.py`). Update `HELP_TEXT` if controls change.
- NVDA access is isolated in `NvdaSpeaker`; it must swallow `ctypes`/`OSError` failures and log once.

---

## Content & Data

- Game data lives in `content/*.json`. Add fields by extending both the JSON and the matching `_parse_*` in `loaders.py` with strict typed accessors.
- Validate on load: unknown ids raise in `bootstrap`, missing referenced sound files raise via `SoundCatalog.missing_files`.
- Don't hardcode horse/track/weather/stable ids in code beyond the documented defaults in `AppConfig` / `GameProgress`.

---

## Persistence

- The only mutable on-disk state is `save/progress.json` via `app/progress.py`. `content/` is read-only at runtime.
- `load_progress` is tolerant: missing or corrupt file → fresh `GameProgress()` defaults. Keep it that way.
- When adding a `GameProgress` field, give it a default, parse it defensively in `load_progress`, and persist it in `record_*`.
- `write_runtime_log` (`app/runtime_log.py`) is for diagnostics (`runtime_debug.log`), not game state.

---

## Testing

- `pytest` with coverage `fail_under = 80` (`pyproject.toml`, source = `horse_racing_game`). Don't merge below the gate.
- Test pure logic directly: drive `RaceEngine`/`GameApp` with scripted `RaceCommand`s; assert on `RaceState` and emitted events.
- Test audio via `FakeAudioBackend` and inspect recorded `AudioCall`s — never require a real audio device.
- One test file per subsystem, mirroring `tests/` naming (`test_<subsystem>.py`).
- Pygame screens use smoke tests under a dummy video driver; keep them fast and non-interactive.

---

## Naming & Style

- Snake_case modules and functions; `PascalCase` classes; `UPPER_SNAKE` constants.
- Suffix units in names where it matters: `_m` (metres), `_mps`, `_s`, `_hz`.
- Private engine/runtime helpers are underscore-prefixed (`_update_runner`, `_RunnerRuntime`).
- Match the surrounding file's comment density — comment the "why" of non-obvious tuning, not the obvious.

---

## Dependencies

Current runtime dependency (`pyproject.toml`):

- `pygame-ce >= 2.5` — window, input, mixer, clock.

NVDA speech uses the bundled `nvdaControllerClient64.dll` via `ctypes` (no pip package). Before adding any dependency, ask whether the standard library or pygame already covers it.
