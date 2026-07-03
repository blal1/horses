# Progress Tracker

Update after every completed change. Anyone reading this should know what is done, in progress, and next.

---

## Current Status

**Version:** 0.1.0 (prototype)
**Phase:** Feature build / balancing
**Last completed:** Runtime diagnostics summary — support diagnostics now report save/log file status, runtime log tail, crash-report count, and queued analytics count, with headless smoke coverage.
**Next:** Continue converting prototype modules into complete playable user flows, with priority on remaining backend persistence gaps and quality-gate cleanup.
**Last verification:** `python -m pytest` — 460 passed

> The vertical slice is complete and playable end to end. "Shipped" below means *built and tested in the prototype*, not *final*. The roadmap captures planned work that does not exist in the code yet.

---

## Shipped Features

### Domain & Content
- [x] Domain types: `Horse`/`HorseStats`, `Track`/`TrackSegment`, `Weather`, `Stable`, `RivalProfile`
- [x] Strict JSON loaders (`content/loaders.py`) with typed errors
- [x] Content: 12 horses, 4 tracks, 4 weather, 4 stables, 6 rivals, 6-race championship, per-track obstacles
- [x] Optional ElevenLabs generated-SFX merge into the sound catalog

### Simulation
- [x] Deterministic seeded `RaceEngine.tick` (pace, speed, stamina, stability, distance)
- [x] Surface / weather / fatigue / curve / slope modifiers
- [x] Opponent pack-racing AI (shadow pace + boosts + aggression + bounded noise)
- [x] Event emission: started, turn, opponent proximity, stamina, status, final stretch, finish
- [x] Trait-driven racing (`simulation/traits.py`): per-tick speed/stamina/acceleration from `Horse.traits`

### Input & Audio
- [x] `RaceCommand` + keyboard / fake input backends
- [x] `AudioEngine` priority sort + `AudioEventPolicy` cooldowns + `AudioEventRouter`
- [x] `SoundCatalog` + `SoundCueMap` (preferred + fallback)
- [x] 2D / 3D positional cues; backend-neutral spatial mixer with distance/rear/lateral shaping
- [x] Opponent readability: per-horse signature sounds layered with approach/passing, falling-behind, and inside-blocking cues
- [x] Pooled moving opponent audio: nearby rivals get positioned gait/gallop loops with surface/weather/inner-rail texture and distance/speed/stamina progression
- [x] Audio playback/codecs: shared SDL_mixer setup, 32 playback channels, channel vs stream codec validation, Ogg/Opus/MP3/FLAC support policy, tracker-module stream recognition, and loop-aware weather ambience
- [x] Accessibility/speech: NVDA client DLL fallback, priority-aware interrupt policy, and speaker tests for reliable announcements
- [x] `VoiceFeedbackController` (status, repeat-last, help)
- [x] `PygameAudioBackend` + NVDA speech (`NvdaSpeaker`)
- [x] Audio mix profiles (normal / descriptive / minimal), music playback
- [x] Continuous player horse audio: gait/surface loops, inner-rail gallop texture, low-stamina breathing, and recovery exhale

### Modes & Progression
- [x] Quick race, tutorial, training (levels 0–5), career championship (6 races) with a dedicated career hub for race/training/rest choices, obstacle lab
- [x] Replay (audio timeline with pause/step/final-stretch/key-moment controls plus share export files), statistics screen, profile screen, track editor, time-trial best tracking, and ghost-race comparison against the last deterministic replay
- [x] Stable boosts, training boosts, rival championship standings
- [x] Progress persistence (`save/progress.json`) with tolerant load
- [x] Release-candidate settings persistence: audio mix, speech verbosity, language, controller profile, mobile gesture profile, haptics, and controller-only navigation
- [x] Save/content foundation: atomic JSON save helpers, project file directories, content pack loading, and custom track round-trips
- [x] Local/online multiplayer duel: lockstep peer command frames, local second-player input scheme, socket transport, host/join lobby, room-code private sessions, and a menu-launched duel screen
- [x] Multiplayer foundation: lockstep peer command frames + per-tick buffer + serialization (`app/multiplayer.py`), socket/session/lobby plumbing with lobby handshakes and room codes (`app/network.py`), proven against `GameApp` and replay reconstruction

