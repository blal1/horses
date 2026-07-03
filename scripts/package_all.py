from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.package_build import BuildInput, build_automation_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the full multi-platform packaging automation plan.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    parser.add_argument("--changelog", default="")
    args = parser.parse_args()

    plan = build_automation_plan(BuildInput(args.version, args.channel, args.changelog))
    payload = {
        "version": plan.inputs.version,
        "channel": plan.inputs.channel,
        "changelog": plan.inputs.changelog,
        "clean_dirs": list(plan.clean_dirs),
        "dist_dir": plan.dist_dir,
        "manifest_path": plan.manifest_path,
        "artifact_manifest": list(plan.artifact_manifest),
        "jobs": [
            {
                "id": job.job_id,
                "platform": job.platform,
                "artifact": job.artifact_name,
                "command": list(job.command),
                "log_path": job.log_path,
            }
            for job in plan.jobs
        ],
        "ci_commands": [list(command) for command in plan.ci_commands],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
