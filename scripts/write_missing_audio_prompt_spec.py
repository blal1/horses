from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from horse_racing_game.audio.asset_coverage import coverage_report, write_missing_prompt_spec
from horse_racing_game.content.loaders import load_sound_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Write an ElevenLabs prompt spec for missing preferred cue sounds.")
    parser.add_argument("--catalog", default="content/sound_manifest.json")
    parser.add_argument("--output", default="content/missing_cue_audio_prompts.json")
    args = parser.parse_args()

    catalog_path = (PROJECT_ROOT / args.catalog).resolve()
    output_path = (PROJECT_ROOT / args.output).resolve()
    catalog = load_sound_catalog(catalog_path)
    count = write_missing_prompt_spec(catalog, output_path)
    payload = {
        "catalog": str(catalog_path),
        "output": str(output_path),
        "missing_count": count,
        "written": count > 0,
        "report": coverage_report(catalog),
        "generator_command": [
            "python",
            "scripts/generate_elevenlabs_audio.py",
            "--spec",
            args.output,
            "--merge-manifest",
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