### UI
- [x] Main menu (19 rows: 6 selectors + 13 actions, including career hub, profile, time trial, and ghost race entries)
- [x] Real-time race screen (60 Hz), stats/replay/track-editor screens
- [x] Obstacle radar + dodge/jump/duck resolution with per-kind hit penalty (mild-long vs sharp-short)
- [x] Obstacle polish: staged warning sounds, action confirmation, near-miss feedback, timing quality, and kind-specific hit cues
- [x] Input/control foundation: hold-duration tracking, smoother keyboard shaping, and support for gradual steering/accel input
- [x] Pace feedback: spoken cruising / overpushing / recovering / wasting-stamina states from the deterministic race engine
- [x] Turn feedback: rail proximity, turn entry/apex/exit, and too-tight/too-wide cues for steering by ear
- [x] Full release-candidate tutorial script: pacing, stamina recovery, rival spatial audio, turn guidance, obstacle radar, dodge/jump/duck timing, replay controls, mobile gestures, status, and menu/restart/quit controls
- [x] Multiplayer chat: text chat + voice-line chat controls, sender switching, and spoken chat readback in the duel screen

### Tooling
- [x] pytest suite (one file per subsystem), coverage gate ≥ 80%
- [x] Deterministic balance fixtures across official tracks/weather for finish time, field spread, stamina envelope, and rain-vs-clear slowdown
- [x] Launchers: `play_game.py`, `c.py`, `PLAY_GAME.bat`, `horse-racing-game` entry point

---

## Decisions Made During Build

- Simulation is pure and seeded — replays/tests/balancing depend on determinism (only `random.Random(seed)`).
- All race state crosses layers as typed `RaceEvent`s; UI/audio never read engine internals.
- Audio is behind the `AudioBackend` ABC so the whole game runs headless under `FakeAudioBackend`.
- Content lives in JSON and is validated on load; missing sound files fail fast at bootstrap.
- NVDA speech degrades gracefully — absent DLL/NVDA never crashes a race.

---

## What's Next

Planned work that does not exist in the code yet. Each item names the concrete hook where it would plug in. Descriptive, not committed — no dates.

