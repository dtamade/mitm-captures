#!/usr/bin/env python3
"""Convert a trusted capture state env file into a cmd.exe import file."""

from __future__ import annotations

import locale
import os
import sys
from pathlib import Path


ALLOWED_STATE_KEYS = {
    "MITM_PID",
    "PROGRAM_MODE",
    "TARGET_DIR",
    "CAPTURES_DIR",
    "RUN_ID",
    "FLOW_FILE",
    "HAR_FILE",
    "LOG_FILE",
    "MANIFEST_FILE",
    "INDEX_FILE",
    "SUMMARY_FILE",
    "AI_JSON_FILE",
    "AI_MD_FILE",
    "BUNDLE_FILE",
    "LISTEN_HOST",
    "LISTEN_PORT",
    "STARTED_AT",
    "PREV_PROXY_ENABLE",
    "PREV_PROXY_SERVER",
    "PREV_PROXY_OVERRIDE",
    "WINHTTP_DUMP_FILE",
    "WINHTTP_SNAPSHOT_STATUS",
    "START_LATEST_FLOW_BACKUP_FILE",
    "START_LATEST_HAR_BACKUP_FILE",
    "START_LATEST_LOG_BACKUP_FILE",
    "START_LATEST_INDEX_BACKUP_FILE",
    "START_LATEST_SUMMARY_BACKUP_FILE",
    "START_LATEST_AI_JSON_BACKUP_FILE",
    "START_LATEST_AI_MD_BACKUP_FILE",
    "START_LATEST_AI_BUNDLE_BACKUP_FILE",
}


def read_state_text(path: Path) -> str:
    data = path.read_bytes()
    encodings = ["utf-8-sig", "utf-8"]
    if os.name == "nt":
        encodings.extend(["oem", "mbcs", locale.getpreferredencoding(False)])

    last_error: UnicodeDecodeError | LookupError | None = None
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
    raise UnicodeError(f"Could not decode state file {path}: {last_error}")


def cmd_import_lines(state_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in state_text.splitlines():
        key, separator, value = raw_line.partition("=")
        if not separator or not key:
            continue
        if key not in ALLOWED_STATE_KEYS:
            raise ValueError(f"Unexpected state key: {key}")
        lines.append(f'set "{key}={value.replace("%", "%%")}"')
    return lines


def write_cmd_import(path: Path, lines: list[str]) -> None:
    encoding = "utf-8"
    if os.name == "nt":
        encoding = "oem"
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding=encoding)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: state_import.py <state-env-file> <cmd-import-file>", file=sys.stderr)
        return 2

    state_file = Path(argv[1])
    import_file = Path(argv[2])

    try:
        write_cmd_import(import_file, cmd_import_lines(read_state_text(state_file)))
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
