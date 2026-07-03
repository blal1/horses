import unittest
from pathlib import Path

from horse_racing_game.app.bootstrap import build_quick_race_services
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.game_app import GameApp
from horse_racing_game.app.replay import (
    RaceReplay,
    build_replay,
    deserialize_command,
    reconstruct_race,
    replay_from_dict,
    replay_to_dict,
    serialize_command,
)
from horse_racing_game.input.commands import RaceCommand


CONTENT_ROOT = Path(__file__).parent.parent / "content"


def _config() -> AppConfig:
    return AppConfig(content_root=CONTENT_ROOT, track_id="ashford_oval", player_horse_id="ember_stride", seed=99)


class CommandSerializationTests(unittest.TestCase):
    def test_command_round_trips(self) -> None:
        command = RaceCommand(
            throttle_delta=0.45,
            lateral_delta=-0.2,
            push_requested=True,
            jump_requested=False,
            duck_requested=True,
            request_status=True,
        )
        self.assertEqual(deserialize_command(serialize_command(command)), command)

    def test_replay_dict_round_trips(self) -> None:
        replay = RaceReplay(
            seed=7,
            track_id="bracken_dirt",
            player_horse_id="night_rail",
            weather_id="windy",
            stable_id="stormforge",
            tick_seconds=0.25,
            commands=(RaceCommand(throttle_delta=1.0), RaceCommand(push_requested=True)),
            rival_stable_ids={"copper_gate": "oak_lane"},
            horse_training_level=2,
        )
        restored = replay_from_dict(replay_to_dict(replay))
        self.assertEqual(restored, replay)

    def test_replay_from_dict_rejects_garbage(self) -> None:
        self.assertIsNone(replay_from_dict(None))
        self.assertIsNone(replay_from_dict({"seed": 1}))  # missing fields
        self.assertIsNone(replay_from_dict({"commands": "not a list"}))


class ReconstructionTests(unittest.TestCase):
    def _run(self) -> tuple[AppConfig, object]:
        config = _config()
        services = build_quick_race_services(config)
        result = GameApp(config, services).run_quick_race()
        return config, result

    def test_reconstruction_reproduces_the_exact_race(self) -> None:
        config, result = self._run()
        replay = build_replay(config, result.commands)

        reconstructed = reconstruct_race(replay, CONTENT_ROOT)

        # Identical final state: positions, ranks, stamina, finish — bit for bit.
        self.assertEqual(reconstructed.state, result.state)
        self.assertEqual(reconstructed.state.player().rank, result.state.player().rank)

    def test_reconstruction_is_stable_across_runs(self) -> None:
        config, result = self._run()
        replay = build_replay(config, result.commands)
        first = reconstruct_race(replay, CONTENT_ROOT)
        second = reconstruct_race(replay, CONTENT_ROOT)
        self.assertEqual(first.state, second.state)

    def test_reconstruction_survives_a_persistence_round_trip(self) -> None:
        config, result = self._run()
        stored = replay_to_dict(build_replay(config, result.commands))
        replay = replay_from_dict(stored)
        self.assertIsNotNone(replay)
        reconstructed = reconstruct_race(replay, CONTENT_ROOT)
        self.assertEqual(reconstructed.state, result.state)


if __name__ == "__main__":
    unittest.main()
