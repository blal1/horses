from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import atomic_write_json, load_json_object


SURFACE_VARIANTS = {"turf", "dirt", "soft_turf", "mud", "sand", "synthetic"}


@dataclass(frozen=True)
class TrackShare:
    track_id: str
    author_id: str
    visibility: str = "private"
    version: int = 1

    def __post_init__(self) -> None:
        if not self.track_id:
            raise ValueError("track_id must be non-empty")
        if not self.author_id:
            raise ValueError("author_id must be non-empty")
        if self.visibility not in {"private", "friends", "public"}:
            raise ValueError("invalid visibility")
        if self.version < 1:
            raise ValueError("version must be positive")


@dataclass(frozen=True)
class TrackRating:
    track_id: str
    player_id: str
    stars: int
    tag_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.track_id:
            raise ValueError("track_id must be non-empty")
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if not 1 <= self.stars <= 5:
            raise ValueError("stars must be between 1 and 5")
        if any(not tag_id for tag_id in self.tag_ids):
            raise ValueError("tag_ids must be non-empty")


@dataclass(frozen=True)
class WeatherPreset:
    preset_id: str
    weather_id: str
    label: str

    def __post_init__(self) -> None:
        if not self.preset_id:
            raise ValueError("preset_id must be non-empty")
        if not self.weather_id:
            raise ValueError("weather_id must be non-empty")
        if not self.label:
            raise ValueError("label must be non-empty")


@dataclass(frozen=True)
class EventRuleset:
    ruleset_id: str
    allowed_surface_variants: tuple[str, ...] = ("turf", "dirt", "soft_turf", "mud")
    weather_preset_ids: tuple[str, ...] = ()
    obstacle_density: str = "normal"

    def __post_init__(self) -> None:
        if not self.ruleset_id:
            raise ValueError("ruleset_id must be non-empty")
        if not self.allowed_surface_variants:
            raise ValueError("allowed_surface_variants must be non-empty")
        if any(surface not in SURFACE_VARIANTS for surface in self.allowed_surface_variants):
            raise ValueError("unknown surface variant")
        if any(not preset_id for preset_id in self.weather_preset_ids):
            raise ValueError("weather_preset_ids must be non-empty")
        if self.obstacle_density not in {"none", "light", "normal", "heavy"}:
            raise ValueError("invalid obstacle density")

    def allows_surface(self, surface: str) -> bool:
        return surface in self.allowed_surface_variants


@dataclass(frozen=True)
class TrackDiscoveryResult:
    track_id: str
    score: float
    average_rating: float
    rating_count: int


