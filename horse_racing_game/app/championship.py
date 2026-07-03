from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.app.career import points_for_rank
from horse_racing_game.content.pack_file import PackFile
from horse_racing_game.domain.rival import RivalProfile
from horse_racing_game.domain.stable import Stable


@dataclass(frozen=True)
class StandingRow:
    name: str
    points: int
    races_run: int
    stable_name: str = "Independent"


@dataclass(frozen=True)
class ChampionshipRace:
    race_id: str
    name: str
    track_id: str
    weather_id: str
    briefing: str
    rival_stables: dict[str, str]


def rival_points_after_race(rival_current_points: int, rival_rank: int) -> int:
    return rival_current_points + points_for_rank(rival_rank)


def compute_standings(
    player_name: str,
    player_points: int,
    player_races: int,
    rivals: tuple[RivalProfile, ...],
    rival_points: dict[str, int] | None = None,
    rival_races: dict[str, int] | None = None,
    rival_stables: dict[str, str] | None = None,
    stables: tuple[Stable, ...] = (),
) -> tuple[StandingRow, ...]:
    rival_points = rival_points or {}
    rival_races = rival_races or {}
    rival_stables = rival_stables or {}
    stable_names = {stable.stable_id: stable.name for stable in stables}

    rows: list[StandingRow] = [
        StandingRow(
            name=player_name,
            points=player_points,
            races_run=player_races,
            stable_name="Player stable",
        )
    ]
    for rival in rivals:
        rows.append(
            StandingRow(
                name=rival.display_name,
                points=rival_points.get(rival.horse_id, 0),
                races_run=rival_races.get(rival.horse_id, 0),
                stable_name=stable_names.get(rival_stables.get(rival.horse_id, ""), "Independent"),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.points, row.name)))


def standings_text(standings: tuple[StandingRow, ...]) -> str:
    lines: list[str] = []
    for index, row in enumerate(standings):
        position = index + 1
        lines.append(f"{position}. {row.name}, {row.points} points, {row.stable_name}.")
    return " ".join(lines)


def load_championship_calendar(path: Path) -> tuple[ChampionshipRace, ...]:
    data = PackFile.from_path(path).read_json(path.name)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return tuple(_parse_calendar_race(item, path) for item in data)


def next_championship_race(calendar: tuple[ChampionshipRace, ...], races_completed: int) -> ChampionshipRace | None:
    if races_completed < 0:
        races_completed = 0
    if races_completed >= len(calendar):
        return None
    return calendar[races_completed]


def championship_title(calendar: tuple[ChampionshipRace, ...], races_completed: int, points: int) -> str:
    next_race = next_championship_race(calendar, races_completed)
    if next_race is None:
        return f"Championship complete. {points} points."
    return f"Championship race {races_completed + 1} of {len(calendar)}. {next_race.name}. {points} points. {next_race.briefing}"


def championship_rival_stables(calendar: tuple[ChampionshipRace, ...]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for race in calendar:
        assignments.update(race.rival_stables)
    return assignments


def _parse_calendar_race(value: object, path: Path) -> ChampionshipRace:
    if not isinstance(value, dict):
        raise ValueError(f"Expected object entries in {path}")
    rival_stables = value.get("rival_stables")
    if not isinstance(rival_stables, dict):
        raise ValueError(f"Expected rival_stables object in {path}")
    parsed_stables: dict[str, str] = {}
    for key, item in rival_stables.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"Expected string rival stable mapping in {path}")
        parsed_stables[key] = item
    return ChampionshipRace(
        race_id=_required_string(value, "race_id", path),
        name=_required_string(value, "name", path),
        track_id=_required_string(value, "track_id", path),
        weather_id=_required_string(value, "weather_id", path),
        briefing=_required_string(value, "briefing", path),
        rival_stables=parsed_stables,
    )


def _required_string(data: dict[str, object], key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Expected string '{key}' in {path}")
    return value
