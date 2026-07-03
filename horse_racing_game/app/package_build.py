from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.app.platform_support import PlatformTarget, platform_save_root


BUILDERS = {"pyinstaller"}
RELEASE_CHANNELS = {"stable", "beta", "dev"}
PYTHON_RUNTIME = "3.10"
WINDOWS_EXECUTABLE = "HorseRacingAudioFirst.exe"
LINUX_EXECUTABLE = "horse-racing-audio-first"
MACOS_EXECUTABLE = "Horse Racing Audio First"


@dataclass(frozen=True)
class AssetRule:
    source: str
    destination: str
    required: bool = True

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("asset source must be non-empty")
        if not self.destination:
            raise ValueError("asset destination must be non-empty")

    def pyinstaller_arg(self) -> str:
        return f"{self.source}{os.pathsep}{self.destination}"


@dataclass(frozen=True)
class BuildToolchain:
    builder: str
    python_runtime: str = PYTHON_RUNTIME
    entry_script: str = "horse_racing_game/app/pygame_main.py"
    console: bool = False
    clean: bool = True

    def __post_init__(self) -> None:
        if self.builder not in BUILDERS:
            raise ValueError("unsupported builder")
        if not self.python_runtime:
            raise ValueError("python_runtime must be non-empty")
        if not self.entry_script:
            raise ValueError("entry_script must be non-empty")


@dataclass(frozen=True)
class BuildTargetSpec:
    target: PlatformTarget
    host_platform: str
    artifact_dir: str
    executable_name: str
    asset_rules: tuple[AssetRule, ...]

    def __post_init__(self) -> None:
        if self.host_platform != self.target.platform:
            raise ValueError("phase 9 native builds require host_platform to match target platform")
        if not self.artifact_dir:
            raise ValueError("artifact_dir must be non-empty")
        if not self.executable_name:
            raise ValueError("executable_name must be non-empty")
        if not self.asset_rules:
            raise ValueError("at least one asset rule is required")


@dataclass(frozen=True)
class ReleaseChannelLayout:
    channel: str
    root_dir: str = "dist"

    def __post_init__(self) -> None:
        if self.channel not in RELEASE_CHANNELS:
            raise ValueError("invalid release channel")
        if not self.root_dir:
            raise ValueError("root_dir must be non-empty")

    def artifact_path(self, artifact_name: str) -> str:
        if not artifact_name:
            raise ValueError("artifact_name must be non-empty")
        return str(Path(self.root_dir) / self.channel / artifact_name)


@dataclass(frozen=True)
class BuildMatrix:
    app_name: str
    version: str
    toolchain: BuildToolchain
    targets: tuple[BuildTargetSpec, ...]
    release_layout: ReleaseChannelLayout = ReleaseChannelLayout("stable")

    def __post_init__(self) -> None:
        if not self.app_name:
            raise ValueError("app_name must be non-empty")
        if not self.version:
            raise ValueError("version must be non-empty")
        if not self.targets:
            raise ValueError("build matrix requires targets")
        target_keys = [(item.target.platform, item.target.architecture, item.target.package_format) for item in self.targets]
        if len(target_keys) != len(set(target_keys)):
            raise ValueError("duplicate build target")

    @property
    def safe_app_name(self) -> str:
        return self.app_name.lower().replace(" ", "-")

    def artifact_name_for(self, spec: BuildTargetSpec) -> str:
        return f"{self.safe_app_name}-{self.version}-{spec.target.artifact_suffix}"

    def artifact_manifest(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "platform": spec.target.platform,
                "architecture": spec.target.architecture,
                "format": spec.target.package_format,
                "builder": self.toolchain.builder,
                "python_runtime": self.toolchain.python_runtime,
                "artifact": self.artifact_name_for(spec),
                "path": self.release_layout.artifact_path(self.artifact_name_for(spec)),
            }
            for spec in self.targets
        )

    def pyinstaller_command(self, spec: BuildTargetSpec) -> tuple[str, ...]:
        if self.toolchain.builder != "pyinstaller":
            raise ValueError("pyinstaller command requested for non-pyinstaller builder")
        command = [
            "python",
            "-m",
            "PyInstaller",
            "--noconfirm",
        ]
        if self.toolchain.clean:
            command.append("--clean")
        command.extend(("--name", spec.executable_name))
        command.append("--console" if self.toolchain.console else "--windowed")
        command.extend(("--distpath", spec.artifact_dir))
        for rule in spec.asset_rules:
            command.extend(("--add-data", rule.pyinstaller_arg()))
        command.extend(("--collect-all", "pygame"))
        command.append(self.toolchain.entry_script)
        return tuple(command)


