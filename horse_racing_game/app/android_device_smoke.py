from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


ANDROID_PACKAGE_ID = "com.horseracing.audiofirst"
ANDROID_DEBUG_PACKAGE_ID = f"{ANDROID_PACKAGE_ID}.debug"
ANDROID_MAIN_ACTIVITY = f"{ANDROID_PACKAGE_ID}.MainActivity"


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    state: str
    description: str = ""

    @property
    def usable(self) -> bool:
        return self.state == "device"


@dataclass(frozen=True)
class AndroidDeviceSmokePlan:
    apk_path: Path
    package_id: str = ANDROID_DEBUG_PACKAGE_ID
    activity: str = ANDROID_MAIN_ACTIVITY

    @property
    def component(self) -> str:
        return f"{self.package_id}/{self.activity}"

    def install_command(self, adb_path: str, serial: str | None = None) -> tuple[str, ...]:
        command = [adb_path]
        if serial:
            command.extend(("-s", serial))
        command.extend(("install", "-r", str(self.apk_path)))
        return tuple(command)

    def launch_command(self, adb_path: str, serial: str | None = None) -> tuple[str, ...]:
        command = [adb_path]
        if serial:
            command.extend(("-s", serial))
        command.extend(("shell", "am", "start", "-n", self.component))
        return tuple(command)

    def focus_check_command(self, adb_path: str, serial: str | None = None) -> tuple[str, ...]:
        command = [adb_path]
        if serial:
            command.extend(("-s", serial))
        command.extend(("shell", "dumpsys", "window", "windows"))
        return tuple(command)


def parse_adb_devices(output: str) -> tuple[AdbDevice, ...]:
    devices: list[AdbDevice] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        columns = line.split()
        if len(columns) < 2:
            continue
        serial, state = columns[0], columns[1]
        devices.append(AdbDevice(serial=serial, state=state, description=" ".join(columns[2:])))
    return tuple(devices)


def run_android_device_smoke(
    adb_path: str,
    apk_path: Path,
    *,
    serial: str | None = None,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    if not apk_path.is_file():
        return {
            "ready": False,
            "skipped": False,
            "reason": "missing_apk",
            "apk_path": str(apk_path),
        }

    devices_result = subprocess.run(
        (adb_path, "devices", "-l"),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    devices = parse_adb_devices(devices_result.stdout)
    usable_devices = [device for device in devices if device.usable]
    if serial:
        usable_devices = [device for device in usable_devices if device.serial == serial]
    if not usable_devices:
        return {
            "ready": False,
            "skipped": True,
            "reason": "no_connected_device",
            "devices": [device.__dict__ for device in devices],
            "apk_path": str(apk_path),
        }

    selected = usable_devices[0]
    plan = AndroidDeviceSmokePlan(apk_path=apk_path)
    install_result = subprocess.run(
        plan.install_command(adb_path, selected.serial),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if install_result.returncode != 0:
        return {
            "ready": False,
            "skipped": False,
            "reason": "install_failed",
            "device": selected.__dict__,
            "stdout": install_result.stdout,
            "stderr": install_result.stderr,
            "apk_path": str(apk_path),
        }

    launch_result = subprocess.run(
        plan.launch_command(adb_path, selected.serial),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if launch_result.returncode != 0:
        return {
            "ready": False,
            "skipped": False,
            "reason": "launch_failed",
            "device": selected.__dict__,
            "stdout": launch_result.stdout,
            "stderr": launch_result.stderr,
            "apk_path": str(apk_path),
        }

    return {
        "ready": True,
        "skipped": False,
        "reason": "installed_and_launched",
        "device": selected.__dict__,
        "component": plan.component,
        "apk_path": str(apk_path),
        "manual_checks": (
            "Confirm RaceSurfaceView is visible.",
            "Enable TalkBack and confirm status/action announcements.",
            "Swipe up/down, double tap, long press, and drag steering/pace.",
            "Confirm haptics, TTS output, audio focus ducking, and save path behavior.",
        ),
    }
