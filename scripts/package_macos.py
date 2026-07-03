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
    macos_build_plan,
    validate_macos_build_inputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the macOS packaging plan.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    matrix = default_build_matrix(args.version, args.channel)
    plan = macos_build_plan(matrix)
    missing = validate_macos_build_inputs(project_root, plan)
    payload = {
        "artifact": plan.artifact_name,
        "command": list(plan.pyinstaller_command),
        "app_bundle_path": plan.app_bundle_path,
        "executable_path": plan.executable_path,
        "bundle_metadata": plan.bundle_metadata.plist(matrix.version),
        "runtime_validation": {
            "required_python": plan.runtime_validation.required_python,
            "required_modules": list(plan.runtime_validation.required_modules),
            "required_tools": list(plan.runtime_validation.required_tools),
            "speech_fallback": plan.runtime_validation.speech_fallback,
        },
        "distribution_notes": {
            "quarantine": plan.distribution_notes.quarantine_note,
            "notarization": plan.distribution_notes.notarization_note,
            "codesign_identity": plan.distribution_notes.codesign_identity,
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
