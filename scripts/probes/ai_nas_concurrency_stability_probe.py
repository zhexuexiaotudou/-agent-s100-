#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    iso_now,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    search_photo_semantic_index,
    search_sqlite_index,
    sqlite_index_status,
)


DEFAULT_SEARCH_QUERIES = [
    "2024 renovation payment contract invoice",
    "invoice screenshot",
    "beach photo",
    "white car",
    "paper notes local AI NAS",
]
DEFAULT_HEALTH_URLS = [
    "http://127.0.0.1:18888/health",
    "http://127.0.0.1:18789/health",
]


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


def check_health_url(url: str, timeout: float = 1.5) -> dict:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(2048).decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return {
                "url": url,
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "elapsed_ms": round(elapsed_ms, 3),
                "body_preview": body[:500],
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(1000).decode("utf-8", errors="replace")
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "url": url,
            "ok": False,
            "status": exc.code,
            "elapsed_ms": round(elapsed_ms, 3),
            "error": body[:500],
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "url": url,
            "ok": False,
            "elapsed_ms": round(elapsed_ms, 3),
            "error": f"{type(exc).__name__}:{exc}",
        }


def run_operation(job: dict, personal_root: Path, db_path: Path, limit: int, max_files: int, health_urls: list[str]) -> dict:
    started = time.perf_counter()
    result = {
        "job_id": job["job_id"],
        "task_type": job["task_type"],
        "submitted_offset_ms": round(job["submitted_offset_ms"], 3),
    }
    try:
        if job["task_type"] == "index_refresh":
            status = build_sqlite_inventory(personal_root, db_path, max_files=max_files)
            result.update(
                {
                    "ok": True,
                    "status": status.get("status"),
                    "file_count": status.get("file_count"),
                    "failed_count": status.get("failed_count"),
                }
            )
        elif job["task_type"] == "file_search":
            matches = search_sqlite_index(db_path, job["query"], limit=limit)
            result.update({"ok": True, "query": job["query"], "match_count": len(matches)})
        elif job["task_type"] == "embedding_search":
            matches = search_embedding_index(db_path, job["query"], limit=limit)
            result.update({"ok": True, "query": job["query"], "match_count": len(matches)})
        elif job["task_type"] == "photo_semantic_search":
            ensure_image_embeddings_for_photos(db_path, limit=max_files)
            matches = search_photo_semantic_index(db_path, job["query"], limit=limit)
            result.update({"ok": True, "query": job["query"], "match_count": len(matches)})
        elif job["task_type"] == "dialog_health":
            checks = [check_health_url(url) for url in health_urls]
            # Health checks are observational. Missing services become limited evidence, not a hard failure.
            result.update(
                {
                    "ok": True,
                    "health_ok_count": sum(1 for item in checks if item.get("ok")),
                    "health_total": len(checks),
                    "health": checks,
                }
            )
        else:
            raise ValueError(f"unsupported_task_type:{job['task_type']}")
    except Exception as exc:  # pragma: no cover - runtime dependent
        result.update({"ok": False, "error": f"{type(exc).__name__}:{exc}"})
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return result


def task_summaries(results: list[dict]) -> dict:
    return {
        task_type: latency_summary(
            [item["elapsed_ms"] for item in results if item.get("ok") and item.get("task_type") == task_type]
        )
        for task_type in sorted({item.get("task_type") for item in results})
    }


