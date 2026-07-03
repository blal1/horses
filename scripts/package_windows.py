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
    validate_windows_build_inputs,
    windows_build_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the Windows packaging plan.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    matrix = default_build_matrix(args.version, args.channel)
    plan = windows_build_plan(matrix)
    missing = validate_windows_build_inputs(project_root, plan)
    payload = {
        "artifact": plan.artifact_name,
        "command": list(plan.pyinstaller_command),
        "executable_path": plan.executable_path,
        "nvda_dll_path": plan.nvda_dll_path,
        "shortcut": {
            "name": plan.launcher_shortcut.name,
            "target": plan.launcher_shortcut.target,
            "working_directory": plan.launcher_shortcut.working_directory,
            "description": plan.launcher_shortcut.description,
        },
        "save_migration": {
            "from": plan.save_migration.legacy_relative_path,
            "to": plan.save_migration.platform_save_path,
        },
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
