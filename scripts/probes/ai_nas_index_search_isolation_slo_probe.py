#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_index_search_isolation_slo"
TARGET_QUERY = "2024 renovation milestonezeta payment contract invoice"
TARGET_RELATIVE_PATH = "Documents/Contracts/2024-renovation-milestonezeta-contract.txt"


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


def prepare_fixture(root: Path, filler_count: int) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    contracts = docs / "Contracts"
    inbox = personal / "Inbox"
    photos = personal / "Photos"
    contracts.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    (personal / TARGET_RELATIVE_PATH).write_text(
        "\n".join(
            [
                "2024 renovation milestonezeta payment contract invoice.",
                "Original contract path must remain queryable while background indexing runs.",
                "Amount CNY 48000. Payment node 2024-04-16 final renovation milestone.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for idx in range(filler_count):
        (docs / f"renovation-background-note-{idx:03d}.txt").write_text(
            f"Background renovation note {idx}. Invoice receipt archive 2024. Queue isolation filler.\n",
            encoding="utf-8",
        )
    for idx in range(max(4, filler_count // 10)):
        (photos / f"beach-car-invoice-placeholder-{idx:02d}.txt").write_text(
            f"Photo placeholder {idx}. Beach car invoice screenshot metadata fallback.\n",
            encoding="utf-8",
        )
    return personal


def mutate_noise_file(personal_root: Path, cycle: int) -> None:
    target = personal_root / "Inbox" / f"background-index-noise-{cycle:03d}.txt"
    target.write_text(
        f"Background index noise cycle {cycle}. Updated at {time.time():.6f}. Contract invoice queue test.\n",
        encoding="utf-8",
    )
    if cycle % 3 == 0:
        stale = personal_root / "Inbox" / f"background-index-noise-{cycle - 2:03d}.txt"
        if stale.exists():
            stale.unlink()


def index_worker(personal_root: Path, db_path: Path, cycles: int, max_files: int, stop_event: threading.Event) -> list[dict]:
    results = []
    for cycle in range(1, cycles + 1):
        started = time.perf_counter()
        try:
            mutate_noise_file(personal_root, cycle)
            status = build_sqlite_inventory(personal_root, db_path, max_files=max_files)
            ok = status.get("status") in {"completed", "completed_with_failures"}
            result = {
                "cycle": cycle,
                "ok": ok,
                "status": status.get("status"),
                "file_count": status.get("file_count"),
                "failed_count": status.get("failed_count"),
                "last_run": status.get("last_run"),
            }
        except Exception as exc:  # pragma: no cover - runtime dependent
            result = {"cycle": cycle, "ok": False, "error": f"{type(exc).__name__}:{exc}"}
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        results.append(result)
        time.sleep(0.01)
    stop_event.set()
    return results


def search_worker(worker_id: int, db_path: Path, iterations: int, limit: int, stop_event: threading.Event) -> list[dict]:
    results = []
    for iteration in range(1, iterations + 1):
        started = time.perf_counter()
        try:
            matches = search_sqlite_index(db_path, TARGET_QUERY, limit=limit)
            top = matches[0] if matches else {}
            target_matches = [item for item in matches if item.get("relative_path") == TARGET_RELATIVE_PATH]
            ok = bool(matches) and bool(target_matches) and bool(top.get("reasons")) and bool(top.get("evidence"))
            result = {
                "worker_id": worker_id,
                "iteration": iteration,
                "ok": ok,
                "match_count": len(matches),
                "target_present": bool(target_matches),
                "top_relative_path": top.get("relative_path"),
                "top_confidence": top.get("confidence"),
                "top_reason_count": len(top.get("reasons") or []),
                "top_evidence_present": bool(top.get("evidence")),
                "source": top.get("source"),
            }
        except Exception as exc:  # pragma: no cover - runtime dependent
            result = {
                "worker_id": worker_id,
                "iteration": iteration,
                "ok": False,
                "error": f"{type(exc).__name__}:{exc}",
            }
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        results.append(result)
        if stop_event.is_set() and iteration >= max(3, iterations // 2):
            break
        time.sleep(0.005)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS bounded index/search isolation SLO acceptance.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--filler-count", type=int, default=80)
    parser.add_argument("--index-cycles", type=int, default=8)
    parser.add_argument("--search-workers", type=int, default=4)
    parser.add_argument("--search-iterations", type=int, default=12)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-files", type=int, default=1000)
    parser.add_argument("--max-search-p95-ms", type=float, default=250.0)
    parser.add_argument("--max-search-p99-ms", type=float, default=400.0)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "index_search_isolation_slo")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root, max(1, args.filler_count))
    db_path = run_dir / "index_search_isolation_slo.sqlite3"

    warmup_started = time.perf_counter()
    warmup_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    warmup_ms = (time.perf_counter() - warmup_started) * 1000
    stop_event = threading.Event()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.search_workers + 1) as executor:
        futures = [
            executor.submit(index_worker, personal_root, db_path, max(1, args.index_cycles), args.max_files, stop_event)
        ]
        for worker_id in range(1, args.search_workers + 1):
            futures.append(
                executor.submit(
                    search_worker,
                    worker_id,
                    db_path,
                    max(1, args.search_iterations),
                    args.limit,
                    stop_event,
                )
            )
        collected = [future.result() for future in as_completed(futures)]
    elapsed_ms = (time.perf_counter() - started) * 1000

    index_runs = []
    search_runs = []
    for batch in collected:
        if batch and "cycle" in batch[0]:
            index_runs.extend(batch)
        else:
            search_runs.extend(batch)
    search_latencies = [item["elapsed_ms"] for item in search_runs if item.get("ok")]
    failed_searches = [item for item in search_runs if not item.get("ok")]
    failed_index_runs = [item for item in index_runs if not item.get("ok")]
    search_latency = latency_summary(search_latencies)
    final_status = sqlite_index_status(db_path)

    blockers = []
    if warmup_status.get("status") not in {"completed", "completed_with_failures"}:
        blockers.append("warmup_index_not_completed")
    if failed_index_runs:
        blockers.append("background_index_run_failed")
    if failed_searches:
        blockers.append("interactive_search_failed_or_lost_evidence")
    if not search_latencies:
        blockers.append("no_successful_search_samples")
    if search_latency.get("p95_ms") is None or search_latency["p95_ms"] > args.max_search_p95_ms:
        blockers.append("interactive_search_p95_slo_missed")
    if search_latency.get("p99_ms") is None or search_latency["p99_ms"] > args.max_search_p99_ms:
        blockers.append("interactive_search_p99_slo_missed")
    if (final_status.get("failed_count") or 0) > 0:
        blockers.append("final_index_has_failed_files")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_index_search_isolation_slo" if not blockers else "failed_ai_nas_index_search_isolation_slo",
        "scope": "bounded fixture acceptance for interactive SQLite/FTS search while background indexing mutates and refreshes files",
        "fixture": {
            "personal_root": str(personal_root),
            "target_relative_path": TARGET_RELATIVE_PATH,
            "query": TARGET_QUERY,
            "filler_count": max(1, args.filler_count),
        },
        "sqlite_index_path": str(db_path),
        "warmup": {
            "elapsed_ms": round(warmup_ms, 3),
            "status": warmup_status.get("status"),
            "file_count": warmup_status.get("file_count"),
            "failed_count": warmup_status.get("failed_count"),
        },
        "summary": {
            "total_elapsed_ms": round(elapsed_ms, 3),
            "index_cycle_count": len(index_runs),
            "search_sample_count": len(search_runs),
            "successful_search_count": len(search_latencies),
            "failed_search_count": len(failed_searches),
            "failed_index_count": len(failed_index_runs),
            "search_latency": search_latency,
            "max_search_p95_ms": args.max_search_p95_ms,
            "max_search_p99_ms": args.max_search_p99_ms,
            "final_index_status": {
                "status": final_status.get("status"),
                "file_count": final_status.get("file_count"),
                "failed_count": final_status.get("failed_count"),
                "last_run": final_status.get("last_run"),
                "queue_progress": final_status.get("queue_progress"),
            },
            "blockers": blockers,
        },
        "index_runs": index_runs,
        "search_samples": search_runs,
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "delete_performed": False,
            "real_delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "service_restart_performed": False,
            "network_call_performed": False,
            "writes": "isolated fixture files, SQLite/FTS index, Markdown/JSON reports only",
        },
        "production_gap": "This is a bounded local SLO fixture. Production still needs NAS-backed long soak with real model/OpenClaw traffic and realistic corpus size.",
    }

    json_path = run_dir / "index_search_isolation_slo.json"
    md_path = run_dir / "index_search_isolation_slo.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Index/Search Isolation SLO",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- query: `{TARGET_QUERY}`",
        f"- target_relative_path: `{TARGET_RELATIVE_PATH}`",
        f"- index_cycle_count: `{payload['summary']['index_cycle_count']}`",
        f"- search_sample_count: `{payload['summary']['search_sample_count']}`",
        f"- failed_search_count: `{payload['summary']['failed_search_count']}`",
        f"- search_p95_ms: `{search_latency.get('p95_ms')}`",
        f"- search_p99_ms: `{search_latency.get('p99_ms')}`",
        f"- blockers: `{blockers}`",
        "",
        "## SLO",
        "",
        f"- max_search_p95_ms: `{args.max_search_p95_ms}`",
        f"- max_search_p99_ms: `{args.max_search_p99_ms}`",
        "",
        "## Audit",
        "",
        "- Isolated fixture only; no real Personal files, services, network calls, source moves, deletes, or overwrites.",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
