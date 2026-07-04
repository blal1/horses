import json
import os
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.package_build import (
    AssetRule,
    BuildAutomationPlan,
    BuildFailureLog,
    BuildInput,
    BuildMatrix,
    BuildTargetSpec,
    BuildToolchain,
    ChecksumEntry,
    DesktopEntryMetadata,
    DistributionFolder,
    DistributionPlan,
    InstallInstruction,
    LauncherShortcutMetadata,
    LinuxBuildPlan,
    LinuxRuntimeValidation,
    MacOSBuildPlan,
    MacOSBundleMetadata,
    MacOSDistributionNotes,
    MacOSRuntimeValidation,
    PackageSmokeCheck,
    ReleaseChannelLayout,
    ReleaseSmokeTest,
    ReleaseUpdateManifest,
    ReleaseValidationPlan,
    ReleaseValidationResult,
    RollbackPolicy,
    SaveMigrationPlan,
    SignedChecksum,
    UpdatePackage,
    WindowsBuildPlan,
    build_automation_plan,
    build_failure_log,
    checksum_file,
    checksum_manifest,
    default_asset_rules,
    default_build_matrix,
    distribution_plan,
    evaluate_release_artifacts,
    install_instructions,
    plaintext_resource_asset_rules,
    protected_asset_rules,
    release_validation_plan,
    signed_checksum,
    validate_protected_asset_rules,
    validate_required_assets,
    validate_windows_build_inputs,
    linux_build_plan,
    macos_build_plan,
    validate_macos_build_inputs,
    validate_linux_build_inputs,
    windows_build_plan,
)
from horse_racing_game.app.platform_support import PlatformTarget


PROJECT_ROOT = Path(__file__).parent.parent


