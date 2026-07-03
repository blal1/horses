import unittest

import horse_racing_game.app.pygame_main as pygame_main
import horse_racing_game.app.realtime_game as realtime_game


class RealtimeGameEntrypointTests(unittest.TestCase):
    def test_legacy_realtime_module_delegates_to_pygame(self) -> None:
        self.assertIs(realtime_game.main, pygame_main.main)


if __name__ == "__main__":
    unittest.main()