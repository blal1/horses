from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.resources.loader import ResourceProvider


@dataclass(frozen=True)
class PackFile:
    root: Path
    logical_prefix: str = ""

    @classmethod
    def from_path(cls, path: Path) -> "PackFile":
        if path.suffix and path.parent.name in {"content", "assets"}:
            return cls(path.parent.parent, path.parent.name)
        return cls(path.parent if path.suffix else path)

    @property
    def provider(self) -> ResourceProvider:
        return ResourceProvider(self.root)

    def logical_name(self, relative_path: str | Path) -> str:
        relative = Path(relative_path)
        parts = relative.parts
        if parts and parts[0] in {"content", "assets"}:
            return relative.as_posix()
        if self.logical_prefix:
            return (Path(self.logical_prefix) / relative).as_posix()
        return relative.as_posix()

    def resolve(self, relative_path: str | Path) -> Path:
        return self.root / Path(relative_path)

    def exists(self, relative_path: str | Path) -> bool:
        name = self.logical_name(relative_path)
        try:
            self.provider.get_bytes(name)
        except FileNotFoundError:
            return False
        return True

    def read_text(self, relative_path: str | Path, encoding: str = "utf-8") -> str:
        return self.provider.get_bytes(self.logical_name(relative_path)).decode(encoding)

    def read_json(self, relative_path: str | Path) -> object:
        return self.provider.get_json(self.logical_name(relative_path))

    def read_json_array(self, relative_path: str | Path) -> list[dict[str, object]]:
        parsed = self.read_json(relative_path)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON array in {self.resolve(relative_path)}")
        objects: list[dict[str, object]] = []
        for item in parsed:
            if not isinstance(item, dict):
                raise ValueError(f"Expected object entries in {self.resolve(relative_path)}")
            objects.append(item)
        return objects

    def iter_paths(self, pattern: str = "**/*") -> tuple[Path, ...]:
        return tuple(path for path in self.root.glob(pattern) if path.is_file())
