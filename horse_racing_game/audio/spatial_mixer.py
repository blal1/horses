from dataclasses import dataclass

from horse_racing_game.audio.audio_backend import RelativeAudioPosition


@dataclass(frozen=True)
class SpatialMix:
    left: float
    right: float
    gain: float


class SpatialAudioMixer:
    """Headphone-oriented stereo projection for race-relative positions.

    This is intentionally backend-neutral: pygame uses it today, and an OpenAL
    backend can keep the same distance/priority policy later.
    """

    def __init__(self, lane_width_m: float = 2.3, hearing_range_m: float = 90.0) -> None:
        self._lane_width_m = lane_width_m
        self._hearing_range_m = hearing_range_m

    def mix(self, position: RelativeAudioPosition, volume: float) -> SpatialMix:
        bounded = self._clamp(volume)
        right_m = position.right_m
        forward_m = position.forward_m
        lateral = abs(right_m)
        distance = (forward_m * forward_m + lateral * lateral * 0.7 + position.up_m * position.up_m) ** 0.5
        distance_factor = 1.0 / (1.0 + (distance / self._hearing_range_m) ** 1.35)
        rear_factor = 0.78 if forward_m < -1.0 else 1.0
        center_focus = 1.0 - min(lateral / (self._lane_width_m * 2.5), 0.22)
        gain = self._clamp(bounded * distance_factor * rear_factor * center_focus)

        pan = self._clamp(right_m / self._lane_width_m, -1.0, 1.0)
        left = gain * (1.0 - max(pan, 0.0) * 0.88)
        right = gain * (1.0 + min(pan, 0.0) * 0.88)
        return SpatialMix(self._clamp(left), self._clamp(right), gain)

    def distance_gain(self, position: RelativeAudioPosition, close_gain: float = 1.0) -> float:
        return self.mix(position, close_gain).gain

    def _clamp(self, value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(maximum, value))
