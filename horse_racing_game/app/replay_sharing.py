from __future__ import annotations

from dataclasses import dataclass, replace

from horse_racing_game.app.replay import RaceReplay, ReplayTimeline, replay_to_dict
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState


@dataclass(frozen=True)
class ReplaySummary:
    replay_id: str
    title: str
    created_at_s: float
    track_id: str
    player_horse_id: str
    duration_s: float
    final_rank: int | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.replay_id:
            raise ValueError("replay_id must be non-empty")
        if not self.title:
            raise ValueError("title must be non-empty")
        if not self.track_id:
            raise ValueError("track_id must be non-empty")
        if not self.player_horse_id:
            raise ValueError("player_horse_id must be non-empty")
        if self.duration_s < 0:
            raise ValueError("duration_s must be non-negative")
        if self.final_rank is not None and self.final_rank < 1:
            raise ValueError("final_rank must be positive when provided")


@dataclass(frozen=True)
class ReplayLibraryEntry:
    summary: ReplaySummary
    replay: RaceReplay


class ReplayBrowser:
    def __init__(self, entries: tuple[ReplayLibraryEntry, ...] = ()) -> None:
        self._entries: dict[str, ReplayLibraryEntry] = {}
        for entry in entries:
            self.add(entry)

    def add(self, entry: ReplayLibraryEntry) -> ReplayLibraryEntry:
        if entry.summary.replay_id in self._entries:
            raise ValueError("replay already exists")
        self._entries[entry.summary.replay_id] = entry
        return entry

    def list_recent(self, limit: int | None = None) -> tuple[ReplaySummary, ...]:
        summaries = sorted(
            (entry.summary for entry in self._entries.values()),
            key=lambda summary: (-summary.created_at_s, summary.replay_id),
        )
        return tuple(summaries if limit is None else summaries[:limit])

    def filter_by_tag(self, tag: str) -> tuple[ReplaySummary, ...]:
        return tuple(summary for summary in self.list_recent() if tag in summary.tags)

    def get(self, replay_id: str) -> ReplayLibraryEntry:
        try:
            return self._entries[replay_id]
        except KeyError as error:
            raise ValueError(f"unknown replay id: {replay_id}") from error


@dataclass(frozen=True)
class TimelineScrubber:
    timeline: ReplayTimeline
    index: int = 0

    def current_event(self) -> RaceEvent | None:
        return self.timeline.event_at(self.index)

    def seek(self, index: int) -> TimelineScrubber:
        if not self.timeline.events:
            return replace(self, index=0)
        return replace(self, index=min(max(index, 0), len(self.timeline.events) - 1))

    def step(self, delta: int) -> TimelineScrubber:
        return self.seek(self.index + delta)

    def seek_key_moment(self, direction: int = 1) -> TimelineScrubber:
        if not self.timeline.key_indices:
            return self
        if direction >= 0:
            target = next((item for item in self.timeline.key_indices if item > self.index), self.timeline.key_indices[-1])
        else:
            reversed_keys = reversed(self.timeline.key_indices)
            target = next((item for item in reversed_keys if item < self.index), self.timeline.key_indices[0])
        return self.seek(target)

    def seek_final_stretch(self) -> TimelineScrubber:
        if self.timeline.final_stretch_index is None:
            return self
        return self.seek(self.timeline.final_stretch_index)


@dataclass(frozen=True)
class SharedGhostFile:
    ghost_id: str
    replay_payload: dict
    display_name: str
    duration_s: float

    def __post_init__(self) -> None:
        if not self.ghost_id:
            raise ValueError("ghost_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")
        if self.duration_s < 0:
            raise ValueError("duration_s must be non-negative")


@dataclass(frozen=True)
class RaceExport:
    replay_id: str
    format: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.replay_id:
            raise ValueError("replay_id must be non-empty")
        if self.format not in {"text", "json"}:
            raise ValueError("unsupported race export format")
        if not self.lines:
            raise ValueError("race export requires at least one line")


