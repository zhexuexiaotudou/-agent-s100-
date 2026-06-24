#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ANALYSIS_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_TELEMETRY_ROOT = Path("tmp/remote_true_batch_reports")
DEFAULT_OUT_JSON = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_post_instrumentation_telemetry_gate_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_post_instrumentation_telemetry_gate_20260621.md"

REQUIRED_TIMING_SUMMARY_FIELDS = [
    "total_input_prepare_ms",
    "input_prepare_fraction_of_wall",
    "total_output_postprocess_ms",
    "output_postprocess_fraction_of_wall",
]

REQUIRED_SEGMENT_FIELDS = [
    "input_prepare_ms",
    "avg_input_prepare_ms",
    "output_postprocess_ms",
    "avg_output_postprocess_ms",
]


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def timing_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("timing_summary")
    return summary if isinstance(summary, dict) else {}


def segment_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("group_rows") or []:
        if not isinstance(group, dict):
            continue
        for row in group.get("segment_rows") or []:
            if isinstance(row, dict):
                rows.append(row)
    return rows


def has_required_post_instrumentation_fields(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    summary = timing_summary(payload)
    for key in REQUIRED_TIMING_SUMMARY_FIELDS:
        if summary.get(key) is None:
            missing.append(f"timing_summary.{key}")

    rows = segment_rows(payload)
    if not rows:
        missing.append("group_rows[].segment_rows")
    else:
        sample = rows[0]
        for key in REQUIRED_SEGMENT_FIELDS:
            if key not in sample:
                missing.append(f"group_rows[].segment_rows[].{key}")

    return not missing, missing


def groups_text(payload: dict[str, Any]) -> str:
    ranges: list[str] = []
    for group in payload.get("groups") or []:
        if not isinstance(group, dict):
            continue
        ranges.append(f"{group.get('start')}:{group.get('end')}")
    return ",".join(ranges)


def telemetry_row(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    has_fields, missing = has_required_post_instrumentation_fields(payload)
    return {
        "path": str(path),
        "name": path.name,
        "generated_at": payload.get("generated_at"),
        "verdict": payload.get("verdict"),
        "batch_size": payload.get("batch_size"),
        "microbatch_count": payload.get("microbatch_count"),
        "inner_order": payload.get("inner_order"),
        "groups": groups_text(payload),
        "release_gc_mode": payload.get("release_gc_mode"),
        "final_logits_mode": payload.get("final_logits_mode"),
        "processed_request_count": payload.get("processed_request_count"),
        "failed_job_count": payload.get("failed_job_count"),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "has_post_instrumentation_fields": has_fields,
        "missing_post_instrumentation_fields": missing,
    }


def collect_rows(roots: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*true_batch_group_major_telemetry.json"):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            payload = read_json(path)
            if not payload:
                continue
            if payload.get("batch_size") != 4:
                continue
            rows.append(telemetry_row(path, payload))
    return sorted(rows, key=lambda row: (str(row.get("generated_at") or ""), str(row.get("path") or "")))


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = collect_rows([args.telemetry_root, args.analysis_root])
    successful_rows = [
        row
        for row in rows
        if row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
        and int(row.get("processed_request_count") or 0) > 0
    ]
    post_rows = [row for row in successful_rows if row.get("has_post_instrumentation_fields") is True]
    baseline_rows = [
        row
        for row in successful_rows
        if row.get("microbatch_count") == 512
        and row.get("inner_order") == "segment-major"
        and row.get("groups") == "0:6,6:12,12:18,18:24,24:28"
        and row.get("final_logits_mode") in (None, "full")
    ]
    next_run_needed = len(post_rows) == 0
    next_run = {
        "purpose": "measure_post_instrumentation_input_prepare_and_output_postprocess_on_existing_mb512_baseline",
        "is_standard_sweep": False,
        "batch_size": 4,
        "microbatch_count": 512,
        "inner_order": "segment-major",
        "groups": "0:6,6:12,12:18,18:24,24:28",
        "final_logits_mode": "full",
        "release_gc_mode": "collect",
        "command": (
            "python3 /mnt/nas/openclaw/scripts/probes/"
            "dream7b_true_batch_group_major_telemetry_probe.py "
            "--hbm-root /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4 "
            "--batch-size 4 --microbatch-count 512 --inner-order segment-major "
            "--groups 0:6,6:12,12:18,18:24,24:28 --release-gc-mode collect "
            "--final-logits-mode full"
        ),
    }
    decision = {
        "post_instrumentation_telemetry_ready": not next_run_needed,
        "input_output_overhead_quantified": not next_run_needed,
        "do_not_claim_input_output_overhead_yet": next_run_needed,
        "run_more_standard_b4_runtime_sweeps_now": False,
        "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available": next_run_needed,
        "next_measurement": next_run if next_run_needed else None,
        "reason": (
            "probe_deployed_but_no_successful_b4_telemetry_contains_new_input_output_fields"
            if next_run_needed
            else "successful_b4_telemetry_contains_post_instrumentation_input_output_fields"
        ),
    }
    verdict = (
        "ok_dream7b_b4_post_instrumentation_telemetry_ready"
        if not next_run_needed
        else "blocked_dream7b_b4_post_instrumentation_telemetry_missing_measurement"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "telemetry_root": str(args.telemetry_root),
            "analysis_root": str(args.analysis_root),
        },
        "required_fields": {
            "timing_summary": REQUIRED_TIMING_SUMMARY_FIELDS,
            "segment_rows": REQUIRED_SEGMENT_FIELDS,
        },
        "coverage": {
            "b4_telemetry_count": len(rows),
            "successful_b4_telemetry_count": len(successful_rows),
            "post_instrumentation_success_count": len(post_rows),
            "baseline_mb512_segment_major_5g_success_count": len(baseline_rows),
            "latest_successful_b4": successful_rows[-1] if successful_rows else None,
            "latest_post_instrumentation_b4": post_rows[-1] if post_rows else None,
        },
        "decision": decision,
        "post_instrumentation_rows": post_rows,
        "baseline_rows": baseline_rows,
        "sample_missing_rows": [
            row
            for row in successful_rows
            if row.get("has_post_instrumentation_fields") is not True
        ][-5:],
        "audit": {
            "network_call_performed": False,
            "s100p_runtime_started": False,
            "compile_started": False,
            "delete_performed": False,
            "move_performed": False,
        },
    }


def render_md(path: Path, payload: dict[str, Any]) -> None:
    decision = payload["decision"]
    coverage = payload["coverage"]
    next_measurement = decision.get("next_measurement") or {}
    lines = [
        "# Dream7B B=4 Post-Instrumentation Telemetry Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- b4_telemetry_count: `{coverage['b4_telemetry_count']}`",
        f"- successful_b4_telemetry_count: `{coverage['successful_b4_telemetry_count']}`",
        f"- post_instrumentation_success_count: `{coverage['post_instrumentation_success_count']}`",
        f"- baseline_mb512_segment_major_5g_success_count: `{coverage['baseline_mb512_segment_major_5g_success_count']}`",
        f"- post_instrumentation_telemetry_ready: `{decision['post_instrumentation_telemetry_ready']}`",
        f"- input_output_overhead_quantified: `{decision['input_output_overhead_quantified']}`",
        f"- do_not_claim_input_output_overhead_yet: `{decision['do_not_claim_input_output_overhead_yet']}`",
        f"- run_more_standard_b4_runtime_sweeps_now: `{decision['run_more_standard_b4_runtime_sweeps_now']}`",
        f"- allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available: `{decision['allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available']}`",
        f"- reason: `{decision['reason']}`",
    ]
    if next_measurement:
        lines.extend(
            [
                "",
                "## Next Measurement",
                "",
                f"- purpose: `{next_measurement['purpose']}`",
                f"- is_standard_sweep: `{next_measurement['is_standard_sweep']}`",
                f"- microbatch_count: `{next_measurement['microbatch_count']}`",
                f"- inner_order: `{next_measurement['inner_order']}`",
                f"- groups: `{next_measurement['groups']}`",
                f"- command: `{next_measurement['command']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Audit",
            "",
            f"- network_call_performed: `{payload['audit']['network_call_performed']}`",
            f"- s100p_runtime_started: `{payload['audit']['s100p_runtime_started']}`",
            f"- compile_started: `{payload['audit']['compile_started']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--telemetry-root", type=Path, default=DEFAULT_TELEMETRY_ROOT)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    write_json(args.out_json, payload)
    render_md(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
