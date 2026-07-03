from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.release_candidate import (
    release_candidate_readiness,
    validate_vertical_slice_release_candidate,
    vertical_slice_release_candidate_scope,
)


def _split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate vertical-slice release-candidate scope readiness.")
    parser.add_argument("--completed-modes", default="")
    parser.add_argument("--completed-builds", default="")
    parser.add_argument("--passed-smoke-checks", default="")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--run-headless", action="store_true")
    args = parser.parse_args()

    scope = vertical_slice_release_candidate_scope()
    validation = None
    if args.run_headless:
        validation = validate_vertical_slice_release_candidate(Path(args.project_root).resolve())
        readiness = validation.readiness
    else:
        readiness = release_candidate_readiness(
            completed_modes=_split_csv(args.completed_modes),
            completed_builds=_split_csv(args.completed_builds),
            passed_smoke_checks=_split_csv(args.passed_smoke_checks),
            scope=scope,
        )
    payload = {
        "scope_id": scope.scope_id,
        "modes": list(scope.modes),
        "builds": list(scope.builds),
        "smoke_checks": list(scope.smoke_checks),
        "deferred_features": list(scope.deferred_features),
        "ready": readiness.ready,
        "missing_modes": list(readiness.missing_modes),
        "missing_builds": list(readiness.missing_builds),
        "missing_smoke_checks": list(readiness.missing_smoke_checks),
        "summary": readiness.summary(),
    }
    if validation is not None:
        payload["checks"] = validation.checks
        payload["details"] = validation.details
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if readiness.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
