# Multiplayer Security Threat Model

Status: draft for the current prototype. Multiplayer is not yet a production
service; current socket code is experimental and local/peer-oriented.

## Assets

- Account identity and display identity.
- Lobby membership, readiness, invite, and reconnect state.
- Race commands, tick ordering, and deterministic replay inputs.
- Race result summaries, ranks, rewards, unlocks, and economy changes.
- Chat messages and moderation events.
- Ban or abuse-scoping identifiers.

## Trust Boundaries

- Local client UI and simulation are untrusted for competitive outcomes.
- Network peers are untrusted, including lobby host in peer-hosted sessions.
- A future match/lobby server is trusted to authenticate users, sequence
  protocol messages, enforce rate limits, and authoritatively finalize results.
- Build resources and local secure saves protect tampering at rest, but do not
  make runtime client decisions trustworthy.

## Attacker Capabilities

- Forge or edit lockstep command packets.
- Replay old lobby, ready, start, command, chat, or result messages.
- Send commands for another peer ID.
- Report false race results, ranks, ticks, distances, rewards, or finish state.
- Stall, flood, or reorder packets to desync a race.
- Abuse reconnect tokens or private room codes.
- Spam chat, invites, matchmaking, and lobby state changes.
- Modify local saves or memory before/after a race.

## Current Prototype Risks

- `SocketLockstepTransport` sends newline-delimited JSON over raw sockets.
  It must be wrapped or replaced with the TLS/authenticated transport before
  production use.
- `RaceResultSummary` only records peer-reported summaries. It is useful for
  smoke tests and server-side validation inputs, not for awarding competitive
  rewards by itself.
- `LoopbackLockstepHub` is acceptable for same-process local play and tests,
  but it is not a security boundary.
- Reconnect tokens are plain application values and must not be treated as
  account credentials.

## Required Production Controls

- Authenticated transport: TLS for login, lobby, matchmaking, chat, and race
  channels. Certificate validation must be mandatory.
- Server-authoritative outcomes: the server decides match result, rank,
  rewards, currency, unlocks, and leaderboard updates. Clients submit inputs
  or telemetry, not final truth.
- Message authentication: every realtime message includes session ID, peer ID,
  monotonic sequence, tick index where applicable, timestamp/window, and a
  server-verifiable signature or MAC.
- Replay protection: reject duplicate sequence numbers, stale timestamps, old
  session IDs, and command ticks outside the accepted window.
- Rate limiting: enforce limits for login, matchmaking, lobby updates, chat,
  reconnect attempts, command stream bursts, and result submission.
- Peer authorization: only the server can assign peer IDs and lobby roles; a
  client cannot claim another peer ID in packets.
- Deterministic validation: for lockstep modes, the server or verifier must
  replay accepted input streams and compare the reported result before awarding
  anything.
- Integrity-only device fingerprinting: use it only for account/ban scoping and
  abuse correlation. Do not use hostile anti-VM or anti-debug checks.

## Implemented Primitives

- `horse_racing_game.app.network_security.ProtocolEnvelope` signs protocol
  messages with HMAC-SHA256 over canonical JSON.
- `signed_packet_envelope()` and `packet_from_signed_envelope()` bind lockstep
  packets to session ID, peer ID, sequence, message kind, timestamp, and
  signature.
- `ReplayWindow` rejects stale or duplicate protocol envelopes.
- `RateLimiter` provides fixed-window limits for login, lobby, chat, command,
  reconnect, and result-submission paths.
- `TlsClientConfig`, `TlsServerConfig`, and TLS context helpers require
  certificate validation, client hostname validation, and explicit server
  certificates for future login/lobby transports.
- `authoritative_race_decision()` rejects competitive outcomes unless the
  expected peer set, race ID, finished state, and rank ordering validate
  server-side.
- `integrity_fingerprint()` returns a salted, scoped hash for abuse
  correlation without anti-VM or anti-debug behavior.

## Non-Goals

- Blocking accessibility tooling, VMs, RDP, or screen-reader injection.
- Trusting client-side save encryption as proof of fair online play.
- Awarding competitive currency, rank, or unlocks from peer-reported results.

## Implementation Gate

Before enabling production multiplayer rewards or leaderboards, add tests that
prove:

- forged peer IDs are rejected;
- unsigned or bad-signature messages are rejected;
- duplicate sequence numbers and stale messages are rejected;
- excessive lobby/chat/command traffic is rate-limited;
- client-reported race results cannot award rewards without server validation;
- reconnect tokens are single-session scoped and expire.