- [x] **Multiplayer (local/online)** — the engine is deterministic and seeded, so peers run the same `RaceEngine(seed)` and exchange one `RaceCommand` per tick. Local duel is wired in the menu and race screen; `app/network.py` has transport-neutral sessions, loopback relay, socket-backed newline-JSON transport, host/connect helpers, lobby handshakes, and lobby readiness state. `ui/pygame_online_lobby.py` provides Local Duel / Host Online / Join Online flow with room codes for private sessions, and `ui/pygame_multiplayer.py` accepts a real `LockstepSession` for remote-controlled peers.
- [x] **True seed+command replay** — `RaceReplay` (`app/replay.py`) stores `(seed, selection ids, tick_seconds, per-tick commands)`; `reconstruct_race` re-runs `RaceEngine` to reproduce the race bit-for-bit. Commands captured in `GameApp.run_quick_race` and `PygameRaceGame.run`, persisted as `GameProgress.last_replay` (serialized dict, survives a save round-trip). Covered by `tests/test_seed_command_replay.py`. (Spoken-line replay via `build_replay_lines` is retained.) Remaining polish: a UI scrubber / ghost-race overlay.
- [x] **Cross-platform speech** — `Speaker` ABC in `audio/speech.py` with `create_speaker(project_root, platform)` factory: NVDA (Windows), `say` (macOS), `spd-say`/speech-dispatcher (Linux), `NullSpeaker` fallback. `NvdaSpeaker` implements `Speaker`; `PygameAudioBackend` builds via the factory. Subprocess backends take an injectable runner and disable-on-first-failure. Covered by `tests/test_speech.py`.
- [x] **Content expansion** — now 12 horses (5 player / 7 opponent), 4 tracks (added `meadowbrook_mile` + its obstacles), 4 weather (added `fog`), 4 stables (added `ironwood`), 6 rivals. All additive via `content/*.json`; loaders/menu/engine pick them up automatically. Custom track-editor tracks are already selectable in races (`load_available_tracks` merges them, used by the menu + bootstrap). Covered by updated `tests/test_content_loading.py`. Remaining: multiple named custom tracks (editor uses one fixed id), and custom/new tracks in the career calendar.
- [x] **Career depth & difficulty tiers** — career length is now data-driven from `content/championship.json` (length flows through `record_race_result(career_length=...)`; load clamps to the calendar via `_career_cap`). Difficulty tiers (`app/difficulty.py`: Rookie/Pro/Elite) scale `opponent_strength`, threaded `AppConfig` → `RaceEngine._opponent_target_pace`; career escalates the tier across the season (`career_difficulty`) and announces it in the intro. Captured in `RaceReplay` for faithful career replays. Covered by `tests/test_difficulty.py`. Remaining: per-tier reward scaling / selectable difficulty for non-career modes.
- [x] **Trait effects in the sim** — `Horse.traits` now drive per-tick speed/stamina/acceleration via `simulation/traits.py` (`sprinter`, `front_runner`, `fast_finisher`/`late_surge`, `quick_start`, `endurance`/`patient_runner`, `mud_specialist`, `rain_comfort`, `inside_runner`). Pure + deterministic, applied in `RaceEngine._update_runner`, covered by `tests/test_traits.py`.
- [x] **Obstacle effects in the sim** — obstacle `kind` now drives a per-kind hit penalty (`ObstaclePenalty`, `penalty_for_kind` in `ui/obstacles.py`): soft ground (mud/puddle) is a long mild brake, barriers (rail/barrel/stone/cone) a sharp hard one, overhead a brief jolt. `pygame_game._apply_obstacle_penalty` enforces the kind's throttle cap; unknown kinds fall back to default. Covered by `tests/test_obstacles.py`.
- [x] **Audio asset generation pipeline** — loop closed. `audio/asset_coverage.py` detects which preferred cue sounds the catalog lacks (`missing_cue_sound_ids`, `coverage_report`) and emits a generator-ready prompt spec for exactly those (`prompt_spec_for_missing`, `write_missing_prompt_spec`), validated against `scripts/generate_elevenlabs_audio.py`'s own `_validate_spec`. Flow: cue rules → detect gap → spec → generate → merge into catalog. `event_cues.cue_sound_requirements()` exposes the requirements, and `scripts/write_missing_audio_prompt_spec.py` now provides the one-command missing-cue prompt-spec wrapper. Covered by `tests/test_audio_asset_coverage.py`; a regression guard asserts the shipped catalog covers all 11 cue sounds. Remaining: an in-app startup coverage log.

### Full Release Roadmap

The items below define a complete racing-game feature set. They are grouped by product area so the finished game can be shipped in layers without losing the audio-first core.

