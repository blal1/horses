from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _gradle_command(android_root: Path) -> tuple[str, ...]:
    windows_wrapper = android_root / "gradlew.bat"
    unix_wrapper = android_root / "gradlew"
    if windows_wrapper.is_file():
        return (str(windows_wrapper), "-p", str(android_root))
    if unix_wrapper.is_file():
        return (str(unix_wrapper), "-p", str(android_root))
    return ("gradle", "-p", str(android_root))


def android_release_plan(version: str, channel: str) -> dict[str, object]:
    if not version:
        raise ValueError("version must be non-empty")
    if channel not in {"stable", "beta", "dev"}:
        raise ValueError("invalid channel")
    android_root = Path("android")
    package_id = "com.horseracing.audiofirst"
    debug_package_id = f"{package_id}.debug"
    gradle_command = _gradle_command(android_root)
    return {
        "version": version,
        "channel": channel,
        "android_root": str(android_root),
        "package_id": package_id,
        "debug_package_id": debug_package_id,
        "signing_properties": str(android_root / "keystore.properties"),
        "signing_properties_example": str(android_root / "keystore.properties.example"),
        "artifacts": {
            "debug_apk": str(android_root / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"),
            "release_aab": str(android_root / "app" / "build" / "outputs" / "bundle" / "release" / "app-release.aab"),
        },
        "commands": {
            "debug_apk": gradle_command + (":app:assembleDebug",),
            "release_aab": gradle_command + (":app:bundleRelease",),
            "install_debug": ("adb", "install", "-r", str(android_root / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk")),
            "launch_debug": ("adb", "shell", "am", "start", "-n", f"{debug_package_id}/{package_id}.MainActivity"),
        },
        "device_smoke_checks": (
            "Install debug APK with adb.",
            "Launch MainActivity and confirm RaceSurfaceView is visible.",
            "Swipe up/down and double tap; confirm TalkBack announcements and haptic feedback.",
            "Trigger status command; confirm TextToSpeech output and audio focus behavior.",
            "Play registered cue resources through SoundPool once raw assets are packaged.",
        ),
        "release_notes": (
            "Release AAB requires android/keystore.properties with a production keystore.",
            "Do not commit keystore files or real signing passwords.",
            "Run device smoke checks on at least one TalkBack-enabled Android device before upload.",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Android APK/AAB packaging and device smoke metadata.")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--channel", default="stable", choices=("stable", "beta", "dev"))
    args = parser.parse_args()

    print(json.dumps(android_release_plan(args.version, args.channel), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