@dataclass(frozen=True)
class HighlightClip:
    clip_id: str
    replay_id: str
    start_s: float
    end_s: float
    label: str
    event_types: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.clip_id:
            raise ValueError("clip_id must be non-empty")
        if not self.replay_id:
            raise ValueError("replay_id must be non-empty")
        if self.end_s <= self.start_s:
            raise ValueError("highlight clip end must be after start")
        if not self.label:
            raise ValueError("label must be non-empty")


@dataclass(frozen=True)
class PhotoFinishFrame:
    replay_id: str
    timestamp_s: float
    runner_distances: tuple[tuple[str, float, int], ...]

    def __post_init__(self) -> None:
        if not self.replay_id:
            raise ValueError("replay_id must be non-empty")
        if self.timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")
        if not self.runner_distances:
            raise ValueError("photo finish requires runner distances")


@dataclass(frozen=True)
class CommandLogShare:
    replay_id: str
    payload: dict
    command_count: int

    def __post_init__(self) -> None:
        if not self.replay_id:
            raise ValueError("replay_id must be non-empty")
        if self.command_count < 0:
            raise ValueError("command_count must be non-negative")


def create_replay_summary(
    replay_id: str,
    title: str,
    created_at_s: float,
    replay: RaceReplay,
    final_state: RaceState | None = None,
    tags: tuple[str, ...] = (),
) -> ReplaySummary:
    final_rank = final_state.player().rank if final_state is not None else None
    duration_s = final_state.elapsed_s if final_state is not None else len(replay.commands) * replay.tick_seconds
    return ReplaySummary(
        replay_id=replay_id,
        title=title,
        created_at_s=created_at_s,
        track_id=replay.track_id,
        player_horse_id=replay.player_horse_id,
        duration_s=duration_s,
        final_rank=final_rank,
        tags=tuple(sorted(set(tags))),
    )


def create_shared_ghost_file(ghost_id: str, replay: RaceReplay, display_name: str) -> SharedGhostFile:
    return SharedGhostFile(
        ghost_id=ghost_id,
        replay_payload=replay_to_dict(replay),
        display_name=display_name,
        duration_s=len(replay.commands) * replay.tick_seconds,
    )


def export_race_text(summary: ReplaySummary, lines: tuple[str, ...]) -> RaceExport:
    if not lines:
        raise ValueError("race text export requires replay lines")
    return RaceExport(summary.replay_id, "text", (summary.title, *lines))


def create_highlight_clips(
    replay_id: str,
    timeline: ReplayTimeline,
    window_s: float = 4.0,
) -> tuple[HighlightClip, ...]:
    if window_s <= 0:
        raise ValueError("window_s must be positive")
    clips: list[HighlightClip] = []
    for ordinal, event_index in enumerate(timeline.key_indices, start=1):
        event = timeline.events[event_index]
        start_s = max(0.0, event.timestamp_s - window_s / 2)
        end_s = event.timestamp_s + window_s / 2
        clips.append(
            HighlightClip(
                clip_id=f"{replay_id}-clip-{ordinal}",
                replay_id=replay_id,
                start_s=start_s,
                end_s=end_s,
                label=event.event_type.replace("_", " "),
                event_types=(event.event_type,),
            )
        )
    return tuple(clips)


def create_photo_finish_frame(replay_id: str, state: RaceState) -> PhotoFinishFrame:
    return PhotoFinishFrame(
        replay_id=replay_id,
        timestamp_s=state.elapsed_s,
        runner_distances=tuple(
            sorted(
                ((runner.runner_id, runner.distance_m, runner.rank) for runner in state.runners),
                key=lambda item: (item[2], -item[1], item[0]),
            )
        ),
    )


def create_command_log_share(replay_id: str, replay: RaceReplay) -> CommandLogShare:
    return CommandLogShare(
        replay_id=replay_id,
        payload=replay_to_dict(replay),
        command_count=len(replay.commands),
    )
