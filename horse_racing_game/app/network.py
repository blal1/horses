from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import socket
import time
from typing import Iterable, Protocol

from horse_racing_game.app.multiplayer import LockstepCommandBuffer, LockstepFrame, PeerCommand, frame_from_dict, frame_to_dict
from horse_racing_game.app.network_security import ProtocolEnvelope, sign_protocol_message, verify_protocol_message
from horse_racing_game.app.replay import deserialize_command, serialize_command
from horse_racing_game.input.commands import RaceCommand


@dataclass(frozen=True)
class LockstepPacket:
    tick_index: int
    peer_id: str
    command: RaceCommand

    def __post_init__(self) -> None:
        if self.tick_index < 0:
            raise ValueError("tick_index must be non-negative")
        if not self.peer_id:
            raise ValueError("peer_id must be non-empty")


@dataclass(frozen=True)
class LobbyHandshake:
    room_code: str
    peer_id: str
    display_name: str
    is_ready: bool = False

    def __post_init__(self) -> None:
        if not self.room_code:
            raise ValueError("room_code must be non-empty")
        if not self.peer_id:
            raise ValueError("peer_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")


@dataclass(frozen=True)
class LobbyStartSignal:
    countdown_s: float
    start_at_unix_s: float

    def __post_init__(self) -> None:
        if self.countdown_s < 0.0:
            raise ValueError("countdown_s must be non-negative")
        if self.start_at_unix_s <= 0.0:
            raise ValueError("start_at_unix_s must be positive")


@dataclass(frozen=True)
class RaceResultSummary:
    race_id: str
    peer_id: str
    finished: bool
    rank: int
    ticks: int
    distance_m: float

    def __post_init__(self) -> None:
        if not self.race_id:
            raise ValueError("race_id must be non-empty")
        if not self.peer_id:
            raise ValueError("peer_id must be non-empty")
        if self.rank < 1:
            raise ValueError("rank must be positive")
        if self.ticks < 0:
            raise ValueError("ticks must be non-negative")
        if self.distance_m < 0.0:
            raise ValueError("distance_m must be non-negative")


@dataclass(frozen=True)
class RaceResultReconciliation:
    race_id: str
    summaries: tuple[RaceResultSummary, ...]

    @property
    def is_consistent(self) -> bool:
        if len(self.summaries) < 2:
            return False
        race_ids = {summary.race_id for summary in self.summaries}
        if race_ids != {self.race_id}:
            return False
        ordered = sorted(self.summaries, key=lambda summary: summary.rank)
        return [summary.rank for summary in ordered] == list(range(1, len(ordered) + 1))

    @property
    def winner_peer_id(self) -> str | None:
        if not self.is_consistent:
            return None
        return min(self.summaries, key=lambda summary: summary.rank).peer_id


@dataclass(frozen=True)
class AuthoritativeRaceDecision:
    race_id: str
    accepted: bool
    winner_peer_id: str | None
    reason: str


def authoritative_race_decision(
    race_id: str,
    summaries: Iterable[RaceResultSummary],
    expected_peer_ids: Iterable[str],
) -> AuthoritativeRaceDecision:
    if not race_id:
        raise ValueError("race_id must be non-empty")
    expected = tuple(str(peer_id) for peer_id in expected_peer_ids)
    if not expected:
        raise ValueError("expected_peer_ids must be non-empty")
    expected_set = set(expected)
    if len(expected_set) != len(expected):
        return AuthoritativeRaceDecision(race_id, False, None, "duplicate expected peer")

    submitted = tuple(summaries)
    submitted_peer_ids = {summary.peer_id for summary in submitted}
    if submitted_peer_ids != expected_set:
        return AuthoritativeRaceDecision(race_id, False, None, "unexpected result submitters")
    if len(submitted) != len(expected):
        return AuthoritativeRaceDecision(race_id, False, None, "duplicate result submitter")
    if any(summary.race_id != race_id for summary in submitted):
        return AuthoritativeRaceDecision(race_id, False, None, "race id mismatch")
    if any(not summary.finished for summary in submitted):
        return AuthoritativeRaceDecision(race_id, False, None, "unfinished result")

    ranks = sorted(summary.rank for summary in submitted)
    if ranks != list(range(1, len(submitted) + 1)):
        return AuthoritativeRaceDecision(race_id, False, None, "invalid ranking")

    winner = min(submitted, key=lambda summary: summary.rank)
    return AuthoritativeRaceDecision(race_id, True, winner.peer_id, "accepted")