class TrackCatalog:
    def __init__(self) -> None:
        self._shares: dict[str, TrackShare] = {}
        self._ratings: dict[tuple[str, str], TrackRating] = {}
        self._weather_presets: dict[str, WeatherPreset] = {}
        self._rulesets: dict[str, EventRuleset] = {}

    def publish(self, share: TrackShare) -> TrackShare:
        self._shares[share.track_id] = share
        return share

    def rate(self, rating: TrackRating) -> TrackRating:
        if rating.track_id not in self._shares:
            raise ValueError("cannot rate an unpublished track")
        self._ratings[(rating.track_id, rating.player_id)] = rating
        return rating

    def add_weather_preset(self, preset: WeatherPreset) -> WeatherPreset:
        self._weather_presets[preset.preset_id] = preset
        return preset

    def add_ruleset(self, ruleset: EventRuleset) -> EventRuleset:
        missing_presets = [preset_id for preset_id in ruleset.weather_preset_ids if preset_id not in self._weather_presets]
        if missing_presets:
            raise ValueError("ruleset references unknown weather preset")
        self._rulesets[ruleset.ruleset_id] = ruleset
        return ruleset

    def average_rating(self, track_id: str) -> float:
        ratings = [rating.stars for rating in self._ratings.values() if rating.track_id == track_id]
        if not ratings:
            return 0.0
        return round(sum(ratings) / len(ratings), 2)

    def discover(
        self,
        *,
        visibility: str = "public",
        surface: str | None = None,
        tag_id: str | None = None,
    ) -> tuple[TrackDiscoveryResult, ...]:
        results: list[TrackDiscoveryResult] = []
        for share in self._shares.values():
            if share.visibility != visibility:
                continue
            ratings = [rating for rating in self._ratings.values() if rating.track_id == share.track_id]
            if tag_id is not None and not any(tag_id in rating.tag_ids for rating in ratings):
                continue
            if surface is not None and not _track_id_suggests_surface(share.track_id, surface):
                continue
            average = self.average_rating(share.track_id)
            rating_count = len(ratings)
            score = round(average + min(rating_count, 10) * 0.1 + share.version * 0.01, 2)
            results.append(TrackDiscoveryResult(share.track_id, score, average, rating_count))
        return tuple(sorted(results, key=lambda item: (-item.score, item.track_id)))

    def ruleset(self, ruleset_id: str) -> EventRuleset:
        try:
            return self._rulesets[ruleset_id]
        except KeyError as error:
            raise ValueError(f"unknown ruleset: {ruleset_id}") from error

    def shares(self) -> tuple[TrackShare, ...]:
        return tuple(sorted(self._shares.values(), key=lambda item: item.track_id))

    def ratings(self) -> tuple[TrackRating, ...]:
        return tuple(sorted(self._ratings.values(), key=lambda item: (item.track_id, item.player_id)))

    def weather_presets(self) -> tuple[WeatherPreset, ...]:
        return tuple(sorted(self._weather_presets.values(), key=lambda item: item.preset_id))

    def rulesets(self) -> tuple[EventRuleset, ...]:
        return tuple(sorted(self._rulesets.values(), key=lambda item: item.ruleset_id))


def track_catalog_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file("track_catalog.json")


def save_track_catalog(project_root: Path, catalog: TrackCatalog) -> None:
    atomic_write_json(
        track_catalog_path(project_root),
        {
            "shares": [asdict(share) for share in catalog.shares()],
            "ratings": [asdict(rating) for rating in catalog.ratings()],
            "weather_presets": [asdict(preset) for preset in catalog.weather_presets()],
            "rulesets": [asdict(ruleset) for ruleset in catalog.rulesets()],
        },
    )


def load_track_catalog(project_root: Path) -> TrackCatalog:
    data = load_json_object(track_catalog_path(project_root))
    catalog = TrackCatalog()
    if data is None:
        return catalog
    try:
        for item in _list(data.get("shares")):
            catalog.publish(
                TrackShare(
                    str(item.get("track_id") or ""),
                    str(item.get("author_id") or ""),
                    str(item.get("visibility") or "private"),
                    int(item.get("version") or 1),
                )
            )
        for item in _list(data.get("weather_presets")):
            catalog.add_weather_preset(
                WeatherPreset(
                    str(item.get("preset_id") or ""),
                    str(item.get("weather_id") or ""),
                    str(item.get("label") or ""),
                )
            )
        for item in _list(data.get("rulesets")):
            catalog.add_ruleset(
                EventRuleset(
                    str(item.get("ruleset_id") or ""),
                    _string_tuple(item.get("allowed_surface_variants")),
                    _string_tuple(item.get("weather_preset_ids")),
                    str(item.get("obstacle_density") or "normal"),
                )
            )
        for item in _list(data.get("ratings")):
            catalog.rate(
                TrackRating(
                    str(item.get("track_id") or ""),
                    str(item.get("player_id") or ""),
                    int(item.get("stars") or 0),
                    _string_tuple(item.get("tag_ids")),
                )
            )
    except (TypeError, ValueError):
        return TrackCatalog()
    return catalog


def _track_id_suggests_surface(track_id: str, surface: str) -> bool:
    return surface in track_id or surface == "turf" and "grass" in track_id


def _list(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str) and item)
