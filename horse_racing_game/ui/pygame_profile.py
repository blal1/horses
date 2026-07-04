import os
from pathlib import Path

import pygame

from horse_racing_game.app.profile import (
    BADGE_OPTIONS,
    COSMETIC_OPTIONS,
    TITLE_OPTIONS,
    PlayerProfile,
    claim_profile_starter_reward,
    equip_profile_badge,
    equip_profile_cosmetic,
    equip_profile_title,
    load_player_profile,
    profile_summary_lines,
)
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog


class PygameProfileScreen:
    def __init__(self, content_root: Path, project_root: Path) -> None:
        self._content_root = content_root
        self._project_root = project_root
        self._profile = load_player_profile(project_root)
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)
        self._selected_row = 0
        self._title_index = _option_index(TITLE_OPTIONS, self._profile.identity.title_id)
        self._badge_index = 0
        self._cosmetic_index = 0

    def run(self) -> None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Profile")
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 52)
        body_font = pygame.font.Font(None, 28)
        small_font = pygame.font.Font(None, 22)
        self._audio.speak(self._spoken_summary(), 90)

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

    def _handle_key(self, key: int) -> bool:
        if key in {pygame.K_ESCAPE, pygame.K_m}:
            return False
        if key == pygame.K_r:
            self._speak_selection()
            return True
        if key in {pygame.K_UP, pygame.K_w}:
            self._selected_row = (self._selected_row - 1) % len(self._rows())
            self._speak_selection()
        elif key in {pygame.K_DOWN, pygame.K_s}:
            self._selected_row = (self._selected_row + 1) % len(self._rows())
            self._speak_selection()
        elif key in {pygame.K_LEFT, pygame.K_a}:
            self._cycle_selected(-1)
            self._speak_selection()
        elif key in {pygame.K_RIGHT, pygame.K_d}:
            self._cycle_selected(1)
            self._speak_selection()
        elif key == pygame.K_SPACE:
            self._activate_selected()
        return True

    def _handle_click(self, position: tuple[int, int]) -> bool:
        for row_index in range(len(self._rows())):
            if self._option_rect(row_index).collidepoint(position):
                self._selected_row = row_index
                self._activate_selected()
                return True
        return True

    def _spoken_summary(self) -> str:
        return "Profile. " + " ".join(profile_summary_lines(self._profile))

    def _speak_selection(self) -> None:
        self._audio.speak(self._selection_text(), 80)

    def _selection_text(self) -> str:
        if self._selected_row == 0:
            return "Claim starter reward. Unlock a title, badge, cosmetic, soft currency, and XP."
        if self._selected_row == 1:
            title_id = self._selected_title()
            status = "owned" if self._is_owned_or_default(title_id) else "locked"
            return f"Title {title_id}, {status}. Left and right change. Space equips."
        if self._selected_row == 2:
            badge_id = self._selected_badge()
            status = "owned" if badge_id in self._profile.economy.owned_item_ids else "locked"
            return f"Badge {badge_id}, {status}. Left and right change. Space equips."
        if self._selected_row == 3:
            cosmetic_id = self._selected_cosmetic()
            status = "owned" if cosmetic_id in self._profile.economy.owned_item_ids else "locked"
            return f"Cosmetic {cosmetic_id}, {status}. Left and right change. Space equips."
        return "Back. Press space to return."

    def _cycle_selected(self, direction: int) -> None:
        if self._selected_row == 1:
            self._title_index = (self._title_index + direction) % len(TITLE_OPTIONS)
        elif self._selected_row == 2:
            self._badge_index = (self._badge_index + direction) % len(BADGE_OPTIONS)
        elif self._selected_row == 3:
            self._cosmetic_index = (self._cosmetic_index + direction) % len(COSMETIC_OPTIONS)

    def _activate_selected(self) -> None:
        try:
            if self._selected_row == 0:
                before = self._profile
                self._profile = claim_profile_starter_reward(self._project_root, self._profile)
                if before == self._profile:
                    self._audio.speak("Starter reward already claimed.", 90)
                else:
                    self._audio.speak("Starter reward claimed.", 90)
            elif self._selected_row == 1:
                self._profile = equip_profile_title(self._project_root, self._profile, self._selected_title())
                self._audio.speak(f"Equipped title {self._selected_title()}.", 90)
            elif self._selected_row == 2:
                self._profile = equip_profile_badge(self._project_root, self._profile, self._selected_badge())
                self._audio.speak(f"Equipped badge {self._selected_badge()}.", 90)
            elif self._selected_row == 3:
                self._profile = equip_profile_cosmetic(self._project_root, self._profile, self._selected_cosmetic())
                self._audio.speak(f"Equipped cosmetic {self._selected_cosmetic()}.", 90)
            else:
                self._audio.speak("Back to menu.", 80)
        except ValueError as error:
            self._audio.speak(str(error), 90)

    def _rows(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Claim reward", "starter identity and economy grant"),
            ("Title", self._selected_title()),
            ("Badge", self._selected_badge()),
            ("Cosmetic", self._selected_cosmetic()),
            ("Back", "return to menu"),
        )

    def _summary_lines(self) -> tuple[str, ...]:
        return profile_summary_lines(self._profile)

    def _selected_title(self) -> str:
        return TITLE_OPTIONS[self._title_index % len(TITLE_OPTIONS)]

    def _selected_badge(self) -> str:
        return BADGE_OPTIONS[self._badge_index % len(BADGE_OPTIONS)]

    def _selected_cosmetic(self) -> str:
        return COSMETIC_OPTIONS[self._cosmetic_index % len(COSMETIC_OPTIONS)]

    def _is_owned_or_default(self, item_id: str) -> bool:
        return item_id == "rookie_rider" or item_id in self._profile.economy.owned_item_ids

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Profile", True, (248, 240, 205)), (58, 42))
        screen.blit(small_font.render("Up/Down row | Left/Right choice | Enter equip/claim | R repeat | M/Esc menu", True, (245, 220, 130)), (62, 92))
        left = pygame.Rect(58, 132, 410, 430)
        right = pygame.Rect(510, 132, 410, 430)
        for rect, label in ((left, "Rider"), (right, "Actions")):
            pygame.draw.rect(screen, (31, 40, 48), rect, border_radius=6)
            pygame.draw.rect(screen, (84, 102, 116), rect, width=2, border_radius=6)
            screen.blit(body_font.render(label, True, (246, 238, 210)), (rect.left + 20, rect.top + 18))

        for index, line in enumerate(self._summary_lines()):
            screen.blit(small_font.render(line, True, (198, 216, 218)), (left.left + 22, left.top + 64 + index * 34))
        for index, row in enumerate(self._rows()):
            rect = self._option_rect(index)
            selected = index == self._selected_row
            color = (64, 78, 90) if selected else (34, 42, 50)
            border = (246, 214, 110) if selected else (82, 98, 110)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, border, rect, width=2, border_radius=6)
            screen.blit(small_font.render(row[0], True, (238, 242, 232)), (rect.left + 16, rect.top + 8))
            screen.blit(small_font.render(row[1], True, (172, 218, 232)), (rect.left + 150, rect.top + 8))
        screen.blit(small_font.render(self._selection_text(), True, (172, 218, 232)), (right.left + 22, right.bottom - 42))

    def _option_rect(self, row_index: int) -> pygame.Rect:
        return pygame.Rect(532, 196 + row_index * 48, 366, 36)


def _option_index(options: tuple[str, ...], value: str) -> int:
    return next((index for index, item in enumerate(options) if item == value), 0)
