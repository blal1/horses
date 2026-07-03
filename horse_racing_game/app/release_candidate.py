from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile


RELEASE_CANDIDATE_MODES = {"quick_race", "short_career", "training", "replay"}
RELEASE_CANDIDATE_BUILDS = {"windows_desktop", "android_debug"}
RELEASE_CANDIDATE_SMOKE_CHECKS = {
    "launch",
    "quick_race_finish",
    "short_career_save",
    "training_complete",
    "replay_load",
    "windows_artifact",
    "android_debug_artifact",
}


@dataclass(frozen=True)
class ReleaseCandidateScope:
    scope_id: str
    modes: tuple[str, ...]
    builds: tuple[str, ...]
    smoke_checks: tuple[str, ...]
    deferred_features: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.scope_id:
            raise ValueError("scope_id must be non-empty")
        if not self.modes:
            raise ValueError("release candidate scope requires modes")
        if not self.builds:
            raise ValueError("release candidate scope requires builds")
        if not self.smoke_checks:
            raise ValueError("release candidate scope requires smoke checks")
        if len(self.modes) != len(set(self.modes)):
            raise ValueError("duplicate release candidate mode")
        if len(self.builds) != len(set(self.builds)):
            raise ValueError("duplicate release candidate build")
        if len(self.smoke_checks) != len(set(self.smoke_checks)):
            raise ValueError("duplicate release candidate smoke check")

    def includes_mode(self, mode: str) -> bool:
        return mode in self.modes

    def includes_build(self, build: str) -> bool:
        return build in self.builds

    def defers_feature(self, feature: str) -> bool:
        return feature in self.deferred_features


@dataclass(frozen=True)
class ReleaseCandidateReadiness:
    scope: ReleaseCandidateScope
    completed_modes: frozenset[str]
    completed_builds: frozenset[str]
    passed_smoke_checks: frozenset[str]

    def __post_init__(self) -> None:
        unknown_modes = self.completed_modes - set(self.scope.modes)
        unknown_builds = self.completed_builds - set(self.scope.builds)
        unknown_checks = self.passed_smoke_checks - set(self.scope.smoke_checks)
        if unknown_modes:
            raise ValueError("completed_modes contains items outside the release candidate scope")
        if unknown_builds:
            raise ValueError("completed_builds contains items outside the release candidate scope")
        if unknown_checks:
            raise ValueError("passed_smoke_checks contains items outside the release candidate scope")

    @property
    def missing_modes(self) -> tuple[str, ...]:
        return tuple(mode for mode in self.scope.modes if mode not in self.completed_modes)

    @property
    def missing_builds(self) -> tuple[str, ...]:
        return tuple(build for build in self.scope.builds if build not in self.completed_builds)

    @property
    def missing_smoke_checks(self) -> tuple[str, ...]:
        return tuple(check for check in self.scope.smoke_checks if check not in self.passed_smoke_checks)

    @property
    def ready(self) -> bool:
        return not self.missing_modes and not self.missing_builds and not self.missing_smoke_checks

    def summary(self) -> str:
        if self.ready:
            return f"{self.scope.scope_id}: ready for release-candidate validation."
        missing = []
        if self.missing_modes:
            missing.append("modes=" + ",".join(self.missing_modes))
        if self.missing_builds:
            missing.append("builds=" + ",".join(self.missing_builds))
        if self.missing_smoke_checks:
            missing.append("smoke_checks=" + ",".join(self.missing_smoke_checks))
        return f"{self.scope.scope_id}: missing " + "; ".join(missing)


@dataclass(frozen=True)
class ReleaseCandidateValidation:
    readiness: ReleaseCandidateReadiness
    checks: dict[str, bool]
    details: dict[str, str]

    @property
    def ready(self) -> bool:
        return self.readiness.ready


