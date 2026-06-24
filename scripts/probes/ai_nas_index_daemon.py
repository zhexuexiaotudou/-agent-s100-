#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import time
from pathlib import Path

from ai_nas_common import DEFAULT_PERSONAL_ROOT, DEFAULT_REPORT_ROOT, DEFAULT_SQLITE_INDEX_PATH, build_sqlite_inventory, iso_now
from ai_nas_index_daemon_readiness_probe import (
    DEFAULT_DAEMON_DB_NAME,
    finish_daemon_run,
    heartbeat_daemon_run,
    open_daemon_db,
    recover_stale_runs,
    start_daemon_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resident AI-NAS SQLite/FTS index daemon.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--daemon-db-path", type=Path, default=None)
    parser.add_argument("--poll-interval-seconds", type=float, default=30.0)
    parser.add_argument("--stale-after-seconds", type=float, default=120.0)
    parser.add_argument("--max-files", type=int, default=50000)
    args = parser.parse_args()

    daemon_db = args.daemon_db_path or (args.report_root / DEFAULT_DAEMON_DB_NAME)
    daemon_db.parent.mkdir(parents=True, exist_ok=True)
    open_daemon_db(daemon_db).close()
    recovered = recover_stale_runs(daemon_db)
    recovered_id = recovered[0]["run_id"] if recovered else None
    run_id = start_daemon_run(
        daemon_db,
        "systemd-resident-index-daemon",
        "polling",
        args.poll_interval_seconds,
        args.stale_after_seconds,
        recovered_id,
    )
    stopping = False

    def handle_signal(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    cycle = 0
    last_result: dict = {"started_at": iso_now(), "recovered_stale_runs": recovered}
    try:
        while not stopping:
            cycle += 1
            started = time.perf_counter()
            status = build_sqlite_inventory(args.personal_root, args.sqlite_index_path, max_files=args.max_files)
            last_run = status.get("last_run") or {}
            last_result = {
                "cycle": cycle,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
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
            heartbeat_daemon_run(daemon_db, run_id, cycle)
            deadline = time.monotonic() + max(1.0, args.poll_interval_seconds)
            while not stopping and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
        finish_daemon_run(daemon_db, run_id, "stopped", last_result)
        return 0
    except Exception as exc:  # pragma: no cover - production runtime dependent
        finish_daemon_run(
            daemon_db,
            run_id,
            "failed",
            {"cycle": cycle, "last_result": last_result},
            error=f"{type(exc).__name__}:{exc}",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
