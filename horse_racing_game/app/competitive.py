from __future__ import annotations

from dataclasses import dataclass


DIVISIONS = (
    ("Bronze", 0),
    ("Silver", 1100),
    ("Gold", 1300),
    ("Platinum", 1550),
    ("Diamond", 1800),
)


@dataclass(frozen=True)
class CompetitiveProfile:
    player_id: str
    display_name: str
    mmr: int = 1000
    ranked_races: int = 0
    wins: int = 0
    placements_remaining: int = 5

    def __post_init__(self) -> None:
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")
        if self.mmr < 0:
            raise ValueError("mmr must be non-negative")
        if self.ranked_races < 0:
            raise ValueError("ranked_races must be non-negative")
        if self.wins < 0:
            raise ValueError("wins must be non-negative")
        if self.placements_remaining < 0:
            raise ValueError("placements_remaining must be non-negative")

    @property
    def division(self) -> str:
        return division_for_mmr(self.mmr)

    @property
    def is_placed(self) -> bool:
        return self.placements_remaining == 0


@dataclass(frozen=True)
class RankedRaceResult:
    player_id: str
    rank: int
    field_size: int

    def __post_init__(self) -> None:
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if self.field_size < 2:
            raise ValueError("field_size must be at least two")
        if self.rank < 1 or self.rank > self.field_size:
            raise ValueError("rank must be within the field")


@dataclass(frozen=True)
class LeaderboardRow:
    position: int
    player_id: str
    display_name: str
    mmr: int
    division: str
    ranked_races: int
    wins: int


class CompetitiveLadder:
    def __init__(self, season_id: str) -> None:
        if not season_id:
            raise ValueError("season_id must be non-empty")
        self._season_id = season_id
        self._profiles: dict[str, CompetitiveProfile] = {}

    @property
    def season_id(self) -> str:
        return self._season_id

    def upsert_profile(self, profile: CompetitiveProfile) -> CompetitiveProfile:
        self._profiles[profile.player_id] = profile
        return profile

    def profile(self, player_id: str) -> CompetitiveProfile:
        try:
            return self._profiles[player_id]
        except KeyError as error:
            raise ValueError(f"unknown player id: {player_id}") from error

    def record_result(self, result: RankedRaceResult) -> CompetitiveProfile:
        profile = self.profile(result.player_id)
        delta = mmr_delta_for_rank(result.rank, result.field_size)
        updated = CompetitiveProfile(
            player_id=profile.player_id,
            display_name=profile.display_name,
            mmr=max(0, profile.mmr + delta),
            ranked_races=profile.ranked_races + 1,
            wins=profile.wins + (1 if result.rank == 1 else 0),
            placements_remaining=max(0, profile.placements_remaining - 1),
        )
        self._profiles[profile.player_id] = updated
        return updated

    def record_results(self, results: tuple[RankedRaceResult, ...]) -> tuple[CompetitiveProfile, ...]:
        if not results:
            return ()
        field_sizes = {result.field_size for result in results}
        ranks = {result.rank for result in results}
        if field_sizes != {len(results)}:
            raise ValueError("field size must match result count")
        if ranks != set(range(1, len(results) + 1)):
            raise ValueError("ranked results must contain each rank exactly once")
        return tuple(self.record_result(result) for result in sorted(results, key=lambda item: item.rank))

    def leaderboard(self, limit: int | None = None) -> tuple[LeaderboardRow, ...]:
        profiles = sorted(self._profiles.values(), key=lambda item: (-item.mmr, -item.wins, item.player_id))
        rows = tuple(
            LeaderboardRow(
                position=index + 1,
                player_id=profile.player_id,
                display_name=profile.display_name,
                mmr=profile.mmr,
                division=profile.division,
                ranked_races=profile.ranked_races,
                wins=profile.wins,
            )
            for index, profile in enumerate(profiles)
        )
        return rows if limit is None else rows[:limit]

    def matchmaking_band(self, player_id: str, width: int = 150) -> tuple[int, int]:
        if width < 0:
            raise ValueError("width must be non-negative")
        profile = self.profile(player_id)
        return max(0, profile.mmr - width), profile.mmr + width


def division_for_mmr(mmr: int) -> str:
    if mmr < 0:
        raise ValueError("mmr must be non-negative")
    current = DIVISIONS[0][0]
    for name, threshold in DIVISIONS:
        if mmr >= threshold:
            current = name
    return current


def mmr_delta_for_rank(rank: int, field_size: int) -> int:
    result = RankedRaceResult("player", rank, field_size)
    midpoint = (result.field_size + 1) / 2.0
    return round((midpoint - result.rank) * 24)
