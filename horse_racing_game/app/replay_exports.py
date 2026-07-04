from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.progress import GameProgress, save_progress
from horse_racing_game.app.replay import (
    KEY_REPLAY_EVENTS,
    ReplayTimeline,
    build_replay_lines,
    reconstruct_race,
    replay_from_dict,
    replay_to_dict,
)
from horse_racing_game.app.replay_sharing import (
    CommandLogShare,
    HighlightClip,
    PhotoFinishFrame,
    RaceExport,
    ReplaySummary,
    SharedGhostFile,
    create_command_log_share,
    create_highlight_clips,
    create_photo_finish_frame,
    create_replay_summary,
    create_shared_ghost_file,
    export_race_text,
)
from horse_racing_game.app.savedata import atomic_write_json, load_json_object


@dataclass(frozen=True)
class ReplayShareBundle:
    summary: ReplaySummary
    ghost: SharedGhostFile
    text_export: RaceExport
    highlight_clips: tuple[HighlightClip, ...]
    photo_finish: PhotoFinishFrame
    command_log: CommandLogShare


@dataclass(frozen=True)
class ReplayShareSaveResult:
    directory: Path
    files: tuple[Path, ...]


@dataclass(frozen=True)
class ReplayShareIndexEntry:
    replay_id: str
    title: str
    track_id: str
    player_horse_id: str
    duration_s: float
    final_rank: int | None
    files: tuple[Path, ...]


@dataclass(frozen=True)
class ReplayShareImportResult:
    replay_id: str
    title: str
    progress: GameProgress
    replay_lines: tuple[str, ...]


def replay_share_directory(project_root: Path) -> Path:
    return FileDirectories(project_root).save_root / "replay_shares"


def build_last_replay_share_bundle(content_root: Path, progress: GameProgress) -> ReplayShareBundle | None:
    replay = replay_from_dict(progress.last_replay or {})
    if replay is None:
        return None
    reconstructed = reconstruct_race(replay, content_root)
    events = tuple(sorted(reconstructed.events, key=lambda event: (event.timestamp_s, -event.priority)))
    timeline = ReplayTimeline(
        events=events,
        key_indices=tuple(index for index, event in enumerate(events) if event.event_type in KEY_REPLAY_EVENTS),
        final_stretch_index=next((index for index, event in enumerate(events) if event.event_type == "final_stretch"), None),
    )
    summary = create_replay_summary(
        "last-replay",
        "Last Race Replay",
        reconstructed.state.elapsed_s,
        replay,
        reconstructed.state,
        tags=("last", "shared"),
    )
    lines = progress.last_replay_lines or build_replay_lines(reconstructed.state, reconstructed.events)
    return ReplayShareBundle(
        summary=summary,
        ghost=create_shared_ghost_file("last-replay-ghost", replay, "Last Race Ghost"),
        text_export=export_race_text(summary, lines),
        highlight_clips=create_highlight_clips(summary.replay_id, timeline),
        photo_finish=create_photo_finish_frame(summary.replay_id, reconstructed.state),
        command_log=create_command_log_share(summary.replay_id, replay),
    )


def save_replay_share_bundle(project_root: Path, bundle: ReplayShareBundle) -> ReplayShareSaveResult:
    directory = replay_share_directory(project_root)
    directory.mkdir(parents=True, exist_ok=True)
    prefix = bundle.summary.replay_id
    text_path = directory / f"{prefix}-race.txt"
    summary_path = directory / f"{prefix}-summary.json"
    ghost_path = directory / f"{prefix}-ghost.json"
    highlights_path = directory / f"{prefix}-highlights.json"
    photo_path = directory / f"{prefix}-photo-finish.json"
    command_path = directory / f"{prefix}-command-log.json"
    manifest_path = directory / f"{prefix}-manifest.json"

    text_path.write_text("\n".join(bundle.text_export.lines) + "\n", encoding="utf-8")
    atomic_write_json(summary_path, asdict(bundle.summary))
    atomic_write_json(ghost_path, asdict(bundle.ghost))
    atomic_write_json(highlights_path, [asdict(clip) for clip in bundle.highlight_clips])
    atomic_write_json(photo_path, asdict(bundle.photo_finish))
    atomic_write_json(command_path, asdict(bundle.command_log))
    files = (text_path, summary_path, ghost_path, highlights_path, photo_path, command_path)
    atomic_write_json(
        manifest_path,
        {
            "replay_id": bundle.summary.replay_id,
            "files": [path.name for path in files],
        },
    )
    return ReplayShareSaveResult(directory=directory, files=files + (manifest_path,))


