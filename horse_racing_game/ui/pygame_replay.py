import os
from pathlib import Path

import pygame

from horse_racing_game.app.progress import GameProgress
from horse_racing_game.app.replay import ReplayTimeline, build_replay_timeline, replay_from_dict, replay_line_for_event
from horse_racing_game.app.replay_exports import build_last_replay_share_bundle, load_replay_share_index, save_replay_share_bundle
from horse_racing_game.audio.audio_engine import AudioEngine
from horse_racing_game.audio.event_router import AudioEventRouter
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_sound_catalog
from horse_racing_game.simulation.race_events import RaceEvent


PLAYBACK_INTERVAL_S = 0.85


class PygameReplayScreen:
    def __init__(self, content_root: Path, project_root: Path, progress: GameProgress) -> None:
        self._content_root = content_root
        self._project_root = project_root
        self._progress = progress
        self._lines = progress.last_replay_lines or ("No replay is available yet. Finish a race first.",)
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)
        self._audio_engine = AudioEngine(AudioEventRouter(catalog, self._audio))
        replay = replay_from_dict(progress.last_replay or {})
        self._timeline = build_replay_timeline(replay, content_root) if replay is not None else ReplayTimeline((), (), None)
        self._index = 0
        self._last_key_index: int | None = None
        self._playing = self._timeline.has_events
        self._time_until_next_s = 0.0
        self._status = "Audio replay ready" if self._timeline.has_events else self._lines[0]
        self._share_status = self._initial_share_status()

    def run(self) -> None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Audio Replay")
        clock = pygame.time.Clock()
        title_font = pygame.font.Font(None, 52)
        body_font = pygame.font.Font(None, 28)
        small_font = pygame.font.Font(None, 22)
        if self._timeline.has_events:
            self._audio.play_2d("replay_start_tape", 0.7)
            self._audio.speak("Audio replay. Space pauses. Right steps. F jumps to final stretch. R repeats the last key moment.", 90)
        else:
            self._audio.speak(self._lines[0], 90)

        running = True
        while running:
            delta_s = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONUP:
                    running = False
            self._update(delta_s)
            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
        self._audio.stop_all()
        pygame.quit()

    def _handle_key(self, key: int) -> bool:
        if key in {pygame.K_ESCAPE, pygame.K_m, pygame.K_q}:
            return False
        if key == pygame.K_SPACE:
            self._playing = not self._playing
            self._status = "Replay playing" if self._playing else "Replay paused"
        elif key in {pygame.K_RIGHT, pygame.K_n}:
            self._playing = False
            self._play_current_and_advance()
        elif key in {pygame.K_LEFT, pygame.K_b}:
            self._playing = False
            self._index = max(0, self._index - 2)
            self._play_current_and_advance()
        elif key == pygame.K_f:
            self._playing = False
            if self._timeline.final_stretch_index is not None:
                self._index = self._timeline.final_stretch_index
                self._play_current_and_advance()
            else:
                self._audio.speak("No final stretch marker in this replay.", 80)
                self._status = "No final stretch marker"
        elif key == pygame.K_r:
            self._playing = False
            self._replay_last_key_moment()
        elif key == pygame.K_s:
            self._playing = False
            self._export_share()
        return True

    def _update(self, delta_s: float) -> None:
        if not self._playing or not self._timeline.has_events:
            return
        self._time_until_next_s -= delta_s
        if self._time_until_next_s <= 0.0:
            self._play_current_and_advance()
            self._time_until_next_s = PLAYBACK_INTERVAL_S

    def _play_current_and_advance(self) -> None:
        event = self._timeline.event_at(self._index)
        if event is None:
            self._status = "No replay events"
            return
        self._play_event(event)
        if self._index in self._timeline.key_indices:
            self._last_key_index = self._index
        self._index += 1
        if self._index >= len(self._timeline.events):
            self._index = len(self._timeline.events) - 1
            self._playing = False
            self._status = "Replay complete"

    def _replay_last_key_moment(self) -> None:
        key_index = self._last_key_index
        if key_index is None:
            key_index = self._timeline.key_index_at_or_before(self._index)
        if key_index is None:
            self._audio.speak("No key moment in this replay.", 80)
            self._status = "No key moment"
            return
        self._index = key_index
        event = self._timeline.event_at(key_index)
        if event is not None:
            self._play_event(event)
            self._last_key_index = key_index

    def _play_event(self, event: RaceEvent) -> None:
        self._audio_engine.render_events((event,))
        line = replay_line_for_event(event) or event.event_type.replace("_", " ").title()
        self._status = f"{event.timestamp_s:.1f}s - {line}"

    def _export_share(self) -> None:
        bundle = build_last_replay_share_bundle(self._content_root, self._progress)
        if bundle is None:
            self._share_status = "No replay to export. Finish a race first."
            self._status = "No replay share available"
            self._audio.speak(self._share_status, 80)
            return
        result = save_replay_share_bundle(self._project_root, bundle)
        self._share_status = f"Exported {len(result.files)} files to {result.directory}."
        self._status = "Replay share exported"
        self._audio.speak("Replay share exported.", 90)

    def _initial_share_status(self) -> str:
        share_count = len(load_replay_share_index(self._project_root))
        suffix = f" {share_count} saved share(s)." if share_count else ""
        if self._timeline.has_events:
            return f"Press S to export replay share files.{suffix}"
        return f"No replay share is available.{suffix}"

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Audio Replay", True, (248, 240, 205)), (58, 42))
        hint = "Space pause/play | Right step | Left back | F final stretch | R key moment | S share | M/Esc menu"
        screen.blit(small_font.render(hint, True, (245, 220, 130)), (62, 92))
        panel = pygame.Rect(58, 132, 860, 420)
        pygame.draw.rect(screen, (31, 40, 48), panel, border_radius=6)
        pygame.draw.rect(screen, (84, 102, 116), panel, width=2, border_radius=6)
        mode = "playing" if self._playing else "paused"
        count = len(self._timeline.events)
        screen.blit(body_font.render(f"Timeline {mode} - {min(self._index + 1, max(count, 1))}/{max(count, 1)}", True, (246, 238, 210)), (panel.left + 22, panel.top + 20))
        screen.blit(small_font.render(self._status, True, (172, 218, 232)), (panel.left + 24, panel.top + 58))
        screen.blit(small_font.render(self._share_status, True, (245, 220, 130)), (panel.left + 24, panel.bottom - 34))
        for index, line in enumerate(self._visible_lines()):
            screen.blit(small_font.render(line, True, (198, 216, 218)), (panel.left + 24, panel.top + 96 + index * 28))

    def _visible_lines(self) -> tuple[str, ...]:
        if not self._timeline.has_events:
            return tuple(f"{index + 1}. {line}" for index, line in enumerate(self._lines[:12]))
        start = max(0, self._index - 4)
        end = min(len(self._timeline.events), start + 10)
        rows: list[str] = []
        for index in range(start, end):
            event = self._timeline.events[index]
            marker = ">" if index == self._index else " "
            key = "*" if index in self._timeline.key_indices else " "
            line = replay_line_for_event(event) or event.event_type.replace("_", " ").title()
            rows.append(f"{marker}{key} {event.timestamp_s:5.1f}s  {line}")
        return tuple(rows)
