from __future__ import annotations

from dataclasses import dataclass

from horse_racing_game.app.stable_management import stable_staff_by_id


@dataclass(frozen=True)
class CareerContract:
    contract_id: str
    sponsor_id: str
    required_reputation: int
    base_prize: int
    win_bonus: int = 0

    def __post_init__(self) -> None:
        if not self.contract_id:
            raise ValueError("contract_id must be non-empty")
        if not self.sponsor_id:
            raise ValueError("sponsor_id must be non-empty")
        if self.required_reputation < 0:
            raise ValueError("required_reputation must be non-negative")
        if self.base_prize < 0 or self.win_bonus < 0:
            raise ValueError("prize values must be non-negative")

    def is_available(self, reputation: int) -> bool:
        return reputation >= self.required_reputation

    def prize_for_rank(self, rank: int) -> int:
        if rank < 1:
            raise ValueError("rank must be positive")
        payout = max(0, self.base_prize - (rank - 1) * max(1, self.base_prize // 4))
        return payout + (self.win_bonus if rank == 1 else 0)


DEFAULT_CAREER_CONTRACTS = (
    CareerContract("rookie_sponsor", "Rookie Feed Co.", required_reputation=0, base_prize=40, win_bonus=20),
    CareerContract("regional_backer", "Regional Backer", required_reputation=12, base_prize=75, win_bonus=35),
    CareerContract("elite_syndicate", "Elite Syndicate", required_reputation=28, base_prize=120, win_bonus=60),
)


def career_contract_by_id(contract_id: str) -> CareerContract | None:
    return next((contract for contract in DEFAULT_CAREER_CONTRACTS if contract.contract_id == contract_id), None)


def career_condition_risk(fatigue: int, energy: int, staff_ids: tuple[str, ...] = ()) -> int:
    fatigue_pressure = max(0, fatigue - 35)
    energy_pressure = 30 if energy <= 0 else 12 if energy == 1 else 0
    vet_reduction = sum(
        12
        for staff_id in staff_ids
        for staff_member in (stable_staff_by_id(staff_id),)
        if staff_member is not None and staff_member.role == "vet"
    )
    return min(100, max(0, fatigue_pressure + energy_pressure - vet_reduction))


def career_condition_after_event(
    condition: "HorseCondition",
    *,
    energy: int,
    rank: int | None,
    is_training: bool,
    staff_ids: tuple[str, ...] = (),
) -> "HorseCondition":
    base_intensity = 10 if is_training else 18
    low_energy_load = 8 if energy <= 0 else 4 if energy == 1 else 0
    poor_finish_load = 4 if rank is not None and rank > 3 and not is_training else 0
    trainer_training_load = 0
    vet_reduction = 0
    for staff_id in staff_ids:
        staff_member = stable_staff_by_id(staff_id)
        if staff_member is None:
            continue
        if staff_member.role == "trainer" and is_training:
            trainer_training_load += 2
        if staff_member.role == "vet":
            vet_reduction += 4
    intensity = max(4, base_intensity + low_energy_load + poor_finish_load + trainer_training_load - vet_reduction)
    updated = condition.after_race(intensity)
    risk = career_condition_risk(updated.fatigue, energy, staff_ids)
    injury_days = 2 if risk >= 75 else 1 if risk >= 55 and energy <= 0 else 0
    return HorseCondition(
        condition.horse_id,
        fatigue=updated.fatigue,
        injury_days_remaining=max(updated.injury_days_remaining, injury_days),
    )


def career_condition_after_rest(condition: "HorseCondition", rest_gain: int) -> "HorseCondition":
    return condition.rest(max(1, rest_gain))


def career_condition_status(fatigue: int, injury_days: int) -> str:
    if injury_days > 0:
        return f"injured for {injury_days} day{'s' if injury_days != 1 else ''}"
    if fatigue >= 70:
        return "high fatigue"
    if fatigue >= 40:
        return "moderate fatigue"
    return "fresh"


@dataclass(frozen=True)
class HorseCondition:
    horse_id: str
    fatigue: int = 0
    injury_days_remaining: int = 0

    def __post_init__(self) -> None:
        if not self.horse_id:
            raise ValueError("horse_id must be non-empty")
        if self.fatigue < 0:
            raise ValueError("fatigue must be non-negative")
        if self.injury_days_remaining < 0:
            raise ValueError("injury_days_remaining must be non-negative")

    @property
    def can_race(self) -> bool:
        return self.injury_days_remaining == 0

    def after_race(self, intensity: int, injured: bool = False) -> "HorseCondition":
        if intensity < 0:
            raise ValueError("intensity must be non-negative")
        return HorseCondition(
            self.horse_id,
            fatigue=min(100, self.fatigue + intensity),
            injury_days_remaining=max(self.injury_days_remaining, 2 if injured else 0),
        )

    def rest(self, days: int = 1) -> "HorseCondition":
        if days < 0:
            raise ValueError("days must be non-negative")
        return HorseCondition(
            self.horse_id,
            fatigue=max(0, self.fatigue - days * 20),
            injury_days_remaining=max(0, self.injury_days_remaining - days),
        )


@dataclass(frozen=True)
class CareerProfile:
    reputation: int = 0
    prize_money: int = 0
    active_contract_id: str | None = None
    completed_story_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reputation < 0:
            raise ValueError("reputation must be non-negative")
        if self.prize_money < 0:
            raise ValueError("prize_money must be non-negative")
        if self.active_contract_id == "":
            raise ValueError("active_contract_id must be non-empty when provided")

    def sign_contract(self, contract: CareerContract) -> "CareerProfile":
        if not contract.is_available(self.reputation):
            raise ValueError("reputation too low for contract")
        return CareerProfile(self.reputation, self.prize_money, contract.contract_id, self.completed_story_ids)

    def record_result(self, contract: CareerContract, rank: int) -> "CareerProfile":
        prize = contract.prize_for_rank(rank)
        reputation_gain = max(1, 6 - rank)
        return CareerProfile(
            reputation=self.reputation + reputation_gain,
            prize_money=self.prize_money + prize,
            active_contract_id=self.active_contract_id,
            completed_story_ids=self.completed_story_ids,
        )

    def complete_story(self, story_id: str) -> "CareerProfile":
        if not story_id:
            raise ValueError("story_id must be non-empty")
        stories = tuple(sorted(set(self.completed_story_ids + (story_id,))))
        return CareerProfile(self.reputation, self.prize_money, self.active_contract_id, stories)


@dataclass(frozen=True)
class ChampionshipBranch:
    branch_id: str
    min_reputation: int
    required_story_id: str | None = None

    def __post_init__(self) -> None:
        if not self.branch_id:
            raise ValueError("branch_id must be non-empty")
        if self.min_reputation < 0:
            raise ValueError("min_reputation must be non-negative")
        if self.required_story_id == "":
            raise ValueError("required_story_id must be non-empty when provided")

    def is_unlocked(self, profile: CareerProfile) -> bool:
        if profile.reputation < self.min_reputation:
            return False
        if self.required_story_id is None:
            return True
        return self.required_story_id in profile.completed_story_ids


def unlocked_branches(profile: CareerProfile, branches: tuple[ChampionshipBranch, ...]) -> tuple[ChampionshipBranch, ...]:
    return tuple(branch for branch in branches if branch.is_unlocked(profile))
