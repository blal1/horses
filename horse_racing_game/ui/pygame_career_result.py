import os
from pathlib import Path

import pygame

from horse_racing_game.app.career_result_feedback import career_result_summary_lines, career_result_summary_text
from horse_racing_game.app.progress import GameProgress
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog


class PygameCareerResultScreen:
    def __init__(self, content_root: Path, project_root: Path, progress: GameProgress) -> None:
        self._content_root = content_root
        self._project_root = project_root
        self._progress = progress
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)

    def run(self) -> None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 520), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Career Result")
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 52)
        body_font = pygame.font.Font(None, 30)
        small_font = pygame.font.Font(None, 22)
        self._audio.speak(self._spoken_summary(), 100)

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONUP:
                    running = False

            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()

    def _handle_key(self, key: int) -> bool:
        if key == pygame.K_r:
            self._audio.speak(self._spoken_summary(), 100)
            return True
        return False

    def _spoken_summary(self) -> str:
        return f"Career result. {career_result_summary_text(self._progress.last_career_result_summary)}"

    def _lines(self) -> tuple[str, ...]:
        return career_result_summary_lines(self._progress.last_career_result_summary)

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Career Result", True, (248, 240, 205)), (58, 42))
        screen.blit(small_font.render("R repeats result | any other key or click continues", True, (245, 220, 130)), (62, 92))

        panel = pygame.Rect(58, 134, 862, 300)
        pygame.draw.rect(screen, (31, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), panel, width=2, border_radius=6)
        for index, line in enumerate(self._lines()):
            color = (246, 238, 210) if index == 0 else (198, 216, 218)
            screen.blit(body_font.render(line, True, color), (panel.left + 28, panel.top + 34 + index * 54))
