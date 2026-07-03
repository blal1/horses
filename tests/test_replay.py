import unittest
from pathlib import Path

from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.replay import build_replay, build_replay_lines, build_replay_timeline, replay_line_for_event
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState, RunnerState


class ReplayTests(unittest.TestCase):
    def test_build_replay_lines_includes_finish_summary_and_key_events(self) -> None:
        state = RaceState(
            elapsed_s=73.5,
            is_finished=True,
            runners=(
                RunnerState("ember_stride", "Ember Stride", 1200.0, 0.0, 0.0, 31.0, 1.0, True, 2),
                RunnerState("copper_gate", "Copper Gate", 1201.0, 0.0, 0.0, 30.0, 1.0, False, 1),
            ),
        )
        events = (
            RaceEvent("race_started", 100, 0.0, None, {}),
            RaceEvent("final_stretch", 70, 55.0, None, {}),
            RaceEvent("finish_line_crossed", 100, 73.5, "ember_stride", {"rank": 2}),
        )

        lines = build_replay_lines(state, events)

        self.assertEqual(lines[0], "Replay. Finished rank 2 after 73.5 seconds.")
        self.assertIn("The field entered the final stretch.", lines)
        self.assertIn("Finish line crossed in rank 2.", lines)

    def test_replay_line_for_event_handles_opponents_and_obstacles(self) -> None:
        self.assertEqual(
            replay_line_for_event(RaceEvent("opponent_passing", 60, 4.0, "copper_gate", {"horse_name": "Copper Gate"})),
            "Copper Gate opponent passing.",
        )
        self.assertEqual(
            replay_line_for_event(RaceEvent("obstacle_hit", 90, 5.0, None, {"label": "rail marker"})),
            "Obstacle hit: rail marker.",
        )

    def test_replay_line_for_event_covers_race_branches(self) -> None:
        cases = (
            (RaceEvent("race_started", 100, 0.0, None, {}), "The gates opened."),
            (RaceEvent("turn_entry", 60, 2.0, None, {"direction": "left"}), "Turn entry: left."),
            (RaceEvent("turn_exit", 55, 3.0, None, {"direction": "left"}), "Turn exit: left."),
            (RaceEvent("turn_apex", 58, 4.0, None, {"direction": "left"}), "Turn apex: left."),
            (RaceEvent("turn_rail_inside", 52, 4.5, None, {"direction": "left"}), "Inside rail: left."),
            (RaceEvent("turn_rail_outside", 52, 5.0, None, {"direction": "left"}), "Outside rail: left."),
            (RaceEvent("turn_too_tight", 70, 5.5, None, {"direction": "left"}), "Too tight: left."),
            (RaceEvent("turn_too_wide", 70, 6.0, None, {"direction": "left"}), "Too wide: left."),
            (RaceEvent("race_finished", 100, 75.0, None, {}), "Race complete."),
            (RaceEvent("critical_stamina", 70, 50.0, "ember_stride", {}), "Critical stamina."),
            (RaceEvent("obstacle_warning", 70, 12.0, None, {"label": "low branch"}), "Obstacle warning: low branch."),
            (RaceEvent("obstacle_near_miss", 76, 13.0, None, {"label": "low branch"}), "Near miss: low branch."),
            (RaceEvent("obstacle_avoided", 70, 14.0, None, {"label": "low branch", "resolution": "duck", "timing_quality": "good"}), "Good duck confirmed: low branch."),
        )

        for event, expected in cases:
            with self.subTest(event=event.event_type):
                self.assertEqual(replay_line_for_event(event), expected)

    def test_build_replay_lines_deduplicates_and_caps_output(self) -> None:
        state = RaceState(
            elapsed_s=88.0,
            is_finished=True,
            runners=(RunnerState("ember_stride", "Ember Stride", 1400.0, 0.0, 0.0, 21.0, 1.0, True, 1),),
        )
        events = tuple(RaceEvent("final_stretch", 70, float(index), None, {}) for index in range(20))

        lines = build_replay_lines(state, events)

        self.assertLessEqual(len(lines), 12)
        self.assertEqual(lines.count("The field entered the final stretch."), 1)

    def test_build_replay_timeline_reconstructs_audio_events_and_key_moments(self) -> None:
        root = Path(__file__).parent.parent
        commands = tuple(RaceCommand(throttle_delta=0.8, push_requested=index > 200) for index in range(500))
        replay = build_replay(AppConfig(content_root=root / "content", tick_hz=4), commands)

        timeline = build_replay_timeline(replay, root / "content")

        self.assertTrue(timeline.has_events)
        self.assertIn("race_started", [event.event_type for event in timeline.events])
        self.assertTrue(timeline.key_indices)
        self.assertIsNotNone(timeline.key_index_at_or_before(len(timeline.events)))


if __name__ == "__main__":
    unittest.main()
