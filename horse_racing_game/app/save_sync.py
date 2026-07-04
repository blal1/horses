from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.platform_support import SaveSyncDecision, SaveSyncRecord, decide_save_sync
from horse_racing_game.app.savedata import atomic_write_json, load_json_object
from horse_racing_game.security.crypto import sha256


SAVE_SYNC_MANIFEST = "save_sync_manifest.json"
SAVE_SYNC_FILES_DIR = "files"
SAVE_SYNC_CONFLICTS_DIR = "sync_conflicts"


@dataclass(frozen=True)
class SaveSyncFile:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.path or self.path.startswith("../") or self.path.startswith("/"):
            raise ValueError("path must be a relative save path")
        if not self.sha256:
            raise ValueError("sha256 must be non-empty")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")


@dataclass(frozen=True)
class SaveSyncManifest:
    device_id: str
    revision: int
    updated_at_s: float
    files: tuple[SaveSyncFile, ...]

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id must be non-empty")
        if self.revision < 0:
            raise ValueError("revision must be non-negative")
        if self.updated_at_s < 0:
            raise ValueError("updated_at_s must be non-negative")

    @property
    def checksum(self) -> str:
        payload = [
            {"path": item.path, "sha256": item.sha256, "size_bytes": item.size_bytes}
            for item in self.files
        ]
        return sha256(json.dumps(payload, sort_keys=True).encode("utf-8"))

    def record(self) -> SaveSyncRecord:
        return SaveSyncRecord(self.device_id, self.revision, self.updated_at_s, self.checksum)


@dataclass(frozen=True)
class SaveSyncResult:
    decision: SaveSyncDecision
    local_manifest: SaveSyncManifest
    remote_manifest: SaveSyncManifest | None
    conflict_backup: Path | None = None


def save_sync_manifest_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file(SAVE_SYNC_MANIFEST)


def build_save_sync_manifest(
    project_root: Path,
    device_id: str,
    revision: int,
    updated_at_s: float,
) -> SaveSyncManifest:
    save_root = FileDirectories(project_root).save_root
    files: list[SaveSyncFile] = []
    if save_root.exists():
        for path in sorted(save_root.rglob("*"), key=lambda item: item.relative_to(save_root).as_posix()):
            if not path.is_file() or _is_ignored_save_path(save_root, path):
                continue
            data = path.read_bytes()
            files.append(SaveSyncFile(path.relative_to(save_root).as_posix(), sha256(data), len(data)))
    return SaveSyncManifest(device_id, revision, updated_at_s, tuple(files))


def load_save_sync_manifest(path: Path) -> SaveSyncManifest | None:
    data = load_json_object(path)
    if data is None:
        return None
    try:
        return SaveSyncManifest(
            str(data.get("device_id") or ""),
            int(data.get("revision") or 0),
            float(data.get("updated_at_s") or 0.0),
            tuple(
                SaveSyncFile(
                    str(item.get("path") or ""),
                    str(item.get("sha256") or ""),
                    int(item.get("size_bytes") or 0),
                )
                for item in _object_list(data.get("files"))
            ),
        )
    except (TypeError, ValueError):
        return None


def sync_save_directory(
    project_root: Path,
    sync_root: Path,
    device_id: str,
    revision: int,
    updated_at_s: float,
) -> SaveSyncResult:
    local_manifest = build_save_sync_manifest(project_root, device_id, revision, updated_at_s)
    remote_manifest = load_save_sync_manifest(Path(sync_root) / SAVE_SYNC_MANIFEST)
    decision = decide_save_sync(local_manifest.record(), None if remote_manifest is None else remote_manifest.record())
    conflict_backup: Path | None = None
    if decision.action == "upload":
        _write_snapshot(FileDirectories(project_root).save_root, Path(sync_root), local_manifest)
    elif decision.action == "download":
        _restore_snapshot(FileDirectories(project_root).save_root, Path(sync_root), remote_manifest)
    elif decision.action == "conflict":
        if decision.winning_device_id == local_manifest.device_id:
            _write_snapshot(FileDirectories(project_root).save_root, Path(sync_root), local_manifest)
        else:
            conflict_backup = _backup_save_root(FileDirectories(project_root).save_root, remote_manifest)
            _restore_snapshot(FileDirectories(project_root).save_root, Path(sync_root), remote_manifest)
    if decision.action in {"download", "conflict"} and decision.winning_device_id != local_manifest.device_id:
        assert remote_manifest is not None
        atomic_write_json(save_sync_manifest_path(project_root), _manifest_to_dict(remote_manifest))
    else:
        atomic_write_json(save_sync_manifest_path(project_root), _manifest_to_dict(local_manifest))
    return SaveSyncResult(decision, local_manifest, remote_manifest, conflict_backup)


def _write_snapshot(save_root: Path, sync_root: Path, manifest: SaveSyncManifest) -> None:
    files_root = sync_root / SAVE_SYNC_FILES_DIR
    files_root.mkdir(parents=True, exist_ok=True)
    for item in manifest.files:
        source = save_root / item.path
        target = _resolved_child(files_root, item.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    atomic_write_json(sync_root / SAVE_SYNC_MANIFEST, _manifest_to_dict(manifest))


def _restore_snapshot(save_root: Path, sync_root: Path, manifest: SaveSyncManifest | None) -> None:
    if manifest is None:
        return
    files_root = sync_root / SAVE_SYNC_FILES_DIR
    save_root.mkdir(parents=True, exist_ok=True)
    for item in manifest.files:
        source = _resolved_child(files_root, item.path)
        if not source.exists():
            raise ValueError(f"missing synced save file: {item.path}")
        data = source.read_bytes()
        if sha256(data) != item.sha256 or len(data) != item.size_bytes:
            raise ValueError(f"synced save file failed checksum: {item.path}")
        target = _resolved_child(save_root, item.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _backup_save_root(save_root: Path, remote_manifest: SaveSyncManifest | None) -> Path | None:
    if remote_manifest is None or not save_root.exists():
        return None
    backup = save_root / SAVE_SYNC_CONFLICTS_DIR / f"{remote_manifest.device_id}-rev{remote_manifest.revision}"
    for path in sorted(save_root.rglob("*"), key=lambda item: item.relative_to(save_root).as_posix()):
        if not path.is_file() or _is_ignored_save_path(save_root, path):
            continue
        target = _resolved_child(backup, path.relative_to(save_root).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return backup


def _is_ignored_save_path(save_root: Path, path: Path) -> bool:
    relative = path.relative_to(save_root).as_posix()
    return (
        relative == SAVE_SYNC_MANIFEST
        or relative.endswith(".tmp")
        or relative.startswith(f"{SAVE_SYNC_CONFLICTS_DIR}/")
    )


def _resolved_child(root: Path, relative: str) -> Path:
    root = root.resolve()
    target = (root / relative).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"path escapes sync root: {relative}")
    return target


def _manifest_to_dict(manifest: SaveSyncManifest) -> dict[str, object]:
    return {
        "device_id": manifest.device_id,
        "revision": manifest.revision,
        "updated_at_s": manifest.updated_at_s,
        "checksum": manifest.checksum,
        "files": [asdict(item) for item in manifest.files],
    }


def _object_list(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))
