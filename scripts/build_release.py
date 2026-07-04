"""One-shot hardened release build.

Pipeline:
    1. Build the encrypted resource pack (content/ + assets/ -> dist/resources.dat)
    2. Compile sensitive modules to native .pyd (Cython + MSVC)
    3. (optional) strip the .py sources of compiled modules so only .pyd ships
    4. Run PyInstaller against HorseRacingAudioFirst.spec

Usage:
    python scripts/build_release.py [--strip-sources] [--skip-pyinstaller]

Run from an environment with the project venv active and MSVC available.
``--strip-sources`` is the real hardening step: after it, the master key and
crypto live only in compiled form. Keep a clean checkout for development.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
WINDOWS_DIST_DIR = ROOT / "dist" / "HorseRacingAudioFirst"
WINDOWS_EXE = WINDOWS_DIST_DIR / "HorseRacingAudioFirst.exe"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Kept in sync with SENSITIVE_MODULES in build_cython.py.
COMPILED_SOURCES = [
    "horse_racing_game/security/_masterkey.py",
    "horse_racing_game/security/crypto.py",
    "horse_racing_game/resources/pack.py",
]


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def signtool_command(
    executable: Path,
    *,
    cert_sha1: str,
    timestamp_url: str,
    signtool: str = "signtool",
) -> list[str]:
    if not cert_sha1:
        raise ValueError("cert_sha1 must be non-empty")
    return [
        signtool,
        "sign",
        "/fd",
        "SHA256",
        "/sha1",
        cert_sha1,
        "/tr",
        timestamp_url,
        "/td",
        "SHA256",
        str(executable),
    ]


def emit_install_integrity_manifest(dist_dir: Path) -> Path:
    from horse_racing_game.app.integrity import write_integrity_manifest

    return write_integrity_manifest(dist_dir)


def audit_protected_release_tree(dist_dir: Path) -> tuple[str, ...]:
    """Return plaintext resource leaks in a protected release tree."""
    leaks: list[str] = []
    if not (dist_dir / "resources.dat").is_file():
        leaks.append("missing resources.dat")
    for name in ("content", "assets"):
        path = dist_dir / name
        if path.exists():
            leaks.append(path.relative_to(dist_dir).as_posix())
    for pattern in ("content/*.json", "assets/**/*.ogg", "assets/**/*.mp3", "assets/**/*.wav"):
        for path in dist_dir.glob(pattern):
            if path.is_file():
                leaks.append(path.relative_to(dist_dir).as_posix())
    return tuple(sorted(set(leaks)))


def audit_sensitive_code_tree(dist_dir: Path, compiled_sources: list[str] | tuple[str, ...] = COMPILED_SOURCES) -> tuple[str, ...]:
    """Return sensitive Python source leaks or missing native extensions."""
    dist_dir = Path(dist_dir)
    problems: list[str] = []
    all_files = [path for path in dist_dir.rglob("*") if path.is_file()]
    for rel in compiled_sources:
        source_path = Path(rel)
        source_posix = source_path.as_posix()
        source_suffix = "/".join(source_path.parts[-3:])
        for path in all_files:
            rel_posix = path.relative_to(dist_dir).as_posix()
            if rel_posix == source_posix or rel_posix.endswith(source_suffix):
                problems.append(f"sensitive source shipped: {rel_posix}")
        native_matches = [
            path for path in all_files
            if path.stem.startswith(source_path.stem) and path.suffix.lower() in {".pyd", ".so", ".dylib"}
        ]
        if not native_matches:
            problems.append(f"missing native extension for sensitive module: {source_posix}")
    return tuple(sorted(set(problems)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Hardened release build.")
    parser.add_argument("--strip-sources", action="store_true",
                        help="delete .py of compiled modules (ship .pyd only)")
    parser.add_argument("--skip-pyinstaller", action="store_true")
    parser.add_argument("--sign", action="store_true", help="sign the Windows executable with signtool")
    parser.add_argument("--signtool", default=os.environ.get("SIGNTOOL", "signtool"))
    parser.add_argument("--cert-sha1", default=os.environ.get("SIGNTOOL_CERT_SHA1", ""))
    parser.add_argument("--timestamp-url", default=os.environ.get("SIGNTOOL_TIMESTAMP_URL", "http://timestamp.digicert.com"))
    args = parser.parse_args()

    run([PY, "scripts/build_lang.py"])
    run([PY, "scripts/build_pack.py", "--out", "dist/resources.dat"])
    run([PY, "scripts/build_cython.py", "build_ext", "--inplace"])

    if args.strip_sources:
        for rel in COMPILED_SOURCES:
            src = ROOT / rel
            pyd = list(src.parent.glob(src.stem + "*.pyd"))
            if not pyd:
                raise SystemExit(f"refusing to strip {rel}: no .pyd built")
            src.unlink()
            print(f"stripped source: {rel} (kept {pyd[0].name})")

    if not args.skip_pyinstaller:
        run([PY, "-m", "PyInstaller", "--noconfirm", "HorseRacingAudioFirst.spec"])
        leaks = audit_protected_release_tree(WINDOWS_DIST_DIR)
        if leaks:
            raise SystemExit("protected release contains plaintext resources: " + ", ".join(leaks))
        if args.strip_sources:
            code_leaks = audit_sensitive_code_tree(WINDOWS_DIST_DIR)
            if code_leaks:
                raise SystemExit("protected release contains readable sensitive code: " + ", ".join(code_leaks))
        if args.sign:
            if not WINDOWS_EXE.exists():
                raise SystemExit(f"cannot sign missing executable: {WINDOWS_EXE}")
            run(signtool_command(WINDOWS_EXE, cert_sha1=args.cert_sha1, timestamp_url=args.timestamp_url, signtool=args.signtool))
        manifest_path = emit_install_integrity_manifest(WINDOWS_DIST_DIR)
        print(f"wrote integrity manifest: {manifest_path.relative_to(ROOT)}")

    print("\nRelease build complete.")


if __name__ == "__main__":
    main()
