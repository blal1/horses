from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.content.pack_file import PackFile
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RunnerState
from horse_racing_game.input.commands import RaceCommand


ACTION_DODGE = "dodge"
ACTION_DUCK = "duck"
ACTION_JUMP = "jump"
RADAR_DISTANCES_M = (120.0, 80.0, 45.0, 25.0, 12.0)
NEAR_MISS_LANE_GAP = 1


@dataclass(frozen=True)
class ObstaclePenalty:
    """How hard a hit hurts. ``throttle_cap`` is the highest throttle the player
    is allowed while the penalty lasts (lower = harder brake)."""

    duration_s: float
    throttle_cap: float


DEFAULT_PENALTY = ObstaclePenalty(1.1, -0.55)

# Different hazards feel different when struck: soft ground is a long, mild drag;
# solid barriers are a sharp, short stumble; overhead hazards a brief hard jolt.
_PENALTY_BY_KIND: dict[str, ObstaclePenalty] = {
    "mud": ObstaclePenalty(1.35, -0.35),
    "puddle": ObstaclePenalty(1.35, -0.35),
    "rail": ObstaclePenalty(0.95, -0.68),
    "barrel": ObstaclePenalty(0.95, -0.68),
    "stone": ObstaclePenalty(0.95, -0.68),
    "cone": ObstaclePenalty(0.85, -0.62),
    "low_branch": ObstaclePenalty(0.75, -0.58),
    "low_banner": ObstaclePenalty(0.75, -0.58),
    "low_gate": ObstaclePenalty(0.75, -0.58),
    "low_rope": ObstaclePenalty(0.75, -0.58),
}


def penalty_for_kind(kind: str) -> ObstaclePenalty:
    """Penalty profile for an obstacle kind; unknown kinds use the default so
    new content never crashes the sim."""
    return _PENALTY_BY_KIND.get(kind, DEFAULT_PENALTY)


@dataclass(frozen=True)
class TrackObstacle:
    obstacle_id: str
    distance_m: float
    lane: int
    kind: str
    label: str
    required_action: str = ACTION_DODGE


class ObstacleController:
    def __init__(self, obstacles: tuple[TrackObstacle, ...]) -> None:
        self._obstacles = obstacles
        self._warned_ids: set[str] = set()
        self._radar_ids: set[tuple[str, float]] = set()
        self._resolved_ids: set[str] = set()
        self._penalty_remaining_s = 0.0
        self._penalty_throttle_cap = DEFAULT_PENALTY.throttle_cap

    @property
    def obstacles(self) -> tuple[TrackObstacle, ...]:
        return self._obstacles

    @property
    def has_penalty(self) -> bool:
        return self._penalty_remaining_s > 0.0

    @property
    def penalty_throttle_cap(self) -> float:
        """Throttle ceiling to enforce while a penalty is active (kind-dependent)."""
        return self._penalty_throttle_cap

    def update(
        self,
        player: RunnerState,
        elapsed_s: float,
        delta_s: float,
        command: RaceCommand | None = None,
    ) -> tuple[RaceEvent, ...]:
        self._penalty_remaining_s = max(0.0, self._penalty_remaining_s - delta_s)
        events: list[RaceEvent] = []
        player_lane = self.player_lane(player)
        for obstacle in self._obstacles:
            if obstacle.obstacle_id in self._resolved_ids:
                continue
            forward_gap = obstacle.distance_m - player.distance_m
            right_gap = (obstacle.lane - player_lane) * 1.15
            radar_event = self._radar_event(obstacle, elapsed_s, forward_gap, right_gap)
            if radar_event is not None:
                events.append(radar_event)
            if 0.0 <= forward_gap <= 38.0 and obstacle.obstacle_id not in self._warned_ids:
                self._warned_ids.add(obstacle.obstacle_id)
                events.append(self._event("obstacle_warning", elapsed_s, obstacle, forward_gap, right_gap))
            if abs(forward_gap) <= 3.2:
                self._resolved_ids.add(obstacle.obstacle_id)
                resolution = self._resolution(obstacle, player_lane, command)
                if resolution == "hit":
                    penalty = penalty_for_kind(obstacle.kind)
                    self._penalty_remaining_s = penalty.duration_s
                    self._penalty_throttle_cap = penalty.throttle_cap
                    events.append(self._event("obstacle_hit", elapsed_s, obstacle, forward_gap, right_gap, resolution))
                elif resolution == "near_miss":
                    events.append(self._event("obstacle_near_miss", elapsed_s, obstacle, forward_gap, right_gap, resolution))
                else:
                    events.append(self._event("obstacle_avoided", elapsed_s, obstacle, forward_gap, right_gap, resolution))
        return tuple(events)

    def _radar_event(
        self,
        obstacle: TrackObstacle,
        elapsed_s: float,
        forward_gap: float,
        right_gap: float,
    ) -> RaceEvent | None:
        if forward_gap < 0.0 or forward_gap > RADAR_DISTANCES_M[0]:
            return None
        for threshold_m in reversed(RADAR_DISTANCES_M):
            key = (obstacle.obstacle_id, threshold_m)
            if forward_gap <= threshold_m and key not in self._radar_ids:
                self._radar_ids.add(key)
                return self._event("obstacle_radar", elapsed_s, obstacle, forward_gap, right_gap, stage_for_threshold(threshold_m))
        return None

    def visible_near(self, player: RunnerState, distance_ahead_m: float) -> tuple[TrackObstacle, ...]:
        return tuple(
            obstacle
            for obstacle in self._obstacles
            if obstacle.obstacle_id not in self._resolved_ids
            and -20.0 <= obstacle.distance_m - player.distance_m <= distance_ahead_m
        )

    def player_lane(self, player: RunnerState) -> int:
        return max(0, int(round(player.lateral_position / 1.15)))

    def _event(
        self,
        event_type: str,
        elapsed_s: float,
        obstacle: TrackObstacle,
        forward_m: float,
        right_m: float,
        resolution: str | None = None,
    ) -> RaceEvent:
        priority = 90 if event_type == "obstacle_hit" else 76 if event_type == "obstacle_near_miss" else 58 if event_type == "obstacle_radar" else 70
        data = {
            "label": obstacle.label,
            "kind": obstacle.kind,
            "lane": obstacle.lane,
            "required_action": obstacle.required_action,
            "forward_m": round(forward_m, 2),
            "right_m": round(right_m, 2),
        }
        if resolution is not None:
            if resolution in {"far", "medium", "close", "urgent", "imminent"}:
                data["warning_stage"] = resolution
            else:
                data["resolution"] = resolution
                data["timing_quality"] = timing_quality(abs(forward_m))
        return RaceEvent(
            event_type=event_type,
            priority=priority,
            timestamp_s=round(elapsed_s, 3),
            subject_id=obstacle.obstacle_id,
            data=data,
        )

    def _resolution(self, obstacle: TrackObstacle, player_lane: int, command: RaceCommand | None) -> str:
        same_lane = obstacle.lane == player_lane
        if not same_lane:
            if abs(obstacle.lane - player_lane) <= NEAR_MISS_LANE_GAP:
                return "near_miss"
            return ACTION_DODGE
        if command is not None and obstacle.required_action == ACTION_JUMP and command.jump_requested:
            return ACTION_JUMP
        if command is not None and obstacle.required_action == ACTION_DUCK and command.duck_requested:
            return ACTION_DUCK
        return "hit"


