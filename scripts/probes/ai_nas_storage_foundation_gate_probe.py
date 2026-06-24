#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_report_dir,
    ensure_storage_root,
    iso_now,
    latest_file_operations,
    open_index_db,
    safe_write_json,
    safe_write_text,
    sha256_file,
    sqlite_index_status,
    storage_status,
)


TOOL_ID = "ai_nas_storage_foundation_gate"
OK_VERDICT = "ok_nas_storage_foundation_gate"
FAILED_VERDICT = "failed_nas_storage_foundation_gate"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw.strip() else {}
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": body}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return {"ok": False, "status": exc.code, "payload": body}


def http_bytes(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None, timeout: int = 120) -> dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "body": response.read()}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read()}


def multipart_upload(url: str, filename: str, content: bytes) -> dict[str, Any]:
    boundary = "ai-nas-storage-boundary"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
            b"Content-Type: application/octet-stream\r\n\r\n",
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    result = http_bytes("POST", url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        result["payload"] = json.loads(result["body"].decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        result["payload"] = {"raw": result["body"].decode("utf-8", errors="replace")}
    return result


def wait_for_server(base_url: str, proc: subprocess.Popen[str]) -> dict[str, Any]:
    deadline = time.monotonic() + 20
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        last = http_json("GET", base_url + "/api/storage/status", timeout=5)
        if last.get("ok"):
            return last
        time.sleep(0.25)
    return {"ok": False, "last": last, "returncode": proc.poll()}


def create_bulk_files(personal_root: Path, count: int) -> dict[str, Any]:
    bulk = personal_root / "Inbox" / "bulk_10k"
    bulk.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    existing = 0
    for idx in range(count):
        path = bulk / f"item_{idx:05d}.txt"
        if path.exists():
            existing += 1
            continue
        path.write_text(f"bulk file {idx:05d} for AI-NAS storage foundation scan\n", encoding="utf-8")
    return {
        "directory": str(bulk),
        "requested_count": count,
        "already_existing": existing,
        "created": count - existing,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def db_counts(db_path: Path) -> dict[str, int]:
    con = open_index_db(db_path)
    try:
        return {
            "records": int(con.execute("SELECT COUNT(*) FROM records").fetchone()[0]),
            "file_operations": int(con.execute("SELECT COUNT(*) FROM file_operations").fetchone()[0]),
            "index_runs": int(con.execute("SELECT COUNT(*) FROM index_runs").fetchone()[0]),
            "change_log": int(con.execute("SELECT COUNT(*) FROM change_log").fetchone()[0]),
        }
    finally:
        con.close()


def db_health(db_path: Path) -> dict[str, list[str]]:
    con = open_index_db(db_path)
    try:
        return {
            "integrity_check": [row[0] for row in con.execute("PRAGMA integrity_check")],
            "quick_check": [row[0] for row in con.execute("PRAGMA quick_check")],
        }
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 1 NAS storage foundation acceptance gate.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--sqlite-index-path", type=Path, default=None)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--file-count", type=int, default=10000)
    parser.add_argument("--keep-fixture", action="store_true")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "nas_storage_foundation_gate")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    if args.personal_root:
        personal_root = args.personal_root
    else:
        if fixture_root.exists() and not args.keep_fixture:
            shutil.rmtree(fixture_root)
        personal_root = fixture_root / "Personal"
    sqlite_index_path = args.sqlite_index_path or (run_dir / "personal_inventory.sqlite3")
    ensure_storage_root(personal_root)
    (personal_root / "Documents" / "seed.txt").write_text("seed document for storage foundation gate\n", encoding="utf-8")

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    server_script = Path(__file__).with_name("ai_nas_operator_portal_server.py")
    server_cmd = [
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
        str(sqlite_index_path),
        "--storage-max-files",
        str(max(args.file_count + 100, 1000)),
        "--no-refresh",
    ]
    proc = subprocess.Popen(server_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    failures: list[str] = []
    http_steps: dict[str, Any] = {}
    try:
        http_steps["server_ready"] = wait_for_server(base_url, proc)
        if not http_steps["server_ready"].get("ok"):
            failures.append("portal_storage_status_not_ready")
        http_steps["root_list"] = http_json("GET", base_url + "/api/storage/list")
        upload_content = b"uploaded bytes for storage foundation gate\n"
        http_steps["upload"] = multipart_upload(base_url + "/api/storage/upload?path=Inbox", "upload.txt", upload_content)
        http_steps["download"] = http_bytes("GET", base_url + "/api/storage/download?path=Inbox%2Fupload.txt")
        if http_steps["download"].get("body") != upload_content:
            failures.append("download_content_mismatch_after_upload")
        http_steps["rename"] = http_json("POST", base_url + "/api/storage/rename", {"path": "Inbox/upload.txt", "new_name": "renamed.txt"})
        http_steps["copy"] = http_json("POST", base_url + "/api/storage/copy", {"source": "Inbox/renamed.txt", "target": "Documents/copied.txt"})
        http_steps["move"] = http_json("POST", base_url + "/api/storage/move", {"source": "Documents/copied.txt", "target": "Inbox/moved.txt"})
        http_steps["delete"] = http_json("DELETE", base_url + "/api/storage/file?path=Inbox%2Fmoved.txt")
        http_steps["traversal_block"] = http_json("GET", base_url + "/api/storage/list?path=..")
        if http_steps["traversal_block"].get("status") < 400:
            failures.append("path_traversal_not_blocked")
        for key in ["root_list", "upload", "rename", "copy", "move", "delete"]:
            if not http_steps.get(key, {}).get("ok"):
                failures.append(f"http_step_failed:{key}")
    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=10)

    bulk = create_bulk_files(personal_root, args.file_count)
    scan_started = time.perf_counter()
    scan_status = build_sqlite_inventory(personal_root, sqlite_index_path, max_files=args.file_count + 100)
    scan_elapsed_ms = round((time.perf_counter() - scan_started) * 1000, 3)
    status = storage_status(personal_root, sqlite_index_path)
    index_status = sqlite_index_status(sqlite_index_path)
    health = db_health(sqlite_index_path)
    counts = db_counts(sqlite_index_path)
    operations = latest_file_operations(sqlite_index_path, limit=20)

    if counts["records"] < args.file_count:
        failures.append("sqlite_record_count_below_10k_fixture")
    if counts["file_operations"] < 5:
        failures.append("file_operation_log_too_short")
    if scan_status.get("status") not in {"completed", "completed_with_failures"}:
        failures.append("sqlite_scan_not_completed")
    if not status.get("writable"):
        failures.append("personal_root_not_writable")
    if not status.get("capacity", {}).get("free_bytes"):
        failures.append("capacity_stats_missing")
    if health.get("integrity_check") != ["ok"] or health.get("quick_check") != ["ok"]:
        failures.append("sqlite_integrity_check_not_ok")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": OK_VERDICT if not failures else FAILED_VERDICT,
        "scope": "Goal 1 NAS storage foundation: discovery/capacity, Personal root convention, web file operations, SQLite metadata, operation logs, 10k scan gate",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "server": {
            "base_url": base_url,
            "command": server_cmd,
            "stdout_tail": (stdout or "")[-2000:],
            "stderr_tail": (stderr or "")[-2000:],
        },
        "http_steps": {
            key: {
                "ok": value.get("ok"),
                "status": value.get("status"),
                "payload": value.get("payload"),
                "body_len": len(value.get("body") or b""),
            }
            for key, value in http_steps.items()
        },
        "bulk_fixture": bulk,
        "scan": {
            "elapsed_ms": scan_elapsed_ms,
            "status": scan_status,
        },
        "storage_status": status,
        "index_status": index_status,
        "db_health": health,
        "db_counts": counts,
        "operation_log_tail": operations,
        "sample_hash": {
            "path": str(personal_root / "Inbox" / "renamed.txt"),
            "sha256": sha256_file(personal_root / "Inbox" / "renamed.txt") if (personal_root / "Inbox" / "renamed.txt").exists() else None,
        },
        "safety": {
            "path_traversal_blocked": http_steps.get("traversal_block", {}).get("status", 0) >= 400,
            "delete_scope": "fixture requested file only; non-empty directory deletes are refused by server",
            "overwrite_policy": "upload/copy/move/rename refuse existing target",
        },
        "failures": failures,
    }
    json_path = run_dir / "nas_storage_foundation_gate.json"
    md_path = run_dir / "nas_storage_foundation_gate.md"
    latest_json = args.report_root / "nas_storage_foundation_gate_latest.json"
    latest_md = args.report_root / "nas_storage_foundation_gate_latest.md"
    safe_write_json(json_path, payload)
    safe_write_json(latest_json, payload)
    lines = [
        "# NAS Storage Foundation Gate",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- personal_root: `{personal_root}`",
        f"- sqlite_index_path: `{sqlite_index_path}`",
        f"- file_count_gate: `{args.file_count}`",
        f"- sqlite_records: `{counts['records']}`",
        f"- scan_elapsed_ms: `{scan_elapsed_ms}`",
        f"- operation_log_count: `{counts['file_operations']}`",
        f"- free_bytes: `{status.get('capacity', {}).get('free_bytes')}`",
        f"- path_traversal_blocked: `{payload['safety']['path_traversal_blocked']}`",
        "",
        "## HTTP Steps",
        "",
    ]
    for key, value in payload["http_steps"].items():
        lines.append(f"- `{key}`: ok=`{value.get('ok')}` status=`{value.get('status')}`")
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in failures)
    safe_write_text(md_path, "\n".join(lines) + "\n")
    safe_write_text(latest_md, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    print(payload["verdict"])
    return 0 if payload["verdict"] == OK_VERDICT else 1


if __name__ == "__main__":
    raise SystemExit(main())
