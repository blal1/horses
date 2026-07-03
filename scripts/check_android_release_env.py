from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.release_candidate import android_debug_build_environment


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Android debug build environment readiness.")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    payload = android_debug_build_environment(project_root)
    payload["ready_for_assemble_debug"] = bool(
        payload["java_on_path"]
        and payload["sdk_root_exists"]
        and (payload["gradle_wrapper"] or payload["gradle_on_path"])
    )
    payload["ready_for_device_smoke"] = bool(payload["ready_for_assemble_debug"] and payload["adb_available"])
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ready_for_assemble_debug"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
