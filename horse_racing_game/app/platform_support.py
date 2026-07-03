from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from horse_racing_game.input.commands import RaceCommand


SUPPORTED_PLATFORMS = {"windows", "linux", "macos", "android"}
PACKAGE_FORMATS = {
    "windows": ("zip", "msi"),
    "linux": ("tar.gz", "appimage"),
    "macos": ("zip", "dmg"),
    "android": ("apk", "aab"),
}
CONTROL_ACTIONS = {"throttle_up", "throttle_down", "steer_left", "steer_right", "push", "jump", "duck", "status"}
UPDATE_CHANNELS = {"stable", "beta", "dev"}


@dataclass(frozen=True)
class PlatformTarget:
    platform: str
    architecture: str = "x64"
    package_format: str = "zip"

    def __post_init__(self) -> None:
        if self.platform not in SUPPORTED_PLATFORMS:
            raise ValueError("unsupported platform")
        if not self.architecture:
            raise ValueError("architecture must be non-empty")
        if self.package_format not in PACKAGE_FORMATS[self.platform]:
            raise ValueError("unsupported package format for platform")

    @property
    def artifact_suffix(self) -> str:
        return f"{self.platform}-{self.architecture}.{self.package_format}"


@dataclass(frozen=True)
class PackageManifest:
    app_name: str
    version: str
    entry_point: str
    targets: tuple[PlatformTarget, ...]
    include_paths: tuple[str, ...] = ("content", "assets", "PLAY_GAME.bat")

    def __post_init__(self) -> None:
        if not self.app_name:
            raise ValueError("app_name must be non-empty")
        if not self.version:
            raise ValueError("version must be non-empty")
        if not self.entry_point:
            raise ValueError("entry_point must be non-empty")
        if not self.targets:
            raise ValueError("at least one package target is required")
        if any(not path for path in self.include_paths):
            raise ValueError("include paths must be non-empty")

    def artifact_names(self) -> tuple[str, ...]:
        safe_name = self.app_name.lower().replace(" ", "-")
        return tuple(f"{safe_name}-{self.version}-{target.artifact_suffix}" for target in self.targets)


@dataclass(frozen=True)
class ControllerBinding:
    action: str
    control: str

    def __post_init__(self) -> None:
        if self.action not in CONTROL_ACTIONS:
            raise ValueError("unknown control action")
        if not self.control:
            raise ValueError("control must be non-empty")


@dataclass(frozen=True)
class ControlRemapProfile:
    profile_id: str
    bindings: tuple[ControllerBinding, ...]
    analog_deadzone: float = 0.15

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id must be non-empty")
        actions = [binding.action for binding in self.bindings]
        if len(actions) != len(set(actions)):
            raise ValueError("duplicate control action binding")
        if not 0.0 <= self.analog_deadzone < 1.0:
            raise ValueError("analog_deadzone must be in [0, 1)")

    def control_for(self, action: str) -> str | None:
        return next((binding.control for binding in self.bindings if binding.action == action), None)

    def with_binding(self, action: str, control: str) -> ControlRemapProfile:
        binding = ControllerBinding(action, control)
        bindings = tuple(item for item in self.bindings if item.action != action)
        return replace(self, bindings=(*bindings, binding))

    def command_from_actions(self, pressed_actions: set[str]) -> RaceCommand:
        unknown_actions = pressed_actions - CONTROL_ACTIONS
        if unknown_actions:
            raise ValueError("unknown pressed action")
        throttle = (1.0 if "throttle_up" in pressed_actions else 0.0) - (1.0 if "throttle_down" in pressed_actions else 0.0)
        lateral = (1.0 if "steer_right" in pressed_actions else 0.0) - (1.0 if "steer_left" in pressed_actions else 0.0)
        return RaceCommand(
            throttle_delta=throttle,
            lateral_delta=lateral,
            push_requested="push" in pressed_actions,
            jump_requested="jump" in pressed_actions,
            duck_requested="duck" in pressed_actions,
            request_status="status" in pressed_actions,
        )