def android_debug_build_environment(project_root: Path) -> dict[str, object]:
    android_root = project_root / "android"
    wrapper_unix = android_root / "gradlew"
    wrapper_windows = android_root / "gradlew.bat"
    sdk_env = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    local_app_data = os.environ.get("LOCALAPPDATA")
    local_sdk = Path(local_app_data) / "Android" / "Sdk" if local_app_data else None
    sdk_root = Path(sdk_env) if sdk_env else local_sdk
    gradle_wrapper = wrapper_unix.is_file() or wrapper_windows.is_file()
    gradle_path = shutil.which("gradle")
    adb_path = shutil.which("adb")
    sdkmanager_path = shutil.which("sdkmanager")

    if sdk_root and not adb_path:
        adb_name = "adb.exe" if os.name == "nt" else "adb"
        sdk_adb = sdk_root / "platform-tools" / adb_name
        if sdk_adb.is_file():
            adb_path = str(sdk_adb)
    if sdk_root and not sdkmanager_path:
        manager_name = "sdkmanager.bat" if os.name == "nt" else "sdkmanager"
        cmdline_tools = sdk_root / "cmdline-tools"
        if cmdline_tools.is_dir():
            for candidate in sorted(cmdline_tools.glob(f"*/bin/{manager_name}")):
                if candidate.is_file():
                    sdkmanager_path = str(candidate)
                    break

    build_command = None
    if wrapper_windows.is_file():
        build_command = "android\\gradlew.bat -p android :app:assembleDebug"
    elif wrapper_unix.is_file():
        build_command = "android/gradlew -p android :app:assembleDebug"
    elif gradle_path:
        build_command = "gradle -p android :app:assembleDebug"

    return {
        "android_root": str(android_root),
        "gradle_wrapper": gradle_wrapper,
        "gradlew": str(wrapper_windows if os.name == "nt" else wrapper_unix),
        "gradle_on_path": bool(gradle_path),
        "gradle_path": gradle_path or "",
        "java_on_path": bool(shutil.which("java")),
        "sdk_root": str(sdk_root) if sdk_root else "",
        "sdk_root_exists": bool(sdk_root and sdk_root.is_dir()),
        "adb_available": bool(adb_path),
        "adb_path": adb_path or "",
        "sdkmanager_available": bool(sdkmanager_path),
        "sdkmanager_path": sdkmanager_path or "",
        "assemble_debug_command": build_command or "",
    }


def vertical_slice_release_candidate_scope() -> ReleaseCandidateScope:
    return ReleaseCandidateScope(
        scope_id="vertical-slice-rc",
        modes=("quick_race", "short_career", "training", "replay"),
        builds=("windows_desktop", "android_debug"),
        smoke_checks=(
            "launch",
            "quick_race_finish",
            "short_career_save",
            "training_complete",
            "replay_load",
            "windows_artifact",
            "android_debug_artifact",
        ),
        deferred_features=(
            "ranked_ladder",
            "full_social_backend",
            "track_marketplace",
            "season_pass",
            "public_android_release",
            "macos_release_artifact",
            "linux_release_artifact",
        ),
    )