def stage_for_threshold(threshold_m: float) -> str:
    if threshold_m >= 120.0:
        return "far"
    if threshold_m >= 80.0:
        return "medium"
    if threshold_m >= 45.0:
        return "close"
    if threshold_m >= 25.0:
        return "urgent"
    return "imminent"


def timing_quality(abs_forward_gap: float) -> str:
    if abs_forward_gap <= 0.9:
        return "perfect"
    if abs_forward_gap <= 2.0:
        return "good"
    return "late"


def load_track_obstacles(path: Path, track_id: str) -> tuple[TrackObstacle, ...]:
    pack_file = PackFile.from_path(path)
    if not pack_file.exists(path.name):
        return ()
    parsed = pack_file.read_json(path.name)
    if not isinstance(parsed, list):
        raise ValueError(f"Expected obstacle JSON array in {path}")
    for entry in parsed:
        if isinstance(entry, dict) and entry.get("track_id") == track_id:
            obstacles = entry.get("obstacles")
            if not isinstance(obstacles, list):
                raise ValueError(f"Expected obstacles list for track {track_id}")
            return tuple(_parse_obstacle(item, path) for item in obstacles)
    return ()


def _parse_obstacle(data: object, path: Path) -> TrackObstacle:
    if not isinstance(data, dict):
        raise ValueError(f"Expected obstacle object in {path}")
    return TrackObstacle(
        obstacle_id=_string(data, "obstacle_id", path),
        distance_m=_number(data, "distance_m", path),
        lane=_integer(data, "lane", path),
        kind=_string(data, "kind", path),
        label=_string(data, "label", path),
        required_action=_optional_action(data, path),
    )


def _optional_action(data: dict[str, object], path: Path) -> str:
    value = data.get("required_action", ACTION_DODGE)
    if not isinstance(value, str):
        raise ValueError(f"Expected string 'required_action' in {path}")
    if value not in {ACTION_DODGE, ACTION_DUCK, ACTION_JUMP}:
        raise ValueError(f"Unsupported required_action '{value}' in {path}")
    return value


def _string(data: dict[str, object], key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Expected string '{key}' in {path}")
    return value


def _number(data: dict[str, object], key: str, path: Path) -> float:
    value = data.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"Expected number '{key}' in {path}")
    return float(value)


def _integer(data: dict[str, object], key: str, path: Path) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Expected integer '{key}' in {path}")
    return value