def persist_stability_run(db_path: Path, payload: dict, json_path: Path) -> dict:
    con = open_sqlite_connection(db_path, timeout=30)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS concurrency_stability_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                verdict TEXT NOT NULL,
                report_json_path TEXT NOT NULL,
                summary_json TEXT NOT NULL
            )
            """
        )
        summary = {
            "task_counts": payload["summary"]["task_counts"],
            "failure_count": payload["summary"]["failure_count"],
            "throughput_jobs_per_s": payload["summary"]["throughput_jobs_per_s"],
            "all_task_latency": payload["summary"]["all_task_latency"],
            "task_latencies": payload["summary"]["task_latencies"],
            "dialog_health": payload["summary"]["dialog_health"],
        }
        cur = con.execute(
            """
            INSERT INTO concurrency_stability_runs(created_at, verdict, report_json_path, summary_json)
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
                FROM concurrency_stability_runs
                ORDER BY id DESC
                LIMIT 5
                """
            )
        ]
        return {"run_id": int(cur.lastrowid), "recent_runs": recent}
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS concurrent index/search/dialog-health stability probe.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--health-url", action="append", default=[])
    args = parser.parse_args()

    args.cycles = max(1, args.cycles)
    args.workers = max(1, args.workers)
    health_urls = args.health_url or DEFAULT_HEALTH_URLS

    warmup_started = time.perf_counter()
    warmup_status = build_sqlite_inventory(args.personal_root, args.sqlite_index_path, max_files=args.max_files)
    warmup_ms = (time.perf_counter() - warmup_started) * 1000.0

    jobs = []
    queued_started = time.perf_counter()
    job_id = 1
    for cycle in range(args.cycles):
        for task_type, query in [
            ("index_refresh", ""),
            ("file_search", DEFAULT_SEARCH_QUERIES[cycle % len(DEFAULT_SEARCH_QUERIES)]),
            ("embedding_search", DEFAULT_SEARCH_QUERIES[(cycle + 1) % len(DEFAULT_SEARCH_QUERIES)]),
            ("photo_semantic_search", DEFAULT_SEARCH_QUERIES[(cycle + 2) % len(DEFAULT_SEARCH_QUERIES)]),
            ("dialog_health", ""),
        ]:
            jobs.append(
                {
                    "job_id": job_id,
                    "cycle": cycle + 1,
                    "task_type": task_type,
                    "query": query,
                    "submitted_offset_ms": (time.perf_counter() - queued_started) * 1000.0,
                }
            )
            job_id += 1

    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(run_operation, job, args.personal_root, args.sqlite_index_path, args.limit, args.max_files, health_urls)
            for job in jobs
        ]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed_s = time.perf_counter() - started
    results.sort(key=lambda item: item["job_id"])

    failures = [item for item in results if not item.get("ok")]
    health_jobs = [item for item in results if item.get("task_type") == "dialog_health"]
    health_checks = [check for item in health_jobs for check in item.get("health", [])]
    health_ok_count = sum(1 for item in health_checks if item.get("ok"))
    health_error_count = sum(1 for item in health_checks if not item.get("ok"))
    error_taxonomy = {}
    for item in failures:
        key = str(item.get("error", "unknown_error")).split(":", 1)[0]
        error_taxonomy[key] = error_taxonomy.get(key, 0) + 1
    for item in health_checks:
        if not item.get("ok"):
            key = str(item.get("error", f"http_{item.get('status', 'unknown')}")).split(":", 1)[0]
            error_taxonomy[f"dialog_health_{key}"] = error_taxonomy.get(f"dialog_health_{key}", 0) + 1

    ok_latencies = [item["elapsed_ms"] for item in results if item.get("ok")]
    if failures:
        verdict = "failed_ai_nas_concurrency_stability"
    elif health_error_count:
        verdict = "limited_ai_nas_concurrency_stability"
    else:
        verdict = "ok_ai_nas_concurrency_stability"

    payload = {
        "generated_at": iso_now(),
        "verdict": verdict,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "health_urls": health_urls,
        "config": {
            "cycles": args.cycles,
            "workers": args.workers,
            "limit": args.limit,
            "max_files": args.max_files,
        },
        "warmup": {
            "elapsed_ms": round(warmup_ms, 3),
            "status": warmup_status.get("status"),
            "file_count": warmup_status.get("file_count"),
            "failed_count": warmup_status.get("failed_count"),
        },
        "summary": {
            "jobs": len(jobs),
            "elapsed_s": round(elapsed_s, 3),
            "throughput_jobs_per_s": round(len(jobs) / elapsed_s, 3) if elapsed_s else None,
            "failure_count": len(failures),
            "task_counts": {
                task_type: sum(1 for item in results if item.get("task_type") == task_type)
                for task_type in sorted({item.get("task_type") for item in results})
            },
            "all_task_latency": latency_summary(ok_latencies),
            "task_latencies": task_summaries(results),
            "dialog_health": {
                "jobs": len(health_jobs),
                "checks": len(health_checks),
                "ok_count": health_ok_count,
                "error_count": health_error_count,
                "latency": latency_summary([item["elapsed_ms"] for item in health_checks]),
            },
            "error_taxonomy": error_taxonomy,
        },
        "final_index_status": sqlite_index_status(args.sqlite_index_path),
        "results": results,
        "audit": {
            "tool_id": "ai_nas_concurrency_stability",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "SQLite index/history rows plus Markdown/JSON report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "concurrency_stability")
    json_path = run_dir / "concurrency_stability.json"
    md_path = run_dir / "concurrency_stability.md"
    history = persist_stability_run(args.sqlite_index_path, payload, json_path)
    payload["history"] = history
    safe_write_json(json_path, payload)

    summary = payload["summary"]
    lines = [
        "# AI-NAS Concurrency Stability",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- jobs: `{summary['jobs']}`",
        f"- workers: `{args.workers}`",
        f"- throughput_jobs_per_s: `{summary['throughput_jobs_per_s']}`",
        f"- all_task_p95_ms: `{summary['all_task_latency']['p95_ms']}`",
        f"- all_task_p99_ms: `{summary['all_task_latency']['p99_ms']}`",
        f"- failure_count: `{summary['failure_count']}`",
        f"- dialog_health_ok: `{summary['dialog_health']['ok_count']}/{summary['dialog_health']['checks']}`",
        "- policy: report/index/history only; no delete, no move, no service restart",
        "",
        "## Task Latencies",
        "",
    ]
    for task_type, item in summary["task_latencies"].items():
        lines.append(
            f"- `{task_type}` count `{item['count']}` p50 `{item['p50_ms']}` "
            f"p95 `{item['p95_ms']}` p99 `{item['p99_ms']}`"
        )
    lines.extend(["", "## Error Taxonomy", ""])
    if not summary["error_taxonomy"]:
        lines.append("- No task failures or dialog-health errors recorded.")
    for key, count in summary["error_taxonomy"].items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Index Refresh Jobs", ""])
    for item in results:
        if item.get("task_type") == "index_refresh":
            lines.append(
                f"- job `{item['job_id']}` elapsed_ms `{item['elapsed_ms']}` "
                f"status `{item.get('status')}` failed_count `{item.get('failed_count')}`"
            )
    lines.extend(["", "## Dialog Health Checks", ""])
    for item in health_jobs:
        for check in item.get("health", []):
            lines.append(
                f"- job `{item['job_id']}` `{check['url']}` ok `{check.get('ok')}` "
                f"elapsed_ms `{check.get('elapsed_ms')}` error `{check.get('error', '')}`"
            )
    lines.extend(["", "## History", ""])
    lines.append(f"- current_run_id: `{history['run_id']}`")
    for item in history["recent_runs"]:
        run_summary = item["summary"]
        all_task = run_summary.get("all_task_latency") or {}
        lines.append(
            f"- run `{item['id']}` `{item['created_at']}` verdict `{item['verdict']}` "
            f"jobs `{sum(run_summary.get('task_counts', {}).values())}` "
            f"p95 `{all_task.get('p95_ms')}` p99 `{all_task.get('p99_ms')}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
