#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import shutil
import sqlite3
import time
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_index_daemon_readiness"
DEFAULT_DAEMON_DB_NAME = "ai_nas_index_daemon_state.sqlite3"


def module_importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def runtime_capabilities() -> dict:
    watchdog_ready = module_importable("watchdog")
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "watchdog_importable": watchdog_ready,
        "inotifywait_path": shutil.which("inotifywait"),
        "systemctl_path": shutil.which("systemctl"),
        "native_event_watcher_ready": bool(watchdog_ready or shutil.which("inotifywait")),
        "polling_fallback_ready": True,
    }


def open_daemon_db(path: Path) -> sqlite3.Connection:
    con = open_sqlite_connection(path, timeout=30, isolation_level=None, row_factory=True)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS daemon_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            status TEXT NOT NULL,
            event_source TEXT NOT NULL,
            poll_interval_seconds REAL NOT NULL,
            stale_after_seconds REAL NOT NULL,
            cycle_count INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            heartbeat_at REAL NOT NULL,
            finished_at TEXT,
            recovered_from_run_id INTEGER,
            result_json TEXT,
            error TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_daemon_runs_status ON daemon_runs(status)")
    return con


def insert_stale_run(daemon_db: Path, owner: str, stale_after_seconds: float) -> int:
    con = open_daemon_db(daemon_db)
    try:
        cur = con.execute(
            """
            INSERT INTO daemon_runs(
                owner, status, event_source, poll_interval_seconds, stale_after_seconds,
                cycle_count, started_at, heartbeat_at, error
            )
            VALUES (?, 'running', 'simulated_previous_polling_worker', ?, ?, 0, ?, ?, ?)
            """,
            (
                owner,
                30.0,
                stale_after_seconds,
                iso_now(),
                time.monotonic() - stale_after_seconds - 60.0,
                "simulated_previous_worker_crash_before_probe_start",
            ),
        )
        return int(cur.lastrowid)
    finally:
        con.close()


def recover_stale_runs(daemon_db: Path) -> list[dict]:
    con = open_daemon_db(daemon_db)
    recovered = []
    now_monotonic = time.monotonic()
    try:
        rows = con.execute(
            """
            SELECT * FROM daemon_runs
            WHERE status='running' AND (? - heartbeat_at) > stale_after_seconds
            ORDER BY id
            """,
            (now_monotonic,),
        ).fetchall()
        for row in rows:
            recovered.append(
                {
                    "run_id": row["id"],
                    "owner": row["owner"],
                    "event_source": row["event_source"],
                    "last_heartbeat_age_seconds": round(now_monotonic - row["heartbeat_at"], 3),
                }
            )
            con.execute(
                """
                UPDATE daemon_runs
                SET status='recovered_stale_lock', finished_at=?, error=?
                WHERE id=?
                """,
                (iso_now(), "recovered_by_readiness_probe", row["id"]),
            )
    finally:
        con.close()
    return recovered


def start_daemon_run(
    daemon_db: Path,
    owner: str,
    event_source: str,
    poll_interval_seconds: float,
    stale_after_seconds: float,
    recovered_from_run_id: int | None,
) -> int:
    con = open_daemon_db(daemon_db)
    try:
        cur = con.execute(
            """
            INSERT INTO daemon_runs(
                owner, status, event_source, poll_interval_seconds, stale_after_seconds,
                started_at, heartbeat_at, recovered_from_run_id
            )
            VALUES (?, 'running', ?, ?, ?, ?, ?, ?)
            """,
            (
                owner,
                event_source,
                poll_interval_seconds,
                stale_after_seconds,
                iso_now(),
                time.monotonic(),
                recovered_from_run_id,
            ),
        )
        return int(cur.lastrowid)
    finally:
        con.close()


def heartbeat_daemon_run(daemon_db: Path, run_id: int, cycle_count: int) -> None:
    con = open_daemon_db(daemon_db)
    try:
        con.execute(
            "UPDATE daemon_runs SET heartbeat_at=?, cycle_count=? WHERE id=?",
            (time.monotonic(), cycle_count, run_id),
        )
    finally:
        con.close()


def finish_daemon_run(daemon_db: Path, run_id: int, status: str, result: dict, error: str | None = None) -> None:
    con = open_daemon_db(daemon_db)
    try:
        con.execute(
            """
            UPDATE daemon_runs
            SET status=?, finished_at=?, result_json=?, error=?
            WHERE id=?
            """,
            (status, iso_now(), json.dumps(result, ensure_ascii=False), error, run_id),
        )
    finally:
        con.close()


