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
from urllib.parse import urlencode
from typing import Any

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_integrated_portal_gate"
OK = "ok_nas_integrated_portal_gate"
FAILED = "failed_nas_integrated_portal_gate"


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


def http_bytes(url: str, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    headers = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "headers": dict(response.headers.items()),
                "body": response.read(),
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "headers": dict(exc.headers.items()), "body": exc.read()}
    except Exception as exc:
        return {"ok": False, "status": 0, "headers": {}, "body": f"{type(exc).__name__}:{exc}".encode("utf-8")}


def multipart_upload(url: str, field_name: str, filename: str, data: bytes, token: str) -> dict[str, Any]:
    boundary = "----openclawgateboundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return {"ok": False, "status": exc.code, "payload": parsed}


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
            self._send({"ok": True, "model": "OpenClaw-Dream7B-S100P-local", "source": "fake_openclaw_gate"})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", "0") or "0")
            _ = self.rfile.read(length)
            self._send({"model": "OpenClaw-Dream7B-S100P-local", "choices": [{"message": {"role": "assistant", "content": "OpenClaw route answered through the integrated portal."}}]})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)


def start_fake_openclaw() -> tuple[ThreadingHTTPServer, str]:
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeOpenClawHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Integrated OpenClaw NAS portal gate.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_integrated_portal_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "integrated_portal_gate")
    personal_root = run_dir / "Personal"
    for name in ["Movies", "Documents", "Photos", "Inbox"]:
        (personal_root / name).mkdir(parents=True, exist_ok=True)
    (personal_root / "Documents" / "secret_invoice.txt").write_text("private invoice fixture\n", encoding="utf-8")
    (personal_root / "Photos" / "car_fixture.jpg").write_bytes(b"fake-jpg-car-fixture")
    (personal_root / "Photos" / "meal_fixture.png").write_bytes(b"fake-png-meal-fixture")
    (personal_root / "Movies" / "frame_sample.mp4").write_bytes(b"fake-video-frame-fixture")

    fake_openclaw, fake_openclaw_url = start_fake_openclaw()
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
        "--official-manager-url",
        "http://nas.local:8080/",
        "--openclaw-gateway-url",
        fake_openclaw_url,
        "--openclaw-model-gateway-url",
        fake_openclaw_url,
        "--qwen-gateway-url",
        fake_openclaw_url,
        "--nas-portal",
        "--no-refresh",
    ]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    stdout = ""
    stderr = ""
    try:
        print("OpenClaw NAS Integrated Portal Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)

        html = http_text(base_url + "/")
        text = html.get("text", "")
        check("Integrated workbench served", html.get("ok") and "Official NAS Manager" in text and "AI Copilot" in text and "Upload files" in text, failures, checks)

        create_admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        check("Admin bootstrap", create_admin.get("ok") and create_admin.get("payload", {}).get("ok"), failures, checks)
        admin_login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        admin_token = (admin_login.get("payload") or {}).get("token")
        check("Admin login", admin_login.get("ok") and bool(admin_token), failures, checks)

        config = http_json("GET", base_url + "/api/portal/config", token=admin_token)
        config_payload = config.get("payload", {}) or {}
        check(
            "Portal config API",
            config.get("ok")
            and config_payload.get("official_manager_configured")
            and (config_payload.get("qwen_health") or {}).get("ok")
            and config_payload.get("chat_primary_route") == "qwen25_official_primary",
            failures,
            checks,
        )

        index_media = http_json("POST", base_url + "/api/media/index", {"path": ""}, token=admin_token)
        check("Media index for search fixtures", index_media.get("ok") and (index_media.get("payload", {}).get("index") or {}).get("scanned", 0) >= 3, failures, checks)

        chat = http_json("POST", base_url + "/api/copilot/chat", {"message": "find image", "type": "all", "limit": 8}, token=admin_token)
        chat_results = (chat.get("payload") or {}).get("results") or []
        check("Copilot chat uses official Qwen route", chat.get("ok") and ((chat.get("payload", {}).get("upstream") or {}).get("name") == "qwen25_official_primary"), failures, checks)
        check("Copilot chat attaches image links", any(item.get("type") == "image" and item.get("open_url") for item in chat_results), failures, checks)

        general_chat = http_json("POST", base_url + "/api/copilot/chat", {"message": "今天天气怎么样", "type": "all", "limit": 8}, token=admin_token)
        general_payload = general_chat.get("payload") or {}
        check(
            "General chat does not attach NAS files",
            general_chat.get("ok")
            and not (general_payload.get("results") or [])
            and not (general_payload.get("vision_results") or [])
            and general_payload.get("attachments_enabled") is False,
            failures,
            checks,
        )

        video_search = http_json("GET", base_url + "/api/copilot/search?" + urlencode({"query": "video", "type": "all", "limit": "10"}), token=admin_token)
        check("Copilot search returns videos", video_search.get("ok") and any(item.get("type") == "video" for item in (video_search.get("payload") or {}).get("results") or []), failures, checks)

        upload = multipart_upload(base_url + "/api/storage/upload?path=Inbox", "file", "portal_upload.txt", b"uploaded through portal gate", admin_token)
        check("Authorized upload API", upload.get("ok") and (upload.get("payload", {}).get("file") or {}).get("relative_path") == "Inbox/portal_upload.txt", failures, checks)
        upload_search = http_json("GET", base_url + "/api/copilot/search?query=portal_upload&type=file&limit=5", token=admin_token)
        check("Uploaded file searchable", upload_search.get("ok") and any(item.get("relative_path") == "Inbox/portal_upload.txt" for item in (upload_search.get("payload") or {}).get("results") or []), failures, checks)

        create_user = http_json("POST", base_url + "/api/identity/create-user", {"username": "viewer", "password": "viewer123", "role": "user"}, token=admin_token)
        check("Low-privilege user created", create_user.get("ok") and create_user.get("payload", {}).get("ok"), failures, checks)
        acl = http_json("POST", base_url + "/api/identity/set-acl", {"path": "Photos", "principal_type": "user", "principal_name": "viewer", "permission": "read"}, token=admin_token)
        check("Viewer read ACL configured", acl.get("ok") and acl.get("payload", {}).get("ok"), failures, checks)
        viewer_login = http_json("POST", base_url + "/api/identity/login", {"username": "viewer", "password": "viewer123"})
        viewer_token = (viewer_login.get("payload") or {}).get("token")
        check("Viewer login", viewer_login.get("ok") and bool(viewer_token), failures, checks)
        viewer_images = http_json("GET", base_url + "/api/copilot/search?" + urlencode({"query": "image", "type": "all", "limit": "10"}), token=viewer_token)
        viewer_paths = [item.get("relative_path") for item in (viewer_images.get("payload") or {}).get("results") or []]
        check("Viewer sees authorized photos", viewer_images.get("ok") and any(str(path).startswith("Photos/") for path in viewer_paths), failures, checks)
        viewer_private = http_json("GET", base_url + "/api/copilot/search?query=secret&type=file&limit=10", token=viewer_token)
        private_paths = [item.get("relative_path") for item in (viewer_private.get("payload") or {}).get("results") or []]
        check("Viewer search does not leak private documents", viewer_private.get("ok") and not any(str(path).startswith("Documents/") for path in private_paths), failures, checks)
        denied_download = http_bytes(base_url + "/api/storage/download?path=Documents/secret_invoice.txt", token=viewer_token)
        check("Viewer cannot download unauthorized file", denied_download.get("status") == 403, failures, checks)
        preview = http_bytes(base_url + f"/api/storage/download?path=Photos/car_fixture.jpg&preview=1&token={viewer_token}")
        check("Token-authenticated preview works", preview.get("ok") and "inline" in (preview.get("headers", {}).get("Content-Disposition") or ""), failures, checks)
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
        "scope": "OpenClaw NAS integrated portal: official manager config, OpenClaw proxy chat, authorized search links, upload, and ACL boundaries",
        "base_url": base_url,
        "openclaw_gateway_url": fake_openclaw_url,
        "server_command": cmd,
        "checks": checks,
        "passed_count": sum(1 for item in checks if item.get("ok")),
        "check_count": len(checks),
        "failures": failures,
        "server": {"stdout_tail": (stdout or "")[-2000:], "stderr_tail": (stderr or "")[-4000:]},
    }
    safe_write_json(run_dir / "integrated_portal_gate.json", payload)
    safe_write_json(args.report_root / "integrated_portal_gate_latest.json", payload)
    lines = [
        "# OpenClaw NAS Integrated Portal Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- passed: `{payload['passed_count']}/{payload['check_count']}`",
        f"- base_url: `{base_url}`",
    ]
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{item}`" for item in failures)
    safe_write_text(run_dir / "integrated_portal_gate.md", "\n".join(lines) + "\n")
    safe_write_text(args.report_root / "integrated_portal_gate_latest.md", "\n".join(lines) + "\n")
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {payload['passed_count']}/{payload['check_count']}")
    if failures:
        for item in failures:
            print(f"    - {item}")
    print(f"{'='*60}")
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
