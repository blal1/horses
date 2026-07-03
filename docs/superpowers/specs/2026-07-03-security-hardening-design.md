# Security & Modern-Build Hardening — Design

Date: 2026-07-03
Project: horse-racing-audio-first

## Goal (ranked)

1. **Protect content / IP** — stop casual asset ripping and save editing.
2. **Look pro / modern** — clean crypto core, Cython-compiled sensitive
   modules, reproducible signed-release pipeline.
3. **Competitive integrity** — deferred; multiplayer is planned, not live.

## Threat model (honest scope)

Client-side encryption is a speed bump, not a vault: the decrypt key must
ship inside the client to play offline. This design stops casual ripping,
drag-and-drop save editing, and script kiddies. It does **not** stop a
skilled reverser with a debugger. Cython `.pyd` raises that bar; nothing
seals it. This matches every shipped Unity/Godot title.

Accessibility note: **no hostile anti-VM / anti-debugger / Cheat-Engine
blocking.** Many blind players use VMs, remote desktop, and screen-reader
injection; aggressive detection would false-ban legitimate disabled users.
Integrity/anti-tamper only.

## Architecture

Two new packages, all sensitive code compilable to native `.pyd`.

### 1. Crypto core — `horse_racing_game/security/`
- AES-256-GCM authenticated encryption; SHA-256 integrity.
- Per-context subkeys via HKDF-SHA256 (`assets`, `save`, `lang`, `pack`
  independent). One cracked context does not expose the others.
- Blob layout: `MAGIC "HRG1" | version | nonce(12) | ciphertext+tag`.
- Master key XOR-split into two shards in `_masterkey.py`, reassembled at
  runtime; hardened by Cython compilation. Rotate via
  `scripts/gen_master_key.py`.
- API: `encrypt_bytes/decrypt_bytes`, `encrypt_file/decrypt_file`,
  `sha256`, `verify` (constant-time). Tamper/wrong-key → `DecryptionError`.

### 2. Resource pack — `horse_racing_game/resources/`
- Single encrypted `.dat`: `MAGIC "HRPK" | version | index_len |
  encrypted-index(context=pack) | concatenated entries(context=assets)`.
- Index maps name → offset/length/sha256; each entry hash-verified before
  decrypt. `PackWriter` / `PackReader`; `loader.ResourceProvider` reads
  pack-or-loose transparently for callers.

### 3. Secure save — `horse_racing_game/app/savedata.py` (extended)
- `write_secure_json` / `read_secure_json` / `read_secure_object`, context
  `save`. Edited saves fail authentication → treated as "no valid save".
- Additive: the 9 existing plaintext callers are unchanged; sensitive files
  (progress, economy, unlocks) opt in file-by-file.

### 4. Build pipeline — `scripts/`
- `build_pack.py` → encrypted `dist/resources.dat`.
- `build_cython.py` → compiles `_masterkey`, `crypto`, `pack` to `.pyd`
  (MSVC). Gameplay code stays pure Python.
- `build_release.py` → pack + cython + optional `--strip-sources` (ship
  `.pyd` only) + PyInstaller.
- `HorseRacingAudioFirst.spec` bundles `resources.dat` (when built) and
  `cryptography`.

## Status

Built, wired, and tested (`496 passed` + real-data smoke):

- Crypto core, resource pack, secure save API, and plaintext-to-secure save
  migration for sensitive progress/profile state.
- Cython pipeline using real MSVC `.pyd` builds for `_masterkey`, `crypto`, and
  `pack`; dev trees keep generated `.pyd` files out of source.
- Runtime content loading through `ResourceProvider`, with release builds
  reading bundled `resources.dat`.
- Release orchestrator with pack build, encrypted language build step,
  Cython build, PyInstaller build, optional source stripping, optional
  Authenticode signing, install integrity manifest, and CI release-build check.
- Multiplayer security primitives: protocol threat model, signed HMAC protocol
  envelopes, replay window, rate limiter, TLS context builders, scoped
  integrity fingerprint, and server-side authoritative race-result decision
  gate.

## Remaining / future

- Production multiplayer service integration: wire login, lobby, matchmaking,
  chat, and race channels through the authenticated TLS transport helpers.
- Deterministic online validation: before awarding ranked rewards or
  leaderboard entries, replay accepted input streams server-side or use a
  stricter verifier in addition to the current authoritative decision gate.
- Real file-based localization content: when `localization/*.json` source files
  exist, `scripts/build_lang.py` will encrypt them into `content/lang/*.lng`
  for the release pack.
