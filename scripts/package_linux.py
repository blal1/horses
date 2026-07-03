from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.package_build import (
    default_build_matrix,
    linux_build_plan,
    validate_linux_build_inputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the Linux packaging plan.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--format", default=None, choices=("tar.gz", "appimage"))
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    matrix = default_build_matrix(args.version, args.channel)
    plan = linux_build_plan(matrix, package_format=args.format)
    missing = validate_linux_build_inputs(project_root, plan)
    payload = {
        "artifact": plan.artifact_name,
        "command": list(plan.pyinstaller_command),
        "executable_path": plan.executable_path,
        "desktop_entry": plan.desktop_entry.text(),
        "runtime_validation": {
            "required_python": plan.runtime_validation.required_python,
            "required_modules": list(plan.runtime_validation.required_modules),
            "required_tools": list(plan.runtime_validation.required_tools),
            "sdl_video_driver_fallback": plan.runtime_validation.sdl_video_driver_fallback,
        },
        "appimage_metadata": dict(plan.appimage_metadata),
        "smoke_checks": [
            {"id": check.check_id, "command": list(check.command), "expected": check.expected}
            for check in plan.smoke_checks
        ],
        "missing_inputs": list(missing),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
