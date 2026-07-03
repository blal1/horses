# Horse Racing Audio First

Audio-first horse racing game prototype built in Python. The project focuses on
playable racing with strong audio feedback, accessibility-friendly controls,
replays, career progression, content packaging, and a hardened Windows release
pipeline.

## Features

- Pygame-based horse racing loop with keyboard and touch input support.
- Audio-first race feedback, spatial audio cues, speech hooks, and generated
  sound manifests.
- Quick race, training, replay, career, championship, track editor, and
  multiplayer prototype modules.
- Secure save support for progression/profile data.
- Encrypted resource pack support for release builds.
- Windows release tooling with Cython compilation for sensitive modules,
  PyInstaller packaging, optional Authenticode signing, and install integrity
  manifest generation.
- Android prototype shell and release-candidate validation helpers.

## Requirements

- Python 3.10
- `pip` or `uv`
- Windows with Visual Studio Build Tools/MSVC for hardened release builds
- Optional: Windows SDK `signtool.exe` for signed Windows releases

## Setup

```powershell
python -m pip install --upgrade pip
python -m pip install -e . pytest
```

For release-build work:

```powershell
python -m pip install pyinstaller cython setuptools
```

## Run

```powershell
python play_game.py
```

Alternative module entry point:

```powershell
python -m horse_racing_game
```

## Test

```powershell
python -m pytest
```

## Build

Build language outputs and the encrypted resource pack:

```powershell
python scripts/build_lang.py
python scripts/build_pack.py --out dist/resources.dat
```

Create an unsigned Windows release:

```powershell
python scripts/build_release.py
```

More details are in [BUILD.md](BUILD.md).

## Security Notes

This project includes client-side hardening for shipped builds: authenticated
encryption, encrypted resource packs, secure saves, Cython-built sensitive
modules, signed protocol-message primitives, replay/rate-limit helpers, and
install integrity checks.

Client-side protection is a speed bump, not a vault. The game intentionally
does not use hostile anti-VM, anti-debug, or accessibility-breaking checks.
See [docs/security-remaining-steps.md](docs/security-remaining-steps.md) and
[docs/multiplayer-security-threat-model.md](docs/multiplayer-security-threat-model.md).

## Repository Hygiene

Generated outputs are ignored, including `build/`, `dist/`, `.venv/`, caches,
local saves, logs, generated encrypted language outputs, Cython-generated C
files, native `.pyd` files, and Android signing secrets.

## Assets And Licenses

The repository contains downloaded and generated audio assets used by the
prototype. License/reference files live under `assets/licenses/` and related
asset directories. Review those files before redistribution.
