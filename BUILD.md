# Build

## Prerequisites

- Python 3.10
- Visual Studio Build Tools with MSVC C++ compiler
- `pip` or `uv`
- Windows SDK `signtool.exe` only for signed releases

## Setup

```powershell
python -m pip install --upgrade pip
python -m pip install -e . pytest pyinstaller cython setuptools
```

## Verify

```powershell
python -m pytest
python scripts/build_lang.py
python scripts/build_pack.py --out dist/resources.dat
```

Expected outputs:

- `content/lang/*.lng` when `localization/*.json` source files exist
- `dist/resources.dat`

## Unsigned Release

```powershell
python scripts/build_release.py
```

Expected output:

- `dist/resources.dat`
- encrypted `content/lang/*.lng` files when localization source exists
- native extensions for the sensitive modules
- `dist/HorseRacingAudioFirst/HorseRacingAudioFirst.exe`
- `dist/HorseRacingAudioFirst/install-integrity.json`

## Signed Release

```powershell
$env:SIGNTOOL_CERT_SHA1 = "<certificate thumbprint>"
python scripts/build_release.py --sign
```

Optional overrides:

```powershell
python scripts/build_release.py --sign --signtool "C:\Path\signtool.exe" --timestamp-url "http://timestamp.digicert.com"
```

## Hardened Shipping Build

Run this only from a clean checkout or disposable release workspace because it removes the Python sources for compiled sensitive modules after verifying matching native extensions exist.

```powershell
python scripts/build_release.py --strip-sources --sign
```
