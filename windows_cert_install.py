from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys

DEFAULT_TIMEOUT_SECONDS = 20


def load_certificate_bytes(cert_path: Path) -> bytes:
    raw = cert_path.read_bytes()
    stripped = raw.lstrip()
    if stripped.startswith(b"-----BEGIN CERTIFICATE-----"):
        return ssl.PEM_cert_to_DER_cert(raw.decode("ascii"))
    return raw


def add_certificate_to_current_user_root(cert_bytes: bytes) -> None:
    if sys.platform != "win32":
        raise RuntimeError("windows_cert_install.py can only run on Windows")
    if not cert_bytes:
        raise RuntimeError("certificate file is empty")

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    add_cert = crypt32.CertAddEncodedCertificateToSystemStoreA
    add_cert.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ubyte), wintypes.DWORD]
    add_cert.restype = wintypes.BOOL

    cert_buffer = (ctypes.c_ubyte * len(cert_bytes)).from_buffer_copy(cert_bytes)
    if not add_cert(b"ROOT", cert_buffer, len(cert_bytes)):
        raise ctypes.WinError(ctypes.get_last_error())


def find_certmgr_executable() -> Path | None:
    direct = shutil.which("certmgr.exe") or shutil.which("certmgr")
    if direct:
        return Path(direct)

    for root_name in ("ProgramFiles(x86)", "ProgramFiles"):
        root = os.environ.get(root_name)
        if not root:
            continue
        base = Path(root)
        for pattern in (
            "Windows Kits/10/bin/*/x64/certmgr.exe",
            "Windows Kits/10/bin/*/x86/certmgr.exe",
            "Windows Kits/10/bin/*/arm64/certmgr.exe",
        ):
            matches = sorted(base.glob(pattern), reverse=True)
            if matches:
                return matches[0]
    return None


def install_with_certmgr(cert_path: Path) -> None:
    certmgr = find_certmgr_executable()
    if certmgr is None:
        raise RuntimeError("CertMgr.exe not found")

    print(f"[INFO] Using CertMgr executable: {certmgr}", flush=True)
    completed = subprocess.run(
        [str(certmgr), "/add", str(cert_path), "/s", "/r", "currentUser", "root"],
        text=True,
        capture_output=True,
        errors="replace",
        timeout=DEFAULT_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"CertMgr.exe failed with exit code {completed.returncode}")


def run_strategy_subprocess(strategy: str, cert_path: Path) -> tuple[int, str, str]:
    completed = subprocess.run(
        [sys.executable, __file__, "--strategy", strategy, str(cert_path)],
        text=True,
        capture_output=True,
        errors="replace",
        timeout=DEFAULT_TIMEOUT_SECONDS,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def run_single_strategy(strategy: str, cert_path: Path) -> None:
    if strategy == "certmgr":
        install_with_certmgr(cert_path)
        return
    if strategy == "crypt32":
        cert_bytes = load_certificate_bytes(cert_path)
        add_certificate_to_current_user_root(cert_bytes)
        return
    raise RuntimeError(f"unknown strategy: {strategy}")


def install_certificate(cert_path: Path) -> None:
    errors: list[str] = []
    for strategy in ("certmgr", "crypt32"):
        print(f"[INFO] Trying certificate import strategy: {strategy}", flush=True)
        try:
            returncode, stdout, stderr = run_strategy_subprocess(strategy, cert_path)
        except subprocess.TimeoutExpired:
            errors.append(f"{strategy}: timed out after {DEFAULT_TIMEOUT_SECONDS}s")
            continue
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        if returncode == 0:
            print(f"[INFO] Certificate import strategy succeeded: {strategy}", flush=True)
            return
        errors.append(f"{strategy}: exited with code {returncode}")
    raise RuntimeError("; ".join(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a certificate into the Windows current-user Root store.")
    parser.add_argument("--strategy", choices=("certmgr", "crypt32"))
    parser.add_argument("certificate", help="Path to a DER or PEM encoded certificate file.")
    args = parser.parse_args(argv)

    cert_path = Path(args.certificate)
    if not cert_path.is_file():
        print(f"[ERROR] Missing certificate file: {cert_path}", file=sys.stderr)
        return 1

    try:
        if args.strategy:
            run_single_strategy(args.strategy, cert_path)
        else:
            install_certificate(cert_path)
    except Exception as exc:
        print(f"[ERROR] Failed to import certificate: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Imported certificate into CurrentUser Root: {cert_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
