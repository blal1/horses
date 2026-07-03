import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from horse_racing_game.app.bootstrap import build_quick_race_services
from horse_racing_game.app.config import AppConfig
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.ui.pygame_game import PygameRaceGame, TUTORIAL_MESSAGES, _Fonts


class PygameSmokeTests(unittest.TestCase):
    def test_race_screen_draws_a_pygame_frame(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", tick_hz=60, max_race_seconds=5.0)
        services = build_quick_race_services(config)
        game = PygameRaceGame(config, services)

        pygame.init()
        try:
            screen = pygame.Surface((1180, 720))
            fonts = _Fonts(
                title=pygame.font.Font(None, 44),
                body=pygame.font.Font(None, 28),
                small=pygame.font.Font(None, 22),
            )
            state = services.race_engine.tick(RaceCommand(request_status=True), config.tick_seconds).state

            game._draw(screen, fonts, state)

            self.assertNotEqual(screen.get_at((10, 10))[:3], (0, 0, 0))
            self.assertNotEqual(screen.get_at((900, 100))[:3], (0, 0, 0))
        finally:
            pygame.quit()

    def test_race_screen_respects_max_race_seconds(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(
            content_root=root / "content",
            tick_hz=120,
            max_race_seconds=0.05,
        )
        game = PygameRaceGame(config, build_quick_race_services(config))

        result = game.run()

        self.assertFalse(result.state.is_finished)
        self.assertGreaterEqual(result.state.elapsed_s, config.max_race_seconds)
        self.assertLess(result.ticks, 60)

    def test_training_mode_does_not_play_weather_ambient(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(
            content_root=root / "content",
            weather_id="windy",
            tick_hz=120,
            max_race_seconds=0.05,
        )
        services = build_quick_race_services(config)
        game = PygameRaceGame(config, services, training_mode=True)

        game.run()

        played_ids = [call.sound_id for call in services.audio_backend.calls if call.method == "play_2d"]
        self.assertNotIn("mixkit_wind_2608", played_ids)

    def test_race_screen_key_actions_return_next_action(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", tick_hz=60, max_race_seconds=5.0)
        game = PygameRaceGame(config, build_quick_race_services(config))

        self.assertEqual(game._handle_keydown(pygame.K_m, True, "quit"), (False, "menu"))
        self.assertEqual(game._handle_keydown(pygame.K_n, True, "quit"), (False, "restart"))
        self.assertEqual(game._handle_keydown(pygame.K_ESCAPE, True, "menu"), (False, "quit"))
        self.assertEqual(game._handle_keydown(pygame.K_q, True, "menu"), (True, "menu"))

    def test_tutorial_mode_speaks_guidance_once_per_step(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", tick_hz=60, max_race_seconds=5.0)
        services = build_quick_race_services(config)
        game = PygameRaceGame(config, services, tutorial_mode=True)

        game._update_tutorial(0.0)
        final_trigger_s = TUTORIAL_MESSAGES[-1][0]
        game._update_tutorial(final_trigger_s)
        game._update_tutorial(final_trigger_s)

        spoken = [call.text for call in services.audio_backend.calls if call.method == "speak"]
        self.assertEqual(spoken, [message for _, message in TUTORIAL_MESSAGES])

    def test_tutorial_messages_cover_release_candidate_audio_topics(self) -> None:
        script = " ".join(message.lower() for _, message in TUTORIAL_MESSAGES)

        for topic in (
            "pacing",
            "stamina",
            "recovery",
            "turn",
            "obstacle radar",
            "jump timing",
            "duck timing",
            "replay controls",
            "mobile",
            "swipe up",
            "swipe down",
        ):
            with self.subTest(topic=topic):
                self.assertIn(topic, script)

    def test_intro_message_is_spoken_and_logged_to_messages(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", tick_hz=60, max_race_seconds=5.0)
        services = build_quick_race_services(config)
        game = PygameRaceGame(config, services, intro_message="Career race 1 of 3. 0 points.")

        game._announce_intro()

        spoken = [call.text for call in services.audio_backend.calls if call.method == "speak"]
        self.assertIn("Career race 1 of 3. 0 points.", spoken)

    def test_rival_event_speaks_narrative_line_once(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", tick_hz=60, max_race_seconds=5.0)
        services = build_quick_race_services(config)
        game = PygameRaceGame(config, services)
        event = RaceEvent(
            event_type="opponent_approaching",
            priority=60,
            timestamp_s=1.0,
            subject_id="copper_gate",
            data={"forward_m": -2.0, "right_m": 0.3, "horse_name": "Copper Gate"},
        )

        game._speak_rival_events((event,))
        game._speak_rival_events((event,))

        spoken = [call.text for call in services.audio_backend.calls if call.method == "speak"]
        self.assertEqual(spoken, ["Copper Gate is pressing on your shoulder."])


if __name__ == "__main__":
    unittest.main()