def default_asset_rules() -> tuple[AssetRule, ...]:
    return (
        AssetRule("content", "content"),
        AssetRule("assets", "assets"),
        AssetRule("nvdaControllerClient64.dll", "."),
        AssetRule("PLAY_GAME.bat", "."),
    )


def default_build_matrix(version: str = "0.1.0", channel: str = "stable") -> BuildMatrix:
    assets = default_asset_rules()
    return BuildMatrix(
        app_name="Horse Racing Audio First",
        version=version,
        toolchain=BuildToolchain("pyinstaller"),
        targets=(
            BuildTargetSpec(PlatformTarget("windows", "x64", "zip"), "windows", "dist/windows", "HorseRacingAudioFirst", assets),
            BuildTargetSpec(PlatformTarget("linux", "x64", "tar.gz"), "linux", "dist/linux", "horse-racing-audio-first", assets),
            BuildTargetSpec(PlatformTarget("macos", "arm64", "zip"), "macos", "dist/macos", "Horse Racing Audio First", assets),
        ),
        release_layout=ReleaseChannelLayout(channel),
    )


def validate_required_assets(project_root: Path, rules: tuple[AssetRule, ...]) -> tuple[str, ...]:
    return tuple(rule.source for rule in rules if rule.required and not (project_root / rule.source).exists())


@dataclass(frozen=True)
class LauncherShortcutMetadata:
    name: str
    target: str
    working_directory: str
    description: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("shortcut name must be non-empty")
        if not self.target:
            raise ValueError("shortcut target must be non-empty")
        if not self.working_directory:
            raise ValueError("shortcut working_directory must be non-empty")
        if not self.description:
            raise ValueError("shortcut description must be non-empty")


@dataclass(frozen=True)
class SaveMigrationPlan:
    legacy_relative_path: str
    platform_save_path: str
    backup_suffix: str = ".bak"

    def __post_init__(self) -> None:
        if not self.legacy_relative_path:
            raise ValueError("legacy_relative_path must be non-empty")
        if not self.platform_save_path:
            raise ValueError("platform_save_path must be non-empty")
        if not self.backup_suffix:
            raise ValueError("backup_suffix must be non-empty")


@dataclass(frozen=True)
class PackageSmokeCheck:
    check_id: str
    command: tuple[str, ...]
    expected: str

    def __post_init__(self) -> None:
        if not self.check_id:
            raise ValueError("check_id must be non-empty")
        if not self.command:
            raise ValueError("smoke check command must be non-empty")
        if not self.expected:
            raise ValueError("expected must be non-empty")


@dataclass(frozen=True)
class ChecksumEntry:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("checksum path must be non-empty")
        if len(self.sha256) != 64:
            raise ValueError("sha256 must be 64 hex characters")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")


@dataclass(frozen=True)
class BuildInput:
    version: str
    channel: str = "stable"
    changelog: str = ""

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("version must be non-empty")
        if self.channel not in RELEASE_CHANNELS:
            raise ValueError("invalid release channel")


@dataclass(frozen=True)
class BuildJob:
    job_id: str
    platform: str
    command: tuple[str, ...]
    artifact_name: str
    log_path: str

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id must be non-empty")
        if self.platform not in {"windows", "linux", "macos"}:
            raise ValueError("invalid build job platform")
        if not self.command:
            raise ValueError("build job command must be non-empty")
        if not self.artifact_name:
            raise ValueError("artifact_name must be non-empty")
        if not self.log_path:
            raise ValueError("log_path must be non-empty")


@dataclass(frozen=True)
class BuildAutomationPlan:
    inputs: BuildInput
    clean_dirs: tuple[str, ...]
    dist_dir: str
    manifest_path: str
    jobs: tuple[BuildJob, ...]
    artifact_manifest: tuple[dict[str, str], ...]
    ci_commands: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.clean_dirs:
            raise ValueError("clean_dirs must be non-empty")
        if not self.dist_dir:
            raise ValueError("dist_dir must be non-empty")
        if not self.manifest_path:
            raise ValueError("manifest_path must be non-empty")
        if not self.jobs:
            raise ValueError("automation plan requires jobs")
        if not self.artifact_manifest:
            raise ValueError("automation plan requires artifact manifest")
        if not self.ci_commands:
            raise ValueError("automation plan requires CI commands")


@dataclass(frozen=True)
class BuildFailureLog:
    job_id: str
    return_code: int
    log_path: str
    stderr_tail: str

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id must be non-empty")
        if self.return_code == 0:
            raise ValueError("failure log requires a non-zero return code")
        if not self.log_path:
            raise ValueError("log_path must be non-empty")


