from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StableUpgrade:
    upgrade_id: str
    category: str
    level: int
    cost: int

    def __post_init__(self) -> None:
        if not self.upgrade_id:
            raise ValueError("upgrade_id must be non-empty")
        if self.category not in {"barn", "track", "clinic", "feed_room"}:
            raise ValueError("invalid upgrade category")
        if self.level < 1:
            raise ValueError("level must be positive")
        if self.cost < 0:
            raise ValueError("cost must be non-negative")


@dataclass(frozen=True)
class StaffMember:
    staff_id: str
    role: str
    skill: int
    weekly_cost: int

    def __post_init__(self) -> None:
        if not self.staff_id:
            raise ValueError("staff_id must be non-empty")
        if self.role not in {"trainer", "vet", "conditioner", "groom"}:
            raise ValueError("invalid staff role")
        if not 1 <= self.skill <= 10:
            raise ValueError("skill must be between 1 and 10")
        if self.weekly_cost < 0:
            raise ValueError("weekly_cost must be non-negative")


DEFAULT_STABLE_STAFF = (
    StaffMember("assistant_trainer", "trainer", 4, 8),
    StaffMember("stable_vet", "vet", 3, 7),
)

DEFAULT_STABLE_UPGRADES = (
    StableUpgrade("training_ring_1", "track", 1, 6),
    StableUpgrade("recovery_clinic_1", "clinic", 1, 10),
)


def stable_staff_by_id(staff_id: str) -> StaffMember | None:
    return next((staff_member for staff_member in DEFAULT_STABLE_STAFF if staff_member.staff_id == staff_id), None)


def stable_upgrade_by_id(upgrade_id: str) -> StableUpgrade | None:
    return next((upgrade for upgrade in DEFAULT_STABLE_UPGRADES if upgrade.upgrade_id == upgrade_id), None)


def stable_staff_weekly_cost(staff_ids: tuple[str, ...]) -> int:
    return sum(
        staff_member.weekly_cost
        for staff_id in staff_ids
        for staff_member in (stable_staff_by_id(staff_id),)
        if staff_member is not None
    )


def stable_rest_energy_gain(upgrade_ids: tuple[str, ...], staff_ids: tuple[str, ...]) -> int:
    clinic_bonus = 0
    for upgrade_id in upgrade_ids:
        upgrade = stable_upgrade_by_id(upgrade_id)
        if upgrade is not None and upgrade.category == "clinic":
            clinic_bonus = 1
            break
    vet_bonus = 0
    for staff_id in staff_ids:
        staff_member = stable_staff_by_id(staff_id)
        if staff_member is not None and staff_member.role == "vet":
            vet_bonus = 1
            break
    return 1 + clinic_bonus + vet_bonus


@dataclass(frozen=True)
class TrainingPlan:
    plan_id: str
    horse_id: str
    focus: str
    intensity: int

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise ValueError("plan_id must be non-empty")
        if not self.horse_id:
            raise ValueError("horse_id must be non-empty")
        if self.focus not in {"speed", "stamina", "handling", "recovery"}:
            raise ValueError("invalid training focus")
        if not 1 <= self.intensity <= 5:
            raise ValueError("intensity must be between 1 and 5")

    def fatigue_cost(self) -> int:
        return self.intensity * (2 if self.focus != "recovery" else 0)


@dataclass(frozen=True)
class SupplyInventory:
    feed_units: int = 0
    medicine_units: int = 0

    def __post_init__(self) -> None:
        if self.feed_units < 0:
            raise ValueError("feed_units must be non-negative")
        if self.medicine_units < 0:
            raise ValueError("medicine_units must be non-negative")

    def consume(self, feed_units: int = 0, medicine_units: int = 0) -> "SupplyInventory":
        if feed_units < 0 or medicine_units < 0:
            raise ValueError("supply consumption must be non-negative")
        if feed_units > self.feed_units or medicine_units > self.medicine_units:
            raise ValueError("not enough supplies")
        return SupplyInventory(self.feed_units - feed_units, self.medicine_units - medicine_units)


