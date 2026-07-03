"""Packed, encrypted resource storage.

A single ``.dat`` file bundles many logical files. The index is encrypted
under the ``pack`` context; each entry is encrypted under ``assets`` and
integrity-checked (SHA-256) on read. See :mod:`horse_racing_game.resources.pack`.
"""

from __future__ import annotations

from horse_racing_game.resources.pack import PackError, PackReader, PackWriter

__all__ = ["PackError", "PackReader", "PackWriter"]
