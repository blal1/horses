from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HorseCard:
    horse_id: str
    display_name: str
    skin_id: str = "default"

    def __post_init__(self) -> None:
        if not self.horse_id:
            raise ValueError("horse_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")
        if not self.skin_id:
            raise ValueError("skin_id must be non-empty")


@dataclass(frozen=True)
class PlayerIdentity:
    player_id: str
    display_name: str
    title_id: str = "rookie_rider"
    badge_ids: tuple[str, ...] = ()
    emblem_id: str = "stable_star"
    club_tag: str | None = None
    horse_card: HorseCard | None = None
    cosmetic_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")
        if not self.title_id:
            raise ValueError("title_id must be non-empty")
        if not self.emblem_id:
            raise ValueError("emblem_id must be non-empty")
        if self.club_tag is not None and not _valid_club_tag(self.club_tag):
            raise ValueError("club_tag must be 2-5 uppercase letters or digits")
        if len(self.badge_ids) != len(set(self.badge_ids)):
            raise ValueError("badge_ids must be unique")
        if len(self.cosmetic_ids) != len(set(self.cosmetic_ids)):
            raise ValueError("cosmetic_ids must be unique")
        if any(not item for item in self.badge_ids):
            raise ValueError("badge_ids must be non-empty")
        if any(not item for item in self.cosmetic_ids):
            raise ValueError("cosmetic_ids must be non-empty")

    @property
    def public_name(self) -> str:
        if self.club_tag is None:
            return self.display_name
        return f"[{self.club_tag}] {self.display_name}"

    def equip_badge(self, badge_id: str, limit: int = 3) -> "PlayerIdentity":
        if not badge_id:
            raise ValueError("badge_id must be non-empty")
        badges = tuple(item for item in self.badge_ids if item != badge_id)
        badges = (badge_id,) + badges
        return self._copy(badge_ids=badges[:limit])

    def equip_cosmetic(self, cosmetic_id: str) -> "PlayerIdentity":
        if not cosmetic_id:
            raise ValueError("cosmetic_id must be non-empty")
        cosmetics = tuple(item for item in self.cosmetic_ids if item != cosmetic_id)
        return self._copy(cosmetic_ids=(cosmetic_id,) + cosmetics)

    def with_title(self, title_id: str) -> "PlayerIdentity":
        if not title_id:
            raise ValueError("title_id must be non-empty")
        return self._copy(title_id=title_id)

    def with_horse_card(self, horse_card: HorseCard) -> "PlayerIdentity":
        return self._copy(horse_card=horse_card)

    def signature(self) -> str:
        parts = [self.public_name, self.title_id.replace("_", " ").title()]
        if self.horse_card is not None:
            parts.append(f"Horse: {self.horse_card.display_name}")
        if self.badge_ids:
            parts.append("Badges: " + ", ".join(self.badge_ids))
        parts.append(f"Emblem: {self.emblem_id}")
        return " | ".join(parts)

    def _copy(
        self,
        *,
        title_id: str | None = None,
        badge_ids: tuple[str, ...] | None = None,
        emblem_id: str | None = None,
        club_tag: str | None = None,
        horse_card: HorseCard | None = None,
        cosmetic_ids: tuple[str, ...] | None = None,
    ) -> "PlayerIdentity":
        return PlayerIdentity(
            player_id=self.player_id,
            display_name=self.display_name,
            title_id=title_id if title_id is not None else self.title_id,
            badge_ids=badge_ids if badge_ids is not None else self.badge_ids,
            emblem_id=emblem_id if emblem_id is not None else self.emblem_id,
            club_tag=club_tag if club_tag is not None else self.club_tag,
            horse_card=horse_card if horse_card is not None else self.horse_card,
            cosmetic_ids=cosmetic_ids if cosmetic_ids is not None else self.cosmetic_ids,
        )


def _valid_club_tag(value: str) -> bool:
    return 2 <= len(value) <= 5 and value.isalnum() and value.upper() == value
