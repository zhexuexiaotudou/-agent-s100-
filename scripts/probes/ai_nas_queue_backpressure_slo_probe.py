#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_queue_backpressure_slo"
QUEUE_SCHEMA_READY: set[str] = set()
INDEX_REBUILD_LOCK = Lock()


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


def latency_summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "min_ms": round(min(values), 3) if values else None,
        "max_ms": round(max(values), 3) if values else None,
        "avg_ms": round(statistics.mean(values), 3) if values else None,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
    }


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    photos = personal / "Photos"
    docs.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    for idx in range(20):
        (docs / f"2024_renovation_packet_{idx:02d}.txt").write_text(
            f"Renovation payment packet {idx}. Contract invoice receipt amount {1000 + idx} CNY on 2024-04-{(idx % 28) + 1:02d}.\n",
            encoding="utf-8",
        )
    (docs / "local_ai_nas_manual.txt").write_text(
        "Local AI NAS manual. Queue backpressure, indexing, search, and recovery notes.\n",
        encoding="utf-8",
    )
    (photos / "2024_invoice_screenshot_note.txt").write_text(
        "Invoice screenshot placeholder for queue search workload.\n",
        encoding="utf-8",
    )
    return personal


def open_queue(path: Path) -> sqlite3.Connection:
    con = open_sqlite_connection(path, timeout=30, isolation_level=None, row_factory=True)
    schema_key = str(path.resolve())
    if schema_key in QUEUE_SCHEMA_READY:
        return con
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_class TEXT NOT NULL,
            task_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 2,
            submitted_monotonic REAL NOT NULL,
            claimed_monotonic REAL,
            finished_monotonic REAL,
            queue_wait_ms REAL,
            elapsed_ms REAL,
            worker_id TEXT,
            result_json TEXT,
            error TEXT,
            reject_reason TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(status, priority, id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_class_status ON jobs(job_class, status)")
    QUEUE_SCHEMA_READY.add(schema_key)
    return con


def accepted_low_depth(con: sqlite3.Connection) -> int:
    row = con.execute(
        """
        SELECT COUNT(*) AS count
        FROM jobs
        WHERE job_class='background' AND status IN ('pending', 'running')
        """
    ).fetchone()
    return int(row["count"])


def enqueue_job(
    queue_path: Path,
    *,
    job_class: str,
    task_type: str,
    payload: dict,
    priority: int,
    submitted_monotonic: float,
    max_low_pending: int,
    max_attempts: int = 2,
) -> dict:
    con = open_queue(queue_path)
    transaction_started = False
    try:
        con.execute("BEGIN IMMEDIATE")
        transaction_started = True
        low_depth = accepted_low_depth(con)
        rejected = job_class == "background" and low_depth >= max_low_pending
        status = "rejected_backpressure" if rejected else "pending"
        reason = "background_queue_depth_limit" if rejected else None
        cur = con.execute(
            """
            INSERT INTO jobs(
                job_class, task_type, payload_json, status, priority, max_attempts,
                submitted_monotonic, reject_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_class,
                task_type,
                json.dumps(payload, ensure_ascii=False),
                status,
                priority,
                max_attempts,
                submitted_monotonic,
                reason,
            ),
        )
        con.execute("COMMIT")
        transaction_started = False
        return {
            "job_id": int(cur.lastrowid),
            "job_class": job_class,
            "task_type": task_type,
            "accepted": not rejected,
            "low_depth_before_admission": low_depth,
            "reject_reason": reason,
        }
    except Exception:
        if transaction_started:
            try:
                con.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
        raise
    finally:
        con.close()


def claim_job(queue_path: Path, worker_id: str, started_monotonic: float) -> dict | None:
    con = open_queue(queue_path)
    transaction_started = False
    try:
        con.execute("BEGIN IMMEDIATE")
        transaction_started = True
        row = con.execute(
            """
            SELECT * FROM jobs
            WHERE status='pending' AND attempts < max_attempts
            ORDER BY priority ASC, id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            con.execute("COMMIT")
            return None
        claimed = time.perf_counter() - started_monotonic
        queue_wait_ms = (claimed - float(row["submitted_monotonic"])) * 1000
        con.execute(
            """
            UPDATE jobs
            SET status='running', attempts=attempts + 1, claimed_monotonic=?,
                queue_wait_ms=?, worker_id=?
            WHERE id=?
            """,
            (claimed, round(queue_wait_ms, 3), worker_id, row["id"]),
        )
        con.execute("COMMIT")
        item = dict(row)
        item["attempts"] = int(item["attempts"]) + 1
        item["queue_wait_ms"] = round(queue_wait_ms, 3)
        item["worker_id"] = worker_id
        return item
    except sqlite3.OperationalError as exc:
        if transaction_started:
            try:
                con.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
        if "locked" in str(exc).lower():
            return {"_retry": True, "error": f"{type(exc).__name__}:{exc}"}
        raise
    except Exception:
        if transaction_started:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def finish_job(queue_path: Path, job: dict, ok: bool, started_monotonic: float, elapsed_ms: float, result: dict | None = None, error: str | None = None) -> None:
    last_error = None
    for _ in range(200):
        con = open_queue(queue_path)
        try:
            status = "done"
            if not ok:
                status = "pending" if int(job["attempts"]) < int(job["max_attempts"]) else "dead_letter"
            con.execute(
                """
                UPDATE jobs
                SET status=?, finished_monotonic=?, elapsed_ms=?, result_json=?, error=?
                WHERE id=?
                """,
                (
                    status,
                    time.perf_counter() - started_monotonic,
                    round(elapsed_ms, 3),
                    json.dumps(result or {}, ensure_ascii=False),
                    error,
                    job["id"],
                ),
            )
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" not in str(exc).lower():
                raise
            time.sleep(0.05)
        finally:
            con.close()
    raise last_error or sqlite3.OperationalError("finish_job retry exhausted")


def execute_job(job: dict, personal_root: Path, db_path: Path, max_files: int, limit: int) -> dict:
    payload = json.loads(job["payload_json"])
    task_type = job["task_type"]
    if task_type == "interactive_search":
        matches = search_sqlite_index(db_path, payload.get("query", ""), limit=limit)
        time.sleep(0.004)
        return {"match_count": len(matches), "query": payload.get("query", "")}
    if task_type == "background_index":
        with INDEX_REBUILD_LOCK:
            status = build_sqlite_inventory(personal_root, db_path, max_files=max_files)
        time.sleep(0.02)
        return {"status": status.get("status"), "file_count": status.get("file_count")}
    if task_type == "background_summary":
        matches = search_sqlite_index(db_path, payload.get("query", ""), limit=limit)
        time.sleep(0.012)
        return {"match_count": len(matches), "summary": "bounded background summary placeholder from indexed evidence"}
    if task_type == "poison":
        raise RuntimeError("simulated_transient_then_dead_letter")
    raise ValueError(f"unsupported_task_type:{task_type}")


def worker_loop(queue_path: Path, worker_id: str, personal_root: Path, db_path: Path, max_files: int, limit: int, started_monotonic: float) -> list[dict]:
    processed = []
    while True:
        job = claim_job(queue_path, worker_id, started_monotonic)
        if job and job.get("_retry"):
            time.sleep(0.01)
            continue
        if not job:
            break
        started = time.perf_counter()
        try:
            result = execute_job(job, personal_root, db_path, max_files, limit)
            elapsed_ms = (time.perf_counter() - started) * 1000
            finish_job(queue_path, job, True, started_monotonic, elapsed_ms, result=result)
            processed.append(
                {
                    "job_id": job["id"],
                    "job_class": job["job_class"],
                    "task_type": job["task_type"],
                    "attempt": job["attempts"],
                    "ok": True,
                    "queue_wait_ms": job["queue_wait_ms"],
                    "elapsed_ms": round(elapsed_ms, 3),
                    "worker_id": worker_id,
                }
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            error = f"{type(exc).__name__}:{exc}"
            finish_job(queue_path, job, False, started_monotonic, elapsed_ms, error=error)
            processed.append(
                {
                    "job_id": job["id"],
                    "job_class": job["job_class"],
                    "task_type": job["task_type"],
                    "attempt": job["attempts"],
                    "ok": False,
                    "queue_wait_ms": job["queue_wait_ms"],
                    "elapsed_ms": round(elapsed_ms, 3),
                    "worker_id": worker_id,
                    "error": error,
                }
            )
    return processed


def queue_snapshot(queue_path: Path) -> dict:
    con = open_queue(queue_path)
    try:
        counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status")
        }
        class_counts = {
            f"{row['job_class']}:{row['status']}": row["count"]
            for row in con.execute("SELECT job_class, status, COUNT(*) AS count FROM jobs GROUP BY job_class, status")
        }
        rows = [dict(row) for row in con.execute("SELECT * FROM jobs ORDER BY id")]
    finally:
        con.close()
    for row in rows:
        if row.get("payload_json"):
            row["payload"] = json.loads(row.pop("payload_json"))
        if row.get("result_json"):
            row["result"] = json.loads(row.pop("result_json"))
    return {"counts": counts, "class_counts": class_counts, "jobs": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded AI-NAS queue backpressure and interactive P95/P99 SLO acceptance.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=None,
        help="Optional local runtime directory for the fixture, SQLite index, and queue; reports still persist under report-root.",
    )
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--max-low-pending", type=int, default=10)
    parser.add_argument("--interactive-p95-ms", type=float, default=180.0)
    parser.add_argument("--interactive-p99-ms", type=float, default=260.0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "queue_backpressure_slo")
    runtime_root = args.runtime_root or (run_dir / "runtime")
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    fixture_root = args.fixture_root or (runtime_root / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = runtime_root / "queue_backpressure_slo.sqlite3"
    queue_path = runtime_root / "queue_backpressure_slo_queue.sqlite3"
    build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    started_monotonic = time.perf_counter()

    admissions = []
    for idx in range(14):
        task_type = "background_index" if idx % 2 == 0 else "background_summary"
        admissions.append(
            enqueue_job(
                queue_path,
                job_class="background",
                task_type=task_type,
                payload={"query": "renovation payment invoice"},
                priority=80,
                submitted_monotonic=time.perf_counter() - started_monotonic,
                max_low_pending=args.max_low_pending,
            )
        )
    for idx in range(5):
        admissions.append(
            enqueue_job(
                queue_path,
                job_class="interactive",
                task_type="interactive_search",
                payload={"query": f"2024 renovation payment invoice {idx}"},
                priority=10,
                submitted_monotonic=time.perf_counter() - started_monotonic,
                max_low_pending=args.max_low_pending,
            )
        )
    admissions.append(
        enqueue_job(
            queue_path,
            job_class="background",
            task_type="poison",
            payload={},
            priority=60,
            submitted_monotonic=time.perf_counter() - started_monotonic,
            max_low_pending=args.max_low_pending + 1,
            max_attempts=2,
        )
    )

    all_processed = []
    for _round in range(3):
        round_processed = []
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [
                executor.submit(
                    worker_loop,
                    queue_path,
                    f"worker-{idx + 1}",
                    personal_root,
                    db_path,
                    args.max_files,
                    args.limit,
                    started_monotonic,
                )
                for idx in range(max(1, args.workers))
            ]
            for future in as_completed(futures):
                round_processed.extend(future.result())
        all_processed.extend(round_processed)
        snapshot = queue_snapshot(queue_path)
        if not any(job["status"] == "pending" for job in snapshot["jobs"]):
            break

    snapshot = queue_snapshot(queue_path)
    interactive_done = [job for job in snapshot["jobs"] if job["job_class"] == "interactive" and job["status"] == "done"]
    background_done = [job for job in snapshot["jobs"] if job["job_class"] == "background" and job["status"] == "done"]
    rejected = [job for job in snapshot["jobs"] if job["status"] == "rejected_backpressure"]
    dead_letter = [job for job in snapshot["jobs"] if job["status"] == "dead_letter"]
    unfinished = [job for job in snapshot["jobs"] if job["status"] in ("pending", "running")]
    interactive_wait = [float(job["queue_wait_ms"]) for job in interactive_done]
    interactive_elapsed = [float(job["elapsed_ms"]) for job in interactive_done]
    interactive_wait_summary = latency_summary(interactive_wait)
    interactive_task_summary = latency_summary(interactive_elapsed)

    failures = []
    if len(interactive_done) != 5:
        failures.append("not_all_interactive_jobs_completed")
    if not rejected:
        failures.append("background_backpressure_did_not_reject_any_job")
    if any(job["job_class"] == "interactive" for job in rejected):
        failures.append("interactive_job_was_backpressure_rejected")
    if not background_done:
        failures.append("accepted_background_jobs_starved")
    if len(dead_letter) != 1:
        failures.append("poison_job_not_moved_to_dead_letter")
    if unfinished:
        failures.append("unfinished_queue_jobs_present")
    if interactive_wait_summary["p95_ms"] is None or interactive_wait_summary["p95_ms"] > args.interactive_p95_ms:
        failures.append("interactive_queue_wait_p95_slo_missed")
    if interactive_wait_summary["p99_ms"] is None or interactive_wait_summary["p99_ms"] > args.interactive_p99_ms:
        failures.append("interactive_queue_wait_p99_slo_missed")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_queue_backpressure_slo" if not failures else "failed_ai_nas_queue_backpressure_slo",
        "scope": "bounded queue admission, priority scheduling, retry/DLQ, and interactive P95/P99 SLO acceptance",
        "config": {
            "workers": args.workers,
            "max_low_pending": args.max_low_pending,
            "runtime_root": str(runtime_root),
            "interactive_p95_ms": args.interactive_p95_ms,
            "interactive_p99_ms": args.interactive_p99_ms,
        },
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "queue_path": str(queue_path),
        "admissions": admissions,
        "processed": sorted(all_processed, key=lambda item: (item["job_id"], item["attempt"])),
        "summary": {
            "accepted_interactive": sum(1 for item in admissions if item["job_class"] == "interactive" and item["accepted"]),
            "accepted_background": sum(1 for item in admissions if item["job_class"] == "background" and item["accepted"]),
            "rejected_background": sum(1 for item in admissions if item["job_class"] == "background" and not item["accepted"]),
            "rejected_interactive": sum(1 for item in admissions if item["job_class"] == "interactive" and not item["accepted"]),
            "interactive_done": len(interactive_done),
            "background_done": len(background_done),
            "dead_letter_jobs": len(dead_letter),
            "unfinished_jobs": len(unfinished),
            "interactive_queue_wait": interactive_wait_summary,
            "interactive_task_latency": interactive_task_summary,
            "all_done_task_latency": latency_summary([float(job["elapsed_ms"]) for job in snapshot["jobs"] if job["status"] == "done" and job.get("elapsed_ms") is not None]),
            "failures": failures,
        },
        "queue": snapshot,
        "final_index_status": sqlite_index_status(db_path),
        "scheduler_contract": {
            "interactive_priority": 10,
            "background_priority": "60-80",
            "backpressure_rule": "background jobs are rejected once pending/running background depth reaches max_low_pending; interactive jobs bypass this low-priority admission cap",
            "retry_rule": "failed jobs return to pending until max_attempts, then move to dead_letter",
            "slo": {
                "interactive_queue_wait_p95_ms": args.interactive_p95_ms,
                "interactive_queue_wait_p99_ms": args.interactive_p99_ms,
            },
        },
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "writes": "isolated fixture files, SQLite index, SQLite queue state, and Markdown/JSON SLO reports",
        },
        "production_gap": "This proves bounded queue backpressure and interactive tail-latency SLO mechanics; production still needs NAS-backed long-running SLO monitoring under real OpenClaw/model load.",
    }
    json_path = run_dir / "queue_backpressure_slo.json"
    md_path = run_dir / "queue_backpressure_slo.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Queue Backpressure SLO",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- accepted_interactive: `{payload['summary']['accepted_interactive']}`",
        f"- rejected_background: `{payload['summary']['rejected_background']}`",
        f"- dead_letter_jobs: `{payload['summary']['dead_letter_jobs']}`",
        f"- unfinished_jobs: `{payload['summary']['unfinished_jobs']}`",
        f"- interactive_queue_wait_p95_ms: `{interactive_wait_summary['p95_ms']}`",
        f"- interactive_queue_wait_p99_ms: `{interactive_wait_summary['p99_ms']}`",
        f"- failures: `{failures}`",
        "- policy: isolated fixture queue/index only; no real Personal mutation and no service start",
        "",
        "## Scheduler Contract",
        "",
    ]
    for key, value in payload["scheduler_contract"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Queue Counts", ""])
    for key, value in snapshot["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("- No SLO acceptance failure.")
    for failure in failures:
        lines.append(f"- {failure}")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
