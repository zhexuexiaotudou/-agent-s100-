#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
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

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_settings_portal_gate"
OK = "ok_ai_nas_settings_portal_gate"
FAILED = "failed_ai_nas_settings_portal_gate"


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


def check(label: str, cond: bool, failures: list[str], checks: list[dict[str, Any]], evidence: dict[str, Any] | None = None) -> None:
    item = {"label": label, "ok": bool(cond)}
    if evidence:
        item["evidence"] = evidence
    checks.append(item)
    print(f"  {'PASS' if cond else 'FAIL'}: {label}")
    if not cond:
        failures.append(label)


class FakeModelHandler(BaseHTTPRequestHandler):
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
            self._send({"ok": True, "model": "Qwen2.5-1.5B-Instruct-S100P-official", "source": "settings_gate_fake_model"})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", "0") or "0")
            _ = self.rfile.read(length)
            self._send({"model": "Qwen2.5-1.5B-Instruct-S100P-official", "choices": [{"message": {"role": "assistant", "content": "Settings route ready."}}]})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)


def start_fake_model() -> tuple[ThreadingHTTPServer, str]:
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def seed_personal(root: Path) -> None:
    for name in ["Movies", "Documents", "Photos", "Inbox", "Music"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "Documents" / "settings_invoice.txt").write_text("settings portal fixture\n", encoding="utf-8")
    (root / "Movies" / "settings_demo.mp4").write_bytes(b"fake-settings-video")
    (root / "Music" / "settings_theme.mp3").write_bytes(b"fake-settings-audio")
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    (root / "Photos" / "settings_photo.png").write_bytes(png)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate for the OpenClaw NAS settings portal.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_settings_portal_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "settings_portal_gate")
    personal_root = run_dir / "Personal"
    seed_personal(personal_root)
    fake_model, fake_model_url = start_fake_model()
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    server_script = Path(__file__).with_name("ai_nas_operator_portal_server.py")
    cmd = [
        sys.executable,
        str(server_script),
        "--bind",
        "127.0.0.1",
        "--port",
        str(port),
        "--report-root",
        str(run_dir),
        "--personal-root",
        str(personal_root),
        "--sqlite-index-path",
        str(run_dir / "personal_inventory.sqlite3"),
        "--identity-db-path",
        str(run_dir / "identity.sqlite3"),
        "--snapshot-db-path",
        str(run_dir / "snapshot.sqlite3"),
        "--backup-db-path",
        str(run_dir / "backup.sqlite3"),
        "--media-db-path",
        str(run_dir / "media.sqlite3"),
        "--ops-db-path",
        str(run_dir / "ops.sqlite3"),
        "--app-db-path",
        str(run_dir / "apps.sqlite3"),
        "--schedule-db-path",
        str(run_dir / "schedule.sqlite3"),
        "--official-manager-url",
        "http://nas.local:8080/",
        "--qwen-gateway-url",
        fake_model_url,
        "--openclaw-gateway-url",
        fake_model_url,
        "--openclaw-model-gateway-url",
        fake_model_url,
        "--nas-portal",
        "--no-refresh",
    ]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    stdout = ""
    stderr = ""
    collected: dict[str, Any] = {"base_url": base_url, "run_dir": str(run_dir)}
    try:
        print("OpenClaw NAS Settings Portal Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)

        html = http_text(base_url + "/")
        text = html.get("text", "")
        check(
            "Settings UI is present in portal HTML",
            html.get("ok")
            and "sec-settings" in text
            and "settingsPanel" in text
            and "settings-go" in text
            and "loadSettings" in text
            and "settingsIndexVision" in text
            and "settingsIndexMedia" in text,
            failures,
            checks,
        )
        check(
            "Settings navigation is safe without a sidebar anchor",
            "settings:loadSettings" in text and "let nav=document.querySelector('[data-sec='+n+']');if(nav)nav.classList.add('active')" in text,
            failures,
            checks,
        )

        admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        check("Admin bootstrap", admin.get("ok") and admin.get("payload", {}).get("ok"), failures, checks)
        login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        token = (login.get("payload") or {}).get("token")
        check("Admin login", login.get("ok") and bool(token), failures, checks)

        endpoints = [
            "/api/portal/config",
            "/api/identity/session",
            "/api/identity/users",
            "/api/identity/groups",
            "/api/identity/acls",
            "/api/storage/status",
            "/api/storage/insights",
            "/api/backup/summary",
            "/api/schedule/summary",
            "/api/media/summary",
            "/api/ops/summary",
            "/api/apps/summary",
            "/api/audit/summary",
            "/api/services",
            "/api/vision/status",
        ]
        endpoint_results = {path: http_json("GET", base_url + path, token=token) for path in endpoints}
        for path, result in endpoint_results.items():
            check(f"Settings data endpoint {path}", result.get("ok") and result.get("payload", {}).get("ok", True) is not False, failures, checks)
        collected["endpoint_results"] = {path: {"ok": result.get("ok"), "status": result.get("status")} for path, result in endpoint_results.items()}

        config = endpoint_results["/api/portal/config"].get("payload") or {}
        check(
            "Settings reflects official manager and model route",
            config.get("official_manager_configured")
            and config.get("chat_primary_route") == "qwen25_official_primary"
            and (config.get("features") or {}).get("copilot_nas_file_control"),
            failures,
            checks,
        )

        health = http_json("POST", base_url + "/api/ops/health-check", {"service_name": "ai-nas-web-os"}, token=token)
        check("Settings health-check action works", health.get("ok") and health.get("payload", {}).get("ok"), failures, checks)
        media_index = http_json("POST", base_url + "/api/media/index", {"path": ""}, token=token)
        media_after_index = http_json("GET", base_url + "/api/media/summary", token=token)
        media_stats = (media_after_index.get("payload") or {}).get("stats") or {}
        check(
            "Settings media-index action works",
            media_index.get("ok")
            and media_after_index.get("ok")
            and media_stats.get("photo_count", 0) >= 1
            and media_stats.get("video_count", 0) >= 1,
            failures,
            checks,
            {"media_stats": media_stats, "index_status": media_index.get("status")},
        )

        insights = http_json("GET", base_url + "/api/storage/insights", token=token)
        visible = (insights.get("payload") or {}).get("visible") or {}
        by_type = (insights.get("payload") or {}).get("by_type") or []
        check(
            "Settings storage card has real fixture data",
            insights.get("ok") and visible.get("file_count", 0) >= 4 and any(row.get("key") == "image" for row in by_type),
            failures,
            checks,
            {"visible": visible, "types": [row.get("key") for row in by_type]},
        )

    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=10)
        fake_model.shutdown()
        fake_model.server_close()

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "scope": "OpenClaw NAS settings entry, settings page rendering hooks, and real settings API/action coverage",
        "checks": checks,
        "failures": failures,
        "collected": collected,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }
    safe_write_json(run_dir / "settings_portal_gate.json", payload)
    safe_write_text(run_dir / "settings_portal_gate.summary.txt", json.dumps(payload, ensure_ascii=False, indent=2))
    print(verdict)
    print(run_dir / "settings_portal_gate.json")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