@dataclass(frozen=True)
class MatchmakingTicket:
    peer_id: str
    display_name: str
    mode: str = "duel"
    region: str = "auto"
    private_room_code: str | None = None

    def __post_init__(self) -> None:
        if not self.peer_id:
            raise ValueError("peer_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")
        if not self.mode:
            raise ValueError("mode must be non-empty")
        if not self.region:
            raise ValueError("region must be non-empty")


@dataclass(frozen=True)
class MatchmakingMatch:
    room_code: str
    tickets: tuple[MatchmakingTicket, ...]
    lobby: LobbyState

    @property
    def peer_ids(self) -> tuple[str, ...]:
        return tuple(ticket.peer_id for ticket in self.tickets)


@dataclass(frozen=True)
class OnlineInvite:
    invite_id: str
    from_peer_id: str
    to_peer_id: str
    room_code: str
    status: str = "pending"

    def __post_init__(self) -> None:
        if not self.invite_id:
            raise ValueError("invite_id must be non-empty")
        if not self.from_peer_id:
            raise ValueError("from_peer_id must be non-empty")
        if not self.to_peer_id:
            raise ValueError("to_peer_id must be non-empty")
        if not self.room_code:
            raise ValueError("room_code must be non-empty")
        if self.status not in {"pending", "accepted", "declined", "cancelled"}:
            raise ValueError("invalid invite status")

    def accept(self) -> "OnlineInvite":
        return OnlineInvite(self.invite_id, self.from_peer_id, self.to_peer_id, self.room_code, "accepted")

    def decline(self) -> "OnlineInvite":
        return OnlineInvite(self.invite_id, self.from_peer_id, self.to_peer_id, self.room_code, "declined")

    def cancel(self) -> "OnlineInvite":
        return OnlineInvite(self.invite_id, self.from_peer_id, self.to_peer_id, self.room_code, "cancelled")


@dataclass(frozen=True)
class PartyMember:
    peer_id: str
    display_name: str
    ready: bool = False

    def __post_init__(self) -> None:
        if not self.peer_id:
            raise ValueError("peer_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")


class LockstepTransport(Protocol):
    def send(self, packet: LockstepPacket) -> None: ...

    def drain_outbound(self) -> tuple[LockstepPacket, ...]: ...

    def deliver(self, packet: LockstepPacket) -> None: ...

    def drain_inbound(self) -> tuple[LockstepPacket, ...]: ...


class InMemoryLockstepTransport:
    """Simple queue-backed transport for tests and future loopback sessions."""

    def __init__(self) -> None:
        self._outbound: deque[LockstepPacket] = deque()
        self._inbound: deque[LockstepPacket] = deque()

    def send(self, packet: LockstepPacket) -> None:
        self._outbound.append(packet)

    def drain_outbound(self) -> tuple[LockstepPacket, ...]:
        packets = tuple(self._outbound)
        self._outbound.clear()
        return packets

    def deliver(self, packet: LockstepPacket) -> None:
        self._inbound.append(packet)

    def drain_inbound(self) -> tuple[LockstepPacket, ...]:
        packets = tuple(self._inbound)
        self._inbound.clear()
        return packets


