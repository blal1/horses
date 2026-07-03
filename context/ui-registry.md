# UI Registry

This game's "UI" is **audio-first**: the canonical interface is the set of menu rows, keyboard controls, race events, spoken lines, and sound cues. The pygame screens mirror these visually. This registry is the inventory of every interactive surface so new entries match existing patterns. Read it before adding a menu row, control, event, or cue.

See [[ui-rules]] for conventions and [[ui-tokens]] for exact strings, constants, and asset ids.

---

## How to Use

Before adding an interactive element:

1. Check whether a similar one already exists here.
2. If yes — match its mode/control/event wording and behavior.
3. If no — add it following [[ui-rules]], then record it here (menu row, key, or event + its cue and spoken line).

---

## Menu Rows

Source of truth: `PygameMenuState` + `_selection_text` (`ui/menu_models.py`, `ui/pygame_menu.py`). `MENU_ROW_COUNT = 16`. Up/Down move rows; Left/Right cycle a selector; Enter/Space activates. Career mode now opens `ui/pygame_career_hub.py` before launching race/training/rest.

### Selectors (rows 0–5)

| Row | Selector       | Cycles over            | Selection field   |
| --- | -------------- | ---------------------- | ----------------- |
| 0   | Horse          | playable horses        | `player_horse_id` |
| 1   | Track          | available tracks       | `track_id`        |
| 2   | Weather        | weather options        | `weather_id`      |
| 3   | Audio profile  | `MIX_PROFILES`         | `audio_mix_id`    |
| 4   | Stable         | stables                | `stable_id`       |
| 5   | Difficulty     | Rookie / Pro / Elite   | `difficulty_id`   |

### Actions (rows 6–17)

| Row | Label / spoken               | Mode           | Behavior                                    |
| --- | ---------------------------- | -------------- | ------------------------------------------- |
| 6   | Quick race                   | `race`         | Launch a single race                        |
| 7   | Tutorial                     | `tutorial`     | Guided spoken controls during a race        |
| 8   | Training                     | `training`     | Finish to raise the horse's training level  |
| 9   | Career race                  | `career`       | Run the next championship race              |
| 10  | Career training              | `career_training` | Spend career energy to train             |
| 11  | Career rest                  | `career_rest`  | Recover career energy                       |
| 12  | Obstacle lab                 | `obstacle_lab` | Fixed short track; dodge/jump/duck drill    |
| 13  | Multiplayer                  | `multiplayer`  | Open local/online multiplayer lobby         |
| 14  | Replay                       | `replay`       | Audio timeline replay                        |
| 15  | Track editor                 | `track_editor` | Build a custom audio track                   |
| 16  | Statistics                   | `stats`        | Season stats + rival standings              |
| 17  | Quit                         | —              | Exit the game                               |

---

## In-Race Controls

Source: key handling in `ui/pygame_game.py`; help string in `audio/voice_feedback.py` (`HELP_TEXT`).

| Action            | Keys                                  | RaceCommand field        |
| ----------------- | ------------------------------------- | ------------------------ |
| Increase pace     | Up / W / Z                            | `throttle_delta` +       |
| Decrease pace     | Down / S                              | `throttle_delta` −       |
| Move lane left    | Left / A / Q                          | `lateral_delta` −        |
| Move lane right   | Right / D                             | `lateral_delta` +        |
| Push (sprint)     | Space                                 | `push_requested`         |
| Jump obstacle     | J                                     | `jump_requested`         |
| Duck obstacle     | K / Ctrl                              | `duck_requested`         |
| Status            | Tab / Enter                           | `request_status`         |
| Repeat last line  | R                                     | (voice feedback)         |
| Open menu         | M                                     | (next_action = menu)     |
| Restart race      | N                                     | (next_action = restart)  |
| Quit              | Escape                                | (next_action = quit)     |

---

## Race Events → Audio

Source: `RaceEngine` emits events; `AudioEventRouter.route` + `event_cues._CUE_RULES` turn them into speech + cues; `AudioEventPolicy` gates frequency.

