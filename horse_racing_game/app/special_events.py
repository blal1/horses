"""Special-event challenges that reuse the core deterministic race loop.

Each challenge is a themed race (track + weather) plus a set of
:class:`ScenarioObjective`s scored from the finished race state. The same
``GameApp.run_quick_race`` loop that powers quick race, career, and time trial
produces the metrics, so no new simulation is required — a special event is the
core loop wrapped in objectives.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.racing_modes import (
    RaceEventSpec,
    ScenarioObjective,
    ScenarioProgress,
    update_scenario_progress,
)
from horse_racing_game.app.savedata import atomic_write_json, load_json_object
from horse_racing_game.simulation.race_state import RaceState


@dataclass(frozen=True)
class SpecialEventChallenge:
    event_id: str
    name: str
    briefing: str
    spec: RaceEventSpec
    objectives: tuple[ScenarioObjective, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must be non-empty")
        if not self.briefing:
            raise ValueError("briefing must be non-empty")
        if not self.objectives:
            raise ValueError("a challenge needs at least one objective")
        if self.spec.event_id != self.event_id:
            raise ValueError("spec event_id must match challenge event_id")

    @property
    def track_id(self) -> str:
        return self.spec.track_id

    @property
    def weather_id(self) -> str:
        return self.spec.weather_id


def default_special_events() -> tuple[SpecialEventChallenge, ...]:
    """Ship a small, distinct set of challenges across existing content."""
    return (
        SpecialEventChallenge(
            event_id="fog_sprint_gauntlet",
            name="Fog Sprint Gauntlet",
            briefing="Race Bracken Dirt blind in the fog. Finish inside the time limit and hold a podium place by ear alone.",
            spec=RaceEventSpec(
                event_id="fog_sprint_gauntlet",
                mode_id="scenario",
                track_id="bracken_dirt",
                weather_id="fog",
                time_limit_s=110.0,
            ),
            objectives=(
                ScenarioObjective("finish", "Cross the finish line", 1.0),
                ScenarioObjective("beat_time", "Finish within the time limit", 1.0),
                ScenarioObjective("podium", "Finish in the top three", 1.0),
            ),
        ),
        SpecialEventChallenge(
            event_id="highcliff_endurance_climb",
            name="Highcliff Endurance Climb",
            briefing="Conquer the Highcliff hill without emptying the tank. Finish with stamina in reserve for the descent home.",
            spec=RaceEventSpec(
                event_id="highcliff_endurance_climb",
                mode_id="scenario",
                track_id="highcliff_rise",
                weather_id="windy",
            ),
            objectives=(
                ScenarioObjective("finish", "Cross the finish line", 1.0),
                ScenarioObjective("stamina_reserve", "Finish with stamina to spare", 8.0),
            ),
        ),
        SpecialEventChallenge(
            event_id="ashford_champion_charge",
            name="Ashford Champion Charge",
            briefing="A clean, fast round at Ashford Oval. Nothing less than the win counts here.",
            spec=RaceEventSpec(
                event_id="ashford_champion_charge",
                mode_id="scenario",
                track_id="ashford_oval",
                weather_id="clear",
            ),
            objectives=(
                ScenarioObjective("finish", "Cross the finish line", 1.0),
                ScenarioObjective("win", "Win the race", 1.0),
            ),
        ),
    )


def special_event_by_id(event_id: str) -> SpecialEventChallenge:
    for challenge in default_special_events():
        if challenge.event_id == event_id:
            return challenge
    raise ValueError(f"unknown special event: {event_id}")


def observed_values_for(challenge: SpecialEventChallenge, state: RaceState) -> dict[str, float]:
    """Score a finished race state into the objective metrics for this challenge.

    Every metric is framed so that ``value >= target`` means success, matching
    :meth:`ScenarioObjective.is_complete`.
    """
    player = state.player()
    values: dict[str, float] = {}
    for objective in challenge.objectives:
        key = objective.objective_id
        if key == "finish":
            values[key] = 1.0 if state.is_finished else 0.0
        elif key == "beat_time":
            limit = challenge.spec.time_limit_s
            within = state.is_finished and limit is not None and state.elapsed_s <= limit
            values[key] = 1.0 if within else 0.0
        elif key == "podium":
            values[key] = 1.0 if state.is_finished and player.rank <= 3 else 0.0
        elif key == "win":
            values[key] = 1.0 if state.is_finished and player.rank == 1 else 0.0
        elif key == "stamina_reserve":
            values[key] = player.stamina if state.is_finished else 0.0
    return values


def evaluate_special_event(challenge: SpecialEventChallenge, state: RaceState) -> ScenarioProgress:
    """Return the scenario progress (completed objectives) for a finished race."""
    values = observed_values_for(challenge, state)
    return update_scenario_progress(
        ScenarioProgress(challenge.event_id), challenge.objectives, values
    )


def special_event_summary(challenge: SpecialEventChallenge, progress: ScenarioProgress) -> str:
    """A spoken/readable summary of which objectives were met."""
    completed = set(progress.completed_objective_ids)
    met = sum(1 for obj in challenge.objectives if obj.objective_id in completed)
    total = len(challenge.objectives)
    status = "Challenge complete." if met == total else "Challenge not yet complete."
    parts = [f"{challenge.name}. {met} of {total} objectives met. {status}"]
    for objective in challenge.objectives:
        mark = "met" if objective.objective_id in completed else "missed"
        parts.append(f"{objective.description}: {mark}.")
    return " ".join(parts)


@dataclass(frozen=True)
class SpecialEventResult:
    challenge: SpecialEventChallenge
    progress: ScenarioProgress
    elapsed_s: float
    rank: int
    is_finished: bool

    @property
    def is_complete(self) -> bool:
        return len(self.progress.completed_objective_ids) == len(self.challenge.objectives)


def special_event_result_from_state(challenge: SpecialEventChallenge, state: RaceState) -> SpecialEventResult:
    """Build a scored result from an already-run race state (e.g. the UI race)."""
    return SpecialEventResult(
        challenge=challenge,
        progress=evaluate_special_event(challenge, state),
        elapsed_s=state.elapsed_s,
        rank=state.player().rank,
        is_finished=state.is_finished,
    )


def run_special_event(project_root: Path, challenge: SpecialEventChallenge) -> SpecialEventResult:
    """Run one special event headlessly through the core race loop and score it."""
    from horse_racing_game.app.bootstrap import build_quick_race_services
    from horse_racing_game.app.config import AppConfig
    from horse_racing_game.app.game_app import GameApp

    config = AppConfig(
        content_root=project_root / "content",
        track_id=challenge.track_id,
        weather_id=challenge.weather_id,
        tick_hz=4,
        max_race_seconds=300.0,
    )
    result = GameApp(config, build_quick_race_services(config)).run_quick_race()
    return special_event_result_from_state(challenge, result.state)


# --- Persistence -----------------------------------------------------------
#
# Special-event progress lives in its own ``save/special_events.json`` file
# (like the social/community/track-catalog catalogs) rather than in
# ``GameProgress`` — its many fields make adding new ones fragile, and this is
# self-contained challenge state.


@dataclass(frozen=True)
class SpecialEventRecord:
    event_id: str
    best_objectives_met: int = 0
    total_objectives: int = 0
    completed: bool = False
    best_elapsed_s: float | None = None


def special_events_save_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file("special_events.json")


def load_special_event_records(project_root: Path) -> dict[str, SpecialEventRecord]:
    data = load_json_object(special_events_save_path(project_root))
    records: dict[str, SpecialEventRecord] = {}
    if data is None:
        return records
    events = data.get("events")
    if not isinstance(events, dict):
        return records
    for event_id, raw in events.items():
        if not isinstance(raw, dict):
            continue
        best_elapsed = raw.get("best_elapsed_s")
        records[event_id] = SpecialEventRecord(
            event_id=event_id,
            best_objectives_met=int(raw.get("best_objectives_met") or 0),
            total_objectives=int(raw.get("total_objectives") or 0),
            completed=bool(raw.get("completed")),
            best_elapsed_s=float(best_elapsed) if isinstance(best_elapsed, (int, float)) else None,
        )
    return records


def _save_special_event_records(
    project_root: Path, records: dict[str, SpecialEventRecord], last_event_id: str | None
) -> None:
    atomic_write_json(
        special_events_save_path(project_root),
        {
            "events": {
                record.event_id: {
                    "best_objectives_met": record.best_objectives_met,
                    "total_objectives": record.total_objectives,
                    "completed": record.completed,
                    "best_elapsed_s": record.best_elapsed_s,
                }
                for record in records.values()
            },
            "last_event_id": last_event_id,
        },
    )


def record_special_event_result(project_root: Path, result: SpecialEventResult) -> SpecialEventRecord:
    """Persist a played special event, keeping the best objectives-met count and
    the best finishing time across attempts. Returns the updated record."""
    records = load_special_event_records(project_root)
    event_id = result.challenge.event_id
    met = len(result.progress.completed_objective_ids)
    total = len(result.challenge.objectives)
    previous = records.get(event_id)
    best_met = max(met, previous.best_objectives_met) if previous else met
    best_elapsed = result.elapsed_s if result.is_finished else None
    if previous and previous.best_elapsed_s is not None:
        if best_elapsed is None:
            best_elapsed = previous.best_elapsed_s
        else:
            best_elapsed = min(best_elapsed, previous.best_elapsed_s)
    updated = SpecialEventRecord(
        event_id=event_id,
        best_objectives_met=best_met,
        total_objectives=total,
        completed=(previous.completed if previous else False) or result.is_complete,
        best_elapsed_s=best_elapsed,
    )
    records[event_id] = updated
    _save_special_event_records(project_root, records, last_event_id=event_id)
    return updated