class SocketLockstepTransport:
    """Newline-delimited JSON transport for real lockstep packets.

    The socket is non-blocking after construction. ``send`` writes packets
    immediately; ``drain_inbound`` reads any complete packet lines currently
    available. Partial lines are buffered until the next pump.
    """

    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock
        self._socket.setblocking(False)
        self._read_buffer = b""
        self._inbound: deque[LockstepPacket] = deque()
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    def send(self, packet: LockstepPacket) -> None:
        if self._closed:
            raise ConnectionError("transport is closed")
        payload = json.dumps(packet_to_dict(packet), separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            self._socket.sendall(payload)
        except OSError as error:
            self.close()
            raise ConnectionError("unable to send lockstep packet") from error

    def drain_outbound(self) -> tuple[LockstepPacket, ...]:
        return ()

    def deliver(self, packet: LockstepPacket) -> None:
        self._inbound.append(packet)

    def drain_inbound(self) -> tuple[LockstepPacket, ...]:
        self._read_available()
        packets = tuple(self._inbound)
        self._inbound.clear()
        return packets

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._socket.close()
        except OSError:
            pass

    def _read_available(self) -> None:
        if self._closed:
            return
        while True:
            try:
                chunk = self._socket.recv(4096)
            except BlockingIOError:
                break
            except OSError as error:
                self.close()
                raise ConnectionError("unable to receive lockstep packet") from error
            if not chunk:
                self.close()
                break
            self._read_buffer += chunk
            while b"\n" in self._read_buffer:
                line, self._read_buffer = self._read_buffer.split(b"\n", 1)
                if line:
                    self._inbound.append(packet_from_dict(json.loads(line.decode("utf-8"))))


def host_socket_transport(
    host: str,
    port: int,
    handshake: LobbyHandshake | None = None,
    countdown_s: float = 0.0,
    timeout_s: float = 10.0,
) -> SocketLockstepTransport:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((host, port))
    listener.listen(1)
    listener.settimeout(timeout_s)
    connection: socket.socket | None = None
    try:
        connection, _address = listener.accept()
        if handshake is not None:
            remote = receive_lobby_handshake(connection, timeout_s)
            if remote.room_code != handshake.room_code:
                raise ConnectionError("room code mismatch")
            if not remote.is_ready or not handshake.is_ready:
                raise ConnectionError("lobby not ready")
            send_lobby_handshake(connection, handshake)
        if countdown_s > 0.0:
            signal = LobbyStartSignal(countdown_s=countdown_s, start_at_unix_s=time.time() + countdown_s)
            send_lobby_start_signal(connection, signal)
            _wait_until(signal.start_at_unix_s)
        return SocketLockstepTransport(connection)
    except Exception:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
        raise
    finally:
        listener.close()


def connect_socket_transport(
    host: str,
    port: int,
    handshake: LobbyHandshake | None = None,
    countdown_s: float = 0.0,
    timeout_s: float = 10.0,
) -> SocketLockstepTransport:
    sock = socket.create_connection((host, port), timeout=timeout_s)
    if handshake is not None:
        send_lobby_handshake(sock, handshake)
        ack = receive_lobby_handshake(sock, timeout_s)
        if ack.room_code != handshake.room_code:
            sock.close()
            raise ConnectionError("room code mismatch")
        if not ack.is_ready or not handshake.is_ready:
            sock.close()
            raise ConnectionError("lobby not ready")
    if countdown_s > 0.0:
        signal = receive_lobby_start_signal(sock, timeout_s)
        if abs(signal.countdown_s - countdown_s) > 0.5:
            sock.close()
            raise ConnectionError("countdown mismatch")
        _wait_until(signal.start_at_unix_s)
    return SocketLockstepTransport(sock)


def send_lobby_handshake(sock: socket.socket, handshake: LobbyHandshake) -> None:
    _send_line(sock, {
        "kind": "lobby_handshake",
        "room_code": handshake.room_code,
        "peer_id": handshake.peer_id,
        "display_name": handshake.display_name,
        "is_ready": handshake.is_ready,
    })


def receive_lobby_handshake(sock: socket.socket, timeout_s: float = 10.0) -> LobbyHandshake:
    payload = _read_line_json(sock, timeout_s)
    if payload.get("kind") != "lobby_handshake":
        raise ConnectionError("invalid lobby handshake")
    return LobbyHandshake(
        room_code=str(payload["room_code"]),
        peer_id=str(payload["peer_id"]),
        display_name=str(payload["display_name"]),
        is_ready=bool(payload.get("is_ready", False)),
    )


def send_lobby_start_signal(sock: socket.socket, signal: LobbyStartSignal) -> None:
    _send_line(sock, {
        "kind": "lobby_start",
        "countdown_s": signal.countdown_s,
        "start_at_unix_s": signal.start_at_unix_s,
    })


def receive_lobby_start_signal(sock: socket.socket, timeout_s: float = 10.0) -> LobbyStartSignal:
    payload = _read_line_json(sock, timeout_s)
    if payload.get("kind") != "lobby_start":
        raise ConnectionError("invalid lobby start signal")
    return LobbyStartSignal(
        countdown_s=float(payload["countdown_s"]),
        start_at_unix_s=float(payload["start_at_unix_s"]),
    )


def send_race_result_summary(sock: socket.socket, summary: RaceResultSummary) -> None:
    _send_line(sock, {
        "kind": "race_result",
        "race_id": summary.race_id,
        "peer_id": summary.peer_id,
        "finished": summary.finished,
        "rank": summary.rank,
        "ticks": summary.ticks,
        "distance_m": summary.distance_m,
    })


def receive_race_result_summary(sock: socket.socket, timeout_s: float = 10.0) -> RaceResultSummary:
    payload = _read_line_json(sock, timeout_s)
    if payload.get("kind") != "race_result":
        raise ConnectionError("invalid race result summary")
    return RaceResultSummary(
        race_id=str(payload["race_id"]),
        peer_id=str(payload["peer_id"]),
        finished=bool(payload["finished"]),
        rank=int(payload["rank"]),
        ticks=int(payload["ticks"]),
        distance_m=float(payload["distance_m"]),
    )


def _send_line(sock: socket.socket, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
    sock.sendall(data)


def _read_line_json(sock: socket.socket, timeout_s: float) -> dict:
    previous_timeout = sock.gettimeout()
    sock.settimeout(timeout_s)
    try:
        buffer = b""
        while b"\n" not in buffer:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("unexpected connection close during lobby handshake")
            buffer += chunk
        line, _rest = buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))
    finally:
        sock.settimeout(previous_timeout)