- [x] **Online race platform** — matchmaking, private rooms, friend invites, party lobbies, reconnects, spectator slots, region selection, race readiness, countdown sync, and race-result reconciliation. Current prototype work covers in-memory public/private matchmaking by mode and region, invite accept/decline/cancel state, party lobby ready checks that feed private matchmaking tickets, room-code gated host/join handshakes, saved reconnect settings, connected/ready racer gating, reconnect-token validation, spectator lobby slots, synchronized countdown starts, final result-summary exchange, and deterministic result reconciliation; the rest remains planned.
- [x] **Social graph** — accounts/profiles, friend requests, recent players, favorites, block/mute lists, presence, activity feed, status notes, and privacy controls. Current prototype work covers player profiles, friend-request accept/decline flow, visible friends, recent-player history, directional mute, blocking that removes friendship and prevents requests, presence state, sorted social snapshots, and persisted local social graph state in `save/social_graph.json`; favorites, feed, privacy controls, and backend sync remain planned.
- [x] **Text and voice communication** — public lobby chat, private messages, voice chat, push-to-talk, mute/deafen controls, voice line shortcuts, chat history, moderation filters, and TTS readback for accessibility. Current prototype work covers public and private message targeting, voice-line messages, viewer-specific chat history, directional mute, private-message block checks, term filtering, TTS-ready readback lines, and persisted local chat session state in `save/chat_session.json`; real voice transport, push-to-talk audio capture, deafen controls, and UI moderation remain planned.
- [x] **Competitive play** — ranked ladders, seasons, divisions, MMR, placements, leaderboards, skill-based matchmaking, race series, weekly cups, ghost challenges, and time-trial boards. Current prototype work covers in-memory ranked profiles, season ladder, deterministic MMR deltas by rank/field size, placement countdowns, division thresholds, leaderboard ordering, complete-field validation, and MMR matchmaking bands; persistence, ranked online UI, race series, cups, ghosts, and time-trial boards remain planned.
- [x] **Player identity** — racer profile, badges, emblems, avatar/horse-card customization, club tags, titles, cosmetics, and shared race signatures. Current prototype work covers in-memory player identity, validated club tags, title/emblem IDs, unique/limited badge equipment, cosmetic equipment, horse-card attachment, public display names, shareable identity signatures, persisted local profile identity in `save/profile.json`, and a menu-launched Profile screen for viewing/equipping title, badge, and cosmetic unlocks; avatar art and broader customization remain planned.
- [x] **Racing modes** — quick race, career, training, obstacle lab, tutorials, custom events, time trial, ghost race, head-to-head, relay/team events, endurance races, and race editor scenarios. Current prototype work covers an in-memory racing mode registry, player-count constraints, event specs, time-limit requirements, ghost replay requirements, team-size requirements, endurance/time-trial hooks, scenario objective progress, menu-launched Time Trial and Ghost Race modes, persisted best time-trial summaries keyed by horse/track/weather, ghost-race comparisons against the last deterministic replay, stats exposure, and headless smoke commands; relay/endurance/scenario dedicated gameplay loops remain planned.
- [x] **Career depth** — expanded season calendars, contracts, rival storylines, injuries/fatigue management, horse development, stable reputation, prize money, sponsorships, and branching championships. Current prototype work covers in-memory career contracts, sponsor payout scaling, reputation-gated contract signing, fatigue/injury/rest state, prize money, story completion flags, reputation/story-gated championship branches, playable career-hub exposure for reputation/active sponsor/projected win payout, explicit contract selection/signing, locked-contract requirement messaging, persisted `active_career_contract_id`, active contract payout application in career race rewards, persisted last-career-result reward summaries, incomplete-attempt no-reward summaries, persisted `career_fatigue` and `career_injury_days`, deterministic fatigue/injury consequences from career races and career training, rest-based condition recovery, injured race/training gating, condition/risk lines in the career hub, and the post-race `PygameCareerResultScreen` with spoken feedback; rival narrative content and full expanded calendars remain planned.
- [x] **Stable management** — stable upgrades, staff, training plans, breeding/sourcing, vet/conditioning, feeds/supplies, loadouts, and horse specialization. Current prototype work covers in-memory stable upgrades, staff hiring, weekly staff costs, per-horse training plans, feed/medicine supplies, training-effect bonuses, vet recovery bonuses, horse specialization, playable career-hub exposure for funds/weekly staff cost/training bonus/vet recovery/supplies, persisted stable upgrade/staff IDs, explicit upgrade/staff selection before purchase/hire, upgrade purchase from career rewards, staff hiring from career rewards, hired-staff upkeep deductions after career races, pre-race upkeep warnings/projected net payout in the career hub, post-race upkeep consequence feedback, `training_ring_1` plus `assistant_trainer` affecting later race training level, `recovery_clinic_1` plus `stable_vet` increasing future career-rest energy recovery, and staff tradeoff feedback showing trainers as training upside and vets as condition-risk mitigation against upkeep; breeding/sourcing, loadouts, and full UI management remain planned.
- [x] **Track ecosystem** — more official tracks, custom tracks, track sharing, track ratings, track discovery, weather presets, surface variants, and event-specific rulesets. Current prototype work covers track publishing, public/private visibility, ratings with tags, average ratings, discovery sorting/filtering, weather presets, surface variants, event rulesets, and persisted local track catalog metadata in `save/track_catalog.json`; real sharing backend, official track expansion, ratings UI, and discovery UI remain planned.
- [x] **Economy and rewards** — currency, unlocks, cosmetics, horse ownership progression, rewards for participation/performance, season passes or equivalent, and achievement milestones. Current prototype work covers in-memory wallet balances, reward grants, race participation/performance rewards, unlock purchases with level/currency gates, owned item tracking, achievement rewards, season level progression from XP, persisted profile wallet/unlocks/XP, and an idempotent Profile starter reward surfaced in UI; store UI, horse ownership progression, and season-pass UI remain planned.
- [x] **Accessibility and audio-first controls** — richer speech filtering, configurable verbosity, announcer profiles, voice macros, hold-to-speak, chat TTS, haptic hooks, and controller-only navigation. Current prototype work covers in-memory speech filters, event-group priority gates, announcer profiles, configurable verbosity, custom voice macros, hold-to-speak timing, haptic enablement, controller-only navigation prompts, and persisted release-candidate settings for audio mix, speech verbosity, language, controller profile, mobile gesture profile, haptics, and controller-only navigation; full input remapping UI remains planned.
- [x] **Community and moderation** — clubs, team chat, event scheduling, message reporting, moderation tools, profanity controls, rate limits, and anti-spam protections. Current prototype work covers club creation and membership roles, team chat with profanity filtering, scheduled club events with participant joins, message reports and report resolution, moderator/owner action permissions, warn/mute/ban actions, mute expiry checks, banned-post blocking, per-player club rate limits, anti-spam protections, sorted community snapshots, and persisted local community/moderation state in `save/community_hub.json`; real moderation UI, appeals, and backend enforcement remain planned.
- [x] **Replays and sharing** — replay browser, scrubbing, shared ghost files, race exports, highlight clips, photo-finish playback, and command-log sharing. Current prototype work covers in-memory replay summaries, a sorted/filterable replay browser, timeline scrubbing with key-moment and final-stretch jumps, shared ghost-file payloads based on deterministic command replays, text race exports, highlight clip windows from key replay events, photo-finish frame snapshots ordered by race rank/distance, command-log share payloads, a Replay-screen `S` export flow that writes share files plus a manifest to `save/replay_shares`, and a local replay-share index loader that rediscovers valid exported manifests while skipping corrupt/incomplete ones; file import UI, video/audio clip rendering, and online sharing remain planned.
- [x] **Cross-platform support** — Windows, Linux, and macOS packaging; controller support; remapping; save sync; and install/update flow. Current prototype work covers validated desktop package targets and artifact names, default Windows/Linux/macOS package manifests, controller action bindings, remappable control profiles that produce `RaceCommand`s, platform-specific save roots, revision/checksum-based save-sync decisions with conflict detection, and update manifests with optional/mandatory install prompts; real package builds, native controller polling, cloud sync, and installer/updater integration remain planned.
- [x] **Live ops and telemetry** — remote config, analytics, crash reporting, A/B tuning for balance, seasonal events, and content rollout controls. Current prototype work covers typed remote config values and merges, bounded analytics event buffering with flush payloads, privacy-safe hashed analytics payloads, consent-gated local telemetry storage in `save/live_ops.json`, crash report generation with stable stack hashes and context, deterministic weighted A/B experiment assignment, remote balance tuning application, seasonal event activation windows, percentage/channel-based content rollout rules, and player-specific content enablement; real telemetry transport, privacy consent UI, dashboards, backend rollout services, and crash upload integration remain planned.
- [x] **Localization and polish** — multilingual UI and speech text, format localization, accessibility language packs, tutorial expansion, onboarding, and UI copy polishing. Current prototype work covers in-memory localization catalogs with fallback locale behavior, format-value validation, missing-locale reporting, English/French/Spanish number-distance-duration formats, accessibility language packs with phonetic overrides and screen-reader hints, tutorial script scheduling, onboarding checklist completion, and copy polish rules for banned phrases, length, whitespace, and punctuation; full UI wiring, persisted language settings, translated content packs, and professional copy review remain planned.
- [x] **Multi-platform packaging and build** — executable packaging strategy, Windows/Linux/macOS build matrix, bundled content/assets/audio validation, local build scripts, artifact manifests, checksums, platform smoke tests, installer/app bundle/archive outputs, and release/update flow. Current prototype work covers 9.1-9.7: PyInstaller-based build strategy, native Windows/Linux/macOS build targets, Python 3.10 runtime metadata, bundled content/assets/NVDA/launcher asset rules, release-channel paths, deterministic artifact naming, generated PyInstaller commands, artifact manifest rows, repository asset validation, Windows executable/NVDA output paths, launcher shortcut metadata, save migration metadata, checksum helpers, Windows input validation, Linux tar.gz/AppImage target selection, Linux executable path metadata, `.desktop` entry generation, SDL/pygame/speech-dispatcher validation metadata, macOS `.app` bundle and executable metadata, `Info.plist` generation, `say` speech fallback validation metadata, quarantine/codesign/notarization notes, platform smoke-check definitions, Windows/Linux/macOS JSON plan scripts, build input metadata, clean/dist planning, platform build jobs, CI-ready commands, failure-log tail capture, aggregate plan output, release validation smoke-test plan for launch/content/audio fallback/save/replay/headless race, checksum manifest path metadata, artifact-present/skipped evaluation, `scripts/validate_release.py` JSON validation output, channel/version-scoped release folders, per-platform update manifests, rollback policy, deterministic signed checksum metadata, Windows/Linux/macOS install/update instructions, and `scripts/distribute_release.py` JSON distribution output. Current real build work also includes `scripts/build_windows_release.py`, a produced Windows x64 ZIP at `dist/stable/horse-racing-audio-first-0.1.0-windows-x64.zip`, and executable smoke checks for content, quick race, save, and replay. Remaining release-machine work: produce Linux/macOS artifacts on native machines, reduce/package-sign Windows output, sign with production keys, and publish hosted artifacts.
- [x] **Android mobile support** — Android app shell, touch gestures, accessible mobile race UI, Android audio/speech, APK/AAB packaging, and Play-ready release flow. Current prototype work covers 10.1-10.5: a pure `input.touch` gesture model that maps Android-friendly gestures into the existing deterministic `RaceCommand` stream, analog drag for pace/steering, swipe up/down for jump/duck, double tap for push, long press or two-finger tap for status readback, deadzone/scaling metadata, Android `apk`/`aab` platform target recognition, Android save-root metadata, isolated `android/` Gradle Kotlin DSL project, Android application module, package id `com.horseracing.audiofirst`, debug/release build-type metadata, manifest/launcher activity, minimal accessible `MainActivity`, resource strings/theme, ProGuard placeholder, Android mobile support documentation, native `RaceSurfaceView`, large full-screen lane drawing, Android `MotionEvent` gesture handling, Kotlin `MobileRaceCommand`, TalkBack `contentDescription`/`announceForAccessibility`, `performClick` tap accessibility, haptic feedback hooks, localized action labels, Activity wiring, native `AndroidAudioController`, `AudioFocusRequest` lifecycle handling, game/accessibility `AudioAttributes`, `TextToSpeech` status/action output, `SoundPool` cue registration/playback, transient ducking volume behavior, surface command-to-audio bridge, release signing metadata via `android/keystore.properties`, no-secret `keystore.properties.example`, Gradle debug APK/release AAB command metadata, artifact path metadata, ADB install/launch commands, device smoke-check checklist, `scripts/package_android.py` JSON output, Gradle wrapper generation, JVM target alignment, Android build-environment diagnostics via `scripts/check_android_release_env.py`, real `assembleDebug` execution, debug APK output at `android/app/build/outputs/apk/debug/app-debug.apk`, connected-device smoke automation via `scripts/smoke_android_device.py`, and tests. Remaining release-machine work: package real Android raw cue resources, sign production release builds, run physical-device smoke tests, and upload to Play.