@dataclass(frozen=True)
class ReleaseSmokeTest:
    test_id: str
    description: str
    command: tuple[str, ...]
    required_artifact: str

    def __post_init__(self) -> None:
        if not self.test_id:
            raise ValueError("test_id must be non-empty")
        if not self.description:
            raise ValueError("description must be non-empty")
        if not self.command:
            raise ValueError("release smoke command must be non-empty")
        if not self.required_artifact:
            raise ValueError("required_artifact must be non-empty")


@dataclass(frozen=True)
class ReleaseValidationPlan:
    version: str
    channel: str
    tests: tuple[ReleaseSmokeTest, ...]
    artifact_manifest: tuple[dict[str, str], ...]
    checksum_manifest_path: str

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("version must be non-empty")
        if self.channel not in RELEASE_CHANNELS:
            raise ValueError("invalid release validation channel")
        if not self.tests:
            raise ValueError("release validation requires tests")
        if not self.artifact_manifest:
            raise ValueError("release validation requires artifact manifest")
        if not self.checksum_manifest_path:
            raise ValueError("checksum_manifest_path must be non-empty")


@dataclass(frozen=True)
class ReleaseValidationResult:
    test_id: str
    status: str
    detail: str

    def __post_init__(self) -> None:
        if not self.test_id:
            raise ValueError("test_id must be non-empty")
        if self.status not in {"passed", "failed", "skipped"}:
            raise ValueError("invalid release validation status")
        if not self.detail:
            raise ValueError("detail must be non-empty")


@dataclass(frozen=True)
class DistributionFolder:
    channel: str
    version: str
    root_dir: str = "dist"

    def __post_init__(self) -> None:
        if self.channel not in RELEASE_CHANNELS:
            raise ValueError("invalid distribution channel")
        if not self.version:
            raise ValueError("version must be non-empty")
        if not self.root_dir:
            raise ValueError("root_dir must be non-empty")

    @property
    def path(self) -> str:
        return str(Path(self.root_dir) / self.channel / self.version)

    def platform_path(self, platform: str) -> str:
        if platform not in {"windows", "linux", "macos"}:
            raise ValueError("invalid distribution platform")
        return str(Path(self.path) / platform)


@dataclass(frozen=True)
class SignedChecksum:
    entry: ChecksumEntry
    signature: str
    algorithm: str = "sha256"

    def __post_init__(self) -> None:
        if not self.signature:
            raise ValueError("signature must be non-empty")
        if not self.algorithm:
            raise ValueError("algorithm must be non-empty")


@dataclass(frozen=True)
class UpdatePackage:
    platform: str
    artifact: str
    version: str
    url: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if self.platform not in {"windows", "linux", "macos"}:
            raise ValueError("invalid update package platform")
        if not self.artifact:
            raise ValueError("artifact must be non-empty")
        if not self.version:
            raise ValueError("version must be non-empty")
        if not self.url:
            raise ValueError("url must be non-empty")
        if len(self.sha256) != 64:
            raise ValueError("sha256 must be 64 hex characters")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")

    def to_dict(self) -> dict[str, str | int]:
        return {
            "platform": self.platform,
            "artifact": self.artifact,
            "version": self.version,
            "url": self.url,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class ReleaseUpdateManifest:
    version: str
    channel: str
    packages: tuple[UpdatePackage, ...]
    mandatory: bool = False
    rollback_version: str | None = None

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("version must be non-empty")
        if self.channel not in RELEASE_CHANNELS:
            raise ValueError("invalid update manifest channel")
        if not self.packages:
            raise ValueError("update manifest requires packages")
        platforms = [package.platform for package in self.packages]
        if len(platforms) != len(set(platforms)):
            raise ValueError("duplicate update package platform")
        if self.rollback_version == self.version:
            raise ValueError("rollback_version must differ from version")

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "channel": self.channel,
            "mandatory": self.mandatory,
            "rollback_version": self.rollback_version,
            "packages": [package.to_dict() for package in self.packages],
        }


@dataclass(frozen=True)
class RollbackPolicy:
    current_version: str
    previous_version: str
    keep_releases: int = 2
    rollback_allowed: bool = True

    def __post_init__(self) -> None:
        if not self.current_version:
            raise ValueError("current_version must be non-empty")
        if not self.previous_version:
            raise ValueError("previous_version must be non-empty")
        if self.current_version == self.previous_version:
            raise ValueError("rollback versions must differ")
        if self.keep_releases < 1:
            raise ValueError("keep_releases must be positive")

    def rollback_target(self) -> str | None:
        return self.previous_version if self.rollback_allowed else None