def _wait_until(target_unix_s: float) -> None:
    while True:
        remaining = target_unix_s - time.time()
        if remaining <= 0.0:
            return
        time.sleep(min(remaining, 0.1))


class LockstepSession:
    """Transport-agnostic lockstep session.

    The session owns deterministic tick buffering. A transport adapter can ship
    outbound packets elsewhere and feed received packets back through
    :meth:`accept_packet`.
    """

    def __init__(
        self,
        peer_ids: Iterable[str],
        local_peer_id: str,
        transport: LockstepTransport | None = None,
    ) -> None:
        self._buffer = LockstepCommandBuffer(peer_ids)
        if local_peer_id not in self._buffer.peer_ids:
            raise ValueError(f"unknown local peer id: {local_peer_id}")
        self._local_peer_id = local_peer_id
        self._transport = transport if transport is not None else InMemoryLockstepTransport()

    @property
    def peer_ids(self) -> tuple[str, ...]:
        return self._buffer.peer_ids

    @property
    def local_peer_id(self) -> str:
        return self._local_peer_id

    @property
    def transport(self) -> LockstepTransport:
        return self._transport

    def submit_local_command(self, tick_index: int, command: RaceCommand) -> LockstepPacket:
        packet = LockstepPacket(tick_index=tick_index, peer_id=self._local_peer_id, command=command)
        self._buffer.submit(tick_index, self._local_peer_id, command)
        self._transport.send(packet)
        return packet

    def accept_packet(self, packet: LockstepPacket) -> None:
        if packet.peer_id not in self._buffer.peer_ids:
            raise ValueError(f"unknown peer id: {packet.peer_id}")
        self._buffer.submit(packet.tick_index, packet.peer_id, packet.command)

    def accept_packets(self, packets: Iterable[LockstepPacket]) -> None:
        for packet in packets:
            self.accept_packet(packet)

    def pump_inbound(self) -> tuple[LockstepPacket, ...]:
        packets = self._transport.drain_inbound()
        self.accept_packets(packets)
        return packets

    def ready_frame(self, tick_index: int) -> LockstepFrame | None:
        return self._buffer.ready_frame(tick_index)

    def pop_ready_frame(self, tick_index: int) -> LockstepFrame | None:
        return self._buffer.pop_ready_frame(tick_index)

    def drain_outbound(self) -> tuple[LockstepPacket, ...]:
        return self._transport.drain_outbound()


