#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_web_os_gate"
OK = "ok_nas_web_os_gate"
FAILED = "failed_nas_web_os_gate"


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
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "text": response.read().decode("utf-8", errors="replace"),
            }
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 5 Web NAS OS acceptance gate.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_web_os_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "web_os_gate")
    personal_root = run_dir / "Personal"
    for name in ["Movies", "Documents", "Photos", "Inbox"]:
        (personal_root / name).mkdir(parents=True, exist_ok=True)
    (personal_root / "Documents" / "welcome.txt").write_text("AI-NAS Web OS document fixture\n", encoding="utf-8")
    (personal_root / "Documents" / "invoice_2024.txt").write_text("invoice fixture for non-long Web OS docs table\n", encoding="utf-8")
    (personal_root / "Photos" / "car_fixture.jpg").write_bytes(b"fake-jpg-car-fixture")
    (personal_root / "Photos" / "meal_fixture.png").write_bytes(b"fake-png-meal-fixture")
    (personal_root / "Movies" / "frame_sample.mp4").write_bytes(b"fake-video-frame-fixture")
    (personal_root / "Documents" / "ocr_fixture.txt").write_text("OCR fixture text placeholder\n", encoding="utf-8")

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
        "--storage-max-files",
        "500",
        "--nas-portal",
        "--no-refresh",
    ]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    stdout = ""
    stderr = ""
    try:
        print("Goal 5 Web NAS OS Gate Probe")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)

        html = http_text(base_url + "/")
        text = html.get("text", "")
        check("Login page served", html.get("ok") and "AI-NAS Web OS" in text and "loginScreen" in text, failures, checks)
        expected_entries = [
            "File Manager",
            "Media Center",
            "Photos / Album",
            "Documents",
            "Backup Tasks",
            "Snapshots / Trash",
            "User Management",
            "System Status",
            "App Ecosystem",
            "AI Copilot",
            "Audit Log",
        ]
        for entry in expected_entries:
            check(f"Web entry: {entry}", entry in text, failures, checks)

        create = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123"})
        check("Admin bootstrap through Web API", create.get("ok") and create.get("payload", {}).get("ok"), failures, checks)
        login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        token = (login.get("payload") or {}).get("token")
        check("Login API returns token", login.get("ok") and bool(token), failures, checks)

        storage_status = http_json("GET", base_url + "/api/storage/status", token=token)
        check("Dashboard storage status API", storage_status.get("ok") and storage_status.get("payload", {}).get("ok"), failures, checks)
        file_list = http_json("GET", base_url + "/api/storage/list", token=token)
        entries = (file_list.get("payload") or {}).get("entries") or []
        check("File manager root listing API", file_list.get("ok") and any(item.get("name") == "Documents" for item in entries), failures, checks)
        users = http_json("GET", base_url + "/api/identity/users", token=token)
        check("User management API", users.get("ok") and len((users.get("payload") or {}).get("users") or []) == 1, failures, checks)
        operations = http_json("GET", base_url + "/api/storage/operations", token=token)
        check("Audit log API", operations.get("ok") and "operations" in (operations.get("payload") or {}), failures, checks)
        latest = http_json("GET", base_url + "/api/latest", token=token)
        check("System/operator status API", latest.get("ok") and (latest.get("payload") or {}).get("tool_id") == "ai_nas_operator_portal_server", failures, checks)
        snapshot = http_json("POST", base_url + "/api/snapshot/create", {"name": "webos_snap", "path": "Documents"}, token=token)
        check("Snapshot action reachable from Web OS backend", snapshot.get("ok") and snapshot.get("payload", {}).get("ok"), failures, checks)
        recovery = http_json("GET", base_url + "/api/snapshot/stats", token=token)
        check("Recovery stats API", recovery.get("ok") and (recovery.get("payload", {}).get("stats") or {}).get("snapshot_count", 0) >= 1, failures, checks)

        backup_create = http_json(
            "POST",
            base_url + "/api/backup/create-task",
            {"name": "webos_docs_backup", "source": "Documents", "dest": "Documents"},
            token=token,
        )
        check("Backup task create API", backup_create.get("ok") and backup_create.get("payload", {}).get("ok"), failures, checks)
        backup_run = http_json("POST", base_url + "/api/backup/run", {"name": "webos_docs_backup"}, token=token)
        check("Backup task run API", backup_run.get("ok") and backup_run.get("payload", {}).get("ok"), failures, checks)
        backup_summary = http_json("GET", base_url + "/api/backup/summary", token=token)
        check("Backup summary API", backup_summary.get("ok") and len((backup_summary.get("payload") or {}).get("tasks") or []) >= 1, failures, checks)

        media_index = http_json("POST", base_url + "/api/media/index", {"path": "Photos"}, token=token)
        check("Media index API", media_index.get("ok") and (media_index.get("payload", {}).get("index") or {}).get("scanned", 0) >= 2, failures, checks)
        album = http_json("POST", base_url + "/api/media/create-album", {"name": "webos_album", "description": "gate fixture"}, token=token)
        check("Album create API", album.get("ok") and album.get("payload", {}).get("ok"), failures, checks)
        media_summary = http_json("GET", base_url + "/api/media/summary", token=token)
        check("Media summary API", media_summary.get("ok") and (media_summary.get("payload", {}).get("stats") or {}).get("photo_count", 0) >= 2, failures, checks)

        ops_check = http_json("POST", base_url + "/api/ops/health-check", {"service_name": "webos-gate"}, token=token)
        check("Ops health-check API", ops_check.get("ok") and (ops_check.get("payload", {}).get("check") or {}).get("status") == "healthy", failures, checks)
        ops_summary = http_json("GET", base_url + "/api/ops/summary", token=token)
        check("Ops summary API", ops_summary.get("ok") and len((ops_summary.get("payload") or {}).get("checks") or []) >= 1, failures, checks)

        plugin = http_json(
            "POST",
            base_url + "/api/apps/register-plugin",
            {"name": "photo-viewer", "version": "0.1.0", "type": "app", "description": "gate fixture"},
            token=token,
        )
        check("Plugin register API", plugin.get("ok") and plugin.get("payload", {}).get("ok"), failures, checks)
        protocol = http_json(
            "POST",
            base_url + "/api/apps/add-protocol",
            {"name": "smb-adapter", "protocol": "SMB", "port": 445, "config": {"implementation_state": "adapter_record_only"}},
            token=token,
        )
        check("Protocol adapter stub API", protocol.get("ok") and protocol.get("payload", {}).get("ok"), failures, checks)
        apps_summary = http_json("GET", base_url + "/api/apps/summary", token=token)
        protocols = (apps_summary.get("payload") or {}).get("protocols") or []
        truthful_adapter = any(item.get("name") == "smb-adapter" and "adapter_record_only" in str(item.get("config_json")) for item in protocols)
        check("App ecosystem summary API", apps_summary.get("ok") and truthful_adapter, failures, checks)

        audit_summary = http_json("GET", base_url + "/api/audit/summary", token=token)
        check("Audit summary API", audit_summary.get("ok") and "operations" in (audit_summary.get("payload") or {}), failures, checks)
    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=10)

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "scope": "Goal 5 Web NAS OS: login, file manager, media, documents, backup, users, status, AI Copilot, audit, and backend APIs",
        "base_url": base_url,
        "server_command": cmd,
        "checks": checks,
        "passed_count": sum(1 for item in checks if item.get("ok")),
        "check_count": len(checks),
        "failures": failures,
        "server": {"stdout_tail": (stdout or "")[-2000:], "stderr_tail": (stderr or "")[-2000:]},
    }
    safe_write_json(run_dir / "web_os_gate.json", payload)
    safe_write_json(args.report_root / "web_os_gate_latest.json", payload)
    lines = [
        "# NAS Web OS Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- passed: `{payload['passed_count']}/{payload['check_count']}`",
        f"- base_url: `{base_url}`",
    ]
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{item}`" for item in failures)
    safe_write_text(run_dir / "web_os_gate.md", "\n".join(lines) + "\n")
    safe_write_text(args.report_root / "web_os_gate_latest.md", "\n".join(lines) + "\n")
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {payload['passed_count']}/{payload['check_count']}")
    if failures:
        for item in failures:
            print(f"    - {item}")
    print(f"{'='*60}")
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
