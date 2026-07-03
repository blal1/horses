import unittest
from pathlib import Path

from horse_racing_game.app.platform_support import (
    ControllerBinding,
    ControlRemapProfile,
    PackageManifest,
    PlatformTarget,
    SaveSyncRecord,
    UpdateManifest,
    decide_save_sync,
    default_controller_profile,
    default_package_manifest,
    platform_save_root,
)


class PlatformSupportTests(unittest.TestCase):
    def test_default_package_manifest_targets_desktop_platforms(self) -> None:
        manifest = default_package_manifest("0.2.0")

        self.assertEqual(manifest.entry_point, "horse-racing-game")
        self.assertEqual(
            manifest.artifact_names(),
            (
                "horse-racing-audio-first-0.2.0-windows-x64.zip",
                "horse-racing-audio-first-0.2.0-linux-x64.tar.gz",
                "horse-racing-audio-first-0.2.0-macos-arm64.zip",
            ),
        )

    def test_platform_target_rejects_invalid_format_for_platform(self) -> None:
        self.assertEqual(PlatformTarget("linux", "x64", "appimage").artifact_suffix, "linux-x64.appimage")
        self.assertEqual(PlatformTarget("android", "arm64-v8a", "aab").artifact_suffix, "android-arm64-v8a.aab")
        with self.assertRaises(ValueError):
            PlatformTarget("windows", "x64", "appimage")
        with self.assertRaises(ValueError):
            PlatformTarget("freebsd")

    def test_package_manifest_requires_target_and_paths(self) -> None:
        with self.assertRaises(ValueError):
            PackageManifest("Game", "1.0.0", "entry", ())
        with self.assertRaises(ValueError):
            PackageManifest("Game", "1.0.0", "entry", (PlatformTarget("windows"),), include_paths=("",))

    def test_controller_profile_maps_actions_to_race_command(self) -> None:
        profile = default_controller_profile()

        command = profile.command_from_actions({"throttle_up", "steer_left", "push", "status"})

        self.assertEqual(command.throttle_delta, 1.0)
        self.assertEqual(command.lateral_delta, -1.0)
        self.assertTrue(command.push_requested)
        self.assertTrue(command.request_status)
        self.assertEqual(profile.control_for("jump"), "east_button")

    def test_controller_profile_can_be_remapped_without_duplicate_actions(self) -> None:
        profile = default_controller_profile().with_binding("jump", "right_bumper")

        self.assertEqual(profile.control_for("jump"), "right_bumper")
        with self.assertRaises(ValueError):
            ControlRemapProfile(
                "bad",
                (ControllerBinding("jump", "a"), ControllerBinding("jump", "b")),
            )
        with self.assertRaises(ValueError):
            profile.command_from_actions({"unknown"})

    def test_platform_save_roots_follow_os_conventions(self) -> None:
        home = Path("/home/player")

        self.assertEqual(platform_save_root(home, "HorseGame", "linux"), Path("/home/player/.local/share/HorseGame"))
        self.assertEqual(
            platform_save_root(Path("C:/Users/player"), "HorseGame", "windows"),
            Path("C:/Users/player/AppData/Roaming/HorseGame"),
        )
        self.assertEqual(
            platform_save_root(home, "HorseGame", "macos"),
            Path("/home/player/Library/Application Support/HorseGame"),
        )
        self.assertEqual(
            platform_save_root(home, "HorseGame", "android"),
            Path("/home/player/Android/data/com.horseracing.audiofirst/files/HorseGame"),
        )
        with self.assertRaises(ValueError):
            platform_save_root(home, "HorseGame", "freebsd")

    def test_save_sync_decision_prefers_revision_then_conflict_time(self) -> None:
        local = SaveSyncRecord("laptop", 3, 20.0, "local")
        older_remote = SaveSyncRecord("desktop", 2, 99.0, "remote")
        newer_remote = SaveSyncRecord("desktop", 4, 10.0, "remote")
        same_remote = SaveSyncRecord("desktop", 3, 99.0, "local")
        conflict_remote = SaveSyncRecord("desktop", 3, 30.0, "remote")

        self.assertEqual(decide_save_sync(local, None).action, "upload")
        self.assertEqual(decide_save_sync(local, older_remote).action, "upload")
        self.assertEqual(decide_save_sync(local, newer_remote).action, "download")
        self.assertEqual(decide_save_sync(local, same_remote).action, "noop")
        conflict = decide_save_sync(local, conflict_remote)
        self.assertEqual(conflict.action, "conflict")
        self.assertEqual(conflict.winning_device_id, "desktop")
        self.assertTrue(conflict.conflict)

    def test_update_manifest_reports_optional_and_mandatory_updates(self) -> None:
        current = UpdateManifest("1.2.0", "1.2.0")
        optional = UpdateManifest("1.2.0", "1.3.0", "beta")
        mandatory = UpdateManifest("1.2.0", "2.0.0", "stable", True, "https://example.invalid/download")

        self.assertFalse(current.update_available)
        self.assertEqual(current.install_prompt(), "Game is up to date.")
        self.assertEqual(optional.install_prompt(), "Optional beta update 1.3.0 available.")
        self.assertEqual(mandatory.install_prompt(), "Mandatory stable update 2.0.0 available.")
        with self.assertRaises(ValueError):
            UpdateManifest("1.0.0", "2.0.0", "nightly")
        with self.assertRaises(ValueError):
            UpdateManifest("1.0.0", "2.0.0", mandatory=True)
        with self.assertRaises(ValueError):
            UpdateManifest("one", "2.0.0").update_available


if __name__ == "__main__":
    unittest.main()
