import unittest

from horse_racing_game.app.accessibility import (
    AccessibilitySettings,
    AnnouncerProfile,
    SpeechFilter,
    VoiceMacro,
    default_accessibility_settings,
)


class AccessibilityTests(unittest.TestCase):
    def test_speech_filter_allows_enabled_groups_above_priority(self) -> None:
        speech_filter = SpeechFilter(("status", "results"), minimum_priority=50)

        self.assertTrue(speech_filter.allows("status", 50))
        self.assertFalse(speech_filter.allows("status", 49))
        self.assertFalse(speech_filter.allows("pace", 90))

    def test_default_profiles_set_verbosity_and_details(self) -> None:
        minimal = default_accessibility_settings("minimal")
        detailed = default_accessibility_settings("detailed")

        self.assertEqual(minimal.announcer.verbosity, "minimal")
        self.assertFalse(minimal.announcer.pace_detail)
        self.assertTrue(detailed.haptics_enabled)
        self.assertTrue(detailed.should_speak("pace", 0))

    def test_settings_can_change_verbosity_and_add_unique_voice_macros(self) -> None:
        settings = AccessibilitySettings()
        settings = settings.with_verbosity("detailed")
        settings = settings.add_voice_macro(VoiceMacro("repeat", "Repeat status.", "accessibility"))
        settings = settings.add_voice_macro(VoiceMacro("repeat", "Repeat that.", "accessibility"))

        self.assertEqual(settings.announcer.verbosity, "detailed")
        self.assertEqual(len(settings.voice_macros), 1)
        self.assertEqual(settings.voice_macros[0].phrase, "Repeat that.")

    def test_controller_prompt_reflects_navigation_mode(self) -> None:
        settings = AccessibilitySettings(controller_only_navigation=True)

        self.assertIn("Controller navigation enabled", settings.controller_prompt())
        self.assertIn("Keyboard and controller", AccessibilitySettings().controller_prompt())

    def test_invalid_accessibility_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SpeechFilter(("unknown",))
        with self.assertRaises(ValueError):
            SpeechFilter(minimum_priority=-1)
        with self.assertRaises(ValueError):
            AnnouncerProfile("", "Standard")
        with self.assertRaises(ValueError):
            AnnouncerProfile("standard", "Standard", "verbose")
        with self.assertRaises(ValueError):
            VoiceMacro("", "Repeat")
        with self.assertRaises(ValueError):
            VoiceMacro("repeat", " ")
        with self.assertRaises(ValueError):
            AccessibilitySettings(hold_to_speak_ms=-1)
        with self.assertRaises(ValueError):
            AccessibilitySettings(voice_macros=(VoiceMacro("repeat", "A"), VoiceMacro("repeat", "B")))
        with self.assertRaises(ValueError):
            AccessibilitySettings().add_voice_macro(VoiceMacro("repeat", "A"), limit=0)


if __name__ == "__main__":
    unittest.main()
