from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RelativeAudioPosition:
    forward_m: float
    right_m: float
    up_m: float = 0.0


class AudioBackend(ABC):
    @abstractmethod
    def play_2d(self, sound_id: str, volume: float) -> None:
        """Play a non-spatial sound."""

    @abstractmethod
    def play_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float) -> None:
        """Play a sound at a position relative to the player."""

    @abstractmethod
    def play_loop(self, sound_id: str, volume: float) -> None:
        """Start or update a looping sound."""

    def play_loop_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float, loop_id: str | None = None) -> None:
        """Start or update a positioned loop. Backends without 3D loops may fall back to mono loops."""
        self.play_loop(sound_id, volume)

    def update_loop_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float, loop_id: str | None = None) -> None:
        """Move an existing positioned loop, starting it if needed."""
        self.play_loop_3d(sound_id, position, volume, loop_id=loop_id)

    @abstractmethod
    def stop_sound(self, sound_id: str) -> None:
        """Stop one looping or active sound by id."""

    @abstractmethod
    def speak(self, text: str, priority: int) -> None:
        """Queue or play a spoken announcement."""

    @abstractmethod
    def stop_all(self) -> None:
        """Stop all active sounds."""

