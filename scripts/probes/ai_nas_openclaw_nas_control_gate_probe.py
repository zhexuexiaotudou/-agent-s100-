#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ai_nas_common import default_official_manager_url, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_openclaw_nas_control_gate"
OK = "ok_ai_nas_openclaw_nas_control_gate"
FAILED = "failed_ai_nas_openclaw_nas_control_gate"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return {"ok": False, "status": exc.code, "payload": parsed}
    except Exception as exc:
        return {"ok": False, "status": 0, "payload": {"error": f"{type(exc).__name__}:{exc}"}}


def http_text(url: str, timeout: int = 30) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "text": response.read().decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "status": 0, "text": "", "error": f"{type(exc).__name__}:{exc}"}


def wait_ready(base_url: str, proc: subprocess.Popen, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout
    last: dict[str, Any] = {}
    while time.perf_counter() < deadline:
        if proc.poll() is not None:
            return {"ok": False, "error": "server_exited", "returncode": proc.poll(), "last": last}
        last = http_json("GET", f"{base_url}/api/storage/status", timeout=3)
        if last.get("ok"):
            return last
        time.sleep(0.2)
    return {"ok": False, "error": "timeout", "last": last}


def check(label: str, cond: bool, failures: list[str], checks: list[dict[str, Any]]) -> None:
    checks.append({"label": label, "ok": bool(cond)})
    print(f"  {'PASS' if cond else 'FAIL'}: {label}")
    if not cond:
        failures.append(label)


class FakeOpenClawHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send({"ok": True, "model": "OpenClaw-Dream7B-S100P-local", "source": "fake_openclaw_nas_control_gate"})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", "0") or "0")
            _ = self.rfile.read(length)
            self._send({"model": "OpenClaw-Dream7B-S100P-local", "choices": [{"message": {"role": "assistant", "content": "OpenClaw normal chat response."}}]})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)


