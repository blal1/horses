import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.progress import load_progress, record_track_editor_selection
from horse_racing_game.app.track_editor import (
    CUSTOM_TRACK_ID,
    CUSTOM_TRACK_SLOTS,
    adjust_draft,
    build_custom_track,
    custom_track_identity,
    custom_tracks_path,
    draft_from_track,
    draft_summary,
    load_available_tracks,
    load_custom_tracks,
    save_custom_track,
)
from horse_racing_game.content.loaders import load_tracks


class TrackEditorTests(unittest.TestCase):
    def test_adjust_draft_changes_audio_first_fields(self) -> None:
        root = Path(__file__).parent.parent
        draft = draft_from_track(load_tracks(root / "content" / "tracks.json")[0])

        longer = adjust_draft(draft, 0, 1)
        surface = adjust_draft(draft, 1, 1)
        direction = adjust_draft(draft, 2, 1)
        curve = adjust_draft(draft, 3, 1)

        self.assertEqual(longer.length_m, draft.length_m + 100.0)
        self.assertNotEqual(surface.surface, draft.surface)
        self.assertNotEqual(direction.handedness, draft.handedness)
        self.assertGreater(curve.curve_intensity, draft.curve_intensity)

    def test_build_custom_track_creates_valid_segments(self) -> None:
        root = Path(__file__).parent.parent
        draft = adjust_draft(draft_from_track(load_tracks(root / "content" / "tracks.json")[0]), 0, -2)

        track = build_custom_track(draft)

        self.assertEqual(track.track_id, CUSTOM_TRACK_ID)
        self.assertEqual(track.length_m, draft.length_m)
        self.assertEqual(track.final_stretch_start_m, draft.length_m * 0.75)
        self.assertEqual(track.segments[-1].end_m, draft.length_m)
        self.assertIn("Custom track draft.", draft_summary(draft))

    def test_custom_track_slots_create_distinct_named_tracks(self) -> None:
        root = Path(__file__).parent.parent
        draft = draft_from_track(load_tracks(root / "content" / "tracks.json")[0])

        first = build_custom_track(draft, 0)
        second = build_custom_track(adjust_draft(draft, 0, 1), 1)

        self.assertEqual(custom_track_identity(0), CUSTOM_TRACK_SLOTS[0])
        self.assertEqual(first.track_id, "custom_audio_track")
        self.assertEqual(second.track_id, "custom_audio_track_2")
        self.assertEqual(second.name, "Custom Audio Track 2")
        self.assertNotEqual(first.track_id, second.track_id)

    def test_save_and_load_custom_track_round_trips(self) -> None:
        root = Path(__file__).parent.parent
        draft = draft_from_track(load_tracks(root / "content" / "tracks.json")[0])
        track = build_custom_track(draft)

        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            content_root = project_root / "content"
            content_root.mkdir()
            (content_root / "tracks.json").write_text((root / "content" / "tracks.json").read_text(encoding="utf-8"), encoding="utf-8")
            save_custom_track(project_root, track)

            self.assertTrue(custom_tracks_path(project_root).exists())
            self.assertEqual(load_custom_tracks(project_root)[0].track_id, CUSTOM_TRACK_ID)
            self.assertEqual(load_available_tracks(content_root)[-1].track_id, CUSTOM_TRACK_ID)

    def test_save_multiple_custom_track_slots_round_trips(self) -> None:
        root = Path(__file__).parent.parent
        draft = draft_from_track(load_tracks(root / "content" / "tracks.json")[0])
        first = build_custom_track(draft, 0)
        second = build_custom_track(adjust_draft(draft, 0, 1), 1)

        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            content_root = project_root / "content"
            content_root.mkdir()
            (content_root / "tracks.json").write_text((root / "content" / "tracks.json").read_text(encoding="utf-8"), encoding="utf-8")

            save_custom_track(project_root, first)
            save_custom_track(project_root, second)

            loaded = load_custom_tracks(project_root)
            available = load_available_tracks(content_root)
            self.assertEqual([track.track_id for track in loaded], ["custom_audio_track", "custom_audio_track_2"])
            self.assertTrue(any(track.track_id == "custom_audio_track_2" for track in available))

    def test_record_track_editor_selection_selects_custom_track(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_track_editor_selection(root, CUSTOM_TRACK_ID)

            self.assertEqual(progress.last_track_id, CUSTOM_TRACK_ID)
            self.assertEqual(load_progress(root).last_track_id, CUSTOM_TRACK_ID)


if __name__ == "__main__":
    unittest.main()
