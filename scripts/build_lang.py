"""Encrypt source localization JSON files into shipped .lng files.

Source files live outside the shipped content tree by default:

    localization/*.json -> content/lang/*.lng

The encrypted output is later included in resources.dat by build_pack.py.
If localization/ does not exist yet, this script is a no-op.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from horse_racing_game.app.localization import (
    localization_catalog_from_dict,
    write_encrypted_localization_catalog,
)


def build_language_files(source_dir: Path, output_dir: Path) -> tuple[Path, ...]:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    if not source_dir.exists():
        return ()
    written: list[Path] = []
    for source in sorted(source_dir.glob("*.json")):
        parsed = json.loads(source.read_text(encoding="utf-8-sig"))
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected localization object in {source}")
        catalog = localization_catalog_from_dict(parsed)
        target = output_dir / f"{source.stem}.lng"
        write_encrypted_localization_catalog(target, catalog)
        written.append(target)
    return tuple(written)


def main() -> int:
    parser = argparse.ArgumentParser(description="Encrypt localization JSON files for release packaging.")
    parser.add_argument("--source", default="localization")
    parser.add_argument("--out", default=str(Path("content") / "lang"))
    args = parser.parse_args()

    written = build_language_files(ROOT / args.source, ROOT / args.out)
    if written:
        print(f"Encrypted {len(written)} language file(s) -> {args.out}")
    else:
        print(f"No source language directory found at {args.source}; skipping.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
