#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sqlite_index_status,
)
from ai_nas_continuous_task_soak_probe import DEFAULT_QUERIES, latency_summary
from ai_nas_folder_rag_probe import folder_query_matches, load_folder_records


TOOL_ID = "ai_nas_nas_backed_long_soak"


def is_nas_root(path: Path) -> bool:
    text = str(path).replace("\\", "/")
    return text.startswith("/mnt/nas/") or text.startswith("//") or text.startswith("\\\\")


def run_search_wave(db_path: Path, limit: int) -> list[dict]:
    samples = []
    for query in DEFAULT_QUERIES:
        started = time.perf_counter()
        matches = search_sqlite_index(db_path, query, limit=limit)
        samples.append(
            {
                "task_type": "search",
                "query": query,
                "ok": True,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "match_count": len(matches),
            }
        )
    started = time.perf_counter()
    records = load_folder_records(db_path, "Documents")
    folder_matches = folder_query_matches(records, "What payment dates and amounts are in this folder?", limit=limit)
    samples.append(
        {
            "task_type": "folder_rag",
            "query": "Documents payment dates and amounts",
            "ok": True,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "match_count": len(folder_matches),
        }
    )
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a production NAS-backed long soak over real Personal data.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--duration-seconds", type=float, default=3600.0)
    parser.add_argument("--min-duration-seconds", type=float, default=3600.0)
    parser.add_argument("--wave-gap-seconds", type=float, default=10.0)
    parser.add_argument("--max-files", type=int, default=50000)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-file-count", type=int, default=100)
    parser.add_argument("--max-task-p95-ms", type=float, default=1000.0)
    parser.add_argument("--max-task-p99-ms", type=float, default=2500.0)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "nas_backed_long_soak")
    wave_results = []
    index_runs = []
    started = time.perf_counter()
    deadline = started + max(0.0, args.duration_seconds)
    wave = 0
    while True:
        wave += 1
        index_started = time.perf_counter()
        index_status = build_sqlite_inventory(args.personal_root, args.sqlite_index_path, max_files=args.max_files)
        index_runs.append(
            {
                "wave": wave,
                "elapsed_ms": round((time.perf_counter() - index_started) * 1000, 3),
                "status": index_status.get("status"),
                "file_count": index_status.get("file_count"),
                "failed_count": index_status.get("failed_count"),
                "last_run": index_status.get("last_run"),
            }
        )
        wave_results.extend({"wave": wave, **item} for item in run_search_wave(args.sqlite_index_path, args.limit))
        if time.perf_counter() >= deadline:
            break
        time.sleep(min(max(0.0, args.wave_gap_seconds), max(0.0, deadline - time.perf_counter())))

    elapsed_s = time.perf_counter() - started
    final_status = sqlite_index_status(args.sqlite_index_path)
    task_latencies = [float(item["elapsed_ms"]) for item in wave_results if item.get("ok")]
    search_failures = [item for item in wave_results if not item.get("ok")]
    index_failures = [item for item in index_runs if item.get("status") not in ("completed", "ready")]
    nas_backed = is_nas_root(args.personal_root)
    blockers = []
    if not args.personal_root.exists():
        blockers.append("personal_root_missing")
    if not nas_backed:
        blockers.append("personal_root_not_nas_backed")
    if elapsed_s < args.min_duration_seconds:
        blockers.append("duration_below_production_minimum")
    if int(final_status.get("file_count") or 0) < args.min_file_count:
        blockers.append("file_count_below_production_minimum")
    if int(final_status.get("failed_count") or 0) > 0:
        blockers.append("index_failed_files_present")
    if index_failures:
        blockers.append("index_wave_failures_present")
    if search_failures:
        blockers.append("search_wave_exceptions_present")
    task_summary = latency_summary(task_latencies)
    if task_summary["p95_ms"] is None or task_summary["p95_ms"] > args.max_task_p95_ms:
        blockers.append("task_p95_slo_missed")
    if task_summary["p99_ms"] is None or task_summary["p99_ms"] > args.max_task_p99_ms:
        blockers.append("task_p99_slo_missed")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_nas_backed_long_soak" if not blockers else "limited_ai_nas_nas_backed_long_soak",
        "scope": "long-running read-only index/search/folder-RAG soak over the configured Personal root",
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "config": {
            "duration_seconds": args.duration_seconds,
            "min_duration_seconds": args.min_duration_seconds,
            "wave_gap_seconds": args.wave_gap_seconds,
            "max_files": args.max_files,
            "min_file_count": args.min_file_count,
            "max_task_p95_ms": args.max_task_p95_ms,
            "max_task_p99_ms": args.max_task_p99_ms,
        },
        "summary": {
            "elapsed_seconds": round(elapsed_s, 3),
            "wave_count": wave,
            "nas_backed": nas_backed,
            "final_file_count": final_status.get("file_count"),
            "final_failed_count": final_status.get("failed_count"),
            "task_latency": task_summary,
            "avg_index_elapsed_ms": round(statistics.mean([item["elapsed_ms"] for item in index_runs]), 3) if index_runs else None,
            "blockers": blockers,
        },
        "index_runs": index_runs,
        "wave_results": wave_results,
        "final_index_status": final_status,
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "writes": "SQLite index refresh plus Markdown/JSON soak reports only",
        },
    }
    json_path = run_dir / "nas_backed_long_soak.json"
    md_path = run_dir / "nas_backed_long_soak.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS NAS-backed Long Soak",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- elapsed_seconds: `{payload['summary']['elapsed_seconds']}`",
        f"- wave_count: `{wave}`",
        f"- nas_backed: `{nas_backed}`",
        f"- final_file_count: `{payload['summary']['final_file_count']}`",
        f"- task_p95_ms: `{task_summary['p95_ms']}`",
        f"- task_p99_ms: `{task_summary['p99_ms']}`",
        f"- blockers: `{blockers}`",
        "- policy: read/index/search only; no real Personal delete, move, rename, overwrite, or service start",
        "",
        "## Audit",
        "",
    ]
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