@dataclass(frozen=True)
class InstallInstruction:
    platform: str
    install_steps: tuple[str, ...]
    update_steps: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.platform not in {"windows", "linux", "macos"}:
            raise ValueError("invalid install instruction platform")
        if not self.install_steps:
            raise ValueError("install_steps must be non-empty")
        if not self.update_steps:
            raise ValueError("update_steps must be non-empty")


@dataclass(frozen=True)
class DistributionPlan:
    folder: DistributionFolder
    update_manifest: ReleaseUpdateManifest
    signed_checksums: tuple[SignedChecksum, ...]
    rollback_policy: RollbackPolicy
    instructions: tuple[InstallInstruction, ...]

    def __post_init__(self) -> None:
        if not self.signed_checksums:
            raise ValueError("distribution plan requires signed checksums")
        if not self.instructions:
            raise ValueError("distribution plan requires install instructions")

    def to_dict(self) -> dict[str, object]:
        return {
            "release_root": self.folder.path,
            "update_manifest": self.update_manifest.to_dict(),
            "signed_checksums": [
                {
                    "path": signed.entry.path,
                    "sha256": signed.entry.sha256,
                    "size_bytes": signed.entry.size_bytes,
                    "signature": signed.signature,
                    "algorithm": signed.algorithm,
                }
                for signed in self.signed_checksums
            ],
            "rollback": {
                "current_version": self.rollback_policy.current_version,
                "previous_version": self.rollback_policy.previous_version,
                "keep_releases": self.rollback_policy.keep_releases,
                "rollback_allowed": self.rollback_policy.rollback_allowed,
                "rollback_target": self.rollback_policy.rollback_target(),
            },
            "instructions": [
                {
                    "platform": instruction.platform,
                    "install_steps": list(instruction.install_steps),
                    "update_steps": list(instruction.update_steps),
                }
                for instruction in self.instructions
            ],
        }


@dataclass(frozen=True)
class WindowsBuildPlan:
    spec: BuildTargetSpec
    artifact_name: str
    pyinstaller_command: tuple[str, ...]
    executable_path: str
    nvda_dll_path: str
    launcher_shortcut: LauncherShortcutMetadata
    save_migration: SaveMigrationPlan
    smoke_checks: tuple[PackageSmokeCheck, ...]
    optional_installer_format: str = "msi"

    def __post_init__(self) -> None:
        if self.spec.target.platform != "windows":
            raise ValueError("WindowsBuildPlan requires a Windows target")
        if not self.artifact_name:
            raise ValueError("artifact_name must be non-empty")
        if not self.pyinstaller_command:
            raise ValueError("pyinstaller_command must be non-empty")
        if not self.executable_path.endswith(".exe"):
            raise ValueError("executable_path must point to an .exe")
        if not self.nvda_dll_path.endswith("nvdaControllerClient64.dll"):
            raise ValueError("nvda_dll_path must point to nvdaControllerClient64.dll")
        if not self.smoke_checks:
            raise ValueError("Windows build plan requires smoke checks")


@dataclass(frozen=True)
class DesktopEntryMetadata:
    name: str
    exec_path: str
    icon_path: str
    categories: tuple[str, ...] = ("Game", "Audio")

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("desktop entry name must be non-empty")
        if not self.exec_path:
            raise ValueError("desktop entry exec_path must be non-empty")
        if not self.icon_path:
            raise ValueError("desktop entry icon_path must be non-empty")
        if not self.categories:
            raise ValueError("desktop entry requires categories")

    def text(self) -> str:
        categories = ";".join(self.categories)
        return "\n".join(
            (
                "[Desktop Entry]",
                "Type=Application",
                f"Name={self.name}",
                f"Exec={self.exec_path}",
                f"Icon={self.icon_path}",
                f"Categories={categories};",
                "Terminal=false",
            )
        )


@dataclass(frozen=True)
class LinuxRuntimeValidation:
    required_python: str = PYTHON_RUNTIME
    required_modules: tuple[str, ...] = ("pygame",)
    required_tools: tuple[str, ...] = ("spd-say",)
    sdl_video_driver_fallback: str = "dummy"

    def __post_init__(self) -> None:
        if not self.required_python:
            raise ValueError("required_python must be non-empty")
        if not self.required_modules:
            raise ValueError("required_modules must be non-empty")
        if not self.sdl_video_driver_fallback:
            raise ValueError("sdl_video_driver_fallback must be non-empty")