@dataclass(frozen=True)
class LobbyPeer:
    peer_id: str
    display_name: str
    ready: bool = False
    role: str = "racer"
    reconnect_token: str | None = None
    connected: bool = True

    def __post_init__(self) -> None:
        if not self.peer_id:
            raise ValueError("peer_id must be non-empty")
        if self.role not in {"racer", "spectator"}:
            raise ValueError("role must be racer or spectator")


@dataclass(frozen=True)
class LobbyState:
    room_code: str
    peers: tuple[LobbyPeer, ...]
    host_peer_id: str = "host"

    @property
    def can_start(self) -> bool:
        racers = tuple(peer for peer in self.peers if peer.role == "racer")
        return len(racers) >= 2 and all(peer.ready and peer.connected for peer in racers)

    @property
    def racers(self) -> tuple[LobbyPeer, ...]:
        return tuple(peer for peer in self.peers if peer.role == "racer")

    @property
    def spectators(self) -> tuple[LobbyPeer, ...]:
        return tuple(peer for peer in self.peers if peer.role == "spectator")

    def peer(self, peer_id: str) -> LobbyPeer:
        for peer in self.peers:
            if peer.peer_id == peer_id:
                return peer
        raise KeyError(peer_id)


class MultiplayerLobby:
    def __init__(
        self,
        room_code: str,
        host_peer_id: str = "host",
        max_racers: int = 2,
        max_spectators: int = 4,
    ) -> None:
        if not room_code:
            raise ValueError("room_code must be non-empty")
        if not host_peer_id:
            raise ValueError("host_peer_id must be non-empty")
        if max_racers < 2:
            raise ValueError("max_racers must be at least 2")
        if max_spectators < 0:
            raise ValueError("max_spectators must be non-negative")
        self._room_code = room_code
        self._host_peer_id = host_peer_id
        self._max_racers = max_racers
        self._max_spectators = max_spectators
        self._peers: dict[str, LobbyPeer] = {}

    def join(
        self,
        peer_id: str,
        display_name: str,
        role: str = "racer",
        reconnect_token: str | None = None,
    ) -> LobbyState:
        if not peer_id:
            raise ValueError("peer_id must be non-empty")
        if role not in {"racer", "spectator"}:
            raise ValueError("role must be racer or spectator")
        existing = self._peers.get(peer_id)
        if existing is None:
            self._ensure_capacity(role)
            ready = False
        else:
            if existing.reconnect_token is not None and reconnect_token != existing.reconnect_token:
                raise ValueError("invalid reconnect token")
            ready = existing.ready
            role = existing.role
            reconnect_token = existing.reconnect_token if reconnect_token is None else reconnect_token
        self._peers[peer_id] = LobbyPeer(
            peer_id=peer_id,
            display_name=display_name or peer_id,
            ready=ready,
            role=role,
            reconnect_token=reconnect_token,
            connected=True,
        )
        return self.state()

    def set_ready(self, peer_id: str, ready: bool) -> LobbyState:
        peer = self._peers.get(peer_id)
        if peer is None:
            raise ValueError(f"unknown peer id: {peer_id}")
        if peer.role == "spectator" and ready:
            raise ValueError("spectators cannot ready for race start")
        self._peers[peer_id] = LobbyPeer(
            peer.peer_id,
            peer.display_name,
            ready,
            peer.role,
            peer.reconnect_token,
            peer.connected,
        )
        return self.state()

    def disconnect(self, peer_id: str) -> LobbyState:
        peer = self._peers.get(peer_id)
        if peer is None:
            raise ValueError(f"unknown peer id: {peer_id}")
        self._peers[peer_id] = LobbyPeer(
            peer.peer_id,
            peer.display_name,
            False,
            peer.role,
            peer.reconnect_token,
            False,
        )
        return self.state()

    def reconnect(self, peer_id: str, reconnect_token: str) -> LobbyState:
        peer = self._peers.get(peer_id)
        if peer is None:
            raise ValueError(f"unknown peer id: {peer_id}")
        if peer.reconnect_token != reconnect_token:
            raise ValueError("invalid reconnect token")
        self._peers[peer_id] = LobbyPeer(
            peer.peer_id,
            peer.display_name,
            peer.ready,
            peer.role,
            peer.reconnect_token,
            True,
        )
        return self.state()

    def state(self) -> LobbyState:
        return LobbyState(
            room_code=self._room_code,
            host_peer_id=self._host_peer_id,
            peers=tuple(sorted(self._peers.values(), key=lambda peer: peer.peer_id)),
        )

    def _ensure_capacity(self, role: str) -> None:
        peers = self.state().peers
        if role == "racer" and sum(1 for peer in peers if peer.role == "racer") >= self._max_racers:
            raise ValueError("racer slots are full")
        if role == "spectator" and sum(1 for peer in peers if peer.role == "spectator") >= self._max_spectators:
            raise ValueError("spectator slots are full")


