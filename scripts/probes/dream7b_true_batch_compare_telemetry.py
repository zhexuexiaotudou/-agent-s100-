#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--true-telemetry", required=True)
    parser.add_argument(
        "--queue-glob",
        default="/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_phase_timing_*/phase_timing_probe.json",
    )
    parser.add_argument("--report-root", default="/mnt/nas/openclaw/reports/models")
    args = parser.parse_args()

    true_path = Path(args.true_telemetry)
    true_payload = load_json(true_path)
    queue_paths = sorted(glob.glob(args.queue_glob))
    queue_payloads = []
    for path in queue_paths:
        try:
            payload = load_json(path)
        except Exception as exc:
            queue_payloads.append({"file": path, "error": f"{type(exc).__name__}:{exc}"})
            continue
        payload["file"] = path
        queue_payloads.append(payload)

    valid_queue = [
        item
        for item in queue_payloads
        if item.get("verdict") == "ok_dream7b_bpu_segment_major_phase_timing_probe"
        and as_float(item.get("processed_request_count")) > 0
        and as_float(item.get("failed_job_count")) == 0
    ]
    latest_queue = valid_queue[-1] if valid_queue else None
    best_queue_avg = max(valid_queue, key=lambda item: as_float(item.get("avg_bpu_loading")), default=None)
    best_queue_nonzero = max(valid_queue, key=lambda item: as_float(item.get("avg_nonzero_bpu_loading")), default=None)

    true_avg = as_float(true_payload.get("avg_bpu_loading"))
    true_nonzero = as_float(true_payload.get("avg_nonzero_bpu_loading"))
    true_max = as_float(true_payload.get("max_bpu_loading"))
    baseline = best_queue_avg or latest_queue
    baseline_avg = as_float(baseline.get("avg_bpu_loading")) if baseline else 0.0
    baseline_nonzero = as_float(baseline.get("avg_nonzero_bpu_loading")) if baseline else 0.0
    baseline_max = as_float(baseline.get("max_bpu_loading")) if baseline else 0.0

    errors = []
    if true_payload.get("verdict") != "ok_dream7b_true_batch_runtime_telemetry":
        errors.append(f"true_verdict={true_payload.get('verdict')}")
    expected_final_shape = true_payload.get("expected_final_shape") or [2, 16, 152064]
    if true_payload.get("chain_final_shape") != expected_final_shape:
        errors.append(f"true_final_shape={true_payload.get('chain_final_shape')}")
    if not valid_queue:
        errors.append("no_valid_queue_phase_timing_baseline")

    telemetry_improved = bool(
        baseline
        and true_avg > baseline_avg
        and true_nonzero >= baseline_nonzero
    )
    verdict = (
        "ok_true_batch_beats_queue_baseline"
        if not errors and telemetry_improved
        else "true_batch_runtime_ok_but_telemetry_not_better"
        if not errors
        else "failed_true_batch_telemetry_compare"
    )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.report_root) / f"dream7b_true_batch_telemetry_compare_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "telemetry_improved": telemetry_improved,
        "true_telemetry": {
            "file": str(true_path),
            "avg_bpu_loading": true_avg,
            "avg_nonzero_bpu_loading": true_nonzero,
            "max_bpu_loading": true_max,
            "sample_count": true_payload.get("bpu_loading_sample_count"),
            "nonzero_sample_count": true_payload.get("nonzero_bpu_loading_sample_count"),
            "chain_total_run_ms": true_payload.get("chain_total_run_ms"),
            "chain_wall_ms": true_payload.get("chain_wall_ms"),
            "chain_final_shape": true_payload.get("chain_final_shape"),
        },
        "queue_baseline": {
            "file": baseline.get("file") if baseline else None,
            "avg_bpu_loading": baseline_avg,
            "avg_nonzero_bpu_loading": baseline_nonzero,
            "max_bpu_loading": baseline_max,
            "processed_request_count": baseline.get("processed_request_count") if baseline else None,
            "failed_job_count": baseline.get("failed_job_count") if baseline else None,
            "wall_ms": baseline.get("wall_ms") if baseline else None,
            "run_ms": baseline.get("run_ms") if baseline else None,
            "amortized_wall_ms_per_processed_request": baseline.get("amortized_wall_ms_per_processed_request") if baseline else None,
        },
        "queue_latest": latest_queue,
        "queue_best_avg": best_queue_avg,
        "queue_best_nonzero": best_queue_nonzero,
        "queue_report_count": len(queue_payloads),
        "valid_queue_report_count": len(valid_queue),
        "errors": errors,
    }
    out_json = run_dir / "true_batch_telemetry_compare.json"
    out_md = run_dir / "true_batch_telemetry_compare.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B True Batch Telemetry Compare",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- telemetry_improved: {payload['telemetry_improved']}",
        f"- true_avg_bpu_loading: {true_avg}",
        f"- true_avg_nonzero_bpu_loading: {true_nonzero}",
        f"- true_max_bpu_loading: {true_max}",
        f"- queue_baseline_avg_bpu_loading: {baseline_avg}",
        f"- queue_baseline_avg_nonzero_bpu_loading: {baseline_nonzero}",
        f"- queue_baseline_max_bpu_loading: {baseline_max}",
        f"- true_chain_total_run_ms: {true_payload.get('chain_total_run_ms')}",
        f"- true_chain_wall_ms: {true_payload.get('chain_wall_ms')}",
        f"- queue_baseline_file: {payload['queue_baseline']['file']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
