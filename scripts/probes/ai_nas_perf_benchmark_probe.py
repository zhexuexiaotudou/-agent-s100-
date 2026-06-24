#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
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
    search_embedding_index,
    search_sqlite_index,
    sqlite_index_status,
)
from ai_nas_folder_rag_probe import folder_query_matches, load_folder_records


DEFAULT_QUERIES = [
    "2024 renovation payment contract invoice reimbursement",
    "invoice screenshot 2024",
    "beach photo 2024",
    "white car photo 2024",
    "paper notes local AI NAS",
]
DEFAULT_FOLDER_RAG_QUESTION = "What payment dates and amounts are in this folder?"


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def latency_summary(samples_ms: list[float]) -> dict:
    return {
        "count": len(samples_ms),
        "min_ms": round(min(samples_ms), 3) if samples_ms else None,
        "max_ms": round(max(samples_ms), 3) if samples_ms else None,
        "avg_ms": round(statistics.mean(samples_ms), 3) if samples_ms else None,
        "p50_ms": round(percentile(samples_ms, 50), 3) if samples_ms else None,
        "p95_ms": round(percentile(samples_ms, 95), 3) if samples_ms else None,
        "p99_ms": round(percentile(samples_ms, 99), 3) if samples_ms else None,
    }


def timed_search(db_path: Path, query: str, limit: int) -> dict:
    started = time.perf_counter()
    matches = search_sqlite_index(db_path, query, limit)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "task_type": "search",
        "query": query,
        "ok": True,
        "elapsed_ms": round(elapsed_ms, 3),
        "match_count": len(matches),
    }


def timed_embedding_search(db_path: Path, query: str, limit: int) -> dict:
    started = time.perf_counter()
    matches = search_embedding_index(db_path, query, limit)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "task_type": "embedding_search",
        "query": query,
        "ok": True,
        "elapsed_ms": round(elapsed_ms, 3),
        "match_count": len(matches),
    }


def timed_folder_rag(db_path: Path, folder: str, question: str, limit: int) -> dict:
    started = time.perf_counter()
    records = load_folder_records(db_path, folder)
    matches = folder_query_matches(records, question, limit)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "task_type": "folder_rag",
        "folder": folder,
        "query": question,
        "ok": True,
        "elapsed_ms": round(elapsed_ms, 3),
        "folder_file_count": len(records),
        "match_count": len(matches),
    }


def timed_index(personal_root: Path, db_path: Path, max_files: int) -> dict:
    started = time.perf_counter()
    status = build_sqlite_inventory(personal_root, db_path, max_files=max_files)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "task_type": "index",
        "ok": True,
        "elapsed_ms": round(elapsed_ms, 3),
        "status": status.get("status"),
        "file_count": status.get("file_count"),
        "failed_count": status.get("failed_count"),
        "last_run": status.get("last_run"),
    }


def run_task(job: dict, personal_root: Path, db_path: Path, limit: int, max_files: int) -> dict:
    dequeued = time.perf_counter()
    result = {
        "job_id": job["job_id"],
        "task_type": job["task_type"],
        "submitted_offset_ms": round(job["submitted_offset_ms"], 3),
        "queue_wait_ms": round((dequeued - job["submitted_at"]) * 1000.0, 3),
    }
    try:
        if job["task_type"] == "index":
            result.update(timed_index(personal_root, db_path, max_files))
        elif job["task_type"] == "embedding_search":
            result.update(timed_embedding_search(db_path, job["query"], limit))
        elif job["task_type"] == "folder_rag":
            result.update(timed_folder_rag(db_path, job.get("folder", "Documents"), job["query"], limit))
        else:
            result.update(timed_search(db_path, job["query"], limit))
    except Exception as exc:  # pragma: no cover - filesystem/sqlite dependent
        result.update(
            {
                "ok": False,
                "elapsed_ms": round((time.perf_counter() - dequeued) * 1000.0, 3),
                "error": f"{type(exc).__name__}:{exc}",
            }
        )
    return result


def task_latency_summaries(results: list[dict]) -> dict:
    task_types = sorted({item.get("task_type") for item in results if item.get("ok")})
    return {
        task_type: latency_summary(
            [item["elapsed_ms"] for item in results if item.get("ok") and item.get("task_type") == task_type]
        )
        for task_type in task_types
    }


