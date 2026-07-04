import os
from pathlib import Path

import pygame

from horse_racing_game.app.progress import GameProgress, record_track_editor_selection
from horse_racing_game.app.track_ecosystem import (
    TrackCatalog,
    TrackRating,
    TrackShare,
    load_track_catalog,
    save_track_catalog,
)
from horse_racing_game.app.track_editor import (
    adjust_draft,
    build_custom_track,
    custom_track_identity,
    CUSTOM_TRACK_SLOTS,
    draft_from_track,
    draft_summary,
    load_available_tracks,
    save_custom_track,
)
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog


FIELD_NAMES = (
    "Length",
    "Surface",
    "Turn direction",
    "Curve intensity",
    "Custom track slot",
    "Publish custom track",
    "Rate current track",
    "Discover public tracks",
    "Select discovered track",
    "Save custom track",
)


class PygameTrackEditorScreen:
    def __init__(self, content_root: Path, project_root: Path, progress: GameProgress) -> None:
        self._content_root = content_root
        self._project_root = project_root
        tracks = load_available_tracks(content_root)
        base = next((track for track in tracks if track.track_id == progress.last_track_id), tracks[0])
        self._draft = draft_from_track(base)
        self._selected_track_id = base.track_id
        self._custom_slot_index = 0
        self._field_index = 0
        self._catalog = load_track_catalog(project_root)
        self._discovery_results = self._catalog.discover()
        self._discovery_index = 0
        self._catalog_status = self._catalog_summary()
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
        if key in {pygame.K_ESCAPE, pygame.K_m}:
            self._audio.speak("Leaving track editor.", 80)
            return False
        if key in {pygame.K_UP, pygame.K_w}:
            self._field_index = (self._field_index - 1) % len(FIELD_NAMES)
            self._speak_current_field()
        elif key in {pygame.K_DOWN, pygame.K_s}:
            self._field_index = (self._field_index + 1) % len(FIELD_NAMES)
            self._speak_current_field()
        elif key in {pygame.K_LEFT, pygame.K_a}:
            self._adjust_current(-1)
        elif key in {pygame.K_RIGHT, pygame.K_d}:
            self._adjust_current(1)
        elif key == pygame.K_r:
            self._audio.speak(f"{draft_summary(self._draft)} {self._catalog_status}", 90)
        elif key == pygame.K_SPACE:
            if self._field_index == len(FIELD_NAMES) - 1:
                track = self._save_custom_track()
                self.saved_track_id = track.track_id
                self._audio.speak("Custom track saved and selected.", 90)
                return False
            if self._field_index == 5:
                self._publish_custom_track()
                return running
            if self._field_index == 6:
                self._rate_current_track()
                return running
            if self._field_index == 7:
                self._refresh_discovery()
                return running
            if self._field_index == 8:
                self._select_discovered_track()
                return running
            self._draft = adjust_draft(self._draft, self._field_index, 1)
            self._speak_current_field()
        return running

    def _speak_current_field(self) -> None:
        self._audio.speak(f"{FIELD_NAMES[self._field_index]}. {self._field_detail()}", 80)

    def _adjust_current(self, delta: int) -> None:
        if self._field_index == 4:
            self._custom_slot_index = (self._custom_slot_index + delta) % len(CUSTOM_TRACK_SLOTS)
        elif self._field_index == 8 and self._discovery_results:
            self._discovery_index = (self._discovery_index + delta) % len(self._discovery_results)
        else:
            self._draft = adjust_draft(self._draft, self._field_index, delta)
        self._speak_current_field()

    def _save_custom_track(self):
        track = build_custom_track(self._draft, self._custom_slot_index)
        save_custom_track(self._project_root, track)
        record_track_editor_selection(self._project_root, track.track_id)
        self._selected_track_id = track.track_id
        return track

    def _publish_custom_track(self) -> None:
        track = self._save_custom_track()
        self._catalog.publish(TrackShare(track.track_id, "local_player", "public", version=1))
        save_track_catalog(self._project_root, self._catalog)
        self._refresh_discovery(speak=False)
        self._catalog_status = f"Published {track.name} as public."
        self._audio.speak(self._catalog_status, 90)

    def _rate_current_track(self) -> None:
        track_id = self._selected_track_id
        if track_id not in {share.track_id for share in self._catalog.shares()}:
            self._catalog.publish(TrackShare(track_id, "local_player", "public", version=1))
        self._catalog.rate(TrackRating(track_id, "local_player", 5, ("favorite", "audio_first")))
        save_track_catalog(self._project_root, self._catalog)
        self._refresh_discovery(speak=False)
        self._catalog_status = f"Rated {track_id} five stars."
        self._audio.speak(self._catalog_status, 90)

    def _refresh_discovery(self, speak: bool = True) -> None:
        self._catalog = load_track_catalog(self._project_root)
        self._discovery_results = self._catalog.discover()
        self._discovery_index = min(self._discovery_index, max(len(self._discovery_results) - 1, 0))
        self._catalog_status = self._catalog_summary()
        if speak:
            self._audio.speak(self._catalog_status, 90)

    def _select_discovered_track(self) -> None:
        result = self._selected_discovery_result()
        if result is None:
            self._catalog_status = "No public track discovery result to select."
            self._audio.speak(self._catalog_status, 80)
            return
        track = next((item for item in load_available_tracks(self._content_root) if item.track_id == result.track_id), None)
        if track is None:
            self._catalog_status = f"{result.track_id} is in the catalog but is not installed locally."
            self._audio.speak(self._catalog_status, 80)
            return
        record_track_editor_selection(self._project_root, track.track_id)
        self._selected_track_id = track.track_id
        self._draft = draft_from_track(track)
        self._catalog_status = f"Selected discovered track {track.name}."
        self._audio.speak(self._catalog_status, 90)

    def _selected_discovery_result(self):
        if not self._discovery_results:
            return None
        return self._discovery_results[self._discovery_index]

    def _catalog_summary(self) -> str:
        if not self._discovery_results:
            return "No public tracks discovered."
        selected = self._selected_discovery_result()
        assert selected is not None
        return (
            f"Discovery {self._discovery_index + 1}/{len(self._discovery_results)}: "
            f"{selected.track_id}, rating {selected.average_rating:.1f}, score {selected.score:.2f}."
        )

    def _field_detail(self) -> str:
        if self._field_index <= 3:
            return draft_summary(self._draft)
        if self._field_index == 4:
            track_id, name = custom_track_identity(self._custom_slot_index)
            return f"{name}. Saved as {track_id}."
        if self._field_index == 5:
            return "Save and publish the custom track to the local public catalog."
        if self._field_index == 6:
            return f"Give {self._selected_track_id} a five star local rating."
        if self._field_index == 7:
            return "Refresh public track discovery."
        if self._field_index == 8:
            return self._catalog_summary()
        return draft_summary(self._draft)

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Track Editor", True, (248, 240, 205)), (58, 42))
        screen.blit(small_font.render("W/S: field | A/D: adjust | R: preview | Space activate/save | M/Esc: menu", True, (245, 220, 130)), (62, 92))
        panel = pygame.Rect(58, 132, 860, 420)
        pygame.draw.rect(screen, (31, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), panel, width=2, border_radius=6)
        rows = (
            f"Length: {self._draft.length_m:.0f} m",
            f"Surface: {self._draft.surface}",
            f"Turn direction: {self._draft.handedness}",
            f"Curve intensity: {self._draft.curve_intensity:.2f}",
            f"Custom slot: {custom_track_identity(self._custom_slot_index)[1]}",
            "Publish custom track",
            f"Rate current track: {self._selected_track_id}",
            "Discover public tracks",
            self._catalog_summary(),
            "Save custom track",
        )
        for index, row in enumerate(rows):
            y = panel.top + 28 + index * 42
            selected = index == self._field_index
            color = (64, 78, 90) if selected else (38, 48, 58)
            rect = pygame.Rect(panel.left + 26, y, 800, 34)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, (246, 214, 110) if selected else (82, 98, 110), rect, width=2, border_radius=6)
            screen.blit(small_font.render(row, True, (238, 242, 232)), (rect.left + 18, rect.top + 8))
        screen.blit(small_font.render(draft_summary(self._draft), True, (198, 216, 218)), (panel.left + 28, panel.bottom - 52))
