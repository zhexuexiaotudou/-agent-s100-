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
from urllib.parse import urlencode

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_visual_search_gate"
OK = "ok_ai_nas_visual_search_gate"
FAILED = "failed_ai_nas_visual_search_gate"


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


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, 604, 384), outline=(24, 82, 92), width=6)
    draw.text((64, 72), text, fill=(20, 30, 40))
    image.save(path, quality=92)


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
            self._send({"ok": True, "model": "OpenClaw-Dream7B-S100P-local", "source": "fake_openclaw_visual_gate"})
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", "0") or "0")
            _ = self.rfile.read(length)
            self._send(
                {
                    "model": "OpenClaw-Dream7B-S100P-local",
                    "choices": [{"message": {"role": "assistant", "content": "我会调用 NAS 授权视觉搜索来找图。"}}],
                }
            )
            return
        self._send({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)


def start_fake_openclaw() -> tuple[ThreadingHTTPServer, str]:
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeOpenClawHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate for OpenClaw NAS visual search portal integration.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_visual_search_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "visual_search_gate")
    personal_root = run_dir / "Personal"
    for name in ["Movies", "Documents", "Photos", "Inbox", "Private"]:
        (personal_root / name).mkdir(parents=True, exist_ok=True)
    write_fixture_image(personal_root / "Photos" / "white_car_invoice_screenshot.jpg", (238, 240, 235), "WHITE CAR INVOICE SCREENSHOT 2026")
    write_fixture_image(personal_root / "Photos" / "beach_meal_family.jpg", (80, 170, 210), "BEACH MEAL FAMILY")
    write_fixture_image(personal_root / "Private" / "private_white_car_invoice_screenshot.jpg", (244, 244, 238), "PRIVATE WHITE CAR INVOICE")
    (personal_root / "Documents" / "invoice_notes.txt").write_text("public invoice text fixture\n", encoding="utf-8")

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
    artifacts: dict[str, Any] = {}
    try:
        print("OpenClaw NAS Visual Search Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)

        html = http_text(base_url + "/")
        text = html.get("text", "")
        check("Portal contains visual search UI", html.get("ok") and "visionQuery" in text and "/api/vision/search" in text, failures, checks)

        create_admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        check("Admin bootstrap", create_admin.get("ok") and create_admin.get("payload", {}).get("ok"), failures, checks)
        admin_login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        admin_token = (admin_login.get("payload") or {}).get("token")
        check("Admin login", admin_login.get("ok") and bool(admin_token), failures, checks)

        create_viewer = http_json("POST", base_url + "/api/identity/create-user", {"username": "viewer", "password": "viewer123", "role": "user"}, token=admin_token)
        set_acl = http_json("POST", base_url + "/api/identity/set-acl", {"path": "Photos", "principal_type": "user", "principal_name": "viewer", "permission": "read"}, token=admin_token)
        viewer_login = http_json("POST", base_url + "/api/identity/login", {"username": "viewer", "password": "viewer123"})
        viewer_token = (viewer_login.get("payload") or {}).get("token")
        check("Viewer ACL setup", create_viewer.get("ok") and set_acl.get("ok") and bool(viewer_token), failures, checks)

        status = http_json("GET", base_url + "/api/vision/status", token=admin_token)
        check("Vision status API", status.get("ok") and "runtime" in (status.get("payload") or {}), failures, checks)

        index = http_json("POST", base_url + "/api/vision/index", {"limit": 100, "include_ocr": True}, token=admin_token, timeout=60)
        index_payload = index.get("payload") or {}
        embedding_counts = ((index_payload.get("image_embedding_summary") or {}).get("status_counts") or {})
        check("Vision index builds image embeddings", index.get("ok") and embedding_counts.get("local_visual_embedding_completed", 0) >= 2, failures, checks)

        search_query = urlencode({"query": "white car invoice screenshot", "limit": "10"})
        admin_search = http_json("GET", f"{base_url}/api/vision/search?{search_query}", token=admin_token)
        admin_results = (admin_search.get("payload") or {}).get("results") or []
        check("Vision search returns authorized image result", admin_search.get("ok") and any(item.get("relative_path") == "Photos/white_car_invoice_screenshot.jpg" for item in admin_results), failures, checks)
        check("Vision results carry evidence links", any(item.get("open_url") and item.get("evidence") for item in admin_results), failures, checks)

        chat = http_json("POST", base_url + "/api/copilot/chat", {"message": "帮我找到白底汽车发票截图", "type": "image", "limit": 8}, token=admin_token, timeout=60)
        vision_results = (chat.get("payload") or {}).get("vision_results") or []
        check("Copilot chat attaches visual search results", chat.get("ok") and any(item.get("relative_path") == "Photos/white_car_invoice_screenshot.jpg" for item in vision_results), failures, checks)

        viewer_search = http_json("GET", f"{base_url}/api/vision/search?{search_query}", token=viewer_token)
        viewer_results = (viewer_search.get("payload") or {}).get("results") or []
        check("Viewer sees only ACL-authorized visual results", viewer_search.get("ok") and viewer_results and all(str(item.get("relative_path", "")).startswith("Photos/") for item in viewer_results), failures, checks)
        check("Viewer visual search does not leak Private", all("Private/" not in str(item.get("relative_path", "")) for item in viewer_results), failures, checks)

        artifacts = {
            "base_url": base_url,
            "vision_status": status.get("payload"),
            "vision_index": index_payload,
            "admin_search": admin_search.get("payload"),
            "chat": chat.get("payload"),
            "viewer_search": viewer_search.get("payload"),
        }
    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
        fake_openclaw.shutdown()

    verdict = OK if not failures else FAILED
    report = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "checks": checks,
        "failures": failures,
        "artifacts": artifacts,
        "server_stdout_tail": stdout[-4000:],
        "server_stderr_tail": stderr[-4000:],
    }
    json_path = run_dir / "visual_search_gate.json"
    md_path = run_dir / "visual_search_gate.md"
    safe_write_json(json_path, report)
    lines = [
        "# OpenClaw NAS Visual Search Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- checks: `{sum(1 for item in checks if item['ok'])}/{len(checks)}`",
        f"- json: `{json_path}`",
    ]
    if failures:
        lines.append("- failures: " + ", ".join(f"`{item}`" for item in failures))
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
