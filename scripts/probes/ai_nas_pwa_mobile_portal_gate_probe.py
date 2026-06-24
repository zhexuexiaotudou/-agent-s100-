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

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_pwa_mobile_portal_gate"
OK = "ok_ai_nas_pwa_mobile_portal_gate"
FAILED = "failed_ai_nas_pwa_mobile_portal_gate"


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
            return {"ok": 200 <= response.status < 300, "status": response.status, "headers": dict(response.headers.items()), "payload": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return {"ok": False, "status": exc.code, "headers": dict(exc.headers.items()), "payload": parsed}
    except Exception as exc:
        return {"ok": False, "status": 0, "headers": {}, "payload": {"error": f"{type(exc).__name__}:{exc}"}}


def http_text(url: str, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    headers = {"Accept": "text/html,*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "headers": dict(response.headers.items()), "text": response.read().decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "status": 0, "headers": {}, "text": "", "error": f"{type(exc).__name__}:{exc}"}


def http_bytes(url: str, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    headers = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "headers": dict(response.headers.items()), "body": response.read()}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "headers": dict(exc.headers.items()), "body": exc.read()}
    except Exception as exc:
        return {"ok": False, "status": 0, "headers": {}, "body": f"{type(exc).__name__}:{exc}".encode("utf-8")}


def multipart_upload(url: str, field_name: str, filename: str, data: bytes, token: str) -> dict[str, Any]:
    boundary = "----openclawpwamobilegate"
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
            self._send({"ok": True, "model": "Qwen2.5-1.5B-Instruct-S100P-official", "source": "fake_s100p_qwen"})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", "0") or "0")
            _ = self.rfile.read(length)
            self._send({"model": "Qwen2.5-1.5B-Instruct-S100P-official", "choices": [{"message": {"role": "assistant", "content": "OpenClaw mobile route is ready."}}]})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)


def start_fake_model() -> tuple[ThreadingHTTPServer, str]:
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def seed_personal(root: Path) -> None:
    for name in ["Movies", "Documents", "Photos", "Inbox"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "Documents" / "mobile_note.txt").write_text("OpenClaw mobile PWA upload and search fixture.\n", encoding="utf-8")
    (root / "Photos" / "mobile_album.jpg").write_bytes(b"fake-mobile-photo")
    (root / "Movies" / "Mobile.Demo.2026.mp4").write_bytes(b"fake-mobile-video")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate for PWA and mobile portal entry.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_pwa_mobile_portal_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "pwa_mobile_portal_gate")
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
    collected: dict[str, Any] = {"base_url": base_url, "run_dir": str(run_dir), "fake_model_url": fake_model_url}
    try:
        print("AI-NAS PWA Mobile Portal Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)

        html = http_text(base_url + "/")
        text = html.get("text", "")
        check(
            "Mobile-responsive portal shell is served",
            html.get("ok")
            and 'name="viewport"' in text
            and "max-width:620px" in text
            and "max-width:680px" in text
            and "loginScreen" in text
            and "chatText" in text,
            failures,
            checks,
        )
        check(
            "PWA hooks are present in HTML",
            "rel=\"manifest\"" in text
            and "serviceWorker" in text
            and "pwaInstallBtn" in text
            and "beforeinstallprompt" in text,
            failures,
            checks,
        )

        manifest_resp = http_json("GET", base_url + "/manifest.webmanifest")
        manifest = manifest_resp.get("payload") or {}
        check(
            "PWA manifest is installable",
            manifest_resp.get("ok")
            and manifest.get("display") == "standalone"
            and manifest.get("start_url") == "/"
            and bool(manifest.get("icons"))
            and manifest.get("theme_color") == "#f4fbf1",
            failures,
            checks,
            {"manifest": manifest},
        )
        icon = http_text(base_url + "/pwa-icon.svg")
        check("PWA icon is served as SVG", icon.get("ok") and "<svg" in icon.get("text", "") and "image/svg" in icon.get("headers", {}).get("Content-Type", ""), failures, checks)
        sw = http_text(base_url + "/sw.js")
        sw_text = sw.get("text", "")
        check(
            "Service worker caches shell but not API responses",
            sw.get("ok")
            and "CACHE_NAME" in sw_text
            and "url.pathname.startsWith('/api/')" in sw_text
            and "return;" in sw_text,
            failures,
            checks,
        )

        create_admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        check("Mobile admin bootstrap", create_admin.get("ok") and create_admin.get("payload", {}).get("ok"), failures, checks)
        login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        token = (login.get("payload") or {}).get("token")
        check("Mobile login API works", login.get("ok") and bool(token), failures, checks)

        config = http_json("GET", base_url + "/api/portal/config", token=token)
        features = (config.get("payload") or {}).get("features") or {}
        check("Portal config advertises PWA/mobile entry", config.get("ok") and features.get("pwa_mobile_entry") is True, failures, checks, {"features": features})

        upload = multipart_upload(base_url + "/api/storage/upload?path=Inbox", "file", "mobile_upload.txt", b"mobile upload fixture", token)
        check("Mobile upload flow works through API", upload.get("ok") and (upload.get("payload", {}).get("file") or {}).get("relative_path") == "Inbox/mobile_upload.txt", failures, checks)
        search = http_json("GET", base_url + "/api/copilot/search?query=mobile_upload&type=file&limit=5", token=token)
        check(
            "Mobile search finds uploaded file",
            search.get("ok") and any(item.get("relative_path") == "Inbox/mobile_upload.txt" for item in (search.get("payload") or {}).get("results") or []),
            failures,
            checks,
        )
        chat = http_json("POST", base_url + "/api/copilot/chat", {"message": "帮我找 mobile 上传文件", "type": "file", "limit": 3}, token=token)
        chat_payload = chat.get("payload") or {}
        check(
            "Mobile OpenClaw chat route works",
            chat.get("ok")
            and ((chat_payload.get("upstream") or {}).get("name") == "qwen25_official_primary")
            and "OpenClaw mobile route" in str(chat_payload.get("message") or ""),
            failures,
            checks,
        )

        media_index = http_json("POST", base_url + "/api/media/index", {"path": ""}, token=token)
        media_summary = http_json("GET", base_url + "/api/media/summary", token=token)
        movies = (media_summary.get("payload") or {}).get("movies") or []
        movie = next((item for item in movies if item.get("relative_path") == "Movies/Mobile.Demo.2026.mp4"), {})
        check("Mobile media library indexes videos", media_index.get("ok") and media_summary.get("ok") and bool(movie), failures, checks, {"movie": movie})
        media_open = http_bytes(base_url + str(movie.get("open_url") or ""), token=token)
        check("Mobile media open link returns authorized video bytes", media_open.get("ok") and media_open.get("body") == b"fake-mobile-video", failures, checks)
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
        "scope": "PWA/mobile portal entry: manifest, service worker, install hooks, responsive shell, login, upload, search, chat, and media links.",
        "checks": checks,
        "failures": failures,
        "summary": collected,
        "browser_verification": {
            "playwright_cli_available": False,
            "reason": "npx was not available in this Windows shell; this gate verifies runtime HTTP/API/PWA resources and responsive HTML/CSS structure.",
        },
        "server": {
            "command": cmd,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
        },
    }
    json_path = run_dir / "pwa_mobile_portal_gate.json"
    md_path = run_dir / "pwa_mobile_portal_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS PWA Mobile Portal Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- checks: `{sum(1 for item in checks if item['ok'])}/{len(checks)}`",
        f"- base_url: `{base_url}`",
        "- browser_verification: Playwright CLI unavailable because `npx` is not installed; API/PWA/runtime checks were executed.",
        "",
        "## Checks",
        "",
    ]
    for item in checks:
        lines.append(f"- {'PASS' if item['ok'] else 'FAIL'}: `{item['label']}`")
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{item}`" for item in failures)
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if verdict == OK else 2


if __name__ == "__main__":
    raise SystemExit(main())
