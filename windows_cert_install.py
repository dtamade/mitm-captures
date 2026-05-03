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
X509_ASN_ENCODING = 0x00000001
PKCS_7_ASN_ENCODING = 0x00010000
CERT_STORE_PROV_SYSTEM_REGISTRY_W = 13
CERT_SYSTEM_STORE_LOCATION_SHIFT = 16
CERT_SYSTEM_STORE_CURRENT_USER_ID = 1
CERT_SYSTEM_STORE_CURRENT_USER = CERT_SYSTEM_STORE_CURRENT_USER_ID << CERT_SYSTEM_STORE_LOCATION_SHIFT
CERT_SYSTEM_STORE_UNPROTECTED_FLAG = 0x40000000
CERT_STORE_ADD_REPLACE_EXISTING = 3


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
    cert_open_store = crypt32.CertOpenStore
    cert_open_store.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    cert_open_store.restype = ctypes.c_void_p

    cert_add = crypt32.CertAddEncodedCertificateToStore
    cert_add.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    cert_add.restype = wintypes.BOOL

    cert_close_store = crypt32.CertCloseStore
    cert_close_store.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    cert_close_store.restype = wintypes.BOOL

    store_name = ctypes.create_unicode_buffer("Root")
    store = cert_open_store(
        ctypes.c_void_p(CERT_STORE_PROV_SYSTEM_REGISTRY_W),
        0,
        None,
        CERT_SYSTEM_STORE_CURRENT_USER | CERT_SYSTEM_STORE_UNPROTECTED_FLAG,
        ctypes.cast(store_name, ctypes.c_void_p),
    )
    if not store:
        raise ctypes.WinError(ctypes.get_last_error())

    cert_buffer = (ctypes.c_ubyte * len(cert_bytes)).from_buffer_copy(cert_bytes)
    cert_context = ctypes.c_void_p()
    try:
        if not cert_add(
            store,
            X509_ASN_ENCODING | PKCS_7_ASN_ENCODING,
            cert_buffer,
            len(cert_bytes),
            CERT_STORE_ADD_REPLACE_EXISTING,
            ctypes.byref(cert_context),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        cert_close_store(store, 0)


def find_certmgr_executable() -> Path | None:
    direct = shutil.which("certmgr.exe")
    if direct:
        candidate = Path(direct)
        if candidate.suffix.lower() == ".exe":
            return candidate

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


def find_pwsh_executable() -> Path | None:
    direct = shutil.which("pwsh.exe") or shutil.which("pwsh")
    if not direct:
        return None
    return Path(direct)


def find_certutil_executable() -> Path | None:
    direct = shutil.which("certutil.exe") or shutil.which("certutil")
    if not direct:
        return None
    return Path(direct)


def install_with_certutil(cert_path: Path) -> None:
    certutil = find_certutil_executable()
    if certutil is None:
        raise RuntimeError("certutil.exe not found")

    print(f"[INFO] Using certutil executable: {certutil}", flush=True)
    completed = subprocess.run(
        [str(certutil), "-f", "-user", "-silent", "-addstore", "Root", str(cert_path)],
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
        raise RuntimeError(f"certutil addstore failed with exit code {completed.returncode}")


def install_with_pwsh_import(cert_path: Path) -> None:
    pwsh = find_pwsh_executable()
    if pwsh is None:
        raise RuntimeError("pwsh.exe not found")

    print(f"[INFO] Using pwsh executable: {pwsh}", flush=True)
    env = dict(os.environ)
    env["MITM_CERT"] = str(cert_path)
    completed = subprocess.run(
        [
            str(pwsh),
            "-NoProfile",
            "-Command",
            "$ErrorActionPreference = 'Stop'; Import-Certificate -FilePath $env:MITM_CERT -CertStoreLocation 'Cert:\\CurrentUser\\Root' | Out-Null",
        ],
        text=True,
        capture_output=True,
        errors="replace",
        timeout=DEFAULT_TIMEOUT_SECONDS,
        check=False,
        env=env,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"pwsh Import-Certificate failed with exit code {completed.returncode}")


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
    if strategy == "certutil-silent":
        install_with_certutil(cert_path)
        return
    if strategy == "crypt32-openstore":
        cert_bytes = load_certificate_bytes(cert_path)
        add_certificate_to_current_user_root(cert_bytes)
        return
    if strategy == "certmgr":
        install_with_certmgr(cert_path)
        return
    if strategy == "pwsh-import":
        install_with_pwsh_import(cert_path)
        return
    raise RuntimeError(f"unknown strategy: {strategy}")


def install_certificate(cert_path: Path) -> None:
    errors: list[str] = []
    for strategy in ("certutil-silent", "crypt32-openstore", "certmgr", "pwsh-import"):
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
    parser.add_argument("--strategy", choices=("certutil-silent", "crypt32-openstore", "certmgr", "pwsh-import"))
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
