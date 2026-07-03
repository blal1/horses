import unittest
import socket
import threading
from pathlib import Path

from horse_racing_game.app.bootstrap import build_quick_race_services
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.game_app import GameApp
from horse_racing_game.app.multiplayer import (
    LockstepCommandBuffer,
    LockstepFrame,
    PeerCommand,
    frame_from_dict,
    frame_to_dict,
    local_commands,
)
from horse_racing_game.app.network import InMemoryLockstepTransport, LockstepPacket, LockstepSession, SocketLockstepTransport
from horse_racing_game.app.replay import build_replay, reconstruct_race
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.ui.pygame_multiplayer import PygameMultiplayerRaceGame


CONTENT_ROOT = Path(__file__).parent.parent / "content"


class LockstepFrameTests(unittest.TestCase):
    def test_frame_sorts_peer_commands_for_deterministic_storage(self) -> None:
        frame = LockstepFrame(
            tick_index=3,
            commands=(
                PeerCommand("guest", RaceCommand(lateral_delta=1.0)),
                PeerCommand("host", RaceCommand(throttle_delta=1.0)),
            ),
        )

        self.assertEqual([item.peer_id for item in frame.commands], ["guest", "host"])
        self.assertEqual(frame.command_for("host"), RaceCommand(throttle_delta=1.0))

    def test_frame_rejects_duplicate_peer_commands(self) -> None:
        with self.assertRaises(ValueError):
            LockstepFrame(
                tick_index=0,
                commands=(
                    PeerCommand("host", RaceCommand()),
                    PeerCommand("host", RaceCommand(throttle_delta=1.0)),
                ),
            )

    def test_frame_round_trips_through_dict(self) -> None:
        frame = LockstepFrame(
            tick_index=7,
            commands=(
                PeerCommand("guest", RaceCommand(duck_requested=True)),
                PeerCommand("host", RaceCommand(push_requested=True, request_status=True)),
            ),
        )

        self.assertEqual(frame_from_dict(frame_to_dict(frame)), frame)


class LockstepCommandBufferTests(unittest.TestCase):
    def test_buffer_waits_until_every_peer_has_submitted_for_tick(self) -> None:
        buffer = LockstepCommandBuffer(("host", "guest"))

        buffer.submit(4, "guest", RaceCommand(lateral_delta=-1.0))
        self.assertIsNone(buffer.ready_frame(4))
        buffer.submit(4, "host", RaceCommand(throttle_delta=0.6))

        frame = buffer.pop_ready_frame(4)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertEqual(frame.command_for("host"), RaceCommand(throttle_delta=0.6))
        self.assertIsNone(buffer.ready_frame(4))

    def test_buffer_rejects_unknown_peer(self) -> None:
        buffer = LockstepCommandBuffer(("host", "guest"))

        with self.assertRaises(ValueError):
            buffer.submit(0, "spectator", RaceCommand())


class LockstepGameAppIntegrationTests(unittest.TestCase):
    def test_local_lockstep_stream_feeds_quick_race_and_reconstructs(self) -> None:
        frames = tuple(
            LockstepFrame(
                tick_index=index,
                commands=(
                    PeerCommand("guest", RaceCommand(lateral_delta=-0.2 if index % 2 else 0.2)),
                    PeerCommand("host", RaceCommand(throttle_delta=1.0, push_requested=index >= 8)),
                ),
            )
            for index in range(64)
        )
        config = AppConfig(
            content_root=CONTENT_ROOT,
            track_id="ashford_oval",
            player_horse_id="ember_stride",
            seed=515,
            max_race_seconds=12.0,
        )
        services = build_quick_race_services(config)

        result = GameApp(config, services).run_quick_race(local_commands(frames, "host"))
        replay = build_replay(config, result.commands)
        reconstructed = reconstruct_race(replay, CONTENT_ROOT)

        self.assertEqual(reconstructed.state, result.state)
        self.assertEqual(result.commands, local_commands(frames, "host")[: result.ticks])

    def test_multiplayer_screen_can_submit_through_remote_session(self) -> None:
        config = AppConfig(content_root=CONTENT_ROOT, tick_hz=60, max_race_seconds=1.0)
        session = LockstepSession(("guest", "host"), "host", InMemoryLockstepTransport())
        game = PygameMultiplayerRaceGame(config, build_quick_race_services(config), remote_session=session)

        game._submit_lockstep_commands(
            session,
            0,
            RaceCommand(throttle_delta=0.5),
            RaceCommand(lateral_delta=-0.5),
        )
        self.assertIsNone(session.ready_frame(0))

        session.accept_packet(LockstepPacket(0, "guest", RaceCommand(lateral_delta=-0.5)))
        frame = session.ready_frame(0)

        self.assertIsNotNone(frame)
        self.assertEqual(frame.command_for("host"), RaceCommand(throttle_delta=0.5))
        self.assertEqual(frame.command_for("guest"), RaceCommand(lateral_delta=-0.5))

    def test_multiplayer_screen_reconciles_remote_result_summary(self) -> None:
        first_socket, second_socket = socket.socketpair()
        try:
            host_session = LockstepSession(("guest", "host"), "host", SocketLockstepTransport(first_socket))
            guest_session = LockstepSession(("guest", "host"), "guest", SocketLockstepTransport(second_socket))
            config = AppConfig(content_root=CONTENT_ROOT, seed=77, track_id="ashford_oval", max_race_seconds=1.0)
            host_game = PygameMultiplayerRaceGame(config, build_quick_race_services(config), remote_session=host_session)
            guest_game = PygameMultiplayerRaceGame(config, build_quick_race_services(config), remote_session=guest_session)
            state = build_quick_race_services(config).race_engine.tick(RaceCommand(request_status=True), config.tick_seconds).state

            def host_side() -> None:
                host_game._reconcile_remote_result(state, 12)

            def guest_side() -> None:
                guest_game._reconcile_remote_result(state, 12)

            threads = (threading.Thread(target=host_side), threading.Thread(target=guest_side))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertTrue(any("Result synced" in message for message in host_game._messages))
            self.assertTrue(any("Result synced" in message for message in guest_game._messages))
        finally:
            first_socket.close()
            second_socket.close()


if __name__ == "__main__":
    unittest.main()
