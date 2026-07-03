# UI Tokens

This is an audio-first game with a minimal pygame screen. The "tokens" that must stay consistent are the **fixed strings, content ids, audio cue ids, and tuning constants** that make up the interface. Treat the values below as the single source of truth; reuse them verbatim rather than inventing new wording or ids.

See [[ui-registry]] for the full inventory and [[ui-rules]] for how to use these.

---

## Identity

| Token        | Value                                | Source                          |
| ------------ | ------------------------------------ | ------------------------------- |
| Package name | `horse-racing-audio-first`           | `pyproject.toml`                |
| Module       | `horse_racing_game`                  | package                          |
| Version      | `0.1.0`                              | `pyproject.toml`                |
| Entry point  | `horse-racing-game` → `app.pygame_main:main` | `[project.scripts]`     |
| NVDA client  | `nvdaControllerClient64.dll` (repo root) | `audio/nvda_speaker.py`     |

---

## Content IDs

### Horses (`content/horses.json`) — `role` player/opponent

| id | name | role | surface |
| -- | ---- | ---- | ------- |
| `ember_stride` | Ember Stride | player | turf |
| `night_rail` | Night Rail | player | dirt |
| `silver_heather` | Silver Heather | player | soft_turf |
| `copper_gate` | Copper Gate | opponent | turf |
| `river_chime` | River Chime | opponent | turf |
| `storm_marrow` | Storm Marrow | opponent | mud |
| `golden_switch` | Golden Switch | opponent | dirt |
| `meadow_signal` | Meadow Signal | opponent | soft_turf |
| `dawn_spark` | Dawn Spark | player | turf |
| `iron_vale` | Iron Vale | player | dirt |
| `brass_comet` | Brass Comet | opponent | dirt |
| `willow_drift` | Willow Drift | opponent | soft_turf |

### Tracks (`content/tracks.json`)

| id | name | length_m | surface | lanes | handedness | final_stretch_start_m |
| -- | ---- | -------- | ------- | ----- | ---------- | --------------------- |
| `ashford_oval` | Ashford Oval | 1600 | turf | 8 | left | 1200 |
| `bracken_dirt` | Bracken Dirt | 1200 | dirt | 6 | right | 850 |
| `audio_obstacle_lab` | Audio Obstacle Lab | 420 | turf | 5 | left | 320 |
| `meadowbrook_mile` | Meadowbrook Mile | 1500 | soft_turf | 8 | right | 1120 |

### Weather (`content/weather.json`)

| id | name | speed | stamina_cost | stability | ambient |
| -- | ---- | ----- | ------------ | --------- | ------- |
| `clear` | Clear | 1.00 | 1.00 | 1.00 | — |
| `windy` | Windy | 0.97 | 1.08 | 0.96 | `mixkit_wind_2608` |
| `rain` | Rain | 0.94 | 1.14 | 0.90 | `mixkit_rain_2393` |
| `fog` | Fog | 0.96 | 1.05 | 0.93 | `mixkit_wind_2608` |

### Stables (`content/stables.json`) — modifiers speed/stamina/handling/calm

| id | name | focus | speed | stamina | handling | calm |
| -- | ---- | ----- | ----- | ------- | -------- | ---- |
| `oak_lane` | Oak Lane Stable | balanced | 1.00 | 1.00 | 1.00 | 1.00 |
| `stormforge` | Stormforge Yard | speed | 1.025 | 0.985 | 0.99 | 1.04 |
| `heatherbank` | Heatherbank Endurance | stamina | 0.99 | 1.04 | 1.01 | 0.94 |
| `ironwood` | Ironwood Control | handling | 0.995 | 1.0 | 1.03 | 0.97 |

### Rivals (`content/rivals.json`)

`copper_gate`, `river_chime`, `storm_marrow`, `golden_switch`, `brass_comet`, `willow_drift` — each with `intro_line`, `approach_line`, `passing_line`.

### Championship (`content/championship.json`) — 3 races

`rookie_cup_opening` (ashford_oval/clear) → `bracken_pressure` (bracken_dirt/windy) → `ashford_final` (ashford_oval/rain).

---

## Audio Mix Profiles (`audio/mix_profile.py`)

| id | name | music_vol | ambient_vol | help_default | tutorial_voice |
| -- | ---- | --------- | ----------- | ------------ | -------------- |
| `normal` | Normal | 0.22 | 0.28 | true | true |
| `descriptive` | Descriptive | 0.16 | 0.22 | true | true |
| `minimal` | Minimal | 0.12 | 0.12 | false | false |

---

## Spoken Lines (use verbatim)

From `audio/event_router.py` and `audio/voice_feedback.py`:

| Trigger | Line |
| ------- | ---- |
| race start | `Start.` |
| turn | `Turn {direction}.` |
| low stamina | `Low stamina.` |
| critical stamina | `Critical stamina.` |
| final stretch | `Final stretch.` |
| finish | `Finished rank {rank}.` |
| obstacle warning | `Obstacle {label}. {action}.` |
| obstacle hit | `Hit {label}.` |
| obstacle avoided | `Cleared {label} by {action}.` |
| repeat with none | `No message to repeat.` |
| help | full control list (`HELP_TEXT`) |

`HELP_TEXT`: "Arrows, ZQSD, or WASD control pace and line. Space pushes. J jumps. K or Control ducks. Tab or Enter gives status. R repeats. M opens menu. N restarts. Escape quits."

---

## Sound Cue IDs (`audio/event_cues.py` `_CUE_RULES`)

