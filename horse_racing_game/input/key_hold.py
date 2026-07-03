from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class HoldSample:
    key_code: int
    held_seconds: float

    @property
    def is_held(self) -> bool:
        return self.held_seconds > 0.0

    def strength(self, ramp_seconds: float = 0.22, floor: float = 0.58) -> float:
        if self.held_seconds <= 0.0:
            return 0.0
        if ramp_seconds <= 0.0:
            return 1.0
        ramp = min(self.held_seconds / ramp_seconds, 1.0)
        return floor + (1.0 - floor) * ramp


class KeyHoldTracker:
    """Track how long each key has been held.

    The tracker is intentionally tiny and deterministic. It gives the UI enough
    information to shape held-input commands without coupling that behavior to
    pygame directly.
    """

    def __init__(self) -> None:
        self._held_seconds: dict[int, float] = {}

    def advance(self, delta_s: float, held_keys: Iterable[int]) -> None:
        if delta_s < 0.0:
            raise ValueError("delta_s must be non-negative")
        held = set(held_keys)
        if delta_s == 0.0 and not held:
            return
        for key_code in list(self._held_seconds):
            if key_code not in held:
                del self._held_seconds[key_code]
        for key_code in held:
            self._held_seconds[key_code] = self._held_seconds.get(key_code, 0.0) + delta_s

    def release(self, key_code: int) -> None:
        self._held_seconds.pop(key_code, None)

    def held_seconds(self, key_code: int) -> float:
        return self._held_seconds.get(key_code, 0.0)

    def is_held(self, key_code: int) -> bool:
        return key_code in self._held_seconds

    def sample(self, key_code: int) -> HoldSample:
        return HoldSample(key_code=key_code, held_seconds=self.held_seconds(key_code))

    def strength(self, key_code: int, ramp_seconds: float = 0.22, floor: float = 0.58) -> float:
        return self.sample(key_code).strength(ramp_seconds=ramp_seconds, floor=floor)

    def axis(
        self,
        positive_keys: Iterable[int],
        negative_keys: Iterable[int],
        ramp_seconds: float = 0.22,
        floor: float = 0.58,
    ) -> float:
        positive = max((self.strength(key_code, ramp_seconds, floor) for key_code in positive_keys), default=0.0)
        negative = max((self.strength(key_code, ramp_seconds, floor) for key_code in negative_keys), default=0.0)
        return positive - negative

