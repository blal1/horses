import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from horse_racing_game.audio.nvda_speaker import NvdaSpeaker
from horse_racing_game.audio.speech import (
    LinuxSpeaker,
    MacSpeaker,
    NullSpeaker,
    Speaker,
    create_speaker,
)


ROOT = Path(__file__).parent.parent


class _Recorder:
    def __init__(self, raises: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self._raises = raises

    def __call__(self, args: list[str]) -> None:
        self.calls.append(args)
        if self._raises is not None:
            raise self._raises


class CreateSpeakerTests(unittest.TestCase):
    def test_picks_backend_by_platform(self) -> None:
        self.assertIsInstance(create_speaker(ROOT, platform="darwin"), MacSpeaker)
        self.assertIsInstance(create_speaker(ROOT, platform="linux"), LinuxSpeaker)
        self.assertIsInstance(create_speaker(ROOT, platform="freebsd"), NullSpeaker)

    def test_windows_returns_nvda_speaker(self) -> None:
        speaker = create_speaker(ROOT, platform="win32")
        self.assertIsInstance(speaker, Speaker)
        self.assertEqual(type(speaker).__name__, "NvdaSpeaker")


class NullSpeakerTests(unittest.TestCase):
    def test_speak_is_a_noop(self) -> None:
        NullSpeaker().speak("anything")  # must not raise


class SubprocessSpeakerTests(unittest.TestCase):
    def test_mac_speaker_invokes_say(self) -> None:
        recorder = _Recorder()
        MacSpeaker(ROOT, runner=recorder).speak("Final stretch.")
        self.assertEqual(recorder.calls, [["say", "Final stretch."]])

    def test_linux_speaker_cancels_then_speaks(self) -> None:
        recorder = _Recorder()
        LinuxSpeaker(ROOT, runner=recorder).speak("Turn left.")
        self.assertEqual(recorder.calls, [["spd-say", "-C", "Turn left."]])

    def test_empty_text_is_skipped(self) -> None:
        recorder = _Recorder()
        MacSpeaker(ROOT, runner=recorder).speak("")
        self.assertEqual(recorder.calls, [])

    def test_missing_tool_disables_after_first_failure(self) -> None:
        recorder = _Recorder(raises=FileNotFoundError("say not found"))
        speaker = MacSpeaker(ROOT, runner=recorder)
        speaker.speak("one")
        speaker.speak("two")
        # tried once, failed, then stayed quiet
        self.assertEqual(len(recorder.calls), 1)


class NvdaSpeakerTests(unittest.TestCase):
    def test_loads_client_dll_name_and_interrupts_high_priority_messages(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nvdaControllerClient.dll").write_bytes(b"stub")
            recorder = _NvdaLoaderRecorder()
            speaker = NvdaSpeaker(root, loader=recorder)

            speaker.speak("low priority", 40)
            speaker.speak("high priority", 90)
            speaker.speak("follow up", 30)

            self.assertEqual(recorder.loaded_paths, [str(root / "nvdaControllerClient.dll")])
            self.assertEqual(
                recorder.calls,
                [
                    "test",
                    "cancel",
                    "speak:low priority",
                    "test",
                    "cancel",
                    "speak:high priority",
                    "test",
                    "speak:follow up",
                ],
            )

    def test_falls_back_to_64_bit_client_when_generic_name_is_missing(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nvdaControllerClient64.dll").write_bytes(b"stub")
            recorder = _NvdaLoaderRecorder()
            speaker = NvdaSpeaker(root, loader=recorder)

            speaker.speak("hello", 80)

            self.assertEqual(recorder.loaded_paths, [str(root / "nvdaControllerClient64.dll")])


class _NvdaLoaderRecorder:
    def __init__(self) -> None:
        self.loaded_paths: list[str] = []
        self.calls: list[str] = []

    def __call__(self, path: str):
        self.loaded_paths.append(path)
        return _NvdaDll(self.calls)


class _NvdaDll:
    def __init__(self, calls: list[str]) -> None:
        self.nvdaController_speakText = _CallableRecorder(calls, "speak")
        self.nvdaController_cancelSpeech = _CallableRecorder(calls, "cancel")
        self.nvdaController_testIfRunning = _CallableRecorder(calls, "test")


class _CallableRecorder:
    def __init__(self, calls: list[str], label: str) -> None:
        self._calls = calls
        self._label = label
        self.argtypes = None
        self.restype = None

    def __call__(self, *args) -> int:
        if self._label == "speak":
            self._calls.append(f"speak:{args[0]}")
        else:
            self._calls.append(self._label)
        return 0


if __name__ == "__main__":
    unittest.main()
