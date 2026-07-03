"""Regenerate the obfuscated master-key shards in security/_masterkey.py.

Usage: python scripts/gen_master_key.py

WARNING: rotating the key invalidates every asset/save encrypted with the
old key. Re-pack assets and migrate saves after rotating.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "horse_racing_game" / "security" / "_masterkey.py"


def _fmt(name: str, data: bytes) -> str:
    body = ", ".join(str(b) for b in data)
    return f"_{name} = ({body})"


def main() -> None:
    master = secrets.token_bytes(32)
    pad = secrets.token_bytes(32)
    shard = bytes(a ^ b for a, b in zip(master, pad))
    assert bytes(a ^ b for a, b in zip(shard, pad)) == master

    text = TARGET.read_text(encoding="utf-8")
    text = re.sub(r"_SHARD_A = \([^)]*\)", _fmt("SHARD_A", shard), text, count=1)
    text = re.sub(r"_SHARD_B = \([^)]*\)", _fmt("SHARD_B", pad), text, count=1)
    TARGET.write_text(text, encoding="utf-8")
    print(f"Rotated master key in {TARGET}")
    print("Re-pack assets and migrate saves before shipping.")


if __name__ == "__main__":
    main()
