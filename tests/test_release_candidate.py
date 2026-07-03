import json
import subprocess
import unittest
from pathlib import Path

from horse_racing_game.app.release_candidate import (
    ReleaseCandidateReadiness,
    ReleaseCandidateScope,
    android_debug_build_environment,
    release_candidate_readiness,
    validate_vertical_slice_release_candidate,
    vertical_slice_release_candidate_scope,
)


PROJECT_ROOT = Path(__file__).parent.parent


class ReleaseCandidateTests(unittest.TestCase):
    def test_vertical_slice_scope_defines_modes_builds_and_deferred_features(self) -> None:
        scope = vertical_slice_release_candidate_scope()

        self.assertEqual(scope.scope_id, "vertical-slice-rc")
        self.assertEqual(scope.modes, ("quick_race", "short_career", "training", "replay"))
        self.assertEqual(scope.builds, ("windows_desktop", "android_debug"))
        self.assertIn("quick_race_finish", scope.smoke_checks)
        self.assertTrue(scope.includes_mode("training"))
        self.assertTrue(scope.includes_build("android_debug"))
        self.assertTrue(scope.defers_feature("ranked_ladder"))
        self.assertFalse(scope.includes_mode("ranked"))

    def test_readiness_reports_missing_scope_items(self) -> None:
        readiness = release_candidate_readiness(
            completed_modes={"quick_race"},
            completed_builds={"windows_desktop"},
            passed_smoke_checks={"launch", "quick_race_finish"},
        )

        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.missing_modes, ("short_career", "training", "replay"))
        self.assertEqual(readiness.missing_builds, ("android_debug",))
        self.assertIn("short_career", readiness.summary())

    def test_readiness_accepts_complete_scope(self) -> None:
        scope = vertical_slice_release_candidate_scope()

        readiness = release_candidate_readiness(set(scope.modes), set(scope.builds), set(scope.smoke_checks), scope)

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.summary(), "vertical-slice-rc: ready for release-candidate validation.")

    def test_headless_validation_completes_playable_modes_and_marks_missing_artifacts(self) -> None:
        validation = validate_vertical_slice_release_candidate(PROJECT_ROOT)
        windows_artifact_present = (
            PROJECT_ROOT / "dist" / "stable" / "horse-racing-audio-first-0.1.0-windows-x64.zip"
        ).is_file()
        android_artifact_present = (
            PROJECT_ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
        ).is_file()

        self.assertEqual(validation.ready, windows_artifact_present and android_artifact_present)
        self.assertTrue(validation.checks["launch"])
        self.assertTrue(validation.checks["quick_race_finish"])
        self.assertTrue(validation.checks["short_career_save"])
        self.assertTrue(validation.checks["training_complete"])
        self.assertTrue(validation.checks["replay_load"])
        self.assertEqual(validation.checks["windows_artifact"], windows_artifact_present)
        self.assertEqual(validation.checks["android_debug_artifact"], android_artifact_present)
        self.assertEqual(validation.readiness.missing_modes, ())
        expected_missing_builds = tuple(
            build
            for build, present in (
                ("windows_desktop", windows_artifact_present),
                ("android_debug", android_artifact_present),
            )
            if not present
        )
        expected_missing_checks = tuple(
            check
            for check, present in (
                ("windows_artifact", windows_artifact_present),
                ("android_debug_artifact", android_artifact_present),
            )
            if not present
        )
        self.assertEqual(validation.readiness.missing_builds, expected_missing_builds)
        self.assertEqual(validation.readiness.missing_smoke_checks, expected_missing_checks)
        self.assertIn("gradle_wrapper=", validation.details["android_debug_environment"])

    def test_android_debug_build_environment_reports_tooling_state(self) -> None:
        environment = android_debug_build_environment(PROJECT_ROOT)

        self.assertEqual(environment["android_root"], str(PROJECT_ROOT / "android"))
        self.assertIn("gradle_wrapper", environment)
        self.assertIn("java_on_path", environment)
        self.assertIn("sdk_root_exists", environment)
        self.assertIn("assemble_debug_command", environment)

    def test_invalid_release_candidate_values_are_rejected(self) -> None:
        scope = vertical_slice_release_candidate_scope()

        with self.assertRaises(ValueError):
            ReleaseCandidateScope("", ("quick_race",), ("windows_desktop",), ("launch",), ())
        with self.assertRaises(ValueError):
            ReleaseCandidateScope("rc", ("quick_race", "quick_race"), ("windows_desktop",), ("launch",), ())
        with self.assertRaises(ValueError):
            ReleaseCandidateReadiness(scope, frozenset({"ranked"}), frozenset(), frozenset())
        with self.assertRaises(ValueError):
            ReleaseCandidateReadiness(scope, frozenset(), frozenset({"linux"}), frozenset())
        with self.assertRaises(ValueError):
            ReleaseCandidateReadiness(scope, frozenset(), frozenset(), frozenset({"unknown"}))

    def test_validate_release_candidate_script_outputs_json_and_nonzero_when_incomplete(self) -> None:
        result = subprocess.run(
            [
                "python",
                "scripts/validate_release_candidate.py",
                "--completed-modes",
                "quick_race",
                "--completed-builds",
                "windows_desktop",
                "--passed-smoke-checks",
                "launch,quick_race_finish",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["missing_builds"], ["android_debug"])
        self.assertIn("short_career", payload["missing_modes"])
        self.assertIn("ranked_ladder", payload["deferred_features"])

    def test_validate_release_candidate_script_returns_zero_when_complete(self) -> None:
        scope = vertical_slice_release_candidate_scope()
        result = subprocess.run(
            [
                "python",
                "scripts/validate_release_candidate.py",
                "--completed-modes",
                ",".join(scope.modes),
                "--completed-builds",
                ",".join(scope.builds),
                "--passed-smoke-checks",
                ",".join(scope.smoke_checks),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["missing_modes"], [])

    def test_validate_release_candidate_script_can_run_headless_slice_checks(self) -> None:
        windows_artifact_present = (
            PROJECT_ROOT / "dist" / "stable" / "horse-racing-audio-first-0.1.0-windows-x64.zip"
        ).is_file()
        android_artifact_present = (
            PROJECT_ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
        ).is_file()
        result = subprocess.run(
            [
                "python",
                "scripts/validate_release_candidate.py",
                "--run-headless",
                "--project-root",
                str(PROJECT_ROOT),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        ready = windows_artifact_present and android_artifact_present
        self.assertEqual(result.returncode, 0 if ready else 1)
        self.assertEqual(payload["missing_modes"], [])
        expected_missing_builds = [
            build
            for build, present in (
                ("windows_desktop", windows_artifact_present),
                ("android_debug", android_artifact_present),
            )
            if not present
        ]
        self.assertEqual(payload["missing_builds"], expected_missing_builds)
        self.assertTrue(payload["checks"]["quick_race_finish"])
        self.assertTrue(payload["checks"]["short_career_save"])
        self.assertTrue(payload["checks"]["training_complete"])
        self.assertTrue(payload["checks"]["replay_load"])
        self.assertEqual(payload["checks"]["windows_artifact"], windows_artifact_present)
        self.assertIn("android_debug_environment", payload["details"])


if __name__ == "__main__":
    unittest.main()
