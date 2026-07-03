from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.security.crypto import sha256, verify


DEFAULT_MANIFEST_NAME = "install-integrity.json"


@dataclass(frozen=True)
class IntegrityEntry:
    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class IntegrityIssue:
    path: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "status": self.status, "detail": self.detail}


def build_integrity_manifest(root: Path, *, manifest_name: str = DEFAULT_MANIFEST_NAME) -> tuple[IntegrityEntry, ...]:
    root = Path(root)
    entries: list[IntegrityEntry] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == manifest_name:
            continue
        data = path.read_bytes()
        entries.append(IntegrityEntry(relative, sha256(data), len(data)))
    return tuple(entries)


def write_integrity_manifest(root: Path, *, manifest_name: str = DEFAULT_MANIFEST_NAME) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    entries = build_integrity_manifest(root, manifest_name=manifest_name)
    payload = {
        "algorithm": "sha256",
        "files": [entry.to_dict() for entry in entries],
    }
    path = root / manifest_name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def verify_integrity_manifest(root: Path, *, manifest_name: str = DEFAULT_MANIFEST_NAME) -> tuple[IntegrityIssue, ...]:
    root = Path(root)
    manifest_path = root / manifest_name
    if not manifest_path.exists():
        return ()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (IntegrityIssue(manifest_name, "invalid", str(exc)),)
    files = payload.get("files")
    if not isinstance(files, list):
        return (IntegrityIssue(manifest_name, "invalid", "missing files array"),)
    issues: list[IntegrityIssue] = []
    for item in files:
        if not isinstance(item, dict):
            issues.append(IntegrityIssue(manifest_name, "invalid", "non-object file entry"))
            continue
        relative = item.get("path")
        expected_hash = item.get("sha256")
        expected_size = item.get("size_bytes")
        if not isinstance(relative, str) or not isinstance(expected_hash, str) or not isinstance(expected_size, int):
            issues.append(IntegrityIssue(manifest_name, "invalid", "malformed file entry"))
            continue
        path = root / relative
        if not path.exists():
            issues.append(IntegrityIssue(relative, "missing", "file is listed but absent"))
            continue
        data = path.read_bytes()
        if len(data) != expected_size:
            issues.append(IntegrityIssue(relative, "size-mismatch", f"expected {expected_size}, got {len(data)}"))
            continue
        if not verify(data, expected_hash):
            issues.append(IntegrityIssue(relative, "hash-mismatch", "sha256 mismatch"))
    return tuple(issues)
