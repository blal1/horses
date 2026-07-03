from dataclasses import dataclass, field
from pathlib import Path

from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState


MAX_REPLAY_LINES = 12


@dataclass(frozen=True)
class RaceReplay:
    """Everything needed to re-simulate a race exactly.

    Because the engine is deterministic given ``(seed, content, commands)``,
    storing the selection ids, seed, tick size, and the per-tick command stream
    is enough to reconstruct the identical race later — no recorded positions
    required. See ``reconstruct_race``.
    """

    seed: int
    track_id: str
    player_horse_id: str
    weather_id: str
    stable_id: str
    tick_seconds: float
    commands: tuple[RaceCommand, ...]
    rival_stable_ids: dict[str, str] = field(default_factory=dict)
    horse_training_level: int = 0
    opponent_strength: float = 1.0


@dataclass(frozen=True)
class ReconstructedRace:
    state: RaceState
    events: tuple[RaceEvent, ...]
    ticks: int


@dataclass(frozen=True)
class ReplayTimeline:
    events: tuple[RaceEvent, ...]
    key_indices: tuple[int, ...]
    final_stretch_index: int | None

    @property
    def has_events(self) -> bool:
        return bool(self.events)

    def event_at(self, index: int) -> RaceEvent | None:
        if not self.events:
            return None
        return self.events[min(max(index, 0), len(self.events) - 1)]

    def key_index_at_or_before(self, index: int) -> int | None:
        candidates = [key_index for key_index in self.key_indices if key_index <= index]
        if candidates:
            return candidates[-1]
        return self.key_indices[0] if self.key_indices else None


KEY_REPLAY_EVENTS = {
    "race_started",
    "turn_entry",
    "turn_apex",
    "final_stretch",
    "opponent_approaching",
    "opponent_passing",
    "low_stamina",
    "critical_stamina",
    "obstacle_warning",
    "obstacle_hit",
    "obstacle_near_miss",
    "obstacle_avoided",
    "finish_line_crossed",
    "race_finished",
}


def serialize_command(command: RaceCommand) -> list[float | bool]:
    """Compact list form (order matters) for JSON storage."""
    return [
        command.throttle_delta,
        command.lateral_delta,
        command.push_requested,
        command.jump_requested,
        command.duck_requested,
        command.request_status,
    ]


def deserialize_command(values: list[float | bool]) -> RaceCommand:
    return RaceCommand(
        throttle_delta=float(values[0]),
        lateral_delta=float(values[1]),
        push_requested=bool(values[2]),
        jump_requested=bool(values[3]),
        duck_requested=bool(values[4]),
        request_status=bool(values[5]),
    )


def replay_to_dict(replay: RaceReplay) -> dict:
    return {
        "seed": replay.seed,
        "track_id": replay.track_id,
        "player_horse_id": replay.player_horse_id,
        "weather_id": replay.weather_id,
        "stable_id": replay.stable_id,
        "tick_seconds": replay.tick_seconds,
        "rival_stable_ids": dict(replay.rival_stable_ids),
        "horse_training_level": replay.horse_training_level,
        "opponent_strength": replay.opponent_strength,
        "commands": [serialize_command(command) for command in replay.commands],
    }


def replay_from_dict(data: dict) -> RaceReplay | None:
    """Parse a stored replay, returning None if the payload is missing/malformed
    so a corrupt save never crashes the game."""
    if not isinstance(data, dict):
        return None
    try:
        raw_commands = data["commands"]
        if not isinstance(raw_commands, list):
            return None
        return RaceReplay(
            seed=int(data["seed"]),
            track_id=str(data["track_id"]),
            player_horse_id=str(data["player_horse_id"]),
            weather_id=str(data["weather_id"]),
            stable_id=str(data["stable_id"]),
            tick_seconds=float(data["tick_seconds"]),
            commands=tuple(deserialize_command(item) for item in raw_commands),
            rival_stable_ids={str(k): str(v) for k, v in dict(data.get("rival_stable_ids", {})).items()},
            horse_training_level=int(data.get("horse_training_level", 0)),
            opponent_strength=float(data.get("opponent_strength", 1.0)),
        )
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def build_replay(config, commands: tuple[RaceCommand, ...]) -> RaceReplay:
    """Capture a finished run as a replay from its config + the commands it used."""
    return RaceReplay(
        seed=config.seed,
        track_id=config.track_id,
        player_horse_id=config.player_horse_id,
        weather_id=config.weather_id,
        stable_id=config.stable_id,
        tick_seconds=config.tick_seconds,
        commands=tuple(commands),
        rival_stable_ids=dict(config.rival_stable_ids),
        horse_training_level=config.horse_training_level,
        opponent_strength=config.opponent_strength,
    )