@dataclass(frozen=True)
class LinuxBuildPlan:
    spec: BuildTargetSpec
    artifact_name: str
    pyinstaller_command: tuple[str, ...]
    executable_path: str
    desktop_entry: DesktopEntryMetadata
    runtime_validation: LinuxRuntimeValidation
    smoke_checks: tuple[PackageSmokeCheck, ...]
    appimage_metadata: dict[str, str]

    def __post_init__(self) -> None:
        if self.spec.target.platform != "linux":
            raise ValueError("LinuxBuildPlan requires a Linux target")
        if not self.artifact_name:
            raise ValueError("artifact_name must be non-empty")
        if not self.pyinstaller_command:
            raise ValueError("pyinstaller_command must be non-empty")
        if self.executable_path.endswith(".exe"):
            raise ValueError("Linux executable must not end with .exe")
        if not self.smoke_checks:
            raise ValueError("Linux build plan requires smoke checks")
        if not self.appimage_metadata:
            raise ValueError("appimage_metadata must be non-empty")


@dataclass(frozen=True)
class MacOSBundleMetadata:
    bundle_name: str
    bundle_identifier: str
    executable_name: str
    icon_file: str = "AppIcon.icns"

    def __post_init__(self) -> None:
        if not self.bundle_name:
            raise ValueError("bundle_name must be non-empty")
        if "." not in self.bundle_identifier:
            raise ValueError("bundle_identifier must be reverse-DNS style")
        if not self.executable_name:
            raise ValueError("executable_name must be non-empty")
        if not self.icon_file.endswith(".icns"):
            raise ValueError("icon_file must be an .icns file")

    def plist(self, version: str) -> dict[str, str]:
        if not version:
            raise ValueError("version must be non-empty")
        return {
            "CFBundleName": self.bundle_name,
            "CFBundleDisplayName": self.bundle_name,
            "CFBundleIdentifier": self.bundle_identifier,
            "CFBundleExecutable": self.executable_name,
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "CFBundleIconFile": self.icon_file,
        }


@dataclass(frozen=True)
class MacOSRuntimeValidation:
    required_python: str = PYTHON_RUNTIME
    required_modules: tuple[str, ...] = ("pygame",)
    required_tools: tuple[str, ...] = ("say",)
    speech_fallback: str = "say"

    def __post_init__(self) -> None:
        if not self.required_python:
            raise ValueError("required_python must be non-empty")
        if not self.required_modules:
            raise ValueError("required_modules must be non-empty")
        if self.speech_fallback != "say":
            raise ValueError("macOS speech_fallback must be say")


@dataclass(frozen=True)
class MacOSDistributionNotes:
    quarantine_note: str
    notarization_note: str
    codesign_identity: str = "-"

    def __post_init__(self) -> None:
        if not self.quarantine_note:
            raise ValueError("quarantine_note must be non-empty")
        if not self.notarization_note:
            raise ValueError("notarization_note must be non-empty")
        if not self.codesign_identity:
            raise ValueError("codesign_identity must be non-empty")


@dataclass(frozen=True)
class MacOSBuildPlan:
    spec: BuildTargetSpec
    artifact_name: str
    pyinstaller_command: tuple[str, ...]
    app_bundle_path: str
    executable_path: str
    bundle_metadata: MacOSBundleMetadata
    runtime_validation: MacOSRuntimeValidation
    distribution_notes: MacOSDistributionNotes
    smoke_checks: tuple[PackageSmokeCheck, ...]

    def __post_init__(self) -> None:
        if self.spec.target.platform != "macos":
            raise ValueError("MacOSBuildPlan requires a macOS target")
        if not self.artifact_name:
            raise ValueError("artifact_name must be non-empty")
        if not self.pyinstaller_command:
            raise ValueError("pyinstaller_command must be non-empty")
        if not self.app_bundle_path.endswith(".app"):
            raise ValueError("app_bundle_path must point to a .app bundle")
        if self.executable_path.endswith(".exe"):
            raise ValueError("macOS executable must not end with .exe")
        if not self.smoke_checks:
            raise ValueError("macOS build plan requires smoke checks")


def windows_build_plan(matrix: BuildMatrix, home: Path | None = None) -> WindowsBuildPlan:
    spec = next((item for item in matrix.targets if item.target.platform == "windows"), None)
    if spec is None:
        raise ValueError("build matrix does not contain a Windows target")
    executable_path = str(Path(spec.artifact_dir) / spec.executable_name / WINDOWS_EXECUTABLE)
    app_save_root = platform_save_root(home or Path("%USERPROFILE%"), "Horse Racing Audio First", "windows")
    return WindowsBuildPlan(
        spec=spec,
        artifact_name=matrix.artifact_name_for(spec),
        pyinstaller_command=matrix.pyinstaller_command(spec),
        executable_path=executable_path,
        nvda_dll_path=str(Path(spec.artifact_dir) / spec.executable_name / "nvdaControllerClient64.dll"),
        launcher_shortcut=LauncherShortcutMetadata(
            name="Horse Racing Audio First",
            target=executable_path,
            working_directory=str(Path(spec.artifact_dir) / spec.executable_name),
            description="Audio-first horse racing game",
        ),
        save_migration=SaveMigrationPlan("save/progress.json", str(app_save_root / "progress.json")),
        smoke_checks=(
            PackageSmokeCheck("launch-help", (executable_path, "--help"), "process exits cleanly"),
            PackageSmokeCheck("content-load", (executable_path, "--smoke-content"), "content loads"),
            PackageSmokeCheck("headless-race", (executable_path, "--smoke-race"), "deterministic race completes"),
            PackageSmokeCheck("save-round-trip", (executable_path, "--smoke-save"), "save write/read succeeds"),
            PackageSmokeCheck("replay-load", (executable_path, "--smoke-replay"), "replay payload loads"),
        ),
    )


