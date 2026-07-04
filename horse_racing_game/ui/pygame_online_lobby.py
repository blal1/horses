from __future__ import annotations

import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pygame

from horse_racing_game.app.network import (
    LockstepSession,
    LockstepTransport,
    LobbyHandshake,
    connect_socket_transport,
    host_socket_transport,
)
from horse_racing_game.app.progress import GameProgress, load_progress, record_online_lobby_settings
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog


DEFAULT_ONLINE_PORT = 45678
LOBBY_ROWS = 8


@dataclass(frozen=True)
class OnlineLobbyResult:
    mode: str
    session: LockstepSession | None = None

    @classmethod
    def local(cls) -> "OnlineLobbyResult":
        return cls("local")

    @classmethod
    def start(cls, session: LockstepSession) -> "OnlineLobbyResult":
        return cls("online", session)

    @classmethod
    def menu(cls) -> "OnlineLobbyResult":
        return cls("menu")

    @classmethod
    def quit(cls) -> "OnlineLobbyResult":
        return cls("quit")


class PygameOnlineLobbyScreen:
    def __init__(
        self,
        content_root: Path,
        project_root: Path,
        host_factory: Callable[..., LockstepTransport] | None = None,
        connect_factory: Callable[..., LockstepTransport] | None = None,
    ) -> None:
        self._content_root = content_root
        self._project_root = project_root
        self._progress = load_progress(project_root)
        self._host_factory = host_factory or (
            lambda host, port, handshake=None, countdown_s=0.0: host_socket_transport(
                host, port, handshake, countdown_s
            )
        )
        self._connect_factory = connect_factory or (
            lambda host, port, handshake=None, countdown_s=0.0: connect_socket_transport(
                host, port, handshake, countdown_s
            )
        )
        self._selected_row = 0
        self._room_code = _generate_room_code()
        self._host = self._progress.last_online_host or "127.0.0.1"
        self._port = self._progress.last_online_port or DEFAULT_ONLINE_PORT
        self._start_countdown_s = 3.0
        self._ready = self._progress.last_online_ready
        if self._progress.last_online_room_code:
            self._room_code = self._progress.last_online_room_code
        self._pending_handshake: LobbyHandshake | None = None
        self._editing_host = False
        self._editing_port = False
        self._connection_thread: threading.Thread | None = None
        self._connection_result: OnlineLobbyResult | None = None
        self._connection_error: str | None = None
        self._status = "Choose local duel, host online, or join online."
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)

    def run(self) -> OnlineLobbyResult:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Multiplayer Lobby")
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 52)
        body_font = pygame.font.Font(None, 30)
        small_font = pygame.font.Font(None, 22)
        self._audio.speak("Multiplayer lobby. Choose local duel, host online, or join online.", 90)

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return OnlineLobbyResult.quit()
                if event.type == pygame.KEYDOWN:
                    result = self._handle_keydown(event)
                    if result is not None:
                        pygame.quit()
                        return result
                elif event.type == pygame.MOUSEBUTTONUP:
                    result = self._handle_click(event.pos)
                    if result is not None:
                        pygame.quit()
                        return result
            result = self._poll_connection()
            if result is not None:
                pygame.quit()
                return result
            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
            clock.tick(60)

    def _handle_keydown(self, event: pygame.event.Event) -> OnlineLobbyResult | None:
        key = event.key
        if key in {pygame.K_ESCAPE, pygame.K_m}:
            return OnlineLobbyResult.menu()
        if self._editing_host:
            return self._edit_host(event)
        if self._editing_port:
            return self._edit_port(event)
        if key == pygame.K_r:
            self._speak_row()
            return None
        if key in {pygame.K_UP, pygame.K_w}:
            self._selected_row = (self._selected_row - 1) % LOBBY_ROWS
            self._speak_row()
        elif key in {pygame.K_DOWN, pygame.K_s}:
            self._selected_row = (self._selected_row + 1) % LOBBY_ROWS
            self._speak_row()
        elif key == pygame.K_SPACE:
            return self._activate_row()
        return None

    def _handle_click(self, position: tuple[int, int]) -> OnlineLobbyResult | None:
        for row_index in range(LOBBY_ROWS):
            if self._row_rect(row_index).collidepoint(position):
                self._selected_row = row_index
                return self._activate_row()
        return None

    def _activate_row(self) -> OnlineLobbyResult | None:
        if self._selected_row == 0:
            return OnlineLobbyResult.local()
        if self._selected_row == 1:
            self._start_connection("host")
        elif self._selected_row == 2:
            self._start_connection("guest")
        elif self._selected_row == 3:
            self._room_code = _generate_room_code()
            self._status = f"Room code generated: {self._room_code}."
            self._audio.speak(self._status, 85)
        elif self._selected_row == 4:
            self._editing_host = True
            pygame.key.start_text_input()
            self._status = "Editing host address."
        elif self._selected_row == 5:
            self._editing_port = True
            pygame.key.start_text_input()
            self._status = "Editing port."
        elif self._selected_row == 6:
            self._ready = not self._ready
            self._status = "Ready" if self._ready else "Not ready"
            self._audio.speak(self._status, 85)
        elif self._selected_row == 7:
            if self._progress.last_online_room_code is None:
                self._status = "No saved room to reconnect."
                self._audio.speak(self._status, 90)
                return None
            self._room_code = self._progress.last_online_room_code
            self._host = self._progress.last_online_host or self._host
            self._port = self._progress.last_online_port or self._port
            self._ready = True
            self._selected_row = 1 if (self._progress.last_online_peer_id or "host") == "host" else 2
            self._status = f"Reconnecting to room {self._room_code}."
            self._audio.speak(self._status, 90)
            self._start_connection(self._progress.last_online_peer_id or "host")
        return None

    def _start_connection(self, peer_id: str) -> None:
        if self._connection_thread is not None and self._connection_thread.is_alive():
            self._status = "Connection already in progress."
            return
        if not self._ready:
            self._status = "Set ready before connecting."
            self._audio.speak(self._status, 90)
            return
        self._connection_error = None
        self._connection_result = None
        if peer_id == "host":
            self._status = f"Hosting room {self._room_code} on port {self._port}. Waiting for guest and synced start."
            target = self._connect_as_host
        else:
            self._status = f"Joining room {self._room_code} at {self._host}:{self._port}. Waiting for synced start."
            target = self._connect_as_guest
        self._pending_handshake = LobbyHandshake(
            self._room_code,
            peer_id,
            "Host" if peer_id == "host" else "Guest",
            is_ready=self._ready,
        )
        record_online_lobby_settings(self._project_root, self._room_code, self._host, self._port, peer_id, self._ready)
        self._audio.speak(self._status, 90)
        self._connection_thread = threading.Thread(target=target, daemon=True)
        self._connection_thread.start()

    def _connect_as_host(self) -> None:
        try:
            transport = self._host_factory("0.0.0.0", self._port, self._pending_handshake, self._start_countdown_s)
            self._connection_result = OnlineLobbyResult.start(LockstepSession(("guest", "host"), "host", transport))
        except Exception as error:
            self._connection_error = str(error)

    def _connect_as_guest(self) -> None:
        try:
            transport = self._connect_factory(self._host, self._port, self._pending_handshake, self._start_countdown_s)
            self._connection_result = OnlineLobbyResult.start(LockstepSession(("guest", "host"), "guest", transport))
        except Exception as error:
            self._connection_error = str(error)

    def _poll_connection(self) -> OnlineLobbyResult | None:
        if self._connection_result is not None:
            self._status = "Connected. Starting online duel."
            self._audio.speak(self._status, 95)
            return self._connection_result
        if self._connection_error is not None:
            self._status = f"Connection failed: {self._connection_error}"
            self._audio.speak("Connection failed.", 90)
            self._connection_error = None
        return None

    def _edit_host(self, event: pygame.event.Event) -> OnlineLobbyResult | None:
        if event.key == pygame.K_ESCAPE:
            self._editing_host = False
            pygame.key.stop_text_input()
            return None
        if event.key == pygame.K_BACKSPACE:
            self._host = self._host[:-1] or "127.0.0.1"
            return None
        if event.key == pygame.K_RETURN:
            self._editing_host = False
            pygame.key.stop_text_input()
            self._status = f"Host set to {self._host}."
            return None
        text = getattr(event, "unicode", "")
        if text and text.isprintable() and not text.isspace():
            if self._host == "127.0.0.1":
                self._host = ""
            self._host = (self._host + text)[:64]
        return None

    def _edit_port(self, event: pygame.event.Event) -> OnlineLobbyResult | None:
        current = str(self._port)
        if event.key == pygame.K_ESCAPE:
            self._editing_port = False
            pygame.key.stop_text_input()
            return None
        if event.key == pygame.K_BACKSPACE:
            current = current[:-1]
            self._port = int(current) if current else DEFAULT_ONLINE_PORT
            return None
        if event.key == pygame.K_RETURN:
            self._editing_port = False
            pygame.key.stop_text_input()
            self._status = f"Port set to {self._port}."
            return None
        text = getattr(event, "unicode", "")
        if text.isdigit():
            parsed = int((current + text)[-5:])
            self._port = min(max(parsed, 1), 65535)
        return None

    def _speak_row(self) -> None:
        self._audio.speak(self._row_text(self._selected_row), 75)

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Multiplayer Lobby", True, (248, 240, 205)), (58, 42))
        screen.blit(small_font.render("Space selects | Host waits | Join connects | R repeat | M/Esc returns", True, (245, 220, 130)), (62, 92))
        panel = pygame.Rect(58, 132, 860, 398)
        pygame.draw.rect(screen, (31, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), panel, width=2, border_radius=6)
        for index in range(LOBBY_ROWS):
            rect = self._row_rect(index)
            selected = index == self._selected_row
            pygame.draw.rect(screen, (64, 78, 90) if selected else (34, 42, 50), rect, border_radius=6)
            pygame.draw.rect(screen, (246, 214, 110) if selected else (82, 98, 110), rect, width=2, border_radius=6)
            screen.blit(body_font.render(self._row_label(index), True, (238, 242, 232)), (rect.left + 18, rect.top + 10))
            screen.blit(small_font.render(self._row_value(index), True, (172, 218, 232)), (rect.left + 280, rect.top + 14))
        screen.blit(small_font.render(self._status, True, (198, 216, 218)), (panel.left + 22, panel.bottom - 42))

    def _row_rect(self, row_index: int) -> pygame.Rect:
        return pygame.Rect(86, 164 + row_index * 56, 804, 42)

    def _row_label(self, row_index: int) -> str:
        return ("Local Duel", "Host Online", "Join Online", "Room Code", "Host Address", "Port", "Ready", "Reconnect")[row_index]

    def _row_value(self, row_index: int) -> str:
        if row_index == 0:
            return "same keyboard"
        if row_index == 1:
            return f"listen on {self._port} | start sync"
        if row_index == 2:
            return f"{self._host}:{self._port} | start sync"
        if row_index == 3:
            return self._room_code
        if row_index == 4:
            return self._host + ("_" if self._editing_host else "")
        if row_index == 5:
            return str(self._port) + ("_" if self._editing_port else "")
        if row_index == 6:
            return "ready" if self._ready else "not ready"
        return "saved room" if self._progress.last_online_room_code else "no saved room"

    def _row_text(self, row_index: int) -> str:
        if row_index == 0:
            return "Local duel. Start two players on this computer."
        if row_index == 1:
            return f"Host online. Room {self._room_code}. Listen on port {self._port}. Race starts with a synced countdown."
        if row_index == 2:
            return f"Join online. Room {self._room_code}. Connect to {self._host} port {self._port}. Race starts with a synced countdown."
        if row_index == 3:
            return f"Room code. {self._room_code}. Press space to regenerate."
        if row_index == 4:
            return f"Host address. {self._host}."
        if row_index == 5:
            return f"Port. {self._port}."
        if row_index == 6:
            return "Ready. Press space to toggle ready before connecting."
        return "Reconnect. Press space to reopen the last saved room settings."


def _generate_room_code() -> str:
    return secrets.token_hex(3).upper()
