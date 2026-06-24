#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_samples(text: str) -> list[float]:
    return [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", text)]


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(values) - 1)
    frac = rank - low
    return values[low] * (1.0 - frac) + values[high] * frac


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Dream7B BPU telemetry.")
    parser.add_argument("--monitor-stdout", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    samples = parse_samples(args.monitor_stdout.read_text(encoding="utf-8", errors="replace"))
    nonzero = [item for item in samples if item > 0.0]
    report = load_json(args.report_json)
    latency_ms = report.get("latency_ms") or report.get("latencies_ms") or []
    if not isinstance(latency_ms, list):
        latency_ms = []

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "backend": args.backend,
        "source_monitor_stdout": str(args.monitor_stdout),
        "source_report_json": str(args.report_json) if args.report_json else None,
        "avg_bpu_loading": round(statistics.fmean(samples), 3) if samples else 0.0,
        "avg_nonzero_bpu_loading": round(statistics.fmean(nonzero), 3) if nonzero else 0.0,
        "max_bpu_loading": max(samples) if samples else 0.0,
        "bpu_loading_sample_count": len(samples),
        "nonzero_bpu_loading_sample_count": len(nonzero),
        "zero_bpu_loading_sample_count": len(samples) - len(nonzero),
        "tokens_per_second": report.get("tokens_per_second") or report.get("tokens/s"),
        "ttft_ms": report.get("ttft_ms") or report.get("TTFT"),
        "tpot_ms": report.get("tpot_ms") or report.get("TPOT"),
        "latency_p50_ms": percentile([float(item) for item in latency_ms], 0.50),
        "latency_p95_ms": percentile([float(item) for item in latency_ms], 0.95),
        "latency_p99_ms": percentile([float(item) for item in latency_ms], 0.99),
        "queue_wait_ms": report.get("queue_wait_ms"),
        "failed_jobs": report.get("failed_job_count") if "failed_job_count" in report else report.get("failed_jobs"),
        "final_logits_time_ms": report.get("final_logits_time_ms") or report.get("final_segment_overhead_ms"),
        "cpu_usage_percent": report.get("cpu_usage_percent"),
        "ram_usage_mb": report.get("ram_usage_mb"),
        "raw_report_keys": sorted(report.keys()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
