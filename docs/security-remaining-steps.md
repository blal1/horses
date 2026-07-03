# Security Hardening — Remaining Steps

Status of the security/modern-build work and everything left to do.
Companion to `docs/superpowers/specs/2026-07-03-security-hardening-design.md`.

## Done (built, tested, verified)

- [x] Crypto core — AES-256-GCM, HKDF per-context subkeys, SHA-256 (`security/crypto.py`, `_masterkey.py`)
- [x] Resource pack — encrypted `.dat`, hash-verified entries (`resources/pack.py`, `loader.py`)
- [x] Secure save API — tamper-evident saves (`app/savedata.py`)
- [x] Cython build — real MSVC `.pyd` for the 3 sensitive modules
- [x] Release orchestrator + PyInstaller wiring (`scripts/build_release.py`, `.spec`)
- [x] Full test suite passing (`496 passed`) + real-data smoke

---

## Remaining Steps

### Phase A — Immediate hygiene (do now, no decisions needed)

- [x] **Delete dev `.pyd`** so source edits take effect during development:
  ```bash
  find horse_racing_game -name "*.pyd" -delete
  ```
  Compile only for release builds.
- [x] **Add `.pyd` and generated `.c` to `.gitignore`** (build artifacts, never commit):
  ```
  *.pyd
  build/cython/
  dist/resources.dat
  ```
- [x] **Rotate the master key once** before first real ship, then leave it:
  ```bash
  python scripts/gen_master_key.py
  ```
  (This invalidates any existing packs/saves — do it before shipping data.)

### Phase B — Wire IP protection into the game (goal #1)

- [x] **Secure the sensitive saves.** Switch progress/economy/unlocks from
      `atomic_write_json` / `load_json` to `write_secure_json` /
      `read_secure_json`. Candidate callers:
      `app/progress.py`, `app/profile.py`, `app/economy.py`, `app/career.py`.
      `progress.json` and `profile.json` now cover career, progression,
      unlocks, and economy state.
- [x] **Write a save migration.** On load: if a plaintext `.json` save exists,
      import it, re-write as secure, delete the old file. One-time, per file.
- [x] **Decide which saves stay plaintext.** Cosmetic/settings files can remain
      readable (e.g. keybindings) — only guard progression/economy.
      Current decision: protect `progress.json` and `profile.json`; keep
      custom tracks, social/chat/community/live-ops/replay export files
      plaintext because they are user-authored, diagnostic, or shareable data.
- [x] **Route content reads through `ResourceProvider`.** Replace direct
      `content/*.json` reads with `default_provider().get_json("content/…")`
      so the game runs from `resources.dat` in release, loose files in dev.
- [x] **Add pack build to the content workflow.** Re-run `build_pack.py`
      whenever `content/` or `assets/` change.
      Rebuilt `dist/resources.dat` after the master-key rotation.

### Phase C — Pro release delivery (goal #2)

- [x] **Full release dry-run:**
  ```bash
  python scripts/build_release.py --strip-sources
  ```
  Confirm the frozen exe launches and reads from the bundled pack.
  Non-stripping unsigned release build passed locally with
  `python scripts/build_release.py`; the frozen exe launched with
  `--smoke-content` and read the bundled pack. The destructive
  `--strip-sources` variant passed in a disposable release workspace
  (`C:\Users\bilal\Downloads\horses_strip_203966e4`); the three sensitive
  `.py` files were stripped, matching `.pyd` files remained, the frozen exe
  launched with `--smoke-content`, and the integrity manifest verified with
  zero issues.
- [x] **Code-signing.** Add a signtool step to `build_release.py`
      (Authenticode cert). Unsigned exes trip SmartScreen and antivirus.
- [x] **Build integrity manifest.** Emit a `sha256` manifest of shipped files;
      verify on launch to detect tampered installs (log, don't hard-block).
- [x] **Reproducible build doc.** Short `BUILD.md`: prerequisites (VS Build
      Tools / MSVC, uv), exact commands, expected outputs.
- [x] **CI build check.** GitHub Actions job that runs tests + a non-signed
      release build on push (`.github/` already exists).

### Phase D — Encrypted localization

- [x] Encrypt language files with context `lang` at build time.
- [x] Decrypt on load through the crypto core; keep source `.lng`/`.json`
      out of the shipped tree.
      Infrastructure is in place: `scripts/build_lang.py` converts future
      `localization/*.json` source files into encrypted `content/lang/*.lng`
      outputs before pack build, and runtime helpers decrypt with context
      `lang`. Current tree has no source language directory yet, so the build
      step is a no-op until file-based localization lands.

### Phase E — Multiplayer security (deferred until MP goes live)

- [x] **Threat model the protocol** before writing net code (what a cheater
      can forge: positions, results, currency).
      See `docs/multiplayer-security-threat-model.md`.
- [x] **TLS / authenticated transport** for login + lobby.
      Added TLS client/server context builders that require certificate
      validation, hostname validation on clients, and explicit server
      certificates. Production login/lobby code still needs to use these
      contexts when the network service is introduced.
- [x] **Server-authoritative state** for anything competitive — never trust
      client-reported outcomes.
      Added an authoritative race decision gate that only accepts complete
      results from the expected peer set, matching race IDs, finished racers,
      and contiguous ranks. Production reward and leaderboard code must call
      this server-side gate, or a stricter deterministic replay verifier, before
      awarding anything.
- [x] **Signed protocol messages** over the realtime channel.
      Added transport-agnostic HMAC-SHA256 protocol envelopes and signed
      lockstep packet helpers. Raw experimental sockets still need to be
      replaced or wrapped by the production authenticated transport.
- [x] **Machine fingerprint for anti-abuse** (account/ban scoping) —
      integrity/identity only, **not** hostile anti-VM (accessibility).
- [x] **Rate limiting + replay protection** on the server.
      Added reusable replay-window and rate-limiter primitives. These are ready
      to attach to the future server/authenticated transport layer.

---

## Explicitly NOT doing (by design)

- Hostile anti-VM / anti-debug / Cheat-Engine blocking — false-bans blind
  players who use VMs, RDP, and screen-reader injection. Integrity only.
- Reproducing Zero Hour Assault's proprietary pack format or keys — this
  build uses its own formats and standard crypto.

## Reference — key commands

| Task | Command |
|------|---------|
| Build pack | `python scripts/build_pack.py --out dist/resources.dat` |
| Compile `.pyd` | `python scripts/build_cython.py build_ext --inplace` |
| Full release | `python scripts/build_release.py --strip-sources` |
| Rotate key | `python scripts/gen_master_key.py` |
| Run security tests | `pytest tests/test_security_crypto.py tests/test_resource_pack.py tests/test_secure_save.py` |
| Clean dev `.pyd` | `find horse_racing_game -name "*.pyd" -delete` |
