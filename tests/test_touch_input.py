import unittest

from horse_racing_game.input.touch import TouchGesture, TouchGestureProfile, default_android_gesture_profile


class TouchInputTests(unittest.TestCase):
    def test_drag_maps_to_analog_pace_and_steering(self) -> None:
        profile = default_android_gesture_profile()

        command = profile.command_for(TouchGesture("drag", 100.0, 220.0, 180.0, 60.0, 0.25))

        self.assertAlmostEqual(command.lateral_delta, 0.5)
        self.assertAlmostEqual(command.throttle_delta, 1.0)
        self.assertEqual(profile.action_for(TouchGesture("drag", 100.0, 100.0, 40.0, 100.0, 0.1)), "steer")

    def test_small_drag_deadzone_prevents_accidental_input(self) -> None:
        profile = TouchGestureProfile(axis_full_scale_px=160.0, analog_deadzone=0.2)

        command = profile.command_for(TouchGesture("drag", 100.0, 100.0, 110.0, 92.0, 0.1))

        self.assertEqual(command.lateral_delta, 0.0)
        self.assertEqual(command.throttle_delta, 0.0)
        self.assertEqual(profile.action_for(TouchGesture("tap", 100.0, 100.0, 100.0, 100.0, 0.05, tap_count=1)), "none")

    def test_accessible_taps_map_to_push_and_status(self) -> None:
        profile = default_android_gesture_profile()

        push = profile.command_for(TouchGesture("tap", 100.0, 100.0, 100.0, 100.0, 0.18, tap_count=2))
        two_finger_status = profile.command_for(TouchGesture("tap", 100.0, 100.0, 100.0, 100.0, 0.1, pointers=2, tap_count=1))
        long_press_status = profile.command_for(TouchGesture("long_press", 100.0, 100.0, 100.0, 100.0, 0.6))

        self.assertTrue(push.push_requested)
        self.assertTrue(two_finger_status.request_status)
        self.assertTrue(long_press_status.request_status)

    def test_swipes_map_to_jump_duck_and_steer(self) -> None:
        profile = default_android_gesture_profile()

        jump = profile.command_for(TouchGesture("swipe", 100.0, 160.0, 100.0, 60.0, 0.12))
        duck = profile.command_for(TouchGesture("swipe", 100.0, 60.0, 100.0, 160.0, 0.12))
        steer = profile.command_for(TouchGesture("swipe", 100.0, 100.0, 20.0, 100.0, 0.12))

        self.assertTrue(jump.jump_requested)
        self.assertTrue(duck.duck_requested)
        self.assertLess(steer.lateral_delta, 0.0)

    def test_invalid_touch_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TouchGesture("pinch", 0.0, 0.0, 0.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            TouchGesture("tap", 0.0, 0.0, 0.0, 0.0, -0.1)
        with self.assertRaises(ValueError):
            TouchGestureProfile(axis_full_scale_px=0.0)


if __name__ == "__main__":
    unittest.main()