def _load_build_release_module():
    spec = importlib.util.spec_from_file_location("build_release", PROJECT_ROOT / "scripts" / "build_release.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PackageBuildTests(unittest.TestCase):
    def test_default_build_matrix_defines_native_desktop_targets(self) -> None:
        matrix = default_build_matrix("0.2.0", "beta")

        self.assertEqual(matrix.toolchain.builder, "pyinstaller")
        self.assertEqual(matrix.toolchain.python_runtime, "3.10")
        self.assertEqual([spec.target.platform for spec in matrix.targets], ["windows", "linux", "macos"])
        self.assertEqual(matrix.release_layout.channel, "beta")

    def test_artifact_manifest_contains_release_paths_and_builder_metadata(self) -> None:
        matrix = default_build_matrix("0.2.0")

        manifest = matrix.artifact_manifest()

        self.assertEqual(manifest[0]["artifact"], "horse-racing-audio-first-0.2.0-windows-x64.zip")
        self.assertEqual(manifest[0]["path"], str(Path("dist") / "stable" / "horse-racing-audio-first-0.2.0-windows-x64.zip"))
        self.assertEqual(manifest[1]["builder"], "pyinstaller")
        self.assertEqual(manifest[2]["python_runtime"], "3.10")

    def test_pyinstaller_command_includes_assets_and_entry_script(self) -> None:
        matrix = default_build_matrix("0.2.0")
        windows = matrix.targets[0]

        command = matrix.pyinstaller_command(windows)

        self.assertEqual(command[:4], ("python", "-m", "PyInstaller", "--noconfirm"))
        self.assertIn("--windowed", command)
        self.assertIn("--collect-all", command)
        self.assertIn("pygame", command)
        self.assertIn(f"dist/resources.dat{os.pathsep}.", command)
        self.assertNotIn(f"content{os.pathsep}content", command)
        self.assertNotIn(f"assets{os.pathsep}assets", command)
        self.assertEqual(command[-1], "horse_racing_game/app/pygame_main.py")

    def test_default_asset_rules_are_protected_pack_rules(self) -> None:
        rules = default_asset_rules()

        self.assertEqual(rules, protected_asset_rules())
        self.assertEqual(validate_protected_asset_rules(rules), ())

    def test_plaintext_resource_asset_rules_are_rejected_for_protected_release(self) -> None:
        problems = validate_protected_asset_rules(plaintext_resource_asset_rules())

        self.assertIn("missing encrypted resource pack: dist/resources.dat", problems)
        self.assertIn("plaintext resource directory included: content", problems)
        self.assertIn("plaintext resource directory included: assets", problems)

    def test_required_assets_match_current_repository(self) -> None:
        missing = validate_required_assets(PROJECT_ROOT, default_asset_rules())

        self.assertEqual(missing, ())

    def test_asset_validation_reports_missing_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "content").mkdir()
            rules = (AssetRule("content", "content"), AssetRule("missing.dat", "."))

            missing = validate_required_assets(root, rules)

            self.assertEqual(missing, ("missing.dat",))

    def test_release_layout_validates_channel_and_artifact_name(self) -> None:
        layout = ReleaseChannelLayout("dev", "builds")

        self.assertEqual(layout.artifact_path("game.zip"), str(Path("builds") / "dev" / "game.zip"))
        with self.assertRaises(ValueError):
            ReleaseChannelLayout("nightly")
        with self.assertRaises(ValueError):
            layout.artifact_path("")

    def test_build_matrix_rejects_duplicate_targets(self) -> None:
        spec = BuildTargetSpec(
            PlatformTarget("windows", "x64", "zip"),
            "windows",
            "dist/windows",
            "Game",
            default_asset_rules(),
        )

        with self.assertRaises(ValueError):
            BuildMatrix("Game", "1.0.0", BuildToolchain("pyinstaller"), (spec, spec))

    def test_invalid_build_strategy_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AssetRule("", ".")
        with self.assertRaises(ValueError):
            BuildToolchain("unknown")
        with self.assertRaises(ValueError):
            BuildTargetSpec(
                PlatformTarget("linux", "x64", "tar.gz"),
                "windows",
                "dist/linux",
                "Game",
                default_asset_rules(),
            )

    def test_windows_build_plan_includes_exe_nvda_shortcut_save_migration_and_smoke_checks(self) -> None:
        matrix = default_build_matrix("0.2.0")

        plan = windows_build_plan(matrix, Path("C:/Users/player"))

        self.assertEqual(plan.artifact_name, "horse-racing-audio-first-0.2.0-windows-x64.zip")
        self.assertTrue(plan.executable_path.endswith("HorseRacingAudioFirst.exe"))
        self.assertTrue(plan.nvda_dll_path.endswith("nvdaControllerClient64.dll"))
        self.assertEqual(plan.launcher_shortcut.name, "Horse Racing Audio First")
        self.assertIn("AppData", plan.save_migration.platform_save_path)
        self.assertEqual([check.check_id for check in plan.smoke_checks], [
            "launch-help",
            "content-load",
            "headless-race",
            "save-round-trip",
            "replay-load",
        ])

    def test_windows_build_inputs_are_present_in_current_repository(self) -> None:
        plan = windows_build_plan(default_build_matrix("0.2.0"))

        missing = validate_windows_build_inputs(PROJECT_ROOT, plan)

        self.assertEqual(missing, ())

    def test_windows_packaging_script_outputs_plan_json(self) -> None:
        result = subprocess.run(
            ["python", "scripts/package_windows.py", "--version", "0.2.0", "--project-root", str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["artifact"], "horse-racing-audio-first-0.2.0-windows-x64.zip")
        self.assertEqual(payload["missing_inputs"], [])
        self.assertIn("PyInstaller", payload["command"])

    def test_checksum_manifest_is_sorted_and_hashes_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "b.txt"
            second = root / "a.txt"
            first.write_text("bravo", encoding="utf-8")
            second.write_text("alpha", encoding="utf-8")

            entries = checksum_manifest((first, second))

            self.assertEqual([Path(entry.path).name for entry in entries], ["a.txt", "b.txt"])
            self.assertEqual(entries[0], checksum_file(second))
            self.assertEqual(entries[0].size_bytes, 5)
            self.assertEqual(len(entries[0].sha256), 64)
            with self.assertRaises(ValueError):
                checksum_file(root / "missing.txt")

    def test_invalid_windows_build_values_are_rejected(self) -> None:
        linux_spec = BuildTargetSpec(
            PlatformTarget("linux", "x64", "tar.gz"),
            "linux",
            "dist/linux",
            "Game",
            default_asset_rules(),
        )
        windows_spec = BuildTargetSpec(
            PlatformTarget("windows", "x64", "zip"),
            "windows",
            "dist/windows",
            "Game",
            default_asset_rules(),
        )

        with self.assertRaises(ValueError):
            LauncherShortcutMetadata("", "target.exe", ".", "description")
        with self.assertRaises(ValueError):
            SaveMigrationPlan("", "C:/Users/player/AppData/Roaming/Game/progress.json")
        with self.assertRaises(ValueError):
            PackageSmokeCheck("", ("game.exe",), "ok")
        with self.assertRaises(ValueError):
            ChecksumEntry("artifact.zip", "abc", 1)
        with self.assertRaises(ValueError):
            WindowsBuildPlan(
                linux_spec,
                "artifact.zip",
                ("python", "-m", "PyInstaller"),
                "Game.exe",
                "nvdaControllerClient64.dll",
                LauncherShortcutMetadata("Game", "Game.exe", ".", "Game"),
                SaveMigrationPlan("save/progress.json", "progress.json"),
                (PackageSmokeCheck("launch", ("Game.exe",), "ok"),),
            )
        with self.assertRaises(ValueError):
            WindowsBuildPlan(
                windows_spec,
                "artifact.zip",
                ("python", "-m", "PyInstaller"),
                "Game.bin",
                "nvdaControllerClient64.dll",
                LauncherShortcutMetadata("Game", "Game.exe", ".", "Game"),
                SaveMigrationPlan("save/progress.json", "progress.json"),
                (PackageSmokeCheck("launch", ("Game.exe",), "ok"),),
            )

    def test_linux_build_plan_includes_desktop_entry_runtime_validation_and_smoke_checks(self) -> None:
        plan = linux_build_plan(default_build_matrix("0.2.0"))

        self.assertEqual(plan.artifact_name, "horse-racing-audio-first-0.2.0-linux-x64.tar.gz")
        self.assertTrue(plan.executable_path.endswith("horse-racing-audio-first"))
        self.assertIn("Name=Horse Racing Audio First", plan.desktop_entry.text())
        self.assertIn("Game;Audio;", plan.desktop_entry.text())
        self.assertEqual(plan.runtime_validation.required_modules, ("pygame",))
        self.assertEqual(plan.runtime_validation.required_tools, ("spd-say",))
        self.assertEqual(plan.runtime_validation.sdl_video_driver_fallback, "dummy")
        self.assertEqual([check.check_id for check in plan.smoke_checks], [
            "launch-help",
            "sdl-fallback",
            "speech-fallback",
            "headless-race",
            "save-round-trip",
        ])

    def test_linux_build_inputs_are_present_in_current_repository(self) -> None:
        plan = linux_build_plan(default_build_matrix("0.2.0"))

        missing = validate_linux_build_inputs(PROJECT_ROOT, plan)

        self.assertEqual(missing, ())

    def test_linux_packaging_script_outputs_plan_json(self) -> None:
        result = subprocess.run(
            ["python", "scripts/package_linux.py", "--version", "0.2.0", "--project-root", str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["artifact"], "horse-racing-audio-first-0.2.0-linux-x64.tar.gz")
        self.assertEqual(payload["missing_inputs"], [])
        self.assertIn("PyInstaller", payload["command"])
        self.assertEqual(payload["runtime_validation"]["required_tools"], ["spd-say"])

    def test_linux_build_plan_can_select_appimage_target_when_present(self) -> None:
        assets = default_asset_rules()
        matrix = BuildMatrix(
            "Horse Racing Audio First",
            "0.2.0",
            BuildToolchain("pyinstaller"),
            (
                BuildTargetSpec(PlatformTarget("linux", "x64", "tar.gz"), "linux", "dist/linux", "game", assets),
                BuildTargetSpec(PlatformTarget("linux", "x64", "appimage"), "linux", "dist/appimage", "game", assets),
            ),
        )

        plan = linux_build_plan(matrix, package_format="appimage")

        self.assertEqual(plan.artifact_name, "horse-racing-audio-first-0.2.0-linux-x64.appimage")
        self.assertEqual(plan.appimage_metadata["archive_format"], "appimage")

    def test_invalid_linux_build_values_are_rejected(self) -> None:
        windows_spec = BuildTargetSpec(
            PlatformTarget("windows", "x64", "zip"),
            "windows",
            "dist/windows",
            "Game",
            default_asset_rules(),
        )
        linux_spec = BuildTargetSpec(
            PlatformTarget("linux", "x64", "tar.gz"),
            "linux",
            "dist/linux",
            "Game",
            default_asset_rules(),
        )

        with self.assertRaises(ValueError):
            DesktopEntryMetadata("", "game", "icon.png")
        with self.assertRaises(ValueError):
            LinuxRuntimeValidation(required_modules=())
        with self.assertRaises(ValueError):
            LinuxBuildPlan(
                windows_spec,
                "artifact.tar.gz",
                ("python", "-m", "PyInstaller"),
                "game",
                DesktopEntryMetadata("Game", "game", "icon.png"),
                LinuxRuntimeValidation(),
                (PackageSmokeCheck("launch", ("game",), "ok"),),
                {"archive_format": "tar.gz"},
            )
        with self.assertRaises(ValueError):
            LinuxBuildPlan(
                linux_spec,
                "artifact.tar.gz",
                ("python", "-m", "PyInstaller"),
                "game.exe",
                DesktopEntryMetadata("Game", "game", "icon.png"),
                LinuxRuntimeValidation(),
                (PackageSmokeCheck("launch", ("game",), "ok"),),
                {"archive_format": "tar.gz"},
            )

    def test_macos_build_plan_includes_bundle_runtime_distribution_notes_and_smoke_checks(self) -> None:
        plan = macos_build_plan(default_build_matrix("0.2.0"), Path("/Users/player"))

        self.assertEqual(plan.artifact_name, "horse-racing-audio-first-0.2.0-macos-arm64.zip")
        self.assertTrue(plan.app_bundle_path.endswith("Horse Racing Audio First.app"))
        self.assertIn("Contents", plan.executable_path)
        self.assertEqual(plan.bundle_metadata.bundle_identifier, "com.horseracing.audiofirst")
        self.assertEqual(plan.runtime_validation.required_tools, ("say",))
        self.assertIn("quarantine", plan.distribution_notes.quarantine_note)
        self.assertEqual([check.check_id for check in plan.smoke_checks], [
            "launch-help",
            "speech-fallback",
            "headless-race",
            "save-round-trip",
            "bundle-metadata",
        ])

    def test_macos_bundle_plist_contains_release_metadata(self) -> None:
        metadata = MacOSBundleMetadata("Game", "com.example.game", "Game")

        plist = metadata.plist("1.2.3")

        self.assertEqual(plist["CFBundleName"], "Game")
        self.assertEqual(plist["CFBundleIdentifier"], "com.example.game")
        self.assertEqual(plist["CFBundleExecutable"], "Game")
        self.assertEqual(plist["CFBundleShortVersionString"], "1.2.3")

    def test_macos_build_inputs_are_present_in_current_repository(self) -> None:
        plan = macos_build_plan(default_build_matrix("0.2.0"))

        missing = validate_macos_build_inputs(PROJECT_ROOT, plan)

        self.assertEqual(missing, ())

    def test_macos_packaging_script_outputs_plan_json(self) -> None:
        result = subprocess.run(
            ["python", "scripts/package_macos.py", "--version", "0.2.0", "--project-root", str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["artifact"], "horse-racing-audio-first-0.2.0-macos-arm64.zip")
        self.assertEqual(payload["missing_inputs"], [])
        self.assertIn("PyInstaller", payload["command"])
        self.assertEqual(payload["runtime_validation"]["required_tools"], ["say"])
        self.assertEqual(payload["bundle_metadata"]["CFBundleIdentifier"], "com.horseracing.audiofirst")

    def test_invalid_macos_build_values_are_rejected(self) -> None:
        linux_spec = BuildTargetSpec(
            PlatformTarget("linux", "x64", "tar.gz"),
            "linux",
            "dist/linux",
            "Game",
            default_asset_rules(),
        )
        macos_spec = BuildTargetSpec(
            PlatformTarget("macos", "arm64", "zip"),
            "macos",
            "dist/macos",
            "Game",
            default_asset_rules(),
        )

        with self.assertRaises(ValueError):
            MacOSBundleMetadata("Game", "notreverse", "Game")
        with self.assertRaises(ValueError):
            MacOSBundleMetadata("Game", "com.example.game", "Game", "icon.png")
        with self.assertRaises(ValueError):
            MacOSRuntimeValidation(speech_fallback="spd-say")
        with self.assertRaises(ValueError):
            MacOSDistributionNotes("", "notarize")
        with self.assertRaises(ValueError):
            MacOSBuildPlan(
                linux_spec,
                "artifact.zip",
                ("python", "-m", "PyInstaller"),
                "Game.app",
                "Game",
                MacOSBundleMetadata("Game", "com.example.game", "Game"),
                MacOSRuntimeValidation(),
                MacOSDistributionNotes("quarantine", "notarize"),
                (PackageSmokeCheck("launch", ("Game",), "ok"),),
            )
        with self.assertRaises(ValueError):
            MacOSBuildPlan(
                macos_spec,
                "artifact.zip",
                ("python", "-m", "PyInstaller"),
                "Game",
                "Game",
                MacOSBundleMetadata("Game", "com.example.game", "Game"),
                MacOSRuntimeValidation(),
                MacOSDistributionNotes("quarantine", "notarize"),
                (PackageSmokeCheck("launch", ("Game",), "ok"),),
            )

    def test_build_automation_plan_defines_clean_dirs_jobs_manifest_and_ci_commands(self) -> None:
        plan = build_automation_plan(BuildInput("0.3.0", "beta", "Release notes"))

        self.assertEqual(plan.inputs.version, "0.3.0")
        self.assertEqual(plan.dist_dir, str(Path("dist") / "beta"))
        self.assertIn("build", plan.clean_dirs)
        self.assertEqual(plan.manifest_path, str(Path("dist") / "beta" / "artifact-manifest.json"))
        self.assertEqual([job.platform for job in plan.jobs], ["windows", "linux", "macos"])
        self.assertEqual([job.job_id for job in plan.jobs], ["build-windows", "build-linux", "build-macos"])
        self.assertEqual(len(plan.artifact_manifest), 3)
        self.assertEqual(plan.ci_commands[0], ("python", "-m", "pytest"))
        self.assertIn(("python", "scripts/package_linux.py", "--version", "0.3.0", "--channel", "beta"), plan.ci_commands)

    def test_package_all_script_outputs_automation_json(self) -> None:
        result = subprocess.run(
            [
                "python",
                "scripts/package_all.py",
                "--version",
                "0.3.0",
                "--channel",
                "dev",
                "--changelog",
                "Packaging pass",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["version"], "0.3.0")
        self.assertEqual(payload["channel"], "dev")
        self.assertEqual(payload["changelog"], "Packaging pass")
        self.assertEqual([job["platform"] for job in payload["jobs"]], ["windows", "linux", "macos"])
        self.assertEqual(payload["manifest_path"], str(Path("dist") / "dev" / "artifact-manifest.json"))
        self.assertIn(["python", "-m", "pytest"], payload["ci_commands"])

    def test_build_failure_log_keeps_stderr_tail(self) -> None:
        job = build_automation_plan(BuildInput("0.3.0")).jobs[0]
        stderr = "\n".join(f"line {index}" for index in range(30))

        failure = build_failure_log(job, 2, stderr)

        self.assertEqual(failure.job_id, "build-windows")
        self.assertEqual(failure.return_code, 2)
        self.assertEqual(failure.log_path, str(Path("build") / "logs" / "windows.log"))
        self.assertTrue(failure.stderr_tail.startswith("line 10"))
        self.assertIn("line 29", failure.stderr_tail)

    def test_invalid_build_automation_values_are_rejected(self) -> None:
        job = build_automation_plan(BuildInput("0.3.0")).jobs[0]

        with self.assertRaises(ValueError):
            BuildInput("", "stable")
        with self.assertRaises(ValueError):
            BuildInput("0.3.0", "nightly")
        with self.assertRaises(ValueError):
            BuildAutomationPlan(
                BuildInput("0.3.0"),
                (),
                "dist",
                "manifest.json",
                (job,),
                ({"artifact": "game.zip"},),
                (("python", "-m", "pytest"),),
            )
        with self.assertRaises(ValueError):
            BuildFailureLog("job", 0, "log.txt", "")

    def test_release_validation_plan_covers_all_platform_smoke_checks(self) -> None:
        plan = release_validation_plan(BuildInput("0.4.0", "stable"))

        self.assertEqual(plan.version, "0.4.0")
        self.assertEqual(plan.checksum_manifest_path, str(Path("dist") / "stable" / "checksums.json"))
        self.assertEqual(len(plan.artifact_manifest), 3)
        self.assertEqual(len(plan.tests), 18)
        self.assertIn("windows-launch", [test.test_id for test in plan.tests])
        self.assertIn("linux-audio", [test.test_id for test in plan.tests])
        self.assertIn("macos-race", [test.test_id for test in plan.tests])

    def test_release_artifact_evaluation_skips_missing_and_passes_present_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            present = root / "dist" / "stable" / "game.zip"
            present.parent.mkdir(parents=True)
            present.write_text("artifact", encoding="utf-8")
            plan = ReleaseValidationPlan(
                "0.4.0",
                "stable",
                (
                    ReleaseSmokeTest("present-launch", "Launch present artifact.", ("game.zip", "--help"), "dist/stable/game.zip"),
                    ReleaseSmokeTest("missing-launch", "Launch missing artifact.", ("missing.zip", "--help"), "dist/stable/missing.zip"),
                ),
                ({"artifact": "game.zip", "path": "dist/stable/game.zip"},),
                "dist/stable/checksums.json",
            )

            results = evaluate_release_artifacts(root, plan)

            self.assertEqual([result.status for result in results], ["passed", "skipped"])
            self.assertIn("artifact missing", results[1].detail)

    def test_validate_release_script_outputs_plan_and_results_json(self) -> None:
        result = subprocess.run(
            ["python", "scripts/validate_release.py", "--version", "0.4.0", "--project-root", str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["version"], "0.4.0")
        self.assertEqual(len(payload["artifact_manifest"]), 3)
        self.assertEqual(len(payload["tests"]), 18)
        self.assertTrue(all(item["status"] in {"passed", "skipped", "failed"} for item in payload["results"]))
        self.assertTrue(any(item["status"] == "skipped" for item in payload["results"]))

    def test_build_windows_release_script_outputs_dry_run_plan_json(self) -> None:
        result = subprocess.run(
            [
                "python",
                "scripts/build_windows_release.py",
                "--version",
                "0.1.0",
                "--channel",
                "stable",
                "--project-root",
                str(PROJECT_ROOT),
                "--dry-run",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["artifact"], "horse-racing-audio-first-0.1.0-windows-x64.zip")
        self.assertEqual(payload["release_artifact"], str(Path("dist") / "stable" / "horse-racing-audio-first-0.1.0-windows-x64.zip"))
        self.assertEqual(payload["missing_inputs"], [])
        self.assertIn("--add-data", payload["command"])
        self.assertTrue(any("--smoke-race" in command for command in payload["smoke_commands"]))

    def test_hardened_release_audit_rejects_plaintext_resource_dirs(self) -> None:
        audit_protected_release_tree = _load_build_release_module().audit_protected_release_tree

        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / "HorseRacingAudioFirst"
            (dist / "content").mkdir(parents=True)
            (dist / "content" / "horses.json").write_text("{}", encoding="utf-8")
            (dist / "assets" / "sfx").mkdir(parents=True)
            (dist / "assets" / "sfx" / "cue.ogg").write_bytes(b"ogg")

            leaks = audit_protected_release_tree(dist)

            self.assertIn("missing resources.dat", leaks)
            self.assertIn("content", leaks)
            self.assertIn("content/horses.json", leaks)
            self.assertIn("assets", leaks)
            self.assertIn("assets/sfx/cue.ogg", leaks)

    def test_hardened_release_audit_accepts_pack_only_resources(self) -> None:
        audit_protected_release_tree = _load_build_release_module().audit_protected_release_tree

        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / "HorseRacingAudioFirst"
            dist.mkdir(parents=True)
            (dist / "resources.dat").write_bytes(b"HRPK")

            self.assertEqual(audit_protected_release_tree(dist), ())

    def test_sensitive_code_audit_rejects_readable_sensitive_sources(self) -> None:
        module = _load_build_release_module()

        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / "HorseRacingAudioFirst"
            source = dist / "horse_racing_game" / "security" / "crypto.py"
            source.parent.mkdir(parents=True)
            source.write_text("MASTER_KEY = 'readable'", encoding="utf-8")

            problems = module.audit_sensitive_code_tree(dist, ("horse_racing_game/security/crypto.py",))

            self.assertIn("sensitive source shipped: horse_racing_game/security/crypto.py", problems)
            self.assertIn("missing native extension for sensitive module: horse_racing_game/security/crypto.py", problems)

    def test_sensitive_code_audit_accepts_native_extension_without_source(self) -> None:
        module = _load_build_release_module()

        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / "HorseRacingAudioFirst"
            native = dist / "horse_racing_game" / "security" / "crypto.cp310-win_amd64.pyd"
            native.parent.mkdir(parents=True)
            native.write_bytes(b"native")

            self.assertEqual(module.audit_sensitive_code_tree(dist, ("horse_racing_game/security/crypto.py",)), ())

    def test_distribution_folder_paths_are_channel_version_platform_scoped(self) -> None:
        folder = DistributionFolder("beta", "0.5.0")

        self.assertEqual(folder.path, str(Path("dist") / "beta" / "0.5.0"))
        self.assertEqual(folder.platform_path("windows"), str(Path("dist") / "beta" / "0.5.0" / "windows"))

    def test_distribution_plan_builds_update_manifest_instructions_and_signed_checksums(self) -> None:
        checksum = ChecksumEntry(
            str(Path("dist") / "beta" / "horse-racing-audio-first-0.5.0-windows-x64.zip"),
            "a" * 64,
            1234,
        )

        plan = distribution_plan(
            BuildInput("0.5.0", "beta"),
            "https://downloads.example.test/releases/",
            (checksum,),
            "release-key",
            "0.4.0",
            mandatory=True,
        )

        self.assertEqual(plan.folder.path, str(Path("dist") / "beta" / "0.5.0"))
        self.assertTrue(plan.update_manifest.mandatory)
        self.assertEqual(plan.update_manifest.rollback_version, "0.4.0")
        self.assertEqual([package.platform for package in plan.update_manifest.packages], ["windows", "linux", "macos"])
        self.assertEqual(plan.update_manifest.packages[0].sha256, "a" * 64)
        self.assertEqual(plan.update_manifest.packages[0].size_bytes, 1234)
        self.assertEqual(plan.update_manifest.packages[1].sha256, "0" * 64)
        self.assertTrue(plan.update_manifest.packages[0].url.endswith("/beta/0.5.0/windows/horse-racing-audio-first-0.5.0-windows-x64.zip"))
        self.assertEqual(len(plan.signed_checksums), 3)
        self.assertEqual(len(plan.signed_checksums[0].signature), 64)
        self.assertEqual([instruction.platform for instruction in plan.instructions], ["windows", "linux", "macos"])

    def test_update_manifest_and_distribution_plan_serialize_to_json_ready_dicts(self) -> None:
        package = UpdatePackage("linux", "game.tar.gz", "0.5.0", "https://example.test/game.tar.gz", "b" * 64, 99)
        manifest = ReleaseUpdateManifest("0.5.0", "dev", (package,), rollback_version="0.4.0")
        signed = signed_checksum(ChecksumEntry("game.tar.gz", "b" * 64, 99), "release-key")
        plan = DistributionPlan(
            DistributionFolder("dev", "0.5.0"),
            manifest,
            (signed,),
            RollbackPolicy("0.5.0", "0.4.0"),
            (InstallInstruction("linux", ("install",), ("update",)),),
        )

        payload = plan.to_dict()

        self.assertEqual(manifest.to_dict()["packages"][0]["platform"], "linux")
        self.assertEqual(payload["release_root"], str(Path("dist") / "dev" / "0.5.0"))
        self.assertEqual(payload["update_manifest"], manifest.to_dict())
        self.assertEqual(payload["rollback"]["rollback_target"], "0.4.0")
        self.assertEqual(payload["instructions"][0]["install_steps"], ["install"])

    def test_distribute_release_script_outputs_distribution_json(self) -> None:
        result = subprocess.run(
            [
                "python",
                "scripts/distribute_release.py",
                "--version",
                "0.5.0",
                "--channel",
                "stable",
                "--base-url",
                "https://downloads.example.test/releases",
                "--previous-version",
                "0.4.0",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["release_root"], str(Path("dist") / "stable" / "0.5.0"))
        self.assertEqual(payload["update_manifest"]["version"], "0.5.0")
        self.assertEqual([item["platform"] for item in payload["update_manifest"]["packages"]], ["windows", "linux", "macos"])
        self.assertEqual(len(payload["signed_checksums"]), 3)
        self.assertEqual(payload["rollback"]["rollback_target"], "0.4.0")

    def test_invalid_distribution_values_are_rejected(self) -> None:
        package = UpdatePackage("windows", "game.zip", "0.5.0", "https://example.test/game.zip", "c" * 64, 1)
        checksum = ChecksumEntry("game.zip", "c" * 64, 1)

        with self.assertRaises(ValueError):
            DistributionFolder("nightly", "0.5.0")
        with self.assertRaises(ValueError):
            UpdatePackage("ios", "game.zip", "0.5.0", "https://example.test/game.zip", "c" * 64, 1)
        with self.assertRaises(ValueError):
            ReleaseUpdateManifest("0.5.0", "stable", (package, package))
        with self.assertRaises(ValueError):
            RollbackPolicy("0.5.0", "0.5.0")
        with self.assertRaises(ValueError):
            InstallInstruction("windows", (), ("update",))
        with self.assertRaises(ValueError):
            SignedChecksum(checksum, "")
        with self.assertRaises(ValueError):
            signed_checksum(checksum, "")
        with self.assertRaises(ValueError):
            distribution_plan(BuildInput("0.5.0"), "")

    def test_invalid_release_validation_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReleaseSmokeTest("", "desc", ("game",), "artifact")
        with self.assertRaises(ValueError):
            ReleaseValidationPlan(
                "0.4.0",
                "nightly",
                (ReleaseSmokeTest("id", "desc", ("game",), "artifact"),),
                ({"artifact": "a"},),
                "checksums.json",
            )
        with self.assertRaises(ValueError):
            ReleaseValidationResult("id", "unknown", "detail")


if __name__ == "__main__":
    unittest.main()
