#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
from collections import deque
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_bpu_headroom_slo"
SLOT_MS = 100
DEFAULT_TARGET_UTIL = 94.0
DEFAULT_MIN_AVG_UTIL = 93.0
DEFAULT_MAX_AVG_UTIL = 95.0
DEFAULT_MAX_P95_UTIL = 96.0
DEFAULT_MAX_P99_UTIL = 97.0
DEFAULT_MIN_P01_HEADROOM = 3.0
DEFAULT_INTERACTIVE_P95_WAIT_MS = 250.0
DEFAULT_INTERACTIVE_P99_WAIT_MS = 350.0
DEFAULT_BACKGROUND_THROUGHPUT_PER_S = 20.0


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


def summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "min": round(min(values), 4) if values else None,
        "max": round(max(values), 4) if values else None,
        "avg": round(statistics.mean(values), 4) if values else None,
        "p01": percentile(values, 0.01),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
    }


def add_job(queue: deque[dict], slot: int, job_class: str, task_type: str, bpu_cost: float, duration_slots: int = 1) -> None:
    queue.append(
        {
            "submitted_slot": slot,
            "job_class": job_class,
            "task_type": task_type,
            "bpu_cost": bpu_cost,
            "duration_slots": duration_slots,
        }
    )


def generate_workload(slot_count: int) -> tuple[deque[dict], deque[dict], dict]:
    interactive: deque[dict] = deque()
    background: deque[dict] = deque()
    arrivals = {"interactive": 0, "background": 0}
    for slot in range(slot_count):
        if slot % 2 == 0:
            add_job(interactive, slot, "interactive", "chat_search", 22.0)
            arrivals["interactive"] += 1
        if slot % 5 == 1:
            add_job(interactive, slot, "interactive", "approval_portal_refresh", 12.0)
            arrivals["interactive"] += 1
        if slot % 11 == 3:
            add_job(interactive, slot, "interactive", "folder_rag_question", 28.0)
            arrivals["interactive"] += 1
        for task_type, cost in [
            ("incremental_index_batch", 24.0),
            ("embedding_batch", 20.0),
            ("ocr_batch", 18.0),
            ("photo_phash_batch", 16.0),
            ("report_generation", 14.0),
            ("audit_flush", 10.0),
            ("freshness_scan", 8.0),
        ]:
            add_job(background, slot, "background", task_type, cost)
            arrivals["background"] += 1
    return interactive, background, arrivals


def claim_from_queue(queue: deque[dict], slot: int, remaining_budget: float) -> tuple[list[dict], float]:
    claimed = []
    ready = []
    future = deque()
    while queue:
        job = queue.popleft()
        if int(job["submitted_slot"]) <= slot:
            ready.append(job)
        else:
            future.append(job)
    ready.sort(key=lambda item: (-float(item["bpu_cost"]), int(item["submitted_slot"]), item["task_type"]))
    unclaimed = []
    for job in ready:
        if float(job["bpu_cost"]) > remaining_budget:
            unclaimed.append(job)
            continue
        job["claimed_slot"] = slot
        job["wait_ms"] = (slot - int(job["submitted_slot"])) * SLOT_MS
        claimed.append(job)
        remaining_budget -= float(job["bpu_cost"])
    unclaimed.sort(key=lambda item: (int(item["submitted_slot"]), item["task_type"], -float(item["bpu_cost"])))
    queue.extend(unclaimed)
    queue.extend(future)
    return claimed, remaining_budget


def simulate(slot_count: int, target_util: float) -> dict:
    interactive, background, arrivals = generate_workload(slot_count)
    completed: list[dict] = []
    slot_records = []
    throttled_background_slots = 0
    for slot in range(slot_count):
        remaining_budget = target_util
        slot_jobs = []
        interactive_jobs, remaining_budget = claim_from_queue(interactive, slot, remaining_budget)
        slot_jobs.extend(interactive_jobs)
        before_background = len(background)
        background_jobs, remaining_budget = claim_from_queue(background, slot, remaining_budget)
        slot_jobs.extend(background_jobs)
        if len(background) == before_background and background:
            throttled_background_slots += 1
        used = round(target_util - remaining_budget, 4)
        completed.extend(slot_jobs)
        slot_records.append(
            {
                "slot": slot,
                "utilization_pct": used,
                "headroom_pct": round(100.0 - used, 4),
                "interactive_completed": sum(1 for job in slot_jobs if job["job_class"] == "interactive"),
                "background_completed": sum(1 for job in slot_jobs if job["job_class"] == "background"),
                "queued_interactive": len(interactive),
                "queued_background": len(background),
            }
        )
    elapsed_s = slot_count * SLOT_MS / 1000.0
    interactive_done = [job for job in completed if job["job_class"] == "interactive"]
    background_done = [job for job in completed if job["job_class"] == "background"]
    return {
        "arrivals": arrivals,
        "completed": {
            "interactive": len(interactive_done),
            "background": len(background_done),
            "total": len(completed),
        },
        "remaining_queue": {
            "interactive": len(interactive),
            "background": len(background),
        },
        "elapsed_s": elapsed_s,
        "background_throughput_jobs_per_s": round(len(background_done) / elapsed_s, 4),
        "throttled_background_slots": throttled_background_slots,
        "utilization": summary([item["utilization_pct"] for item in slot_records]),
        "headroom": summary([item["headroom_pct"] for item in slot_records]),
        "interactive_wait_ms": summary([float(job["wait_ms"]) for job in interactive_done]),
        "background_wait_ms": summary([float(job["wait_ms"]) for job in background_done]),
        "slot_records_preview": slot_records[:12],
        "completed_preview": completed[:12],
    }