def load_replay_share_index(project_root: Path) -> tuple[ReplayShareIndexEntry, ...]:
    directory = replay_share_directory(project_root)
    if not directory.exists():
        return ()
    entries: list[ReplayShareIndexEntry] = []
    for manifest_path in sorted(directory.glob("*-manifest.json")):
        entry = _load_replay_share_manifest(directory, manifest_path)
        if entry is not None:
            entries.append(entry)
    return tuple(sorted(entries, key=lambda item: (-item.duration_s, item.replay_id)))


def import_replay_share(
    project_root: Path,
    content_root: Path,
    replay_id: str,
    progress: GameProgress,
) -> ReplayShareImportResult | None:
    entry = next((item for item in load_replay_share_index(project_root) if item.replay_id == replay_id), None)
    if entry is None:
        return None
    command_path = next((path for path in entry.files if path.name == f"{entry.replay_id}-command-log.json"), None)
    if command_path is None:
        return None
    command_log = load_json_object(command_path)
    if command_log is None:
        return None
    replay = replay_from_dict(command_log.get("payload"))
    if replay is None:
        return None
    try:
        reconstructed = reconstruct_race(replay, content_root)
    except (OSError, ValueError):
        return None
    lines = build_replay_lines(reconstructed.state, reconstructed.events)
    imported = replace(
        progress,
        last_horse_id=replay.player_horse_id,
        last_track_id=replay.track_id,
        last_weather_id=replay.weather_id,
        last_stable_id=replay.stable_id,
        last_replay_lines=lines,
        last_replay=replay_to_dict(replay),
    )
    save_progress(project_root, imported)
    return ReplayShareImportResult(entry.replay_id, entry.title, imported, lines)


def _load_replay_share_manifest(directory: Path, manifest_path: Path) -> ReplayShareIndexEntry | None:
    manifest = load_json_object(manifest_path)
    if manifest is None:
        return None
    replay_id = manifest.get("replay_id")
    files = manifest.get("files")
    if not isinstance(replay_id, str) or not replay_id:
        return None
    if not isinstance(files, list):
        return None
    paths = tuple(directory / item for item in files if isinstance(item, str) and item)
    if not paths or not all(path.exists() for path in paths):
        return None
    summary = _load_summary(directory / f"{replay_id}-summary.json")
    if summary is None:
        return None
    return ReplayShareIndexEntry(
        replay_id=summary.replay_id,
        title=summary.title,
        track_id=summary.track_id,
        player_horse_id=summary.player_horse_id,
        duration_s=summary.duration_s,
        final_rank=summary.final_rank,
        files=paths + (manifest_path,),
    )


def _load_summary(path: Path) -> ReplaySummary | None:
    data = load_json_object(path)
    if data is None:
        return None
    try:
        rank_value = data.get("final_rank")
        return ReplaySummary(
            str(data.get("replay_id") or ""),
            str(data.get("title") or ""),
            float(data.get("created_at_s") or 0.0),
            str(data.get("track_id") or ""),
            str(data.get("player_horse_id") or ""),
            float(data.get("duration_s") or 0.0),
            None if rank_value is None else int(rank_value),
            _string_tuple(data.get("tags")),
        )
    except (TypeError, ValueError):
        return None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)
