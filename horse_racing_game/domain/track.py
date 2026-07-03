from dataclasses import dataclass


@dataclass(frozen=True)
class TrackSegment:
    start_m: float
    end_m: float
    curve_direction: str
    curve_intensity: float
    slope: float
    audio_marker: str


@dataclass(frozen=True)
class Track:
    track_id: str
    name: str
    length_m: float
    surface: str
    lanes: int
    handedness: str
    final_stretch_start_m: float
    audio_profile: dict[str, str]
    segments: tuple[TrackSegment, ...]

    def segment_at(self, distance_m: float) -> TrackSegment:
        clamped_distance = min(max(distance_m, 0.0), self.length_m)
        for segment in self.segments:
            if segment.start_m <= clamped_distance < segment.end_m:
                return segment
        return self.segments[-1]

