from __future__ import annotations

import ctypes
from pathlib import Path
from collections.abc import Callable

from horse_racing_game.app.runtime_log import write_runtime_log
from horse_racing_game.audio.speech import Speaker


NvdaLoader = Callable[[str], ctypes.WinDLL]


class NvdaSpeaker(Speaker):
    def __init__(self, project_root: Path, loader: NvdaLoader | None = None) -> None:
        self._project_root = project_root
        self._loader = loader or ctypes.WinDLL
        self._dll: ctypes.WinDLL | None = None
        self._load_failed = False
        self._last_spoken_text: str | None = None
        self._last_priority = -1

    def speak(self, text: str, priority: int = 50) -> None:
        dll = self._load_dll()
        if dll is None or not text:
            return
        try:
            if dll.nvdaController_testIfRunning() != 0:
                return
            if self._should_interrupt(priority):
                dll.nvdaController_cancelSpeech()
            dll.nvdaController_speakText(str(text))
            self._last_spoken_text = text
            self._last_priority = priority
        except (OSError, AttributeError, ctypes.ArgumentError) as error:
            if not self._load_failed:
                self._load_failed = True
                write_runtime_log(self._project_root, f"nvda: speak failed: {error}")

    def _should_interrupt(self, priority: int) -> bool:
        if self._last_spoken_text is None:
            return True
        if priority >= 85:
            return True
        return priority >= self._last_priority

    def _load_dll(self) -> ctypes.WinDLL | None:
        if self._dll is not None:
            return self._dll
        if self._load_failed:
            return None

        candidate_names = ("nvdaControllerClient.dll", "nvdaControllerClient64.dll")
        for dll_name in candidate_names:
            dll_path = self._project_root / dll_name
            if not dll_path.exists():
                continue
            try:
                dll = self._loader(str(dll_path))
                dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
                dll.nvdaController_speakText.restype = ctypes.c_int
                dll.nvdaController_cancelSpeech.argtypes = []
                dll.nvdaController_cancelSpeech.restype = ctypes.c_int
                dll.nvdaController_testIfRunning.argtypes = []
                dll.nvdaController_testIfRunning.restype = ctypes.c_int
            except (OSError, AttributeError) as error:
                self._load_failed = True
                write_runtime_log(self._project_root, f"nvda: unavailable: {error}")
                return None

            self._dll = dll
            write_runtime_log(self._project_root, f"nvda: controller loaded from {dll_name}")
            return dll

        self._load_failed = True
        write_runtime_log(self._project_root, "nvda: nvdaControllerClient.dll not found")
        return None