@dataclass(frozen=True)
class StableManagementState:
    stable_id: str
    funds: int
    upgrades: tuple[StableUpgrade, ...] = ()
    staff: tuple[StaffMember, ...] = ()
    training_plans: tuple[TrainingPlan, ...] = ()
    supplies: SupplyInventory = SupplyInventory()
    horse_specializations: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.stable_id:
            raise ValueError("stable_id must be non-empty")
        if self.funds < 0:
            raise ValueError("funds must be non-negative")
        specializations = self.horse_specializations or {}
        if any(not horse_id for horse_id in specializations):
            raise ValueError("horse specialization ids must be non-empty")
        if any(focus not in {"speed", "stamina", "handling", "recovery"} for focus in specializations.values()):
            raise ValueError("invalid horse specialization")

    def buy_upgrade(self, upgrade: StableUpgrade) -> "StableManagementState":
        if any(item.upgrade_id == upgrade.upgrade_id for item in self.upgrades):
            raise ValueError("upgrade already purchased")
        if upgrade.cost > self.funds:
            raise ValueError("not enough funds")
        return self._copy(funds=self.funds - upgrade.cost, upgrades=self.upgrades + (upgrade,))

    def hire_staff(self, staff_member: StaffMember) -> "StableManagementState":
        if any(item.staff_id == staff_member.staff_id for item in self.staff):
            raise ValueError("staff already hired")
        return self._copy(staff=self.staff + (staff_member,))

    def add_training_plan(self, plan: TrainingPlan) -> "StableManagementState":
        plans = tuple(item for item in self.training_plans if item.horse_id != plan.horse_id)
        return self._copy(training_plans=plans + (plan,))

    def specialize_horse(self, horse_id: str, focus: str) -> "StableManagementState":
        if not horse_id:
            raise ValueError("horse_id must be non-empty")
        if focus not in {"speed", "stamina", "handling", "recovery"}:
            raise ValueError("invalid specialization focus")
        specializations = dict(self.horse_specializations or {})
        specializations[horse_id] = focus
        return self._copy(horse_specializations=specializations)

    def weekly_cost(self) -> int:
        return sum(member.weekly_cost for member in self.staff)

    def training_effect_bonus(self, focus: str) -> float:
        if focus not in {"speed", "stamina", "handling", "recovery"}:
            raise ValueError("invalid training focus")
        staff_bonus = sum(member.skill for member in self.staff if member.role in {"trainer", "conditioner"}) * 0.01
        facility_bonus = sum(upgrade.level for upgrade in self.upgrades if upgrade.category in {"track", "barn"}) * 0.025
        return round(1.0 + staff_bonus + facility_bonus, 3)

    def vet_recovery_bonus(self) -> float:
        staff_bonus = sum(member.skill for member in self.staff if member.role == "vet") * 0.015
        clinic_bonus = sum(upgrade.level for upgrade in self.upgrades if upgrade.category == "clinic") * 0.04
        return round(1.0 + staff_bonus + clinic_bonus, 3)

    def _copy(
        self,
        *,
        funds: int | None = None,
        upgrades: tuple[StableUpgrade, ...] | None = None,
        staff: tuple[StaffMember, ...] | None = None,
        training_plans: tuple[TrainingPlan, ...] | None = None,
        supplies: SupplyInventory | None = None,
        horse_specializations: dict[str, str] | None = None,
    ) -> "StableManagementState":
        return StableManagementState(
            stable_id=self.stable_id,
            funds=self.funds if funds is None else funds,
            upgrades=self.upgrades if upgrades is None else upgrades,
            staff=self.staff if staff is None else staff,
            training_plans=self.training_plans if training_plans is None else training_plans,
            supplies=self.supplies if supplies is None else supplies,
            horse_specializations=dict(self.horse_specializations or {}) if horse_specializations is None else horse_specializations,
        )
