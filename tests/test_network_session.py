import unittest
import socket
import threading

from horse_racing_game.app.multiplayer import LockstepFrame, PeerCommand
from horse_racing_game.app.network import (
    AuthoritativeRaceDecision,
    InMemoryLockstepTransport,
    LobbyHandshake,
    LobbyStartSignal,
    LockstepPacket,
    LockstepSession,
    LoopbackLockstepHub,
    MatchmakingQueue,
    MatchmakingTicket,
    MultiplayerLobby,
    OnlineInvite,
    PartyLobby,
    RaceResultReconciliation,
    RaceResultSummary,
    SocketLockstepTransport,
    authoritative_race_decision,
    receive_lobby_handshake,
    receive_lobby_start_signal,
    receive_race_result_summary,
    send_lobby_handshake,
    send_lobby_start_signal,
    send_race_result_summary,
    packet_from_dict,
    packet_from_signed_envelope,
    packet_to_dict,
    signed_packet_envelope,
)
from horse_racing_game.app.network_security import ProtocolEnvelope
from horse_racing_game.input.commands import RaceCommand


class LockstepPacketTests(unittest.TestCase):
    def test_packet_round_trips_through_dict(self) -> None:
        packet = LockstepPacket(4, "host", RaceCommand(throttle_delta=0.75, request_status=True))

        self.assertEqual(packet_from_dict(packet_to_dict(packet)), packet)

    def test_packet_round_trips_through_signed_envelope(self) -> None:
        packet = LockstepPacket(4, "host", RaceCommand(throttle_delta=0.75, request_status=True))
        envelope = signed_packet_envelope(
            packet,
            session_id="race-1",
            sequence=12,
            shared_key=b"session-key",
            sent_at_unix_s=100.0,
        )

        self.assertEqual(packet_from_signed_envelope(envelope, b"session-key"), packet)
        with self.assertRaises(ValueError):
            packet_from_signed_envelope(envelope, b"wrong-key")

    def test_signed_packet_rejects_peer_mismatch(self) -> None:
        packet = LockstepPacket(4, "host", RaceCommand(throttle_delta=0.75))
        envelope = signed_packet_envelope(
            packet,
            session_id="race-1",
            sequence=12,
            shared_key=b"session-key",
            sent_at_unix_s=100.0,
        )
        mismatch = ProtocolEnvelope(
            envelope.session_id,
            "guest",
            envelope.sequence,
            envelope.kind,
            envelope.payload,
            envelope.sent_at_unix_s,
            envelope.signature,
        )

        with self.assertRaises(ValueError):
            packet_from_signed_envelope(mismatch, b"session-key")


