import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pygame

from horse_racing_game.app.bootstrap import GameServices, build_quick_race_services
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.runtime_log import write_runtime_log
from horse_racing_game.audio.continuous_race_audio import ContinuousRaceAudio
from horse_racing_game.audio.mix_profile import mix_profile_by_id
from horse_racing_game.audio.opponent_spatial_audio import OpponentSpatialAudio
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.audio.pygame_music import play_music, set_music_volume, stop_music
from horse_racing_game.audio.voice_feedback import HELP_TEXT, VoiceFeedbackController
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.input.events import KeyboardControlState
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState, RunnerState
from horse_racing_game.ui.obstacles import ObstacleController, TrackObstacle, load_track_obstacles


@dataclass(frozen=True)
class PygameGameResult:
    state: RaceState
    ticks: int
    events: tuple[RaceEvent, ...]
    next_action: str = "quit"
    commands: tuple[RaceCommand, ...] = ()


UI_FRAME_RATE = 60
VISIBLE_OBSTACLE_DISTANCE_M = 260.0
RACE_MUSIC = "assets/downloads/musicword-horsemen-242175.mp3"
TUTORIAL_MESSAGES = (
    (0.0, "Tutorial started. Use up and down arrows, W and S, or Z and S, to change pace."),
    (4.0, "Pacing by ear matters. Cruising means efficient speed; overpushing means ease off before stamina collapses."),
    (8.0, "Stamina is heard in breathing. Heavy breath means ease off until recovery cues settle, then build pace again."),
    (12.0, "Rivals are spatial. A rival louder in the left ear is on your left; right ear means right side."),
    (16.0, "Turn warnings use rail sweeps. A left rail sweep means prepare to guide left; a right sweep means guide right."),
    (20.0, "At the turn apex, small steering taps are safer than holding hard into the rail."),
    (24.0, "Obstacle radar pings get faster as hazards approach. The warning names the lane and required action."),
    (28.0, "For dodge obstacles, change lanes early and listen for the near miss or clean pass confirmation."),
    (32.0, "For jump timing, press J when the obstacle warning is close, then listen for takeoff and confirmation."),
    (36.0, "For duck timing, press K or Control on low branches, banners, gates, or ropes."),
    (40.0, "Final stretch has a crowd rise. Save a push for that cue instead of spending all stamina early."),
    (44.0, "Press Tab or Enter any time to hear rank, distance, stamina, and weather."),
    (48.0, "Replay controls use pause, step, final stretch, and key moment jumps to review the race by audio."),
    (52.0, "On mobile, drag for pace and steering, swipe up to jump, swipe down to duck, and long press for status."),
    (56.0, "M returns to the menu. N restarts. Escape quits."),
)


