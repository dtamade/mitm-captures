from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import ssl
import sys


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a certificate into the Windows current-user Root store.")
    parser.add_argument("certificate", help="Path to a DER or PEM encoded certificate file.")
    args = parser.parse_args(argv)

    cert_path = Path(args.certificate)
    if not cert_path.is_file():
        print(f"[ERROR] Missing certificate file: {cert_path}", file=sys.stderr)
        return 1

    try:
        cert_bytes = load_certificate_bytes(cert_path)
        add_certificate_to_current_user_root(cert_bytes)
    except Exception as exc:
        print(f"[ERROR] Failed to import certificate: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Imported certificate into CurrentUser Root: {cert_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