---

## Prototype To Complete Playable Project

This is the next product roadmap. The rule for this phase: stop adding isolated prototype systems unless they directly help the release-candidate slice become playable end to end.

### Immediate Target: Vertical Slice Release Candidate

- [x] Define the release-candidate scope as quick race + short career + training + replay + Windows desktop build + Android debug build. Implemented as `horse_racing_game/app/release_candidate.py` with explicit modes, builds, smoke checks, deferred features, readiness reporting, and `scripts/validate_release_candidate.py` JSON output.
- [x] Make that slice playable from launch to save/replay/build validation without developer-only assumptions. Headless RC validation now executes launch/service wiring, quick race finish, short career save with replay payload, training completion, replay reconstruction, explicit Windows/Android artifact detection, and passes with the real Windows ZIP plus Android debug APK.
- [x] Use the slice to force integration decisions: UI exposure, persistence, audio polish, packaging, and device testing. The RC validator reports exactly which modes, smoke checks, and builds are missing, so future feature work must either pass the slice or stay deferred.
- [x] Defer features outside the slice unless they unblock the slice. The RC scope explicitly defers ranked ladder, full social backend, track marketplace, season pass, public Android release, macOS artifact, and Linux artifact until they serve the playable slice or a later release target.

### 1. Branch Foundations Into Real Gameplay