class PartyLobby:
    """In-memory party model for invite-based matchmaking."""

    def __init__(self, party_id: str, leader_peer_id: str, max_members: int = 2) -> None:
        if not party_id:
            raise ValueError("party_id must be non-empty")
        if not leader_peer_id:
            raise ValueError("leader_peer_id must be non-empty")
        if max_members < 2:
            raise ValueError("max_members must be at least 2")
        self._party_id = party_id
        self._leader_peer_id = leader_peer_id
        self._max_members = max_members
        self._members: dict[str, PartyMember] = {}
        self._invites: dict[str, OnlineInvite] = {}

    @property
    def party_id(self) -> str:
        return self._party_id

    @property
    def leader_peer_id(self) -> str:
        return self._leader_peer_id

    @property
    def members(self) -> tuple[PartyMember, ...]:
        return tuple(sorted(self._members.values(), key=lambda member: member.peer_id))

    @property
    def invites(self) -> tuple[OnlineInvite, ...]:
        return tuple(sorted(self._invites.values(), key=lambda invite: invite.invite_id))

    @property
    def can_matchmake(self) -> bool:
        return len(self._members) >= 2 and all(member.ready for member in self._members.values())

    def join(self, peer_id: str, display_name: str) -> None:
        if peer_id not in self._members and len(self._members) >= self._max_members:
            raise ValueError("party is full")
        self._members[peer_id] = PartyMember(peer_id, display_name)

    def leave(self, peer_id: str) -> PartyMember:
        try:
            member = self._members.pop(peer_id)
        except KeyError as error:
            raise ValueError(f"unknown party member: {peer_id}") from error
        if peer_id == self._leader_peer_id and self._members:
            self._leader_peer_id = self.members[0].peer_id
        return member

    def set_ready(self, peer_id: str, ready: bool) -> None:
        member = self._member(peer_id)
        self._members[peer_id] = PartyMember(member.peer_id, member.display_name, ready)

    def invite(self, invite_id: str, from_peer_id: str, to_peer_id: str, room_code: str) -> OnlineInvite:
        if from_peer_id != self._leader_peer_id:
            raise ValueError("only the party leader can invite")
        self._member(from_peer_id)
        invite = OnlineInvite(invite_id, from_peer_id, to_peer_id, room_code)
        self._invites[invite_id] = invite
        return invite

    def accept_invite(self, invite_id: str, display_name: str) -> OnlineInvite:
        invite = self._invite(invite_id)
        if invite.status != "pending":
            raise ValueError("invite is not pending")
        accepted = invite.accept()
        self._invites[invite_id] = accepted
        self.join(invite.to_peer_id, display_name)
        return accepted

    def decline_invite(self, invite_id: str) -> OnlineInvite:
        invite = self._invite(invite_id)
        declined = invite.decline()
        self._invites[invite_id] = declined
        return declined

    def cancel_invite(self, invite_id: str) -> OnlineInvite:
        invite = self._invite(invite_id)
        cancelled = invite.cancel()
        self._invites[invite_id] = cancelled
        return cancelled

    def matchmaking_tickets(self, mode: str = "duel", region: str = "auto") -> tuple[MatchmakingTicket, ...]:
        if not self.can_matchmake:
            raise ValueError("party is not ready")
        return tuple(
            MatchmakingTicket(member.peer_id, member.display_name, mode=mode, region=region, private_room_code=self._party_id)
            for member in self.members
        )

    def _member(self, peer_id: str) -> PartyMember:
        try:
            return self._members[peer_id]
        except KeyError as error:
            raise ValueError(f"unknown party member: {peer_id}") from error

    def _invite(self, invite_id: str) -> OnlineInvite:
        try:
            return self._invites[invite_id]
        except KeyError as error:
            raise ValueError(f"unknown invite: {invite_id}") from error


