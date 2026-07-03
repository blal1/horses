"""Authenticated encryption (AES-256-GCM) and integrity hashing.

Blob layout produced by :func:`encrypt_bytes`::

    MAGIC(4) | VERSION(1) | NONCE(12) | CIPHERTEXT+TAG(...)

AES-GCM is authenticated: any tampering (or a wrong context/key) fails
decryption with :class:`DecryptionError` rather than returning garbage.
Each ``context`` derives its own subkey via HKDF-SHA256, so the "save"
key and the "assets" key are independent.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from horse_racing_game.security._masterkey import load_master_key

_MAGIC = b"HRG1"
_VERSION = 1
_NONCE_LEN = 12
_HEADER_LEN = len(_MAGIC) + 1 + _NONCE_LEN


class DecryptionError(Exception):
    """Raised when a blob is corrupt, truncated, tampered with, or was
    encrypted under a different key or context."""


def _subkey(context: str) -> bytes:
    """Derive a 32-byte AES key for ``context`` from the master key."""
    hkdf = HKDF(algorithm=SHA256(), length=32, salt=None,
                info=f"hrg/{context}".encode("utf-8"))
    return hkdf.derive(load_master_key())


def encrypt_bytes(data: bytes, context: str) -> bytes:
    """Encrypt ``data`` under the subkey for ``context``. Returns a
    self-describing blob (magic + version + nonce + ciphertext)."""
    key = _subkey(context)
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return _MAGIC + bytes([_VERSION]) + nonce + ciphertext


def decrypt_bytes(blob: bytes, context: str) -> bytes:
    """Reverse :func:`encrypt_bytes`. Raises :class:`DecryptionError` on
    any mismatch or tampering."""
    if len(blob) < _HEADER_LEN or blob[:4] != _MAGIC:
        raise DecryptionError("not an HRG blob (bad magic or truncated)")
    if blob[4] != _VERSION:
        raise DecryptionError(f"unsupported blob version {blob[4]}")
    nonce = blob[5:5 + _NONCE_LEN]
    ciphertext = blob[_HEADER_LEN:]
    try:
        return AESGCM(_subkey(context)).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise DecryptionError("authentication failed (tampered or wrong key)") from exc


def encrypt_file(src: Path, dst: Path, context: str) -> None:
    """Encrypt ``src`` to ``dst`` atomically."""
    blob = encrypt_bytes(Path(src).read_bytes(), context)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_bytes(blob)
    tmp.replace(dst)


def decrypt_file(src: Path, dst: Path | None, context: str) -> bytes:
    """Decrypt ``src``. Writes to ``dst`` when given (atomically) and
    always returns the plaintext bytes."""
    plaintext = decrypt_bytes(Path(src).read_bytes(), context)
    if dst is not None:
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(dst.suffix + ".tmp")
        tmp.write_bytes(plaintext)
        tmp.replace(dst)
    return plaintext


def sha256(data: bytes) -> str:
    """Hex SHA-256 of ``data`` — used for asset/build integrity checks."""
    return hashlib.sha256(data).hexdigest()


def verify(data: bytes, expected_hex: str) -> bool:
    """Constant-time check that ``data`` hashes to ``expected_hex``."""
    return hmac.compare_digest(sha256(data), expected_hex.lower())
