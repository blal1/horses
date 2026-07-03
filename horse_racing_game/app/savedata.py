from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from horse_racing_game.security.crypto import (
    DecryptionError,
    decrypt_bytes,
    encrypt_bytes,
)

_SAVE_CONTEXT = "save"


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_json_object(path: Path) -> dict[str, object] | None:
    data = load_json(path)
    return data if isinstance(data, dict) else None


def load_json_array(path: Path) -> list[object] | None:
    data = load_json(path)
    return data if isinstance(data, list) else None


def atomic_write_json(path: Path, payload: object, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, indent=indent, sort_keys=True), encoding="utf-8")
    temporary_path.replace(path)


# --- Secure (tamper-evident) saves -------------------------------------------
# For files that must resist hand-editing (progress, economy, unlocks). The
# payload is JSON, then AES-256-GCM encrypted under the "save" context. Any
# edit to the file fails authentication, so load returns None (treat as "no
# valid save") rather than trusting altered data.


def write_secure_json(path: Path, payload: object) -> None:
    """Write ``payload`` as an encrypted, tamper-evident save, atomically."""
    blob = encrypt_bytes(
        json.dumps(payload, sort_keys=True).encode("utf-8"), _SAVE_CONTEXT
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_bytes(blob)
    temporary_path.replace(path)


def read_secure_json(path: Path) -> Any | None:
    """Read an encrypted save. Returns ``None`` if the file is missing,
    unreadable, or has been tampered with (failed authentication)."""
    if not path.exists():
        return None
    try:
        plaintext = decrypt_bytes(path.read_bytes(), _SAVE_CONTEXT)
    except (OSError, DecryptionError):
        return None
    try:
        return json.loads(plaintext)
    except json.JSONDecodeError:
        return None


def read_secure_object(path: Path) -> dict[str, object] | None:
    data = read_secure_json(path)
    return data if isinstance(data, dict) else None


def read_secure_object_migrating_plaintext(path: Path) -> dict[str, object] | None:
    """Read a secure object, importing an existing plaintext JSON object once."""
    data = read_secure_object(path)
    if data is not None:
        return data
    data = load_json_object(path)
    if data is None:
        return None
    write_secure_json(path, data)
    return data
