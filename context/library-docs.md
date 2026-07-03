# Library Docs

How this project uses each external dependency and the key standard-library patterns. Read the relevant section before touching code that depends on it. These notes cover project-specific usage only — consult upstream docs for full APIs.

Runtime dependency (`pyproject.toml`):

```
pygame-ce >= 2.5
```

Plus the bundled `nvdaControllerClient64.dll` (loaded via `ctypes`, no pip package). Everything else is the Python standard library.

---

## pygame-ce

The game framework: window, input, audio mixer, and frame clock. Used only inside `ui/` and `audio/pygame_*` — never in `domain`/`simulation`.

```python
import pygame

pygame.init()
screen = pygame.display.set_mode((980, 640))     # menu / game window
clock = pygame.time.Clock()
clock.tick(60)                                    # UI_FRAME_RATE

for event in pygame.event.get():                  # input
    if event.type == pygame.KEYDOWN: ...

pygame.mixer.Sound(path).play()                   # SFX
pygame.mixer.music.load(path); pygame.mixer.music.play(-1)   # music loop
```

**Usage here:**

- **Display/clock:** `PygameRaceGame.run()` runs a fixed-rate loop (`UI_FRAME_RATE = 60`), advancing the engine one tick per frame. The menu uses a `980x640` window.
- **Input:** key events are mapped to a `RaceCommand` (arrows / WASD / ZQSD for pace+lane, Space push, J jump, K/Ctrl duck, Tab/Enter status, R repeat, M menu, N restart, Esc quit).
- **Mixer:** `PygameAudioBackend` loads `SoundAsset`s into `pygame.mixer.Sound`, plays one-shot 2D/3D cues (panning via channel volume / relative position) and loops; `pygame_music.py` handles background tracks and volume.

**Rules:**

- Confine pygame to `ui/` and `audio/pygame_*`. Lower layers stay framework-free.
- Cache loaded `Sound` objects; track failed ids so a missing file is attempted once, logged, then skipped.
- For headless runs/tests, use the dummy drivers (`SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`) — tests prefer `FakeAudioBackend` and avoid the real mixer entirely.

---

## NVDA Controller Client (`nvdaControllerClient64.dll`)

Screen-reader speech on Windows, wrapped by `audio/nvda_speaker.py` using `ctypes`.

```python
import ctypes
dll = ctypes.WinDLL(str(project_root / "nvdaControllerClient64.dll"))
dll.nvdaController_testIfRunning()      # 0 == NVDA running
dll.nvdaController_cancelSpeech()
dll.nvdaController_speakText("Final stretch.")
```

**Usage here:**

- `NvdaSpeaker.speak(text)` lazy-loads the DLL, checks NVDA is running, cancels prior speech, then speaks. `PygameAudioBackend.speak` calls into it.

**Rules:**

- All DLL access stays in `NvdaSpeaker`. Catch `OSError`/`AttributeError`/`ctypes.ArgumentError`, log once via `write_runtime_log`, and set a "failed" flag so it is not retried.
- A missing DLL or absent NVDA is non-fatal — the game still plays with sound cues; speech is simply skipped.

### Cross-platform speech (`audio/speech.py`)

`NvdaSpeaker` is one implementation of the `Speaker` ABC. `create_speaker(project_root, platform)` selects a backend by OS:

- **Windows** → `NvdaSpeaker` (the DLL above).
- **macOS** → `MacSpeaker` → `say <text>`.
- **Linux** → `LinuxSpeaker` → `spd-say -C <text>` (speech-dispatcher).
- **other / tool missing** → `NullSpeaker` (no-op).

The subprocess backends take an injectable `runner` (default `subprocess.run`) so tests never spawn a process, and disable themselves after the first failure. `PygameAudioBackend.speak` calls whichever `Speaker` the factory returned — it never branches on platform itself.

---

## Standard Library Patterns

The codebase leans on the stdlib instead of extra dependencies:

- **`dataclasses`** — every data type (`@dataclass(frozen=True)`): domain objects, `RaceEvent`, `RaceState`, `AppConfig`, `GameServices`, results, menu models. Use `field(default_factory=...)` for mutable defaults (e.g. `rival_stable_ids`).
- **`random.Random`** — the engine's seeded RNG (`RaceEngine._rng`). The **only** source of randomness in `simulation/`; never the module-level `random`.
- **`json`** — all content + save I/O. Loaders read with `encoding="utf-8-sig"` (tolerates BOM) and validate types strictly.
- **`pathlib.Path`** — every path. `content_root`, `project_root`, sound asset paths, `save/progress.json`. Never string-concatenate paths.
- **`ctypes`** — NVDA DLL binding (see above).
- **`abc`** — backend abstractions (`AudioBackend`, `InputBackend`) with fake + real implementations.
- **`collections.abc` / `collections.deque`** — `Iterable[RaceCommand]` in `GameApp`; deque for recent-event buffers in the UI.
- **`traceback`** — `pygame_main` logs full tracebacks to `runtime_debug.log` on unhandled exceptions.

**Rule:** reach for the standard library before adding a dependency. See [[code-standards]] → Dependencies.

---

## Optional: ElevenLabs Generated Audio

`content/elevenlabs_audio_prompts.json` describes optional generated sound effects. `content/loaders.py` (`_load_existing_elevenlabs_sound_effects`) merges any of those assets that actually exist on disk into the `SoundCatalog`. This is a build-time/asset-generation aid, not a runtime dependency — no ElevenLabs API is called while the game runs.

**The generation loop:**

1. `audio/asset_coverage.py` — `missing_cue_sound_ids(catalog)` / `coverage_report(catalog)` report which preferred cue sounds (`event_cues.cue_sound_requirements()`) the catalog lacks. `prompt_spec_for_missing` / `write_missing_prompt_spec` emit a generation spec covering exactly those.
2. `scripts/generate_elevenlabs_audio.py` — reads a spec (`--spec`), generates SFX/music with provider+key fallback, retries, resume state, and `--dry-run`; writes files under `output_dir`, a generated manifest, and optionally `--merge-manifest` into `content/sound_manifest.json`. Needs `ELEVENLABS_API_KEY` (or a providers config) only when actually generating.
3. The merged manifest is loaded by `SoundCatalog` on next run, so the new cue sounds resolve directly instead of falling back.

`tools/` and `scripts/` hold the generation helpers (see `test_elevenlabs_generator.py`, `test_audio_asset_coverage.py`).
