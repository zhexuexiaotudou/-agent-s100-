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
from http import HTTPStatus
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_scheduled_rules_portal_gate"
OK = "ok_ai_nas_scheduled_rules_portal_gate"
FAILED = "failed_ai_nas_scheduled_rules_portal_gate"


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


def report_payload(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def seed_personal(root: Path) -> None:
    for name in ["Movies", "Documents", "Photos", "Inbox"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "Documents" / "project_plan.txt").write_text(
        "Project plan. NAS folder summary fixture. Owner: admin. Topic: weekly archive review.\n",
        encoding="utf-8",
    )
    (root / "Documents" / "invoice_renovation_2026.txt").write_text(
        "Invoice fixture. Renovation payment 2026-06-24 amount 1280 CNY.\n",
        encoding="utf-8",
    )
    duplicate = b"duplicate-photo-binary-fixture"
    (root / "Photos" / "family_photo_a.jpg").write_bytes(duplicate)
    (root / "Inbox" / "family_photo_a_copy.jpg").write_bytes(duplicate)
    (root / "Movies" / "OpenClaw.Demo.2026.mp4").write_bytes(b"fake-movie-bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate for user-visible scheduled organizing rules in the OpenClaw NAS portal.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_scheduled_rules_portal_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "scheduled_rules_portal_gate")
    personal_root = run_dir / "Personal"
    seed_personal(personal_root)
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
        print("AI-NAS Scheduled Rules Portal Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks, {"ready": ready.get("ok")})

        html = http_text(base_url + "/")
        text = html.get("text", "")
        check(
            "NAS portal exposes scheduled rules UI",
            html.get("ok") and "scheduleRuleName" in text and "/api/schedule/create-rule" in text,
            failures,
            checks,
        )

        create_admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        check("Admin bootstrap", create_admin.get("ok") and create_admin.get("payload", {}).get("ok"), failures, checks)
        admin_login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        admin_token = (admin_login.get("payload") or {}).get("token")
        check("Admin login", admin_login.get("ok") and bool(admin_token), failures, checks)

        initial = http_json("GET", base_url + "/api/schedule/summary", token=admin_token)
        initial_rules = (initial.get("payload") or {}).get("rules") or []
        check("Default scheduled rules are visible", initial.get("ok") and len(initial_rules) >= 3, failures, checks, {"rule_count": len(initial_rules)})

        custom = http_json(
            "POST",
            base_url + "/api/schedule/create-rule",
            {
                "name": "gate-folder-summary",
                "rule_type": "folder_summary",
                "interval_seconds": 604800,
                "config": {"path": "Documents"},
                "enabled": True,
            },
            token=admin_token,
        )
        check("Admin can create folder summary rule", custom.get("ok") and (custom.get("payload") or {}).get("ok"), failures, checks)

        folder_run = http_json("POST", base_url + "/api/schedule/run-dry", {"name": "gate-folder-summary"}, token=admin_token)
        folder_payload = (folder_run.get("payload") or {}).get("run") or {}
        folder_report = report_payload(folder_payload.get("report_path"))
        folder_result = folder_report.get("result") or {}
        check(
            "Folder summary dry-run uses real indexed files",
            folder_run.get("ok")
            and folder_payload.get("status") == "completed"
            and folder_result.get("file_count", 0) >= 2
            and folder_result.get("source_mutations") is False
            and folder_report.get("delete_performed") is False,
            failures,
            checks,
            {"report_path": folder_payload.get("report_path"), "file_count": folder_result.get("file_count")},
        )

        duplicate_rule = http_json(
            "POST",
            base_url + "/api/schedule/create-rule",
            {
                "name": "gate-duplicate-report",
                "rule_type": "duplicate_report",
                "interval_seconds": 604800,
                "config": {"path": ""},
                "enabled": True,
            },
            token=admin_token,
        )
        check("Admin can create duplicate report rule", duplicate_rule.get("ok") and (duplicate_rule.get("payload") or {}).get("ok"), failures, checks)
        duplicate_run = http_json("POST", base_url + "/api/schedule/run-dry", {"name": "gate-duplicate-report"}, token=admin_token)
        duplicate_payload = (duplicate_run.get("payload") or {}).get("run") or {}
        duplicate_report = report_payload(duplicate_payload.get("report_path"))
        duplicate_result = duplicate_report.get("result") or {}
        check(
            "Duplicate dry-run reports duplicate group without source mutations",
            duplicate_run.get("ok")
            and duplicate_result.get("duplicate_group_count", 0) >= 1
            and duplicate_result.get("source_mutations") is False
            and duplicate_report.get("move_performed") is False,
            failures,
            checks,
            {"report_path": duplicate_payload.get("report_path"), "duplicate_group_count": duplicate_result.get("duplicate_group_count")},
        )

        index_rule = http_json(
            "POST",
            base_url + "/api/schedule/create-rule",
            {
                "name": "gate-index-refresh",
                "rule_type": "index_refresh",
                "interval_seconds": 86400,
                "config": {"path": ""},
                "enabled": True,
            },
            token=admin_token,
        )
        check("Admin can create index refresh rule", index_rule.get("ok") and (index_rule.get("payload") or {}).get("ok"), failures, checks)
        index_run = http_json("POST", base_url + "/api/schedule/run-dry", {"name": "gate-index-refresh"}, token=admin_token)
        index_payload = (index_run.get("payload") or {}).get("run") or {}
        index_report = report_payload(index_payload.get("report_path"))
        index_result = index_report.get("result") or {}
        check(
            "Index refresh dry-run refreshes metadata only",
            index_run.get("ok")
            and index_result.get("file_count", 0) >= 5
            and index_result.get("failed_count") == 0
            and index_report.get("source_mutations") is False,
            failures,
            checks,
            {"report_path": index_payload.get("report_path"), "file_count": index_result.get("file_count")},
        )

        disabled = http_json("POST", base_url + "/api/schedule/set-enabled", {"name": "gate-index-refresh", "enabled": False}, token=admin_token)
        check("Admin can disable scheduled rule", disabled.get("ok") and (disabled.get("payload") or {}).get("rule", {}).get("enabled") is False, failures, checks)

        create_viewer = http_json("POST", base_url + "/api/identity/create-user", {"username": "viewer", "password": "viewer123", "role": "user"}, token=admin_token)
        viewer_login = http_json("POST", base_url + "/api/identity/login", {"username": "viewer", "password": "viewer123"})
        viewer_token = (viewer_login.get("payload") or {}).get("token")
        low_priv = http_json("POST", base_url + "/api/schedule/create-rule", {"name": "viewer-rule", "rule_type": "folder_summary"}, token=viewer_token)
        check(
            "Low-privilege user cannot create scheduled rule",
            create_viewer.get("ok") and viewer_login.get("ok") and low_priv.get("status") == 403,
            failures,
            checks,
        )

        final_summary = http_json("GET", base_url + "/api/schedule/summary", token=admin_token)
        final_payload = final_summary.get("payload") or {}
        collected["final_summary"] = final_payload
        check(
            "Schedule summary exposes rules and recent dry-run reports",
            final_summary.get("ok")
            and (final_payload.get("stats") or {}).get("rule_count", 0) >= 6
            and (final_payload.get("stats") or {}).get("run_count", 0) >= 3,
            failures,
            checks,
            {"stats": final_payload.get("stats")},
        )
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
        "scope": "User-visible scheduled organizing rules: create/list/enable/dry-run/report paths with source-file safety.",
        "checks": checks,
        "failures": failures,
        "summary": collected,
        "server": {
            "command": cmd,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
        },
    }
    json_path = run_dir / "scheduled_rules_portal_gate.json"
    md_path = run_dir / "scheduled_rules_portal_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Scheduled Rules Portal Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- checks: `{sum(1 for item in checks if item['ok'])}/{len(checks)}`",
        f"- base_url: `{base_url}`",
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
