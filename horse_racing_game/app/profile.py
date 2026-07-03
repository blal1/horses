from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from horse_racing_game.app.economy import EconomyState, RewardGrant, Wallet
from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.identity import HorseCard, PlayerIdentity
from horse_racing_game.app.savedata import read_secure_object_migrating_plaintext, write_secure_json


TITLE_OPTIONS = ("rookie_rider", "storm_rider", "elite_racer")
BADGE_OPTIONS = ("founder", "winner", "veteran")
COSMETIC_OPTIONS = ("red_silks", "gold_saddle", "midnight_wrap")
STARTER_REWARD_ID = "profile_starter"
STARTER_REWARD = RewardGrant(
    STARTER_REWARD_ID,
    soft_currency=120,
    xp=140,
    item_ids=("storm_rider", "founder", "red_silks"),
)


@dataclass(frozen=True)
class PlayerProfile:
    identity: PlayerIdentity
    economy: EconomyState = field(default_factory=EconomyState)

    def signature(self) -> str:
        return self.identity.signature()


def profile_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file("profile.json")


def default_player_profile() -> PlayerProfile:
    return PlayerProfile(
        PlayerIdentity(
            "local_player",
            "Rider",
            horse_card=HorseCard("ember_stride", "Ember Stride"),
        )
    )


def load_player_profile(project_root: Path) -> PlayerProfile:
    data = read_secure_object_migrating_plaintext(profile_path(project_root))
    if data is None:
        return default_player_profile()
    identity_data = data.get("identity")
    economy_data = data.get("economy")
    try:
        identity = _identity_from_dict(identity_data if isinstance(identity_data, dict) else {})
        economy = _economy_from_dict(economy_data if isinstance(economy_data, dict) else {})
    except (TypeError, ValueError):
        return default_player_profile()
    return PlayerProfile(identity, economy)


def save_player_profile(project_root: Path, profile: PlayerProfile) -> None:
    write_secure_json(
        profile_path(project_root),
        {
            "identity": _identity_to_dict(profile.identity),
            "economy": _economy_to_dict(profile.economy),
        },
    )


def claim_profile_starter_reward(project_root: Path, profile: PlayerProfile) -> PlayerProfile:
    if STARTER_REWARD_ID in profile.economy.completed_achievement_ids:
        return profile
    rewarded = profile.economy.grant(STARTER_REWARD)
    economy = EconomyState(
        wallet=rewarded.wallet,
        owned_item_ids=rewarded.owned_item_ids,
        xp=rewarded.xp,
        season_level=rewarded.season_level,
        completed_achievement_ids=tuple(sorted(rewarded.completed_achievement_ids + (STARTER_REWARD_ID,))),
    )
    updated = PlayerProfile(profile.identity, economy)
    save_player_profile(project_root, updated)
    return updated


def equip_profile_title(project_root: Path, profile: PlayerProfile, title_id: str) -> PlayerProfile:
    _require_known(title_id, TITLE_OPTIONS, "title")
    if title_id != "rookie_rider" and title_id not in profile.economy.owned_item_ids:
        raise ValueError("title is not owned")
    updated = PlayerProfile(profile.identity.with_title(title_id), profile.economy)
    save_player_profile(project_root, updated)
    return updated


def equip_profile_badge(project_root: Path, profile: PlayerProfile, badge_id: str) -> PlayerProfile:
    _require_known(badge_id, BADGE_OPTIONS, "badge")
    if badge_id not in profile.economy.owned_item_ids:
        raise ValueError("badge is not owned")
    updated = PlayerProfile(profile.identity.equip_badge(badge_id), profile.economy)
    save_player_profile(project_root, updated)
    return updated


def equip_profile_cosmetic(project_root: Path, profile: PlayerProfile, cosmetic_id: str) -> PlayerProfile:
    _require_known(cosmetic_id, COSMETIC_OPTIONS, "cosmetic")
    if cosmetic_id not in profile.economy.owned_item_ids:
        raise ValueError("cosmetic is not owned")
    updated = PlayerProfile(profile.identity.equip_cosmetic(cosmetic_id), profile.economy)
    save_player_profile(project_root, updated)
    return updated


def profile_summary_lines(profile: PlayerProfile) -> tuple[str, ...]:
    identity = profile.identity
    economy = profile.economy
    return (
        f"Rider: {identity.public_name}",
        f"Title: {identity.title_id}",
        f"Badges: {', '.join(identity.badge_ids) if identity.badge_ids else 'none'}",
        f"Cosmetics: {', '.join(identity.cosmetic_ids) if identity.cosmetic_ids else 'none'}",
        f"Wallet: {economy.wallet.soft_currency} soft | {economy.wallet.premium_currency} premium",
        f"XP: {economy.xp} | Season level: {economy.season_level}",
        f"Owned items: {len(economy.owned_item_ids)}",
        f"Signature: {identity.signature()}",
    )


def _identity_to_dict(identity: PlayerIdentity) -> dict:
    payload = asdict(identity)
    return payload


def _identity_from_dict(data: dict[str, object]) -> PlayerIdentity:
    horse_card_data = data.get("horse_card")
    horse_card = None
    if isinstance(horse_card_data, dict):
        horse_card = HorseCard(
            str(horse_card_data.get("horse_id") or "ember_stride"),
            str(horse_card_data.get("display_name") or "Ember Stride"),
            str(horse_card_data.get("skin_id") or "default"),
        )
    return PlayerIdentity(
        str(data.get("player_id") or "local_player"),
        str(data.get("display_name") or "Rider"),
        title_id=str(data.get("title_id") or "rookie_rider"),
        badge_ids=_string_tuple(data.get("badge_ids")),
        emblem_id=str(data.get("emblem_id") or "stable_star"),
        club_tag=_optional_string(data.get("club_tag")),
        horse_card=horse_card,
        cosmetic_ids=_string_tuple(data.get("cosmetic_ids")),
    )


def _economy_to_dict(economy: EconomyState) -> dict:
    return {
        "wallet": asdict(economy.wallet),
        "owned_item_ids": list(economy.owned_item_ids),
        "xp": economy.xp,
        "season_level": economy.season_level,
        "completed_achievement_ids": list(economy.completed_achievement_ids),
    }


def _economy_from_dict(data: dict[str, object]) -> EconomyState:
    wallet_data = data.get("wallet")
    wallet = Wallet()
    if isinstance(wallet_data, dict):
        wallet = Wallet(
            soft_currency=_non_negative_int(wallet_data.get("soft_currency"), 0),
            premium_currency=_non_negative_int(wallet_data.get("premium_currency"), 0),
        )
    return EconomyState(
        wallet=wallet,
        owned_item_ids=_string_tuple(data.get("owned_item_ids")),
        xp=_non_negative_int(data.get("xp"), 0),
        season_level=max(_non_negative_int(data.get("season_level"), 1), 1),
        completed_achievement_ids=_string_tuple(data.get("completed_achievement_ids")),
    )


def _require_known(item_id: str, options: tuple[str, ...], label: str) -> None:
    if item_id not in options:
        raise ValueError(f"unknown {label}")


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _non_negative_int(value: object, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(parsed, 0)