class MatchmakingQueue:
    """Small in-memory matcher for public and private two-player rooms."""

    def __init__(self, room_prefix: str = "MM") -> None:
        if not room_prefix:
            raise ValueError("room_prefix must be non-empty")
        self._room_prefix = room_prefix.upper()
        self._tickets: dict[str, MatchmakingTicket] = {}
        self._match_counter = 0

    @property
    def waiting_tickets(self) -> tuple[MatchmakingTicket, ...]:
        return tuple(sorted(self._tickets.values(), key=lambda ticket: ticket.peer_id))

    def enqueue(self, ticket: MatchmakingTicket) -> MatchmakingMatch | None:
        self._tickets[ticket.peer_id] = ticket
        partner = self._find_partner(ticket)
        if partner is None:
            return None
        return self._build_match(partner, ticket)

    def cancel(self, peer_id: str) -> MatchmakingTicket | None:
        return self._tickets.pop(peer_id, None)

    def _find_partner(self, ticket: MatchmakingTicket) -> MatchmakingTicket | None:
        for candidate in self.waiting_tickets:
            if candidate.peer_id == ticket.peer_id:
                continue
            if _tickets_compatible(candidate, ticket):
                return candidate
        return None

    def _build_match(self, first: MatchmakingTicket, second: MatchmakingTicket) -> MatchmakingMatch:
        self._tickets.pop(first.peer_id, None)
        self._tickets.pop(second.peer_id, None)
        tickets = tuple(sorted((first, second), key=lambda item: item.peer_id))
        room_code = first.private_room_code or second.private_room_code or self._next_room_code()
        lobby = MultiplayerLobby(room_code)
        for ticket in tickets:
            lobby.join(ticket.peer_id, ticket.display_name)
            lobby.set_ready(ticket.peer_id, True)
        return MatchmakingMatch(room_code=room_code, tickets=tickets, lobby=lobby.state())

    def _next_room_code(self) -> str:
        self._match_counter += 1
        return f"{self._room_prefix}{self._match_counter:04d}"


def _tickets_compatible(first: MatchmakingTicket, second: MatchmakingTicket) -> bool:
    if first.mode != second.mode:
        return False
    if first.region != second.region:
        return False
    if first.private_room_code or second.private_room_code:
        return first.private_room_code is not None and first.private_room_code == second.private_room_code
    return True