Many Phase 7/8 systems exist as tested models, but not all are exposed through complete playable flows.

- [ ] Integrate advanced career, stable management, economy, player identity, replay sharing, social, and matchmaking into accessible screens.
- [x] Start converting in-memory/prototype modules into real user flows: career-depth contracts and stable-management projections are now visible, spoken, persistable, and partially affect future race rewards/configuration in the career hub.
- [x] Add career result feedback as a real UI flow: completed career races now open a spoken post-race summary screen, and incomplete career attempts persist a failure/no-reward summary instead of reusing stale results.
- [x] Continue converting prototype modules into real user flows with menu entries, spoken labels, save/load behavior, and failure states. Current completed flows include career/stable decisions, Time Trial, Ghost Race, Profile identity/economy, and Replay share export.
- [x] Add UI-level tests or smoke paths for each integrated feature, not only model-level tests. Current career/stable result feedback has UI-level tests in `tests/test_pygame_secondary_screens.py`; Time Trial and Ghost Race have menu-model tests plus `--smoke-time-trial` and `--smoke-ghost` entrypoint coverage; Profile has menu/screen tests plus `--smoke-profile`; Replay sharing has model/screen tests plus `--smoke-replay-share`.
- [ ] Keep new feature work scoped to complete playable flows; avoid adding more standalone systems until the vertical slice is solid.