class LockstepSessionTests(unittest.TestCase):
    def test_session_buffers_local_and_remote_commands_for_a_frame(self) -> None:
        transport = InMemoryLockstepTransport()
        session = LockstepSession(("guest", "host"), "host", transport=transport)

        local_packet = session.submit_local_command(2, RaceCommand(throttle_delta=1.0))
        self.assertEqual(local_packet.peer_id, "host")
        self.assertEqual(transport.drain_outbound(), (local_packet,))
        self.assertIsNone(session.ready_frame(2))

        transport.deliver(LockstepPacket(2, "guest", RaceCommand(lateral_delta=-1.0)))
        self.assertEqual(
            session.pump_inbound(),
            (LockstepPacket(2, "guest", RaceCommand(lateral_delta=-1.0)),),
        )

        frame = session.pop_ready_frame(2)
        self.assertEqual(
            frame,
            LockstepFrame(
                tick_index=2,
                commands=(
                    PeerCommand("guest", RaceCommand(lateral_delta=-1.0)),
                    PeerCommand("host", RaceCommand(throttle_delta=1.0)),
                ),
            ),
        )

    def test_session_rejects_unknown_remote_peer(self) -> None:
        session = LockstepSession(("host", "guest"), "host")

        with self.assertRaises(ValueError):
            session.accept_packet(LockstepPacket(0, "spectator", RaceCommand()))

    def test_session_drain_inbound_returns_empty_when_no_packets_arrived(self) -> None:
        session = LockstepSession(("host", "guest"), "host")

        self.assertEqual(session.pump_inbound(), ())

    def test_socket_transports_exchange_real_packets(self) -> None:
        first_socket, second_socket = socket.socketpair()
        try:
            host_transport = SocketLockstepTransport(first_socket)
            guest_transport = SocketLockstepTransport(second_socket)
            host = LockstepSession(("guest", "host"), "host", host_transport)
            guest = LockstepSession(("guest", "host"), "guest", guest_transport)

            host.submit_local_command(1, RaceCommand(throttle_delta=0.8))
            guest.pump_inbound()
            self.assertIsNone(guest.ready_frame(1))

            guest.submit_local_command(1, RaceCommand(lateral_delta=-0.4))
            host.pump_inbound()

            self.assertEqual(host.ready_frame(1), guest.ready_frame(1))
            self.assertEqual(host.ready_frame(1).command_for("host"), RaceCommand(throttle_delta=0.8))
            self.assertEqual(host.ready_frame(1).command_for("guest"), RaceCommand(lateral_delta=-0.4))
        finally:
            first_socket.close()
            second_socket.close()

    def test_lobby_handshake_round_trips_room_code_and_peer_identity(self) -> None:
        first_socket, second_socket = socket.socketpair()
        try:
            host_handshake = LobbyHandshake("ROOM42", "host", "Host", True)
            guest_handshake = LobbyHandshake("ROOM42", "guest", "Guest", True)
            results: dict[str, LobbyHandshake] = {}

            def host_side() -> None:
                results["host_seen"] = receive_lobby_handshake(first_socket, 1.0)
                send_lobby_handshake(first_socket, host_handshake)

            def guest_side() -> None:
                send_lobby_handshake(second_socket, guest_handshake)
                results["guest_seen"] = receive_lobby_handshake(second_socket, 1.0)

            threads = (threading.Thread(target=host_side), threading.Thread(target=guest_side))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(results["host_seen"], guest_handshake)
            self.assertEqual(results["guest_seen"], host_handshake)
        finally:
            first_socket.close()
            second_socket.close()

    def test_lobby_start_signal_round_trips_countdown_and_start_time(self) -> None:
        first_socket, second_socket = socket.socketpair()
        try:
            host_signal = LobbyStartSignal(3.0, 12345.5)
            guest_signal = LobbyStartSignal(3.0, 12345.5)
            results: dict[str, LobbyStartSignal] = {}

            def host_side() -> None:
                results["host_seen"] = receive_lobby_start_signal(first_socket, 1.0)
                send_lobby_start_signal(first_socket, host_signal)

            def guest_side() -> None:
                send_lobby_start_signal(second_socket, guest_signal)
                results["guest_seen"] = receive_lobby_start_signal(second_socket, 1.0)

            threads = (threading.Thread(target=host_side), threading.Thread(target=guest_side))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(results["host_seen"], guest_signal)
            self.assertEqual(results["guest_seen"], host_signal)
        finally:
            first_socket.close()
            second_socket.close()

    def test_race_result_summary_round_trips(self) -> None:
        first_socket, second_socket = socket.socketpair()
        try:
            host_summary = RaceResultSummary("seed:track", "host", True, 1, 240, 812.5)
            guest_summary = RaceResultSummary("seed:track", "guest", True, 2, 240, 809.0)
            results: dict[str, RaceResultSummary] = {}

            def host_side() -> None:
                send_race_result_summary(first_socket, host_summary)
                results["host_seen"] = receive_race_result_summary(first_socket, 1.0)

            def guest_side() -> None:
                results["guest_seen"] = receive_race_result_summary(second_socket, 1.0)
                send_race_result_summary(second_socket, guest_summary)

            threads = (threading.Thread(target=host_side), threading.Thread(target=guest_side))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(results["host_seen"], guest_summary)
            self.assertEqual(results["guest_seen"], host_summary)
        finally:
            first_socket.close()
            second_socket.close()


class LoopbackLockstepHubTests(unittest.TestCase):
    def test_hub_relays_packets_between_peers_and_emits_one_frame(self) -> None:
        hub = LoopbackLockstepHub(("host", "guest"))

        host_packet = hub.submit("host", 6, RaceCommand(throttle_delta=1.0))
        self.assertEqual(host_packet.peer_id, "host")
        self.assertIsNone(hub.ready_frame(6))

        guest_packet = hub.submit("guest", 6, RaceCommand(lateral_delta=0.5))
        self.assertEqual(guest_packet.peer_id, "guest")

        frame = hub.pop_ready_frame(6)
        self.assertEqual(
            frame,
            LockstepFrame(
                tick_index=6,
                commands=(
                    PeerCommand("guest", RaceCommand(lateral_delta=0.5)),
                    PeerCommand("host", RaceCommand(throttle_delta=1.0)),
                ),
            ),
        )


