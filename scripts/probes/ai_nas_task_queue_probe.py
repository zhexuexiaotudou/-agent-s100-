#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    search_sqlite_index,
    sqlite_index_status,
)


DEFAULT_QUEUE_DB_NAME = "ai_nas_task_queue.sqlite3"
DEFAULT_TASKS = [
    {"task_type": "index", "payload": {}},
    {"task_type": "search", "payload": {"query": "2024 renovation payment contract invoice screenshot"}},
    {"task_type": "search", "payload": {"query": "invoice screenshot 2024"}},
    {"task_type": "search", "payload": {"query": "beach photo 2024"}},
    {"task_type": "search", "payload": {"query": "white car photo 2024"}},
]


def open_queue_db(queue_path: Path) -> sqlite3.Connection:
    con = open_sqlite_connection(queue_path, timeout=30, isolation_level=None, row_factory=True)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 2,
            lease_owner TEXT,
            lease_expires_at REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            elapsed_ms REAL,
            result_json TEXT,
            error TEXT,
            recovery_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    return con


def reset_queue(queue_path: Path) -> None:
    con = open_queue_db(queue_path)
    try:
        con.execute("DELETE FROM jobs")
    finally:
        con.close()


def enqueue_job(queue_path: Path, task_type: str, payload: dict, priority: int = 100, status: str = "pending", **extra) -> int:
    now = iso_now()
    con = open_queue_db(queue_path)
    try:
        cur = con.execute(
            """
            INSERT INTO jobs(
                task_type, payload_json, status, priority, attempts, max_attempts,
                lease_owner, lease_expires_at, created_at, updated_at, started_at,
                error, recovery_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_type,
                json.dumps(payload, ensure_ascii=False),
                status,
                priority,
                extra.get("attempts", 0),
                extra.get("max_attempts", 2),
                extra.get("lease_owner"),
                extra.get("lease_expires_at"),
                now,
                now,
                extra.get("started_at"),
                extra.get("error"),
                extra.get("recovery_count", 0),
            ),
        )
        return int(cur.lastrowid)
    finally:
        con.close()


def recover_stale_jobs(queue_path: Path) -> list[dict]:
    now_monotonic = time.monotonic()
    now = iso_now()
    con = open_queue_db(queue_path)
    recovered = []
    try:
        rows = con.execute(
            """
            SELECT * FROM jobs
            WHERE status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?
            ORDER BY id
            """,
            (now_monotonic,),
        ).fetchall()
        for row in rows:
            recovered.append(
                {
                    "job_id": row["id"],
                    "task_type": row["task_type"],
                    "previous_owner": row["lease_owner"],
                    "attempts": row["attempts"],
                }
            )
            con.execute(
                """
                UPDATE jobs
                SET status='pending', lease_owner=NULL, lease_expires_at=NULL,
                    updated_at=?, error=?, recovery_count=recovery_count + 1
                WHERE id=?
                """,
                (now, "recovered_from_expired_lease", row["id"]),
            )
    finally:
        con.close()
    return recovered


def claim_job(queue_path: Path, worker_id: str, lease_seconds: float) -> dict | None:
    con = open_queue_db(queue_path)
    now = iso_now()
    lease_expires_at = time.monotonic() + lease_seconds
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            """
            SELECT * FROM jobs
            WHERE status = 'pending' AND attempts < max_attempts
            ORDER BY priority ASC, id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            con.execute("COMMIT")
            return None
        con.execute(
            """
            UPDATE jobs
            SET status='running', lease_owner=?, lease_expires_at=?,
                attempts=attempts + 1, started_at=COALESCE(started_at, ?), updated_at=?
            WHERE id=?
            """,
            (worker_id, lease_expires_at, now, now, row["id"]),
        )
        con.execute("COMMIT")
        claimed = dict(row)
        claimed["attempts"] = claimed["attempts"] + 1
        claimed["lease_owner"] = worker_id
        return claimed
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def finish_job(queue_path: Path, job_id: int, ok: bool, elapsed_ms: float, result: dict | None = None, error: str | None = None) -> None:
    now = iso_now()
    con = open_queue_db(queue_path)
    try:
        con.execute(
            """
            UPDATE jobs
            SET status=?, finished_at=?, updated_at=?, elapsed_ms=?, result_json=?,
                error=?, lease_owner=NULL, lease_expires_at=NULL
            WHERE id=?
            """,
            (
                "done" if ok else "failed",
                now,
                now,
                round(elapsed_ms, 3),
                json.dumps(result or {}, ensure_ascii=False),
                error,
                job_id,
            ),
        )
    finally:
        con.close()


def execute_job(job: dict, personal_root: Path, index_path: Path, limit: int, max_files: int) -> dict:
    payload = json.loads(job["payload_json"])
    if job["task_type"] == "index":
        status = build_sqlite_inventory(personal_root, index_path, max_files=max_files)
        return {
            "status": status.get("status"),
            "file_count": status.get("file_count"),
            "failed_count": status.get("failed_count"),
            "last_run": status.get("last_run"),
        }
    if job["task_type"] == "search":
        query = payload.get("query", "")
        matches = search_sqlite_index(index_path, query, limit=limit)
        return {
            "query": query,
            "match_count": len(matches),
            "top_matches": [
                {
                    "relative_path": item["relative_path"],
                    "confidence": item["confidence"],
                    "source": item["source"],
                }
                for item in matches[:3]
            ],
        }
    raise ValueError(f"unsupported_task_type:{job['task_type']}")


def worker_loop(queue_path: Path, worker_id: str, personal_root: Path, index_path: Path, limit: int, max_files: int, lease_seconds: float) -> list[dict]:
    processed = []
    while True:
        job = claim_job(queue_path, worker_id, lease_seconds)
        if not job:
            break
        started = time.perf_counter()
        try:
            result = execute_job(job, personal_root, index_path, limit=limit, max_files=max_files)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            finish_job(queue_path, job["id"], True, elapsed_ms, result=result)
            processed.append({"job_id": job["id"], "worker_id": worker_id, "ok": True, "elapsed_ms": round(elapsed_ms, 3)})
        except Exception as exc:  # pragma: no cover - task dependent
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            finish_job(queue_path, job["id"], False, elapsed_ms, error=f"{type(exc).__name__}:{exc}")
            processed.append(
                {
                    "job_id": job["id"],
                    "worker_id": worker_id,
                    "ok": False,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
    return processed


def queue_snapshot(queue_path: Path) -> dict:
    con = open_queue_db(queue_path)
    try:
        counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status")
        }
        jobs = [dict(row) for row in con.execute("SELECT * FROM jobs ORDER BY id")]
    finally:
        con.close()
    for job in jobs:
        if job.get("payload_json"):
            job["payload"] = json.loads(job.pop("payload_json"))
        if job.get("result_json"):
            job["result"] = json.loads(job.pop("result_json"))
    return {"counts": counts, "jobs": jobs}


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS persistent SQLite task queue and crash-recovery probe.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--queue-path", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--lease-seconds", type=float, default=10.0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args()

    queue_path = args.queue_path or (args.report_root / DEFAULT_QUEUE_DB_NAME)
    reset_queue(queue_path)
    build_sqlite_inventory(args.personal_root, args.sqlite_index_path, max_files=args.max_files)

    stale_id = enqueue_job(
        queue_path,
        "search",
        {"query": "recovered stale invoice 2024"},
        priority=10,
        status="running",
        attempts=1,
        lease_owner="simulated_crashed_worker",
        lease_expires_at=time.monotonic() - 60,
        started_at=iso_now(),
        error="simulated_crash_before_probe_start",
    )
    enqueued_ids = [stale_id]
    for idx, task in enumerate(DEFAULT_TASKS, start=1):
        enqueued_ids.append(enqueue_job(queue_path, task["task_type"], task["payload"], priority=20 + idx))

    recovered = recover_stale_jobs(queue_path)
    worker_results = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            executor.submit(
                worker_loop,
                queue_path,
                f"worker-{idx + 1}",
                args.personal_root,
                args.sqlite_index_path,
                args.limit,
                args.max_files,
                args.lease_seconds,
            )
            for idx in range(max(1, args.workers))
        ]
        for future in as_completed(futures):
            worker_results.extend(future.result())
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    snapshot = queue_snapshot(queue_path)
    failures = [job for job in snapshot["jobs"] if job["status"] != "done"]
    payload = {
        "verdict": "ok_ai_nas_task_queue_probe" if not failures and recovered else "failed_ai_nas_task_queue_probe",
        "queue_path": str(queue_path),
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "enqueued_job_ids": enqueued_ids,
        "simulated_stale_job_id": stale_id,
        "recovered_jobs": recovered,
        "workers": args.workers,
        "elapsed_ms": round(elapsed_ms, 3),
        "worker_results": sorted(worker_results, key=lambda item: item["job_id"]),
        "queue": snapshot,
        "final_index_status": sqlite_index_status(args.sqlite_index_path),
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "queue SQLite plus Markdown/JSON report",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "task_queue")
    json_path = run_dir / "task_queue.json"
    md_path = run_dir / "task_queue.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Task Queue Probe",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- queue_path: `{payload['queue_path']}`",
        f"- workers: `{args.workers}`",
        f"- elapsed_ms: `{payload['elapsed_ms']}`",
        f"- queue_counts: `{snapshot['counts']}`",
        f"- recovered_jobs: `{len(recovered)}`",
        "- policy: source files are not modified; queue and reports only",
        "",
        "## Recovered Jobs",
        "",
    ]
    for item in recovered:
        lines.append(
            f"- job `{item['job_id']}` | task `{item['task_type']}` | "
            f"previous_owner `{item['previous_owner']}` | attempts `{item['attempts']}`"
        )
    lines.extend(["", "## Jobs", ""])
    for job in snapshot["jobs"]:
        lines.append(
            f"- job `{job['id']}` | `{job['task_type']}` | status `{job['status']}` | "
            f"attempts `{job['attempts']}` | recoveries `{job['recovery_count']}` | elapsed_ms `{job.get('elapsed_ms')}`"
        )
        if job.get("error"):
            lines.append(f"  - error: `{job['error']}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