class LoopbackLockstepHub:
    """In-process relay for multiple lockstep sessions.

    This is the current local-multiplayer wiring path and a convenient stand-in
    for real transport later.
    """

    def __init__(self, peer_ids: Iterable[str]) -> None:
        ordered_peer_ids = tuple(sorted(str(peer_id) for peer_id in peer_ids))
        if not ordered_peer_ids:
            raise ValueError("at least one peer is required")
        self._peer_ids = ordered_peer_ids
        self._sessions = {peer_id: LockstepSession(ordered_peer_ids, peer_id) for peer_id in ordered_peer_ids}

    @property
    def peer_ids(self) -> tuple[str, ...]:
        return self._peer_ids

    def submit(self, peer_id: str, tick_index: int, command: RaceCommand) -> LockstepPacket:
        session = self._session(peer_id)
        packet = session.submit_local_command(tick_index, command)
        self._relay_outbound(peer_id)
        return packet

    def ready_frame(self, tick_index: int) -> LockstepFrame | None:
        reference_session = self._sessions[self._peer_ids[0]]
        frame = reference_session.ready_frame(tick_index)
        if frame is None:
            return None
        if any(session.ready_frame(tick_index) is None for session in self._sessions.values()):
            return None
        return frame

    def pop_ready_frame(self, tick_index: int) -> LockstepFrame | None:
        frame = self.ready_frame(tick_index)
        if frame is None:
            return None
        for session in self._sessions.values():
            session.pop_ready_frame(tick_index)
        return frame

    def _relay_outbound(self, source_peer_id: str) -> None:
        packets = self._sessions[source_peer_id].drain_outbound()
        if not packets:
            return
        for packet in packets:
            for peer_id, session in self._sessions.items():
                if peer_id != source_peer_id:
                    session._transport.deliver(packet)
                    session.pump_inbound()

    def _session(self, peer_id: str) -> LockstepSession:
        try:
            return self._sessions[peer_id]
        except KeyError as error:
            raise ValueError(f"unknown peer id: {peer_id}") from error


def packet_to_dict(packet: LockstepPacket) -> dict:
    return {
        "tick_index": packet.tick_index,
        "peer_id": packet.peer_id,
        "command": serialize_command(packet.command),
    }


def packet_from_dict(data: dict) -> LockstepPacket:
    return LockstepPacket(
        tick_index=int(data["tick_index"]),
        peer_id=str(data["peer_id"]),
        command=deserialize_command(data["command"]),
    )


def signed_packet_envelope(
    packet: LockstepPacket,
    *,
    session_id: str,
    sequence: int,
    shared_key: bytes,
    sent_at_unix_s: float | None = None,
) -> ProtocolEnvelope:
    return sign_protocol_message(
        session_id=session_id,
        peer_id=packet.peer_id,
        sequence=sequence,
        kind="lockstep_packet",
        payload=packet_to_dict(packet),
        shared_key=shared_key,
        sent_at_unix_s=sent_at_unix_s,
    )


def packet_from_signed_envelope(envelope: ProtocolEnvelope, shared_key: bytes) -> LockstepPacket:
    if envelope.kind != "lockstep_packet":
        raise ValueError("expected lockstep_packet envelope")
    if not verify_protocol_message(envelope, shared_key):
        raise ValueError("invalid protocol signature")
    packet = packet_from_dict(envelope.payload)
    if packet.peer_id != envelope.peer_id:
        raise ValueError("packet peer does not match envelope peer")
    return packet


def frame_packets(frame: LockstepFrame) -> tuple[LockstepPacket, ...]:
    return tuple(
        LockstepPacket(tick_index=frame.tick_index, peer_id=item.peer_id, command=item.command)
        for item in frame.commands
    )


def session_from_frame(frame: LockstepFrame) -> tuple[LockstepPacket, ...]:
    return frame_packets(frame)


def session_frame_to_dict(frame: LockstepFrame) -> dict:
    return frame_to_dict(frame)


def session_frame_from_dict(data: dict) -> LockstepFrame:
    return frame_from_dict(data)