class MultiplayerLobbyTests(unittest.TestCase):
    def test_lobby_tracks_joined_peers_and_ready_state(self) -> None:
        lobby = MultiplayerLobby("room-42")

        lobby.join("host", "Host")
        state = lobby.join("guest", "Guest")
        self.assertFalse(state.can_start)

        lobby.set_ready("host", True)
        state = lobby.set_ready("guest", True)

        self.assertTrue(state.can_start)
        self.assertEqual([peer.peer_id for peer in state.peers], ["guest", "host"])

    def test_lobby_rejects_ready_for_unknown_peer(self) -> None:
        lobby = MultiplayerLobby("room-42")

        with self.assertRaises(ValueError):
            lobby.set_ready("ghost", True)

    def test_lobby_allows_spectators_without_blocking_race_start(self) -> None:
        lobby = MultiplayerLobby("room-42", max_spectators=1)

        lobby.join("host", "Host", reconnect_token="host-token")
        lobby.join("guest", "Guest")
        state = lobby.join("spectator-1", "Spectator", role="spectator")
        self.assertEqual([peer.peer_id for peer in state.spectators], ["spectator-1"])

        lobby.set_ready("host", True)
        state = lobby.set_ready("guest", True)

        self.assertTrue(state.can_start)
        with self.assertRaises(ValueError):
            lobby.set_ready("spectator-1", True)
        with self.assertRaises(ValueError):
            lobby.join("spectator-2", "Second Spectator", role="spectator")

    def test_lobby_disconnect_and_reconnect_require_token(self) -> None:
        lobby = MultiplayerLobby("room-42")

        lobby.join("host", "Host", reconnect_token="token-1")
        lobby.join("guest", "Guest")
        lobby.set_ready("host", True)
        lobby.set_ready("guest", True)
        state = lobby.disconnect("host")

        self.assertFalse(state.peer("host").connected)
        self.assertFalse(state.peer("host").ready)
        self.assertFalse(state.can_start)
        with self.assertRaises(ValueError):
            lobby.reconnect("host", "bad-token")

        state = lobby.reconnect("host", "token-1")
        self.assertTrue(state.peer("host").connected)
        self.assertFalse(state.peer("host").ready)


class RaceResultReconciliationTests(unittest.TestCase):
    def test_result_reconciliation_identifies_consistent_winner(self) -> None:
        reconciliation = RaceResultReconciliation(
            "seed:track",
            (
                RaceResultSummary("seed:track", "guest", True, 2, 240, 805.0),
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
            ),
        )

        self.assertTrue(reconciliation.is_consistent)
        self.assertEqual(reconciliation.winner_peer_id, "host")

    def test_result_reconciliation_rejects_gaps_and_wrong_race(self) -> None:
        rank_gap = RaceResultReconciliation(
            "seed:track",
            (
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
                RaceResultSummary("seed:track", "guest", True, 3, 240, 805.0),
            ),
        )
        wrong_race = RaceResultReconciliation(
            "seed:track",
            (
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
                RaceResultSummary("other", "guest", True, 2, 240, 805.0),
            ),
        )

        self.assertFalse(rank_gap.is_consistent)
        self.assertIsNone(rank_gap.winner_peer_id)
        self.assertFalse(wrong_race.is_consistent)


class AuthoritativeRaceDecisionTests(unittest.TestCase):
    def test_authoritative_decision_accepts_complete_expected_results(self) -> None:
        decision = authoritative_race_decision(
            "seed:track",
            (
                RaceResultSummary("seed:track", "guest", True, 2, 240, 805.0),
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
            ),
            ("host", "guest"),
        )

        self.assertEqual(decision, AuthoritativeRaceDecision("seed:track", True, "host", "accepted"))

    def test_authoritative_decision_rejects_missing_or_extra_submitters(self) -> None:
        missing_guest = authoritative_race_decision(
            "seed:track",
            (RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),),
            ("host", "guest"),
        )
        forged_peer = authoritative_race_decision(
            "seed:track",
            (
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
                RaceResultSummary("seed:track", "intruder", True, 2, 240, 805.0),
            ),
            ("host", "guest"),
        )

        self.assertFalse(missing_guest.accepted)
        self.assertIsNone(missing_guest.winner_peer_id)
        self.assertEqual(missing_guest.reason, "unexpected result submitters")
        self.assertFalse(forged_peer.accepted)
        self.assertIsNone(forged_peer.winner_peer_id)
        self.assertEqual(forged_peer.reason, "unexpected result submitters")

    def test_authoritative_decision_rejects_wrong_race_unfinished_and_bad_ranks(self) -> None:
        wrong_race = authoritative_race_decision(
            "seed:track",
            (
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
                RaceResultSummary("other", "guest", True, 2, 240, 805.0),
            ),
            ("host", "guest"),
        )
        unfinished = authoritative_race_decision(
            "seed:track",
            (
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
                RaceResultSummary("seed:track", "guest", False, 2, 240, 805.0),
            ),
            ("host", "guest"),
        )
        rank_gap = authoritative_race_decision(
            "seed:track",
            (
                RaceResultSummary("seed:track", "host", True, 1, 240, 810.0),
                RaceResultSummary("seed:track", "guest", True, 3, 240, 805.0),
            ),
            ("host", "guest"),
        )

        self.assertEqual(wrong_race.reason, "race id mismatch")
        self.assertEqual(unfinished.reason, "unfinished result")
        self.assertEqual(rank_gap.reason, "invalid ranking")


