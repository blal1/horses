from __future__ import annotations

import importlib.util
from pathlib import Path

from horse_racing_game.app.integrity import (
    build_integrity_manifest,
    verify_integrity_manifest,
    write_integrity_manifest,
)


_BUILD_RELEASE_PATH = Path(__file__).parent.parent / "scripts" / "build_release.py"
_SPEC = importlib.util.spec_from_file_location("build_release", _BUILD_RELEASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BUILD_RELEASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BUILD_RELEASE)
signtool_command = _BUILD_RELEASE.signtool_command


def test_integrity_manifest_hashes_files_and_skips_itself(tmp_path):
    (tmp_path / "game.exe").write_bytes(b"binary")
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "resources.dat").write_bytes(b"packed")

    manifest_path = write_integrity_manifest(tmp_path)
    entries = build_integrity_manifest(tmp_path)

    assert manifest_path.name == "install-integrity.json"
    assert [entry.path for entry in entries] == ["content/resources.dat", "game.exe"]
    assert verify_integrity_manifest(tmp_path) == ()


def test_integrity_manifest_reports_tampered_file(tmp_path):
    path = tmp_path / "game.exe"
    path.write_bytes(b"original")
    write_integrity_manifest(tmp_path)

    path.write_bytes(b"edited")

    issues = verify_integrity_manifest(tmp_path)
    assert len(issues) == 1
    assert issues[0].path == "game.exe"
    assert issues[0].status == "size-mismatch"


def test_signtool_command_uses_sha256_timestamp_and_cert():
    command = signtool_command(
        "dist/HorseRacingAudioFirst/HorseRacingAudioFirst.exe",
        cert_sha1="ABC123",
        timestamp_url="https://timestamp.example.test",
        signtool="C:/signtool.exe",
    )

    assert command[:6] == ["C:/signtool.exe", "sign", "/fd", "SHA256", "/sha1", "ABC123"]
    assert "/tr" in command
    assert "https://timestamp.example.test" in command