def validate_vertical_slice_release_candidate(project_root: Path) -> ReleaseCandidateValidation:
    from horse_racing_game.app.bootstrap import build_quick_race_services
    from horse_racing_game.app.config import AppConfig
    from horse_racing_game.app.game_app import GameApp
    from horse_racing_game.app.progress import GameProgress, load_progress, record_race_result
    from horse_racing_game.app.replay import build_replay, replay_to_dict, reconstruct_race
    from horse_racing_game.app.training import next_training_level

    scope = vertical_slice_release_candidate_scope()
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}
    completed_modes: set[str] = set()
    completed_builds: set[str] = set()
    passed_smoke_checks: set[str] = set()

    content_root = project_root / "content"
    try:
        config = AppConfig(content_root=content_root)
        services = build_quick_race_services(config)
        app = GameApp(config, services)
        result = app.run_quick_race()
        launch_ok = bool(services.horses and services.track.track_id and services.sound_catalog)
        quick_ok = result.state.is_finished and result.ticks > 0 and bool(result.events)
        checks["launch"] = launch_ok
        checks["quick_race_finish"] = quick_ok
        details["launch"] = f"track={services.track.track_id}; horses={len(services.horses)}; sounds={len(services.sound_catalog)}"
        details["quick_race_finish"] = f"finished={result.state.is_finished}; ticks={result.ticks}; events={len(result.events)}"
        if launch_ok:
            passed_smoke_checks.add("launch")
        if quick_ok:
            completed_modes.add("quick_race")
            passed_smoke_checks.add("quick_race_finish")

        replay = build_replay(config, result.commands)
        reconstructed = reconstruct_race(replay, content_root)
        replay_ok = reconstructed.state.is_finished and reconstructed.ticks > 0
        checks["replay_load"] = replay_ok
        details["replay_load"] = f"finished={reconstructed.state.is_finished}; ticks={reconstructed.ticks}"
        if replay_ok:
            completed_modes.add("replay")
            passed_smoke_checks.add("replay_load")

        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            rank = result.state.player().rank
            career_progress = record_race_result(
                state_root,
                GameProgress(),
                config.player_horse_id,
                config.track_id,
                is_tutorial=False,
                finished=result.state.is_finished,
                is_career=True,
                rank=rank,
                replay=replay_to_dict(replay),
                career_length=3,
            )
            loaded = load_progress(state_root)
            career_ok = (
                career_progress.career_races_completed == 1
                and loaded.career_races_completed == 1
                and loaded.last_replay is not None
            )
            training_level = next_training_level(0, result.state.is_finished)
            training_progress = record_race_result(
                state_root,
                loaded,
                config.player_horse_id,
                config.track_id,
                is_tutorial=False,
                finished=result.state.is_finished,
                is_training=True,
                rank=rank,
            )
            training_ok = training_level == 1 and training_progress.horse_training_levels.get(config.player_horse_id) == 1
        checks["short_career_save"] = career_ok
        checks["training_complete"] = training_ok
        details["short_career_save"] = f"career_races={1 if career_ok else 0}; replay_saved={career_ok}"
        details["training_complete"] = f"training_level={training_level}"
        if career_ok:
            completed_modes.add("short_career")
            passed_smoke_checks.add("short_career_save")
        if training_ok:
            completed_modes.add("training")
            passed_smoke_checks.add("training_complete")
    except Exception as error:
        details["headless_slice"] = str(error)

    windows_artifact = project_root / "dist" / "stable" / "horse-racing-audio-first-0.1.0-windows-x64.zip"
    android_artifact = project_root / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    checks["windows_artifact"] = windows_artifact.is_file()
    checks["android_debug_artifact"] = android_artifact.is_file()
    details["windows_artifact"] = str(windows_artifact)
    details["android_debug_artifact"] = str(android_artifact)
    android_environment = android_debug_build_environment(project_root)
    details["android_debug_environment"] = "; ".join(
        f"{key}={value}" for key, value in android_environment.items()
    )
    if checks["windows_artifact"]:
        completed_builds.add("windows_desktop")
        passed_smoke_checks.add("windows_artifact")
    if checks["android_debug_artifact"]:
        completed_builds.add("android_debug")
        passed_smoke_checks.add("android_debug_artifact")

    return ReleaseCandidateValidation(
        readiness=release_candidate_readiness(completed_modes, completed_builds, passed_smoke_checks, scope),
        checks=checks,
        details=details,
    )


def release_candidate_readiness(
    completed_modes: set[str] | frozenset[str],
    completed_builds: set[str] | frozenset[str],
    passed_smoke_checks: set[str] | frozenset[str],
    scope: ReleaseCandidateScope | None = None,
) -> ReleaseCandidateReadiness:
    return ReleaseCandidateReadiness(
        scope=scope or vertical_slice_release_candidate_scope(),
        completed_modes=frozenset(completed_modes),
        completed_builds=frozenset(completed_builds),
        passed_smoke_checks=frozenset(passed_smoke_checks),
    )
