from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SoundAsset:
    sound_id: str
    path: Path
    source: str
    license: str
    category: str
    loop: bool
    default_volume: float
    priority: int


class SoundCatalog:
    def __init__(self, assets: tuple[SoundAsset, ...]) -> None:
        self._assets = assets
        self._by_id = {asset.sound_id: asset for asset in assets}

    def __len__(self) -> int:
        return len(self._assets)

    def get(self, sound_id: str) -> SoundAsset | None:
        return self._by_id.get(sound_id)

    def assets(self) -> tuple[SoundAsset, ...]:
        return self._assets

    def missing_files(self, project_root: Path) -> tuple[Path, ...]:
        missing: list[Path] = []
        for asset in self._assets:
            asset_path = project_root / asset.path
            if not asset_path.exists():
                missing.append(asset.path)
        return tuple(missing)

    def first_by_category(self, category: str) -> SoundAsset | None:
        for asset in self._assets:
            if asset.category == category:
                return asset
        return None

    def first_id_by_category(self, category: str) -> str | None:
        asset = self.first_by_category(category)
        if asset is None:
            return None
        return asset.sound_id

    def first_matching_id(self, category: str, token: str) -> str | None:
        for asset in self._assets:
            if asset.category == category and token in asset.sound_id:
                return asset.sound_id
        return self.first_id_by_category(category)

