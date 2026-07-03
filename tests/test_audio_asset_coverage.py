import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from horse_racing_game.audio.asset_coverage import (
    coverage_report,
    missing_cue_sound_ids,
    prompt_spec_for_missing,
    write_missing_prompt_spec,
)
from horse_racing_game.audio.event_cues import cue_sound_requirements
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog
from horse_racing_game.content.loaders import load_sound_catalog


ROOT = Path(__file__).parent.parent


def load_generator_module():
    script_path = ROOT / "scripts" / "generate_elevenlabs_audio.py"
    spec = importlib.util.spec_from_file_location("generate_elevenlabs_audio", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _asset(sound_id: str, category: str) -> SoundAsset:
    return SoundAsset(sound_id, Path(f"x/{sound_id}.mp3"), "src", "lic", category, False, 0.5, 40)


def _catalog_missing(*missing_ids: str) -> SoundCatalog:
    requirements = cue_sound_requirements()
    assets = tuple(_asset(sid, cat) for sid, cat in requirements.items() if sid not in missing_ids)
    return SoundCatalog(assets)


class CoverageDetectionTests(unittest.TestCase):
    def test_real_catalog_covers_every_cue(self) -> None:
        # Regression guard: adding a cue with a preferred id not in the manifest
        # should fail here, prompting generation rather than a silent fallback.
        catalog = load_sound_catalog(ROOT / "content" / "sound_manifest.json")
        self.assertEqual(missing_cue_sound_ids(catalog), ())

    def test_missing_ids_are_detected(self) -> None:
        a_cue = next(iter(cue_sound_requirements()))
        catalog = _catalog_missing(a_cue)
        self.assertIn(a_cue, missing_cue_sound_ids(catalog))

    def test_report_text_reflects_state(self) -> None:
        self.assertIn("all preferred cue sounds present", coverage_report(_catalog_missing()))
        a_cue = next(iter(cue_sound_requirements()))
        self.assertIn(a_cue, coverage_report(_catalog_missing(a_cue)))


class PromptSpecTests(unittest.TestCase):
    def test_spec_covers_exactly_the_missing_cues(self) -> None:
        requirements = cue_sound_requirements()
        missing = sorted(list(requirements)[:2])
        spec = prompt_spec_for_missing(_catalog_missing(*missing))
        self.assertEqual(sorted(asset["id"] for asset in spec["assets"]), missing)
        for asset in spec["assets"]:
            self.assertEqual(asset["category"], requirements[asset["id"]])
            self.assertTrue(asset["prompt"])
            self.assertTrue(asset["file"].endswith(".mp3"))

    def test_generated_spec_is_accepted_by_the_generator(self) -> None:
        # The whole point of the loop: our spec must be valid generator input.
        generator = load_generator_module()
        missing = sorted(list(cue_sound_requirements())[:3])
        spec = prompt_spec_for_missing(_catalog_missing(*missing))
        generator._validate_spec(spec)  # raises if malformed
        selected = generator._selected_assets(spec, set(), "sound_effect")
        self.assertEqual(sorted(a["id"] for a in selected), missing)

    def test_complete_coverage_yields_empty_asset_list(self) -> None:
        self.assertEqual(prompt_spec_for_missing(_catalog_missing())["assets"], [])


class WriteSpecTests(unittest.TestCase):
    def test_writes_spec_when_cues_are_missing(self) -> None:
        a_cue = next(iter(cue_sound_requirements()))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.json"
            count = write_missing_prompt_spec(_catalog_missing(a_cue), path)
            self.assertEqual(count, 1)
            self.assertTrue(path.exists())

    def test_writes_nothing_when_coverage_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.json"
            count = write_missing_prompt_spec(_catalog_missing(), path)
            self.assertEqual(count, 0)
            self.assertFalse(path.exists())

    def test_write_missing_prompt_script_reports_complete_real_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "missing_prompts.json"
            result = subprocess.run(
                [
                    "python",
                    "scripts/write_missing_audio_prompt_spec.py",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(result.stdout)

            self.assertEqual(payload["missing_count"], 0)
            self.assertFalse(payload["written"])
            self.assertFalse(output.exists())
            self.assertIn("scripts/generate_elevenlabs_audio.py", payload["generator_command"])

    def test_write_missing_prompt_script_writes_spec_for_incomplete_catalog(self) -> None:
        requirements = cue_sound_requirements()
        missing_id = next(iter(requirements))
        assets = [_asset(sid, cat) for sid, cat in requirements.items() if sid != missing_id]
        catalog_payload = [
            {
                "sound_id": asset.sound_id,
                "path": str(asset.path),
                "source": asset.source,
                "license": asset.license,
                "category": asset.category,
                "loop": asset.loop,
                "default_volume": asset.default_volume,
                "priority": asset.priority,
            }
            for asset in assets
        ]
        with tempfile.TemporaryDirectory() as tmp:
            catalog_path = Path(tmp) / "sound_manifest.json"
            output_path = Path(tmp) / "missing_prompts.json"
            catalog_path.write_text(json.dumps(catalog_payload), encoding="utf-8")

            result = subprocess.run(
                [
                    "python",
                    "scripts/write_missing_audio_prompt_spec.py",
                    "--catalog",
                    str(catalog_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(result.stdout)
            written = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["missing_count"], 1)
            self.assertTrue(payload["written"])
            self.assertEqual(written["assets"][0]["id"], missing_id)


if __name__ == "__main__":
    unittest.main()
