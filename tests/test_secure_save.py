from __future__ import annotations

from horse_racing_game.app.savedata import (
    read_secure_json,
    read_secure_object,
    read_secure_object_migrating_plaintext,
    write_secure_json,
)


def test_secure_save_roundtrip(tmp_path):
    path = tmp_path / "progress.sav"
    payload = {"credits": 500, "unlocks": ["barn", "sprint"], "level": 7}
    write_secure_json(path, payload)
    assert read_secure_json(path) == payload
    assert read_secure_object(path) == payload


def test_secure_save_is_not_plaintext(tmp_path):
    path = tmp_path / "economy.sav"
    write_secure_json(path, {"credits": 999999})
    raw = path.read_bytes()
    assert b"999999" not in raw
    assert b"credits" not in raw


def test_edited_save_rejected(tmp_path):
    path = tmp_path / "progress.sav"
    write_secure_json(path, {"credits": 100})
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0x01  # a save editor flips a byte
    path.write_bytes(bytes(raw))
    assert read_secure_json(path) is None  # tamper -> treated as no valid save


def test_missing_save_returns_none(tmp_path):
    assert read_secure_json(tmp_path / "nope.sav") is None
    assert read_secure_object(tmp_path / "nope.sav") is None


def test_plaintext_object_is_migrated_to_secure_save(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text('{"credits": 250, "unlocks": ["stable"]}', encoding="utf-8")

    assert read_secure_object_migrating_plaintext(path) == {
        "credits": 250,
        "unlocks": ["stable"],
    }
    assert read_secure_object(path) == {"credits": 250, "unlocks": ["stable"]}
    assert b"credits" not in path.read_bytes()
