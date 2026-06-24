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
from ai_nas_folder_rag_probe import folder_query_matches, load_folder_records


TOOL_ID = "ai_nas_continuous_task_soak"
DEFAULT_QUERIES = [
    "2024 renovation payment contract invoice",
    "reimbursement invoice 2024 amount",
    "paper notes local AI NAS",
    "manual setup troubleshooting",
    "payment dates amounts",
]
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


def latency_summary(samples_ms: list[float]) -> dict:
    return {
        "count": len(samples_ms),
        "min_ms": round(min(samples_ms), 3) if samples_ms else None,
        "max_ms": round(max(samples_ms), 3) if samples_ms else None,
        "avg_ms": round(statistics.mean(samples_ms), 3) if samples_ms else None,
        "p50_ms": percentile(samples_ms, 0.50),
        "p95_ms": percentile(samples_ms, 0.95),
        "p99_ms": percentile(samples_ms, 0.99),
    }


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    inbox = personal / "Inbox"
    docs.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    (docs / "2024_renovation_contract.txt").write_text(
        "2024 renovation contract. Payment deposit 20000 CNY on 2024-03-01. Final 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    (docs / "2024_reimbursement_invoice.txt").write_text(
        "Reimbursement invoice. Amount 12000 CNY. Date 2024-04-15. Tax invoice INV-2024-0415.\n",
        encoding="utf-8",
    )
    (docs / "local_ai_nas_paper_notes.txt").write_text(
        "Research paper notes about local AI NAS indexing, retrieval, and reproducible evaluation.\n",
        encoding="utf-8",
    )
    (docs / "device_manual.txt").write_text(
        "User manual. Setup steps. Troubleshooting. Safety instructions.\n",
        encoding="utf-8",
    )
    (inbox / "payment_chat_screenshot_note.txt").write_text(
        "Chat screenshot note: renovation payment reminder and receipt photo pending review.\n",
        encoding="utf-8",
    )
    return personal


def open_queue(path: Path) -> sqlite3.Connection:
    con = open_sqlite_connection(path, timeout=30, isolation_level=None, row_factory=True)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wave INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL,
            submitted_monotonic REAL NOT NULL,
            claimed_monotonic REAL,
            finished_monotonic REAL,
            queue_wait_ms REAL,
            elapsed_ms REAL,
            result_json TEXT,
            error TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs(status, priority, id)")
    return con