@dataclass(frozen=True)
class SaveSyncRecord:
    device_id: str
    revision: int
    updated_at_s: float
    checksum: str

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id must be non-empty")
        if self.revision < 0:
            raise ValueError("revision must be non-negative")
        if self.updated_at_s < 0:
            raise ValueError("updated_at_s must be non-negative")
        if not self.checksum:
            raise ValueError("checksum must be non-empty")


@dataclass(frozen=True)
class SaveSyncDecision:
    action: str
    winning_device_id: str | None = None
    conflict: bool = False

    def __post_init__(self) -> None:
        if self.action not in {"noop", "upload", "download", "conflict"}:
            raise ValueError("invalid save sync action")
        if self.action != "noop" and not self.winning_device_id:
            raise ValueError("winning_device_id is required for sync action")


def decide_save_sync(local: SaveSyncRecord, remote: SaveSyncRecord | None) -> SaveSyncDecision:
    if remote is None:
        return SaveSyncDecision("upload", local.device_id)
    if local.checksum == remote.checksum:
        return SaveSyncDecision("noop")
    if local.revision > remote.revision:
        return SaveSyncDecision("upload", local.device_id)
    if remote.revision > local.revision:
        return SaveSyncDecision("download", remote.device_id)
    if local.updated_at_s == remote.updated_at_s:
        return SaveSyncDecision("conflict", local.device_id, True)
    winner = local if local.updated_at_s > remote.updated_at_s else remote
    return SaveSyncDecision("conflict", winner.device_id, True)


@dataclass(frozen=True)
class UpdateManifest:
    current_version: str
    latest_version: str
    channel: str = "stable"
    mandatory: bool = False
    download_url: str = ""

    def __post_init__(self) -> None:
        if not self.current_version:
            raise ValueError("current_version must be non-empty")
        if not self.latest_version:
            raise ValueError("latest_version must be non-empty")
        if self.channel not in UPDATE_CHANNELS:
            raise ValueError("invalid update channel")
        if self.mandatory and not self.download_url:
            raise ValueError("mandatory update requires download_url")

    @property
    def update_available(self) -> bool:
        return _version_tuple(self.latest_version) > _version_tuple(self.current_version)

    def install_prompt(self) -> str:
        if not self.update_available:
            return "Game is up to date."
        prefix = "Mandatory" if self.mandatory else "Optional"
        return f"{prefix} {self.channel} update {self.latest_version} available."


def default_package_manifest(version: str = "0.1.0") -> PackageManifest:
    return PackageManifest(
        app_name="Horse Racing Audio First",
        version=version,
        entry_point="horse-racing-game",
        targets=(
            PlatformTarget("windows", "x64", "zip"),
            PlatformTarget("linux", "x64", "tar.gz"),
            PlatformTarget("macos", "arm64", "zip"),
        ),
    )


def default_controller_profile(profile_id: str = "controller-default") -> ControlRemapProfile:
    return ControlRemapProfile(
        profile_id=profile_id,
        bindings=(
            ControllerBinding("throttle_up", "right_trigger"),
            ControllerBinding("throttle_down", "left_trigger"),
            ControllerBinding("steer_left", "left_stick_left"),
            ControllerBinding("steer_right", "left_stick_right"),
            ControllerBinding("push", "south_button"),
            ControllerBinding("jump", "east_button"),
            ControllerBinding("duck", "west_button"),
            ControllerBinding("status", "north_button"),
        ),
    )


def platform_save_root(home: Path, app_name: str, platform: str) -> Path:
    if not app_name:
        raise ValueError("app_name must be non-empty")
    if platform == "windows":
        return home / "AppData" / "Roaming" / app_name
    if platform == "darwin" or platform == "macos":
        return home / "Library" / "Application Support" / app_name
    if platform == "linux":
        return home / ".local" / "share" / app_name
    if platform == "android":
        return home / "Android" / "data" / "com.horseracing.audiofirst" / "files" / app_name
    raise ValueError("unsupported platform")


def _version_tuple(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as error:
        raise ValueError("versions must use numeric dot-separated parts") from error
