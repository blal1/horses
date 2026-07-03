from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.package_build import (
    BuildInput,
    evaluate_release_artifacts,
    release_validation_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and evaluate release validation smoke tests.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    plan = release_validation_plan(BuildInput(args.version, args.channel))
    results = evaluate_release_artifacts(project_root, plan)
    payload = {
        "version": plan.version,
        "channel": plan.channel,
        "checksum_manifest_path": plan.checksum_manifest_path,
        "artifact_manifest": list(plan.artifact_manifest),
        "tests": [
            {
                "id": test.test_id,
                "description": test.description,
                "command": list(test.command),
                "required_artifact": test.required_artifact,
            }
            for test in plan.tests
        ],
        "results": [
            {"id": result.test_id, "status": result.status, "detail": result.detail}
            for result in results
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