def persist_benchmark_run(db_path: Path, payload: dict, json_path: Path) -> dict:
    con = open_sqlite_connection(db_path, timeout=30)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS perf_benchmark_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                verdict TEXT NOT NULL,
                report_json_path TEXT NOT NULL,
                summary_json TEXT NOT NULL
            )
            """
        )
        summary = {
            "sequential_search": payload.get("sequential_search"),
            "concurrent_queue": {
                "jobs": payload.get("concurrent_queue", {}).get("jobs"),
                "workers": payload.get("concurrent_queue", {}).get("workers"),
                "throughput_jobs_per_s": payload.get("concurrent_queue", {}).get("throughput_jobs_per_s"),
                "queue_wait": payload.get("concurrent_queue", {}).get("queue_wait"),
                "all_task_latency": payload.get("concurrent_queue", {}).get("all_task_latency"),
                "task_latencies": payload.get("concurrent_queue", {}).get("task_latencies"),
                "failure_count": len(payload.get("concurrent_queue", {}).get("failures", [])),
            },
        }
        cur = con.execute(
            """
            INSERT INTO perf_benchmark_runs(created_at, verdict, report_json_path, summary_json)
            VALUES (?, ?, ?, ?)
            """,
            (iso_now(), payload["verdict"], str(json_path), json.dumps(summary, ensure_ascii=False)),
        )
        con.commit()
        recent = [
            {
                "id": row[0],
                "created_at": row[1],
                "verdict": row[2],
                "report_json_path": row[3],
                "summary": json.loads(row[4]),
            }
            for row in con.execute(
                """
                SELECT id, created_at, verdict, report_json_path, summary_json
                FROM perf_benchmark_runs
                ORDER BY id DESC
                LIMIT 5
                """
            )
        ]
        return {"run_id": int(cur.lastrowid), "recent_runs": recent}
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS P95/P99 and concurrent mixed workload benchmark.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--concurrent-jobs", type=int, default=30)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--folder-rag-folder", default="Documents")
    parser.add_argument("--folder-rag-question", default=DEFAULT_FOLDER_RAG_QUESTION)
    args = parser.parse_args()

    args.iterations = max(1, args.iterations)
    args.concurrent_jobs = max(1, args.concurrent_jobs)
    args.workers = max(1, args.workers)

    warmup_started = time.perf_counter()
    warmup_status = build_sqlite_inventory(args.personal_root, args.sqlite_index_path, max_files=args.max_files)
    warmup_ms = (time.perf_counter() - warmup_started) * 1000.0

    sequential_results = []
    seq_started = time.perf_counter()
    for idx in range(args.iterations):
        query = DEFAULT_QUERIES[idx % len(DEFAULT_QUERIES)]
        sequential_results.append(timed_search(args.sqlite_index_path, query, args.limit))
    seq_elapsed_s = time.perf_counter() - seq_started

    queue_started = time.perf_counter()
    jobs = []
    index_job_position = max(0, args.concurrent_jobs // 3)
    for idx in range(args.concurrent_jobs):
        if idx == index_job_position:
            task_type = "index"
        elif idx % 5 == 0:
            task_type = "folder_rag"
        elif idx % 3 == 0:
            task_type = "embedding_search"
        else:
            task_type = "search"
        query = args.folder_rag_question if task_type == "folder_rag" else DEFAULT_QUERIES[idx % len(DEFAULT_QUERIES)]
        jobs.append(
            {
                "job_id": idx + 1,
                "task_type": task_type,
                "query": query,
                "folder": args.folder_rag_folder,
                "submitted_at": time.perf_counter(),
                "submitted_offset_ms": (time.perf_counter() - queue_started) * 1000.0,
            }
        )

    concurrent_results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(run_task, job, args.personal_root, args.sqlite_index_path, args.limit, args.max_files)
            for job in jobs
        ]
        for future in as_completed(futures):
            concurrent_results.append(future.result())
    queue_elapsed_s = time.perf_counter() - queue_started
    concurrent_results.sort(key=lambda item: item["job_id"])

    seq_latencies = [item["elapsed_ms"] for item in sequential_results if item.get("ok")]
    concurrent_search_latencies = [
        item["elapsed_ms"]
        for item in concurrent_results
        if item.get("ok") and item.get("task_type") == "search"
    ]
    concurrent_all_latencies = [item["elapsed_ms"] for item in concurrent_results if item.get("ok")]
    queue_waits = [item["queue_wait_ms"] for item in concurrent_results]
    failures = [item for item in concurrent_results if not item.get("ok")]
    final_status = sqlite_index_status(args.sqlite_index_path)

    payload = {
        "verdict": "ok_ai_nas_perf_benchmark" if not failures else "failed_ai_nas_perf_benchmark",
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "warmup": {
            "elapsed_ms": round(warmup_ms, 3),
            "status": warmup_status.get("status"),
            "file_count": warmup_status.get("file_count"),
            "failed_count": warmup_status.get("failed_count"),
        },
        "sequential_search": {
            "iterations": args.iterations,
            "elapsed_s": round(seq_elapsed_s, 3),
            "throughput_qps": round(args.iterations / seq_elapsed_s, 3) if seq_elapsed_s else None,
            "latency": latency_summary(seq_latencies),
        },
        "concurrent_queue": {
            "jobs": args.concurrent_jobs,
            "workers": args.workers,
            "elapsed_s": round(queue_elapsed_s, 3),
            "throughput_jobs_per_s": round(args.concurrent_jobs / queue_elapsed_s, 3) if queue_elapsed_s else None,
            "queue_wait": latency_summary(queue_waits),
            "all_task_latency": latency_summary(concurrent_all_latencies),
            "search_latency": latency_summary(concurrent_search_latencies),
            "task_latencies": task_latency_summaries(concurrent_results),
            "task_counts": {
                task_type: sum(1 for item in concurrent_results if item.get("task_type") == task_type)
                for task_type in sorted({item.get("task_type") for item in concurrent_results})
            },
            "index_jobs": [item for item in concurrent_results if item.get("task_type") == "index"],
            "failures": failures,
        },
        "final_index_status": final_status,
        "results": {
            "sequential": sequential_results,
            "concurrent": concurrent_results,
        },
    }

    run_dir = ensure_report_dir(args.report_root, "perf_benchmark")
    json_path = run_dir / "perf_benchmark.json"
    md_path = run_dir / "perf_benchmark.md"
    history = persist_benchmark_run(args.sqlite_index_path, payload, json_path)
    payload["history"] = history
    safe_write_json(json_path, payload)

    seq = payload["sequential_search"]
    conc = payload["concurrent_queue"]
    lines = [
        "# AI-NAS Performance Benchmark",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- personal_root: `{payload['personal_root']}`",
        f"- sqlite_index_path: `{payload['sqlite_index_path']}`",
        f"- warmup_ms: `{payload['warmup']['elapsed_ms']}`",
        "",
        "## Sequential Search",
        "",
        f"- iterations: `{seq['iterations']}`",
        f"- throughput_qps: `{seq['throughput_qps']}`",
        f"- p50_ms: `{seq['latency']['p50_ms']}`",
        f"- p95_ms: `{seq['latency']['p95_ms']}`",
        f"- p99_ms: `{seq['latency']['p99_ms']}`",
        "",
        "## Concurrent Queue",
        "",
        f"- jobs: `{conc['jobs']}`",
        f"- workers: `{conc['workers']}`",
        f"- throughput_jobs_per_s: `{conc['throughput_jobs_per_s']}`",
        f"- queue_wait_p95_ms: `{conc['queue_wait']['p95_ms']}`",
        f"- all_task_p95_ms: `{conc['all_task_latency']['p95_ms']}`",
        f"- all_task_p99_ms: `{conc['all_task_latency']['p99_ms']}`",
        f"- search_p95_ms: `{conc['search_latency']['p95_ms']}`",
        f"- search_p99_ms: `{conc['search_latency']['p99_ms']}`",
        f"- task_counts: `{conc['task_counts']}`",
        f"- failures: `{len(conc['failures'])}`",
        "",
        "## Mixed Task Latencies",
        "",
    ]
    for task_type, summary in conc["task_latencies"].items():
        lines.append(
            f"- `{task_type}` count `{summary['count']}` p50 `{summary['p50_ms']}` "
            f"p95 `{summary['p95_ms']}` p99 `{summary['p99_ms']}`"
        )
    lines.extend(
        [
        "",
        "## Index Jobs",
        "",
        ]
    )
    for item in conc["index_jobs"]:
        lines.append(
            f"- job `{item['job_id']}` | elapsed_ms `{item.get('elapsed_ms')}` | "
            f"status `{item.get('status')}` | failed_count `{item.get('failed_count')}`"
        )
    lines.extend(["", "## Benchmark History", ""])
    lines.append(f"- current_run_id: `{history['run_id']}`")
    for item in history["recent_runs"]:
        summary = item["summary"]["concurrent_queue"]
        all_task = summary.get("all_task_latency") or {}
        lines.append(
            f"- run `{item['id']}` `{item['created_at']}` verdict `{item['verdict']}` "
            f"jobs `{summary['jobs']}` all_task_p95 `{all_task.get('p95_ms')}` "
            f"all_task_p99 `{all_task.get('p99_ms')}`"
        )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