class MatchmakingQueueTests(unittest.TestCase):
    def test_public_matchmaking_pairs_compatible_racers_into_ready_lobby(self) -> None:
        queue = MatchmakingQueue("qa")

        self.assertIsNone(queue.enqueue(MatchmakingTicket("host", "Host", region="eu")))
        match = queue.enqueue(MatchmakingTicket("guest", "Guest", region="eu"))

        self.assertIsNotNone(match)
        self.assertEqual(match.room_code, "QA0001")
        self.assertEqual(match.peer_ids, ("guest", "host"))
        self.assertTrue(match.lobby.can_start)
        self.assertEqual(queue.waiting_tickets, ())


class PartyLobbyTests(unittest.TestCase):
    def test_party_invite_acceptance_creates_ready_private_matchmaking_tickets(self) -> None:
        party = PartyLobby("ROOM42", "host")
        party.join("host", "Host")

        invite = party.invite("invite-1", "host", "guest", "ROOM42")
        self.assertEqual(invite.status, "pending")
        accepted = party.accept_invite("invite-1", "Guest")
        self.assertEqual(accepted.status, "accepted")
        self.assertEqual([member.peer_id for member in party.members], ["guest", "host"])
        self.assertFalse(party.can_matchmake)

        party.set_ready("host", True)
        party.set_ready("guest", True)
        tickets = party.matchmaking_tickets(region="eu")

        self.assertTrue(party.can_matchmake)
        self.assertEqual([ticket.private_room_code for ticket in tickets], ["ROOM42", "ROOM42"])
        self.assertEqual([ticket.region for ticket in tickets], ["eu", "eu"])

    def test_party_invite_requires_leader_and_tracks_decline_cancel(self) -> None:
        party = PartyLobby("ROOM42", "host")
        party.join("host", "Host")
        party.join("guest", "Guest")

        with self.assertRaises(ValueError):
            party.invite("bad", "guest", "third", "ROOM42")

        party.leave("guest")
        invite = party.invite("invite-1", "host", "guest", "ROOM42")
        self.assertEqual(party.decline_invite(invite.invite_id).status, "declined")
        self.assertEqual(party.cancel_invite(invite.invite_id).status, "cancelled")

    def test_party_feeds_private_matchmaking_queue(self) -> None:
        party = PartyLobby("ROOM42", "host")
        party.join("host", "Host")
        party.invite("invite-1", "host", "guest", "ROOM42")
        party.accept_invite("invite-1", "Guest")
        party.set_ready("host", True)
        party.set_ready("guest", True)
        queue = MatchmakingQueue()

        tickets = party.matchmaking_tickets()
        self.assertIsNone(queue.enqueue(tickets[0]))
        match = queue.enqueue(tickets[1])

        self.assertIsNotNone(match)
        self.assertEqual(match.room_code, "ROOM42")
        self.assertTrue(match.lobby.can_start)

    def test_online_invite_rejects_invalid_status(self) -> None:
        with self.assertRaises(ValueError):
            OnlineInvite("invite-1", "host", "guest", "ROOM42", "expired")

    def test_matchmaking_keeps_incompatible_regions_and_modes_waiting(self) -> None:
        queue = MatchmakingQueue()

        self.assertIsNone(queue.enqueue(MatchmakingTicket("alice", "Alice", mode="duel", region="eu")))
        self.assertIsNone(queue.enqueue(MatchmakingTicket("bob", "Bob", mode="duel", region="us")))
        self.assertIsNone(queue.enqueue(MatchmakingTicket("carol", "Carol", mode="time_trial", region="eu")))

        self.assertEqual([ticket.peer_id for ticket in queue.waiting_tickets], ["alice", "bob", "carol"])

    def test_private_matchmaking_requires_same_room_code(self) -> None:
        queue = MatchmakingQueue()

        self.assertIsNone(queue.enqueue(MatchmakingTicket("host", "Host", private_room_code="ROOM42")))
        self.assertIsNone(queue.enqueue(MatchmakingTicket("stranger", "Stranger", private_room_code="OTHER")))
        match = queue.enqueue(MatchmakingTicket("guest", "Guest", private_room_code="ROOM42"))

        self.assertIsNotNone(match)
        self.assertEqual(match.room_code, "ROOM42")
        self.assertEqual(match.peer_ids, ("guest", "host"))
        self.assertEqual([ticket.peer_id for ticket in queue.waiting_tickets], ["stranger"])

    def test_matchmaking_cancel_removes_waiting_ticket(self) -> None:
        queue = MatchmakingQueue()
        ticket = MatchmakingTicket("host", "Host")

        queue.enqueue(ticket)

        self.assertEqual(queue.cancel("host"), ticket)
        self.assertIsNone(queue.cancel("host"))
        self.assertEqual(queue.waiting_tickets, ())


if __name__ == "__main__":
    unittest.main()
