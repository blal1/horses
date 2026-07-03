from __future__ import annotations

from dataclasses import dataclass


RACING_MODE_IDS = {
    "quick_race",
    "career",
    "training",
    "obstacle_lab",
    "tutorial",
    "time_trial",
    "ghost_race",
    "head_to_head",
    "relay",
    "endurance",
    "scenario",
}


@dataclass(frozen=True)
class RacingMode:
    mode_id: str
    label: str
    min_players: int = 1
    max_players: int = 1
    uses_time_limit: bool = False
    uses_ghost: bool = False
    uses_team: bool = False

    def __post_init__(self) -> None:
        if self.mode_id not in RACING_MODE_IDS:
            raise ValueError("unknown racing mode")
        if not self.label:
            raise ValueError("label must be non-empty")
        if self.min_players < 1:
            raise ValueError("min_players must be positive")
        if self.max_players < self.min_players:
            raise ValueError("max_players must be at least min_players")

    def supports_player_count(self, player_count: int) -> bool:
        return self.min_players <= player_count <= self.max_players


@dataclass(frozen=True)
class RaceEventSpec:
    event_id: str
    mode_id: str
    track_id: str
    weather_id: str = "clear"
    lap_count: int = 1
    time_limit_s: float | None = None
    ghost_replay_id: str | None = None
    team_size: int = 1

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must be non-empty")
        if self.mode_id not in RACING_MODE_IDS:
            raise ValueError("unknown racing mode")
        if not self.track_id:
            raise ValueError("track_id must be non-empty")
        if not self.weather_id:
            raise ValueError("weather_id must be non-empty")
        if self.lap_count < 1:
            raise ValueError("lap_count must be positive")
        if self.time_limit_s is not None and self.time_limit_s <= 0.0:
            raise ValueError("time_limit_s must be positive when provided")
        if self.team_size < 1:
            raise ValueError("team_size must be positive")

    def validate_for_mode(self, mode: RacingMode) -> None:
        if self.mode_id != mode.mode_id:
            raise ValueError("event mode does not match racing mode")
        if mode.uses_time_limit and self.time_limit_s is None:
            raise ValueError("mode requires a time limit")
        if mode.uses_ghost and self.ghost_replay_id is None:
            raise ValueError("mode requires a ghost replay")
        if mode.uses_team and self.team_size < 2:
            raise ValueError("team mode requires team size of at least two")


@dataclass(frozen=True)
class ScenarioObjective:
    objective_id: str
    description: str
    target_value: float

    def __post_init__(self) -> None:
        if not self.objective_id:
            raise ValueError("objective_id must be non-empty")
        if not self.description:
            raise ValueError("description must be non-empty")
        if self.target_value < 0.0:
            raise ValueError("target_value must be non-negative")

    def is_complete(self, value: float) -> bool:
        return value >= self.target_value


@dataclass(frozen=True)
class ScenarioProgress:
    event_id: str
    completed_objective_ids: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return bool(self.completed_objective_ids)


def default_racing_modes() -> tuple[RacingMode, ...]:
    return (
        RacingMode("quick_race", "Quick Race"),
        RacingMode("career", "Career"),
        RacingMode("training", "Training"),
        RacingMode("obstacle_lab", "Obstacle Lab"),
        RacingMode("tutorial", "Tutorial"),
        RacingMode("time_trial", "Time Trial", uses_time_limit=True),
        RacingMode("ghost_race", "Ghost Race", uses_ghost=True),
        RacingMode("head_to_head", "Head To Head", min_players=2, max_players=2),
        RacingMode("relay", "Relay", min_players=2, max_players=4, uses_team=True),
        RacingMode("endurance", "Endurance", uses_time_limit=True),
        RacingMode("scenario", "Scenario"),
    )


def racing_mode_by_id(mode_id: str, modes: tuple[RacingMode, ...] | None = None) -> RacingMode:
    for mode in modes or default_racing_modes():
        if mode.mode_id == mode_id:
            return mode
    raise ValueError(f"unknown racing mode: {mode_id}")


def update_scenario_progress(
    progress: ScenarioProgress,
    objectives: tuple[ScenarioObjective, ...],
    observed_values: dict[str, float],
) -> ScenarioProgress:
    completed = set(progress.completed_objective_ids)
    objective_ids = {objective.objective_id for objective in objectives}
    if not completed.issubset(objective_ids):
        raise ValueError("progress contains unknown objective")
    for objective in objectives:
        value = observed_values.get(objective.objective_id)
        if value is not None and objective.is_complete(value):
            completed.add(objective.objective_id)
    return ScenarioProgress(progress.event_id, tuple(sorted(completed)))
