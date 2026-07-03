import unittest
from pathlib import Path

from horse_racing_game.app.bootstrap import build_quick_race_services
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.game_app import GameApp
from horse_racing_game.content.loaders import load_tracks, load_weather
from horse_racing_game.input.commands import RaceCommand


def _root() -> Path:
    return Path(__file__).parent.parent


def _run(track_id: str, commands) -> "QuickRaceResult":  # noqa: F821
    config = AppConfig(content_root=_root() / "content", track_id=track_id, tick_hz=4, max_race_seconds=300.0)
    app = GameApp(config, build_quick_race_services(config))
    return app.run_quick_race(commands)


def _run_weather(track_id: str, weather_id: str) -> "QuickRaceResult":  # noqa: F821
    config = AppConfig(
        content_root=_root() / "content",
        track_id=track_id,
        weather_id=weather_id,
        tick_hz=4,
        max_race_seconds=300.0,
    )
    app = GameApp(config, build_quick_race_services(config))
    return app.run_quick_race()


def _official_track_ids() -> tuple[str, ...]:
    return tuple(
        track.track_id
        for track in load_tracks(_root() / "content" / "tracks.json")
        if track.track_id != "audio_obstacle_lab"
    )


def _weather_ids() -> tuple[str, ...]:
    return tuple(weather.weather_id for weather in load_weather(_root() / "content" / "weather.json"))


class RaceBalanceTests(unittest.TestCase):
    def test_full_race_finishes_on_both_tracks(self) -> None:
        for track_id in ("ashford_oval", "bracken_dirt"):
            with self.subTest(track=track_id):
                result = _run(track_id, None)
                self.assertTrue(result.state.is_finished, f"race did not finish on {track_id}")
                leader = max(result.state.runners, key=lambda r: r.distance_m)
                self.assertGreaterEqual(leader.distance_m, 0.0)

    def test_opponents_keep_race_close_under_default_driver(self) -> None:
        result = _run("ashford_oval", None)
        self.assertTrue(result.state.is_finished)
        player = result.state.player()
        ordered = sorted(result.state.runners, key=lambda r: r.rank)
        leader, last = ordered[0], ordered[-1]
        # the field must stay bunched — no runner hopelessly dropped
        self.assertLess(leader.distance_m - last.distance_m, 250.0)
        # and the player must not lap the entire field (competitive, not trivial)
        self.assertLess(player.distance_m - last.distance_m, 250.0)

    def test_passive_player_does_not_dominate(self) -> None:
        # a player who never touches the controls must not win — opponents compete
        passive = [RaceCommand() for _ in range(2000)]
        result = _run("ashford_oval", passive)
        player = result.state.player()
        self.assertGreater(player.rank, 1, "passive player should not win the race")

    def test_stamina_runs_out_under_constant_sprint(self) -> None:
        sprint = [RaceCommand(throttle_delta=1.0, push_requested=True) for _ in range(2000)]
        result = _run("ashford_oval", sprint)
        self.assertLess(result.state.player().stamina, 20.0)

    def test_default_driver_stays_inside_balance_envelopes_across_content(self) -> None:
        for track_id in _official_track_ids():
            for weather_id in _weather_ids():
                with self.subTest(track=track_id, weather=weather_id):
                    result = _run_weather(track_id, weather_id)
                    player = result.state.player()
                    ordered = sorted(result.state.runners, key=lambda runner: runner.rank)
                    field_spread = ordered[0].distance_m - ordered[-1].distance_m

                    self.assertTrue(result.state.is_finished)
                    self.assertGreaterEqual(result.state.elapsed_s, 70.0)
                    self.assertLessEqual(result.state.elapsed_s, 150.0)
                    self.assertGreaterEqual(player.stamina, 5.0)
                    self.assertLessEqual(player.stamina, 25.0)
                    self.assertLess(field_spread, 180.0)
                    self.assertLessEqual(player.rank, len(result.state.runners))

    def test_rain_is_slower_than_clear_for_default_driver(self) -> None:
        for track_id in _official_track_ids():
            with self.subTest(track=track_id):
                clear = _run_weather(track_id, "clear")
                rain = _run_weather(track_id, "rain")

                self.assertTrue(clear.state.is_finished)
                self.assertTrue(rain.state.is_finished)
                self.assertGreater(rain.state.elapsed_s, clear.state.elapsed_s)


if __name__ == "__main__":
    unittest.main()