| Event | Preferred id | Fallback category (+token) | Volume |
| ----- | ------------ | -------------------------- | ------ |
| `race_started` | `race_start_gate_snap` | countdown | 0.78 |
| `turn_incoming` | `turn_warning_left_rail` | wind | 0.62 |
| `opponent_approaching` | `opponent_approach_left` | horse | 0.66 |
| `opponent_passing` | `opponent_pass_whoosh` | horse | 0.66 |
| `low_stamina` | `horse_breath_low_stamina` | horse | 0.58 |
| `critical_stamina` | `horse_breath_low_stamina` | horse | 0.70 |
| `final_stretch` | `final_stretch_crowd_rise` | crowd | 0.68 |
| `finish_line_crossed` | `finish_line_bell_crowd` | ui (confirmation) | 0.75 |
| `race_finished` | `ui_confirm_warm_chime` | ui (confirmation) | 0.65 |
| `obstacle_radar` | `obstacle_warning_diamond` | ui (question) | 0.45 |
| `obstacle_warning` | `obstacle_warning_diamond` | ui (question) | 0.72 |
| `obstacle_hit` | `obstacle_hit_rail_marker` | ui (error) | 0.76 |
| `obstacle_avoided` | `obstacle_avoided_clean_pass` | ui (confirmation) | 0.52 |

Track audio profiles also reference `crowd_loop`, `wind_loop`, `rain_loop`, `countdown` ids per track (`content/tracks.json`).

---

## Event Cooldowns (`audio/event_policy.py` `_EVENT_COOLDOWNS`, seconds)

| Event | Cooldown |
| ----- | -------- |
| `opponent_approaching` / `opponent_passing` | 1.0 |
| `status_requested` | 0.75 |
| `turn_incoming` | 1.5 |
| `low_stamina` / `critical_stamina` | 5.0 |
| `obstacle_warning` | 1.2 |
| `obstacle_hit` | 1.0 |

---

## Tuning Constants

| Token | Value | Where |
| ----- | ----- | ----- |
| Default seed | `42` | `AppConfig.seed` |
| Real-time tick / frame rate | `60` Hz | `AppConfig` (pygame), `UI_FRAME_RATE` |
| Headless default tick | `4` Hz | `AppConfig.tick_hz` default |
| Max race seconds | `240.0` | `AppConfig.max_race_seconds` |
| Lane spacing | `1.15` m | `race_engine`, `obstacles` |
| Obstacle radar stages | `(120, 80, 45, 25, 12)` m | `RADAR_DISTANCES_M` |
| Obstacle warning range | `38.0` m | `ObstacleController.update` |
| Obstacle resolve range | `3.2` m | `ObstacleController.update` |
| Obstacle hit penalty | `1.25` s | `ObstacleController` |
| Opponent proximity gate | `12.0` m fwd / `1.4` m lateral | `_opponent_proximity_events` |
| Career length | data-driven (len of `championship.json`; default `3`) | `CAREER_LENGTH` / `_career_cap` |
| Career points | `10 / 7 / 5 / 3 / 1` | `points_for_rank` |
| Difficulty tiers | Rookie `0.97` / Pro `1.0` / Elite `1.04` | `DIFFICULTY_TIERS` (opponent_strength) |
| Max training level | `5` | `MAX_TRAINING_LEVEL` |
| Menu rows | `16` | `MENU_ROW_COUNT` |
| Coverage gate | `80%` | `pyproject.toml` |

---

## Filenames & Paths

| Token | Value |
| ----- | ----- |
| Content dir | `content/` (read-only JSON) |
| Save file | `save/progress.json` |
| Runtime log | `runtime_debug.log` (`app/runtime_log.py`) |
| Audio assets | `assets/`, `sfx/` (referenced by `sound_manifest.json`) |
| Race music | `assets/downloads/musicword-horsemen-242175.mp3` (`RACE_MUSIC`) |
| Menu music | `assets/downloads/dpstudiomusic-fun-farm-324289.mp3` (`MENU_MUSIC`) |

---

## Defaults (`AppConfig` / `GameProgress`)

| Field | Default |
| ----- | ------- |
| horse | `ember_stride` |
| track | `ashford_oval` |
| weather | `clear` |
| audio mix | `normal` |
| stable | `oak_lane` |

---

## Adding New Tokens (Future Work)

Where new entries slot in as the game grows (see [[architecture]] → Extension Points):

- **New content** (horse/track/weather/stable/rival): add to the matching `content/*.json` and update the table above. The menu selectors pick it up automatically — no UI code change.
- **New sound cue**: add the id to the manifest/catalog, then a rule in `event_cues._CUE_RULES` (preferred id + fallback) and a row in the Sound Cue IDs table here.
- **New spoken line**: add it via `AudioEventRouter` / `VoiceFeedbackController`, keep it one short sentence, and record it verbatim in Spoken Lines above.
- **New control**: wire the key in `ui/pygame_game.py`, update `HELP_TEXT`, and add it to [[ui-registry]] → In-Race Controls.
- **New tuning constant**: define it at its source module and add a row to Tuning Constants — never duplicate the literal elsewhere.
- **New audio mix profile**: extend `MIX_PROFILES` and the table above.

---

## Invariants

- Reuse the exact spoken-line strings and sound-cue ids above — do not paraphrase or rename.
- Content ids are fixed by `content/*.json`; never hardcode alternates in code beyond the documented defaults.
- Tuning constants live at their listed source — reference them, don't duplicate literals.
- Keep this table in sync when adding content, cues, controls, or constants.
