from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Wallet:
    soft_currency: int = 0
    premium_currency: int = 0

    def __post_init__(self) -> None:
        if self.soft_currency < 0:
            raise ValueError("soft_currency must be non-negative")
        if self.premium_currency < 0:
            raise ValueError("premium_currency must be non-negative")

    def credit(self, soft_currency: int = 0, premium_currency: int = 0) -> "Wallet":
        if soft_currency < 0 or premium_currency < 0:
            raise ValueError("credit values must be non-negative")
        return Wallet(self.soft_currency + soft_currency, self.premium_currency + premium_currency)

    def spend(self, soft_currency: int = 0, premium_currency: int = 0) -> "Wallet":
        if soft_currency < 0 or premium_currency < 0:
            raise ValueError("spend values must be non-negative")
        if soft_currency > self.soft_currency or premium_currency > self.premium_currency:
            raise ValueError("not enough currency")
        return Wallet(self.soft_currency - soft_currency, self.premium_currency - premium_currency)


@dataclass(frozen=True)
class Unlockable:
    item_id: str
    category: str
    soft_cost: int = 0
    premium_cost: int = 0
    required_level: int = 0

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("item_id must be non-empty")
        if self.category not in {"cosmetic", "horse", "track", "title", "badge"}:
            raise ValueError("invalid unlock category")
        if self.soft_cost < 0 or self.premium_cost < 0:
            raise ValueError("cost values must be non-negative")
        if self.required_level < 0:
            raise ValueError("required_level must be non-negative")


@dataclass(frozen=True)
class RewardGrant:
    reason: str
    soft_currency: int = 0
    premium_currency: int = 0
    xp: int = 0
    item_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("reason must be non-empty")
        if self.soft_currency < 0 or self.premium_currency < 0 or self.xp < 0:
            raise ValueError("reward values must be non-negative")
        if any(not item_id for item_id in self.item_ids):
            raise ValueError("item_ids must be non-empty")


@dataclass(frozen=True)
class Achievement:
    achievement_id: str
    description: str
    target_value: int
    reward: RewardGrant

    def __post_init__(self) -> None:
        if not self.achievement_id:
            raise ValueError("achievement_id must be non-empty")
        if not self.description:
            raise ValueError("description must be non-empty")
        if self.target_value < 1:
            raise ValueError("target_value must be positive")

    def is_unlocked(self, value: int) -> bool:
        return value >= self.target_value


@dataclass(frozen=True)
class EconomyState:
    wallet: Wallet = Wallet()
    owned_item_ids: tuple[str, ...] = ()
    xp: int = 0
    season_level: int = 1
    completed_achievement_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.xp < 0:
            raise ValueError("xp must be non-negative")
        if self.season_level < 1:
            raise ValueError("season_level must be positive")
        if len(self.owned_item_ids) != len(set(self.owned_item_ids)):
            raise ValueError("owned_item_ids must be unique")
        if len(self.completed_achievement_ids) != len(set(self.completed_achievement_ids)):
            raise ValueError("completed_achievement_ids must be unique")

    def grant(self, reward: RewardGrant) -> "EconomyState":
        owned = tuple(sorted(set(self.owned_item_ids + reward.item_ids)))
        xp = self.xp + reward.xp
        return EconomyState(
            wallet=self.wallet.credit(reward.soft_currency, reward.premium_currency),
            owned_item_ids=owned,
            xp=xp,
            season_level=season_level_for_xp(xp),
            completed_achievement_ids=self.completed_achievement_ids,
        )

    def purchase(self, unlockable: Unlockable) -> "EconomyState":
        if self.season_level < unlockable.required_level:
            raise ValueError("season level too low")
        if unlockable.item_id in self.owned_item_ids:
            raise ValueError("item already owned")
        return EconomyState(
            wallet=self.wallet.spend(unlockable.soft_cost, unlockable.premium_cost),
            owned_item_ids=tuple(sorted(self.owned_item_ids + (unlockable.item_id,))),
            xp=self.xp,
            season_level=self.season_level,
            completed_achievement_ids=self.completed_achievement_ids,
        )

    def complete_achievement(self, achievement: Achievement, value: int) -> "EconomyState":
        if achievement.achievement_id in self.completed_achievement_ids:
            return self
        if not achievement.is_unlocked(value):
            raise ValueError("achievement target not met")
        rewarded = self.grant(achievement.reward)
        return EconomyState(
            wallet=rewarded.wallet,
            owned_item_ids=rewarded.owned_item_ids,
            xp=rewarded.xp,
            season_level=rewarded.season_level,
            completed_achievement_ids=tuple(sorted(rewarded.completed_achievement_ids + (achievement.achievement_id,))),
        )


def race_participation_reward(rank: int, finished: bool) -> RewardGrant:
    if rank < 1:
        raise ValueError("rank must be positive")
    if not finished:
        return RewardGrant("race_participation", soft_currency=5, xp=5)
    soft = max(10, 60 - (rank - 1) * 12)
    xp = max(10, 40 - (rank - 1) * 6)
    return RewardGrant("race_result", soft_currency=soft, xp=xp)


def season_level_for_xp(xp: int) -> int:
    if xp < 0:
        raise ValueError("xp must be non-negative")
    return xp // 100 + 1
