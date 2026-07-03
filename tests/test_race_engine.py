import unittest
from pathlib import Path

from horse_racing_game.content.loaders import load_horses, load_tracks, load_weather
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_engine import RaceEngine


class RaceEngineTests(unittest.TestCase):
    def test_engine_is_deterministic_for_same_seed(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        first = RaceEngine(track, horses, "ember_stride", seed=42)
        second = RaceEngine(track, horses, "ember_stride", seed=42)
        command = RaceCommand(throttle_delta=0.6, lateral_delta=-0.2, push_requested=True)

        first_result = first.tick(command, 1.0)
        second_result = second.tick(command, 1.0)

        self.assertEqual(first_result.state, second_result.state)
        self.assertEqual(first_result.events, second_result.events)

    def test_status_request_emits_rank_distance_and_stamina(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        engine = RaceEngine(track, horses, "ember_stride", seed=7)

        result = engine.tick(RaceCommand(request_status=True), 0.5)

        status_events = [event for event in result.events if event.event_type == "status_requested"]
        self.assertEqual(len(status_events), 1)
        self.assertIn("rank", status_events[0].data)
        self.assertIn("distance_remaining_m", status_events[0].data)
        self.assertIn("stamina", status_events[0].data)
        self.assertIn("weather", status_events[0].data)

    def test_stamina_decreases_under_sustained_pace(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        engine = RaceEngine(track, horses, "ember_stride", seed=11)

        initial = engine.tick(RaceCommand(), 0.1).state.player().stamina
        result = None
        for _ in range(20):
            result = engine.tick(RaceCommand(throttle_delta=1.0, push_requested=True), 0.5)

        self.assertIsNotNone(result)
        self.assertLess(result.state.player().stamina, initial)

    def test_pace_feedback_emits_each_driver_state(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        cases = (
            ("pace_cruising", RaceCommand(throttle_delta=0.0), 0.64, 10.0, 82.0, 9.8, 81.6),
            ("pace_overpushing", RaceCommand(throttle_delta=1.0, push_requested=True), 0.9, 15.5, 40.0, 14.8, 41.0),
            ("pace_recovering", RaceCommand(throttle_delta=-0.3), 0.5, 8.5, 55.0, 8.7, 54.4),
            ("pace_wasting_stamina", RaceCommand(throttle_delta=1.0, push_requested=True), 0.9, 11.0, 24.0, 10.6, 24.3),
        )

        for event_type, command, pace, speed, stamina, previous_speed, previous_stamina in cases:
            with self.subTest(event_type=event_type):
                engine = RaceEngine(track, horses, "ember_stride", seed=31)
                player = engine._player_runtime()
                player.pace = pace
                player.speed_mps = speed
                player.stamina = stamina

                events = engine._detect_pace_events(command, previous_speed, previous_stamina)

                self.assertEqual(events[0].event_type, event_type)
                self.assertEqual(events[0].subject_id, "ember_stride")

    def test_pace_feedback_is_emitted_once_per_state_change(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        engine = RaceEngine(track, horses, "ember_stride", seed=31)
        player = engine._player_runtime()
        player.pace = 0.66
        player.speed_mps = 10.0
        player.stamina = 80.0

        first = engine._detect_pace_events(RaceCommand(), 9.7, 79.5)
        second = engine._detect_pace_events(RaceCommand(), 9.8, 79.2)

        self.assertEqual(first[0].event_type, "pace_cruising")
        self.assertEqual(second, [])

    def test_rain_reduces_player_distance_and_stability(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        weather = {item.weather_id: item for item in load_weather(root / "content" / "weather.json")}
        clear = RaceEngine(track, horses, "ember_stride", seed=22, weather=weather["clear"])
        rain = RaceEngine(track, horses, "ember_stride", seed=22, weather=weather["rain"])
        command = RaceCommand(throttle_delta=1.0, push_requested=True)

        clear_result = None
        rain_result = None
        for _ in range(20):
            clear_result = clear.tick(command, 0.5)
            rain_result = rain.tick(command, 0.5)

        self.assertIsNotNone(clear_result)
        self.assertIsNotNone(rain_result)
        self.assertLess(rain_result.state.player().distance_m, clear_result.state.player().distance_m)
        self.assertLess(rain_result.state.player().stability, clear_result.state.player().stability)

    def test_turn_feedback_emits_entry_apex_and_exit(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        engine = RaceEngine(track, horses, "ember_stride", seed=31)
        curve_index = next(index for index, segment in enumerate(track.segments) if segment.curve_direction != "none")
        curve_segment = track.segments[curve_index]
        previous_segment = track.segments[curve_index - 1]
        player = engine._player_runtime()

        player.distance_m = curve_segment.start_m + 1.0
        player.lateral_position = 0.05 if curve_segment.curve_direction == "left" else max(track.lanes - 1, 0) * 1.15 - 0.05
        engine._last_player_segment = previous_segment

        entry_events = engine._detect_player_events(RaceCommand())
        self.assertIn("turn_entry", [event.event_type for event in entry_events])

        player.distance_m = (curve_segment.start_m + curve_segment.end_m) * 0.5 + 0.2
        engine._last_player_segment = curve_segment
        apex_events = engine._detect_player_events(RaceCommand())
        self.assertIn("turn_apex", [event.event_type for event in apex_events])

        next_segment = track.segments[curve_index + 1]
        player.distance_m = next_segment.start_m + 0.1
        engine._last_player_segment = curve_segment
        exit_events = engine._detect_player_events(RaceCommand())
        self.assertIn("turn_exit", [event.event_type for event in exit_events])

    def test_turn_line_feedback_distinguishes_inside_outside_and_tight_wide(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        engine = RaceEngine(track, horses, "ember_stride", seed=31)
        curve_segment = next(segment for segment in track.segments if segment.curve_direction != "none")
        player = engine._player_runtime()
        player.distance_m = curve_segment.start_m + 10.0
        engine._last_player_segment = curve_segment

        player.lateral_position = 0.05 if curve_segment.curve_direction == "left" else max(track.lanes - 1, 0) * 1.15 - 0.05
        tight_or_inside = engine._turn_line_feedback_event(player, curve_segment)
        self.assertIn(tight_or_inside.event_type, {"turn_too_tight", "turn_rail_inside"})

        player.lateral_position = max(track.lanes - 1, 0) * 1.15 - 0.05 if curve_segment.curve_direction == "left" else 0.05
        wide_or_outside = engine._turn_line_feedback_event(player, curve_segment)
        self.assertIn(wide_or_outside.event_type, {"turn_too_wide", "turn_rail_outside"})


    def test_opponent_events_include_identity_side_and_relative_speed(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        engine = RaceEngine(track, horses, "ember_stride", seed=9)
        player = engine._player_runtime()
        opponent = next(runner for runner in engine._runners if not runner.is_player)
        player.distance_m = 100.0
        player.lateral_position = 1.15
        player.speed_mps = 12.0
        opponent.distance_m = 105.0
        opponent.lateral_position = 0.65
        opponent.speed_mps = 11.0

        events = engine._opponent_proximity_events(player)
        blocking = next(event for event in events if event.event_type == "opponent_blocking_inside")

        self.assertEqual(blocking.subject_id, opponent.horse.horse_id)
        self.assertEqual(blocking.data["side"], "left")
        self.assertEqual(blocking.data["signature_sound"], opponent.horse.signature_sound)
        self.assertEqual(blocking.data["relative_speed_mps"], -1.0)

    def test_opponent_falling_behind_event_when_player_pulls_clear(self) -> None:
        root = Path(__file__).parent.parent
        horses = load_horses(root / "content" / "horses.json")
        track = load_tracks(root / "content" / "tracks.json")[0]
        engine = RaceEngine(track, horses, "ember_stride", seed=10)
        player = engine._player_runtime()
        opponent = next(runner for runner in engine._runners if not runner.is_player)
        player.distance_m = 120.0
        player.lateral_position = 1.15
        player.speed_mps = 13.0
        opponent.distance_m = 103.0
        opponent.lateral_position = 1.0
        opponent.speed_mps = 10.5

        events = engine._opponent_proximity_events(player)

        self.assertIn("opponent_falling_behind", [event.event_type for event in events])
if __name__ == "__main__":
    unittest.main()


