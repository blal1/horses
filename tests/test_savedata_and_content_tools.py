import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import atomic_write_json, load_json_array, load_json_object
from horse_racing_game.app.track_editor import build_custom_track, load_custom_tracks, save_custom_track
from horse_racing_game.content.pack_file import PackFile


class FileDirectoriesTests(unittest.TestCase):
    def test_directory_paths_are_derived_from_project_root(self) -> None:
        directories = FileDirectories(Path("/tmp/project"))

        self.assertEqual(directories.content_root, Path("/tmp/project/content"))
        self.assertEqual(directories.save_root, Path("/tmp/project/save"))
        self.assertEqual(directories.progress_file(), Path("/tmp/project/save/progress.json"))
        self.assertEqual(directories.custom_tracks_file(), Path("/tmp/project/save/custom_tracks.json"))


class SavedDataTests(unittest.TestCase):
    def test_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            payload = {"name": "ember", "values": [1, 2, 3]}

            atomic_write_json(path, payload)

            self.assertEqual(load_json_object(path), payload)

    def test_json_array_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            payload = [1, 2, 3]

            atomic_write_json(path, payload)

            self.assertEqual(load_json_array(path), payload)


class PackFileTests(unittest.TestCase):
    def test_reads_json_array_from_file_or_directory_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_file = root / "items.json"
            data_file.write_text('[{"id": "a"}, {"id": "b"}]', encoding="utf-8")

            from_file = PackFile.from_path(data_file)
            from_root = PackFile.from_path(root)

            self.assertEqual(from_file.read_json_array("items.json"), [{"id": "a"}, {"id": "b"}])
            self.assertEqual(from_root.read_json_array("items.json"), [{"id": "a"}, {"id": "b"}])


class CustomTrackSaveTests(unittest.TestCase):
    def test_custom_track_save_round_trips_through_track_loader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            track = build_custom_track(
                load_custom_track_draft(),
            )

            save_custom_track(root, track)
            restored = load_custom_tracks(root)

            self.assertEqual(len(restored), 1)
            self.assertEqual(restored[0].track_id, track.track_id)
            self.assertEqual(restored[0].name, track.name)


def load_custom_track_draft():
    from horse_racing_game.app.track_editor import TrackDraft

    return TrackDraft(length_m=1450.0, surface="mud", handedness="left", curve_intensity=0.45)


if __name__ == "__main__":
    unittest.main()
