"""Compile security-sensitive modules to native ``.pyd`` extensions.

Usage (Windows, needs MSVC from Visual Studio Build Tools):
    python scripts/build_cython.py build_ext --inplace

After a successful build each listed module has a matching ``.pyd`` next to
its ``.py``. For a hardened release, delete the source ``.py`` files below
so only the compiled extensions ship — this turns the embedded key shards
and crypto routines into native code that no longer appears as readable
Python source.

Modules are chosen for IP protection: the master key, the crypto core, and
the pack format. Gameplay code stays pure Python for easy iteration.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

import Cython
from setuptools import setup
from Cython.Build import cythonize

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Modules compiled to .pyd. Paths are relative to the project root.
SENSITIVE_MODULES = [
    "horse_racing_game/security/_masterkey.py",
    "horse_racing_game/security/crypto.py",
    "horse_racing_game/resources/pack.py",
]


def _cython_major_version() -> int:
    try:
        return int(Cython.__version__.split(".", 1)[0])
    except (AttributeError, ValueError):
        return 0


def main() -> None:
    if _cython_major_version() < 3:
        raise SystemExit(
            f"Cython >= 3.0 is required for the release build; found {Cython.__version__}. "
            "Run: python -m pip install --upgrade 'cython>=3.0'"
        )
    os.chdir(ROOT)
    modules = list(SENSITIVE_MODULES)
    setup(
        name="horse_racing_game_secure",
        packages=[],  # ext-only build; skip flat-layout package auto-discovery
        ext_modules=cythonize(
            modules,
            compiler_directives={"language_level": "3", "annotation_typing": False},
            build_dir=str(ROOT / "build" / "cython"),
        ),
        script_args=sys.argv[1:] or ["build_ext", "--inplace"],
    )


if __name__ == "__main__":
    main()
