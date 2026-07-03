from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileDirectories:
    project_root: Path

    @property
    def content_root(self) -> Path:
        return self.project_root / "content"

    @property
    def save_root(self) -> Path:
        return self.project_root / "save"

    @property
    def assets_root(self) -> Path:
        return self.project_root / "assets"

    def content_file(self, name: str) -> Path:
        return self.content_root / name

    def save_file(self, name: str) -> Path:
        return self.save_root / name

    def custom_tracks_file(self) -> Path:
        return self.save_file("custom_tracks.json")

    def progress_file(self) -> Path:
        return self.save_file("progress.json")