def recent_changes(index_path: Path, limit: int = 20) -> list[dict]:
    con = open_sqlite_connection(index_path, row_factory=True)
    try:
        rows = con.execute(
            """
            SELECT action, relative_path, path, reason, created_at
            FROM change_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        con.close()
    return [dict(row) for row in rows]


def daemon_db_snapshot(daemon_db: Path) -> dict:
    con = open_daemon_db(daemon_db)
    try:
        counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM daemon_runs GROUP BY status")
        }
        latest = [
            {
                "id": row["id"],
                "owner": row["owner"],
                "status": row["status"],
                "event_source": row["event_source"],
                "cycle_count": row["cycle_count"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "recovered_from_run_id": row["recovered_from_run_id"],
                "error": row["error"],
            }
            for row in con.execute("SELECT * FROM daemon_runs ORDER BY id DESC LIMIT 10")
        ]
    finally:
        con.close()
    return {"status_counts": counts, "latest_runs": latest}


def service_unit_draft(poll_interval_seconds: float) -> dict:
    return {
        "unit_name": "ai-nas-index-daemon.service",
        "install_path": "/etc/systemd/system/ai-nas-index-daemon.service",
        "written_by_probe": False,
        "restart_policy": "Restart=always; RestartSec=5",
        "exec_start_template": (
            "python3 /root/.openclaw/workspace/scripts/probes/ai_nas_index_daemon.py "
            f"--poll-interval-seconds {poll_interval_seconds:.1f}"
        ),
        "required_runtime_contract": [
            "single writer lease in ai_nas_index_daemon_state.sqlite3",
            "incremental SQLite/FTS scan using size, mtime_ns, and SHA256 for changed files",
            "change_log rows for added, updated, deleted, and failed files",
            "status endpoint or report exposing last heartbeat, queue depth, failures, and latest run",
            "no source delete, move, rename, or overwrite",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS background index daemon readiness probe.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--daemon-db-path", type=Path, default=None)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--poll-interval-seconds", type=float, default=30.0)
    parser.add_argument("--stale-after-seconds", type=float, default=120.0)
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args()

    daemon_db = args.daemon_db_path or (args.report_root / DEFAULT_DAEMON_DB_NAME)
    capabilities = runtime_capabilities()
    event_source = "native_watchdog_or_inotify" if capabilities["native_event_watcher_ready"] else "polling_fallback"

    stale_run_id = insert_stale_run(daemon_db, "simulated-crashed-index-daemon", args.stale_after_seconds)
    recovered = recover_stale_runs(daemon_db)
    recovered_id = recovered[0]["run_id"] if recovered else None
    run_id = start_daemon_run(
        daemon_db,
        "readiness-probe",
        event_source,
        args.poll_interval_seconds,
        args.stale_after_seconds,
        recovered_id,
    )
    cycle_results = []
    started = time.perf_counter()
    error = None
    try:
        for cycle in range(1, max(1, args.cycles) + 1):
            before = time.perf_counter()
            status = build_sqlite_inventory(args.personal_root, args.sqlite_index_path, max_files=args.max_files)
            elapsed_ms = (time.perf_counter() - before) * 1000.0
            last_run = status.get("last_run") or {}
            cycle_results.append(
                {
                    "cycle": cycle,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "index_status": status.get("status"),
                    "file_count": status.get("file_count"),
                    "failed_count": status.get("failed_count"),
                    "last_run": {
                        "added": last_run.get("added", 0),
                        "updated": last_run.get("updated", 0),
                        "unchanged": last_run.get("unchanged", 0),
                        "deleted": last_run.get("deleted", 0),
                        "failed": last_run.get("failed", 0),
                    },
                }
            )
            heartbeat_daemon_run(daemon_db, run_id, cycle)
    except Exception as exc:  # pragma: no cover - filesystem dependent
        error = f"{type(exc).__name__}:{exc}"

    total_elapsed_ms = (time.perf_counter() - started) * 1000.0
    final_index_status = sqlite_index_status(args.sqlite_index_path)
    change_rows = recent_changes(args.sqlite_index_path)
    hard_failures = bool(error)
    native_watcher_missing = not capabilities["native_event_watcher_ready"]
    verdict = (
        "failed_ai_nas_index_daemon_readiness"
        if hard_failures
        else "limited_ai_nas_index_daemon_readiness"
        if native_watcher_missing
        else "ok_ai_nas_index_daemon_readiness"
    )
    readiness_gaps = []
    if native_watcher_missing:
        readiness_gaps.append("No native filesystem watcher runtime detected; daemon should use polling fallback until watchdog/inotify is installed.")
    if not capabilities["systemctl_path"]:
        readiness_gaps.append("systemctl is not available in this environment; service unit can be generated but not locally verified here.")
    if not change_rows:
        readiness_gaps.append("No recent change_log rows were present after readiness cycles; change detection still depends on future filesystem events.")

    result = {
        "cycles_requested": args.cycles,
        "cycle_results": cycle_results,
        "total_elapsed_ms": round(total_elapsed_ms, 3),
        "final_index_status": final_index_status.get("status"),
        "file_count": final_index_status.get("file_count"),
        "failed_count": final_index_status.get("failed_count"),
        "recent_change_count": len(change_rows),
    }
    finish_daemon_run(daemon_db, run_id, "failed" if error else "completed", result, error=error)

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "daemon_db_path": str(daemon_db),
        "event_source": event_source,
        "capabilities": capabilities,
        "simulated_stale_run_id": stale_run_id,
        "recovered_stale_runs": recovered,
        "active_run_id": run_id,
        "cycle_results": cycle_results,
        "final_index_status": final_index_status,
        "recent_changes": change_rows,
        "daemon_state": daemon_db_snapshot(daemon_db),
        "service_unit_draft": service_unit_draft(args.poll_interval_seconds),
        "readiness_gaps": readiness_gaps,
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "service_unit_written": False,
            "writes": "Markdown/JSON readiness report plus daemon SQLite state and refreshed SQLite/FTS index rows",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "index_daemon_readiness")
    json_path = run_dir / "index_daemon_readiness.json"
    md_path = run_dir / "index_daemon_readiness.md"
    safe_write_json(json_path, payload)

    lines = [
        "# AI-NAS Index Daemon Readiness",
        "",
        f"- verdict: `{verdict}`",
        f"- event_source: `{event_source}`",
        f"- daemon_db_path: `{daemon_db}`",
        f"- sqlite_index_path: `{args.sqlite_index_path}`",
        f"- cycles: `{len(cycle_results)}`",
        f"- recovered_stale_runs: `{len(recovered)}`",
        f"- recent_change_count: `{len(change_rows)}`",
        "- policy: readiness/report/index state only; no source delete, no move, no overwrite, no service start",
        "",
        "## Runtime Capabilities",
        "",
    ]
    for key, value in capabilities.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Cycles", ""])
    for cycle in cycle_results:
        last_run = cycle["last_run"]
        lines.append(
            f"- cycle `{cycle['cycle']}` elapsed_ms `{cycle['elapsed_ms']}` status `{cycle['index_status']}` "
            f"added `{last_run['added']}` updated `{last_run['updated']}` unchanged `{last_run['unchanged']}` "
            f"deleted `{last_run['deleted']}` failed `{last_run['failed']}`"
        )
    lines.extend(["", "## Recovered Stale Locks", ""])
    if not recovered:
        lines.append("- No stale daemon lock was recovered.")
    for item in recovered:
        lines.append(
            f"- run `{item['run_id']}` owner `{item['owner']}` "
            f"heartbeat_age_seconds `{item['last_heartbeat_age_seconds']}`"
        )
    lines.extend(["", "## Recent Index Changes", ""])
    if not change_rows:
        lines.append("- No recent change_log rows.")
    for change in change_rows[:10]:
        lines.append(
            f"- `{change.get('action')}` `{change.get('relative_path') or change.get('path')}` "
            f"| `{change.get('reason')}` | `{change.get('created_at')}`"
        )
    lines.extend(["", "## Service Unit Draft", ""])
    draft = payload["service_unit_draft"]
    lines.append(f"- unit_name: `{draft['unit_name']}`")
    lines.append(f"- written_by_probe: `{draft['written_by_probe']}`")
    lines.append(f"- restart_policy: `{draft['restart_policy']}`")
    lines.append(f"- exec_start_template: `{draft['exec_start_template']}`")
    lines.extend(["", "## Readiness Gaps", ""])
    if not readiness_gaps:
        lines.append("- No readiness gap detected by this bounded probe.")
    for gap in readiness_gaps:
        lines.append(f"- {gap}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
