"""Pack game resources into a single encrypted ``.dat``.

Usage:
    python scripts/build_pack.py [--out dist/resources.dat] [DIR ...]

Defaults to packing ``content/`` and ``assets/``. Logical entry names are
paths relative to the project root, using forward slashes, so the runtime
loader can request e.g. ``content/horses.json``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from horse_racing_game.resources import PackReader, PackWriter
DEFAULT_DIRS = ["content", "assets"]


def _iter_files(directory: Path):
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            yield path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an encrypted resource pack.")
    parser.add_argument("dirs", nargs="*", default=DEFAULT_DIRS, help="directories to pack")
    parser.add_argument("--out", default="dist/resources.dat", help="output pack path")
    args = parser.parse_args()

    writer = PackWriter()
    count = 0
    for rel in args.dirs:
        directory = ROOT / rel
        if not directory.is_dir():
            print(f"skip (missing): {rel}")
            continue
        for path in _iter_files(directory):
            name = path.relative_to(ROOT).as_posix()
            writer.add_file(name, path)
            count += 1

    out = ROOT / args.out
    writer.write(out)
    reader = PackReader(out)  # verify it reads back
    size_mb = out.stat().st_size / 1_048_576
    print(f"Packed {count} files -> {args.out} ({size_mb:.2f} MiB), {len(reader.list_files())} entries verified")


if __name__ == "__main__":
    main()