class PygameRaceGame:
    def __init__(
        self,
        config: AppConfig,
        services: GameServices,
        project_root: Path | None = None,
        tutorial_mode: bool = False,
        training_mode: bool = False,
        intro_message: str | None = None,
    ) -> None:
        self._project_root = project_root or config.content_root.parent
        self._config = config
        self._services = services
        self._tutorial_mode = tutorial_mode
        self._training_mode = training_mode
        self._intro_message = intro_message
        self._tutorial_announced: set[int] = set()
        self._rival_announced: set[tuple[str, str]] = set()
        self._mix_profile = mix_profile_by_id(config.audio_mix_id)
        self._messages: deque[str] = deque(maxlen=8)
        self._events: list[RaceEvent] = []
        self._voice_feedback = VoiceFeedbackController(services.audio_backend)
        self._paused = False
        self._show_help = self._mix_profile.show_help_by_default
        self._last_input_text = "No input"
        self._held_keys: set[int] = set()
        self._input_state = KeyboardControlState(held_keys=self._held_keys)
        self._jump_buffer_s = 0.0
        self._duck_buffer_s = 0.0
        self._ambient_sound_id: str | None = None
        self._continuous_audio = ContinuousRaceAudio(
            services.audio_backend,
            services.sound_catalog,
            services.track,
            services.weather,
        )
        self._opponent_spatial_audio = OpponentSpatialAudio(
            services.audio_backend,
            services.sound_catalog,
            services.track,
            services.weather,
        )
        self._audio_duck_s = 0.0
        self._obstacles = ObstacleController(
            load_track_obstacles(config.content_root / "obstacles.json", services.track.track_id)
        )

    def run(self) -> PygameGameResult:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        write_runtime_log(self._project_root, "game: pygame.init")
        pygame.init()
        screen = pygame.display.set_mode((1180, 720), pygame.SHOWN)
        write_runtime_log(self._project_root, "game: set_mode 1180x720 ok")
        pygame.display.set_caption("Horse Racing Prototype V2 - Obstacles + 3D Audio")
        play_music(self._project_root, RACE_MUSIC, self._mix_profile.music_volume)
        self._play_countdown()
        self._play_ambient()
        clock = pygame.time.Clock()
        fonts = _Fonts(
            title=pygame.font.Font(None, 44),
            body=pygame.font.Font(None, 28),
            small=pygame.font.Font(None, 22),
        )

        recorded_commands: list[RaceCommand] = []
        initial_command = RaceCommand(request_status=True)
        recorded_commands.append(initial_command)
        initial_tick = self._services.race_engine.tick(initial_command, self._config.tick_seconds)
        state = initial_tick.state
        self._record_events(initial_tick.events, state)
        self._announce_intro()
        self._update_tutorial(state.elapsed_s)

        running = True
        next_action = "quit"
        ticks = 1
        accumulator_s = 0.0
        while running:
            frame_delta_s = clock.tick(UI_FRAME_RATE) / 1000.0
            accumulator_s = min(accumulator_s + frame_delta_s, 0.25)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running, next_action = self._handle_keydown(event.key, running, next_action)
                elif event.type == pygame.KEYUP:
                    self._handle_keyup(event.key)
            command = self._poll_command()

            while not self._paused and not state.is_finished and accumulator_s >= self._config.tick_seconds:
                engine_command = self._apply_obstacle_penalty(command)
                recorded_commands.append(engine_command)
                tick_result = self._services.race_engine.tick(
                    engine_command,
                    self._config.tick_seconds,
                )
                state = tick_result.state
                self._record_events(tick_result.events, state)
                self._record_events(
                    self._obstacles.update(state.player(), state.elapsed_s, self._config.tick_seconds, command),
                    state,
                )
                self._update_tutorial(state.elapsed_s)
                ticks += 1
                accumulator_s -= self._config.tick_seconds
                if state.elapsed_s >= self._config.max_race_seconds:
                    running = False
                    break

            self._draw(screen, fonts, state)
            pygame.display.flip()
            self._tick_action_buffers(frame_delta_s)
            self._update_continuous_audio(state, frame_delta_s)

        self._continuous_audio.stop()
        self._opponent_spatial_audio.stop()
        self._stop_ambient()
        stop_music(self._project_root)
        pygame.quit()
        return PygameGameResult(
            state=state,
            ticks=ticks,
            events=tuple(self._events),
            next_action=next_action,
            commands=tuple(recorded_commands),
        )

    def _record_events(self, events: tuple[RaceEvent, ...], state: RaceState) -> None:
        if not events:
            return
        self._events.extend(events)
        self._services.audio_engine.render_events(events)
        self._duck_audio_for_priority_events(events)
        self._speak_rival_events(events)
        self._voice_feedback.observe_events(events, state)
        self._append_event_messages(events)

    def _speak_rival_events(self, events: tuple[RaceEvent, ...]) -> None:
        rivals = {rival.horse_id: rival for rival in self._services.rivals}
        for event in events:
            if event.event_type not in {"opponent_approaching", "opponent_passing"}:
                continue
            rival = rivals.get(event.subject_id or "")
            if rival is None:
                continue
            key = (rival.horse_id, event.event_type)
            if key in self._rival_announced:
                continue
            self._rival_announced.add(key)
            line = rival.passing_line if event.event_type == "opponent_passing" else rival.approach_line
            self._services.audio_backend.speak(line, event.priority + 5)
            self._messages.appendleft(line)

    def _announce_intro(self) -> None:
        if not self._intro_message:
            return
        self._services.audio_backend.speak(self._intro_message, 100)
        self._messages.appendleft(self._intro_message)

    def _play_countdown(self) -> None:
        if self._services.sound_catalog.get("race_countdown_three_beeps") is not None:
            self._services.audio_backend.play_2d("race_countdown_three_beeps", 0.72)

    def _play_ambient(self) -> None:
        if self._training_mode:
            return
        sound_id = self._services.weather.ambient_sound_id
        if sound_id is None:
            return
        asset = self._services.sound_catalog.get(sound_id)
        if asset is not None and asset.loop:
            self._services.audio_backend.play_loop(sound_id, self._mix_profile.ambient_volume)
            self._ambient_sound_id = sound_id
            return
        self._services.audio_backend.play_2d(sound_id, self._mix_profile.ambient_volume)

    def _stop_ambient(self) -> None:
        if self._ambient_sound_id is None:
            return
        self._services.audio_backend.stop_sound(self._ambient_sound_id)
        self._ambient_sound_id = None

    def _update_tutorial(self, elapsed_s: float) -> None:
        if not self._tutorial_mode or not self._mix_profile.tutorial_voice:
            return
        for index, item in enumerate(TUTORIAL_MESSAGES):
            trigger_s, message = item
            if elapsed_s >= trigger_s and index not in self._tutorial_announced:
                self._tutorial_announced.add(index)
                self._services.audio_backend.speak(message, 95)
                self._messages.appendleft(message)

    def _poll_command(self) -> RaceCommand:
        input_state = getattr(self, "_input_state", None)
        if input_state is None:
            keys = self._pressed_keys()
            self._last_input_text = self._input_text(keys)
            return RaceCommand(
                throttle_delta=self._axis(
                    self._any_key_down(keys, pygame.K_UP, pygame.K_w, pygame.K_z),
                    self._any_key_down(keys, pygame.K_DOWN, pygame.K_s),
                ),
                lateral_delta=self._axis(
                    self._any_key_down(keys, pygame.K_RIGHT, pygame.K_d),
                    self._any_key_down(keys, pygame.K_LEFT, pygame.K_a, pygame.K_q),
                ),
                push_requested=self._any_key_down(keys, pygame.K_SPACE),
                jump_requested=self._any_key_down(keys, pygame.K_j) or self._jump_buffer_s > 0.0,
                duck_requested=self._any_key_down(keys, pygame.K_k, pygame.K_LCTRL, pygame.K_RCTRL) or self._duck_buffer_s > 0.0,
                request_status=self._any_key_down(keys, pygame.K_TAB, pygame.K_RETURN),
            )
        self._last_input_text = input_state.describe()
        command = input_state.command()
        return RaceCommand(
            throttle_delta=command.throttle_delta,
            lateral_delta=command.lateral_delta,
            push_requested=command.push_requested,
            jump_requested=command.jump_requested or self._jump_buffer_s > 0.0,
            duck_requested=command.duck_requested or self._duck_buffer_s > 0.0,
            request_status=command.request_status,
        )

    def _handle_keydown(self, key: int, running: bool, next_action: str) -> tuple[bool, str]:
        self._held_keys.add(key)
        input_state = getattr(self, "_input_state", None)
        if input_state is not None:
            input_state.key_down(key)
        if key == pygame.K_ESCAPE:
            return False, "quit"
        if key == pygame.K_m:
            return False, "menu"
        if key == pygame.K_n:
            return False, "restart"
        if key == pygame.K_SPACE:
            self._play_action_sound("horse_push_surge", 0.64)
        if key == pygame.K_j:
            self._jump_buffer_s = 0.35
            self._play_action_sound("horse_jump_takeoff", 0.62)
        if key in {pygame.K_k, pygame.K_LCTRL, pygame.K_RCTRL}:
            self._duck_buffer_s = 0.35
            self._play_action_sound("horse_lane_change_hoof_sweep", 0.46)
        if key == pygame.K_p:
            self._paused = not self._paused
        elif key == pygame.K_h or key == pygame.K_F1:
            self._show_help = not self._show_help
            self._services.audio_backend.speak(HELP_TEXT, 90)
            self._messages.appendleft(HELP_TEXT)
        elif key == pygame.K_r:
            self._voice_feedback.repeat_last()
            self._messages.appendleft("Repeated last spoken message")
        return running, next_action

    def _play_action_sound(self, sound_id: str, volume: float) -> None:
        services = getattr(self, "_services", None)
        if services is None:
            return
        if services.sound_catalog.get(sound_id) is None:
            return
        services.audio_backend.play_2d(sound_id, volume)

    def _handle_keyup(self, key: int) -> None:
        self._held_keys.discard(key)
        input_state = getattr(self, "_input_state", None)
        if input_state is not None:
            input_state.key_up(key)

    def _tick_action_buffers(self, delta_s: float) -> None:
        input_state = getattr(self, "_input_state", None)
        if input_state is not None:
            input_state.advance(delta_s)
        self._jump_buffer_s = max(0.0, self._jump_buffer_s - delta_s)
        self._duck_buffer_s = max(0.0, self._duck_buffer_s - delta_s)

    def _duck_audio_for_priority_events(self, events: tuple[RaceEvent, ...]) -> None:
        for event in events:
            if event.event_type in {"obstacle_warning", "obstacle_hit", "finish_line_crossed"}:
                self._audio_duck_s = max(self._audio_duck_s, 1.25)
            elif event.event_type == "obstacle_radar" and float(event.data.get("forward_m", 999.0)) <= 25.0:
                self._audio_duck_s = max(self._audio_duck_s, 0.65)

    def _update_continuous_audio(self, state: RaceState, delta_s: float) -> None:
        self._update_music_ducking(delta_s)
        self._continuous_audio.update(state.player(), state.is_finished)
        opponent_audio = getattr(self, "_opponent_spatial_audio", None)
        if opponent_audio is not None:
            opponent_audio.update(state)

    def _update_music_ducking(self, delta_s: float) -> None:
        if self._audio_duck_s > 0.0:
            self._audio_duck_s = max(0.0, self._audio_duck_s - delta_s)
            set_music_volume(self._project_root, self._mix_profile.music_volume * 0.38)
        else:
            set_music_volume(self._project_root, self._mix_profile.music_volume)

    def _append_event_messages(self, events: tuple[RaceEvent, ...]) -> None:
        for event in events:
            message = self._message_for_event(event)
            if message is not None:
                self._messages.appendleft(message)

    def _message_for_event(self, event: RaceEvent) -> str | None:
        if event.event_type == "race_started":
            return "Race started"
        if event.event_type == "status_requested":
            return (
                f"Rank {event.data.get('rank', '?')} | "
                f"{event.data.get('distance_remaining_m', '?')}m left | "
                f"Stamina {event.data.get('stamina', '?')}"
            )
        if event.event_type in {"turn_incoming", "turn_entry"}:
            return f"Turn entry: {event.data.get('direction', 'ahead')}"
        if event.event_type == "turn_exit":
            return f"Turn exit: {event.data.get('direction', 'ahead')}"
        if event.event_type == "turn_apex":
            return f"Turn apex: {event.data.get('direction', 'ahead')}"
        if event.event_type == "turn_rail_inside":
            return f"Inside rail: {event.data.get('direction', 'ahead')}"
        if event.event_type == "turn_rail_outside":
            return f"Outside rail: {event.data.get('direction', 'ahead')}"
        if event.event_type == "turn_too_tight":
            return f"Too tight: {event.data.get('direction', 'ahead')}"
        if event.event_type == "turn_too_wide":
            return f"Too wide: {event.data.get('direction', 'ahead')}"
        if event.event_type == "pace_cruising":
            return "Cruising"
        if event.event_type == "pace_overpushing":
            return "Overpushing"
        if event.event_type == "pace_recovering":
            return "Recovering"
        if event.event_type == "pace_wasting_stamina":
            return "Wasting stamina"
        if event.event_type in {"opponent_approaching", "opponent_passing"}:
            return f"{event.data.get('horse_name', 'Opponent')} {event.event_type.replace('_', ' ')}"
        if event.event_type == "obstacle_warning":
            lane_text = self._lane_text(event)
            action = self._action_text(event.data.get("required_action"))
            return f"Obstacle ahead: {event.data.get('label', 'Obstacle')} {lane_text} - {action}"
        if event.event_type == "obstacle_hit":
            return f"Hit obstacle: {event.data.get('label', 'Obstacle')} - speed penalty"
        if event.event_type == "obstacle_near_miss":
            return f"Near miss: {event.data.get('label', 'Obstacle')}"
        if event.event_type == "obstacle_avoided":
            resolution = self._action_text(event.data.get("resolution"))
            quality = event.data.get("timing_quality")
            prefix = f"{str(quality).title()} " if quality in {"perfect", "good", "late"} else ""
            return f"{prefix}{resolution} confirmed: {event.data.get('label', 'Obstacle')}"
        if event.event_type == "final_stretch":
            return "Final stretch"
        if event.event_type == "finish_line_crossed":
            return f"Finished rank {event.data.get('rank', '?')}"
        if event.event_type == "race_finished":
            return "Race finished"
        if event.event_type in {"low_stamina", "critical_stamina"}:
            return event.event_type.replace("_", " ").title()
        return None

    def _lane_text(self, event: RaceEvent) -> str:
        lane = event.data.get("lane")
        if isinstance(lane, int):
            return f"lane {lane + 1}"
        return ""

    def _action_text(self, action: object) -> str:
        if action == "jump":
            return "jump"
        if action == "duck":
            return "duck"
        return "dodge"

    def _draw(self, screen: pygame.Surface, fonts: "_Fonts", state: RaceState) -> None:
        screen.fill((22, 28, 34))
        self._draw_track(screen, fonts, state)
        self._draw_hud(screen, fonts, state)
        self._draw_messages(screen, fonts)
        self._draw_text(screen, fonts.small, f"Input: {self._last_input_text}", (44, 574), (245, 220, 130))
        if self._show_help:
            self._draw_help(screen, fonts)
        if self._paused:
            self._draw_overlay(screen, fonts, "PAUSED")
        elif state.is_finished:
            self._draw_overlay(screen, fonts, "FINISHED")

    def _draw_track(self, screen: pygame.Surface, fonts: "_Fonts", state: RaceState) -> None:
        track_rect = pygame.Rect(42, 96, 800, 470)
        pygame.draw.rect(screen, (42, 74, 54), track_rect, border_radius=6)
        pygame.draw.rect(screen, (225, 225, 215), track_rect, width=3, border_radius=6)
        lane_height = track_rect.height / self._services.track.lanes
        for lane_index in range(self._services.track.lanes + 1):
            y = int(track_rect.top + lane_index * lane_height)
            pygame.draw.line(screen, (160, 178, 150), (track_rect.left, y), (track_rect.right, y), 1)

        finish_x = self._distance_to_x(self._services.track.final_stretch_start_m, track_rect)
        pygame.draw.line(screen, (240, 205, 78), (finish_x, track_rect.top), (finish_x, track_rect.bottom), 3)
        finish_label = fonts.small.render("final stretch", True, (245, 230, 170))
        screen.blit(finish_label, (finish_x - 42, track_rect.top - 24))

        self._draw_obstacles(screen, fonts, state, track_rect, lane_height)
        for runner in sorted(state.runners, key=lambda item: item.rank, reverse=True):
            self._draw_runner(screen, fonts, runner, track_rect, lane_height)

    def _draw_obstacles(
        self,
        screen: pygame.Surface,
        fonts: "_Fonts",
        state: RaceState,
        track_rect: pygame.Rect,
        lane_height: float,
    ) -> None:
        player = state.player()
        for obstacle in self._obstacles.visible_near(player, VISIBLE_OBSTACLE_DISTANCE_M):
            x = self._distance_to_x(obstacle.distance_m, track_rect)
            y = int(track_rect.top + lane_height * (obstacle.lane + 0.5))
            self._draw_obstacle_marker(screen, x, y, obstacle)
            if abs(obstacle.distance_m - player.distance_m) <= 70.0:
                label = fonts.small.render(f"{obstacle.kind}/{obstacle.required_action}", True, (246, 236, 210))
                screen.blit(label, (min(x + 12, track_rect.right - 72), y - 24))

    def _draw_obstacle_marker(self, screen: pygame.Surface, x: int, y: int, obstacle: TrackObstacle) -> None:
        points = ((x, y - 13), (x + 13, y), (x, y + 13), (x - 13, y))
        pygame.draw.polygon(screen, (10, 12, 14), points)
        inner = ((x, y - 10), (x + 10, y), (x, y + 10), (x - 10, y))
        pygame.draw.polygon(screen, self._obstacle_color(obstacle.kind), inner)

    def _draw_runner(
        self,
        screen: pygame.Surface,
        fonts: "_Fonts",
        runner: RunnerState,
        track_rect: pygame.Rect,
        lane_height: float,
    ) -> None:
        x = self._distance_to_x(runner.distance_m, track_rect)
        y = int(track_rect.top + lane_height * (runner.lateral_position / 1.15 + 0.5))
        color = (245, 214, 90) if runner.is_player else (108, 172, 232)
        pygame.draw.circle(screen, (12, 18, 20), (x, y), 15)
        pygame.draw.circle(screen, color, (x, y), 12)
        label = fonts.small.render(str(runner.rank), True, (5, 8, 10))
        screen.blit(label, label.get_rect(center=(x, y)))
        name = fonts.small.render(runner.horse_name, True, (230, 236, 232))
        screen.blit(name, (min(x + 18, track_rect.right - 118), y - 10))

    def _draw_hud(self, screen: pygame.Surface, fonts: "_Fonts", state: RaceState) -> None:
        player = state.player()
        panel = pygame.Rect(872, 78, 260, 330)
        pygame.draw.rect(screen, (33, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, (90, 110, 124), panel, width=2, border_radius=6)
        self._draw_text(screen, fonts.title, "Race HUD V2", (panel.left + 20, panel.top + 18), (244, 246, 238))
        penalty = "YES" if self._obstacles.has_penalty else "no"
        rows = (
            f"Track: {self._services.track.name}",
            f"Weather: {self._services.weather.name}",
            f"Audio: {self._mix_profile.name}",
            f"Horse: {player.horse_name}",
            f"Rank: {player.rank}/{len(state.runners)}",
            f"Distance: {player.distance_m:.0f}/{self._services.track.length_m:.0f}m",
            f"Speed: {player.speed_mps:.1f} m/s",
            f"Stamina: {player.stamina:.0f}",
            f"Stability: {player.stability:.2f}",
            f"Penalty: {penalty}",
        )
        for index, row in enumerate(rows):
            self._draw_text(screen, fonts.small, row, (panel.left + 20, panel.top + 72 + index * 24), (215, 226, 220))
        self._draw_bar(screen, pygame.Rect(panel.left + 20, panel.bottom - 30, 214, 14), player.stamina / 100.0)

    def _draw_messages(self, screen: pygame.Surface, fonts: "_Fonts") -> None:
        panel = pygame.Rect(872, 430, 260, 214)
        pygame.draw.rect(screen, (30, 34, 40), panel, border_radius=6)
        pygame.draw.rect(screen, (86, 98, 112), panel, width=2, border_radius=6)
        self._draw_text(screen, fonts.body, "Event Log", (panel.left + 18, panel.top + 14), (244, 246, 238))
        for index, message in enumerate(self._messages):
            self._draw_text(screen, fonts.small, message, (panel.left + 18, panel.top + 52 + index * 22), (210, 218, 218))

    def _draw_help(self, screen: pygame.Surface, fonts: "_Fonts") -> None:
        help_rect = pygame.Rect(42, 600, 800, 76)
        pygame.draw.rect(screen, (34, 42, 52), help_rect, border_radius=6)
        pygame.draw.rect(screen, (95, 112, 130), help_rect, width=2, border_radius=6)
        self._draw_text(
            screen,
            fonts.body,
            "Arrows/ZQSD/WASD control horse | Space push | J jump | K/Ctrl duck | Tab/Enter status | R repeat | M menu | Esc quit",
            (help_rect.left + 18, help_rect.top + 25),
            (245, 220, 130),
        )

    def _draw_overlay(self, screen: pygame.Surface, fonts: "_Fonts", text: str) -> None:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 86))
        screen.blit(overlay, (0, 0))
        label = fonts.title.render(text, True, (255, 240, 160))
        screen.blit(label, label.get_rect(center=(590, 55)))
        hint = fonts.body.render("M: menu | N: restart | Esc: quit", True, (245, 220, 130))
        screen.blit(hint, hint.get_rect(center=(590, 92)))

    def _draw_bar(self, screen: pygame.Surface, rect: pygame.Rect, value: float) -> None:
        bounded = min(max(value, 0.0), 1.0)
        pygame.draw.rect(screen, (15, 18, 20), rect, border_radius=4)
        fill = pygame.Rect(rect.left, rect.top, int(rect.width * bounded), rect.height)
        pygame.draw.rect(screen, (82, 194, 126), fill, border_radius=4)
        pygame.draw.rect(screen, (190, 206, 190), rect, width=1, border_radius=4)

    def _draw_text(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        position: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        screen.blit(font.render(text, True, color), position)

    def _apply_obstacle_penalty(self, command: RaceCommand) -> RaceCommand:
        if not self._obstacles.has_penalty:
            return command
        return RaceCommand(
            throttle_delta=min(command.throttle_delta, self._obstacles.penalty_throttle_cap),
            lateral_delta=command.lateral_delta,
            push_requested=False,
            jump_requested=command.jump_requested,
            duck_requested=command.duck_requested,
            request_status=command.request_status,
        )

    def _obstacle_color(self, kind: str) -> tuple[int, int, int]:
        if kind in {"mud", "puddle"}:
            return (70, 118, 154)
        if kind in {"rail", "barrel"}:
            return (210, 82, 72)
        if kind in {"low_branch", "low_banner", "low_gate", "low_rope"}:
            return (166, 112, 226)
        return (226, 168, 62)

    def _input_text(self, keys) -> str:
        active: list[str] = []
        if self._any_key_down(keys, pygame.K_UP, pygame.K_w, pygame.K_z):
            active.append("up")
        if self._any_key_down(keys, pygame.K_DOWN, pygame.K_s):
            active.append("down")
        if self._any_key_down(keys, pygame.K_LEFT, pygame.K_a, pygame.K_q):
            active.append("left")
        if self._any_key_down(keys, pygame.K_RIGHT, pygame.K_d):
            active.append("right")
        if self._any_key_down(keys, pygame.K_SPACE):
            active.append("push")
        if self._any_key_down(keys, pygame.K_j) or self._jump_buffer_s > 0.0:
            active.append("jump")
        if self._any_key_down(keys, pygame.K_k, pygame.K_LCTRL, pygame.K_RCTRL) or self._duck_buffer_s > 0.0:
            active.append("duck")
        if self._any_key_down(keys, pygame.K_TAB, pygame.K_RETURN):
            active.append("status")
        if not active:
            return "No input"
        return ", ".join(active)

    def _distance_to_x(self, distance_m: float, track_rect: pygame.Rect) -> int:
        progress = min(max(distance_m / self._services.track.length_m, 0.0), 1.0)
        return int(track_rect.left + progress * track_rect.width)

    def _axis(self, positive: bool, negative: bool) -> float:
        value = 0.0
        if positive:
            value += 1.0
        if negative:
            value -= 1.0
        return value

    def _any_key_down(self, keys, *key_codes: int) -> bool:
        for key_code in key_codes:
            if key_code in self._held_keys:
                return True
            if keys[key_code]:
                return True
        return False

    def _pressed_keys(self):
        try:
            return pygame.key.get_pressed()
        except pygame.error:
            return _NoPressedKeys()


class _NoPressedKeys:
    def __getitem__(self, key_code: int) -> bool:
        return False


@dataclass(frozen=True)
class _Fonts:
    title: pygame.font.Font
    body: pygame.font.Font
    small: pygame.font.Font


def build_pygame_services(config: AppConfig) -> GameServices:
    catalog_services = build_quick_race_services(config)
    audio_backend = PygameAudioBackend(config.content_root.parent, catalog_services.sound_catalog)
    return build_quick_race_services(config, audio_backend)









