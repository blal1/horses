import importlib.util
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


def load_generator_module():
    script_path = Path(__file__).parent.parent / "scripts" / "generate_elevenlabs_audio.py"
    spec = importlib.util.spec_from_file_location("generate_elevenlabs_audio", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load ElevenLabs generator script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ElevenLabsGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = load_generator_module()

    def test_selects_assets_by_id_and_kind(self) -> None:
        spec = {
            "assets": [
                {"id": "ui_tick", "kind": "sound_effect"},
                {"id": "menu_music", "kind": "music"},
                {"id": "rain_loop", "kind": "sound_effect"},
            ]
        }

        selected = self.generator._selected_assets(spec, {"ui_tick", "menu_music"}, "sound_effect")

        self.assertEqual([asset["id"] for asset in selected], ["ui_tick"])

    def test_manifest_entry_uses_generated_path_and_audio_metadata(self) -> None:
        asset = {
            "id": "ui_tick",
            "file": "sfx/ui_tick.mp3",
            "category": "ui",
            "loop": False,
            "volume": 0.45,
            "priority": 33,
            "prompt": "Short UI tick.",
        }

        entry = self.generator._manifest_entry(Path("assets/generated/elevenlabs"), asset)

        self.assertEqual(entry["sound_id"], "ui_tick")
        self.assertEqual(entry["path"], "assets/generated/elevenlabs/sfx/ui_tick.mp3")
        self.assertEqual(entry["category"], "ui")
        self.assertEqual(entry["default_volume"], 0.45)
        self.assertEqual(entry["priority"], 33)

    def test_prompt_text_applies_default_production_suffix(self) -> None:
        asset = {"prompt": "Short hoof cue."}
        defaults = {"prompt_suffix": "Production-ready game audio, no clipping."}

        prompt = self.generator._prompt_text(asset, defaults)

        self.assertEqual(prompt, "Short hoof cue. Production-ready game audio, no clipping.")

    def test_validate_spec_rejects_out_of_range_sfx_duration(self) -> None:
        spec = {
            "output_dir": "assets/generated/elevenlabs",
            "generated_manifest": "content/generated_elevenlabs_sound_manifest.json",
            "assets": [
                {
                    "id": "bad_tick",
                    "kind": "sound_effect",
                    "category": "ui",
                    "file": "sfx/bad_tick.mp3",
                    "duration_seconds": 0.1,
                    "prompt": "Too short.",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "between 0.5 and 30.0"):
            self.generator._validate_spec(spec)

    def test_validate_audio_rejects_tiny_partial_file(self) -> None:
        asset = {"id": "partial", "duration_seconds": 2.0}

        with self.assertRaisesRegex(RuntimeError, "too small to be complete"):
            self.generator._validate_audio_bytes(b"ID3tiny", asset)

    def test_existing_sound_effect_manifest_entries_include_all_existing_sfx(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "generated"
            (output_root / "sfx").mkdir(parents=True)
            (output_root / "sfx" / "ui_tick.mp3").write_bytes(b"fake audio bytes for manifest only")
            spec = {
                "assets": [
                    {
                        "id": "ui_tick",
                        "kind": "sound_effect",
                        "category": "ui",
                        "file": "sfx/ui_tick.mp3",
                        "prompt": "Short UI tick.",
                    },
                    {
                        "id": "menu_music",
                        "kind": "music",
                        "category": "music",
                        "file": "music/menu_music.mp3",
                        "prompt": "Menu music.",
                    },
                ]
            }

            entries = self.generator._existing_sound_effect_manifest_entries(output_root, spec)

        self.assertEqual([entry["sound_id"] for entry in entries], ["ui_tick"] )

    def test_quota_exhausted_key_falls_back_and_stays_disabled(self) -> None:
        providers = [
            self.generator.ProviderSpec("key_1", "elevenlabs", "https://api.elevenlabs.io", "first"),
            self.generator.ProviderSpec("key_2", "elevenlabs", "https://api.elevenlabs.io", "second"),
        ]
        calls = []

        def fake_generate(provider, asset, defaults, timeout, retries):
            calls.append((provider.name, asset["id"]))
            if provider.name == "key_1":
                raise self.generator.ProviderAPIError(
                    provider.name,
                    402,
                    '{"detail":{"code":"quota_exceeded","message":"0 credits remaining"}}',
                    "https://api.elevenlabs.io/v1/sound-generation",
                )
            return b"ID3" + (b"\0" * 4096)

        unavailable_all = set()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            first_asset = {
                "id": "asset_a",
                "kind": "sound_effect",
                "file": "sfx/asset_a.mp3",
                "prompt": "A.",
                "category": "ui",
            }
            second_asset = dict(first_asset, id="asset_b", file="sfx/asset_b.mp3")
            with mock.patch.object(self.generator, "_generate_with_provider", side_effect=fake_generate):
                first = self.generator._generate_asset_with_fallback(
                    providers, unavailable_all, {}, output_root, first_asset, {}, False, 1.0, 0
                )
                second = self.generator._generate_asset_with_fallback(
                    providers, unavailable_all, {}, output_root, second_asset, {}, False, 1.0, 0
                )

        self.assertEqual(first.provider_name, "key_2")
        self.assertEqual(second.provider_name, "key_2")
        self.assertIn("key_1", unavailable_all)
        self.assertEqual(calls, [("key_1", "asset_a"), ("key_2", "asset_a"), ("key_2", "asset_b")])
    def test_merge_manifest_replaces_generated_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "sound_manifest.json"
            self.generator._write_json(
                manifest_path,
                [
                    {"sound_id": "existing", "path": "assets/existing.mp3"},
                    {"sound_id": "ui_tick", "path": "old/generated/path.mp3"},
                ],
            )

            self.generator._merge_manifest(
                manifest_path,
                [{"sound_id": "ui_tick", "path": "assets/generated/elevenlabs/sfx/ui_tick.mp3"}],
            )

            merged = self.generator._load_json(manifest_path)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["sound_id"], "existing")
        self.assertEqual(merged[1]["path"], "assets/generated/elevenlabs/sfx/ui_tick.mp3")


if __name__ == "__main__":
    unittest.main()


