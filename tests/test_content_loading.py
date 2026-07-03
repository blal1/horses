import unittest
import tempfile
from pathlib import Path

from horse_racing_game.app.championship import load_championship_calendar
from horse_racing_game.content.loaders import load_horses, load_rivals, load_sound_catalog, load_stables, load_tracks, load_weather


class ContentLoadingTests(unittest.TestCase):
    def test_loads_existing_content_files(self) -> None:
        root = Path(__file__).parent.parent

        horses = load_horses(root / "content" / "horses.json")
        rivals = load_rivals(root / "content" / "rivals.json")
        tracks = load_tracks(root / "content" / "tracks.json")
        weather_options = load_weather(root / "content" / "weather.json")
        stables = load_stables(root / "content" / "stables.json")
        calendar = load_championship_calendar(root / "content" / "championship.json")
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")

        self.assertEqual(len(horses), 12)
        self.assertEqual(len(rivals), 6)
        self.assertEqual(rivals[0].horse_id, "copper_gate")
        self.assertEqual(len(tracks), 4)
        self.assertEqual(tracks[-1].track_id, "meadowbrook_mile")
        self.assertEqual(len(weather_options), 4)
        self.assertEqual(weather_options[-1].weather_id, "fog")
        self.assertEqual(len(stables), 4)
        self.assertEqual(stables[0].stable_id, "oak_lane")
        self.assertEqual(len(calendar), 6)
        self.assertEqual(calendar[0].race_id, "rookie_cup_opening")
        self.assertEqual(calendar[-1].weather_id, "rain")
        self.assertGreaterEqual(len(catalog), 148)
        self.assertIsNotNone(catalog.get("mixkit_horse_85"))
        self.assertIsNotNone(catalog.get("ui_move_soft_tick"))
        self.assertIsNone(catalog.get("music_menu_pastoral_loop"))

    def test_missing_content_file_raises_clear_error(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_horses(Path("does-not-exist.json"))

    def test_invalid_json_shapes_raise_clear_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            object_file = root / "object.json"
            object_file.write_text("{}", encoding="utf-8")
            scalar_entry_file = root / "scalar_entry.json"
            scalar_entry_file.write_text("[1]", encoding="utf-8")
            bad_elevenlabs = root / "elevenlabs_audio_prompts.json"
            bad_elevenlabs.write_text("[]", encoding="utf-8")
            sound_manifest = root / "sound_manifest.json"
            sound_manifest.write_text("[]", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_horses(object_file)
            with self.assertRaises(ValueError):
                load_horses(scalar_entry_file)
            with self.assertRaises(ValueError):
                load_sound_catalog(sound_manifest)


if __name__ == "__main__":
    unittest.main()
