from __future__ import annotations

import pytest

from horse_racing_game.resources import PackError, PackReader, PackWriter


def _build(tmp_path, entries):
    writer = PackWriter()
    for name, data in entries.items():
        writer.add(name, data)
    path = tmp_path / "game.dat"
    writer.write(path)
    return path


def test_pack_roundtrip(tmp_path):
    entries = {"horses.json": b'{"a":1}', "sfx/gallop.ogg": b"\x00\x01\x02" * 50}
    path = _build(tmp_path, entries)
    reader = PackReader(path)
    assert reader.list_files() == ["horses.json", "sfx/gallop.ogg"]
    for name, data in entries.items():
        assert reader.exists(name)
        assert reader.get(name) == data


def test_pack_is_not_plaintext(tmp_path):
    path = _build(tmp_path, {"secret.json": b"top secret content string"})
    raw = path.read_bytes()
    assert b"top secret content string" not in raw
    assert raw[:4] == b"HRPK"


def test_missing_entry_raises(tmp_path):
    path = _build(tmp_path, {"a": b"x"})
    reader = PackReader(path)
    assert not reader.exists("b")
    with pytest.raises(PackError):
        reader.get("b")


def test_duplicate_add_raises(tmp_path):
    writer = PackWriter()
    writer.add("a", b"1")
    with pytest.raises(PackError):
        writer.add("a", b"2")


def test_bad_magic_raises(tmp_path):
    bad = tmp_path / "bad.dat"
    bad.write_bytes(b"NOPE" + b"\x00" * 20)
    with pytest.raises(PackError):
        PackReader(bad)


def test_tampered_entry_detected(tmp_path):
    path = _build(tmp_path, {"a": b"important data" * 10})
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF  # corrupt last data byte
    path.write_bytes(bytes(raw))
    reader = PackReader(path)
    with pytest.raises(PackError):
        reader.get("a")
