"""Runtime resource access: read from the encrypted pack when present,
otherwise fall back to loose files on disk (developer builds).

Game code should request resources by their project-relative posix name,
e.g. ``get_json("content/horses.json")``. In a packed release the bytes
come from ``resources.dat``; in a dev checkout they come straight from the
file tree. Callers do not care which.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from horse_racing_game.resources.pack import PackReader


class ResourceProvider:
    def __init__(self, root: Path, pack_name: str = "resources.dat") -> None:
        self._root = Path(root)
        pack_path = self._root / pack_name
        self._pack = PackReader(pack_path) if pack_path.exists() else None

    @property
    def packed(self) -> bool:
        return self._pack is not None

    def get_bytes(self, name: str) -> bytes:
        if self._pack is not None and self._pack.exists(name):
            return self._pack.get(name)
        path = self._root / name
        if not path.exists():
            raise FileNotFoundError(name)
        return path.read_bytes()

    def get_json(self, name: str) -> Any:
        return json.loads(self.get_bytes(name).decode("utf-8-sig"))


@lru_cache(maxsize=1)
def default_provider() -> ResourceProvider:
    """Provider rooted at the app base dir. Prefers a bundled pack next to
    the executable / project root."""
    # dist/resources.dat in dev; alongside the frozen exe in a release.
    for candidate in (Path.cwd() / "dist", Path.cwd(), Path(__file__).resolve().parents[2]):
        if (candidate / "resources.dat").exists():
            return ResourceProvider(candidate)
    return ResourceProvider(Path(__file__).resolve().parents[2])