def enqueue_wave(queue_path: Path, wave: int, jobs_per_wave: int, started_monotonic: float) -> list[int]:
    con = open_queue(queue_path)
    ids = []
    try:
        for idx in range(jobs_per_wave):
            if idx % 6 == 0:
                task_type = "index"
                payload = {}
            elif idx % 5 == 0:
                task_type = "folder_rag"
                payload = {"folder": "Documents", "query": "What payment dates and amounts are in this folder?"}
            else:
                task_type = "search"
                payload = {"query": DEFAULT_QUERIES[idx % len(DEFAULT_QUERIES)]}
            cur = con.execute(
                """
                INSERT INTO jobs(wave, task_type, payload_json, status, priority, submitted_monotonic)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (wave, task_type, json.dumps(payload, ensure_ascii=False), idx, time.perf_counter() - started_monotonic),
            )
            ids.append(int(cur.lastrowid))
    finally:
        con.close()
    return ids


def claim_job(queue_path: Path, started_monotonic: float) -> dict | None:
    last_error: Exception | None = None
    for attempt in range(8):
        con = open_queue(queue_path)
        in_transaction = False
        try:
            con.execute("BEGIN IMMEDIATE")
            in_transaction = True
            row = con.execute(
                "SELECT * FROM jobs WHERE status='pending' ORDER BY priority ASC, id ASC LIMIT 1"
            ).fetchone()
            if not row:
                con.execute("COMMIT")
                return None
            claimed = time.perf_counter() - started_monotonic
            queue_wait_ms = (claimed - float(row["submitted_monotonic"])) * 1000
            con.execute(
                "UPDATE jobs SET status='running', claimed_monotonic=?, queue_wait_ms=? WHERE id=?",
                (claimed, round(queue_wait_ms, 3), row["id"]),
            )
            con.execute("COMMIT")
            item = dict(row)
            item["claimed_monotonic"] = claimed
            item["queue_wait_ms"] = round(queue_wait_ms, 3)
            return item
        except sqlite3.OperationalError as exc:
            last_error = exc
            if in_transaction:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
            if "locked" not in str(exc).lower():
                raise
            time.sleep(0.05 * (attempt + 1))
        except Exception:
            if in_transaction:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
            raise
        finally:
            con.close()
    raise RuntimeError(f"failed to claim queue job after lock retries: {last_error}")


def finish_job(queue_path: Path, job_id: int, ok: bool, started_monotonic: float, elapsed_ms: float, result: dict | None = None, error: str | None = None) -> None:
    last_error: Exception | None = None
    for attempt in range(8):
        con = open_queue(queue_path)
        try:
            con.execute(
                """
                UPDATE jobs
                SET status=?, finished_monotonic=?, elapsed_ms=?, result_json=?, error=?
                WHERE id=?
                """,
                (
                    "done" if ok else "failed",
                    time.perf_counter() - started_monotonic,
                    round(elapsed_ms, 3),
                    json.dumps(result or {}, ensure_ascii=False),
                    error,
                    job_id,
                ),
            )
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" not in str(exc).lower():
                raise
            time.sleep(0.05 * (attempt + 1))
        finally:
            con.close()
    raise RuntimeError(f"failed to finish queue job after lock retries: {last_error}")


def execute_job(job: dict, personal_root: Path, db_path: Path, limit: int, max_files: int) -> dict:
    payload = json.loads(job["payload_json"])
    if job["task_type"] == "index":
        with INDEX_REBUILD_LOCK:
            status = build_sqlite_inventory(personal_root, db_path, max_files=max_files)
        return {"status": status.get("status"), "file_count": status.get("file_count"), "failed_count": status.get("failed_count")}
    if job["task_type"] == "folder_rag":
        records = load_folder_records(db_path, payload.get("folder", "Documents"))
        matches = folder_query_matches(records, payload.get("query", ""), limit=limit)
        return {"folder_file_count": len(records), "match_count": len(matches)}
    if job["task_type"] == "search":
        matches = search_sqlite_index(db_path, payload.get("query", ""), limit=limit)
        return {"query": payload.get("query", ""), "match_count": len(matches)}
    raise ValueError(f"unsupported_task_type:{job['task_type']}")


def worker_loop(queue_path: Path, personal_root: Path, db_path: Path, limit: int, max_files: int, started_monotonic: float) -> list[dict]:
    processed = []
    while True:
        job = claim_job(queue_path, started_monotonic)
        if not job:
            break
        started = time.perf_counter()
        try:
            result = execute_job(job, personal_root, db_path, limit, max_files)
            elapsed_ms = (time.perf_counter() - started) * 1000
            finish_job(queue_path, job["id"], True, started_monotonic, elapsed_ms, result=result)
            processed.append(
                {
                    "job_id": job["id"],
                    "wave": job["wave"],
                    "task_type": job["task_type"],
                    "ok": True,
                    "queue_wait_ms": job["queue_wait_ms"],
                    "elapsed_ms": round(elapsed_ms, 3),
                    "result": result,
                }
            )
        except Exception as exc:  # pragma: no cover - runtime dependent
            elapsed_ms = (time.perf_counter() - started) * 1000
            error = f"{type(exc).__name__}:{exc}"
            finish_job(queue_path, job["id"], False, started_monotonic, elapsed_ms, error=error)
            processed.append(
                {
                    "job_id": job["id"],
                    "wave": job["wave"],
                    "task_type": job["task_type"],
                    "ok": False,
                    "queue_wait_ms": job["queue_wait_ms"],
                    "elapsed_ms": round(elapsed_ms, 3),
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
        rows = [dict(row) for row in con.execute("SELECT * FROM jobs ORDER BY id")]
    finally:
        con.close()
    return {"counts": counts, "jobs": rows}


def summarize_wave(results: list[dict], wave: int, elapsed_s: float) -> dict:
    items = [item for item in results if item["wave"] == wave]
    ok_items = [item for item in items if item.get("ok")]
    return {
        "wave": wave,
        "jobs": len(items),
        "ok_jobs": len(ok_items),
        "failed_jobs": len(items) - len(ok_items),
        "elapsed_s": round(elapsed_s, 3),
        "throughput_jobs_per_s": round(len(items) / elapsed_s, 3) if elapsed_s else None,
        "queue_wait": latency_summary([float(item["queue_wait_ms"]) for item in items]),
        "task_latency": latency_summary([float(item["elapsed_ms"]) for item in ok_items]),
        "task_counts": {
            task_type: sum(1 for item in items if item["task_type"] == task_type)
            for task_type in sorted({item["task_type"] for item in items})
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded continuous AI-NAS task soak over an isolated fixture queue.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=None,
        help="Optional local runtime directory for the fixture, SQLite index, and queue; reports still persist under report-root.",
    )
    parser.add_argument("--waves", type=int, default=5)
    parser.add_argument("--jobs-per-wave", type=int, default=14)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--wave-gap-seconds", type=float, default=0.05)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--max-task-p95-ms", type=float, default=250.0)
    parser.add_argument("--max-task-p99-ms", type=float, default=400.0)
    parser.add_argument("--max-queue-p99-ms", type=float, default=1000.0)
    parser.add_argument("--max-p95-degradation-ratio", type=float, default=3.0)
    parser.add_argument("--min-p95-baseline-ms", type=float, default=10.0)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "continuous_task_soak")
    runtime_root = args.runtime_root or (run_dir / "runtime")
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    fixture_root = args.fixture_root or (runtime_root / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = runtime_root / "continuous_task_soak.sqlite3"
    queue_path = runtime_root / "continuous_task_soak_queue.sqlite3"
    build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    started_monotonic = time.perf_counter()
    all_results = []
    wave_summaries = []
    for wave in range(1, max(1, args.waves) + 1):
        enqueue_wave(queue_path, wave, max(1, args.jobs_per_wave), started_monotonic)
        wave_started = time.perf_counter()
        wave_results = []
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [
                executor.submit(worker_loop, queue_path, personal_root, db_path, args.limit, args.max_files, started_monotonic)
                for _ in range(max(1, args.workers))
            ]
            for future in as_completed(futures):
                wave_results.extend(future.result())
        wave_elapsed_s = time.perf_counter() - wave_started
        wave_results.sort(key=lambda item: item["job_id"])
        all_results.extend(wave_results)
        wave_summaries.append(summarize_wave(wave_results, wave, wave_elapsed_s))
        if args.wave_gap_seconds:
            time.sleep(max(0.0, args.wave_gap_seconds))

    all_ok = [item for item in all_results if item.get("ok")]
    failures = [item for item in all_results if not item.get("ok")]
    first_p95 = wave_summaries[0]["task_latency"]["p95_ms"] if wave_summaries else None
    last_p95 = wave_summaries[-1]["task_latency"]["p95_ms"] if wave_summaries else None
    p95_degradation_denominator = max(float(first_p95 or 0), args.min_p95_baseline_ms)
    p95_degradation_ratio = round(float(last_p95) / p95_degradation_denominator, 4) if last_p95 else None
    queue = queue_snapshot(queue_path)
    unfinished = [job for job in queue["jobs"] if job["status"] != "done"]
    overall_queue_wait = latency_summary([float(item["queue_wait_ms"]) for item in all_results])
    overall_task_latency = latency_summary([float(item["elapsed_ms"]) for item in all_ok])
    blockers = []
    if failures:
        blockers.append("task_failures_present")
    if unfinished:
        blockers.append("unfinished_queue_jobs_present")
    if overall_task_latency["p95_ms"] is None or overall_task_latency["p95_ms"] > args.max_task_p95_ms:
        blockers.append("task_p95_slo_missed")
    if overall_task_latency["p99_ms"] is None or overall_task_latency["p99_ms"] > args.max_task_p99_ms:
        blockers.append("task_p99_slo_missed")
    if overall_queue_wait["p99_ms"] is None or overall_queue_wait["p99_ms"] > args.max_queue_p99_ms:
        blockers.append("queue_wait_p99_slo_missed")
    if p95_degradation_ratio and p95_degradation_ratio > args.max_p95_degradation_ratio:
        blockers.append("p95_degradation_ratio_slo_missed")
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_continuous_task_soak" if not blockers else "limited_ai_nas_continuous_task_soak",
        "scope": "bounded continuous multi-wave index/search/folder-RAG queue soak over an isolated fixture",
        "config": {
            "waves": args.waves,
            "jobs_per_wave": args.jobs_per_wave,
            "workers": args.workers,
            "runtime_root": str(runtime_root),
            "wave_gap_seconds": args.wave_gap_seconds,
            "max_task_p95_ms": args.max_task_p95_ms,
            "max_task_p99_ms": args.max_task_p99_ms,
            "max_queue_p99_ms": args.max_queue_p99_ms,
            "max_p95_degradation_ratio": args.max_p95_degradation_ratio,
            "min_p95_baseline_ms": args.min_p95_baseline_ms,
        },
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "queue_path": str(queue_path),
        "summary": {
            "total_jobs": len(all_results),
            "ok_jobs": len(all_ok),
            "failed_jobs": len(failures),
            "unfinished_jobs": len(unfinished),
            "overall_queue_wait": overall_queue_wait,
            "overall_task_latency": overall_task_latency,
            "overall_throughput_jobs_per_s": round(len(all_results) / max(0.001, sum(item["elapsed_s"] for item in wave_summaries)), 3),
            "p95_degradation_ratio_last_over_first": p95_degradation_ratio,
            "p95_degradation_denominator_ms": round(p95_degradation_denominator, 4),
            "blockers": blockers,
        },
        "wave_summaries": wave_summaries,
        "results": all_results,
        "queue": queue,
        "final_index_status": sqlite_index_status(db_path),
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "writes": "isolated fixture files, SQLite index, SQLite queue, and Markdown/JSON soak reports",
        },
        "production_gap": "This bounded soak proves multi-wave queue/latency/throughput telemetry; production still needs long-running NAS-backed soak under real OpenClaw and model-service load.",
    }
    json_path = run_dir / "continuous_task_soak.json"
    md_path = run_dir / "continuous_task_soak.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Continuous Task Soak",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- total_jobs: `{payload['summary']['total_jobs']}`",
        f"- ok_jobs: `{payload['summary']['ok_jobs']}`",
        f"- failed_jobs: `{payload['summary']['failed_jobs']}`",
        f"- unfinished_jobs: `{payload['summary']['unfinished_jobs']}`",
        f"- overall_throughput_jobs_per_s: `{payload['summary']['overall_throughput_jobs_per_s']}`",
        f"- queue_wait_p95_ms: `{payload['summary']['overall_queue_wait']['p95_ms']}`",
        f"- task_p95_ms: `{payload['summary']['overall_task_latency']['p95_ms']}`",
        f"- task_p99_ms: `{payload['summary']['overall_task_latency']['p99_ms']}`",
        f"- p95_degradation_ratio_last_over_first: `{p95_degradation_ratio}`",
        f"- p95_degradation_denominator_ms: `{payload['summary']['p95_degradation_denominator_ms']}`",
        f"- blockers: `{blockers}`",
        "- policy: isolated fixture queue/index only; no real Personal mutation and no service start",
        "",
        "## Waves",
        "",
    ]
    for item in wave_summaries:
        lines.append(
            f"- wave `{item['wave']}` jobs `{item['jobs']}` throughput `{item['throughput_jobs_per_s']}` "
            f"queue_p95 `{item['queue_wait']['p95_ms']}` task_p95 `{item['task_latency']['p95_ms']}` task_p99 `{item['task_latency']['p99_ms']}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures and not unfinished else 1


if __name__ == "__main__":
    raise SystemExit(main())