def start_fake_openclaw() -> tuple[ThreadingHTTPServer, str]:
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeOpenClawHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate for OpenClaw NAS file-control tool integration.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_openclaw_nas_control_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "openclaw_nas_control_gate")
    personal_root = run_dir / "Personal"
    for name in ["Movies", "Documents", "Photos", "Inbox"]:
        (personal_root / name).mkdir(parents=True, exist_ok=True)
    (personal_root / "Inbox" / "control.txt").write_text("control fixture\n", encoding="utf-8")
    (personal_root / "Photos" / "car_fixture.jpg").write_bytes(b"fake image")
    (personal_root / "Documents" / "secret.txt").write_text("private\n", encoding="utf-8")

    fake_openclaw, fake_openclaw_url = start_fake_openclaw()
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    server_script = Path(__file__).with_name("ai_nas_operator_portal_server.py")
    cmd = [
        sys.executable,
        str(server_script),
        "--bind", "127.0.0.1",
        "--port", str(port),
        "--report-root", str(run_dir),
        "--personal-root", str(personal_root),
        "--sqlite-index-path", str(run_dir / "personal_inventory.sqlite3"),
        "--identity-db-path", str(run_dir / "identity.sqlite3"),
        "--snapshot-db-path", str(run_dir / "snapshot.sqlite3"),
        "--backup-db-path", str(run_dir / "backup.sqlite3"),
        "--media-db-path", str(run_dir / "media.sqlite3"),
        "--ops-db-path", str(run_dir / "ops.sqlite3"),
        "--app-db-path", str(run_dir / "apps.sqlite3"),
        "--official-manager-url", default_official_manager_url(),
        "--openclaw-gateway-url", fake_openclaw_url,
        "--openclaw-model-gateway-url", fake_openclaw_url,
        "--qwen-gateway-url", fake_openclaw_url,
        "--nas-portal",
        "--no-refresh",
    ]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    stdout = ""
    stderr = ""
    try:
        print("OpenClaw NAS Control Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)

        html = http_text(base_url + "/")
        check("Portal renders NAS action cards", html.get("ok") and "renderNasAction" in html.get("text", "") and "nas_action" in html.get("text", ""), failures, checks)

        admin_create = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        admin_login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        admin_token = (admin_login.get("payload") or {}).get("token")
        check("Admin login", admin_create.get("ok") and admin_login.get("ok") and bool(admin_token), failures, checks)

        list_chat = http_json("POST", base_url + "/api/copilot/chat", {"message": '列出 "Inbox"', "type": "all", "limit": 10}, token=admin_token)
        list_action = (list_chat.get("payload") or {}).get("nas_action") or {}
        check("OpenClaw chat lists NAS directory", list_chat.get("ok") and list_action.get("operation") == "list" and any(item.get("name") == "control.txt" for item in list_action.get("entries") or []), failures, checks)

        rename_chat = http_json("POST", base_url + "/api/copilot/chat", {"message": '把 "Inbox/control.txt" 重命名为 "renamed_control.txt"', "type": "all", "limit": 10}, token=admin_token)
        rename_action = (rename_chat.get("payload") or {}).get("nas_action") or {}
        check("OpenClaw chat renames NAS file", rename_chat.get("ok") and rename_action.get("status") == "completed" and (personal_root / "Inbox" / "renamed_control.txt").exists(), failures, checks)

        copy_chat = http_json("POST", base_url + "/api/copilot/chat", {"message": '复制 "Inbox/renamed_control.txt" 到 "Documents/copied_control.txt"', "type": "all", "limit": 10}, token=admin_token)
        copy_action = (copy_chat.get("payload") or {}).get("nas_action") or {}
        check("OpenClaw chat copies NAS file", copy_chat.get("ok") and copy_action.get("status") == "completed" and (personal_root / "Documents" / "copied_control.txt").exists(), failures, checks)

        delete_chat = http_json("POST", base_url + "/api/copilot/chat", {"message": '删除 "Inbox/renamed_control.txt"', "type": "all", "limit": 10}, token=admin_token)
        delete_action = (delete_chat.get("payload") or {}).get("nas_action") or {}
        check("OpenClaw chat requires confirmation for delete", delete_chat.get("ok") and delete_action.get("status") == "confirmation_required" and (personal_root / "Inbox" / "renamed_control.txt").exists(), failures, checks)

        viewer_create = http_json("POST", base_url + "/api/identity/create-user", {"username": "viewer", "password": "viewer123", "role": "user"}, token=admin_token)
        acl = http_json("POST", base_url + "/api/identity/set-acl", {"path": "Photos", "principal_type": "user", "principal_name": "viewer", "permission": "read"}, token=admin_token)
        viewer_login = http_json("POST", base_url + "/api/identity/login", {"username": "viewer", "password": "viewer123"})
        viewer_token = (viewer_login.get("payload") or {}).get("token")
        check("Viewer read-only setup", viewer_create.get("ok") and acl.get("ok") and bool(viewer_token), failures, checks)

        denied_chat = http_json("POST", base_url + "/api/copilot/chat", {"message": '复制 "Photos/car_fixture.jpg" 到 "Documents/copied.jpg"', "type": "all", "limit": 10}, token=viewer_token)
        denied_action = (denied_chat.get("payload") or {}).get("nas_action") or {}
        check("OpenClaw chat respects ACL on copy target", denied_chat.get("ok") and denied_action.get("status") == "permission_denied" and not (personal_root / "Documents" / "copied.jpg").exists(), failures, checks)

        denied_api = http_json("POST", base_url + "/api/storage/rename", {"path": "Photos/car_fixture.jpg", "new_name": "renamed.jpg"}, token=viewer_token)
        check("Direct storage mutation route respects ACL", denied_api.get("status") == 403, failures, checks)

        artifacts = {
            "base_url": base_url,
            "list_action": list_action,
            "rename_action": rename_action,
            "copy_action": copy_action,
            "delete_action": delete_action,
            "denied_action": denied_action,
            "denied_api": denied_api,
        }
    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=10)
        fake_openclaw.shutdown()
        fake_openclaw.server_close()

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "scope": "OpenClaw as a NAS assistant with ordinary chat plus ACL-aware file control tools",
        "checks": checks,
        "passed_count": sum(1 for item in checks if item.get("ok")),
        "check_count": len(checks),
        "failures": failures,
        "artifacts": artifacts,
        "server": {"stdout_tail": (stdout or "")[-2000:], "stderr_tail": (stderr or "")[-4000:]},
    }
    safe_write_json(run_dir / "openclaw_nas_control_gate.json", payload)
    safe_write_json(args.report_root / "openclaw_nas_control_gate_latest.json", payload)
    lines = [
        "# OpenClaw NAS Control Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- passed: `{payload['passed_count']}/{payload['check_count']}`",
    ]
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{item}`" for item in failures)
    safe_write_text(run_dir / "openclaw_nas_control_gate.md", "\n".join(lines) + "\n")
    safe_write_text(args.report_root / "openclaw_nas_control_gate_latest.md", "\n".join(lines) + "\n")
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {payload['passed_count']}/{payload['check_count']}")
    if failures:
        for item in failures:
            print(f"    - {item}")
    print(f"{'='*60}")
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
