#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import http.server
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Sequence


EXPECTED_PATH = "/ci-smoke?answer=42"


class SmokeHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, SmokeRequestHandler)
        self.received_paths: list[str] = []


class SmokeRequestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"ok": True, "path": self.path}).encode("utf-8")
        self.server.received_paths.append(self.path)  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real mitm-captures smoke test.")
    parser.add_argument("--entrypoint", choices=("shell", "windows"), required=True)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    return parser.parse_args()


def quote_for_log(arg: str) -> str:
    if not arg or any(ch.isspace() for ch in arg):
        return json.dumps(arg)
    return arg


def format_command(cmd: Sequence[str] | str) -> str:
    if isinstance(cmd, str):
        return cmd
    return " ".join(quote_for_log(part) for part in cmd)


def build_windows_cmd(batch: Path, args: Sequence[str]) -> list[str]:
    return [
        "cmd.exe",
        "/d",
        "/s",
        "/c",
        "call " + subprocess.list2cmdline([str(batch), *args]),
    ]


def run_command(cmd: Sequence[str] | str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    print("$", format_command(cmd), flush=True)
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=isinstance(cmd, str),
        text=True,
        capture_output=True,
        timeout=timeout,
        errors="replace",
    )
    if completed.stdout:
        print(completed.stdout, end="", flush=True)
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr, flush=True)
    return completed


