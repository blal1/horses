import os
from pathlib import Path

import pygame

from horse_racing_game.app.special_events import (
    SpecialEventChallenge,
    default_special_events,
    load_special_event_records,
)
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog


class PygameSpecialEventScreen:
    """Lists the special-event scenario challenges, shows saved completion, and
    returns the chosen challenge to launch (or ``None`` to return to the menu).

    Audio-first: the current row and its objectives/status are spoken; ``R``
    repeats, ``Space`` launches, ``Esc``/``M`` returns to the menu.
    """

    def __init__(
        self,
        content_root: Path,
        project_root: Path,
        last_result_summary: str | None = None,
    ) -> None:
        self._content_root = content_root
        self._project_root = project_root
        self._challenges = default_special_events()
        self._records = load_special_event_records(project_root)
        self._selected_row = 0
        self._last_result_summary = last_result_summary
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)
        self.chosen_event_id: str | None = None

    def run(self) -> SpecialEventChallenge | None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Special Events")
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 52)
        body_font = pygame.font.Font(None, 28)
        small_font = pygame.font.Font(None, 22)
        if self._last_result_summary:
            self._audio.speak(self._last_result_summary, 95)
        else:
            self._audio.speak(self._intro(), 90)

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONUP:
                    running = self._handle_click(event.pos)
            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        if self.chosen_event_id is None:
            return None
        return self._challenges[self._selected_row]

    def _handle_key(self, key: int) -> bool:
        if key in {pygame.K_ESCAPE, pygame.K_m}:
            self._audio.speak("Back to the menu.", 80)
            return False
        if key == pygame.K_r:
            self._speak_selection()
            return True
        if key in {pygame.K_UP, pygame.K_w}:
            self._selected_row = (self._selected_row - 1) % len(self._challenges)
            self._speak_selection()
        elif key in {pygame.K_DOWN, pygame.K_s}:
            self._selected_row = (self._selected_row + 1) % len(self._challenges)
            self._speak_selection()
        elif key == pygame.K_SPACE:
            self.chosen_event_id = self._challenges[self._selected_row].event_id
            self._audio.speak(f"Starting {self._selected().name}.", 90)
            return False
        return True

    def _handle_click(self, position: tuple[int, int]) -> bool:
        for index in range(len(self._challenges)):
            if self._row_rect(index).collidepoint(position):
                self._selected_row = index
                self.chosen_event_id = self._challenges[index].event_id
                return False
        return True

    def _selected(self) -> SpecialEventChallenge:
        return self._challenges[self._selected_row]

    def _intro(self) -> str:
        return (
            "Special events. Scenario challenges that reuse the race loop. "
            f"{len(self._challenges)} available. Up and down to browse, space to start. "
            + self._selection_text()
        )

    def _speak_selection(self) -> None:
        self._audio.speak(self._selection_text(), 80)

    def _selection_text(self) -> str:
        challenge = self._selected()
        objectives = "; ".join(obj.description for obj in challenge.objectives)
        return f"{challenge.name}. {challenge.briefing} Objectives: {objectives}. {self._status_text(challenge)}"

    def _status_text(self, challenge: SpecialEventChallenge) -> str:
        record = self._records.get(challenge.event_id)
        total = len(challenge.objectives)
        if record is None:
            return f"Not attempted. 0 of {total} objectives."
        status = "Complete" if record.completed else "In progress"
        best_time = "" if record.best_elapsed_s is None else f" Best time {record.best_elapsed_s:.1f}s."
        return f"{status}. Best {record.best_objectives_met} of {total} objectives.{best_time}"

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Special Events", True, (248, 240, 205)), (58, 42))
        screen.blit(
            small_font.render("Up/Down browse | Space start | R repeat | M/Esc menu", True, (245, 220, 130)),
            (62, 92),
        )
        for index, challenge in enumerate(self._challenges):
            rect = self._row_rect(index)
            selected = index == self._selected_row
            color = (64, 78, 90) if selected else (34, 42, 50)
            border = (246, 214, 110) if selected else (82, 98, 110)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, border, rect, width=2, border_radius=6)
            record = self._records.get(challenge.event_id)
            total = len(challenge.objectives)
            if record is None:
                badge = f"0/{total}"
            else:
                badge = ("done " if record.completed else "") + f"{record.best_objectives_met}/{total}"
            screen.blit(body_font.render(challenge.name, True, (238, 242, 232)), (rect.left + 18, rect.top + 12))
            screen.blit(small_font.render(badge, True, (172, 218, 232)), (rect.right - 120, rect.top + 16))

        panel = pygame.Rect(58, 470, 862, 130)
        pygame.draw.rect(screen, (31, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), panel, width=2, border_radius=6)
        selected = self._selected()
        screen.blit(body_font.render(selected.name, True, (246, 238, 210)), (panel.left + 20, panel.top + 14))
        screen.blit(small_font.render(self._status_text(selected), True, (172, 218, 232)), (panel.left + 22, panel.top + 50))
        for index, objective in enumerate(selected.objectives):
            screen.blit(
                small_font.render(f"- {objective.description}", True, (198, 216, 218)),
                (panel.left + 22, panel.top + 76 + index * 22),
            )

    def _row_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(58, 140 + index * 66, 862, 54)
