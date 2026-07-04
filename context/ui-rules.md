# UI Rules

This is an **audio-first** game: the interface is sound first, screen second. These rules keep menus, controls, spoken feedback, and sound cues consistent, accessible, and predictable. Read them before adding or changing any menu row, control, race event, or cue.

See [[ui-registry]] for the full inventory and [[ui-tokens]] for exact strings, constants, and asset ids.

---

## Guiding Principle: Playable With The Screen Off

Everything the player needs to make a decision must reach them through **sound**:

- Every meaningful state change emits a `RaceEvent` that becomes a spoken line and/or a positioned cue.
- Status (rank, distance remaining, stamina, weather) is always available on demand (Tab/Enter) and announced periodically.
- The last spoken line is repeatable (R); the full control list is speakable (help).
- Never encode required information in visuals only. The pygame screen mirrors audio — it does not replace it.

---

## Menus

- The menu is a flat vertical list of rows (`MENU_ROW_COUNT = 20`): selectors (rows 0–5) then actions (rows 6–19). Keep this order.
- Up/Down move between rows; Left/Right cycle the selected selector; Space activates a row.
- Every row has a spoken `_selection_text` line naming what it is, its current value, and what Space does (e.g. "Track. Ashford Oval. Press space to change.").
- Selecting a row speaks it immediately. Activating an action speaks a short start line ("Starting tutorial.").
- Add new selectors before actions; add new actions before Quit (keep Quit last).

---

## Controls

- Support the current solo movement schemes: **Arrows** and **ZQSD** (AZERTY) for pace and lane.
- Reuse existing keys; don't reassign without updating tests and help text. Pace = Up/Z & Down/S; lane = Left/Q & Right/D; J push; Space jump; Ctrl duck; Tab status; R repeat; M menu; N restart; Esc quit.
- A control maps to a `RaceCommand` field — the UI builds the command, the engine interprets it. Don't put game logic in the key handler.
- If you add a control, update `HELP_TEXT` (`audio/voice_feedback.py`) and the tutorial messages (`ui/pygame_game.py`).

---

## Spoken Feedback

- Lines are **short, plain sentences** ("Final stretch.", "Low stamina.", "Turn left."). No jargon, no numbers the player can't act on.
- Status lines read rank, distance remaining, stamina, weather — in that order.
- Priorities drive ordering: higher-priority events speak first (`AudioEngine` sorts by `priority`). Reuse the existing priority bands (status ~40, proximity/turn ~60, key race beats ~80, help ~90).
- Route new spoken lines through `VoiceFeedbackController` / `AudioEventRouter` — never call `speak` ad hoc from the engine or UI.

---

## Sound Cues

- Every audible event has a cue rule in `event_cues._CUE_RULES`: a **preferred sound id** plus a **fallback category** (and optional token). Always provide a fallback so a missing asset still produces sound.
- Resolve sounds via the `SoundCatalog` — never hardcode a file path in routing.
- Use **3D positional** playback (`play_3d` with `RelativeAudioPosition`) for things in space (opponents); use **2D** (`play_2d`) for global cues (start, final stretch, finish, obstacles).
- Spatial sign convention: positive `right_m` = to the player's right, positive `forward_m` = ahead. Keep lane spacing (`1.15`) consistent across simulation, obstacles, and positioning.

---

## Event Frequency

- Anything that can fire many ticks in a row needs a cooldown in `AudioEventPolicy._EVENT_COOLDOWNS` (keyed by event type + subject). Match existing values: proximity 1.0 s, status 0.75 s, turn 1.5 s, stamina 5.0 s, obstacle warning 1.2 s.
- One-shot beats (start, final stretch, finish) need no cooldown but are announced once via engine guard flags.

---

## Accessibility & Degradation

- NVDA speech is best-effort: absent NVDA or a missing DLL must be logged once and skipped — the game keeps playing with cues.
- Missing sound files must not crash: the catalog's fallback resolves an alternative, or the cue is skipped.
- Respect the chosen audio mix profile (`MIX_PROFILES`): music/ambient volume and whether help/tutorial voice are on by default.

---

## Concurrency / Loop Discipline

- The race loop runs at `UI_FRAME_RATE = 60`. One engine tick per frame; route the tick's events, then draw.
- Read input, advance the engine, update obstacles, route events, render — in that order. Don't interleave audio calls into the physics update.

---

## Do Nots

- Never gate required information behind the visual screen.
- Never reassign or drop the active control scheme without updating the input contract, UI help, and tests.
- Never call `pygame.mixer` or NVDA directly outside `PygameAudioBackend` / `NvdaSpeaker`.
- Never emit an audible event without a cooldown if it can repeat every tick.
- Never hardcode a sound file path — go through the catalog with a fallback.
- Never add a spoken line longer than one short sentence.
