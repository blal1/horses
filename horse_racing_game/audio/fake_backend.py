from dataclasses import dataclass

from horse_racing_game.audio.audio_backend import AudioBackend, RelativeAudioPosition


@dataclass(frozen=True)
class AudioCall:
    method: str
    sound_id: str | None
    volume: float | None
    position: RelativeAudioPosition | None
    text: str | None
    priority: int | None


class FakeAudioBackend(AudioBackend):
    def __init__(self) -> None:
        self.calls: list[AudioCall] = []

    def play_2d(self, sound_id: str, volume: float) -> None:
        self.calls.append(AudioCall("play_2d", sound_id, volume, None, None, None))

    def play_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float) -> None:
        self.calls.append(AudioCall("play_3d", sound_id, volume, position, None, None))

    def play_loop(self, sound_id: str, volume: float) -> None:
        self.calls.append(AudioCall("play_loop", sound_id, volume, None, None, None))

    def play_loop_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float, loop_id: str | None = None) -> None:
        recorded_id = loop_id or sound_id
        self.calls.append(AudioCall("play_loop_3d", recorded_id, volume, position, None, None))

    def update_loop_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float, loop_id: str | None = None) -> None:
        recorded_id = loop_id or sound_id
        self.calls.append(AudioCall("update_loop_3d", recorded_id, volume, position, None, None))

    def stop_sound(self, sound_id: str) -> None:
        self.calls.append(AudioCall("stop_sound", sound_id, None, None, None, None))

    def speak(self, text: str, priority: int) -> None:
        self.calls.append(AudioCall("speak", None, None, None, text, priority))

    def stop_all(self) -> None:
        self.calls.append(AudioCall("stop_all", None, None, None, None, None))

