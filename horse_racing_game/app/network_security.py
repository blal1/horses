from __future__ import annotations

import hashlib
import hmac
import json
import platform
import socket
import ssl
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class TlsClientConfig:
    server_hostname: str
    cafile: str | None = None
    minimum_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2

    def __post_init__(self) -> None:
        if not self.server_hostname:
            raise ValueError("server_hostname must be non-empty")


@dataclass(frozen=True)
class TlsServerConfig:
    certfile: str
    keyfile: str
    cafile: str | None = None
    require_client_cert: bool = False
    minimum_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2

    def __post_init__(self) -> None:
        if not self.certfile:
            raise ValueError("certfile must be non-empty")
        if not self.keyfile:
            raise ValueError("keyfile must be non-empty")
        if self.require_client_cert and not self.cafile:
            raise ValueError("cafile is required when client certificates are required")


def client_tls_context(config: TlsClientConfig) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=config.cafile)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = config.minimum_tls_version
    return context


def server_tls_context(config: TlsServerConfig) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = config.minimum_tls_version
    context.load_cert_chain(certfile=config.certfile, keyfile=config.keyfile)
    if config.require_client_cert:
        context.load_verify_locations(cafile=config.cafile)
        context.verify_mode = ssl.CERT_REQUIRED
    return context


def wrap_client_socket(sock: socket.socket, config: TlsClientConfig) -> ssl.SSLSocket:
    return client_tls_context(config).wrap_socket(sock, server_hostname=config.server_hostname)


def wrap_server_socket(sock: socket.socket, config: TlsServerConfig) -> ssl.SSLSocket:
    return server_tls_context(config).wrap_socket(sock, server_side=True)


@dataclass(frozen=True)
class ProtocolEnvelope:
    session_id: str
    peer_id: str
    sequence: int
    kind: str
    payload: JsonObject
    sent_at_unix_s: float
    signature: str

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must be non-empty")
        if not self.peer_id:
            raise ValueError("peer_id must be non-empty")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not self.kind:
            raise ValueError("kind must be non-empty")
        if self.sent_at_unix_s <= 0.0:
            raise ValueError("sent_at_unix_s must be positive")
        if self.signature and len(self.signature) != 64:
            raise ValueError("signature must be 64 hex characters")

    def to_dict(self) -> JsonObject:
        return {
            "session_id": self.session_id,
            "peer_id": self.peer_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": self.payload,
            "sent_at_unix_s": self.sent_at_unix_s,
            "signature": self.signature,
        }


def sign_protocol_message(
    *,
    session_id: str,
    peer_id: str,
    sequence: int,
    kind: str,
    payload: JsonObject,
    shared_key: bytes,
    sent_at_unix_s: float | None = None,
) -> ProtocolEnvelope:
    if not shared_key:
        raise ValueError("shared_key must be non-empty")
    timestamp = time.time() if sent_at_unix_s is None else sent_at_unix_s
    envelope = ProtocolEnvelope(session_id, peer_id, sequence, kind, payload, timestamp, "")
    return ProtocolEnvelope(
        envelope.session_id,
        envelope.peer_id,
        envelope.sequence,
        envelope.kind,
        envelope.payload,
        envelope.sent_at_unix_s,
        _signature(envelope, shared_key),
    )


def verify_protocol_message(envelope: ProtocolEnvelope, shared_key: bytes) -> bool:
    if not shared_key:
        raise ValueError("shared_key must be non-empty")
    return hmac.compare_digest(envelope.signature, _signature(envelope, shared_key))


def protocol_envelope_from_dict(data: JsonObject) -> ProtocolEnvelope:
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return ProtocolEnvelope(
        session_id=str(data["session_id"]),
        peer_id=str(data["peer_id"]),
        sequence=int(data["sequence"]),
        kind=str(data["kind"]),
        payload=payload,
        sent_at_unix_s=float(data["sent_at_unix_s"]),
        signature=str(data["signature"]),
    )


def _signature(envelope: ProtocolEnvelope, shared_key: bytes) -> str:
    return hmac.new(shared_key, _canonical_payload(envelope), hashlib.sha256).hexdigest()


def _canonical_payload(envelope: ProtocolEnvelope) -> bytes:
    payload = {
        "session_id": envelope.session_id,
        "peer_id": envelope.peer_id,
        "sequence": envelope.sequence,
        "kind": envelope.kind,
        "payload": envelope.payload,
        "sent_at_unix_s": envelope.sent_at_unix_s,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


class ReplayWindow:
    def __init__(self, max_age_s: float = 30.0, max_seen_per_peer: int = 256) -> None:
        if max_age_s <= 0.0:
            raise ValueError("max_age_s must be positive")
        if max_seen_per_peer < 1:
            raise ValueError("max_seen_per_peer must be positive")
        self._max_age_s = max_age_s
        self._max_seen_per_peer = max_seen_per_peer
        self._seen: dict[tuple[str, str], deque[int]] = defaultdict(deque)
        self._seen_sets: dict[tuple[str, str], set[int]] = defaultdict(set)

    def accept(self, envelope: ProtocolEnvelope, *, now_unix_s: float | None = None) -> bool:
        now = time.time() if now_unix_s is None else now_unix_s
        if abs(now - envelope.sent_at_unix_s) > self._max_age_s:
            return False
        key = (envelope.session_id, envelope.peer_id)
        if envelope.sequence in self._seen_sets[key]:
            return False
        self._seen[key].append(envelope.sequence)
        self._seen_sets[key].add(envelope.sequence)
        while len(self._seen[key]) > self._max_seen_per_peer:
            evicted = self._seen[key].popleft()
            self._seen_sets[key].discard(evicted)
        return True


class RateLimiter:
    def __init__(self, max_events: int, window_s: float) -> None:
        if max_events < 1:
            raise ValueError("max_events must be positive")
        if window_s <= 0.0:
            raise ValueError("window_s must be positive")
        self._max_events = max_events
        self._window_s = window_s
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, now_unix_s: float | None = None) -> bool:
        if not key:
            raise ValueError("key must be non-empty")
        now = time.time() if now_unix_s is None else now_unix_s
        events = self._events[key]
        while events and now - events[0] >= self._window_s:
            events.popleft()
        if len(events) >= self._max_events:
            return False
        events.append(now)
        return True


def integrity_fingerprint(scope_salt: str, *, node: int | None = None, system: str | None = None) -> str:
    """Privacy-preserving abuse scope. Not anti-VM or anti-debug."""
    if not scope_salt:
        raise ValueError("scope_salt must be non-empty")
    machine_node = uuid.getnode() if node is None else node
    os_name = platform.system() if system is None else system
    payload = f"{scope_salt}:{os_name}:{machine_node:012x}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]
