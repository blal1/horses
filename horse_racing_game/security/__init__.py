"""Security core: authenticated encryption and integrity hashing.

Public surface is intentionally small. Callers pass a ``context`` label
(e.g. ``"assets"``, ``"save"``, ``"lang"``); each context uses its own
HKDF-derived subkey, so cracking one context does not expose the others.

This package is a candidate for Cython compilation at build time
(see the build pipeline sub-project). Compiling ``_masterkey`` to a
``.pyd`` turns the embedded key shards into C-level constants.
"""

from __future__ import annotations

from horse_racing_game.security.crypto import (
    DecryptionError,
    decrypt_bytes,
    decrypt_file,
    encrypt_bytes,
    encrypt_file,
    sha256,
    verify,
)

__all__ = [
    "DecryptionError",
    "decrypt_bytes",
    "decrypt_file",
    "encrypt_bytes",
    "encrypt_file",
    "sha256",
    "verify",
]
