from pathlib import Path
import json
import subprocess

from horse_racing_game.app.android_device_smoke import AndroidDeviceSmokePlan, parse_adb_devices


ROOT = Path(__file__).parent.parent
ANDROID_ROOT = ROOT / "android"


def test_android_gradle_shell_declares_application_module() -> None:
    settings = (ANDROID_ROOT / "settings.gradle.kts").read_text(encoding="utf-8")
    root_build = (ANDROID_ROOT / "build.gradle.kts").read_text(encoding="utf-8")
    app_build = (ANDROID_ROOT / "app" / "build.gradle.kts").read_text(encoding="utf-8")

    assert 'include(":app")' in settings
    assert 'id("com.android.application")' in root_build
    assert 'id("org.jetbrains.kotlin.android")' in root_build
    assert 'namespace = "com.horseracing.audiofirst"' in app_build
    assert 'applicationId = "com.horseracing.audiofirst"' in app_build
    assert "versionName = \"0.1.0\"" in app_build
    assert "signingConfigs" in app_build
    assert "keystore.properties" in app_build
    assert "signingConfig = signingConfigs.getByName(\"release\")" in app_build
    assert "sourceCompatibility = JavaVersion.VERSION_17" in app_build
    assert 'jvmTarget = "17"' in app_build


def test_android_gradle_wrapper_is_generated() -> None:
    wrapper_properties = (ANDROID_ROOT / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text(
        encoding="utf-8"
    )

    assert (ANDROID_ROOT / "gradlew").is_file()
    assert (ANDROID_ROOT / "gradlew.bat").is_file()
    assert (ANDROID_ROOT / "gradle" / "wrapper" / "gradle-wrapper.jar").is_file()
    assert "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.10.2-bin.zip" in wrapper_properties


def test_android_manifest_and_activity_expose_accessible_shell() -> None:
    manifest = (ANDROID_ROOT / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
    activity = (
        ANDROID_ROOT
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "horseracing"
        / "audiofirst"
        / "MainActivity.kt"
    ).read_text(encoding="utf-8")
    strings = (ANDROID_ROOT / "app" / "src" / "main" / "res" / "values" / "strings.xml").read_text(encoding="utf-8")

    assert 'android:name=".MainActivity"' in manifest
    assert 'android:exported="true"' in manifest
    assert "RaceSurfaceView(this)" in activity
    assert "android_shell_status" in strings


def test_android_race_surface_exposes_accessible_touch_contract() -> None:
    surface = (
        ANDROID_ROOT
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "horseracing"
        / "audiofirst"
        / "RaceSurfaceView.kt"
    ).read_text(encoding="utf-8")
    strings = (ANDROID_ROOT / "app" / "src" / "main" / "res" / "values" / "strings.xml").read_text(encoding="utf-8")

    assert "data class MobileRaceCommand" in surface
    assert "override fun onTouchEvent" in surface
    assert "override fun performClick" in surface
    assert "announceForAccessibility" in surface
    assert "performHapticFeedback" in surface
    assert "HapticFeedbackConstants" in surface
    assert "race_surface_description" in strings
    assert "double tap to push" in strings


def test_android_audio_controller_handles_focus_tts_and_low_latency_cues() -> None:
    controller = (
        ANDROID_ROOT
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "horseracing"
        / "audiofirst"
        / "AndroidAudioController.kt"
    ).read_text(encoding="utf-8")
    activity = (
        ANDROID_ROOT
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "horseracing"
        / "audiofirst"
        / "MainActivity.kt"
    ).read_text(encoding="utf-8")
    surface = (
        ANDROID_ROOT
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "horseracing"
        / "audiofirst"
        / "RaceSurfaceView.kt"
    ).read_text(encoding="utf-8")

    assert "AudioFocusRequest.Builder" in controller
    assert "requestAudioFocus" in controller
    assert "abandonAudioFocusRequest" in controller
    assert "TextToSpeech" in controller
    assert "SoundPool.Builder" in controller
    assert "AudioAttributes.USAGE_GAME" in controller
    assert "AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY" in controller
    assert "AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK" in controller
    assert "registerCue" in controller
    assert "handleCommand" in controller
    assert "audioController.start()" in activity
    assert "audioController.stop()" in activity
    assert "audioController.shutdown()" in activity
    assert "setAudioController(audioController)" in activity
    assert "audioController?.handleCommand" in surface


def test_android_release_packaging_metadata_is_declared() -> None:
    keystore_example = (ANDROID_ROOT / "keystore.properties.example").read_text(encoding="utf-8")

    assert "storeFile=release/horse-racing-audio-first.jks" in keystore_example
    assert "keyAlias=horse-racing-audio-first" in keystore_example
    assert "change-me" in keystore_example


def test_android_packaging_script_outputs_release_plan_json() -> None:
    result = subprocess.run(
        ["python", "scripts/package_android.py", "--version", "0.2.0", "--channel", "beta"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert payload["version"] == "0.2.0"
    assert payload["channel"] == "beta"
    assert payload["package_id"] == "com.horseracing.audiofirst"
    assert payload["debug_package_id"] == "com.horseracing.audiofirst.debug"
    assert payload["artifacts"]["debug_apk"].endswith("app-debug.apk")
    assert payload["artifacts"]["release_aab"].endswith("app-release.aab")
    assert payload["commands"]["debug_apk"][-3:] == ["-p", "android", ":app:assembleDebug"]
    assert payload["commands"]["release_aab"][-3:] == ["-p", "android", ":app:bundleRelease"]
    assert payload["commands"]["debug_apk"][0].endswith(("gradlew", "gradlew.bat", "gradle"))
    assert "TalkBack" in payload["device_smoke_checks"][2]
    assert "Do not commit keystore" in payload["release_notes"][1]


def test_android_release_environment_script_reports_build_prerequisites() -> None:
    result = subprocess.run(
        ["python", "scripts/check_android_release_env.py", "--project-root", str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert result.returncode in {0, 1}
    assert payload["android_root"] == str(ANDROID_ROOT)
    assert "gradle_wrapper" in payload
    assert "java_on_path" in payload
    assert "sdk_root_exists" in payload
    assert "ready_for_assemble_debug" in payload
    assert "ready_for_device_smoke" in payload


def test_android_device_smoke_parses_adb_devices_and_builds_commands() -> None:
    devices = parse_adb_devices(
        "\n".join(
            (
                "List of devices attached",
                "emulator-5554 device product:sdk_gphone64 model:sdk_gphone64 transport_id:1",
                "USB123 unauthorized transport_id:2",
            )
        )
    )
    plan = AndroidDeviceSmokePlan(Path("android/app/build/outputs/apk/debug/app-debug.apk"))

    assert [device.serial for device in devices] == ["emulator-5554", "USB123"]
    assert devices[0].usable is True
    assert devices[1].usable is False
    assert plan.component == "com.horseracing.audiofirst.debug/com.horseracing.audiofirst.MainActivity"
    install_command = plan.install_command("adb", "emulator-5554")
    assert install_command[:5] == (
        "adb",
        "-s",
        "emulator-5554",
        "install",
        "-r",
    )
    assert Path(install_command[5]) == Path("android/app/build/outputs/apk/debug/app-debug.apk")
    assert plan.launch_command("adb", "emulator-5554")[-3:] == (
        "start",
        "-n",
        "com.horseracing.audiofirst.debug/com.horseracing.audiofirst.MainActivity",
    )


def test_android_device_smoke_script_skips_when_no_device_is_connected() -> None:
    result = subprocess.run(
        ["python", "scripts/smoke_android_device.py", "--project-root", str(ROOT), "--timeout-seconds", "10"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert result.returncode in {0, 2}
    if result.returncode == 2:
        assert payload["skipped"] is True
        assert payload["reason"] == "no_connected_device"
    else:
        assert payload["ready"] is True


def test_android_mobile_support_doc_mentions_gesture_contract() -> None:
    doc = (ROOT / "docs" / "android-mobile-support.md").read_text(encoding="utf-8")

    assert "Drag horizontally" in doc
    assert "Swipe up" in doc
    assert "Double tap" in doc
    assert "horse_racing_game/input/touch.py" in doc
    assert "RaceSurfaceView" in doc
    assert "AndroidAudioController" in doc
    assert "AudioFocusRequest" in doc
    assert "SoundPool" in doc
    assert "APK" in doc
    assert "AAB" in doc