### 2. Finalize Core Gameplay

The core race loop must become satisfying, replayable, and balanced.

- [x] Balance horses, tracks, weather, stamina, pace, obstacles, and rival behavior using deterministic race fixtures. Current guards cover all official tracks except the obstacle lab across clear/windy/rain/fog, with finish-time, stamina, field-spread, and rain-slowdown envelopes.
- [ ] Complete career progression with rewards, contracts, fatigue, upgrades, and stable consequences that affect future races.
- [x] Add immediate career reward/failure feedback: reward base, sponsor payout, staff upkeep, net gain, balance, and stable consequence are shown and spoken after career races.
- [x] Make stable recovery investments affect future races: career rest now recovers more energy when `recovery_clinic_1` and/or `stable_vet` are owned, capped by max career energy and shown in the career hub.
- [x] Extend long-term career consequences beyond energy recovery: career races/training now add persisted fatigue and deterministic injury days, rest reduces both, vet staff lowers condition risk, and injured horses must rest before racing or training.
- [x] Build a full audio tutorial for pacing, turns, obstacle radar, jump/duck timing, stamina recovery, replay controls, and mobile gestures.
- [x] Finish clear mode loops for quick race, career, training, time trial, and ghost/replay.
- [x] Add regression tests for balance envelopes and career progression outcomes. Current coverage includes career reward/fatigue/injury/rest outcomes plus deterministic race balance envelopes.

### 3. Build Real Desktop And Mobile Runtime

Desktop release work:

- [x] Produce a real PyInstaller Windows x64 artifact on a native Windows machine.
- [x] Run Windows package smoke tests against the real executable for content loading, quick race, save write/read, and replay load.
- [ ] Produce real Linux and macOS artifacts on native release machines.
- [ ] Verify audio, saves, NVDA/speech, controller input, installer/update paths, and checksums on each desktop platform.

