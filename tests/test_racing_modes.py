import unittest

from horse_racing_game.app.racing_modes import (
    RaceEventSpec,
    RacingMode,
    ScenarioObjective,
    ScenarioProgress,
    default_racing_modes,
    racing_mode_by_id,
    update_scenario_progress,
)


class RacingModesTests(unittest.TestCase):
    def test_default_modes_include_future_release_modes(self) -> None:
        mode_ids = [mode.mode_id for mode in default_racing_modes()]

        self.assertIn("time_trial", mode_ids)
        self.assertIn("ghost_race", mode_ids)
        self.assertIn("relay", mode_ids)
        self.assertIn("endurance", mode_ids)
        self.assertIn("scenario", mode_ids)

    def test_mode_player_count_constraints(self) -> None:
        head_to_head = racing_mode_by_id("head_to_head")

        self.assertFalse(head_to_head.supports_player_count(1))
        self.assertTrue(head_to_head.supports_player_count(2))
        self.assertFalse(head_to_head.supports_player_count(3))

    def test_event_spec_validates_required_mode_fields(self) -> None:
        RaceEventSpec("tt-1", "time_trial", "ashford_oval", time_limit_s=90.0).validate_for_mode(
            racing_mode_by_id("time_trial")
        )
        RaceEventSpec("ghost-1", "ghost_race", "ashford_oval", ghost_replay_id="replay-1").validate_for_mode(
            racing_mode_by_id("ghost_race")
        )
        RaceEventSpec("relay-1", "relay", "ashford_oval", team_size=2).validate_for_mode(racing_mode_by_id("relay"))

        with self.assertRaises(ValueError):
            RaceEventSpec("tt-2", "time_trial", "ashford_oval").validate_for_mode(racing_mode_by_id("time_trial"))
        with self.assertRaises(ValueError):
            RaceEventSpec("ghost-2", "ghost_race", "ashford_oval").validate_for_mode(racing_mode_by_id("ghost_race"))
        with self.assertRaises(ValueError):
            RaceEventSpec("relay-2", "relay", "ashford_oval", team_size=1).validate_for_mode(
                racing_mode_by_id("relay")
            )

    def test_scenario_progress_completes_observed_objectives(self) -> None:
        objectives = (
            ScenarioObjective("finish_under", "Finish under target time", 120.0),
            ScenarioObjective("clean_jumps", "Clear jumps", 3.0),
        )
        progress = ScenarioProgress("scenario-1")

        progress = update_scenario_progress(progress, objectives, {"finish_under": 121.0, "clean_jumps": 2.0})
        self.assertEqual(progress.completed_objective_ids, ("finish_under",))
        progress = update_scenario_progress(progress, objectives, {"clean_jumps": 3.0})
        self.assertEqual(progress.completed_objective_ids, ("clean_jumps", "finish_under"))

    def test_invalid_mode_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RacingMode("unknown", "Unknown")
        with self.assertRaises(ValueError):
            RacingMode("quick_race", "", max_players=1)
        with self.assertRaises(ValueError):
            RaceEventSpec("", "quick_race", "ashford_oval")
        with self.assertRaises(ValueError):
            RaceEventSpec("event", "quick_race", "ashford_oval", lap_count=0)
        with self.assertRaises(ValueError):
            ScenarioObjective("", "Objective", 1.0)
        with self.assertRaises(ValueError):
            update_scenario_progress(ScenarioProgress("scenario", ("missing",)), (), {})


if __name__ == "__main__":
    unittest.main()
