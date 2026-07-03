from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.package_build import BuildInput, ChecksumEntry, distribution_plan


def _load_checksums(path: Path | None) -> tuple[ChecksumEntry, ...]:
    if path is None:
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(ChecksumEntry(item["path"], item["sha256"], item["size_bytes"]) for item in payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare release distribution and update metadata.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--checksums")
    parser.add_argument("--signing-key-id", default="local-dev")
    parser.add_argument("--previous-version", default="0.0.0")
    parser.add_argument("--mandatory", action="store_true")
    args = parser.parse_args()

    checksum_path = Path(args.checksums) if args.checksums else None
    plan = distribution_plan(
        BuildInput(args.version, args.channel),
        args.base_url,
        _load_checksums(checksum_path),
        args.signing_key_id,
        args.previous_version,
        args.mandatory,
    )
    print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
