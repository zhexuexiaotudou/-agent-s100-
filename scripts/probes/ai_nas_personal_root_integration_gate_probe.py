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
from urllib.parse import urlencode

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
)


TOOL_ID = "ai_nas_personal_root_integration_gate"
OK = "ok_ai_nas_personal_root_integration_gate"
FAILED = "failed_ai_nas_personal_root_integration_gate"


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


def http_bytes(url: str, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    headers = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "body": response.read(), "headers": dict(response.headers.items())}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read(), "headers": dict(exc.headers.items())}
    except Exception as exc:
        return {"ok": False, "status": 0, "body": f"{type(exc).__name__}:{exc}".encode("utf-8"), "headers": {}}


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


def check(label: str, condition: bool, failures: list[str], checks: list[dict[str, Any]], evidence: dict[str, Any] | None = None) -> None:
    checks.append({"label": label, "ok": bool(condition), "evidence": evidence or {}})
    print(f"  {'PASS' if condition else 'FAIL'}: {label}")
    if not condition:
        failures.append(label)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the configured Personal root through real portal storage/search APIs.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--query", default="renovation invoice receipt")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "personal_root_integration_gate")
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    personal_root = args.personal_root

    print("AI-NAS Personal Root Integration Gate")
    check("Personal root exists", personal_root.exists() and personal_root.is_dir(), failures, checks, {"personal_root": str(personal_root)})
    for dirname in ["Documents", "Inbox", "Movies", "Photos"]:
        check(f"Personal root contains {dirname}", (personal_root / dirname).is_dir(), failures, checks)

    index_status = build_sqlite_inventory(personal_root, args.sqlite_index_path) if not failures else {}
    check(
        "SQLite inventory indexes real Personal content",
        index_status.get("status") == "completed" and int(index_status.get("file_count") or 0) >= 50 and int(index_status.get("failed_count") or 0) == 0,
        failures,
        checks,
        {"file_count": index_status.get("file_count"), "failed_count": index_status.get("failed_count")},
    )

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
        str(args.report_root),
        "--personal-root",
        str(personal_root),
        "--sqlite-index-path",
        str(args.sqlite_index_path),
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
        "--nas-portal",
        "--no-refresh",
    ]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = ""
    stderr = ""
    try:
        ready = wait_ready(base_url, proc)
        check("Portal API starts on configured Personal root", bool(ready.get("ok")), failures, checks, ready)

        create_admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        check("Admin user bootstrap succeeds", create_admin.get("ok") and create_admin.get("payload", {}).get("ok"), failures, checks, create_admin)
        login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        token = (login.get("payload") or {}).get("token")
        check("Admin login succeeds", login.get("ok") and bool(token), failures, checks, login)

        status = http_json("GET", base_url + "/api/storage/status", token=token)
        status_payload = status.get("payload") or {}
        check(
            "Storage status reports configured Personal root",
            status.get("ok") and Path(str(status_payload.get("personal_root") or "")).resolve(strict=False) == personal_root.resolve(strict=False),
            failures,
            checks,
            {"personal_root": status_payload.get("personal_root"), "capacity": status_payload.get("capacity")},
        )

        root_listing = http_json("GET", base_url + "/api/storage/list?path=", token=token)
        names = {item.get("name") for item in (root_listing.get("payload") or {}).get("entries") or []}
        check("Storage list returns root folders", root_listing.get("ok") and {"Documents", "Inbox", "Movies", "Photos"}.issubset(names), failures, checks, {"names": sorted(names)})

        invoice_listing = http_json("GET", base_url + "/api/storage/list?" + urlencode({"path": "Documents/Invoices/2024"}), token=token)
        invoice_entries = (invoice_listing.get("payload") or {}).get("entries") or []
        check("Storage list opens nested invoice folder", invoice_listing.get("ok") and len(invoice_entries) >= 1, failures, checks, {"entry_count": len(invoice_entries)})

        search = http_json("GET", base_url + "/api/copilot/search?" + urlencode({"query": args.query, "type": "file", "limit": "5"}), token=token)
        results = (search.get("payload") or {}).get("results") or []
        target = next((item for item in results if str(item.get("relative_path") or "").startswith("Documents/Invoices/")), results[0] if results else {})
        check(
            "Copilot search returns indexed Personal file result",
            search.get("ok") and bool(target.get("relative_path")) and bool(target.get("open_url")),
            failures,
            checks,
            {"query": args.query, "target": target},
        )

        if target.get("relative_path"):
            download = http_bytes(base_url + "/api/storage/download?" + urlencode({"path": target["relative_path"]}), token=token)
            body_preview = download.get("body", b"")[:400].decode("utf-8", errors="replace")
            check(
                "Downloaded search result contains real invoice or renovation text",
                download.get("ok") and any(term in body_preview.lower() for term in ["invoice", "renovation", "receipt", "payment"]),
                failures,
                checks,
                {"relative_path": target["relative_path"], "body_preview": body_preview},
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
        "scope": "Task A acceptance: configured Personal root exists, indexes real content, and serves storage/search/download APIs.",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "base_url": base_url,
        "index_status": index_status,
        "checks": checks,
        "passed_count": sum(1 for item in checks if item.get("ok")),
        "check_count": len(checks),
        "failures": failures,
        "server": {"stdout_tail": (stdout or "")[-2000:], "stderr_tail": (stderr or "")[-4000:]},
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON gate report plus SQLite index refresh only",
        },
    }
    safe_write_json(run_dir / "personal_root_integration_gate.json", payload)
    safe_write_json(args.report_root / "personal_root_integration_gate_latest.json", payload)
    lines = [
        "# AI-NAS Personal Root Integration Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- passed: `{payload['passed_count']}/{payload['check_count']}`",
        f"- personal_root: `{personal_root}`",
        f"- sqlite_index_path: `{args.sqlite_index_path}`",
    ]
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{item}`" for item in failures)
    safe_write_text(run_dir / "personal_root_integration_gate.md", "\n".join(lines) + "\n")
    safe_write_text(args.report_root / "personal_root_integration_gate_latest.md", "\n".join(lines) + "\n")
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {payload['passed_count']}/{payload['check_count']}")
    if failures:
        for item in failures:
            print(f"    - {item}")
    print(f"{'='*60}")
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