Android release work:

- [x] Add or generate a Gradle wrapper for the Android project.
- [x] Run `assembleDebug` on a machine with Android SDK and produce `android/app/build/outputs/apk/debug/app-debug.apk`.
- [ ] Run `bundleRelease` with production signing on a release machine.
- [ ] Connect `RaceSurfaceView` to the real game runtime or define a mobile-native runtime bridge.
- [ ] Package real Android raw audio cue resources and map them into `AndroidAudioController.registerCue`.
- [ ] Test TalkBack, TTS, audio focus, haptics, gestures, save paths, and launch flow on physical devices. Current machine has `adb` and an automated install/launch smoke script, but no device was connected during validation.

### 4. Add Persistence And Backend

Social, live, and multiplayer systems are mostly local/prototype today.

- [ ] Add persistent accounts/profiles. Current local progress: gameplay profile identity persists in `save/profile.json`, and social profile graph state persists in `save/social_graph.json`; account auth/cloud identity remains planned.
- [ ] Add cloud save sync or a robust local-first sync equivalent.
- [ ] Build a real matchmaking/lobby backend for public/private rooms, reconnects, and spectator flows.
- [ ] Persist shared replays, ghost files, custom tracks, ratings, and discovery metadata. Current local progress: last-replay share exports are written to `save/replay_shares`, valid replay share manifests can be indexed from disk, custom tracks persist in `save/custom_tracks.json`, and track shares/ratings/weather presets/rulesets persist in `save/track_catalog.json`; replay import UI, discovery UI, and backend sync remain planned.
- [ ] Persist moderation reports/actions, club data, chat history where appropriate, and appeal/audit state. Current local progress: social graph state, mute/block lists, and presence persist in `save/social_graph.json`; clubs, team chat, reports, moderation actions, bans, and mute expiry persist in `save/community_hub.json`; lobby/private/voice-line chat history and chat mute/block pairs persist in `save/chat_session.json`; appeals, audit trails, and backend sync remain planned.
- [x] Add analytics and crash reporting behind explicit consent, with privacy-safe payloads. Current implementation keeps local telemetry gated by consent, persists it in `save/live_ops.json`, and exposes hashed-player analytics payloads; real upload transport and consent UI remain planned.

### 5. Product Quality Gate

Before release, the game needs a hard quality pass.

- [ ] Run accessibility testing with real screen readers: NVDA, TalkBack, and platform speech fallbacks.
- [ ] Run manual test passes on keyboard, controller, Android touch, TalkBack, and NVDA.
- [ ] Remove menu dead zones and ensure every screen has clear status, back/cancel, repeat/help, and failure feedback.
- [x] Persist audio, speech, verbosity, language, controller, and mobile gesture settings.
- [ ] Audit packaged assets, generated audio, third-party licenses, and attribution.
- [x] Add crash logs, runtime diagnostics, and user-facing troubleshooting output. Current implementation keeps `runtime_debug.log`, stores consent-gated crash reports in `save/live_ops.json`, and builds a diagnostics summary with save-file status, log tail, crash counts, analytics counts, and troubleshooting lines via `app/diagnostics.py`; fuller in-app/export UI remains planned.
- [ ] Validate install/update flows for desktop and Android.

### 6. Expand Content And Polish

The product needs more playable material and final audio polish.

- [ ] Add more official tracks with distinct turn, surface, weather, and obstacle profiles.
- [ ] Expand career length and calendar variety.
- [ ] Give rivals clearer identity through narrative hooks, spoken lines, behavior, and sound signatures.
- [ ] Add special events, scenarios, time trials, and ghost challenges that reuse the core race loop.
- [ ] Finalize critical cue sounds and replace placeholders/fallbacks.
- [ ] Polish voice lines, announcements, music, ambience, mix profiles, and localization.

---

## Notes

- This is the single detailed tracker. See [[project-state]] for the compressed file map.
- Coverage gate is `fail_under = 80` in `pyproject.toml`; keep new logic tested.