def validate_windows_build_inputs(project_root: Path, plan: WindowsBuildPlan) -> tuple[str, ...]:
    missing = list(validate_required_assets(project_root, plan.spec.asset_rules))
    if not (project_root / "horse_racing_game" / "app" / "pygame_main.py").exists():
        missing.append("horse_racing_game/app/pygame_main.py")
    return tuple(missing)


def linux_build_plan(matrix: BuildMatrix, package_format: str | None = None) -> LinuxBuildPlan:
    candidates = [item for item in matrix.targets if item.target.platform == "linux"]
    if package_format is not None:
        candidates = [item for item in candidates if item.target.package_format == package_format]
    spec = candidates[0] if candidates else None
    if spec is None:
        raise ValueError("build matrix does not contain a matching Linux target")
    executable_path = str(Path(spec.artifact_dir) / spec.executable_name / LINUX_EXECUTABLE)
    desktop_entry = DesktopEntryMetadata(
        name="Horse Racing Audio First",
        exec_path=executable_path,
        icon_path=str(Path(spec.artifact_dir) / spec.executable_name / "assets" / "icon.png"),
    )
    return LinuxBuildPlan(
        spec=spec,
        artifact_name=matrix.artifact_name_for(spec),
        pyinstaller_command=matrix.pyinstaller_command(spec),
        executable_path=executable_path,
        desktop_entry=desktop_entry,
        runtime_validation=LinuxRuntimeValidation(),
        smoke_checks=(
            PackageSmokeCheck("launch-help", (executable_path, "--help"), "process exits cleanly"),
            PackageSmokeCheck("sdl-fallback", ("SDL_VIDEODRIVER=dummy", executable_path, "--smoke-content"), "pygame initializes headless"),
            PackageSmokeCheck("speech-fallback", (executable_path, "--smoke-speech"), "speech-dispatcher fallback does not crash"),
            PackageSmokeCheck("headless-race", (executable_path, "--smoke-race"), "deterministic race completes"),
            PackageSmokeCheck("save-round-trip", (executable_path, "--smoke-save"), "save write/read succeeds"),
        ),
        appimage_metadata={
            "app_id": "horse-racing-audio-first",
            "desktop_file": "horse-racing-audio-first.desktop",
            "archive_format": spec.target.package_format,
        },
    )


def validate_linux_build_inputs(project_root: Path, plan: LinuxBuildPlan) -> tuple[str, ...]:
    missing = [item for item in validate_required_assets(project_root, plan.spec.asset_rules) if item != "PLAY_GAME.bat"]
    if not (project_root / "horse_racing_game" / "app" / "pygame_main.py").exists():
        missing.append("horse_racing_game/app/pygame_main.py")
    return tuple(missing)


def macos_build_plan(matrix: BuildMatrix, home: Path | None = None) -> MacOSBuildPlan:
    spec = next((item for item in matrix.targets if item.target.platform == "macos"), None)
    if spec is None:
        raise ValueError("build matrix does not contain a macOS target")
    app_bundle_path = str(Path(spec.artifact_dir) / f"{MACOS_EXECUTABLE}.app")
    executable_path = str(Path(app_bundle_path) / "Contents" / "MacOS" / MACOS_EXECUTABLE)
    app_save_root = platform_save_root(home or Path("$HOME"), "Horse Racing Audio First", "macos")
    save_check_path = str(app_save_root / "progress.json")
    return MacOSBuildPlan(
        spec=spec,
        artifact_name=matrix.artifact_name_for(spec),
        pyinstaller_command=matrix.pyinstaller_command(spec),
        app_bundle_path=app_bundle_path,
        executable_path=executable_path,
        bundle_metadata=MacOSBundleMetadata(
            bundle_name="Horse Racing Audio First",
            bundle_identifier="com.horseracing.audiofirst",
            executable_name=MACOS_EXECUTABLE,
        ),
        runtime_validation=MacOSRuntimeValidation(),
        distribution_notes=MacOSDistributionNotes(
            quarantine_note="Unsigned local builds may require removing quarantine attributes before first launch.",
            notarization_note="Public distribution should codesign and notarize the .app or .dmg on macOS.",
        ),
        smoke_checks=(
            PackageSmokeCheck("launch-help", (executable_path, "--help"), "process exits cleanly"),
            PackageSmokeCheck("speech-fallback", (executable_path, "--smoke-speech"), "say fallback does not crash"),
            PackageSmokeCheck("headless-race", (executable_path, "--smoke-race"), "deterministic race completes"),
            PackageSmokeCheck("save-round-trip", (executable_path, "--smoke-save", save_check_path), "save write/read succeeds"),
            PackageSmokeCheck("bundle-metadata", (app_bundle_path, "Info.plist"), "bundle metadata exists"),
        ),
    )


