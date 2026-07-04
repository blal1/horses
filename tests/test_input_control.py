import unittest

import pygame

from horse_racing_game.input.events import DEFAULT_CONTROL_SCHEME, KeyboardControlState, MULTIPLAYER_GUEST_SCHEME
from horse_racing_game.input.key_hold import KeyHoldTracker
from horse_racing_game.ui.menu_models import MENU_ROW_COUNT


class KeyHoldTrackerTests(unittest.TestCase):
    def test_hold_strength_ramps_up_with_time(self) -> None:
        tracker = KeyHoldTracker()
        tracker.advance(0.05, {pygame.K_UP})
        short = tracker.strength(pygame.K_UP)
        tracker.advance(0.20, {pygame.K_UP})
        long = tracker.strength(pygame.K_UP)

        self.assertGreater(long, short)
        self.assertGreater(long, 0.9)


class KeyboardControlStateTests(unittest.TestCase):
    def test_default_control_scheme_matches_solo_key_map(self) -> None:
        self.assertEqual(DEFAULT_CONTROL_SCHEME.throttle_up, (pygame.K_UP, pygame.K_z))
        self.assertEqual(DEFAULT_CONTROL_SCHEME.throttle_down, (pygame.K_DOWN, pygame.K_s))
        self.assertEqual(DEFAULT_CONTROL_SCHEME.lateral_left, (pygame.K_LEFT, pygame.K_q))
        self.assertEqual(DEFAULT_CONTROL_SCHEME.lateral_right, (pygame.K_RIGHT, pygame.K_d))
        self.assertEqual(DEFAULT_CONTROL_SCHEME.push, (pygame.K_j,))
        self.assertEqual(DEFAULT_CONTROL_SCHEME.jump, (pygame.K_SPACE,))
        self.assertEqual(DEFAULT_CONTROL_SCHEME.duck, (pygame.K_LCTRL, pygame.K_RCTRL))
        self.assertEqual(DEFAULT_CONTROL_SCHEME.status, (pygame.K_TAB,))

    def test_lateral_input_decays_after_release(self) -> None:
        state = KeyboardControlState()
        state.key_down(pygame.K_RIGHT)
        state.advance(0.20)
        held = state.command().lateral_delta
        state.key_up(pygame.K_RIGHT)
        state.advance(0.20)
        decayed = state.command().lateral_delta

        self.assertGreater(held, 0.0)
        self.assertGreater(decayed, 0.0)
        self.assertLess(decayed, held)

    def test_keyboard_state_reports_pressed_actions(self) -> None:
        state = KeyboardControlState()
        state.key_down(pygame.K_SPACE)
        state.key_down(pygame.K_j)

        command = state.command()

        self.assertTrue(command.push_requested)
        self.assertTrue(command.jump_requested)

    def test_guest_scheme_uses_non_overlapping_keys(self) -> None:
        state = KeyboardControlState(control_scheme=MULTIPLAYER_GUEST_SCHEME)
        state.key_down(pygame.K_t)
        state.key_down(pygame.K_f)
        state.advance(0.25)

        command = state.command()

        self.assertGreater(command.throttle_delta, 0.0)
        self.assertLess(command.lateral_delta, 0.0)


class MenuModelTests(unittest.TestCase):
    def test_menu_includes_profile_time_trial_ghost_and_multiplayer_rows(self) -> None:
        self.assertEqual(MENU_ROW_COUNT, 20)


if __name__ == "__main__":
    unittest.main()
