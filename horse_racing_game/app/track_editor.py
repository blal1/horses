from dataclasses import asdict, dataclass
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import atomic_write_json, load_json_array
from horse_racing_game.content.loaders import load_tracks
from horse_racing_game.domain.track import Track, TrackSegment


CUSTOM_TRACK_ID = "custom_audio_track"
CUSTOM_TRACK_NAME = "Custom Audio Track"
SURFACES = ("turf", "dirt", "soft_turf", "mud")


@dataclass(frozen=True)
class TrackDraft:
    length_m: float
    surface: str
    handedness: str
    curve_intensity: float


def custom_tracks_path(project_root: Path) -> Path:
    return FileDirectories(project_root).custom_tracks_file()


def load_available_tracks(content_root: Path) -> tuple[Track, ...]:
    base_tracks = load_tracks(content_root / "tracks.json")
    custom_tracks = load_custom_tracks(content_root.parent)
    custom_ids = {track.track_id for track in custom_tracks}
    filtered_base = tuple(track for track in base_tracks if track.track_id not in custom_ids)
    return filtered_base + custom_tracks


def load_custom_tracks(project_root: Path) -> tuple[Track, ...]:
    path = custom_tracks_path(project_root)
    data = load_json_array(path)
    if data is None:
        return ()
    temporary_path = project_root / "save" / ".custom_tracks.tmp.json"
    temporary_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(temporary_path, data)
    try:
        return load_tracks(temporary_path)
    finally:
        try:
            temporary_path.unlink()
        except OSError:
            pass


def save_custom_track(project_root: Path, track: Track) -> None:
    existing = [item for item in load_custom_tracks(project_root) if item.track_id != track.track_id]
    tracks = existing + [track]
    path = custom_tracks_path(project_root)
    payload = [_track_to_json(item) for item in tracks]
    atomic_write_json(path, payload)


def draft_from_track(track: Track) -> TrackDraft:
    strongest_curve = max((segment.curve_intensity for segment in track.segments), default=0.45)
    return TrackDraft(
        length_m=track.length_m,
        surface=track.surface,
        handedness=track.handedness,
        curve_intensity=round(strongest_curve, 2),
    )


def adjust_draft(draft: TrackDraft, field_index: int, delta: int) -> TrackDraft:
    if field_index == 0:
        return TrackDraft(_clamp(draft.length_m + delta * 100.0, 800.0, 2400.0), draft.surface, draft.handedness, draft.curve_intensity)
    if field_index == 1:
        surface_index = SURFACES.index(draft.surface) if draft.surface in SURFACES else 0
        return TrackDraft(draft.length_m, SURFACES[(surface_index + delta) % len(SURFACES)], draft.handedness, draft.curve_intensity)
    if field_index == 2:
        return TrackDraft(draft.length_m, draft.surface, "right" if draft.handedness == "left" else "left", draft.curve_intensity)
    if field_index == 3:
        return TrackDraft(draft.length_m, draft.surface, draft.handedness, round(_clamp(draft.curve_intensity + delta * 0.05, 0.1, 0.8), 2))
    return draft


def build_custom_track(draft: TrackDraft) -> Track:
    length = draft.length_m
    curve_start = length * 0.25
    backstretch_start = length * 0.52
    final_start = length * 0.75
    return Track(
        track_id=CUSTOM_TRACK_ID,
        name=CUSTOM_TRACK_NAME,
        length_m=length,
        surface=draft.surface,
        lanes=6,
        handedness=draft.handedness,
        final_stretch_start_m=final_start,
        audio_profile={
            "crowd_loop": "mixkit_crowd_424",
            "wind_loop": "mixkit_wind_2608",
            "rain_loop": "mixkit_rain_2393",
            "countdown": "mixkit_countdown_916",
        },
        segments=(
            TrackSegment(0.0, curve_start, "none", 0.0, 0.0, "custom_start_gate"),
            TrackSegment(curve_start, backstretch_start, draft.handedness, draft.curve_intensity, 0.01, f"inner_rail_{draft.handedness}"),
            TrackSegment(backstretch_start, final_start, "none", 0.0, -0.005, "custom_backstretch_wind"),
            TrackSegment(final_start, length, "none", 0.0, 0.0, "finish_crowd_front"),
        ),
    )


def draft_summary(draft: TrackDraft) -> str:
    return (
        f"Custom track draft. Length {draft.length_m:.0f} meters. "
        f"Surface {draft.surface}. Turns {draft.handedness}. Curve intensity {draft.curve_intensity:.2f}."
    )


def _track_to_json(track: Track) -> dict[str, object]:
    data = asdict(track)
    data["segments"] = [asdict(segment) for segment in track.segments]
    return data


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