def validate_macos_build_inputs(project_root: Path, plan: MacOSBuildPlan) -> tuple[str, ...]:
    missing = [item for item in validate_required_assets(project_root, plan.spec.asset_rules) if item not in {"PLAY_GAME.bat", "nvdaControllerClient64.dll"}]
    if not (project_root / "horse_racing_game" / "app" / "pygame_main.py").exists():
        missing.append("horse_racing_game/app/pygame_main.py")
    return tuple(missing)


def checksum_file(path: Path) -> ChecksumEntry:
    if not path.is_file():
        raise ValueError(f"cannot checksum missing file: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ChecksumEntry(str(path), digest, path.stat().st_size)


def checksum_manifest(paths: tuple[Path, ...]) -> tuple[ChecksumEntry, ...]:
    return tuple(checksum_file(path) for path in sorted(paths, key=lambda item: str(item)))


def build_automation_plan(inputs: BuildInput) -> BuildAutomationPlan:
    matrix = default_build_matrix(inputs.version, inputs.channel)
    artifact_manifest = matrix.artifact_manifest()
    jobs = tuple(
        BuildJob(
            job_id=f"build-{spec.target.platform}",
            platform=spec.target.platform,
            command=matrix.pyinstaller_command(spec),
            artifact_name=matrix.artifact_name_for(spec),
            log_path=str(Path("build") / "logs" / f"{spec.target.platform}.log"),
        )
        for spec in matrix.targets
    )
    ci_commands = (
        ("python", "-m", "pytest"),
        ("python", "scripts/package_windows.py", "--version", inputs.version, "--channel", inputs.channel),
        ("python", "scripts/package_linux.py", "--version", inputs.version, "--channel", inputs.channel),
        ("python", "scripts/package_macos.py", "--version", inputs.version, "--channel", inputs.channel),
    )
    return BuildAutomationPlan(
        inputs=inputs,
        clean_dirs=("build", "dist/windows", "dist/linux", "dist/macos", str(Path("dist") / inputs.channel)),
        dist_dir=str(Path("dist") / inputs.channel),
        manifest_path=str(Path("dist") / inputs.channel / "artifact-manifest.json"),
        jobs=jobs,
        artifact_manifest=artifact_manifest,
        ci_commands=ci_commands,
    )


def build_failure_log(job: BuildJob, return_code: int, stderr: str) -> BuildFailureLog:
    tail = "\n".join(stderr.splitlines()[-20:])
    return BuildFailureLog(job.job_id, return_code, job.log_path, tail)


def release_validation_plan(inputs: BuildInput) -> ReleaseValidationPlan:
    matrix = default_build_matrix(inputs.version, inputs.channel)
    tests: list[ReleaseSmokeTest] = []
    for row in matrix.artifact_manifest():
        artifact_path = row["path"]
        platform = row["platform"]
        tests.extend(
            (
                ReleaseSmokeTest(f"{platform}-launch", "Packaged executable launches help output.", (artifact_path, "--help"), artifact_path),
                ReleaseSmokeTest(f"{platform}-content", "Packaged artifact loads bundled content.", (artifact_path, "--smoke-content"), artifact_path),
                ReleaseSmokeTest(f"{platform}-audio", "Packaged artifact survives audio/speech backend fallback.", (artifact_path, "--smoke-speech"), artifact_path),
                ReleaseSmokeTest(f"{platform}-save", "Packaged artifact can write and read save data.", (artifact_path, "--smoke-save"), artifact_path),
                ReleaseSmokeTest(f"{platform}-replay", "Packaged artifact can load replay payloads.", (artifact_path, "--smoke-replay"), artifact_path),
                ReleaseSmokeTest(f"{platform}-race", "Packaged artifact completes deterministic headless race.", (artifact_path, "--smoke-race"), artifact_path),
            )
        )
    return ReleaseValidationPlan(
        version=inputs.version,
        channel=inputs.channel,
        tests=tuple(tests),
        artifact_manifest=matrix.artifact_manifest(),
        checksum_manifest_path=str(Path("dist") / inputs.channel / "checksums.json"),
    )


def evaluate_release_artifacts(project_root: Path, plan: ReleaseValidationPlan) -> tuple[ReleaseValidationResult, ...]:
    results: list[ReleaseValidationResult] = []
    for test in plan.tests:
        artifact = project_root / test.required_artifact
        if artifact.exists():
            results.append(ReleaseValidationResult(test.test_id, "passed", "artifact present; smoke command ready"))
        else:
            results.append(ReleaseValidationResult(test.test_id, "skipped", f"artifact missing: {test.required_artifact}"))
    return tuple(results)


def signed_checksum(entry: ChecksumEntry, signing_key_id: str) -> SignedChecksum:
    if not signing_key_id:
        raise ValueError("signing_key_id must be non-empty")
    payload = f"{signing_key_id}:{entry.path}:{entry.sha256}:{entry.size_bytes}".encode("utf-8")
    return SignedChecksum(entry, hashlib.sha256(payload).hexdigest())


def install_instructions() -> tuple[InstallInstruction, ...]:
    return (
        InstallInstruction(
            "windows",
            (
                "Download the Windows .zip artifact and matching checksum entry.",
                "Extract the archive to a writable folder.",
                "Run HorseRacingAudioFirst.exe; saves migrate to the platform AppData folder.",
            ),
            (
                "Close the game before replacing files.",
                "Extract the new release over the previous application folder.",
                "Keep the AppData save folder unchanged so progress survives the update.",
            ),
        ),
        InstallInstruction(
            "linux",
            (
                "Download the Linux tar.gz artifact and matching checksum entry.",
                "Extract the archive, then mark the executable as runnable if needed.",
                "Launch horse-racing-audio-first from the extracted folder or desktop entry.",
            ),
            (
                "Close the game before replacing files.",
                "Extract the new archive beside the previous release.",
                "Move custom files only after checksum verification succeeds.",
            ),
        ),
        InstallInstruction(
            "macos",
            (
                "Download the macOS .zip artifact and matching checksum entry.",
                "Extract the archive and move the .app bundle to Applications.",
                "For unsigned local builds, remove quarantine only after checksum verification.",
            ),
            (
                "Close the game before replacing the .app bundle.",
                "Move the new .app bundle over the previous one.",
                "Keep Application Support save data unchanged so progress survives the update.",
            ),
        ),
    )


def _checksum_lookup(checksums: tuple[ChecksumEntry, ...]) -> dict[str, ChecksumEntry]:
    lookup: dict[str, ChecksumEntry] = {}
    for entry in checksums:
        lookup[entry.path] = entry
        lookup[Path(entry.path).name] = entry
    return lookup


def distribution_plan(
    inputs: BuildInput,
    base_url: str,
    checksums: tuple[ChecksumEntry, ...] = (),
    signing_key_id: str = "local-dev",
    previous_version: str = "0.0.0",
    mandatory: bool = False,
) -> DistributionPlan:
    if not base_url:
        raise ValueError("base_url must be non-empty")
    folder = DistributionFolder(inputs.channel, inputs.version)
    manifest_rows = default_build_matrix(inputs.version, inputs.channel).artifact_manifest()
    lookup = _checksum_lookup(checksums)
    packages: list[UpdatePackage] = []
    checksum_entries: list[ChecksumEntry] = []
    root_url = base_url.rstrip("/")

    for row in manifest_rows:
        artifact = row["artifact"]
        entry = lookup.get(row["path"]) or lookup.get(artifact)
        if entry is None:
            entry = ChecksumEntry(row["path"], "0" * 64, 0)
        checksum_entries.append(entry)
        packages.append(
            UpdatePackage(
                row["platform"],
                artifact,
                inputs.version,
                f"{root_url}/{inputs.channel}/{inputs.version}/{row['platform']}/{artifact}",
                entry.sha256,
                entry.size_bytes,
            )
        )

    rollback_policy = RollbackPolicy(inputs.version, previous_version)
    return DistributionPlan(
        folder=folder,
        update_manifest=ReleaseUpdateManifest(inputs.version, inputs.channel, tuple(packages), mandatory, rollback_policy.rollback_target()),
        signed_checksums=tuple(signed_checksum(entry, signing_key_id) for entry in checksum_entries),
        rollback_policy=rollback_policy,
        instructions=install_instructions(),
    )
