import os
from pathlib import Path

import pygame

from horse_racing_game.app.runtime_log import write_runtime_log
from horse_racing_game.app.track_editor import load_available_tracks
from horse_racing_game.audio.mix_profile import MIX_PROFILES
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.audio.pygame_music import play_music, stop_music

from horse_racing_game.content.loaders import load_horses, load_sound_catalog, load_stables, load_weather
from horse_racing_game.ui.menu_models import MENU_ROW_COUNT, MenuSelection, PygameMenuState


MENU_MUSIC = "assets/downloads/dpstudiomusic-fun-farm-324289.mp3"


class PygameMainMenu:
    def __init__(
        self,
        content_root: Path,
        project_root: Path | None = None,
        initial_horse_id: str | None = None,
        initial_track_id: str | None = None,
        initial_weather_id: str | None = None,
        initial_audio_mix_id: str | None = None,
        initial_stable_id: str | None = None,
        initial_difficulty_id: str | None = None,
    ) -> None:
        self._project_root = project_root or content_root.parent
        playable_horses = tuple(horse for horse in load_horses(content_root / "horses.json") if horse.role == "player")
        self._state = PygameMenuState(
            playable_horses,
            load_available_tracks(content_root),
            load_weather(content_root / "weather.json"),
            MIX_PROFILES,
            load_stables(content_root / "stables.json"),
        )
        if any(
            value is not None
            for value in (
                initial_horse_id,
                initial_track_id,
                initial_weather_id,
                initial_audio_mix_id,
                initial_stable_id,
                initial_difficulty_id,
            )
        ):
            self._state.select_ids(
                initial_horse_id or "",
                initial_track_id or "",
                initial_weather_id or "",
                initial_audio_mix_id or "",
                initial_stable_id or "",
                initial_difficulty_id or "",
            )
        self._catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(self._project_root, self._catalog)

    def run(self) -> MenuSelection | None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        write_runtime_log(self._project_root, "menu: pygame.init")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        write_runtime_log(self._project_root, "menu: set_mode 980x640 ok")
        pygame.display.set_caption("Horse Racing Prototype V2")
        play_music(self._project_root, MENU_MUSIC, 0.28)
        self._speak_selection()
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 56)
        body_font = pygame.font.Font(None, 30)
        small_font = pygame.font.Font(None, 22)

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    stop_music(self._project_root)
                    pygame.quit()
                    return None
                if event.type == pygame.KEYDOWN:
                    result = self._handle_keydown(event.key)
                    if result is not _MenuAction.CONTINUE:
                        stop_music(self._project_root)
                        pygame.quit()
                        return result.selection
                elif event.type == pygame.MOUSEBUTTONUP:
                    result = self._handle_click(event.pos)
                    if result is not _MenuAction.CONTINUE:
                        stop_music(self._project_root)
                        pygame.quit()
                        return result.selection

            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
            clock.tick(60)

    def _handle_keydown(self, key: int) -> "_MenuAction":
        if key in {pygame.K_ESCAPE, pygame.K_q}:
            self._play_ui("ui_cancel_low_tap", 0.52, "kenney_close_001")
            self._audio.speak("Quit menu.", 80)
            return _MenuAction.quit()
        if key == pygame.K_r:
            self._speak_selection()
            return _MenuAction.CONTINUE
        if key in {pygame.K_UP, pygame.K_w}:
            self._state.move_row(-1)
            self._play_ui("ui_move_soft_tick", 0.48, "kenney_click_001")
            self._speak_selection()
        elif key in {pygame.K_DOWN, pygame.K_s}:
            self._state.move_row(1)
            self._play_ui("ui_move_soft_tick", 0.48, "kenney_click_001")
            self._speak_selection()
        elif key in {pygame.K_LEFT, pygame.K_a}:
            self._state.cycle_current_option(-1)
            self._play_ui("ui_change_option_pluck", 0.5, "kenney_pluck_001")
            self._speak_selection()
        elif key in {pygame.K_RIGHT, pygame.K_d}:
            self._state.cycle_current_option(1)
            self._play_ui("ui_change_option_pluck", 0.5, "kenney_pluck_002")
            self._speak_selection()
        elif key == pygame.K_SPACE:
            if self._state.selected_row in {0, 1, 2, 3, 4, 5}:
                self._state.cycle_current_option(1)
                self._play_ui("ui_open_panel_stable", 0.5, "kenney_open_001")
                self._speak_selection()
            elif self._state.selected_row == 6:
                self._play_confirm()
                self._audio.speak("Starting quick race.", 90)
                return _MenuAction.start(self._state.selection("race"))
            elif self._state.selected_row == 7:
                self._play_confirm()
                self._audio.speak("Starting tutorial.", 90)
                return _MenuAction.start(self._state.selection("tutorial"))
            elif self._state.selected_row == 8:
                self._play_confirm()
                self._audio.speak("Starting training.", 90)
                return _MenuAction.start(self._state.selection("training"))
            elif self._state.selected_row == 9:
                self._play_confirm()
                self._audio.speak("Opening career hub.", 90)
                return _MenuAction.start(self._state.selection("career"))
            elif self._state.selected_row == 10:
                self._play_confirm()
                self._audio.speak("Starting obstacle lab.", 90)
                return _MenuAction.start(self._state.selection("obstacle_lab"))
            elif self._state.selected_row == 11:
                self._play_confirm()
                self._audio.speak("Starting time trial.", 90)
                return _MenuAction.start(self._state.selection("time_trial"))
            elif self._state.selected_row == 12:
                self._play_confirm()
                self._audio.speak("Starting ghost race.", 90)
                return _MenuAction.start(self._state.selection("ghost_race"))
            elif self._state.selected_row == 13:
                self._play_confirm()
                self._audio.speak("Opening multiplayer lobby.", 90)
                return _MenuAction.start(self._state.selection("multiplayer"))
            elif self._state.selected_row == 14:
                self._play_confirm()
                self._audio.speak("Showing replay.", 90)
                return _MenuAction.start(self._state.selection("replay"))
            elif self._state.selected_row == 15:
                self._play_confirm()
                self._audio.speak("Opening track editor.", 90)
                return _MenuAction.start(self._state.selection("track_editor"))
            elif self._state.selected_row == 16:
                self._play_confirm()
                self._audio.speak("Opening profile.", 90)
                return _MenuAction.start(self._state.selection("profile"))
            elif self._state.selected_row == 17:
                self._play_confirm()
                self._audio.speak("Showing statistics.", 90)
                return _MenuAction.start(self._state.selection("stats"))
            elif self._state.selected_row == 18:
                self._play_confirm()
                self._audio.speak("Opening special events.", 90)
                return _MenuAction.start(self._state.selection("special_event"))
            elif self._state.selected_row == 19:
                self._play_ui("ui_cancel_low_tap", 0.52, "kenney_close_001")
                self._audio.speak("Quit.", 80)
                return _MenuAction.quit()
        return _MenuAction.CONTINUE

    def _handle_click(self, position: tuple[int, int]) -> "_MenuAction":
        for row_index in range(MENU_ROW_COUNT):
            if self._option_rect(row_index).collidepoint(position):
                self._state.selected_row = row_index
                if row_index in {0, 1, 2, 3, 4, 5}:
                    self._state.cycle_current_option(1)
                    self._play_ui("ui_open_panel_stable", 0.5, "kenney_open_001")
                    self._speak_selection()
                    return _MenuAction.CONTINUE
                if row_index == 6:
                    self._play_confirm()
                    self._audio.speak("Starting quick race.", 90)
                    return _MenuAction.start(self._state.selection("race"))
                if row_index == 7:
                    self._play_confirm()
                    self._audio.speak("Starting tutorial.", 90)
                    return _MenuAction.start(self._state.selection("tutorial"))
                if row_index == 8:
                    self._play_confirm()
                    self._audio.speak("Starting training.", 90)
                    return _MenuAction.start(self._state.selection("training"))
                if row_index == 9:
                    self._play_confirm()
                    self._audio.speak("Opening career hub.", 90)
                    return _MenuAction.start(self._state.selection("career"))
                if row_index == 10:
                    self._play_confirm()
                    self._audio.speak("Starting obstacle lab.", 90)
                    return _MenuAction.start(self._state.selection("obstacle_lab"))
                if row_index == 11:
                    self._play_confirm()
                    self._audio.speak("Starting time trial.", 90)
                    return _MenuAction.start(self._state.selection("time_trial"))
                if row_index == 12:
                    self._play_confirm()
                    self._audio.speak("Starting ghost race.", 90)
                    return _MenuAction.start(self._state.selection("ghost_race"))
                if row_index == 13:
                    self._play_confirm()
                    self._audio.speak("Opening multiplayer lobby.", 90)
                    return _MenuAction.start(self._state.selection("multiplayer"))
                if row_index == 14:
                    self._play_confirm()
                    self._audio.speak("Showing replay.", 90)
                    return _MenuAction.start(self._state.selection("replay"))
                if row_index == 15:
                    self._play_confirm()
                    self._audio.speak("Opening track editor.", 90)
                    return _MenuAction.start(self._state.selection("track_editor"))
                if row_index == 16:
                    self._play_confirm()
                    self._audio.speak("Opening profile.", 90)
                    return _MenuAction.start(self._state.selection("profile"))
                if row_index == 17:
                    self._play_confirm()
                    self._audio.speak("Showing statistics.", 90)
                    return _MenuAction.start(self._state.selection("stats"))
                if row_index == 18:
                    self._play_confirm()
                    self._audio.speak("Opening special events.", 90)
                    return _MenuAction.start(self._state.selection("special_event"))
                self._play_ui("ui_cancel_low_tap", 0.52, "kenney_close_001")
                self._audio.speak("Quit.", 80)
                return _MenuAction.quit()
        return _MenuAction.CONTINUE

    def _speak_selection(self) -> None:
        self._audio.speak(self._selection_text(), 70)

    def _selection_text(self) -> str:
        if self._state.selected_row == 0:
            return f"Horse. {self._state.selected_horse.name}. Press space to change."
        if self._state.selected_row == 1:
            return f"Track. {self._state.selected_track.name}. Press space to change."
        if self._state.selected_row == 2:
            return f"Weather. {self._state.selected_weather.name}. Press space to change."
        if self._state.selected_row == 3:
            return f"Audio profile. {self._state.selected_audio_profile.name}. Press space to change."
        if self._state.selected_row == 4:
            return f"Stable. {self._state.selected_stable.name}. {self._state.selected_stable.focus}. Press space to change."
        if self._state.selected_row == 5:
            return f"Difficulty. {self._state.selected_difficulty.name}. Press space to change."
        if self._state.selected_row == 6:
            return "Quick race. Press space to launch."
        if self._state.selected_row == 7:
            return "Tutorial. Press space for guided controls."
        if self._state.selected_row == 8:
            return "Training. Press space to improve the selected horse."
        if self._state.selected_row == 9:
            return "Career. Press space to open race, training, and rest choices."
        if self._state.selected_row == 10:
            return "Obstacle lab. Press space to test dodge, jump, and duck obstacles."
        if self._state.selected_row == 11:
            return "Time trial. Press space to race the clock and save your best time."
        if self._state.selected_row == 12:
            return "Ghost race. Press space to race against the last saved replay."
        if self._state.selected_row == 13:
            return "Multiplayer. Press space for local duel or online lobby."
        if self._state.selected_row == 14:
            return "Replay. Press space to hear the last race again."
        if self._state.selected_row == 15:
            return "Track editor. Press space to build a custom audio track."
        if self._state.selected_row == 16:
            return "Profile. Press space to view identity, wallet, and unlocks."
        if self._state.selected_row == 17:
            return "Statistics. Press space to view season stats and standings."
        if self._state.selected_row == 18:
            return "Special events. Press space to open scenario challenges."
        if self._state.selected_row == 19:
            return "Quit. Press space to exit."
        return "Quit. Press space to exit."

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        self._draw_header(screen, title_font, small_font)
        self._draw_options(screen, body_font)
        self._draw_horse_panel(screen, body_font, small_font)
        self._draw_track_panel(screen, body_font, small_font)
        self._draw_action_hint(screen, body_font, small_font)
        hint = small_font.render("W/S or Up/Down: row | A/D or Left/Right: change | Space: activate | R: repeat | Q/Esc: quit", True, (245, 220, 130))
        screen.blit(hint, (60, 582))

    def _draw_header(self, screen: pygame.Surface, title_font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        title = title_font.render("Horse Racing", True, (248, 240, 205))
        screen.blit(title, (58, 44))
        subtitle = small_font.render("PROTOTYPE V2 - obstacles, menus, Pygame audio", True, (156, 182, 194))
        screen.blit(subtitle, (62, 96))

    def _draw_options(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        rows = (
            ("Horse", self._state.selected_horse.name),
            ("Track", self._state.selected_track.name),
            ("Weather", self._state.selected_weather.name),
            ("Audio", self._state.selected_audio_profile.name),
            ("Stable", self._state.selected_stable.name),
            ("Difficulty", self._state.selected_difficulty.name),
            ("Quick Race", "press Space or click"),
            ("Tutorial", "guided audio basics"),
            ("Training", "improve horse"),
            ("Career", "race, train, rest"),
            ("Obstacle Lab", "test obstacle timing"),
            ("Time Trial", "race the clock"),
            ("Ghost Race", "last replay challenge"),
            ("Multiplayer", "local or online"),
            ("Replay", "last race audio"),
            ("Track Editor", "custom audio track"),
            ("Profile", "identity and wallet"),
            ("Statistics", "stats and standings"),
            ("Special Events", "scenario challenges"),
            ("Quit", ""),
        )
        for index, row in enumerate(rows):
            rect = self._option_rect(index)
            selected = index == self._state.selected_row
            color = (64, 78, 90) if selected else (34, 42, 50)
            border = (246, 214, 110) if selected else (82, 98, 110)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, border, rect, width=2, border_radius=6)
            if selected:
                pygame.draw.polygon(
                    screen,
                    (246, 214, 110),
                    ((rect.left - 20, rect.centery), (rect.left - 6, rect.centery - 9), (rect.left - 6, rect.centery + 9)),
                )
            label = font.render(row[0], True, (238, 242, 232))
            screen.blit(label, (rect.left + 18, rect.top + 12))
            if row[1]:
                value = font.render(row[1], True, (172, 218, 232))
                screen.blit(value, (rect.left + 152, rect.top + 12))

    def _draw_horse_panel(self, screen: pygame.Surface, body_font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        rect = pygame.Rect(500, 142, 410, 210)
        pygame.draw.rect(screen, (31, 40, 48), rect, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), rect, width=2, border_radius=6)
        horse = self._state.selected_horse
        screen.blit(body_font.render(horse.name, True, (246, 238, 210)), (rect.left + 20, rect.top + 18))
        screen.blit(small_font.render(f"Surface: {horse.preferred_surface}", True, (198, 216, 218)), (rect.left + 22, rect.top + 56))
        stats = (
            ("Speed", horse.stats.max_speed_mps / 18.0),
            ("Accel", horse.stats.acceleration / 10.0),
            ("Stamina", horse.stats.stamina_capacity / 100.0),
            ("Handling", horse.stats.handling / 10.0),
        )
        for index, stat in enumerate(stats):
            self._draw_stat_bar(screen, small_font, rect.left + 22, rect.top + 88 + index * 26, stat[0], stat[1])

    def _draw_track_panel(self, screen: pygame.Surface, body_font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        rect = pygame.Rect(500, 376, 410, 172)
        pygame.draw.rect(screen, (31, 40, 48), rect, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), rect, width=2, border_radius=6)
        track = self._state.selected_track
        screen.blit(body_font.render(track.name, True, (246, 238, 210)), (rect.left + 20, rect.top + 18))
        rows = (
            f"Length: {track.length_m:.0f}m",
            f"Surface: {track.surface}",
            f"Lanes: {track.lanes}",
            f"Direction: {track.handedness}",
        )
        for index, row in enumerate(rows):
            screen.blit(small_font.render(row, True, (198, 216, 218)), (rect.left + 22, rect.top + 58 + index * 24))

    def _draw_action_hint(self, screen: pygame.Surface, body_font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        row = self._state.selected_row
        if row == 0:
            text = "Selected: Horse - Space changes horse"
        elif row == 1:
            text = "Selected: Track - Space changes track"
        elif row == 2:
            text = "Selected: Weather - Space changes weather"
        elif row == 3:
            text = "Selected: Audio - Space changes audio profile"
        elif row == 4:
            text = "Selected: Stable - Space changes stable"
        elif row == 5:
            text = "Selected: Difficulty - Space changes quick race difficulty"
        elif row == 6:
            text = "Selected: Quick Race - Space launches"
        elif row == 7:
            text = "Selected: Tutorial - Space starts guided help"
        elif row == 8:
            text = "Selected: Training - Space starts improvement run"
        elif row == 9:
            text = "Selected: Career - Space opens career choices"
        elif row == 10:
            text = "Selected: Obstacle Lab - Space starts obstacle test"
        elif row == 11:
            text = "Selected: Time Trial - Space starts a timed run"
        elif row == 12:
            text = "Selected: Ghost Race - Space races the last replay"
        elif row == 13:
            text = "Selected: Multiplayer - Space opens lobby"
        elif row == 14:
            text = "Selected: Replay - Space repeats last race"
        elif row == 15:
            text = "Selected: Track Editor - Space opens editor"
        elif row == 16:
            text = "Selected: Profile - Space opens identity and wallet"
        elif row == 17:
            text = "Selected: Statistics - Space shows stats and standings"
        elif row == 18:
            text = "Selected: Special Events - Space opens scenario challenges"
        elif row == 19:
            text = "Selected: Quit - Space exits"
        else:
            text = "Selected: Quit - Space exits"
        panel = pygame.Rect(58, 524, 388, 50)
        pygame.draw.rect(screen, (26, 34, 42), panel, border_radius=6)
        pygame.draw.rect(screen, (94, 112, 130), panel, width=2, border_radius=6)
        screen.blit(body_font.render("Menu ready", True, (246, 238, 210)), (panel.left + 18, panel.top + 8))
        screen.blit(small_font.render(text, True, (172, 218, 232)), (panel.left + 18, panel.top + 34))

    def _draw_stat_bar(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        x: int,
        y: int,
        label: str,
        value: float,
    ) -> None:
        bounded = min(max(value, 0.0), 1.0)
        screen.blit(font.render(label, True, (210, 222, 220)), (x, y - 2))
        bar_rect = pygame.Rect(x + 86, y, 236, 12)
        pygame.draw.rect(screen, (14, 18, 22), bar_rect, border_radius=4)
        pygame.draw.rect(screen, (96, 190, 132), (bar_rect.left, bar_rect.top, int(bar_rect.width * bounded), 12), border_radius=4)
        pygame.draw.rect(screen, (164, 184, 172), bar_rect, width=1, border_radius=4)

    def _option_rect(self, row_index: int) -> pygame.Rect:
        return pygame.Rect(58, 104 + row_index * 23, 388, 20)

    def _play_confirm(self) -> None:
        self._play_ui("ui_confirm_warm_chime", 0.58, "kenney_confirmation_001")

    def _play_ui(self, sound_id: str, volume: float, fallback_sound_id: str | None = None) -> None:
        if self._catalog.get(sound_id) is not None:
            self._audio.play_2d(sound_id, volume)
            return
        if fallback_sound_id is not None:
            self._audio.play_2d(fallback_sound_id, volume)


class _MenuAction:
    CONTINUE = None

    def __init__(self, selection: MenuSelection | None) -> None:
        self.selection = selection

    @classmethod
    def start(cls, selection: MenuSelection) -> "_MenuAction":
        return cls(selection)

    @classmethod
    def quit(cls) -> "_MenuAction":
        return cls(None)


_MenuAction.CONTINUE = _MenuAction(None)
