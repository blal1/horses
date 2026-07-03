from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.android_device_smoke import run_android_device_smoke
from horse_racing_game.app.release_candidate import android_debug_build_environment


def main() -> int:
    parser = argparse.ArgumentParser(description="Install and launch the Android debug APK on a connected adb device.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--apk", default="")
    parser.add_argument("--serial", default="")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    environment = android_debug_build_environment(project_root)
    adb_path = str(environment.get("adb_path") or "adb")
    apk_path = Path(args.apk) if args.apk else project_root / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    payload = run_android_device_smoke(
        adb_path,
        apk_path,
        serial=args.serial or None,
        timeout_seconds=args.timeout_seconds,
    )
    payload["adb_path"] = adb_path
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["ready"]:
        return 0
    return 2 if payload.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
