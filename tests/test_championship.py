import unittest
import tempfile
from pathlib import Path

from horse_racing_game.app.championship import (
    championship_calendar_with_custom_tracks,
    championship_rival_stables,
    championship_title,
    compute_standings,
    load_championship_calendar,
    load_playable_championship_calendar,
    next_championship_race,
    rival_points_after_race,
    standings_text,
)
from horse_racing_game.app.track_editor import build_custom_track, draft_from_track, save_custom_track
from horse_racing_game.content.loaders import load_stables
from horse_racing_game.content.loaders import load_tracks
from horse_racing_game.domain.rival import RivalProfile


class ChampionshipTests(unittest.TestCase):
    def test_rival_points_after_race_uses_career_scoring(self) -> None:
        self.assertEqual(rival_points_after_race(3, 1), 13)
        self.assertEqual(rival_points_after_race(3, 5), 4)
        self.assertEqual(rival_points_after_race(3, 99), 3)

    def test_compute_standings_sorts_by_points_then_name(self) -> None:
        root = Path(__file__).parent.parent
        stables = load_stables(root / "content" / "stables.json")
        rivals = (
            RivalProfile("copper_gate", "Copper Gate", "", "", ""),
            RivalProfile("silver_bell", "Silver Bell", "", "", ""),
        )

        standings = compute_standings(
            "You",
            7,
            1,
            rivals,
            {"copper_gate": 10, "silver_bell": 7},
            {"copper_gate": 1, "silver_bell": 1},
            {"copper_gate": "stormforge", "silver_bell": "heatherbank"},
            stables,
        )

        self.assertEqual([row.name for row in standings], ["Copper Gate", "Silver Bell", "You"])
        self.assertEqual(standings[0].races_run, 1)
        self.assertEqual(standings[0].stable_name, "Stormforge Yard")

    def test_standings_text_is_speakable(self) -> None:
        rivals = (RivalProfile("copper_gate", "Copper Gate", "", "", ""),)
        text = standings_text(compute_standings("You", 10, 1, rivals, {"copper_gate": 7}, {"copper_gate": 1}))

        self.assertIn("1. You, 10 points, Player stable.", text)
        self.assertIn("2. Copper Gate, 7 points, Independent.", text)

    def test_load_championship_calendar_and_next_race(self) -> None:
        root = Path(__file__).parent.parent
        calendar = load_championship_calendar(root / "content" / "championship.json")

        self.assertEqual(next_championship_race(calendar, 0).track_id, "ashford_oval")
        self.assertEqual(next_championship_race(calendar, 1).weather_id, "windy")
        self.assertEqual(next_championship_race(calendar, 2).track_id, "meadowbrook_mile")
        self.assertEqual(next_championship_race(calendar, 3).track_id, "highcliff_rise")
        self.assertEqual(next_championship_race(calendar, 5).weather_id, "fog")
        self.assertIsNone(next_championship_race(calendar, 9))
        self.assertIn("Rookie Cup Opening", championship_title(calendar, 0, 0))
        self.assertIn("Championship complete", championship_title(calendar, 9, 22))

    def test_championship_rival_stables_merges_calendar_assignments(self) -> None:
        root = Path(__file__).parent.parent
        calendar = load_championship_calendar(root / "content" / "championship.json")

        assignments = championship_rival_stables(calendar)

        self.assertEqual(assignments["golden_switch"], "stormforge")
        self.assertEqual(assignments["river_chime"], "heatherbank")

    def test_custom_tracks_append_playable_career_rounds(self) -> None:
        root = Path(__file__).parent.parent
        base_calendar = load_championship_calendar(root / "content" / "championship.json")
        custom_track = build_custom_track(draft_from_track(load_tracks(root / "content" / "tracks.json")[0]), 1)

        calendar = championship_calendar_with_custom_tracks(base_calendar, (custom_track,))

        self.assertEqual(len(calendar), len(base_calendar) + 1)
        self.assertEqual(calendar[-1].race_id, "custom_career_custom_audio_track_2")
        self.assertEqual(calendar[-1].track_id, "custom_audio_track_2")
        self.assertEqual(calendar[-1].weather_id, "clear")
        self.assertIn("Local custom track exhibition", calendar[-1].briefing)

    def test_playable_calendar_loads_saved_custom_tracks(self) -> None:
        source_root = Path(__file__).parent.parent
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            content_root = project_root / "content"
            content_root.mkdir()
            (content_root / "championship.json").write_text(
                (source_root / "content" / "championship.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (content_root / "tracks.json").write_text(
                (source_root / "content" / "tracks.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            custom_track = build_custom_track(draft_from_track(load_tracks(source_root / "content" / "tracks.json")[0]), 2)
            save_custom_track(project_root, custom_track)

            calendar = load_playable_championship_calendar(content_root, project_root)

            self.assertEqual(calendar[-1].track_id, "custom_audio_track_3")

    def test_next_championship_race_clamps_negative_progress(self) -> None:
        root = Path(__file__).parent.parent
        calendar = load_championship_calendar(root / "content" / "championship.json")

        self.assertEqual(next_championship_race(calendar, -2), calendar[0])

    def test_invalid_championship_calendar_reports_schema_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            not_array = root / "not_array.json"
            not_array.write_text("{}", encoding="utf-8")
            not_object = root / "not_object.json"
            not_object.write_text("[1]", encoding="utf-8")
            missing_stables = root / "missing_stables.json"
            missing_stables.write_text('[{"race_id":"r","name":"n","track_id":"t","weather_id":"w","briefing":"b"}]', encoding="utf-8")
            bad_mapping = root / "bad_mapping.json"
            bad_mapping.write_text(
                '[{"race_id":"r","name":"n","track_id":"t","weather_id":"w","briefing":"b","rival_stables":{"rival":1}}]',
                encoding="utf-8",
            )
            missing_string = root / "missing_string.json"
            missing_string.write_text(
                '[{"race_id":1,"name":"n","track_id":"t","weather_id":"w","briefing":"b","rival_stables":{}}]',
                encoding="utf-8",
            )

            for path in (not_array, not_object, missing_stables, bad_mapping, missing_string):
                with self.subTest(path=path.name):
                    with self.assertRaises(ValueError):
                        load_championship_calendar(path)


if __name__ == "__main__":
    unittest.main()
