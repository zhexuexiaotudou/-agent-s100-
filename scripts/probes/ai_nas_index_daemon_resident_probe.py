#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_index_daemon_resident"


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 4)


def open_daemon_db(path: Path) -> sqlite3.Connection:
    con = open_sqlite_connection(path, timeout=30, isolation_level=None, row_factory=True)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_pid INTEGER NOT NULL,
            cycle INTEGER NOT NULL,
            run_id INTEGER,
            status TEXT NOT NULL,
            file_count INTEGER,
            failed_count INTEGER,
            added INTEGER NOT NULL DEFAULT 0,
            updated INTEGER NOT NULL DEFAULT 0,
            unchanged INTEGER NOT NULL DEFAULT 0,
            deleted INTEGER NOT NULL DEFAULT 0,
            elapsed_ms REAL NOT NULL,
            created_at TEXT NOT NULL,
            error TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_worker_heartbeats_cycle ON worker_heartbeats(cycle)")
    return con


def insert_heartbeat(daemon_db: Path, worker_pid: int, cycle: int, status: dict, elapsed_ms: float, error: str | None = None) -> None:
    last_run = status.get("last_run") or {}
    con = open_daemon_db(daemon_db)
    try:
        con.execute(
            """
            INSERT INTO worker_heartbeats(
                worker_pid, cycle, run_id, status, file_count, failed_count,
                added, updated, unchanged, deleted, elapsed_ms, created_at, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                worker_pid,
                cycle,
                status.get("run_id"),
                status.get("status", "unknown"),
                status.get("file_count"),
                status.get("failed_count"),
                int(last_run.get("added", 0) or 0),
                int(last_run.get("updated", 0) or 0),
                int(last_run.get("unchanged", 0) or 0),
                int(last_run.get("deleted", 0) or 0),
                round(elapsed_ms, 3),
                iso_now(),
                error,
            ),
        )
    finally:
        con.close()


def heartbeat_snapshot(daemon_db: Path) -> dict:
    con = open_daemon_db(daemon_db)
    try:
        rows = [dict(row) for row in con.execute("SELECT * FROM worker_heartbeats ORDER BY id")]
    finally:
        con.close()
    return {
        "count": len(rows),
        "latest": rows[-1] if rows else None,
        "rows": rows,
    }


def latest_change_for(db_path: Path, relative_path: str, action: str) -> dict | None:
    con = open_sqlite_connection(db_path, row_factory=True)
    try:
        row = con.execute(
            """
            SELECT id, run_id, action, path, relative_path, reason, created_at
            FROM change_log
            WHERE relative_path = ? AND action = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (relative_path.replace("\\", "/"), action),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def worker_main(args: argparse.Namespace) -> int:
    cycle = 0
    deadline = time.monotonic() + args.max_runtime_seconds
    stop_file = args.stop_file
    while time.monotonic() < deadline and not stop_file.exists():
        cycle += 1
        started = time.perf_counter()
        error = None
        try:
            status = build_sqlite_inventory(args.personal_root, args.sqlite_index_path, max_files=args.max_files)
        except Exception as exc:  # pragma: no cover - filesystem dependent
            error = f"{type(exc).__name__}:{exc}"
            status = {"status": "failed", "last_run": {}, "file_count": None, "failed_count": None, "run_id": None}
        elapsed_ms = (time.perf_counter() - started) * 1000
        insert_heartbeat(args.daemon_db_path, worker_pid=__import__("os").getpid(), cycle=cycle, status=status, elapsed_ms=elapsed_ms, error=error)
        time.sleep(max(0.05, args.poll_interval_seconds))
    return 0


def prepare_fixture(root: Path) -> dict:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    documents = personal / "Documents"
    documents.mkdir(parents=True, exist_ok=True)
    baseline = documents / "resident-baseline-contract.txt"
    baseline.write_text("Resident daemon baseline contract. Payment 1000 CNY on 2024-01-01.\n", encoding="utf-8")
    return {"fixture_root": str(root), "personal_root": str(personal), "baseline_file": str(baseline)}


def wait_for_heartbeat(daemon_db: Path, min_count: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if heartbeat_snapshot(daemon_db)["count"] >= min_count:
            return True
        time.sleep(0.05)
    return False


def wait_for_change(db_path: Path, relative_path: str, action: str, timeout_seconds: float) -> tuple[dict | None, float]:
    started = time.perf_counter()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        change = latest_change_for(db_path, relative_path, action)
        if change:
            return change, (time.perf_counter() - started) * 1000
        time.sleep(0.05)
    return None, (time.perf_counter() - started) * 1000


def mutate(path: Path, action: str, content: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if action in {"added", "updated"}:
        path.write_text(content or "", encoding="utf-8")
    elif action == "deleted":
        if path.exists():
            path.unlink()
    else:
        raise ValueError(f"unsupported action: {action}")


def parent_main(args: argparse.Namespace) -> int:
    run_dir = ensure_report_dir(args.report_root, "index_daemon_resident")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    fixture = prepare_fixture(fixture_root)
    personal_root = Path(fixture["personal_root"])
    db_path = run_dir / "index_daemon_resident.sqlite3"
    daemon_db = run_dir / "index_daemon_resident_state.sqlite3"
    stop_file = run_dir / "stop-worker"
    worker_cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--personal-root",
        str(personal_root),
        "--sqlite-index-path",
        str(db_path),
        "--daemon-db-path",
        str(daemon_db),
        "--stop-file",
        str(stop_file),
        "--poll-interval-seconds",
        str(args.poll_interval_seconds),
        "--max-runtime-seconds",
        str(args.max_runtime_seconds),
        "--max-files",
        str(args.max_files),
    ]
    worker = subprocess.Popen(worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    events = []
    worker_started = wait_for_heartbeat(daemon_db, min_count=1, timeout_seconds=args.startup_timeout_seconds)
    try:
        planned_events = [
            ("added", "Documents/resident-invoice.txt", "Resident invoice. Amount 1200 CNY. Date 2024-02-01.\n"),
            ("updated", "Documents/resident-baseline-contract.txt", "Resident daemon revised contract. Payment 1000 CNY on 2024-01-01. Final 500 CNY on 2024-02-15.\n"),
            ("deleted", "Documents/resident-invoice.txt", None),
        ]
        for action, rel, content in planned_events:
            target = personal_root / rel
            mutate(target, action, content)
            change, latency_ms = wait_for_change(db_path, rel, action, timeout_seconds=args.event_timeout_seconds)
            events.append(
                {
                    "action": action,
                    "relative_path": rel,
                    "detected": bool(change),
                    "detection_latency_ms": round(latency_ms, 3),
                    "change_log": change,
                }
            )
    finally:
        stop_file.write_text("stop\n", encoding="utf-8")
        try:
            stdout, stderr = worker.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            stdout, stderr = worker.communicate(timeout=5)
    heartbeats = heartbeat_snapshot(daemon_db)
    detected_latencies = [event["detection_latency_ms"] for event in events if event["detected"]]
    all_detected = all(event["detected"] for event in events)
    worker_ok = worker.returncode == 0
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_index_daemon_resident" if worker_started and worker_ok and all_detected else "failed_ai_nas_index_daemon_resident",
        "scope": "bounded owned child-process resident polling daemon over an isolated Personal fixture",
        "fixture": fixture,
        "sqlite_index_path": str(db_path),
        "daemon_db_path": str(daemon_db),
        "worker": {
            "cmd": worker_cmd,
            "pid": worker.pid,
            "returncode": worker.returncode,
            "started": worker_started,
            "stdout": stdout[-2000:],
            "stderr": stderr[-2000:],
        },
        "heartbeats": heartbeats,
        "events": events,
        "summary": {
            "event_count": len(events),
            "detected_count": sum(1 for event in events if event["detected"]),
            "failed_detection_count": sum(1 for event in events if not event["detected"]),
            "heartbeat_count": heartbeats["count"],
            "detection_latency_ms": {
                "p50": percentile(detected_latencies, 0.50),
                "p95": percentile(detected_latencies, 0.95),
                "p99": percentile(detected_latencies, 0.99),
                "max": round(max(detected_latencies), 3) if detected_latencies else None,
            },
        },
        "final_index_status": sqlite_index_status(db_path),
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": True,
            "fixture_file_deleted": True,
            "delete_performed_on_real_personal": False,
            "move_performed": False,
            "overwrite_performed_on_real_personal": False,
            "service_installed": False,
            "service_started": False,
            "owned_child_process_started": True,
            "owned_child_process_stopped": worker.returncode == 0,
            "writes": "isolated fixture files, SQLite/FTS index, daemon heartbeat SQLite, and Markdown/JSON reports",
        },
        "production_gap": "This proves a resident child-process polling loop and heartbeat/change detection contract; production still needs a systemd-installed daemon and long-running NAS-backed soak.",
    }
    json_path = run_dir / "index_daemon_resident.json"
    md_path = run_dir / "index_daemon_resident.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Resident Index Daemon Probe",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- worker_started: `{worker_started}`",
        f"- worker_returncode: `{worker.returncode}`",
        f"- heartbeat_count: `{heartbeats['count']}`",
        f"- detected_count: `{payload['summary']['detected_count']}` / `{payload['summary']['event_count']}`",
        f"- detection_p95_ms: `{payload['summary']['detection_latency_ms']['p95']}`",
        f"- detection_p99_ms: `{payload['summary']['detection_latency_ms']['p99']}`",
        "- policy: owned child process and isolated fixture only; no real Personal mutation and no service install/start",
        "",
        "## Events",
        "",
    ]
    for event in events:
        lines.append(
            f"- `{event['action']}` `{event['relative_path']}` detected `{event['detected']}` "
            f"latency_ms `{event['detection_latency_ms']}`"
        )
        if event["change_log"]:
            lines.append(f"  - change_log_id: `{event['change_log']['id']}` reason `{event['change_log']['reason']}`")
    lines.extend(["", "## Heartbeats", ""])
    for row in heartbeats["rows"][-8:]:
        lines.append(
            f"- cycle `{row['cycle']}` run_id `{row['run_id']}` status `{row['status']}` "
            f"added `{row['added']}` updated `{row['updated']}` deleted `{row['deleted']}` elapsed_ms `{row['elapsed_ms']}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if payload["verdict"].startswith("ok_") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded resident AI-NAS index daemon probe over an isolated Personal fixture.")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--sqlite-index-path", type=Path, default=None)
    parser.add_argument("--daemon-db-path", type=Path, default=None)
    parser.add_argument("--stop-file", type=Path, default=None)
    parser.add_argument("--poll-interval-seconds", type=float, default=0.2)
    parser.add_argument("--startup-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--event-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--max-runtime-seconds", type=float, default=20.0)
    parser.add_argument("--max-files", type=int, default=5000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.worker:
        required = [args.personal_root, args.sqlite_index_path, args.daemon_db_path, args.stop_file]
        if any(value is None for value in required):
            raise SystemExit("--worker requires --personal-root, --sqlite-index-path, --daemon-db-path, and --stop-file")
        return worker_main(args)
    return parent_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
