import unittest
from pathlib import Path

from horse_racing_game.simulation.race_state import RunnerState
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.ui.obstacles import (
    DEFAULT_PENALTY,
    ObstacleController,
    TrackObstacle,
    load_track_obstacles,
    penalty_for_kind,
    stage_for_threshold,
    timing_quality,
)


class ObstacleTests(unittest.TestCase):
    def test_track_obstacles_load_from_content(self) -> None:
        root = Path(__file__).parent.parent

        obstacles = load_track_obstacles(root / "content" / "obstacles.json", "ashford_oval")

        self.assertGreaterEqual(len(obstacles), 5)
        self.assertEqual(obstacles[0].obstacle_id, "ashford_cone_1")

    def test_audio_obstacle_lab_has_three_action_types(self) -> None:
        root = Path(__file__).parent.parent

        obstacles = load_track_obstacles(root / "content" / "obstacles.json", "audio_obstacle_lab")

        self.assertEqual([obstacle.required_action for obstacle in obstacles], ["dodge", "jump", "duck"])

    def test_warning_then_hit_applies_penalty(self) -> None:
        controller = ObstacleController(
            (
                TrackObstacle(
                    obstacle_id="cone_1",
                    distance_m=100.0,
                    lane=1,
                    kind="cone",
                    label="cone",
                ),
            )
        )

        warning_events = controller.update(_player(distance_m=70.0, lane=1), elapsed_s=1.0, delta_s=0.1)
        hit_events = controller.update(_player(distance_m=100.0, lane=1), elapsed_s=2.0, delta_s=0.1)

        self.assertEqual(warning_events[-1].event_type, "obstacle_warning")
        self.assertEqual(hit_events[-1].event_type, "obstacle_hit")
        self.assertTrue(controller.has_penalty)

    def test_obstacle_radar_emits_spatial_pulses_as_player_approaches(self) -> None:
        controller = ObstacleController(
            (
                TrackObstacle(
                    obstacle_id="cone_1",
                    distance_m=200.0,
                    lane=2,
                    kind="cone",
                    label="cone",
                ),
            )
        )

        gaps = (115.0, 78.0, 44.0, 24.0, 11.0)
        events = []
        for index, gap in enumerate(gaps):
            events.extend(controller.update(_player(distance_m=200.0 - gap, lane=1), elapsed_s=float(index), delta_s=0.1))

        radar_events = [event for event in events if event.event_type == "obstacle_radar"]

        self.assertEqual(len(radar_events), 5)
        self.assertEqual(radar_events[0].data["forward_m"], 115.0)
        self.assertEqual(radar_events[0].data["right_m"], 1.15)
        self.assertEqual(radar_events[-1].data["required_action"], "dodge")
        self.assertEqual(
            [event.data["warning_stage"] for event in radar_events],
            ["far", "medium", "close", "urgent", "imminent"],
        )

    def test_different_lane_avoids_obstacle(self) -> None:
        controller = ObstacleController(
            (
                TrackObstacle(
                    obstacle_id="puddle_1",
                    distance_m=100.0,
                    lane=2,
                    kind="puddle",
                    label="puddle",
                ),
            )
        )

        events = controller.update(_player(distance_m=100.0, lane=0), elapsed_s=1.0, delta_s=0.1)

        self.assertEqual(events[-1].event_type, "obstacle_avoided")
        self.assertEqual(events[-1].data["resolution"], "dodge")
        self.assertFalse(controller.has_penalty)

    def test_adjacent_lane_is_reported_as_near_miss(self) -> None:
        controller = ObstacleController(
            (
                TrackObstacle(
                    obstacle_id="puddle_1",
                    distance_m=100.0,
                    lane=2,
                    kind="puddle",
                    label="puddle",
                ),
            )
        )

        events = controller.update(_player(distance_m=100.0, lane=1), elapsed_s=1.0, delta_s=0.1)

        self.assertEqual(events[-1].event_type, "obstacle_near_miss")
        self.assertEqual(events[-1].data["resolution"], "near_miss")
        self.assertFalse(controller.has_penalty)

    def test_jump_clears_jump_obstacle_in_same_lane(self) -> None:
        controller = ObstacleController(
            (
                TrackObstacle(
                    obstacle_id="rail_1",
                    distance_m=100.0,
                    lane=1,
                    kind="rail",
                    label="rail",
                    required_action="jump",
                ),
            )
        )

        events = controller.update(
            _player(distance_m=100.0, lane=1),
            elapsed_s=1.0,
            delta_s=0.1,
            command=RaceCommand(jump_requested=True),
        )

        self.assertEqual(events[-1].event_type, "obstacle_avoided")
        self.assertEqual(events[-1].data["resolution"], "jump")
        self.assertEqual(events[-1].data["timing_quality"], "perfect")
        self.assertFalse(controller.has_penalty)

    def test_duck_clears_low_obstacle_in_same_lane(self) -> None:
        controller = ObstacleController(
            (
                TrackObstacle(
                    obstacle_id="branch_1",
                    distance_m=100.0,
                    lane=1,
                    kind="low_branch",
                    label="low branch",
                    required_action="duck",
                ),
            )
        )

        events = controller.update(
            _player(distance_m=100.0, lane=1),
            elapsed_s=1.0,
            delta_s=0.1,
            command=RaceCommand(duck_requested=True),
        )

        self.assertEqual(events[-1].event_type, "obstacle_avoided")
        self.assertEqual(events[-1].data["resolution"], "duck")
        self.assertFalse(controller.has_penalty)

    def test_wrong_action_still_hits_obstacle(self) -> None:
        controller = ObstacleController(
            (
                TrackObstacle(
                    obstacle_id="rail_1",
                    distance_m=100.0,
                    lane=1,
                    kind="rail",
                    label="rail",
                    required_action="jump",
                ),
            )
        )

        events = controller.update(
            _player(distance_m=100.0, lane=1),
            elapsed_s=1.0,
            delta_s=0.1,
            command=RaceCommand(duck_requested=True),
        )

        self.assertEqual(events[-1].event_type, "obstacle_hit")
        self.assertEqual(events[-1].data["resolution"], "hit")
        self.assertTrue(controller.has_penalty)


    def _hit(self, kind: str) -> ObstacleController:
        controller = ObstacleController(
            (TrackObstacle(obstacle_id=f"{kind}_1", distance_m=100.0, lane=1, kind=kind, label=kind),)
        )
        controller.update(_player(distance_m=100.0, lane=1), elapsed_s=1.0, delta_s=0.1)
        return controller

    def test_unknown_kind_uses_default_penalty(self) -> None:
        controller = self._hit("mystery_hazard")
        self.assertTrue(controller.has_penalty)
        self.assertEqual(controller.penalty_throttle_cap, DEFAULT_PENALTY.throttle_cap)

    def test_soft_ground_is_a_longer_milder_brake_than_a_barrier(self) -> None:
        mud = self._hit("mud")
        rail = self._hit("rail")
        # soft ground brakes less hard (higher throttle cap) ...
        self.assertGreater(mud.penalty_throttle_cap, rail.penalty_throttle_cap)
        # ... but for longer (drains slower), so it is still active after the barrier clears
        for _ in range(12):  # 12 * 0.1s = 1.2s
            mud.update(_player(distance_m=400.0, lane=1), elapsed_s=5.0, delta_s=0.1)
            rail.update(_player(distance_m=400.0, lane=1), elapsed_s=5.0, delta_s=0.1)
        self.assertFalse(rail.has_penalty)
        self.assertTrue(mud.has_penalty)

    def test_barrier_hit_brakes_harder_than_default(self) -> None:
        self.assertLess(penalty_for_kind("rail").throttle_cap, DEFAULT_PENALTY.throttle_cap)

    def test_penalty_cap_matches_kind_profile(self) -> None:
        self.assertEqual(self._hit("barrel").penalty_throttle_cap, penalty_for_kind("barrel").throttle_cap)

    def test_warning_stage_and_timing_quality_helpers(self) -> None:
        self.assertEqual(stage_for_threshold(120.0), "far")
        self.assertEqual(stage_for_threshold(12.0), "imminent")
        self.assertEqual(timing_quality(0.2), "perfect")
        self.assertEqual(timing_quality(1.5), "good")
        self.assertEqual(timing_quality(3.0), "late")


def _player(distance_m: float, lane: int) -> RunnerState:
    return RunnerState(
        runner_id="ember_stride",
        horse_name="Ember Stride",
        distance_m=distance_m,
        lateral_position=lane * 1.15,
        speed_mps=10.0,
        stamina=80.0,
        stability=1.0,
        is_player=True,
        rank=1,
    )


if __name__ == "__main__":
    unittest.main()
