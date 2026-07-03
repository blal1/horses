from __future__ import annotations

from datetime import datetime
from pathlib import Path


def runtime_log_path(project_root: Path) -> Path:
    return project_root / "runtime_debug.log"


def write_runtime_log(project_root: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    path = runtime_log_path(project_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")