| Event type            | Spoken line (router/voice)            | Preferred cue / mode             | Cooldown (s) |
| --------------------- | ------------------------------------- | -------------------------------- | ------------ |
| `race_started`        | "Start."                              | `race_start_gate_snap` (2D)      | —            |
| `turn_incoming`       | "Turn {left/right}."                  | `turn_warning_*_rail` (2D)       | 1.5          |
| `opponent_approaching`| rival approach line                   | `opponent_approach_*` (3D)       | 1.0          |
| `opponent_passing`    | rival passing line                    | `opponent_pass_whoosh` (3D)      | 1.0          |
| `low_stamina`         | "Low stamina."                        | `horse_breath_low_stamina` (2D)  | 5.0          |
| `critical_stamina`    | "Critical stamina."                   | `horse_breath_low_stamina` (2D)  | 5.0          |
| `status_requested`    | rank / distance / stamina / weather   | (speech only)                    | 0.75         |
| `final_stretch`       | "Final stretch."                      | `final_stretch_crowd_rise` (2D)  | —            |
| `finish_line_crossed` | "Finished rank {n}."                  | `finish_line_bell_crowd` (2D)    | —            |
| `race_finished`       | —                                     | `ui_confirm_warm_chime` (2D)     | —            |
| `obstacle_radar`      | (ping only, staged)                   | `obstacle_warning_diamond` (2D)  | —            |
| `obstacle_warning`    | "Obstacle {label}. {action}."         | `obstacle_warning_diamond` (2D)  | 1.2          |
| `obstacle_hit`        | "Hit {label}."                        | `obstacle_hit_rail_marker` (2D)  | 1.0          |
| `obstacle_avoided`    | "Cleared {label} by {action}."        | `obstacle_avoided_clean_pass`    | —            |

Each cue falls back to a category (+token) sound when the preferred id is absent — see [[ui-tokens]] and `event_cues._CUE_RULES`.

---

## Obstacle Radar Stages

`ObstacleController` (`ui/obstacles.py`) pings as a hazard approaches at `RADAR_DISTANCES_M = (120, 80, 45, 25, 12)` m, then emits `obstacle_warning` within 38 m and resolves within 3.2 m to `obstacle_avoided` or `obstacle_hit` (1.25 s penalty). Required actions: `dodge` (clear the lane), `jump` (J), `duck` (K/Ctrl).

---

## Secondary Screens

| Screen                   | Class (`ui/`)              | Purpose                                  |
| ------------------------ | ------------------------- | ---------------------------------------- |
| Stats                    | `PygameStatsScreen`       | Season stats, wins/podiums, rival standings, last online race summary |
| Replay                   | `PygameReplayScreen`      | Audio replay timeline with pause/step/final-stretch/key-moment controls |
| Track editor             | `PygameTrackEditorScreen` | Build/save a custom audio track          |
| Online lobby             | `PygameOnlineLobbyScreen` | Choose local duel, host online, join online, reconnect saved room settings, or regenerate a private room code with synced countdown and ready gate |

### Replay Controls

| Action             | Keys              | Behavior |
| ------------------ | ----------------- | -------- |
| Play / pause       | Space             | Toggle timeline playback |
| Step forward       | Right / N         | Play current event and advance |
| Step backward      | Left / B          | Move back and play an earlier event |
| Final stretch      | F                 | Jump to the final-stretch marker |
| Last key moment    | R                 | Replay the most recent key event |
| Return             | M / Escape / Q    | Leave replay screen |

### Online Lobby Controls

| Action       | Keys / Row         | Behavior |
| ------------ | ------------------ | -------- |
| Local Duel   | Row 0 / Enter      | Start same-keyboard lockstep duel |
| Host Online  | Row 1 / Enter      | Listen for a guest on the configured port and start a synced countdown |
| Join Online  | Row 2 / Enter      | Connect to configured host and port, then wait for the synced countdown |
| Room Code    | Row 3 / Enter      | Regenerate the private room code |
| Host Address | Row 4 / Enter      | Edit host address for joining |
| Port         | Row 5 / Enter      | Edit TCP port |
| Ready        | Row 6 / Enter      | Toggle ready before connecting |
| Reconnect    | Row 7 / Enter      | Reopen the last saved room settings |
| Return       | M / Escape         | Leave lobby screen |

Each is launched from the menu and reloads progress on return (`app/pygame_main.py`).

---

## Extending the Interface (Future Work)

How new interactive surfaces get added as planned features land (see [[architecture]] → Extension Points, [[progress-tracker]] → What's Next):

- **New menu row / mode**: add to `PygameMenuState` + `_selection_text` (`ui/menu_models.py`, `ui/pygame_menu.py`), bump `MENU_ROW_COUNT`, add a `mode` dispatch in `app/pygame_main.main`. Keep Quit last; selectors before actions. Career actions are centralized in `ui/pygame_career_hub.py`.
- **New in-race control**: wire the key in `ui/pygame_game.py` → a `RaceCommand` field, update `HELP_TEXT` and the tutorial messages, and add a row to In-Race Controls above.
- **New race event → audio**: emit the `RaceEvent`, add a `route` branch, a cue in `_CUE_RULES`, and (if it repeats) a cooldown — then record it in the Race Events → Audio table.
- **Network/AI command source** (multiplayer, ghost replay): feeds `RaceCommand`s through the same per-tick path as the keyboard; no new on-screen control needed, but document any lobby/replay screen here.
- **New secondary screen**: add the `ui/` class and its menu launcher, then list it in Secondary Screens above.
