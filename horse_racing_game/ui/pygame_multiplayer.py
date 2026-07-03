from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pygame

from horse_racing_game.app.bootstrap import build_quick_race_services
from horse_racing_game.app.chat import ChatMessage, ChatSession
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.network import LockstepSession, LoopbackLockstepHub, RaceResultSummary, receive_race_result_summary, send_race_result_summary
from horse_racing_game.app.progress import record_online_race_summary
from horse_racing_game.app.runtime_log import write_runtime_log
from horse_racing_game.audio.pygame_music import play_music, set_music_volume, stop_music
from horse_racing_game.audio.voice_feedback import HELP_TEXT
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.input.events import KeyboardControlState, MULTIPLAYER_GUEST_SCHEME
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState
from horse_racing_game.ui.menu_models import MenuSelection
from horse_racing_game.ui.pygame_game import PygameGameResult


UI_FRAME_RATE = 60
MULTIPLAYER_MUSIC = "assets/downloads/musicword-horsemen-242175.mp3"


@dataclass(frozen=True)
class MultiplayerState:
    host_state: RaceState
    guest_state: RaceState
    ticks: int
    host_events: tuple[RaceEvent, ...]
    guest_events: tuple[RaceEvent, ...]


class PygameMultiplayerRaceGame:
    def __init__(
        self,
        config: AppConfig,
        services,
        project_root: Path | None = None,
        selection: MenuSelection | None = None,
        guest_horse_id: str | None = None,
        remote_session: LockstepSession | None = None,
    ) -> None:
        self._project_root = project_root or config.content_root.parent
        self._config = config
        self._selection = selection
        self._host_services = services
        guest_horse_id = guest_horse_id or self._pick_guest_horse_id(services.horses, config.player_horse_id)
        guest_config = AppConfig(
            content_root=config.content_root,
            track_id=config.track_id,
            player_horse_id=guest_horse_id,
            weather_id=config.weather_id,
            audio_mix_id=config.audio_mix_id,
            stable_id=config.stable_id,
            rival_stable_ids=dict(config.rival_stable_ids),
            horse_training_level=config.horse_training_level,
            opponent_strength=config.opponent_strength,
            seed=config.seed,
            tick_hz=config.tick_hz,
            max_race_seconds=config.max_race_seconds,
        )
        self._guest_services = build_quick_race_services(guest_config)
        self._host_input = KeyboardControlState()
        self._guest_input = KeyboardControlState(control_scheme=MULTIPLAYER_GUEST_SCHEME)
        self._messages: deque[str] = deque(maxlen=10)
        self._chat = ChatSession(("host", "guest"))
        self._chat_mode = "off"
        self._chat_restore_pause = False
        self._audio_duck_s = 0.0
        self._paused = False
        self._show_help = True
        self._next_action = "quit"
        self._remote_session = remote_session
        self._submitted_remote_ticks: set[int] = set()

    def run(self) -> PygameGameResult:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        write_runtime_log(self._project_root, "multiplayer: pygame.init")
        pygame.init()
        screen = pygame.display.set_mode((1240, 760), pygame.SHOWN)
        write_runtime_log(self._project_root, "multiplayer: set_mode 1240x760 ok")
        pygame.display.set_caption("Horse Racing Prototype V2 - Multiplayer Duel")
        play_music(self._project_root, MULTIPLAYER_MUSIC, 0.26)
        clock = pygame.time.Clock()
        fonts = _Fonts(
            title=pygame.font.Font(None, 44),
            body=pygame.font.Font(None, 28),
            small=pygame.font.Font(None, 22),
        )

        host_state, host_events = self._tick_initial(self._host_services)
        guest_state, guest_events = self._tick_initial(self._guest_services)
        host_commands: list[RaceCommand] = [RaceCommand(request_status=True)]
        self._append_messages("Multiplayer duel started.")
        lockstep = self._remote_session if self._remote_session is not None else LoopbackLockstepHub(("guest", "host"))
        tick_index = 0
        accumulator_s = 0.0
        running = True
        while running:
            frame_delta_s = clock.tick(UI_FRAME_RATE) / 1000.0
            accumulator_s = min(accumulator_s + frame_delta_s, 0.25)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    self._next_action = "quit"
                elif event.type == pygame.KEYDOWN:
                    if self._chat_mode != "off":
                        running, self._next_action = self._handle_chat_keydown(event, running, self._next_action)
                    else:
                        running, self._next_action = self._handle_keydown(event.key, running, self._next_action)
                elif event.type == pygame.KEYUP:
                    self._handle_keyup(event.key)

            self._host_input.advance(frame_delta_s)
            self._guest_input.advance(frame_delta_s)
            host_command = self._host_input.command()
            guest_command = self._guest_input.command()
            self._submit_lockstep_commands(lockstep, tick_index, host_command, guest_command)

            while not self._paused and accumulator_s >= self._config.tick_seconds:
                frame = lockstep.pop_ready_frame(tick_index)
                if frame is None:
                    break
                host_result = self._host_services.race_engine.tick(frame.command_for("host"), self._config.tick_seconds)
                guest_result = self._guest_services.race_engine.tick(frame.command_for("guest"), self._config.tick_seconds)
                host_state = host_result.state
                guest_state = guest_result.state
                host_commands.append(frame.command_for("host"))
                host_events.extend(host_result.events)
                guest_events.extend(guest_result.events)
                self._host_services.audio_engine.render_events(host_result.events)
                self._guest_services.audio_engine.render_events(guest_result.events)
                self._messages.appendleft(
                    f"Tick {tick_index + 1}: host rank {host_state.player().rank}, guest rank {guest_state.player().rank}"
                )
                tick_index += 1
                self._submitted_remote_ticks.discard(tick_index - 2)
                accumulator_s -= self._config.tick_seconds
                if host_state.is_finished and guest_state.is_finished:
                    running = False
                    self._next_action = "quit"
                    break
                if host_state.elapsed_s >= self._config.max_race_seconds:
                    running = False
                    self._next_action = "quit"
                    break

            self._draw(screen, fonts, host_state, guest_state, tick_index)
            pygame.display.flip()
            self._update_music_ducking(frame_delta_s)

        self._reconcile_remote_result(host_state, tick_index)
        stop_music(self._project_root)
        pygame.quit()
        return PygameGameResult(
            state=host_state,
            ticks=tick_index,
            events=tuple(host_events),
            next_action=self._next_action,
            commands=tuple(host_commands),
        )

    def _submit_lockstep_commands(
        self,
        lockstep: LockstepSession | LoopbackLockstepHub,
        tick_index: int,
        host_command: RaceCommand,
        guest_command: RaceCommand,
    ) -> None:
        if isinstance(lockstep, LockstepSession):
            lockstep.pump_inbound()
            if tick_index in self._submitted_remote_ticks:
                return
            if lockstep.local_peer_id == "host":
                lockstep.submit_local_command(tick_index, host_command)
            elif lockstep.local_peer_id == "guest":
                lockstep.submit_local_command(tick_index, guest_command)
            else:
                raise ValueError(f"unsupported multiplayer peer id: {lockstep.local_peer_id}")
            self._submitted_remote_ticks.add(tick_index)
            return
        lockstep.submit("host", tick_index, host_command)
        lockstep.submit("guest", tick_index, guest_command)

    def _tick_initial(self, services) -> tuple[RaceState, tuple[RaceEvent, ...]]:
        result = services.race_engine.tick(RaceCommand(request_status=True), self._config.tick_seconds)
        services.audio_engine.render_events(result.events)
        return result.state, result.events

    def _handle_keydown(self, key: int, running: bool, next_action: str) -> tuple[bool, str]:
        if key == pygame.K_c:
            self._enter_chat_mode("text")
            return running, next_action
        if key == pygame.K_v:
            self._enter_chat_mode("voice")
            return running, next_action
        if key in self._host_input.control_scheme.throttle_up or key in self._host_input.control_scheme.throttle_down or key in self._host_input.control_scheme.lateral_left or key in self._host_input.control_scheme.lateral_right or key in self._host_input.control_scheme.push or key in self._host_input.control_scheme.jump or key in self._host_input.control_scheme.duck or key in self._host_input.control_scheme.status:
            self._host_input.key_down(key)
        if key in self._guest_input.control_scheme.throttle_up or key in self._guest_input.control_scheme.throttle_down or key in self._guest_input.control_scheme.lateral_left or key in self._guest_input.control_scheme.lateral_right or key in self._guest_input.control_scheme.push or key in self._guest_input.control_scheme.jump or key in self._guest_input.control_scheme.duck or key in self._guest_input.control_scheme.status:
            self._guest_input.key_down(key)
        if key == pygame.K_ESCAPE:
            return False, "quit"
        if key == pygame.K_m:
            return False, "menu"
        if key == pygame.K_n:
            return False, "restart"
        if key == pygame.K_p:
            self._paused = not self._paused
        elif key == pygame.K_h or key == pygame.K_F1:
            self._show_help = not self._show_help
            self._messages.appendleft(HELP_TEXT)
        return running, next_action

    def _handle_chat_keydown(self, event: pygame.event.Event, running: bool, next_action: str) -> tuple[bool, str]:
        key = event.key
        if key == pygame.K_ESCAPE:
            self._leave_chat_mode()
            return running, next_action
        if key == pygame.K_TAB:
            self._chat.cycle_sender(1)
            self._messages.appendleft(f"Chat sender: {self._chat.composer.sender_label}")
            return running, next_action
        if self._chat_mode == "voice":
            if key in {pygame.K_LEFT, pygame.K_UP}:
                self._chat.cycle_voice_macro(-1)
                self._messages.appendleft(f"Voice line: {self._chat.composer.voice_macro}")
                return running, next_action
            if key in {pygame.K_RIGHT, pygame.K_DOWN}:
                self._chat.cycle_voice_macro(1)
                self._messages.appendleft(f"Voice line: {self._chat.composer.voice_macro}")
                return running, next_action
            if key == pygame.K_RETURN:
                self._send_chat_message(self._chat.submit_voice(), spoken_prefix="Voice")
                self._leave_chat_mode()
                return running, next_action
            if key == pygame.K_t:
                self._chat_mode = "text"
                self._messages.appendleft("Text chat mode.")
                return running, next_action
            if key == pygame.K_v:
                return running, next_action
        else:
            if key == pygame.K_RETURN:
                if self._chat.composer.draft.strip():
                    self._send_chat_message(self._chat.submit_text())
                self._leave_chat_mode()
                return running, next_action
            if key == pygame.K_BACKSPACE:
                self._chat.backspace()
                return running, next_action
            if key == pygame.K_v:
                self._chat_mode = "voice"
                self._messages.appendleft("Voice chat mode.")
                return running, next_action
            text = getattr(event, "unicode", "")
            if text and text.isprintable() and not text.isspace() or text == " ":
                self._chat.append_text(text)
                return running, next_action
        return running, next_action

    def _handle_keyup(self, key: int) -> None:
        if key in self._host_input.control_scheme.throttle_up or key in self._host_input.control_scheme.throttle_down or key in self._host_input.control_scheme.lateral_left or key in self._host_input.control_scheme.lateral_right or key in self._host_input.control_scheme.push or key in self._host_input.control_scheme.jump or key in self._host_input.control_scheme.duck or key in self._host_input.control_scheme.status:
            self._host_input.key_up(key)
        if key in self._guest_input.control_scheme.throttle_up or key in self._guest_input.control_scheme.throttle_down or key in self._guest_input.control_scheme.lateral_left or key in self._guest_input.control_scheme.lateral_right or key in self._guest_input.control_scheme.push or key in self._guest_input.control_scheme.jump or key in self._guest_input.control_scheme.duck or key in self._guest_input.control_scheme.status:
            self._guest_input.key_up(key)

    def _draw(self, screen: pygame.Surface, fonts: "_Fonts", host_state: RaceState, guest_state: RaceState, tick_index: int) -> None:
        screen.fill((18, 24, 30))
        self._draw_header(screen, fonts)
        self._draw_peer_panel(screen, fonts, host_state, (48, 122, 255), 44, "Host", self._host_input.describe(), self._host_services.track.length_m)
        self._draw_peer_panel(screen, fonts, guest_state, (250, 174, 76), 640, "Guest", self._guest_input.describe(), self._guest_services.track.length_m)
        self._draw_messages(screen, fonts)
        self._draw_chat(screen, fonts)
        self._draw_footer(screen, fonts, tick_index)
        if self._paused:
            self._draw_overlay(screen, fonts, "PAUSED")
        elif host_state.is_finished and guest_state.is_finished:
            self._draw_overlay(screen, fonts, "FINISHED")

    def _draw_header(self, screen: pygame.Surface, fonts: "_Fonts") -> None:
        screen.blit(fonts.title.render("Multiplayer Duel", True, (248, 240, 205)), (48, 26))
        screen.blit(fonts.small.render("Two lockstep peers. Host uses arrows/WASD. Guest uses TGFH/RYUO.", True, (156, 182, 194)), (50, 72))

    def _draw_peer_panel(self, screen: pygame.Surface, fonts: "_Fonts", state: RaceState, accent: tuple[int, int, int], x: int, label: str, input_text: str, track_length_m: float) -> None:
        panel = pygame.Rect(x, 110, 552, 390)
        pygame.draw.rect(screen, (31, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, accent, panel, width=2, border_radius=6)
        player = state.player()
        screen.blit(fonts.body.render(f"{label}: {player.horse_name}", True, (246, 238, 210)), (panel.left + 20, panel.top + 16))
        rows = (
            f"Rank {player.rank}/{len(state.runners)}",
            f"Distance {player.distance_m:.0f}/{track_length_m:.0f} m",
            f"Speed {player.speed_mps:.1f} m/s",
            f"Stamina {player.stamina:.0f}",
            f"Input {input_text}",
        )
        for index, row in enumerate(rows):
            screen.blit(fonts.small.render(row, True, (198, 216, 218)), (panel.left + 20, panel.top + 66 + index * 30))
        self._draw_progress(screen, panel.left + 20, panel.bottom - 54, panel.width - 40, player.distance_m / max(track_length_m, 1.0))

    def _draw_progress(self, screen: pygame.Surface, x: int, y: int, width: int, value: float) -> None:
        bounded = min(max(value, 0.0), 1.0)
        bar_rect = pygame.Rect(x, y, width, 14)
        pygame.draw.rect(screen, (14, 18, 22), bar_rect, border_radius=4)
        pygame.draw.rect(screen, (96, 190, 132), (bar_rect.left, bar_rect.top, int(bar_rect.width * bounded), 14), border_radius=4)
        pygame.draw.rect(screen, (164, 184, 172), bar_rect, width=1, border_radius=4)

    def _draw_messages(self, screen: pygame.Surface, fonts: "_Fonts") -> None:
        panel = pygame.Rect(48, 522, 620, 158)
        pygame.draw.rect(screen, (30, 34, 40), panel, border_radius=6)
        pygame.draw.rect(screen, (86, 98, 112), panel, width=2, border_radius=6)
        screen.blit(fonts.body.render("Session Log", True, (244, 246, 238)), (panel.left + 18, panel.top + 14))
        for index, message in enumerate(self._messages):
            screen.blit(fonts.small.render(message, True, (210, 218, 218)), (panel.left + 18, panel.top + 52 + index * 20))

    def _draw_chat(self, screen: pygame.Surface, fonts: "_Fonts") -> None:
        panel = pygame.Rect(684, 522, 508, 158)
        pygame.draw.rect(screen, (28, 34, 44), panel, border_radius=6)
        pygame.draw.rect(screen, (94, 112, 130), panel, width=2, border_radius=6)
        mode = "TEXT" if self._chat_mode == "text" else "VOICE" if self._chat_mode == "voice" else "OFF"
        header = f"Chat [{mode}] {self._chat.composer.sender_label}"
        screen.blit(fonts.body.render(header, True, (244, 246, 238)), (panel.left + 16, panel.top + 14))
        if self._chat_mode == "voice":
            hint = f"Voice line: {self._chat.composer.voice_macro}"
            draft = "Up/Down voice | Left/Right sender | Enter send | Esc exit"
        elif self._chat_mode == "text":
            hint = f"> {self._chat.composer.draft}"
            draft = "Type message | Enter send | Tab sender | Esc exit"
        else:
            hint = "C text chat | V voice chat"
            draft = "Chat is idle"
        screen.blit(fonts.small.render(draft, True, (170, 194, 204)), (panel.left + 16, panel.top + 52))
        screen.blit(fonts.small.render(hint, True, (240, 220, 132)), (panel.left + 16, panel.top + 76))
        for index, message in enumerate(self._chat.messages[:2]):
            label = f"{message.sender_label}: {message.body}"
            if message.kind == "voice":
                label = f"{message.sender_label} [voice]: {message.body}"
            screen.blit(fonts.small.render(label, True, (210, 224, 226)), (panel.left + 16, panel.top + 102 + index * 18))

    def _draw_footer(self, screen: pygame.Surface, fonts: "_Fonts", tick_index: int) -> None:
        footer = pygame.Rect(48, 692, 1144, 40)
        pygame.draw.rect(screen, (26, 30, 36), footer, border_radius=6)
        pygame.draw.rect(screen, (88, 96, 108), footer, width=2, border_radius=6)
        text = f"Tick {tick_index} | P pause | H help | M menu | N restart | Esc quit"
        screen.blit(fonts.small.render(text, True, (245, 220, 130)), (footer.left + 18, footer.top + 11))

    def _draw_overlay(self, screen: pygame.Surface, fonts: "_Fonts", text: str) -> None:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 86))
        screen.blit(overlay, (0, 0))
        label = fonts.title.render(text, True, (255, 240, 160))
        screen.blit(label, label.get_rect(center=(620, 42)))

    def _update_music_ducking(self, delta_s: float) -> None:
        if self._audio_duck_s > 0.0:
            self._audio_duck_s = max(0.0, self._audio_duck_s - delta_s)
            set_music_volume(self._project_root, 0.18)
        else:
            set_music_volume(self._project_root, 0.26)

    def _append_messages(self, message: str) -> None:
        self._messages.appendleft(message)

    def _enter_chat_mode(self, mode: str) -> None:
        if self._chat_mode == "off":
            self._chat_restore_pause = self._paused
        self._paused = True
        self._chat_mode = mode
        pygame.key.start_text_input()
        self._messages.appendleft(f"{mode.title()} chat mode.")

    def _leave_chat_mode(self) -> None:
        self._chat_mode = "off"
        self._paused = self._chat_restore_pause
        pygame.key.stop_text_input()

    def _send_chat_message(self, message: ChatMessage, spoken_prefix: str = "Chat") -> None:
        self._chat.add_message(message)
        line = f"{message.sender_label}: {message.body}"
        self._messages.appendleft(line)
        self._host_services.audio_backend.speak(f"{spoken_prefix} {line}", 75)

    def _pick_guest_horse_id(self, horses, host_horse_id: str) -> str:
        playable = [horse.horse_id for horse in horses if getattr(horse, "role", "") == "player" and horse.horse_id != host_horse_id]
        return playable[0] if playable else host_horse_id

    def _reconcile_remote_result(self, host_state: RaceState, ticks: int) -> None:
        if self._remote_session is None:
            return
        transport = self._remote_session.transport
        raw_socket = getattr(transport, "_socket", None)
        if raw_socket is None:
            return
        summary = RaceResultSummary(
            race_id=f"{self._config.seed}:{self._config.track_id}",
            peer_id=self._remote_session.local_peer_id,
            finished=host_state.is_finished,
            rank=host_state.player().rank,
            ticks=ticks,
            distance_m=host_state.player().distance_m,
        )
        try:
            if self._remote_session.local_peer_id == "host":
                send_race_result_summary(raw_socket, summary)
                remote_summary = receive_race_result_summary(raw_socket, 5.0)
            else:
                remote_summary = receive_race_result_summary(raw_socket, 5.0)
                send_race_result_summary(raw_socket, summary)
        except Exception as error:
            self._messages.appendleft(f"Result sync failed: {error}")
            return
        if remote_summary.race_id != summary.race_id or remote_summary.rank != summary.rank or remote_summary.finished != summary.finished:
            self._messages.appendleft(
                f"Result mismatch: local rank {summary.rank}, remote rank {remote_summary.rank}"
            )
        else:
            self._messages.appendleft(f"Result synced: rank {summary.rank}, ticks {summary.ticks}")
            if self._remote_session.local_peer_id == "host":
                record_online_race_summary(
                    self._project_root,
                    {
                        "race_id": summary.race_id,
                        "peer_id": summary.peer_id,
                        "finished": summary.finished,
                        "rank": summary.rank,
                        "ticks": summary.ticks,
                        "distance_m": summary.distance_m,
                        "remote_peer_id": remote_summary.peer_id,
                        "remote_rank": remote_summary.rank,
                        "remote_finished": remote_summary.finished,
                        "remote_ticks": remote_summary.ticks,
                        "remote_distance_m": remote_summary.distance_m,
                    },
                )


@dataclass(frozen=True)
class _Fonts:
    title: pygame.font.Font
    body: pygame.font.Font
    small: pygame.font.Font
