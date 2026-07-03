from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from horse_racing_game.app.replay import deserialize_command, serialize_command
from horse_racing_game.input.commands import RaceCommand


@dataclass(frozen=True)
class PeerCommand:
    peer_id: str
    command: RaceCommand


@dataclass(frozen=True)
class LockstepFrame:
    tick_index: int
    commands: tuple[PeerCommand, ...]

    def __post_init__(self) -> None:
        if self.tick_index < 0:
            raise ValueError("tick_index must be non-negative")
        peer_ids = [item.peer_id for item in self.commands]
        if len(peer_ids) != len(set(peer_ids)):
            raise ValueError("each peer may submit at most one command per tick")
        if tuple(peer_ids) != tuple(sorted(peer_ids)):
            ordered = tuple(sorted(self.commands, key=lambda item: item.peer_id))
            object.__setattr__(self, "commands", ordered)

    def command_for(self, peer_id: str) -> RaceCommand:
        for item in self.commands:
            if item.peer_id == peer_id:
                return item.command
        raise KeyError(peer_id)


class LockstepCommandBuffer:
    """Collect peer commands until a deterministic frame is ready for a tick."""

    def __init__(self, peer_ids: Iterable[str]) -> None:
        ordered_peer_ids = tuple(sorted(str(peer_id) for peer_id in peer_ids))
        if not ordered_peer_ids:
            raise ValueError("at least one peer is required")
        if any(not peer_id for peer_id in ordered_peer_ids):
            raise ValueError("peer ids must be non-empty")
        if len(ordered_peer_ids) != len(set(ordered_peer_ids)):
            raise ValueError("peer ids must be unique")
        self._peer_ids = ordered_peer_ids
        self._pending: dict[int, dict[str, RaceCommand]] = {}

    @property
    def peer_ids(self) -> tuple[str, ...]:
        return self._peer_ids

    def submit(self, tick_index: int, peer_id: str, command: RaceCommand) -> None:
        if tick_index < 0:
            raise ValueError("tick_index must be non-negative")
        if peer_id not in self._peer_ids:
            raise ValueError(f"unknown peer id: {peer_id}")
        tick_commands = self._pending.setdefault(tick_index, {})
        tick_commands[peer_id] = command

    def ready_frame(self, tick_index: int) -> LockstepFrame | None:
        tick_commands = self._pending.get(tick_index)
        if tick_commands is None:
            return None
        if any(peer_id not in tick_commands for peer_id in self._peer_ids):
            return None
        return LockstepFrame(
            tick_index=tick_index,
            commands=tuple(PeerCommand(peer_id, tick_commands[peer_id]) for peer_id in self._peer_ids),
        )

    def pop_ready_frame(self, tick_index: int) -> LockstepFrame | None:
        frame = self.ready_frame(tick_index)
        if frame is None:
            return None
        self._pending.pop(tick_index, None)
        return frame


def local_commands(frames: Iterable[LockstepFrame], local_peer_id: str) -> tuple[RaceCommand, ...]:
    return tuple(frame.command_for(local_peer_id) for frame in sorted(frames, key=lambda item: item.tick_index))


def frame_to_dict(frame: LockstepFrame) -> dict:
    return {
        "tick_index": frame.tick_index,
        "commands": [
            {"peer_id": item.peer_id, "command": serialize_command(item.command)}
            for item in frame.commands
        ],
    }


def frame_from_dict(data: dict) -> LockstepFrame:
    return LockstepFrame(
        tick_index=int(data["tick_index"]),
        commands=tuple(
            PeerCommand(str(item["peer_id"]), deserialize_command(item["command"]))
            for item in data["commands"]
        ),
    )
