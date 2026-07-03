"""Cross-platform screen-reader / TTS speech.

Speech is best-effort and must never crash the game: a missing tool or a failed
call is logged once and then silently skipped for the rest of the session.

- Windows: NVDA via ``NvdaSpeaker`` (ctypes DLL).
- macOS: the built-in ``say`` command.
- Linux: ``spd-say`` (speech-dispatcher).
- Anything else / no tool: ``NullSpeaker`` (does nothing).

``create_speaker`` picks the right backend by platform. The subprocess backends
accept an injectable ``runner`` so tests never spawn a real process.
"""

import subprocess
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from horse_racing_game.app.runtime_log import write_runtime_log


CommandRunner = Callable[[list[str]], None]


class Speaker(ABC):
    @abstractmethod
    def speak(self, text: str, priority: int = 50) -> None:
        """Speak text, or do nothing if speech is unavailable."""


class NullSpeaker(Speaker):
    def speak(self, text: str, priority: int = 50) -> None:
        return


class _SubprocessSpeaker(Speaker):
    """Base for speakers that shell out to a TTS binary."""

    tool = ""

    def __init__(self, project_root: Path, runner: CommandRunner | None = None) -> None:
        self._project_root = project_root
        self._runner = runner or self._default_runner
        self._disabled = False

    def _args(self, text: str) -> list[str]:
        raise NotImplementedError

    def speak(self, text: str, priority: int = 50) -> None:
        if self._disabled or not text:
            return
        try:
            self._runner(self._args(text))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self._disabled = True
            write_runtime_log(self._project_root, f"speech: {self.tool} unavailable: {error}")

    @staticmethod
    def _default_runner(args: list[str]) -> None:
        subprocess.run(args, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class MacSpeaker(_SubprocessSpeaker):
    tool = "say"

    def _args(self, text: str) -> list[str]:
        return ["say", text]


class LinuxSpeaker(_SubprocessSpeaker):
    tool = "spd-say"

    def _args(self, text: str) -> list[str]:
        # -C cancels any in-progress speech so cues stay responsive, like NVDA.
        return ["spd-say", "-C", text]


def create_speaker(
    project_root: Path,
    platform: str | None = None,
    runner: CommandRunner | None = None,
) -> Speaker:
    platform = platform if platform is not None else sys.platform
    if platform.startswith("win"):
        from horse_racing_game.audio.nvda_speaker import NvdaSpeaker

        return NvdaSpeaker(project_root)
    if platform == "darwin":
        return MacSpeaker(project_root, runner)
    if platform.startswith("linux"):
        return LinuxSpeaker(project_root, runner)
    return NullSpeaker()
