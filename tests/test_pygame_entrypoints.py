import unittest
import subprocess
import tempfile
from pathlib import Path

import c
import play_game
import horse_racing_game.__main__ as package_main
import horse_racing_game.app.keyboard_main as keyboard_main
import horse_racing_game.app.main as app_main
import horse_racing_game.app.pygame_main as pygame_main


PROJECT_ROOT = Path(__file__).parent.parent


class PygameEntrypointTests(unittest.TestCase):
    def test_user_facing_entrypoints_all_launch_pygame_main(self) -> None:
        self.assertIs(c.main, pygame_main.main)
        self.assertIs(play_game.main, pygame_main.main)
        self.assertIs(package_main.main, pygame_main.main)
        self.assertIs(app_main.main, pygame_main.main)
        self.assertIs(keyboard_main.main, pygame_main.main)

    def test_pygame_main_smoke_content_runs_headless(self) -> None:
        result = subprocess.run(
            ["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-content"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("content ok", result.stdout)

    def test_pygame_main_smoke_race_replay_speech_and_save_run_headless(self) -> None:
        commands = (
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-race"], "race ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-replay"], "replay ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-replay-share"], "replay share ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-replay-library"], "replay library ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-time-trial"], "time trial ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-ghost"], "ghost ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-settings"], "settings ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-profile"], "profile ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-track-catalog"], "track catalog ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-social-graph"], "social graph ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-community"], "community ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-chat-session"], "chat session ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-live-ops"], "live ops ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-diagnostics"], "diagnostics ok"),
            (["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-speech"], "speech ok"),
        )
        for command, expected in commands:
            with self.subTest(command=command):
                result = subprocess.run(command, cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
                self.assertIn(expected, result.stdout)

        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["python", "-m", "horse_racing_game.app.pygame_main", "--smoke-save", directory],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("save ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
