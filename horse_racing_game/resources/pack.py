"""Encrypted resource pack: bundle many files into one ``.dat``.

File layout::

    MAGIC(4)="HRPK" | VERSION(1) | INDEX_LEN(4, big-endian uint32) |
    INDEX_BLOB (encrypted, context="pack") | DATA (concatenated entries)

The index is a JSON object ``{name: {"offset": int, "length": int,
"sha256": hex}}`` where offsets are relative to the start of DATA and
lengths/hashes describe each entry's *encrypted* blob (context="assets").
Reading verifies the hash before decrypting, so a corrupted or swapped
pack fails loudly.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from horse_racing_game.security.crypto import (
    DecryptionError,
    decrypt_bytes,
    encrypt_bytes,
    sha256,
    verify,
)

_MAGIC = b"HRPK"
_VERSION = 1
_INDEX_CONTEXT = "pack"
_ENTRY_CONTEXT = "assets"


class PackError(Exception):
    """Raised on a malformed, corrupt, or tampered pack."""


class PackWriter:
    """Accumulate named files, then write an encrypted pack."""

    def __init__(self) -> None:
        self._entries: dict[str, bytes] = {}

    def add(self, name: str, data: bytes) -> None:
        if name in self._entries:
            raise PackError(f"duplicate entry: {name}")
        self._entries[name] = data

    def add_file(self, name: str, path: Path) -> None:
        self.add(name, Path(path).read_bytes())

    def write(self, path: Path) -> None:
        index: dict[str, dict[str, object]] = {}
        data = bytearray()
        for name in sorted(self._entries):
            blob = encrypt_bytes(self._entries[name], _ENTRY_CONTEXT)
            index[name] = {"offset": len(data), "length": len(blob), "sha256": sha256(blob)}
            data.extend(blob)

        index_blob = encrypt_bytes(json.dumps(index, sort_keys=True).encode("utf-8"), _INDEX_CONTEXT)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as fh:
            fh.write(_MAGIC)
            fh.write(bytes([_VERSION]))
            fh.write(struct.pack(">I", len(index_blob)))
            fh.write(index_blob)
            fh.write(bytes(data))
        tmp.replace(path)


class PackReader:
    """Read entries from an encrypted pack. Loads the index eagerly; entry
    bytes are read and decrypted on demand."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        raw = self._path.read_bytes()
        if len(raw) < 9 or raw[:4] != _MAGIC:
            raise PackError("not an HRPK pack (bad magic or truncated)")
        if raw[4] != _VERSION:
            raise PackError(f"unsupported pack version {raw[4]}")
        (index_len,) = struct.unpack(">I", raw[5:9])
        index_blob = raw[9:9 + index_len]
        if len(index_blob) != index_len:
            raise PackError("truncated pack index")
        try:
            index_json = decrypt_bytes(index_blob, _INDEX_CONTEXT)
        except DecryptionError as exc:
            raise PackError("pack index failed authentication") from exc
        self._index: dict[str, dict] = json.loads(index_json)
        self._data = raw[9 + index_len:]

    def list_files(self) -> list[str]:
        return sorted(self._index)

    def exists(self, name: str) -> bool:
        return name in self._index

    def get(self, name: str) -> bytes:
        meta = self._index.get(name)
        if meta is None:
            raise PackError(f"no such entry: {name}")
        start = int(meta["offset"])
        blob = self._data[start:start + int(meta["length"])]
        if not verify(blob, str(meta["sha256"])):
            raise PackError(f"integrity check failed for {name}")
        try:
            return decrypt_bytes(blob, _ENTRY_CONTEXT)
        except DecryptionError as exc:
            raise PackError(f"decryption failed for {name}") from exc
