from __future__ import annotations

import ssl
from dataclasses import replace

from horse_racing_game.app.network_security import (
    RateLimiter,
    ReplayWindow,
    TlsClientConfig,
    TlsServerConfig,
    client_tls_context,
    integrity_fingerprint,
    protocol_envelope_from_dict,
    sign_protocol_message,
    verify_protocol_message,
)


def test_signed_protocol_message_round_trips_and_rejects_tampering() -> None:
    key = b"session-key"
    envelope = sign_protocol_message(
        session_id="race-1",
        peer_id="host",
        sequence=7,
        kind="command",
        payload={"tick": 12, "throttle": 1.0},
        shared_key=key,
        sent_at_unix_s=100.0,
    )

    assert verify_protocol_message(envelope, key)
    assert protocol_envelope_from_dict(envelope.to_dict()) == envelope

    tampered = replace(envelope, payload={"tick": 12, "throttle": 0.0})
    assert not verify_protocol_message(tampered, key)
    assert not verify_protocol_message(envelope, b"wrong-key")


def test_replay_window_rejects_duplicate_and_stale_messages() -> None:
    key = b"session-key"
    window = ReplayWindow(max_age_s=10.0)
    envelope = sign_protocol_message(
        session_id="race-1",
        peer_id="guest",
        sequence=1,
        kind="command",
        payload={"tick": 1},
        shared_key=key,
        sent_at_unix_s=100.0,
    )

    assert window.accept(envelope, now_unix_s=105.0)
    assert not window.accept(envelope, now_unix_s=106.0)

    stale = sign_protocol_message(
        session_id="race-1",
        peer_id="guest",
        sequence=2,
        kind="command",
        payload={"tick": 2},
        shared_key=key,
        sent_at_unix_s=50.0,
    )
    assert not window.accept(stale, now_unix_s=100.0)


def test_rate_limiter_allows_windowed_burst_then_blocks() -> None:
    limiter = RateLimiter(max_events=2, window_s=5.0)

    assert limiter.allow("peer:chat", now_unix_s=10.0)
    assert limiter.allow("peer:chat", now_unix_s=11.0)
    assert not limiter.allow("peer:chat", now_unix_s=12.0)
    assert limiter.allow("peer:chat", now_unix_s=16.1)


def test_integrity_fingerprint_is_scoped_and_stable() -> None:
    first = integrity_fingerprint("ban-scope", node=0x123456789ABC, system="Windows")
    second = integrity_fingerprint("ban-scope", node=0x123456789ABC, system="Windows")
    other_scope = integrity_fingerprint("analytics-scope", node=0x123456789ABC, system="Windows")

    assert first == second
    assert first != other_scope
    assert len(first) == 32


def test_client_tls_context_requires_certificate_validation() -> None:
    context = client_tls_context(TlsClientConfig("match.example.com"))

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_tls_configs_reject_insecure_missing_identity() -> None:
    try:
        TlsClientConfig("")
    except ValueError as error:
        assert "server_hostname" in str(error)
    else:
        raise AssertionError("empty server hostname should be rejected")

    try:
        TlsServerConfig("", "server.key")
    except ValueError as error:
        assert "certfile" in str(error)
    else:
        raise AssertionError("empty server certfile should be rejected")

    try:
        TlsServerConfig("server.crt", "server.key", require_client_cert=True)
    except ValueError as error:
        assert "cafile" in str(error)
    else:
        raise AssertionError("client certificate mode should require a CA file")
