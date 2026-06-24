#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def num(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def ratio_delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline in (None, 0):
        return None
    return (candidate - baseline) / baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Dream7B backend telemetry reports.")
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    queue = load(args.queue)
    candidate = load(args.candidate)
    failed_jobs = num(candidate, "failed_jobs")
    avg_bpu_delta = (num(candidate, "avg_bpu_loading") or 0.0) - (num(queue, "avg_bpu_loading") or 0.0)
    tokens_delta_ratio = ratio_delta(num(candidate, "tokens_per_second"), num(queue, "tokens_per_second"))
    p95_ttft_delta = ratio_delta(num(candidate, "ttft_ms"), num(queue, "ttft_ms"))
    p95_tpot_delta = ratio_delta(num(candidate, "tpot_ms"), num(queue, "tpot_ms"))
    p95_latency_delta = ratio_delta(num(candidate, "latency_p95_ms"), num(queue, "latency_p95_ms"))

    minimum_gate = {
        "failed_jobs_zero": failed_jobs == 0,
        "avg_bpu_within_1pct_of_queue": avg_bpu_delta >= -1.0,
        "tokens_per_second_15pct_above_queue": tokens_delta_ratio is not None and tokens_delta_ratio >= 0.15,
        "ttft_not_degraded_over_10pct": p95_ttft_delta is None or p95_ttft_delta <= 0.10,
        "tpot_not_degraded_over_10pct": p95_tpot_delta is None or p95_tpot_delta <= 0.10,
        "p95_latency_not_degraded_over_10pct": p95_latency_delta is None or p95_latency_delta <= 0.10,
    }
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "queue_file": str(args.queue),
        "candidate_file": str(args.candidate),
        "queue_backend": queue.get("backend"),
        "candidate_backend": candidate.get("backend"),
        "deltas": {
            "avg_bpu_loading_points": round(avg_bpu_delta, 3),
            "avg_nonzero_bpu_loading_points": round(
                (num(candidate, "avg_nonzero_bpu_loading") or 0.0)
                - (num(queue, "avg_nonzero_bpu_loading") or 0.0),
                3,
            ),
            "tokens_per_second_ratio": tokens_delta_ratio,
            "ttft_ratio": p95_ttft_delta,
            "tpot_ratio": p95_tpot_delta,
            "latency_p95_ratio": p95_latency_delta,
        },
        "minimum_gate": minimum_gate,
        "promotion_ready": all(minimum_gate.values()),
        "note": "Do not promote true-batch if only avg_nonzero_bpu_loading improves.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
