import unittest
import tempfile
import importlib.util
import json
from pathlib import Path

from horse_racing_game.app.localization import (
    AccessibilityLanguagePack,
    CopyPolishRule,
    LocalizationCatalog,
    LocalizedString,
    OnboardingChecklist,
    TutorialScript,
    TutorialStep,
    default_accessibility_language_pack,
    default_localization_catalog,
    default_tutorial_script,
    load_encrypted_localization_catalog,
    localization_catalog_to_dict,
    locale_format,
    write_encrypted_localization_catalog,
)


_BUILD_LANG_PATH = Path(__file__).parent.parent / "scripts" / "build_lang.py"
_SPEC = importlib.util.spec_from_file_location("build_lang", _BUILD_LANG_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BUILD_LANG = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BUILD_LANG)
build_language_files = _BUILD_LANG.build_language_files


class LocalizationTests(unittest.TestCase):
    def test_catalog_renders_translated_ui_and_speech_text(self) -> None:
        catalog = default_localization_catalog()

        self.assertEqual(catalog.text("race.start", "en-US"), "Start.")
        self.assertEqual(catalog.text("race.start", "fr-FR"), "Depart.")
        self.assertEqual(catalog.text("race.finish_rank", "fr-FR", rank=2), "Arrive en position 2.")
        self.assertEqual(catalog.text("race.start", "de-DE"), "Start.")

    def test_encrypted_localization_catalog_round_trips_without_plaintext(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ui.lng"
            catalog = default_localization_catalog()

            write_encrypted_localization_catalog(path, catalog)
            loaded = load_encrypted_localization_catalog(path)

            self.assertEqual(loaded.text("race.finish_rank", "es-ES", rank=3), "Termino en posicion 3.")
            raw = path.read_bytes()
            self.assertNotIn(b"race.finish_rank", raw)
            self.assertNotIn(b"Termino", raw)

    def test_build_language_files_encrypts_source_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "localization"
            output = root / "content" / "lang"
            source.mkdir()
            catalog = default_localization_catalog()
            (source / "ui.json").write_text(
                json.dumps(localization_catalog_to_dict(catalog)),
                encoding="utf-8",
            )

            written = build_language_files(source, output)

            self.assertEqual([path.name for path in written], ["ui.lng"])
            loaded = load_encrypted_localization_catalog(output / "ui.lng")
            self.assertEqual(loaded.text("race.start", "fr-FR"), "Depart.")

    def test_catalog_reports_missing_locale_keys_and_requires_format_values(self) -> None:
        catalog = default_localization_catalog()

        self.assertEqual(catalog.missing_keys_for_locale("es-ES"), ("help.controls", "tutorial.status"))
        with self.assertRaises(ValueError):
            catalog.text("race.finish_rank", "en-US")
        with self.assertRaises(ValueError):
            catalog.text("missing", "en-US")

    def test_locale_format_handles_numbers_distance_and_duration(self) -> None:
        english = locale_format("en-US")
        french = locale_format("fr-FR")
        spanish = locale_format("es-ES")

        self.assertEqual(english.distance(1234.0), "1,234 m")
        self.assertEqual(french.duration(12.5), "12,5 s")
        self.assertEqual(spanish.number(1234.5, 1), "1.234,5")
        with self.assertRaises(ValueError):
            french.number(1.0, -1)

    def test_accessibility_language_pack_applies_phonetic_overrides(self) -> None:
        pack = default_accessibility_language_pack("fr-FR")

        self.assertEqual(pack.pronounce("Ember Stride at Ashford"), "Ember Straide at Acheford")
        self.assertEqual(default_accessibility_language_pack("en-US").screen_reader_hint, "Screen reader active.")
        with self.assertRaises(ValueError):
            AccessibilityLanguagePack("en-US", "rapid")

    def test_tutorial_script_returns_due_steps_once(self) -> None:
        script = default_tutorial_script()

        first = script.due_steps(1.0, set())
        later = script.due_steps(30.0, {step.step_id for step in first})

        self.assertEqual([step.step_id for step in first], ["pace"])
        self.assertEqual([step.step_id for step in later], ["status"])
        with self.assertRaises(ValueError):
            TutorialScript("bad", (TutorialStep("same", "a", 0.0), TutorialStep("same", "b", 1.0)))

    def test_onboarding_checklist_tracks_completion(self) -> None:
        checklist = OnboardingChecklist("new-player", ("onboarding.first_race", "help.controls"))

        updated = checklist.mark_complete("onboarding.first_race")

        self.assertEqual(checklist.completion_fraction, 0.0)
        self.assertEqual(updated.completion_fraction, 0.5)
        self.assertIs(updated.mark_complete("onboarding.first_race"), updated)
        with self.assertRaises(ValueError):
            checklist.mark_complete("missing")

    def test_copy_polish_flags_and_normalizes_problematic_copy(self) -> None:
        rule = CopyPolishRule(max_words=5)
        text = "  Click here   simply to start this obvious long sentence!! "

        issues = rule.issues(text)
        polished = rule.polished(text)

        self.assertIn("banned phrase: click here", issues)
        self.assertIn("banned phrase: simply", issues)
        self.assertIn("too many words", issues)
        self.assertIn("overexcited punctuation", issues)
        self.assertEqual(polished, "to start this obvious long sentence.")

    def test_invalid_localization_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LocalizedString("", {"en-US": "Text"})
        with self.assertRaises(ValueError):
            LocalizedString("key", {"de-DE": "Text"})
        with self.assertRaises(ValueError):
            LocalizationCatalog((LocalizedString("key", {"en-US": "One"}), LocalizedString("key", {"en-US": "Two"})))
        with self.assertRaises(ValueError):
            OnboardingChecklist("bad", ())
        with self.assertRaises(ValueError):
            CopyPolishRule(max_words=0)


if __name__ == "__main__":
    unittest.main()