def reconstruct_race(replay: RaceReplay, content_root: Path) -> ReconstructedRace:
    """Re-run the seeded engine with the recorded commands to reproduce the race.

    Imported lazily to avoid an import cycle (bootstrap pulls in many modules)."""
    from horse_racing_game.app.bootstrap import build_quick_race_services
    from horse_racing_game.app.config import AppConfig
    from horse_racing_game.ui.obstacles import ObstacleController, load_track_obstacles

    config = AppConfig(
        content_root=content_root,
        track_id=replay.track_id,
        player_horse_id=replay.player_horse_id,
        weather_id=replay.weather_id,
        stable_id=replay.stable_id,
        rival_stable_ids=dict(replay.rival_stable_ids),
        horse_training_level=replay.horse_training_level,
        opponent_strength=replay.opponent_strength,
        seed=replay.seed,
    )
    services = build_quick_race_services(config)
    obstacles = ObstacleController(load_track_obstacles(content_root / "obstacles.json", services.track.track_id))
    events: list[RaceEvent] = []
    state: RaceState | None = None
    ticks = 0
    for command in replay.commands:
        result = services.race_engine.tick(command, replay.tick_seconds)
        events.extend(result.events)
        state = result.state
        events.extend(obstacles.update(state.player(), state.elapsed_s, replay.tick_seconds, command))
        ticks += 1
        if state.is_finished:
            break
    if state is None:
        state = services.race_engine.tick(RaceCommand(request_status=True), replay.tick_seconds).state
    return ReconstructedRace(state=state, events=tuple(events), ticks=ticks)


def build_replay_timeline(replay: RaceReplay, content_root: Path) -> ReplayTimeline:
    reconstructed = reconstruct_race(replay, content_root)
    events = tuple(sorted(reconstructed.events, key=lambda event: (event.timestamp_s, -event.priority)))
    key_indices = tuple(index for index, event in enumerate(events) if event.event_type in KEY_REPLAY_EVENTS)
    final_stretch_index = next((index for index, event in enumerate(events) if event.event_type == "final_stretch"), None)
    return ReplayTimeline(events=events, key_indices=key_indices, final_stretch_index=final_stretch_index)


def build_replay_lines(state: RaceState, events: tuple[RaceEvent, ...]) -> tuple[str, ...]:
    player = state.player()
    lines = [
        f"Replay. Finished rank {player.rank} after {state.elapsed_s:.1f} seconds.",
        f"Distance {player.distance_m:.0f} meters. Stamina {player.stamina:.0f}.",
    ]
    for event in events:
        line = replay_line_for_event(event)
        if line is not None and line not in lines:
            lines.append(line)
        if len(lines) >= MAX_REPLAY_LINES:
            break
    return tuple(lines)


def replay_line_for_event(event: RaceEvent) -> str | None:
    if event.event_type == "race_started":
        return "The gates opened."
    if event.event_type in {"turn_incoming", "turn_entry"}:
        return f"Turn entry: {event.data.get('direction', 'ahead')}."
    if event.event_type == "turn_exit":
        return f"Turn exit: {event.data.get('direction', 'ahead')}."
    if event.event_type == "turn_apex":
        return f"Turn apex: {event.data.get('direction', 'ahead')}."
    if event.event_type == "turn_rail_inside":
        return f"Inside rail: {event.data.get('direction', 'ahead')}."
    if event.event_type == "turn_rail_outside":
        return f"Outside rail: {event.data.get('direction', 'ahead')}."
    if event.event_type == "turn_too_tight":
        return f"Too tight: {event.data.get('direction', 'ahead')}."
    if event.event_type == "turn_too_wide":
        return f"Too wide: {event.data.get('direction', 'ahead')}."
    if event.event_type == "final_stretch":
        return "The field entered the final stretch."
    if event.event_type == "finish_line_crossed":
        return f"Finish line crossed in rank {event.data.get('rank', '?')}."
    if event.event_type == "race_finished":
        return "Race complete."
    if event.event_type in {"low_stamina", "critical_stamina"}:
        return event.event_type.replace("_", " ").capitalize() + "."
    if event.event_type in {"opponent_approaching", "opponent_passing"}:
        horse_name = event.data.get("horse_name", "Opponent")
        return f"{horse_name} {event.event_type.replace('_', ' ')}."
    if event.event_type == "obstacle_warning":
        return f"Obstacle warning: {event.data.get('label', 'obstacle')}."
    if event.event_type == "obstacle_hit":
        return f"Obstacle hit: {event.data.get('label', 'obstacle')}."
    if event.event_type == "obstacle_near_miss":
        return f"Near miss: {event.data.get('label', 'obstacle')}."
    if event.event_type == "obstacle_avoided":
        quality = event.data.get("timing_quality")
        prefix = f"{str(quality).title()} " if quality in {"perfect", "good", "late"} else ""
        return f"{prefix}{event.data.get('resolution', 'dodge')} confirmed: {event.data.get('label', 'obstacle')}."
    return None
