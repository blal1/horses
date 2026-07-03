from __future__ import annotations

import pytest

from horse_racing_game.security import (
    DecryptionError,
    decrypt_bytes,
    decrypt_file,
    encrypt_bytes,
    encrypt_file,
    sha256,
    verify,
)


def test_roundtrip_bytes():
    data = b"photo finish at the wire"
    blob = encrypt_bytes(data, "assets")
    assert blob != data
    assert decrypt_bytes(blob, "assets") == data


def test_empty_payload_roundtrips():
    blob = encrypt_bytes(b"", "save")
    assert decrypt_bytes(blob, "save") == b""


def test_nonce_is_random_per_call():
    a = encrypt_bytes(b"same", "assets")
    b = encrypt_bytes(b"same", "assets")
    assert a != b  # different nonce -> different ciphertext


def test_wrong_context_fails():
    blob = encrypt_bytes(b"secret", "save")
    with pytest.raises(DecryptionError):
        decrypt_bytes(blob, "assets")


def test_tampering_is_detected():
    blob = bytearray(encrypt_bytes(b"integrity matters", "lang"))
    blob[-1] ^= 0x01  # flip a ciphertext bit
    with pytest.raises(DecryptionError):
        decrypt_bytes(bytes(blob), "lang")


def test_truncated_and_bad_magic():
    with pytest.raises(DecryptionError):
        decrypt_bytes(b"", "assets")
    with pytest.raises(DecryptionError):
        decrypt_bytes(b"XXXX" + b"\x01" + b"0" * 12, "assets")


def test_file_roundtrip(tmp_path):
    src = tmp_path / "plain.bin"
    enc = tmp_path / "cipher.dat"
    dec = tmp_path / "out.bin"
    src.write_bytes(b"track data" * 100)
    encrypt_file(src, enc, "assets")
    assert enc.read_bytes()[:4] == b"HRG1"
    returned = decrypt_file(enc, dec, "assets")
    assert returned == src.read_bytes()
    assert dec.read_bytes() == src.read_bytes()


def test_sha256_and_verify():
    data = b"checksum me"
    digest = sha256(data)
    assert len(digest) == 64
    assert verify(data, digest)
    assert verify(data, digest.upper())
    assert not verify(data, sha256(b"other"))
