"""Obfuscated embedded master key.

The 32-byte master key is never stored as a plain literal. It is split
into two XOR shards that are recombined at runtime. On its own this is
light obfuscation; the real hardening comes from compiling this module to
a ``.pyd`` via Cython, which lifts these tuples into C constants that no
longer appear as readable byte strings in the shipped binary.

Rotating the key: regenerate both shards (see scripts/gen_master_key.py)
and re-encrypt all packed assets/saves with the new key.
"""

from __future__ import annotations

# XOR shards. master = SHARD_A ^ SHARD_B. Neither shard alone reveals it.
_SHARD_A = (204, 216, 23, 19, 253, 125, 172, 194, 78, 11, 51, 202, 64, 205, 34, 198, 221, 126, 137, 138, 147, 216, 9, 83, 163, 226, 99, 173, 192, 249, 170, 162)
_SHARD_B = (241, 132, 16, 250, 18, 53, 218, 9, 205, 242, 247, 55, 4, 128, 9, 225, 119, 100, 237, 37, 5, 130, 92, 175, 107, 108, 221, 54, 53, 219, 181, 79)


def load_master_key() -> bytes:
    """Reassemble the master key. Kept as a function so nothing holds the
    raw key at import time longer than necessary."""
    return bytes(a ^ b for a, b in zip(_SHARD_A, _SHARD_B))
