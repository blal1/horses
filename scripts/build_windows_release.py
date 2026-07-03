from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.app.package_build import (
    checksum_file,
    default_build_matrix,
    validate_windows_build_inputs,
    windows_build_plan,
)


def windows_release_build_payload(version: str, channel: str, project_root: Path) -> dict[str, object]:
    matrix = default_build_matrix(version, channel)
    plan = windows_build_plan(matrix)
    release_artifact = Path("dist") / channel / plan.artifact_name
    return {
        "version": version,
        "channel": channel,
        "artifact": plan.artifact_name,
        "release_artifact": str(release_artifact),
        "build_output": plan.executable_path,
        "command": list(plan.pyinstaller_command),
        "missing_inputs": list(validate_windows_build_inputs(project_root, plan)),
        "smoke_commands": [list(check.command) for check in plan.smoke_checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Windows release-candidate artifact with PyInstaller.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    payload = windows_release_build_payload(args.version, args.channel, project_root)
    if payload["missing_inputs"]:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    command = [str(item) for item in payload["command"]]
    subprocess.run(command, cwd=project_root, check=True)
    release_artifact = project_root / str(payload["release_artifact"])
    release_artifact.parent.mkdir(parents=True, exist_ok=True)
    unpacked_dir = project_root / "dist" / "windows" / "HorseRacingAudioFirst"
    if not unpacked_dir.is_dir():
        raise SystemExit(f"missing PyInstaller output: {unpacked_dir}")
    archive_base = release_artifact.with_suffix("")
    if release_artifact.suffix == ".zip" and archive_base.suffix:
        archive_base = release_artifact.with_suffix("")
    built_zip = Path(shutil.make_archive(str(archive_base), "zip", unpacked_dir))
    if built_zip != release_artifact:
        if release_artifact.exists():
            release_artifact.unlink()
        built_zip.replace(release_artifact)
    checksum = checksum_file(release_artifact)
    payload["checksum"] = {"path": checksum.path, "sha256": checksum.sha256, "size_bytes": checksum.size_bytes}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
