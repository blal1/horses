import os
from pathlib import Path

import pygame

from horse_racing_game.app.championship import (
    championship_rival_stables,
    compute_standings,
    load_championship_calendar,
    next_championship_race,
    standings_text,
)
from horse_racing_game.app.career_result_feedback import career_result_summary_lines
from horse_racing_game.app.progress import GameProgress
from horse_racing_game.app.stats import compute_player_stats, stats_summary_text
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.content.loaders import load_rivals, load_sound_catalog, load_stables


class PygameStatsScreen:
    def __init__(self, content_root: Path, project_root: Path, progress: GameProgress) -> None:
        self._content_root = content_root
        self._project_root = project_root
        self._progress = progress
        catalog = load_sound_catalog(content_root / "sound_manifest.json")
        self._audio = PygameAudioBackend(project_root, catalog)

    def run(self) -> None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "centered")
        pygame.init()
        screen = pygame.display.set_mode((980, 640), pygame.SHOWN)
        pygame.display.set_caption("Horse Racing - Statistics")
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
                    running = False

            self._draw(screen, title_font, body_font, small_font)
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()

    def _handle_key(self, key: int) -> bool:
        if key == pygame.K_r:
            self._audio.speak(self._spoken_summary(), 90)
            return True
        return False

    def _spoken_summary(self) -> str:
        return f"Statistics. {stats_summary_text(compute_player_stats(self._progress))} Standings. {standings_text(self._standings())}"

    def _stats_lines(self) -> tuple[str, ...]:
        stats = compute_player_stats(self._progress)
        best = "none" if stats.best_rank is None else str(stats.best_rank)
        online_summary = "none"
        if stats.last_online_race_summary is not None:
            summary = stats.last_online_race_summary
            online_summary = (
                f"rank {summary.get('rank', '?')} | "
                f"ticks {summary.get('ticks', '?')} | "
                f"distance {summary.get('distance_m', '?')} m"
            )
        career_summary = "none"
        if stats.last_career_result_summary is not None:
            career_summary = career_result_summary_lines(stats.last_career_result_summary)[1]
        return (
            f"Total sessions: {stats.total_races}",
            f"Quick races: {stats.quick_races}",
            f"Career races: {stats.career_races}/{len(load_championship_calendar(self._content_root / 'championship.json'))}",
            f"Training levels earned: {stats.training_sessions}",
            f"Wins: {stats.wins} | Podiums: {stats.podiums} | Best rank: {best}",
            f"Win rate: {stats.win_rate_percent}%",
            f"Career points: {stats.career_points}",
            f"Career energy: {stats.career_energy} | Rewards: {stats.career_rewards}",
            f"Current stable: {stats.stable_id}",
            f"Quick difficulty: {stats.difficulty_id}",
            f"Trained horses: {stats.trained_horses}",
            f"Rivals encountered: {stats.rivals_encountered}",
            f"Last career result: {career_summary}",
            f"Last online race: {online_summary}",
            self._next_race_line(),
        )

    def _standing_lines(self) -> tuple[str, ...]:
        return tuple(
            f"{index + 1}. {row.name} - {row.points} pts ({row.races_run} races) - {row.stable_name}"
            for index, row in enumerate(self._standings())
        )

    def _standings(self):
        rivals = load_rivals(self._content_root / "rivals.json")
        stables = load_stables(self._content_root / "stables.json")
        calendar = load_championship_calendar(self._content_root / "championship.json")
        return compute_standings(
            "You",
            self._progress.career_points,
            self._progress.career_races_completed,
            rivals,
            self._progress.rival_championship_points,
            self._progress.rival_championship_races,
            championship_rival_stables(calendar),
            stables,
        )

    def _next_race_line(self) -> str:
        calendar = load_championship_calendar(self._content_root / "championship.json")
        next_race = next_championship_race(calendar, self._progress.career_races_completed)
        if next_race is None:
            return "Next championship race: complete"
        return f"Next race: {next_race.name} on {next_race.track_id}, weather {next_race.weather_id}"

    def _draw(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        screen.fill((18, 24, 30))
        screen.blit(title_font.render("Statistics", True, (248, 240, 205)), (58, 42))
        screen.blit(small_font.render("R repeats summary | any other key or click returns to menu", True, (245, 220, 130)), (62, 92))

        left = pygame.Rect(58, 132, 410, 430)
        right = pygame.Rect(510, 132, 410, 430)
        for rect, title in ((left, "Player"), (right, "Championship")):
            pygame.draw.rect(screen, (31, 40, 48), rect, border_radius=6)
            pygame.draw.rect(screen, (84, 102, 116), rect, width=2, border_radius=6)
            screen.blit(body_font.render(title, True, (246, 238, 210)), (rect.left + 20, rect.top + 18))

        for index, line in enumerate(self._stats_lines()):
            screen.blit(small_font.render(line, True, (198, 216, 218)), (left.left + 22, left.top + 64 + index * 34))
        for index, line in enumerate(self._standing_lines()[:10]):
            screen.blit(small_font.render(line, True, (198, 216, 218)), (right.left + 22, right.top + 64 + index * 34))
