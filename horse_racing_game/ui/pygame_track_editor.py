import os
from pathlib import Path

import pygame

from horse_racing_game.app.progress import GameProgress, record_track_editor_selection
from horse_racing_game.app.track_editor import (
    adjust_draft,
    build_custom_track,
    draft_from_track,
    draft_summary,
    load_available_tracks,
    save_custom_track,
)
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog


FIELD_NAMES = ("Length", "Surface", "Turn direction", "Curve intensity", "Save custom track")


class PygameTrackEditorScreen:
    def __init__(self, content_root: Path, project_root: Path, progress: GameProgress) -> None:
        self._content_root = content_root
        self._project_root = project_root
        tracks = load_available_tracks(content_root)
        base = next((track for track in tracks if track.track_id == progress.last_track_id), tracks[0])
        self._draft = draft_from_track(base)
        self._field_index = 0
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)
        self.saved_track_id: str | None = None

    def run(self) -> str | None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Track Editor")
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 52)
        body_font = pygame.font.Font(None, 28)
        small_font = pygame.font.Font(None, 22)
        self._speak_current_field()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._handle_key(event.key, running)
                elif event.type == pygame.MOUSEBUTTONUP:
                    running = False
            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        return self.saved_track_id

    def _handle_key(self, key: int, running: bool) -> bool:
        if key in {pygame.K_ESCAPE, pygame.K_q}:
            self._audio.speak("Leaving track editor.", 80)
            return False
        if key in {pygame.K_UP, pygame.K_w}:
            self._field_index = (self._field_index - 1) % len(FIELD_NAMES)
            self._speak_current_field()
        elif key in {pygame.K_DOWN, pygame.K_s, pygame.K_TAB}:
            self._field_index = (self._field_index + 1) % len(FIELD_NAMES)
            self._speak_current_field()
        elif key in {pygame.K_LEFT, pygame.K_a}:
            self._draft = adjust_draft(self._draft, self._field_index, -1)
            self._speak_current_field()
        elif key in {pygame.K_RIGHT, pygame.K_d}:
            self._draft = adjust_draft(self._draft, self._field_index, 1)
            self._speak_current_field()
        elif key == pygame.K_r:
            self._audio.speak(draft_summary(self._draft), 90)
        elif key in {pygame.K_RETURN, pygame.K_SPACE}:
            if self._field_index == len(FIELD_NAMES) - 1:
                track = build_custom_track(self._draft)
                save_custom_track(self._project_root, track)
                record_track_editor_selection(self._project_root, track.track_id)
                self.saved_track_id = track.track_id
                self._audio.speak("Custom track saved and selected.", 90)
                return False
            self._draft = adjust_draft(self._draft, self._field_index, 1)
            self._speak_current_field()
        return running

    def _speak_current_field(self) -> None:
        self._audio.speak(f"{FIELD_NAMES[self._field_index]}. {draft_summary(self._draft)}", 80)

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Track Editor", True, (248, 240, 205)), (58, 42))
        screen.blit(small_font.render("W/S: field | A/D: adjust | R: preview | Enter on Save | Q/Esc: menu", True, (245, 220, 130)), (62, 92))
        panel = pygame.Rect(58, 132, 860, 420)
        pygame.draw.rect(screen, (31, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), panel, width=2, border_radius=6)
        rows = (
            f"Length: {self._draft.length_m:.0f} m",
            f"Surface: {self._draft.surface}",
            f"Turn direction: {self._draft.handedness}",
            f"Curve intensity: {self._draft.curve_intensity:.2f}",
            "Save custom track",
        )
        for index, row in enumerate(rows):
            y = panel.top + 34 + index * 58
            selected = index == self._field_index
            color = (64, 78, 90) if selected else (38, 48, 58)
            rect = pygame.Rect(panel.left + 26, y, 800, 42)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, (246, 214, 110) if selected else (82, 98, 110), rect, width=2, border_radius=6)
            screen.blit(body_font.render(row, True, (238, 242, 232)), (rect.left + 18, rect.top + 10))
        screen.blit(small_font.render(draft_summary(self._draft), True, (198, 216, 218)), (panel.left + 28, panel.bottom - 52))
