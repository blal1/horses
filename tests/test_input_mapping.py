import unittest

import horse_racing_game.app.pygame_main as pygame_main
import horse_racing_game.input.command_mapper as command_mapper
import horse_racing_game.input.keyboard_backend as keyboard_backend


class InputEntrypointTests(unittest.TestCase):
    def test_legacy_input_modules_delegate_to_pygame(self) -> None:
        self.assertIs(command_mapper.main, pygame_main.main)
        self.assertIs(keyboard_backend.main, pygame_main.main)


if __name__ == "__main__":
    unittest.main()