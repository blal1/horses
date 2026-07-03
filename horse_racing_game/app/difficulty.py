"""Difficulty tiers that scale opponent strength.

``opponent_strength`` is multiplied into the opponents' target pace in
``RaceEngine`` (1.0 = current balance, higher = tougher field). Career mode
escalates the tier across the season so the final race is the hardest.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyTier:
    tier_id: str
    name: str
    opponent_strength: float


DIFFICULTY_TIERS = (
    DifficultyTier("rookie", "Rookie", 0.97),
    DifficultyTier("pro", "Pro", 1.0),
    DifficultyTier("elite", "Elite", 1.04),
)

DEFAULT_DIFFICULTY = DIFFICULTY_TIERS[1]


def difficulty_by_id(tier_id: str) -> DifficultyTier:
    for tier in DIFFICULTY_TIERS:
        if tier.tier_id == tier_id:
            return tier
    return DEFAULT_DIFFICULTY


def career_difficulty(race_index: int, total_races: int) -> DifficultyTier:
    """Tier for the ``race_index``-th career race (0-based) of a ``total_races``
    season: opening races are Rookie, the middle Pro, the closer Elite."""
    if total_races <= 1:
        return DEFAULT_DIFFICULTY
    index = min(max(race_index, 0), total_races - 1)
    fraction = index / (total_races - 1)
    if fraction < 1 / 3:
        return DIFFICULTY_TIERS[0]
    if fraction < 2 / 3:
        return DIFFICULTY_TIERS[1]
    return DIFFICULTY_TIERS[2]