def evaluate(sim: dict, args: argparse.Namespace) -> list[str]:
    failures = []
    util = sim["utilization"]
    headroom = sim["headroom"]
    interactive_wait = sim["interactive_wait_ms"]
    if sim["remaining_queue"]["interactive"] != 0:
        failures.append("interactive_queue_not_drained")
    if sim["completed"]["background"] <= 0:
        failures.append("background_jobs_starved")
    if sim["background_throughput_jobs_per_s"] < args.min_background_throughput:
        failures.append("background_throughput_below_slo")
    if util["avg"] is None or not (args.min_avg_util <= util["avg"] <= args.max_avg_util):
        failures.append("average_bpu_utilization_outside_headroom_band")
    if util["p95"] is None or util["p95"] > args.max_p95_util:
        failures.append("bpu_utilization_p95_too_high")
    if util["p99"] is None or util["p99"] > args.max_p99_util:
        failures.append("bpu_utilization_p99_too_high")
    if util["max"] is None or util["max"] >= 100.0:
        failures.append("bpu_utilization_reached_100_percent")
    if headroom["p01"] is None or headroom["p01"] < args.min_p01_headroom:
        failures.append("bpu_headroom_p01_below_slo")
    if interactive_wait["p95"] is None or interactive_wait["p95"] > args.interactive_p95_wait_ms:
        failures.append("interactive_queue_wait_p95_too_high")
    if interactive_wait["p99"] is None or interactive_wait["p99"] > args.interactive_p99_wait_ms:
        failures.append("interactive_queue_wait_p99_too_high")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS BPU headroom, P95/P99, and queue scheduling SLO contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--slots", type=int, default=120)
    parser.add_argument("--target-util", type=float, default=DEFAULT_TARGET_UTIL)
    parser.add_argument("--min-avg-util", type=float, default=DEFAULT_MIN_AVG_UTIL)
    parser.add_argument("--max-avg-util", type=float, default=DEFAULT_MAX_AVG_UTIL)
    parser.add_argument("--max-p95-util", type=float, default=DEFAULT_MAX_P95_UTIL)
    parser.add_argument("--max-p99-util", type=float, default=DEFAULT_MAX_P99_UTIL)
    parser.add_argument("--min-p01-headroom", type=float, default=DEFAULT_MIN_P01_HEADROOM)
    parser.add_argument("--interactive-p95-wait-ms", type=float, default=DEFAULT_INTERACTIVE_P95_WAIT_MS)
    parser.add_argument("--interactive-p99-wait-ms", type=float, default=DEFAULT_INTERACTIVE_P99_WAIT_MS)
    parser.add_argument("--min-background-throughput", type=float, default=DEFAULT_BACKGROUND_THROUGHPUT_PER_S)
    args = parser.parse_args()

    args.slots = max(10, args.slots)
    sim = simulate(args.slots, args.target_util)
    failures = evaluate(sim, args)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_bpu_headroom_slo" if not failures else "failed_ai_nas_bpu_headroom_slo",
        "scope": "bounded scheduling contract proving BPU headroom is preserved while P95/P99 queue SLOs and background throughput remain acceptable",
        "policy": {
            "do_not_target_100_percent_average_bpu": True,
            "target_utilization_pct": args.target_util,
            "accepted_average_band_pct": [args.min_avg_util, args.max_avg_util],
            "max_p95_util_pct": args.max_p95_util,
            "max_p99_util_pct": args.max_p99_util,
            "min_p01_headroom_pct": args.min_p01_headroom,
            "interactive_priority": True,
            "background_uses_remaining_headroom": True,
        },
        "simulation": sim,
        "summary": {
            "average_utilization_pct": sim["utilization"]["avg"],
            "p95_utilization_pct": sim["utilization"]["p95"],
            "p99_utilization_pct": sim["utilization"]["p99"],
            "p01_headroom_pct": sim["headroom"]["p01"],
            "interactive_wait_p95_ms": sim["interactive_wait_ms"]["p95"],
            "interactive_wait_p99_ms": sim["interactive_wait_ms"]["p99"],
            "background_throughput_jobs_per_s": sim["background_throughput_jobs_per_s"],
            "interactive_remaining": sim["remaining_queue"]["interactive"],
            "background_remaining": sim["remaining_queue"]["background"],
            "failures": failures,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "download_performed": False,
            "network_call_performed": False,
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON BPU headroom SLO report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "bpu_headroom_slo")
    json_path = run_dir / "bpu_headroom_slo.json"
    md_path = run_dir / "bpu_headroom_slo.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS BPU Headroom SLO",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- average_utilization_pct: `{payload['summary']['average_utilization_pct']}`",
        f"- p95_utilization_pct: `{payload['summary']['p95_utilization_pct']}`",
        f"- p99_utilization_pct: `{payload['summary']['p99_utilization_pct']}`",
        f"- p01_headroom_pct: `{payload['summary']['p01_headroom_pct']}`",
        f"- interactive_wait_p95_ms: `{payload['summary']['interactive_wait_p95_ms']}`",
        f"- interactive_wait_p99_ms: `{payload['summary']['interactive_wait_p99_ms']}`",
        f"- background_throughput_jobs_per_s: `{payload['summary']['background_throughput_jobs_per_s']}`",
        "- policy: preserve scheduling headroom; do not optimize for 100% average BPU utilization",
        "",
        "## Failures",
        "",
    ]
    if not failures:
        lines.append("- No BPU headroom SLO failure detected.")
    for failure in failures:
        lines.append(f"- {failure}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
