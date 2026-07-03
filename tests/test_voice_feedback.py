import unittest

from horse_racing_game.audio.fake_backend import FakeAudioBackend
from horse_racing_game.audio.voice_feedback import HELP_TEXT, VoiceFeedbackController
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState, RunnerState


class VoiceFeedbackTests(unittest.TestCase):
    def test_repeat_without_message_speaks_fallback(self) -> None:
        backend = FakeAudioBackend()
        feedback = VoiceFeedbackController(backend)

        feedback.repeat_last()

        self.assertEqual(backend.calls[0].text, "No message to repeat.")

    def test_observed_status_can_be_repeated(self) -> None:
        backend = FakeAudioBackend()
        feedback = VoiceFeedbackController(backend)
        state = RaceState(
            elapsed_s=1.0,
            runners=(
                RunnerState(
                    runner_id="ember_stride",
                    horse_name="Ember Stride",
                    distance_m=10.0,
                    lateral_position=0.0,
                    speed_mps=8.0,
                    stamina=80.0,
                    stability=1.0,
                    is_player=True,
                    rank=2,
                ),
            ),
            is_finished=False,
        )

        feedback.observe_events(
            (
                RaceEvent(
                    event_type="status_requested",
                    priority=40,
                    timestamp_s=1.0,
                    subject_id="ember_stride",
                    data={"rank": 2, "distance_remaining_m": 1590.0, "stamina": 80.0},
                ),
            ),
            state,
        )
        feedback.repeat_last()

        self.assertIn("Rank 2", backend.calls[0].text or "")

    def test_obstacle_message_can_be_repeated(self) -> None:
        backend = FakeAudioBackend()
        feedback = VoiceFeedbackController(backend)
        state = RaceState(
            elapsed_s=1.0,
            runners=(
                RunnerState(
                    runner_id="ember_stride",
                    horse_name="Ember Stride",
                    distance_m=100.0,
                    lateral_position=0.0,
                    speed_mps=8.0,
                    stamina=80.0,
                    stability=1.0,
                    is_player=True,
                    rank=1,
                ),
            ),
            is_finished=False,
        )

        feedback.observe_events(
            (
                RaceEvent(
                    event_type="obstacle_hit",
                    priority=90,
                    timestamp_s=1.0,
                    subject_id="cone_1",
                    data={"label": "cone"},
                ),
            ),
            state,
        )
        feedback.repeat_last()

        self.assertEqual(backend.calls[0].text, "Hit cone.")
    def test_help_speaks_control_summary(self) -> None:
        backend = FakeAudioBackend()
        feedback = VoiceFeedbackController(backend)

        feedback.speak_help()

        self.assertEqual(backend.calls[0].text, HELP_TEXT)

    def test_common_race_events_are_spoken_and_repeatable(self) -> None:
        backend = FakeAudioBackend()
        feedback = VoiceFeedbackController(backend)
        state = RaceState(
            elapsed_s=8.0,
            runners=(RunnerState("ember_stride", "Ember Stride", 200.0, 0.0, 9.0, 50.0, 1.0, True, 1),),
            is_finished=False,
        )
        cases = (
            (RaceEvent("race_started", 100, 0.0, None, {}), "Start."),
            (RaceEvent("turn_entry", 70, 2.0, None, {"direction": "right"}), "Turn entry right."),
            (RaceEvent("turn_exit", 55, 2.5, None, {"direction": "right"}), "Turn exit right."),
            (RaceEvent("turn_apex", 58, 2.8, None, {"direction": "right"}), "Apex right."),
            (RaceEvent("turn_rail_inside", 52, 2.9, None, {"direction": "right"}), "Inside rail right."),
            (RaceEvent("turn_rail_outside", 52, 3.0, None, {"direction": "right"}), "Outside rail right."),
            (RaceEvent("turn_too_tight", 70, 3.1, None, {"direction": "right"}), "Too tight right."),
            (RaceEvent("turn_too_wide", 70, 3.2, None, {"direction": "right"}), "Too wide right."),
            (RaceEvent("low_stamina", 70, 3.0, "ember_stride", {}), "Low stamina."),
            (RaceEvent("critical_stamina", 80, 4.0, "ember_stride", {}), "Critical stamina."),
            (RaceEvent("pace_cruising", 45, 4.5, "ember_stride", {}), "Cruising."),
            (RaceEvent("pace_overpushing", 45, 5.0, "ember_stride", {}), "Overpushing."),
            (RaceEvent("pace_recovering", 45, 5.5, "ember_stride", {}), "Recovering."),
            (RaceEvent("pace_wasting_stamina", 45, 6.0, "ember_stride", {}), "Wasting stamina."),
            (RaceEvent("obstacle_warning", 70, 5.0, None, {"label": "low branch", "required_action": "duck"}), "Obstacle low branch. duck."),
            (RaceEvent("obstacle_near_miss", 76, 5.5, None, {"label": "low branch"}), "Near miss low branch."),
            (RaceEvent("obstacle_avoided", 70, 6.0, None, {"label": "low branch", "resolution": "jump", "timing_quality": "perfect"}), "Perfect jump confirmed."),
            (RaceEvent("final_stretch", 90, 7.0, None, {}), "Final stretch."),
            (RaceEvent("finish_line_crossed", 100, 8.0, "ember_stride", {"rank": 1}), "Finished rank 1."),
            (RaceEvent("race_finished", 100, 9.0, None, {}), "Race finished. Rank 1."),
        )

        for event, expected in cases:
            with self.subTest(event=event.event_type):
                backend.calls.clear()
                feedback.observe_events((event,), state)
                feedback.repeat_last()
                self.assertEqual(backend.calls[0].text, expected)

    def test_unknown_event_does_not_replace_last_message(self) -> None:
        backend = FakeAudioBackend()
        feedback = VoiceFeedbackController(backend)
        state = RaceState(
            elapsed_s=1.0,
            runners=(RunnerState("ember_stride", "Ember Stride", 0.0, 0.0, 0.0, 100.0, 1.0, True, 1),),
            is_finished=False,
        )

        feedback.observe_events((RaceEvent("race_started", 100, 0.0, None, {}),), state)
        feedback.observe_events((RaceEvent("unknown", 1, 1.0, None, {}),), state)
        feedback.repeat_last()

        self.assertEqual(backend.calls[0].text, "Start.")


if __name__ == "__main__":
    unittest.main()