def run_checked(cmd: Sequence[str] | str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    completed = run_command(cmd, cwd=cwd, timeout=timeout)
    if completed.returncode != 0:
        raise AssertionError(f"command failed with exit code {completed.returncode}: {format_command(cmd)}")
    return completed


def run_stop_checked(cmd: Sequence[str] | str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    completed = run_command(cmd, cwd=cwd, timeout=timeout)
    if completed.returncode == 0:
        return completed

    combined = f"{completed.stdout}\n{completed.stderr}"
    if "Another capture operation is running. Please retry." not in combined:
        raise AssertionError(f"command failed with exit code {completed.returncode}: {format_command(cmd)}")

    time.sleep(2.0)
    completed = run_command(cmd, cwd=cwd, timeout=timeout)
    if completed.returncode != 0:
        raise AssertionError(f"command failed with exit code {completed.returncode}: {format_command(cmd)}")
    return completed


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def make_request_via_proxy(proxy_port: int, upstream_port: int) -> dict[str, object]:
    conn = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=15)
    try:
        conn.request("GET", f"http://127.0.0.1:{upstream_port}{EXPECTED_PATH}", headers={"Connection": "close"})
        response = conn.getresponse()
        body = response.read().decode("utf-8")
    finally:
        conn.close()
    if response.status != 200:
        raise AssertionError(f"unexpected upstream status via proxy: {response.status}")
    payload = json.loads(body)
    if payload.get("path") != EXPECTED_PATH:
        raise AssertionError(f"unexpected upstream payload path: {payload!r}")
    return payload


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def read_json(path: Path) -> dict[str, object]:
    return json.loads(read_text(path))


def shell_commands(repo_root: Path, target_dir: Path, proxy_port: int) -> dict[str, list[str]]:
    return {
        "start": [
            "bash",
            str(repo_root / "startCaptures.sh"),
            "--program",
            "--dir",
            str(target_dir),
            "--host",
            "127.0.0.1",
            "--port",
            str(proxy_port),
        ],
        "stop": [
            "bash",
            str(repo_root / "stopCaptures.sh"),
            "--dir",
            str(target_dir),
        ],
        "ai": [
            "bash",
            str(repo_root / "ai.sh"),
            "--dir",
            str(target_dir),
            "--stdout",
        ],
    }


def windows_commands(repo_root: Path, target_dir: Path, proxy_port: int) -> dict[str, list[str]]:
    batch = repo_root / "mitm-captures.bat"
    return {
        "start": build_windows_cmd(
            batch,
            [
                "start",
                "--program",
                "--dir",
                str(target_dir),
                "--host",
                "127.0.0.1",
                "--port",
                str(proxy_port),
            ],
        ),
        "status": build_windows_cmd(batch, ["status", "--dir", str(target_dir)]),
        "stop": build_windows_cmd(batch, ["stop", "--dir", str(target_dir)]),
        "ai": build_windows_cmd(batch, ["ai", "--dir", str(target_dir), "--stdout"]),
    }


def assert_artifacts(target_dir: Path, bundle_output: str) -> None:
    captures_dir = target_dir / "captures"
    required_files = [
        captures_dir / "latest.flow",
        captures_dir / "latest.har",
        captures_dir / "latest.log",
        captures_dir / "latest.manifest.json",
        captures_dir / "latest.index.ndjson",
        captures_dir / "latest.summary.md",
        captures_dir / "latest.ai.json",
        captures_dir / "latest.ai.md",
        captures_dir / "latest.ai.bundle.txt",
    ]
    for path in required_files:
        if not path.exists():
            raise AssertionError(f"missing artifact: {path}")
        if path.name != "latest.log" and path.stat().st_size <= 0:
            raise AssertionError(f"empty artifact: {path}")

    if (captures_dir / "proxy_info.env").exists():
        raise AssertionError("proxy_info.env should be removed after a successful stop")

    manifest = read_json(captures_dir / "latest.manifest.json")
    if manifest.get("programMode") is not True:
        raise AssertionError(f"manifest should record programMode=true: {manifest}")
    if not manifest.get("stoppedAt"):
        raise AssertionError(f"manifest should record stoppedAt: {manifest}")
    raw_policy = manifest.get("rawDataPolicy")
    if not isinstance(raw_policy, dict) or raw_policy.get("immutable") is not True:
        raise AssertionError(f"manifest missing immutable rawDataPolicy: {manifest}")

    index_text = read_text(captures_dir / "latest.index.ndjson")
    if "/ci-smoke" not in index_text:
        raise AssertionError("latest.index.ndjson did not capture the smoke request path")

    summary_text = read_text(captures_dir / "latest.summary.md")
    if "127.0.0.1" not in summary_text:
        raise AssertionError("latest.summary.md did not include the local smoke host")

    ai_bundle_text = read_text(captures_dir / "latest.ai.bundle.txt")
    if "# AI Analysis Bundle" not in ai_bundle_text:
        raise AssertionError("latest.ai.bundle.txt missing AI bundle header")
    if "/ci-smoke" not in ai_bundle_text and "/ci-smoke" not in bundle_output:
        raise AssertionError("AI bundle output did not include the captured smoke path")

    ai_json = read_json(captures_dir / "latest.ai.json")
    capture_info = ai_json.get("capture")
    if not isinstance(capture_info, dict) or not capture_info.get("stoppedAt"):
        raise AssertionError(f"latest.ai.json should record capture.stoppedAt: {ai_json}")
    file_info = ai_json.get("files")
    if not isinstance(file_info, dict) or not file_info.get("manifest"):
        raise AssertionError(f"latest.ai.json should include manifest path: {ai_json}")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    proxy_port = pick_free_port()
    server = SmokeHTTPServer(("127.0.0.1", 0))
    server_port = int(server.server_address[1])
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    commands = (
        shell_commands(repo_root, Path("unused"), proxy_port)
        if args.entrypoint == "shell"
        else windows_commands(repo_root, Path("unused"), proxy_port)
    )

    started = False
    with tempfile.TemporaryDirectory(prefix="mitm-captures-smoke-", dir=repo_root) as temp_dir:
        target_dir = Path(temp_dir).resolve()
        commands = (
            shell_commands(repo_root, target_dir, proxy_port)
            if args.entrypoint == "shell"
            else windows_commands(repo_root, target_dir, proxy_port)
        )
        try:
            start_result = run_checked(commands["start"], cwd=repo_root)
            if "mitmproxy capture started" not in start_result.stdout.lower():
                raise AssertionError("start command did not report a started capture")
            started = True

            if args.entrypoint == "windows":
                status_result = run_checked(commands["status"], cwd=repo_root)
                if "Running:         yes" not in status_result.stdout:
                    raise AssertionError("windows status command did not report Running: yes")

            make_request_via_proxy(proxy_port, server_port)
            time.sleep(1.0)

            stop_result = run_stop_checked(commands["stop"], cwd=repo_root)
            started = False
            if "mitmproxy capture stop" not in stop_result.stdout.lower():
                raise AssertionError("stop command did not report a stop summary")

            bundle_result = run_checked(commands["ai"], cwd=repo_root)
            if "# AI Analysis Bundle" not in bundle_result.stdout:
                raise AssertionError("ai command did not emit the AI bundle")

            if EXPECTED_PATH not in server.received_paths:
                raise AssertionError(f"upstream server did not observe expected path: {server.received_paths!r}")

            assert_artifacts(target_dir, bundle_result.stdout)
        finally:
            if started:
                try:
                    run_stop_checked(commands["stop"], cwd=repo_root, timeout=180)
                except Exception as exc:  # pragma: no cover - best effort cleanup
                    print(f"[WARN] cleanup stop failed: {exc}", file=sys.stderr, flush=True)
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)

    print("runtime smoke test passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
