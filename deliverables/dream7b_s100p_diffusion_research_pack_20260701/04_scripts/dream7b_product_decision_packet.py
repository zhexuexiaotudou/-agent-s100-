#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def failure_segment(error: str | None) -> str | None:
    if not error:
        return None
    match = re.search(r"/(seg\d{2}_\d{2})/", error)
    if match:
        return match.group(1)
    match = re.search(r"(seg\d{2}_\d{2})", error)
    return match.group(1) if match else None


def latest_json(root: Path, pattern: str) -> Path | None:
    paths = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime)
    return paths[-1] if paths else None


def latest_json_or_fallback(root: Path, pattern: str, fallback: Path) -> Path:
    return latest_json(root, pattern) or fallback


def latest_json_with_verdict(root: Path, pattern: str, verdict: str) -> Path | None:
    paths = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime)
    for path in reversed(paths):
        try:
            if read_json(path).get("verdict") == verdict:
                return path
        except Exception:
            continue
    return paths[-1] if paths else None


def run_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_cmd(args: argparse.Namespace, remote_command: str, timeout: int = 30) -> dict[str, Any]:
    return run_cmd(
        [
            "ssh.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            remote_command,
        ],
        timeout=timeout,
    )


def parse_kv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def metric_row_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("metric")): row for row in rows}


def summarize_current_b4(schedule: dict[str, Any]) -> dict[str, Any]:
    runs = schedule.get("b4_true_batch_runs") or []
    latest_ok = [
        row
        for row in runs
        if row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
        and int(row.get("processed_request_count") or 0) > 0
    ]
    latest = max(latest_ok, key=lambda row: int(row.get("microbatch_count") or 0), default={})
    comparison = (schedule.get("comparisons") or {}).get("latest_b4_vs_queue_baseline") or {}
    mb512_split = (schedule.get("comparisons") or {}).get("group_split_mb512_segment_major") or {}
    release_gc_128 = (schedule.get("comparisons") or {}).get("release_gc_mb128_5_groups") or {}
    release_gc_512 = (schedule.get("comparisons") or {}).get("release_gc_mb512_5_groups") or {}
    failed = [
        row
        for row in runs
        if row.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry"
    ]
    failed_details = []
    for row in sorted(failed, key=lambda item: int(item.get("microbatch_count") or 0)):
        error = next(iter(row.get("errors") or []), "")
        failed_details.append(
            {
                "file": row.get("file"),
                "microbatch_count": row.get("microbatch_count"),
                "group_count": row.get("group_count"),
                "completed_group_count": row.get("completed_group_count"),
                "group_ranges": row.get("group_ranges"),
                "failed_segment": failure_segment(error),
                "processed_request_count": row.get("processed_request_count"),
                "error": error,
            }
        )
    return {
        "schedule_verdict": schedule.get("verdict"),
        "telemetry_count": len(runs),
        "successful_run_count": len(latest_ok),
        "failed_capacity_probe_count": len(failed),
        "failed_capacity_probe_details": failed_details,
        "latest_successful_file": latest.get("file"),
        "latest_microbatch_count": latest.get("microbatch_count"),
        "latest_processed_request_count": latest.get("processed_request_count"),
        "latest_avg_bpu_loading": latest.get("avg_bpu_loading"),
        "latest_avg_nonzero_bpu_loading": latest.get("avg_nonzero_bpu_loading"),
        "latest_ms_per_request": latest.get("amortized_wall_ms_per_request"),
        "avg_bpu_gap_points_vs_queue": comparison.get("avg_bpu_gap_points"),
        "nonzero_bpu_gap_points_vs_queue": comparison.get("nonzero_bpu_gap_points"),
        "ms_per_request_ratio_vs_queue": comparison.get("ms_per_request_ratio_vs_queue"),
        "mb512_six_group_ms_per_request_delta_vs_5_group": mb512_split.get(
            "six_group_ms_per_request_delta"
        ),
        "mb512_six_group_avg_bpu_delta_vs_5_group": mb512_split.get("six_group_avg_bpu_delta"),
        "mb512_six_group_nonzero_bpu_delta_vs_5_group": mb512_split.get(
            "six_group_nonzero_bpu_delta"
        ),
        "mb512_final_isolated_ms_per_request_delta_vs_5_group": mb512_split.get(
            "final_isolated_group_ms_per_request_delta"
        ),
        "mb512_final_isolated_avg_bpu_delta_vs_5_group": mb512_split.get(
            "final_isolated_group_avg_bpu_delta"
        ),
        "mb512_final_isolated_nonzero_bpu_delta_vs_5_group": mb512_split.get(
            "final_isolated_group_nonzero_bpu_delta"
        ),
        "mb512_seven_group_ms_per_request_delta_vs_5_group": mb512_split.get(
            "seven_group_ms_per_request_delta"
        ),
        "release_gc_skip_mb128_ms_per_request_delta": release_gc_128.get("skip_ms_per_request_delta"),
        "release_gc_skip_mb128_avg_bpu_delta": release_gc_128.get("skip_avg_bpu_delta"),
        "release_gc_skip_mb128_nonzero_bpu_delta": release_gc_128.get("skip_nonzero_bpu_delta"),
        "release_gc_skip_mb128_group_release_ms_delta": release_gc_128.get("skip_total_group_release_ms_delta"),
        "release_gc_skip_mb128_unaccounted_gap_ms_delta": release_gc_128.get("skip_unaccounted_gap_ms_delta"),
        "release_gc_skip_mb512_ms_per_request_delta": release_gc_512.get("skip_ms_per_request_delta"),
        "release_gc_skip_mb512_avg_bpu_delta": release_gc_512.get("skip_avg_bpu_delta"),
        "release_gc_skip_mb512_nonzero_bpu_delta": release_gc_512.get("skip_nonzero_bpu_delta"),
        "release_gc_skip_mb512_group_release_ms_delta": release_gc_512.get("skip_total_group_release_ms_delta"),
        "release_gc_skip_mb512_unaccounted_gap_ms_delta": release_gc_512.get("skip_unaccounted_gap_ms_delta"),
    }


def summarize_prealloc(prealloc: dict[str, Any]) -> dict[str, Any]:
    rows = metric_row_map(prealloc.get("rows") or [])
    return {
        "verdict": prealloc.get("verdict"),
        "report_interpretation": prealloc.get("interpretation") or [],
        "wall_ms_delta": (rows.get("wall_ms") or {}).get("delta_prealloc_minus_no_prealloc"),
        "ms_per_request_delta": (rows.get("ms_per_request") or {}).get("delta_prealloc_minus_no_prealloc"),
        "avg_bpu_delta": (rows.get("avg_bpu") or {}).get("delta_prealloc_minus_no_prealloc"),
        "hidden_materialize_ms_delta": (rows.get("total_hidden_materialize_ms") or {}).get(
            "delta_prealloc_minus_no_prealloc"
        ),
        "reused_hidden_buffer_count": (rows.get("reused_hidden_buffer_count") or {}).get("prealloc"),
        "decision": "experimental_flag_only",
    }


def summarize_group_split(group_split: dict[str, Any]) -> dict[str, Any]:
    rows = {row.get("label"): row for row in group_split.get("rows") or []}
    return {
        "verdict": group_split.get("verdict"),
        "g4_verdict": (rows.get("g4_capacity_failed") or {}).get("verdict"),
        "g4_error": (rows.get("g4_capacity_failed") or {}).get("error"),
        "g5_ms_per_request": (rows.get("g5_baseline") or {}).get("ms_per_request"),
        "g6_ms_per_request": (rows.get("g6_intermediate") or {}).get("ms_per_request"),
        "g6_minus_g5_delta": group_split.get("g6_minus_g5_delta") or {},
        "decision": group_split.get("decision") or [],
    }


def summarize_final_logits(final_logits: dict[str, Any]) -> dict[str, Any]:
    latest = final_logits.get("latest_non_prealloc_default_group") or {}
    return {
        "verdict": final_logits.get("verdict"),
        "analyzed_run_count": len(final_logits.get("runs") or []),
        "latest_microbatch_count": latest.get("microbatch_count"),
        "final_avg_run_ms": latest.get("final_avg_run_ms"),
        "hidden_mean_avg_run_ms": latest.get("hidden_mean_avg_run_ms"),
        "final_vs_hidden_avg_run_ratio": latest.get("final_vs_hidden_avg_run_ratio"),
        "final_segment_total_fraction_of_all_segment_total": latest.get(
            "final_segment_total_fraction_of_all_segment_total"
        ),
        "final_group_load_vs_non_final_mean_ratio": latest.get("final_group_load_vs_non_final_mean_ratio"),
        "interpretation": final_logits.get("interpretation") or [],
    }


def summarize_final_output(final_output: dict[str, Any]) -> dict[str, Any]:
    latest = final_output.get("latest_default_b4") or {}
    decision = final_output.get("decision") or {}
    queue = final_output.get("queue_raw_final_reference") or {}
    return {
        "verdict": final_output.get("verdict"),
        "latest_final_run_ms_per_request": latest.get("final_run_ms_per_request"),
        "latest_final_segment_overhead_ms_per_request": latest.get(
            "final_segment_overhead_ms_per_request"
        ),
        "latest_final_excess_ms_per_request_if_hidden_speed": latest.get(
            "final_excess_ms_per_request_if_hidden_speed"
        ),
        "queue_raw_final_overhead_ms_per_request": queue.get(
            "final_segment_overhead_ms_per_request"
        ),
        "b4_final_python_output_overhead_small": decision.get(
            "b4_final_python_output_overhead_small"
        ),
        "b4_final_excess_dominated_by_runtime_run": decision.get(
            "b4_final_excess_dominated_by_runtime_run"
        ),
        "recommended_next": decision.get("recommended_next"),
    }


def summarize_hbm_load(hbm_load: dict[str, Any]) -> dict[str, Any]:
    latest = hbm_load.get("latest_default_run") or {}
    decision = hbm_load.get("decision") or {}
    prewarm = hbm_load.get("prewarm_comparison") or {}
    slowest = hbm_load.get("slowest_load_segments_latest") or []
    top = slowest[0] if slowest else {}
    second = slowest[1] if len(slowest) > 1 else {}
    return {
        "verdict": hbm_load.get("verdict"),
        "analyzed_run_count": hbm_load.get("analyzed_run_count"),
        "latest_microbatch_count": latest.get("microbatch_count"),
        "total_group_load_ms_per_request": latest.get("total_group_load_ms_per_request"),
        "hidden_mean_load_ms": latest.get("hidden_mean_load_ms"),
        "hidden_stdev_load_ms": latest.get("hidden_stdev_load_ms"),
        "token_load_ms": latest.get("token_load_ms"),
        "final_load_ms": latest.get("final_load_ms"),
        "final_vs_hidden_load_ratio": latest.get("final_vs_hidden_load_ratio"),
        "slowest_load_segment": {
            "index": top.get("index"),
            "kind": top.get("kind"),
            "load_ms": top.get("load_ms"),
            "hbm_size_mib": top.get("hbm_size_mib"),
        },
        "second_slowest_load_segment": {
            "index": second.get("index"),
            "kind": second.get("kind"),
            "load_ms": second.get("load_ms"),
            "hbm_size_mib": second.get("hbm_size_mib"),
        },
        "per_segment_load_telemetry_ready": decision.get("per_segment_load_telemetry_ready"),
        "token_embedding_load_is_outlier": decision.get("token_embedding_load_is_outlier"),
        "final_logits_load_is_outlier": decision.get("final_logits_load_is_outlier"),
        "largest_load_group": decision.get("largest_load_group"),
        "final_group_is_largest_load_group": decision.get("final_group_is_largest_load_group"),
        "group_boundary_tuning_alone_not_primary": decision.get("group_boundary_tuning_alone_not_primary"),
        "continue_prioritizing_final_logits_compute_or_output_reduction": decision.get(
            "continue_prioritizing_final_logits_compute_or_output_reduction"
        ),
        "prewarm_hbm_default": decision.get("prewarm_hbm_default"),
        "prewarm_wall_ms_per_request_delta": prewarm.get("wall_ms_per_request_delta"),
        "prewarm_group_load_ms_delta": prewarm.get("group_load_ms_delta"),
        "prewarm_group_load_ms_per_request_delta": prewarm.get("group_load_ms_per_request_delta"),
        "prewarm_ms": prewarm.get("prewarm_ms"),
        "prewarm_mib": prewarm.get("prewarm_mib"),
        "prewarm_net_prewarm_plus_group_load_ms_delta": prewarm.get("net_prewarm_plus_group_load_ms_delta"),
    }


def summarize_bottleneck_closure_model(model: dict[str, Any]) -> dict[str, Any]:
    baseline = model.get("baseline") or {}
    components = model.get("components_ms_per_request") or {}
    decision = model.get("decision") or {}
    candidates = model.get("closure_candidates") or []
    top = candidates[0] if candidates else {}
    final_candidate = next(
        (
            row
            for row in candidates
            if row.get("name") == "seg27_28_last_token_logits_projection"
        ),
        {},
    )
    hbm_candidate = next(
        (
            row
            for row in candidates
            if row.get("name") == "perfect_hbm_group_load_residency"
        ),
        {},
    )
    return {
        "verdict": model.get("verdict"),
        "latest_microbatch_count": baseline.get("latest_microbatch_count"),
        "latest_ms_per_request": baseline.get("latest_ms_per_request"),
        "latest_avg_bpu_loading": baseline.get("latest_avg_bpu_loading"),
        "latest_avg_bpu_gap_to_queue_points": baseline.get(
            "latest_avg_bpu_gap_to_queue_points"
        ),
        "latest_nonzero_shortfall_points_for_93_avg": baseline.get(
            "latest_nonzero_shortfall_points_for_93_avg"
        ),
        "hbm_group_load_ms_per_request": components.get("hbm_group_load"),
        "release_plus_unaccounted_group_gap_ms_per_request": components.get(
            "release_plus_unaccounted_group_gap"
        ),
        "nonhidden_python_segment_overhead_ms_per_request": components.get(
            "nonhidden_python_segment_overhead"
        ),
        "hidden_materialize_ms_per_request": components.get("hidden_materialize"),
        "output_postprocess_ms_per_request": components.get("output_postprocess"),
        "final_logits_projection_saved_ms_per_request": components.get(
            "final_logits_last_token_projection"
        ),
        "top_closure_candidate": top.get("name"),
        "top_closure_saved_ms_per_request": top.get("estimated_saved_ms_per_request"),
        "top_closure_decision": top.get("decision"),
        "final_logits_projected_ms_per_request": final_candidate.get(
            "projected_ms_per_request"
        ),
        "final_logits_wall_only_projected_avg_bpu": final_candidate.get(
            "wall_only_projected_avg_bpu"
        ),
        "hbm_residency_projected_ms_per_request": hbm_candidate.get(
            "projected_ms_per_request"
        ),
        "hbm_residency_wall_only_projected_avg_bpu": hbm_candidate.get(
            "wall_only_projected_avg_bpu"
        ),
        "primary_next_code_target": decision.get("primary_next_code_target"),
        "small_python_and_gap_optimizations_combined_ms_per_request": decision.get(
            "small_python_and_gap_optimizations_combined_ms_per_request"
        ),
        "group_size_or_inner_order_current_primary_lever": decision.get(
            "group_size_or_inner_order_current_primary_lever"
        ),
        "run_more_group_size_or_inner_order_sweeps_now": decision.get(
            "run_more_group_size_or_inner_order_sweeps_now"
        ),
        "projection_is_not_bpu_promotion_proof": decision.get(
            "projection_is_not_bpu_promotion_proof"
        ),
        "requires_real_runtime_result_before_promotion": decision.get(
            "requires_real_runtime_result_before_promotion"
        ),
    }


def parse_markdown_kv(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        values[key.strip()] = value.strip()
    return values


def summarize_last_token_candidate(
    sizing: dict[str, Any],
    experiment_path: Path | None,
    remote_values: dict[str, str],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    current = sizing.get("current") or {}
    candidate = sizing.get("last_token_logits_candidate") or {}
    decision = sizing.get("decision") or {}
    experiment = parse_markdown_kv(experiment_path)
    remote_compiled = remote_values.get("last_token_manifest_verified") == "true"
    readiness_preflight = (readiness.get("preflight") or {}).get("values") or {}
    readiness_largest = next(iter(readiness.get("top_private_processes") or []), {})
    latest_largest_private_process = (
        f"{readiness_largest.get('path')}, pid {readiness_largest.get('pid')}, "
        f"private {readiness_largest.get('private_gb')} GB"
        if readiness_largest
        else None
    )
    return {
        "sizing_verdict": sizing.get("verdict"),
        "readiness_verdict": readiness.get("verdict"),
        "experiment_note": str(experiment_path) if experiment_path and experiment_path.exists() else None,
        "status": experiment.get("status") or "unknown",
        "compile_started": experiment.get("compile_started"),
        "compile_ready": readiness.get("compile_ready"),
        "runtime_validation_ready": readiness.get("runtime_validation_ready"),
        "readiness_blockers": readiness.get("blockers") or [],
        "normal_hbm_root": experiment.get("normal_hbm_root"),
        "alternate_final_hbm_root": experiment.get("alternate_final_hbm_root"),
        "remote_final_probe_has_final_hbm_root": remote_values.get("probe_has_final_hbm_root") == "true",
        "remote_final_probe_has_final_logits_mode": remote_values.get("probe_has_final_logits_mode") == "true",
        "remote_last_token_manifest_verified": remote_compiled,
        "remote_last_token_hbm_exists": remote_values.get("last_token_hbm_exists") == "true",
        "current_final_shape": current.get("final_shape"),
        "candidate_target_shape": candidate.get("target_shape"),
        "output_element_reduction_vs_current": candidate.get("output_element_reduction_vs_current"),
        "projection_only_hypothesis_saved_ms_per_request": candidate.get(
            "projection_only_hypothesis_saved_ms_per_request"
        ),
        "projection_only_hypothesis_final_run_ms_per_request": candidate.get(
            "projection_only_hypothesis_final_run_ms_per_request"
        ),
        "preflight_commit_headroom_gb": readiness_preflight.get("commit_headroom_gb")
        or experiment.get("preflight_commit_headroom_gb"),
        "preflight_min_commit_headroom_gb": readiness_preflight.get("min_commit_headroom_gb")
        or experiment.get("preflight_min_commit_headroom_gb"),
        "latest_preflight_commit_headroom_gb": readiness_preflight.get("commit_headroom_gb"),
        "latest_preflight_min_commit_headroom_gb": readiness_preflight.get("min_commit_headroom_gb"),
        "latest_preflight_commit_headroom_deficit_gb": readiness_preflight.get("commit_headroom_deficit_gb"),
        "latest_preflight_physical_available_gb": readiness_preflight.get("physical_available_gb"),
        "largest_private_process": latest_largest_private_process or experiment.get("largest_private_process"),
        "latest_largest_private_process": latest_largest_private_process,
        "compile_candidate": decision.get("compile_candidate"),
        "runtime_probe_change": decision.get("runtime_probe_change"),
        "promotion_gate": decision.get("promotion_gate"),
        "next_gate": "compile_manifest_verification_then_mb512_runtime_validation",
    }


def summarize_last_token_validation_compare(compare: dict[str, Any]) -> dict[str, Any]:
    decision = compare.get("decision") or {}
    candidate = compare.get("candidate") or {}
    baseline = compare.get("baseline") or {}
    deltas = compare.get("deltas_candidate_minus_baseline") or {}
    checks = compare.get("structural_checks") or {}
    return {
        "verdict": compare.get("verdict"),
        "decision": decision.get("decision"),
        "structural_ok": decision.get("structural_ok"),
        "performance_ok": decision.get("performance_ok"),
        "candidate_exists": candidate.get("exists"),
        "candidate_path": candidate.get("path"),
        "candidate_final_shape": candidate.get("final_shape"),
        "candidate_final_logits_mode": candidate.get("final_logits_mode"),
        "candidate_ms_per_request": candidate.get("ms_per_request"),
        "candidate_avg_bpu_loading": candidate.get("avg_bpu_loading"),
        "candidate_avg_nonzero_bpu_loading": candidate.get("avg_nonzero_bpu_loading"),
        "baseline_path": baseline.get("path"),
        "baseline_ms_per_request": baseline.get("ms_per_request"),
        "baseline_avg_bpu_loading": baseline.get("avg_bpu_loading"),
        "baseline_avg_nonzero_bpu_loading": baseline.get("avg_nonzero_bpu_loading"),
        "ms_per_request_delta": deltas.get("ms_per_request_delta"),
        "avg_bpu_loading_delta": deltas.get("avg_bpu_loading_delta"),
        "avg_nonzero_bpu_loading_delta": deltas.get("avg_nonzero_bpu_loading_delta"),
        "final_run_ms_per_request_delta": deltas.get("final_run_ms_per_request_delta"),
        "candidate_result_exists_check": checks.get("candidate_result_exists"),
        "do_not_promote_to_default": decision.get("do_not_promote_to_default"),
    }


def summarize_final_logits_leverage_model(model: dict[str, Any]) -> dict[str, Any]:
    current = model.get("current") or {}
    leverage = model.get("leverage") or {}
    bpu_gap = model.get("bpu_promotion_gap") or {}
    thresholds = model.get("validation_thresholds") or {}
    decision = model.get("decision") or {}
    return {
        "verdict": model.get("verdict"),
        "primary_candidate": decision.get("primary_candidate"),
        "projection_saved_ms_per_request": leverage.get("projection_saved_ms_per_request"),
        "final_excess_ms_per_request_if_hidden_speed": leverage.get(
            "final_excess_ms_per_request_if_hidden_speed"
        ),
        "projection_capture_of_final_excess_pct": leverage.get(
            "projection_capture_of_final_excess_pct"
        ),
        "latest_ms_per_request": current.get("latest_ms_per_request"),
        "latest_projected_ms_per_request_if_saved": leverage.get(
            "latest_projected_ms_per_request_if_saved"
        ),
        "latest_projected_latency_reduction_pct": leverage.get(
            "latest_projected_latency_reduction_pct"
        ),
        "mb512_projected_latency_reduction_pct": leverage.get(
            "mb512_projected_latency_reduction_pct"
        ),
        "final_run_reduction_pct_if_projection_holds": leverage.get(
            "final_run_reduction_pct_if_projection_holds"
        ),
        "projection_saved_to_group_switch_gap_ratio": leverage.get(
            "projection_saved_to_group_switch_gap_ratio"
        ),
        "latest_nonzero_bpu": bpu_gap.get("latest_nonzero_bpu"),
        "latest_required_nonzero_bpu_for_93_avg": bpu_gap.get(
            "latest_required_nonzero_bpu_for_93_avg"
        ),
        "latest_nonzero_shortfall_points": bpu_gap.get("latest_nonzero_shortfall_points"),
        "low_load_nonzero_shortfall_points": bpu_gap.get(
            "low_load_nonzero_shortfall_points"
        ),
        "projected_max_avg_bpu_if_nonzero_unchanged": bpu_gap.get(
            "projected_max_avg_bpu_if_nonzero_unchanged"
        ),
        "projected_max_still_below_93": bpu_gap.get("projected_max_still_below_93"),
        "min_wall_improvement_ms_per_request": thresholds.get(
            "min_wall_improvement_ms_per_request"
        ),
        "min_final_run_improvement_ms_per_request": thresholds.get(
            "min_final_run_improvement_ms_per_request"
        ),
        "max_nonzero_bpu_regression_points": thresholds.get(
            "max_nonzero_bpu_regression_points"
        ),
        "projection_closes_most_final_logits_excess": decision.get(
            "projection_closes_most_final_logits_excess"
        ),
        "projection_is_latency_meaningful": decision.get("projection_is_latency_meaningful"),
        "projection_is_not_bpu_promotion_proof": decision.get(
            "projection_is_not_bpu_promotion_proof"
        ),
        "do_not_promote_without_runtime_result": decision.get(
            "do_not_promote_without_runtime_result"
        ),
        "do_not_run_standard_group_or_inner_order_sweeps": decision.get(
            "do_not_run_standard_group_or_inner_order_sweeps"
        ),
        "current_compare_decision": decision.get("current_compare_decision"),
    }


def summarize_scaling_saturation(saturation: dict[str, Any]) -> dict[str, Any]:
    latest = saturation.get("latest_observed") or {}
    asymptotic = saturation.get("asymptotic_projection") or {}
    decision = saturation.get("decision") or {}
    return {
        "verdict": saturation.get("verdict"),
        "latest_microbatch_count": latest.get("microbatch_count"),
        "latest_avg_bpu_loading": latest.get("avg_bpu_loading"),
        "latest_avg_nonzero_bpu_loading": latest.get("avg_nonzero_bpu_loading"),
        "latest_ms_per_request": latest.get("ms_per_request"),
        "latest_required_nonzero_gap_to_observed_nonzero": latest.get(
            "latest_required_nonzero_gap_to_observed_nonzero"
        ),
        "required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction": asymptotic.get(
            "required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction"
        ),
        "projected_max_avg_bpu_if_nonzero_unchanged": asymptotic.get(
            "projected_max_avg_bpu_if_nonzero_unchanged"
        ),
        "projected_max_still_below_93": asymptotic.get("projected_max_still_below_93"),
        "microbatch_only_sweeps_deprioritized": decision.get("microbatch_only_sweeps_deprioritized"),
        "do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes": decision.get(
            "do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes"
        ),
        "next_runtime_candidate": decision.get("next_runtime_candidate"),
    }


def summarize_group_switch(group_switch: dict[str, Any]) -> dict[str, Any]:
    latest = group_switch.get("latest_default_summary") or {}
    latest_gap = group_switch.get("latest_gap_instrumented_summary") or {}
    decision = group_switch.get("decision") or {}
    return {
        "verdict": group_switch.get("verdict"),
        "latest_microbatch_count": latest.get("microbatch_count"),
        "group_load_ms_per_request": latest.get("group_load_ms_per_request"),
        "group_switch_gap_ms_per_request": latest.get("group_switch_gap_ms_per_request"),
        "group_release_ms_per_request": latest.get("group_release_ms_per_request"),
        "unaccounted_gap_ms_per_request": latest.get("unaccounted_gap_ms_per_request"),
        "segment_overhead_ms_per_request": latest.get("segment_overhead_ms_per_request"),
        "hidden_materialize_ms_per_request": latest.get("hidden_materialize_ms_per_request"),
        "inter_segment_first_run_gap_ms_per_request": latest.get(
            "inter_segment_first_run_gap_ms_per_request"
        ),
        "intra_segment_run_gap_ms_per_request": latest.get("intra_segment_run_gap_ms_per_request"),
        "segment_overhead_excluding_hidden_materialize_ms_per_request": latest.get(
            "segment_overhead_excluding_hidden_materialize_ms_per_request"
        ),
        "segment_overhead_excluding_measured_gaps_ms_per_request": latest.get(
            "segment_overhead_excluding_measured_gaps_ms_per_request"
        ),
        "latest_gap_file": latest_gap.get("file"),
        "latest_gap_microbatch_count": latest_gap.get("microbatch_count"),
        "latest_gap_ms_per_request": latest_gap.get("ms_per_request"),
        "latest_gap_avg_bpu_loading": latest_gap.get("avg_bpu_loading"),
        "latest_gap_inter_segment_first_run_gap_ms_per_request": latest_gap.get(
            "inter_segment_first_run_gap_ms_per_request"
        ),
        "latest_gap_intra_segment_run_gap_ms_per_request": latest_gap.get(
            "intra_segment_run_gap_ms_per_request"
        ),
        "latest_gap_residual_after_gaps_ms_per_request": latest_gap.get(
            "segment_overhead_excluding_measured_gaps_ms_per_request"
        ),
        "final_logits_excess_ms_per_request_if_hidden_speed": latest.get(
            "final_logits_excess_ms_per_request_if_hidden_speed"
        ),
        "group_load_to_switch_gap_ratio": latest.get("group_load_to_switch_gap_ratio"),
        "final_excess_to_switch_gap_ratio": latest.get("final_excess_to_switch_gap_ratio"),
        "group_release_and_unaccounted_gap_not_primary": decision.get(
            "group_release_and_unaccounted_gap_not_primary"
        ),
        "hbm_group_load_is_fixed_amortization_not_active_bpu_fix": decision.get(
            "hbm_group_load_is_fixed_amortization_not_active_bpu_fix"
        ),
        "segment_overhead_has_some_python_headroom_but_less_than_final_logits": decision.get(
            "segment_overhead_has_some_python_headroom_but_less_than_final_logits"
        ),
        "scheduler_followup": decision.get("scheduler_followup"),
    }


def summarize_runtime_boundary(boundary: dict[str, Any]) -> dict[str, Any]:
    summary = boundary.get("summary") or {}
    decision = boundary.get("decision") or {}
    return {
        "verdict": boundary.get("verdict"),
        "latest_successful_microbatch_count": summary.get("latest_successful_microbatch_count"),
        "latest_gap_success_microbatch_count": summary.get("latest_gap_success_microbatch_count"),
        "first_gap_failure_microbatch_count": summary.get("first_gap_failure_microbatch_count"),
        "gap_instrumented_success_boundary_microbatch_count": decision.get(
            "gap_instrumented_success_boundary_microbatch_count"
        ),
        "gap_instrumented_first_failed_microbatch_count": decision.get(
            "gap_instrumented_first_failed_microbatch_count"
        ),
        "do_not_continue_gap_microbatch_sweeps_above_success_boundary": decision.get(
            "do_not_continue_gap_microbatch_sweeps_above_success_boundary"
        ),
        "continue_prioritizing_final_logits_candidate": decision.get(
            "continue_prioritizing_final_logits_candidate"
        ),
        "reason": decision.get("reason"),
    }


def summarize_group_order_candidates(group_order: dict[str, Any]) -> dict[str, Any]:
    baseline = group_order.get("baseline") or {}
    decision = group_order.get("decision") or {}
    capacity = group_order.get("capacity_reference") or {}
    return {
        "verdict": group_order.get("verdict"),
        "baseline": decision.get("baseline"),
        "baseline_ms_per_request": baseline.get("ms_per_request"),
        "baseline_avg_bpu_loading": baseline.get("avg_bpu_loading"),
        "segment_major_preferred_over_microbatch_major": decision.get(
            "segment_major_preferred_over_microbatch_major"
        ),
        "best_nonbaseline_observed_variant": decision.get("best_nonbaseline_observed_variant"),
        "best_nonbaseline_observed_variant_delta_ms_per_request": decision.get(
            "best_nonbaseline_observed_variant_delta_ms_per_request"
        ),
        "no_observed_variant_beats_baseline": decision.get("no_observed_variant_beats_baseline"),
        "observed_group_order_variants_within_noise_band": decision.get(
            "observed_group_order_variants_within_noise_band"
        ),
        "more_mb512_group_boundary_sweeps_deprioritized": decision.get(
            "more_mb512_group_boundary_sweeps_deprioritized"
        ),
        "mb768_or_higher_group_sweeps_blocked_by_capacity_boundary": decision.get(
            "mb768_or_higher_group_sweeps_blocked_by_capacity_boundary"
        ),
        "only_capacity_probe_if_needed": decision.get("only_capacity_probe_if_needed"),
        "observed_success_peak_group_hbm_mib": capacity.get(
            "observed_success_peak_group_hbm_mib"
        ),
        "observed_failed_g4_peak_group_hbm_mib": capacity.get(
            "observed_failed_g4_peak_group_hbm_mib"
        ),
        "next_runtime_candidate": decision.get("next_runtime_candidate"),
        "reason": decision.get("reason"),
    }


def summarize_group_partition_planner(planner: dict[str, Any]) -> dict[str, Any]:
    decision = planner.get("decision") or {}
    baseline = planner.get("baseline") or {}
    counts = planner.get("recommendation_counts") or {}
    top_candidates = planner.get("top_capacity_probe_candidates") or []
    top = top_candidates[0] if top_candidates else {}
    observed = planner.get("observed_nonbaseline_variants") or []
    best_observed = min(
        observed,
        key=lambda row: as_float(row.get("observed_mb512_delta_ms_per_request")),
        default={},
    )
    return {
        "verdict": planner.get("verdict"),
        "candidate_count": (planner.get("inputs") or {}).get("candidate_count"),
        "run_new_partition_now": decision.get("run_new_partition_now"),
        "only_probe_if_memory_plan_changes": decision.get(
            "only_probe_if_memory_plan_changes"
        ),
        "baseline_group_ranges": baseline.get("group_ranges"),
        "baseline_max_group_hbm_mib": baseline.get("max_group_hbm_mib"),
        "observed_failed_g4_peak_group_hbm_mib": (
            planner.get("capacity_reference") or {}
        ).get("observed_failed_g4_peak_group_hbm_mib"),
        "top_capacity_probe_groups": top.get("group_ranges"),
        "top_capacity_probe_max_group_hbm_mib": top.get("max_group_hbm_mib"),
        "top_capacity_probe_peak_delta_pct": top.get("peak_hbm_delta_pct_vs_baseline"),
        "top_capacity_probe_release_delta_ms_per_request": top.get(
            "estimated_release_delta_ms_per_request"
        ),
        "observed_nonbaseline_count": len(observed),
        "best_observed_nonbaseline_delta_ms_per_request": best_observed.get(
            "observed_mb512_delta_ms_per_request"
        ),
        "capacity_probe_only_count": counts.get(
            "capacity_probe_only_if_memory_plan_changes"
        ),
        "do_not_run_more_group_switches_count": counts.get(
            "do_not_run_more_group_switches_without_memory_change"
        ),
        "reason": decision.get("reason"),
    }


def summarize_group_inner_order_value_audit(audit: dict[str, Any]) -> dict[str, Any]:
    summary = audit.get("summary") or {}
    decision = audit.get("decision") or {}
    rankings = audit.get("value_rankings") or []
    return {
        "verdict": audit.get("verdict"),
        "failed_checks": audit.get("failed_checks") or [],
        "baseline": summary.get("baseline"),
        "preferred_inner_order": summary.get("preferred_inner_order"),
        "preferred_group_policy": summary.get("preferred_group_policy"),
        "observed_nonbaseline_count": summary.get("observed_nonbaseline_count"),
        "best_nonbaseline_variant": summary.get("best_nonbaseline_variant"),
        "best_nonbaseline_delta_ms_per_request": summary.get(
            "best_nonbaseline_delta_ms_per_request"
        ),
        "slower_or_equal_nonbaseline_count": summary.get(
            "slower_or_equal_nonbaseline_count"
        ),
        "capacity_probe_only_candidate_count": summary.get(
            "capacity_probe_only_candidate_count"
        ),
        "final_logits_rank1_rate": summary.get("final_logits_rank1_rate"),
        "final_to_token_excess_ratio": summary.get("final_to_token_excess_ratio"),
        "final_to_max_hidden_excess_ratio": summary.get(
            "final_to_max_hidden_excess_ratio"
        ),
        "primary_code_target_projected_saved_ms_per_request": summary.get(
            "primary_code_target_projected_saved_ms_per_request"
        ),
        "run_more_group_size_or_inner_order_sweeps_now": decision.get(
            "run_more_group_size_or_inner_order_sweeps_now"
        ),
        "group_size_and_inner_order_are_current_primary_levers": decision.get(
            "group_size_and_inner_order_are_current_primary_levers"
        ),
        "only_capacity_probe_if_memory_plan_changes": decision.get(
            "only_capacity_probe_if_memory_plan_changes"
        ),
        "primary_runtime_candidate_before_new_group_sweeps": decision.get(
            "primary_runtime_candidate_before_new_group_sweeps"
        ),
        "next_s100p_runtime_experiment_allowed_now": decision.get(
            "next_s100p_runtime_experiment_allowed_now"
        ),
        "next_compile_allowed_now": decision.get("next_compile_allowed_now"),
        "top_value_lever": (rankings[0] if rankings else {}).get("lever"),
        "top_value_expected_value": (rankings[0] if rankings else {}).get(
            "expected_value"
        ),
    }


def summarize_true_batch_nas_inventory(inventory: dict[str, Any]) -> dict[str, Any]:
    remote = inventory.get("remote") or {}
    coverage = inventory.get("local_coverage") or {}
    decision = inventory.get("decision") or {}
    return {
        "verdict": inventory.get("verdict"),
        "remote_group_major_report_count": remote.get("group_major_report_count"),
        "remote_group_major_report_json_count": remote.get("group_major_report_json_count"),
        "remote_batch_counts": remote.get("batch_counts"),
        "remote_report_json_batch_counts": remote.get("report_json_batch_counts"),
        "missing_report_json_dirs": remote.get("missing_report_json_dirs") or [],
        "remote_b4_group_major_report_count": remote.get("b4_group_major_report_count"),
        "remote_b4_group_major_report_json_count": remote.get(
            "b4_group_major_report_json_count"
        ),
        "local_b4_json_count": coverage.get("local_b4_json_count"),
        "local_b4_successful_count": coverage.get("successful_count"),
        "local_b4_failed_count": coverage.get("failed_count"),
        "local_b4_by_microbatch_count": coverage.get("by_microbatch_count"),
        "local_b4_by_group_count": coverage.get("by_group_count"),
        "b4_hbm_count": remote.get("b4_hbm_count"),
        "b4_manifest_count": remote.get("b4_manifest_count"),
        "last_token_file_count": remote.get("last_token_file_count"),
        "b4_remote_local_count_match": decision.get("b4_remote_local_count_match"),
        "b4_remote_json_local_count_match": decision.get(
            "b4_remote_json_local_count_match"
        ),
        "b4_history_is_already_mirrored_locally": decision.get(
            "b4_history_is_already_mirrored_locally"
        ),
        "last_token_candidate_already_ran": decision.get(
            "last_token_candidate_already_ran"
        ),
        "run_more_standard_b4_runtime_sweeps_now": decision.get(
            "run_more_standard_b4_runtime_sweeps_now"
        ),
        "duplicate_stop_rules": decision.get("duplicate_stop_rules") or [],
        "remaining_nonduplicate_work": decision.get("remaining_nonduplicate_work") or [],
    }


def summarize_runtime_experiment_gate(gate: dict[str, Any]) -> dict[str, Any]:
    decision = gate.get("decision") or {}
    standard = gate.get("standard_b4_coverage") or {}
    service = gate.get("service_gate") or {}
    admission = gate.get("admission_evidence") or {}
    last_token = gate.get("last_token_candidate") or {}
    partition = gate.get("partition_candidate") or {}
    post_instrumentation = gate.get("post_instrumentation_measurement") or {}
    post_segment = gate.get("post_instrumentation_segment_attribution") or {}
    return {
        "verdict": gate.get("verdict"),
        "s100p_runtime_experiment_now": decision.get("s100p_runtime_experiment_now"),
        "allowed_experiments": decision.get("allowed_experiments") or [],
        "run_standard_b4_sweeps_now": decision.get("run_standard_b4_sweeps_now"),
        "run_last_token_mb512_validation_now": decision.get(
            "run_last_token_mb512_validation_now"
        ),
        "run_capacity_partition_probe_now": decision.get("run_capacity_partition_probe_now"),
        "run_post_instrumentation_baseline_measurement_now": decision.get(
            "run_post_instrumentation_baseline_measurement_now"
        ),
        "post_instrumentation_measurement_command": decision.get(
            "post_instrumentation_measurement_command"
        ),
        "reason": decision.get("reason"),
        "next_nonduplicate_runtime_candidate": decision.get(
            "next_nonduplicate_runtime_candidate"
        ),
        "service_gate_ready": service.get("ready"),
        "slo_freshness_accepted": service.get("slo_freshness_accepted"),
        "admission_evidence_ready": admission.get("ready"),
        "final_logits_leverage_gate_ready": admission.get(
            "final_logits_leverage_gate_ready"
        ),
        "runtime_refactor_gate_ready": admission.get("runtime_refactor_gate_ready"),
        "tuning_matrix_gate_ready": admission.get("tuning_matrix_gate_ready"),
        "per_run_matrix_gate_ready": admission.get("per_run_matrix_gate_ready"),
        "per_run_matrix_verdict": admission.get("per_run_matrix_verdict"),
        "per_run_matrix_run_count": admission.get("per_run_matrix_run_count"),
        "per_run_matrix_successful_run_count": admission.get(
            "per_run_matrix_successful_run_count"
        ),
        "per_run_matrix_failed_run_count": admission.get(
            "per_run_matrix_failed_run_count"
        ),
        "per_run_matrix_top_segment": admission.get("per_run_matrix_top_segment"),
        "per_run_matrix_top_segment_rate": admission.get(
            "per_run_matrix_top_segment_rate"
        ),
        "per_run_matrix_standard_sweep_status": admission.get(
            "per_run_matrix_standard_sweep_status"
        ),
        "per_run_matrix_next_nonduplicate_runtime_candidate": admission.get(
            "per_run_matrix_next_nonduplicate_runtime_candidate"
        ),
        "admission_projected_saved_ms_per_request": admission.get(
            "projected_saved_ms_per_request"
        ),
        "admission_not_bpu_promotion_proof": admission.get(
            "projection_is_not_bpu_promotion_proof"
        ),
        "admission_standard_sweeps_blocked": admission.get(
            "standard_group_or_inner_order_sweeps_blocked"
        ),
        "admission_runtime_refactor_primary_target": admission.get(
            "runtime_refactor_primary_target"
        ),
        "admission_tuning_primary_code_target": admission.get("tuning_primary_code_target"),
        "nas_b4_group_major_report_count": standard.get("nas_b4_group_major_report_count"),
        "local_b4_json_count": standard.get("local_b4_json_count"),
        "standard_run_more_sweeps_now": standard.get("run_more_standard_b4_runtime_sweeps_now"),
        "last_token_compile_ready": last_token.get("compile_ready"),
        "last_token_manifest_ready": last_token.get("manifest_ready"),
        "last_token_runtime_validation_ready": last_token.get("runtime_validation_ready"),
        "last_token_candidate_result_exists": last_token.get("candidate_result_exists"),
        "partition_run_new_now": partition.get("run_new_partition_now"),
        "post_instrumentation_gate_verdict": post_instrumentation.get("gate_verdict"),
        "post_instrumentation_telemetry_ready": post_instrumentation.get(
            "post_instrumentation_telemetry_ready"
        ),
        "post_instrumentation_input_output_overhead_quantified": post_instrumentation.get(
            "input_output_overhead_quantified"
        ),
        "post_segment_blocks_standard_group_sweeps": post_segment.get(
            "blocks_standard_group_sweeps"
        ),
        "post_segment_group_size_tuning_implication": post_segment.get(
            "group_size_tuning_implication"
        ),
        "post_segment_inner_order_tuning_implication": post_segment.get(
            "inner_order_tuning_implication"
        ),
        "post_segment_primary_single_segment_bottleneck": post_segment.get(
            "primary_single_segment_bottleneck"
        ),
        "blockers": gate.get("blockers") or [],
        "duplicate_stop_rules": gate.get("duplicate_stop_rules") or [],
        "remaining_nonduplicate_work": gate.get("remaining_nonduplicate_work") or [],
    }


def summarize_runtime_command_guard(guard_payload: dict[str, Any]) -> dict[str, Any]:
    guard = guard_payload.get("guard") or {}
    classification = guard_payload.get("classification") or {}
    return {
        "verdict": guard_payload.get("verdict"),
        "command_guard_active": guard.get("command_guard_active"),
        "proposed_command_present": guard.get("proposed_command_present"),
        "command_admitted": guard.get("command_admitted"),
        "would_start_runtime": guard.get("would_start_runtime"),
        "runtime_gate_allows_experiments": guard.get("runtime_gate_allows_experiments"),
        "allowed_experiments": guard.get("allowed_experiments") or [],
        "standard_sweep_commands_blocked": guard.get("standard_sweep_commands_blocked"),
        "last_token_command_requires_runtime_gate": guard.get(
            "last_token_command_requires_runtime_gate"
        ),
        "admission_evidence_ready": guard.get("admission_evidence_ready"),
        "admission_projected_saved_ms_per_request": guard.get(
            "admission_projected_saved_ms_per_request"
        ),
        "admission_not_bpu_promotion_proof": guard.get(
            "admission_not_bpu_promotion_proof"
        ),
        "classification_blockers": classification.get("blockers") or [],
        "classification_standard_sweep_like": classification.get("standard_sweep_like"),
        "classification_matches_last_token_shape": classification.get(
            "matches_expected_last_token_validation_shape"
        ),
    }


def summarize_compile_command_guard(guard_payload: dict[str, Any]) -> dict[str, Any]:
    guard = guard_payload.get("guard") or {}
    classification = guard_payload.get("classification") or {}
    return {
        "verdict": guard_payload.get("verdict"),
        "compile_guard_active": guard.get("compile_guard_active"),
        "proposed_command_present": guard.get("proposed_command_present"),
        "command_admitted": guard.get("command_admitted"),
        "preflight_admitted": guard.get("preflight_admitted"),
        "would_start_compile": guard.get("would_start_compile"),
        "only_single_segment_last_token_compile_allowed": guard.get(
            "only_single_segment_last_token_compile_allowed"
        ),
        "b8_full_compile_blocked": guard.get("b8_full_compile_blocked"),
        "blocked_now_by_readiness": guard.get("blocked_now_by_readiness"),
        "blocked_now_by_capacity": guard.get("blocked_now_by_capacity"),
        "compile_ready": guard.get("compile_ready"),
        "commit_headroom_gb": guard.get("commit_headroom_gb"),
        "required_commit_headroom_gb": guard.get("required_commit_headroom_gb"),
        "large_private_process_count": guard.get("large_private_process_count"),
        "classification_matches_allowed_shape": classification.get(
            "matches_allowed_single_segment_last_token_shape"
        ),
        "classification_b8_or_larger_compile": classification.get("b8_or_larger_compile"),
        "classification_multi_segment_compile": classification.get("multi_segment_compile"),
        "classification_full_final_logits_compile": classification.get(
            "full_final_logits_compile"
        ),
        "classification_blockers": classification.get("blockers") or [],
    }


def summarize_next_action_admission_pack(pack: dict[str, Any]) -> dict[str, Any]:
    summary = pack.get("summary") or {}
    decision = pack.get("decision") or {}
    return {
        "verdict": pack.get("verdict"),
        "production_default": summary.get("production_default"),
        "queue_should_remain_default": summary.get("queue_should_remain_default"),
        "next_nonduplicate_runtime_candidate": summary.get(
            "next_nonduplicate_runtime_candidate"
        ),
        "allowed_now_count": summary.get("allowed_now_count"),
        "preflight_only_count": summary.get("preflight_only_count"),
        "blocked_action_count": summary.get("blocked_action_count"),
        "would_start_runtime": summary.get("would_start_runtime"),
        "would_start_compile": summary.get("would_start_compile"),
        "per_run_matrix_gate_ready": summary.get("per_run_matrix_gate_ready"),
        "per_run_matrix_verdict": summary.get("per_run_matrix_verdict"),
        "per_run_matrix_run_count": summary.get("per_run_matrix_run_count"),
        "per_run_matrix_successful_run_count": summary.get(
            "per_run_matrix_successful_run_count"
        ),
        "per_run_matrix_failed_run_count": summary.get("per_run_matrix_failed_run_count"),
        "per_run_matrix_top_segment": summary.get("per_run_matrix_top_segment"),
        "per_run_matrix_top_segment_rate": summary.get(
            "per_run_matrix_top_segment_rate"
        ),
        "per_run_matrix_standard_sweep_status": summary.get(
            "per_run_matrix_standard_sweep_status"
        ),
        "safe_compile_preflight_command": summary.get("safe_compile_preflight_command"),
        "do_not_run_standard_true_batch_runtime_now": decision.get(
            "do_not_run_standard_true_batch_runtime_now"
        ),
        "do_not_start_compile_now": decision.get("do_not_start_compile_now"),
        "do_not_promote_true_batch_now": decision.get("do_not_promote_true_batch_now"),
        "queue_batch_product_work_allowed_now": decision.get(
            "queue_batch_product_work_allowed_now"
        ),
        "local_runtime_refactor_analysis_allowed_now": decision.get(
            "local_runtime_refactor_analysis_allowed_now"
        ),
        "compile_preflight_only_allowed_now": decision.get(
            "compile_preflight_only_allowed_now"
        ),
        "only_future_runtime_candidate": decision.get("only_future_runtime_candidate"),
        "failed_checks": pack.get("failed_checks") or [],
    }


def summarize_runtime_refactor_source_contract(contract: dict[str, Any]) -> dict[str, Any]:
    summary = contract.get("summary") or {}
    local_contract = contract.get("local_refactor_contract") or {}
    return {
        "verdict": contract.get("verdict"),
        "source_path": contract.get("source_path"),
        "cli_defaults_preserved": summary.get("cli_defaults_preserved"),
        "last_token_path_supported": summary.get("last_token_path_supported"),
        "telemetry_contract_ready": summary.get("telemetry_contract_ready"),
        "protected_telemetry_fields_ready": summary.get(
            "protected_telemetry_fields_ready"
        ),
        "protected_telemetry_field_count": summary.get(
            "protected_telemetry_field_count"
        ),
        "protected_telemetry_missing_count": summary.get(
            "protected_telemetry_missing_count"
        ),
        "runtime_order_changed": summary.get("runtime_order_changed"),
        "default_promotes_experimental_flags": summary.get(
            "default_promotes_experimental_flags"
        ),
        "runtime_started": summary.get("runtime_started"),
        "compile_started": summary.get("compile_started"),
        "last_token_candidate_can_be_selected_without_changing_default": local_contract.get(
            "last_token_candidate_can_be_selected_without_changing_default"
        ),
        "hidden_materialize_can_be_measured_before_any_promotion": local_contract.get(
            "hidden_materialize_can_be_measured_before_any_promotion"
        ),
        "group_switch_gap_can_be_measured_before_group_policy_changes": local_contract.get(
            "group_switch_gap_can_be_measured_before_group_policy_changes"
        ),
        "preallocate_hidden_must_remain_explicit": local_contract.get(
            "preallocate_hidden_must_remain_explicit"
        ),
        "prewarm_hbm_must_remain_explicit": local_contract.get(
            "prewarm_hbm_must_remain_explicit"
        ),
        "missing_checks": contract.get("missing_checks") or [],
        "missing_telemetry_fields": contract.get("missing_telemetry_fields") or [],
    }


def summarize_runtime_refactor_admission_contract(contract: dict[str, Any]) -> dict[str, Any]:
    summary = contract.get("summary") or {}
    decision = contract.get("decision") or {}
    return {
        "verdict": contract.get("verdict"),
        "queue_batch_remains_default": summary.get("queue_batch_remains_default"),
        "default_runtime_code_change_allowed_now": summary.get(
            "default_runtime_code_change_allowed_now"
        ),
        "local_report_only_refactor_allowed_now": summary.get(
            "local_report_only_refactor_allowed_now"
        ),
        "design_only_hidden_materialize_allowed_now": summary.get(
            "design_only_hidden_materialize_allowed_now"
        ),
        "s100p_runtime_experiment_allowed_now": summary.get(
            "s100p_runtime_experiment_allowed_now"
        ),
        "compile_start_allowed_now": summary.get("compile_start_allowed_now"),
        "compile_preflight_only_allowed_now": summary.get(
            "compile_preflight_only_allowed_now"
        ),
        "protected_telemetry_field_count": summary.get(
            "protected_telemetry_field_count"
        ),
        "protected_telemetry_missing_count": summary.get(
            "protected_telemetry_missing_count"
        ),
        "primary_runtime_refactor_target": summary.get(
            "primary_runtime_refactor_target"
        ),
        "only_future_runtime_candidate": summary.get("only_future_runtime_candidate"),
        "allowed_now_count": summary.get("allowed_now_count"),
        "runtime_blocked_candidate_count": summary.get("runtime_blocked_candidate_count"),
        "admit_default_runtime_behavior_change_now": decision.get(
            "admit_default_runtime_behavior_change_now"
        ),
        "admit_s100p_runtime_now": decision.get("admit_s100p_runtime_now"),
        "admit_compile_start_now": decision.get("admit_compile_start_now"),
        "block_standard_group_or_inner_order_sweeps": decision.get(
            "block_standard_group_or_inner_order_sweeps"
        ),
        "block_prewarm_or_cache_default": decision.get(
            "block_prewarm_or_cache_default"
        ),
        "failed_checks": contract.get("failed_checks") or [],
        "admission_rows": [
            {
                "id": row.get("id"),
                "category": row.get("category"),
                "admitted_now": row.get("admitted_now"),
                "would_start_runtime": row.get("would_start_runtime"),
                "would_start_compile": row.get("would_start_compile"),
                "default_behavior_change_allowed": row.get(
                    "default_behavior_change_allowed"
                ),
            }
            for row in contract.get("admission_rows") or []
        ],
    }


def summarize_runtime_source_implementation_map(source_map: dict[str, Any]) -> dict[str, Any]:
    summary = source_map.get("summary") or {}
    audit = source_map.get("audit") or {}
    checks = source_map.get("checks") or {}
    rows = source_map.get("implementation_rows") or []
    return {
        "verdict": source_map.get("verdict"),
        "runtime_source": (source_map.get("source_paths") or {}).get("runtime_source"),
        "implementation_area_count": summary.get("implementation_area_count"),
        "source_pattern_count": summary.get("source_pattern_count"),
        "missing_source_pattern_count": summary.get("missing_source_pattern_count"),
        "queue_batch_remains_default": summary.get("queue_batch_remains_default"),
        "primary_runtime_refactor_target": summary.get(
            "primary_runtime_refactor_target"
        ),
        "primary_schedule_bottleneck": summary.get("primary_schedule_bottleneck"),
        "preferred_group_policy": summary.get("preferred_group_policy"),
        "preferred_inner_order": summary.get("preferred_inner_order"),
        "allowed_now_count": summary.get("allowed_now_count"),
        "allowed_now": summary.get("allowed_now") or [],
        "duplicate_or_blocked_area_count": summary.get(
            "duplicate_or_blocked_area_count"
        ),
        "s100p_runtime_experiment_allowed_now": summary.get(
            "s100p_runtime_experiment_allowed_now"
        ),
        "compile_start_allowed_now": summary.get("compile_start_allowed_now"),
        "compile_preflight_only_now": summary.get("compile_preflight_only_now"),
        "runtime_default_change_allowed_now": summary.get(
            "runtime_default_change_allowed_now"
        ),
        "runtime_started": summary.get("runtime_started"),
        "compile_started": summary.get("compile_started"),
        "remote_access_performed": summary.get("remote_access_performed"),
        "service_restarted": summary.get("service_restarted"),
        "all_required_source_patterns_present": checks.get(
            "all_required_source_patterns_present"
        ),
        "defaults_preserved": checks.get("defaults_preserved"),
        "standard_group_inner_order_sweeps_blocked": checks.get(
            "standard_group_inner_order_sweeps_blocked"
        ),
        "runtime_compile_not_started": checks.get("runtime_compile_not_started"),
        "remote_access_not_performed": checks.get("remote_access_not_performed"),
        "failed_checks": source_map.get("failed_checks") or [],
        "missing_source_patterns": source_map.get("missing_source_patterns") or [],
        "implementation_rows": [
            {
                "implementation_area": row.get("implementation_area"),
                "class": row.get("class"),
                "source_line_span": row.get("source_line_span"),
                "source_contract_present": row.get("source_contract_present"),
                "current_default_safe": row.get("current_default_safe"),
                "allowed_now": row.get("allowed_now"),
                "allowed_scope": row.get("allowed_scope"),
                "runtime_or_compile_required": row.get("runtime_or_compile_required"),
                "duplicate_with_prior_true_batch_runtime_work": row.get(
                    "duplicate_with_prior_true_batch_runtime_work"
                ),
                "next_gate": row.get("next_gate"),
            }
            for row in rows
        ],
        "source_modified": audit.get("source_modified"),
    }


def summarize_runtime_refactor_work_order(work_order: dict[str, Any]) -> dict[str, Any]:
    summary = work_order.get("summary") or {}
    decision = work_order.get("decision") or {}
    audit = work_order.get("audit") or {}
    rows = work_order.get("work_order_rows") or []
    return {
        "verdict": work_order.get("verdict"),
        "work_order_count": summary.get("work_order_count"),
        "allowed_local_work_count": summary.get("allowed_local_work_count"),
        "future_runtime_candidate_count": summary.get(
            "future_runtime_candidate_count"
        ),
        "source_anchor_missing_count": summary.get("source_anchor_missing_count"),
        "source_contract_missing_token_count": summary.get(
            "source_contract_missing_token_count"
        ),
        "primary_local_design_item": summary.get("primary_local_design_item"),
        "primary_future_runtime_candidate": summary.get(
            "primary_future_runtime_candidate"
        ),
        "primary_runtime_refactor_target": summary.get(
            "primary_runtime_refactor_target"
        ),
        "next_nonduplicate_runtime_candidate": summary.get(
            "next_nonduplicate_runtime_candidate"
        ),
        "most_common_top_segment": summary.get("most_common_top_segment"),
        "most_common_top_segment_rate": summary.get("most_common_top_segment_rate"),
        "standard_b4_runtime_sweep_status": summary.get(
            "standard_b4_runtime_sweep_status"
        ),
        "preferred_group_policy": summary.get("preferred_group_policy"),
        "preferred_inner_order": summary.get("preferred_inner_order"),
        "hidden_materialize_design_contract_verdict": summary.get(
            "hidden_materialize_design_contract_verdict"
        ),
        "hidden_materialize_design_allowed_design_only_count": summary.get(
            "hidden_materialize_design_allowed_design_only_count"
        ),
        "hidden_materialize_design_source_anchor_missing_count": summary.get(
            "hidden_materialize_design_source_anchor_missing_count"
        ),
        "hidden_materialize_design_current_preallocate_hidden_rejected": summary.get(
            "hidden_materialize_design_current_preallocate_hidden_rejected"
        ),
        "hidden_materialize_design_next_design_only_item": summary.get(
            "hidden_materialize_design_next_design_only_item"
        ),
        "hidden_materialize_design_next_report_only_item": summary.get(
            "hidden_materialize_design_next_report_only_item"
        ),
        "hidden_materialize_design_default_runtime_change_allowed_now": summary.get(
            "hidden_materialize_design_default_runtime_change_allowed_now"
        ),
        "hidden_materialize_design_s100p_runtime_allowed_now": summary.get(
            "hidden_materialize_design_s100p_runtime_allowed_now"
        ),
        "hidden_materialize_design_compile_start_allowed_now": summary.get(
            "hidden_materialize_design_compile_start_allowed_now"
        ),
        "hidden_materialize_telemetry_contract_verdict": summary.get(
            "hidden_materialize_telemetry_contract_verdict"
        ),
        "hidden_materialize_telemetry_required_field_count": summary.get(
            "hidden_materialize_telemetry_required_field_count"
        ),
        "hidden_materialize_telemetry_source_anchor_missing_count": summary.get(
            "hidden_materialize_telemetry_source_anchor_missing_count"
        ),
        "hidden_materialize_telemetry_source_ready": summary.get(
            "hidden_materialize_telemetry_source_ready"
        ),
        "hidden_materialize_telemetry_default_runtime_change_allowed_now": summary.get(
            "hidden_materialize_telemetry_default_runtime_change_allowed_now"
        ),
        "hidden_materialize_telemetry_s100p_runtime_allowed_now": summary.get(
            "hidden_materialize_telemetry_s100p_runtime_allowed_now"
        ),
        "hidden_materialize_telemetry_compile_start_allowed_now": summary.get(
            "hidden_materialize_telemetry_compile_start_allowed_now"
        ),
        "queue_batch_remains_default": summary.get("queue_batch_remains_default"),
        "default_runtime_change_allowed_now": summary.get(
            "default_runtime_change_allowed_now"
        ),
        "s100p_runtime_experiment_allowed_now": summary.get(
            "s100p_runtime_experiment_allowed_now"
        ),
        "compile_start_allowed_now": summary.get("compile_start_allowed_now"),
        "compile_preflight_only_allowed_now": summary.get(
            "compile_preflight_only_allowed_now"
        ),
        "next_local_work": decision.get("next_local_work") or [],
        "hidden_materialize_next_design_only_item": decision.get(
            "hidden_materialize_next_design_only_item"
        ),
        "hidden_materialize_next_report_only_item": decision.get(
            "hidden_materialize_next_report_only_item"
        ),
        "hidden_materialize_next_evidence_gate": decision.get(
            "hidden_materialize_next_evidence_gate"
        ),
        "do_not_change_runtime_defaults_now": decision.get(
            "do_not_change_runtime_defaults_now"
        ),
        "do_not_start_s100p_runtime_now": decision.get(
            "do_not_start_s100p_runtime_now"
        ),
        "do_not_start_compile_now": decision.get("do_not_start_compile_now"),
        "do_not_run_more_standard_b4_runtime_sweeps_now": decision.get(
            "do_not_run_more_standard_b4_runtime_sweeps_now"
        ),
        "keep_queue_batch_default": decision.get("keep_queue_batch_default"),
        "next_external_gate": decision.get("next_external_gate"),
        "runtime_started": audit.get("runtime_started"),
        "compile_started": audit.get("compile_started"),
        "remote_access_performed": audit.get("remote_access_performed"),
        "failed_checks": work_order.get("failed_checks") or [],
        "work_order_rows": [
            {
                "rank": row.get("rank"),
                "id": row.get("id"),
                "work_type": row.get("work_type"),
                "allowed_now": row.get("allowed_now"),
                "default_behavior_change_allowed_now": row.get(
                    "default_behavior_change_allowed_now"
                ),
                "source_anchors_all_present": row.get("source_anchors_all_present"),
                "source_anchor_missing_count": row.get("source_anchor_missing_count"),
                "projected_saved_ms_per_request": row.get(
                    "projected_saved_ms_per_request"
                ),
                "expected_ceiling_ms_per_request": row.get(
                    "expected_ceiling_ms_per_request"
                ),
                "local_next_action": row.get("local_next_action"),
                "hidden_materialize_design_contract_verdict": row.get(
                    "hidden_materialize_design_contract_verdict"
                ),
                "hidden_materialize_design_allowed_design_only_count": row.get(
                    "hidden_materialize_design_allowed_design_only_count"
                ),
                "hidden_materialize_design_current_preallocate_hidden_rejected": row.get(
                    "hidden_materialize_design_current_preallocate_hidden_rejected"
                ),
                "hidden_materialize_design_next_design_only_item": row.get(
                    "hidden_materialize_design_next_design_only_item"
                ),
                "hidden_materialize_design_next_report_only_item": row.get(
                    "hidden_materialize_design_next_report_only_item"
                ),
                "hidden_materialize_telemetry_contract_verdict": row.get(
                    "hidden_materialize_telemetry_contract_verdict"
                ),
                "hidden_materialize_telemetry_required_field_count": row.get(
                    "hidden_materialize_telemetry_required_field_count"
                ),
                "hidden_materialize_telemetry_source_anchor_missing_count": row.get(
                    "hidden_materialize_telemetry_source_anchor_missing_count"
                ),
                "hidden_materialize_telemetry_source_ready": row.get(
                    "hidden_materialize_telemetry_source_ready"
                ),
            }
            for row in rows
        ],
    }


def summarize_segment_bottleneck_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    decision = scorecard.get("decision") or {}
    latest = scorecard.get("latest_default_focus") or {}
    stability = scorecard.get("segment_stability") or {}
    default_final = stability.get("default_collect_final_excess_ms_per_request") or {}
    all_final = stability.get("all_segment_major_final_excess_ms_per_request") or {}
    group_tuning = scorecard.get("group_tuning") or {}
    top_rows = scorecard.get("segment_bottlenecks") or []
    final_row = next((row for row in top_rows if row.get("index") == 27), {})
    token_row = next((row for row in top_rows if row.get("index") == 0), {})
    hidden_row = next((row for row in top_rows if row.get("kind") == "hidden_block"), {})
    priorities = scorecard.get("action_priorities") or []
    return {
        "verdict": scorecard.get("verdict"),
        "primary_runtime_lever": decision.get("primary_runtime_lever"),
        "preferred_inner_order": decision.get("preferred_inner_order"),
        "preferred_group_policy": decision.get("preferred_group_policy"),
        "avoid_more_mb512_boundary_sweeps": decision.get("avoid_more_mb512_boundary_sweeps"),
        "avoid_gap_microbatch_sweeps_above_mb512": decision.get(
            "avoid_gap_microbatch_sweeps_above_mb512"
        ),
        "next_runtime_candidate": decision.get("next_runtime_candidate"),
        "latest_microbatch_count": latest.get("microbatch_count"),
        "latest_ms_per_request": latest.get("ms_per_request"),
        "final_vs_hidden_mean_ratio": latest.get("final_vs_hidden_mean_ratio"),
        "default_collect_run_count": stability.get("default_collect_run_count"),
        "analyzed_segment_major_run_count": stability.get("analyzed_run_count"),
        "default_collect_final_excess_mean_ms_per_request": default_final.get("mean"),
        "default_collect_final_excess_stdev_ms_per_request": default_final.get("stdev"),
        "all_segment_major_final_excess_mean_ms_per_request": all_final.get("mean"),
        "all_segment_major_final_excess_stdev_ms_per_request": all_final.get("stdev"),
        "final_excess_ms_per_request": final_row.get("mean_positive_excess_ms_per_request"),
        "final_load_ms_per_request": final_row.get("load_ms_per_request"),
        "token_excess_ms_per_request": token_row.get("mean_positive_excess_ms_per_request"),
        "token_load_ms_per_request": token_row.get("load_ms_per_request"),
        "max_hidden_index": hidden_row.get("index"),
        "max_hidden_excess_ms_per_request": hidden_row.get("mean_positive_excess_ms_per_request"),
        "g7_even_delta_ms_per_request": group_tuning.get("g7_even_delta_ms_per_request"),
        "microbatch_major_delta_ms_per_request": group_tuning.get(
            "microbatch_major_delta_ms_per_request"
        ),
        "no_observed_variant_beats_baseline": group_tuning.get(
            "no_observed_variant_beats_baseline"
        ),
        "top_action": (priorities[0] if priorities else {}).get("action"),
        "top_action_reason": (priorities[0] if priorities else {}).get("why"),
    }


def summarize_segment_group_schedule_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    summary = scorecard.get("summary") or {}
    decision = scorecard.get("decision") or {}
    rows = scorecard.get("scorecard_rows") or []
    top_row = rows[0] if rows else {}
    audit = scorecard.get("audit") or {}
    return {
        "verdict": scorecard.get("verdict"),
        "latest_default_microbatch_count": summary.get("latest_default_microbatch_count"),
        "latest_default_ms_per_request": summary.get("latest_default_ms_per_request"),
        "latest_default_avg_bpu_loading": summary.get("latest_default_avg_bpu_loading"),
        "primary_single_segment_bottleneck": summary.get(
            "primary_single_segment_bottleneck"
        ),
        "final_logits_segment_total_ms_per_request": summary.get(
            "final_logits_segment_total_ms_per_request"
        ),
        "final_logits_compute_excess_ms_per_request": summary.get(
            "final_logits_compute_excess_ms_per_request"
        ),
        "final_to_top_hidden_compute_excess_ratio": summary.get(
            "final_to_top_hidden_compute_excess_ratio"
        ),
        "group_switch_gap_ms_per_request": summary.get("group_switch_gap_ms_per_request"),
        "final_excess_to_group_switch_gap_ratio": summary.get(
            "final_excess_to_group_switch_gap_ratio"
        ),
        "best_nonbaseline_group_delta_ms_per_request": summary.get(
            "best_nonbaseline_group_delta_ms_per_request"
        ),
        "observed_nonbaseline_group_or_order_count": summary.get(
            "observed_nonbaseline_group_or_order_count"
        ),
        "capacity_probe_only_candidate_count": summary.get(
            "capacity_probe_only_candidate_count"
        ),
        "primary_code_target_projected_saved_ms_per_request": summary.get(
            "primary_code_target_projected_saved_ms_per_request"
        ),
        "production_default": decision.get("production_default"),
        "true_batch_b4_status": decision.get("true_batch_b4_status"),
        "primary_schedule_bottleneck": decision.get("primary_schedule_bottleneck"),
        "primary_code_target": decision.get("primary_code_target"),
        "preferred_group_policy": decision.get("preferred_group_policy"),
        "preferred_inner_order": decision.get("preferred_inner_order"),
        "run_more_standard_b4_group_or_inner_order_sweeps_now": decision.get(
            "run_more_standard_b4_group_or_inner_order_sweeps_now"
        ),
        "run_new_group_partition_now": decision.get("run_new_group_partition_now"),
        "run_s100p_runtime_now": decision.get("run_s100p_runtime_now"),
        "start_compile_now": decision.get("start_compile_now"),
        "compile_preflight_only_now": decision.get("compile_preflight_only_now"),
        "local_report_only_refactor_allowed_now": decision.get(
            "local_report_only_refactor_allowed_now"
        ),
        "next_runtime_candidate_after_readiness": decision.get(
            "next_runtime_candidate_after_readiness"
        ),
        "recommended_next": decision.get("recommended_next"),
        "top_scorecard_target": top_row.get("target"),
        "top_scorecard_status": top_row.get("status"),
        "top_scorecard_estimated_saved_ms_per_request": top_row.get(
            "estimated_saved_ms_per_request"
        ),
        "failed_checks": scorecard.get("failed_checks") or [],
        "runtime_started": audit.get("runtime_started"),
        "compile_started": audit.get("compile_started"),
        "remote_access_performed": audit.get("remote_access_performed"),
    }


def summarize_runtime_instrumentation(contract: dict[str, Any], deployment: dict[str, Any]) -> dict[str, Any]:
    contract_behavior = contract.get("behavior") or {}
    deployment_behavior = deployment.get("behavior") or {}
    remote_values = deployment.get("remote_values") or {}
    return {
        "contract_verdict": contract.get("verdict"),
        "deployment_verdict": deployment.get("verdict"),
        "new_telemetry_fields": contract.get("new_telemetry_fields") or [],
        "default_cli_changed": contract_behavior.get("default_cli_changed"),
        "runtime_order_changed": contract_behavior.get("runtime_order_changed"),
        "requires_s100p_runtime": contract_behavior.get("requires_s100p_runtime"),
        "remote_probe": deployment.get("remote_probe"),
        "remote_probe_sha256": remote_values.get("probe_sha256"),
        "remote_backup": remote_values.get("latest_backup"),
        "input_prepare_count": as_float(remote_values.get("input_prepare_count")),
        "output_postprocess_count": as_float(remote_values.get("output_postprocess_count")),
        "total_input_prepare_count": as_float(remote_values.get("total_input_prepare_count")),
        "total_output_postprocess_count": as_float(remote_values.get("total_output_postprocess_count")),
        "avg_input_prepare_count": as_float(remote_values.get("avg_input_prepare_count")),
        "avg_output_postprocess_count": as_float(remote_values.get("avg_output_postprocess_count")),
        "active_true_batch_python": as_float(remote_values.get("active_true_batch_python")),
        "active_compile_true_batch": as_float(remote_values.get("active_compile_true_batch")),
        "runtime_experiment_started": deployment_behavior.get("runtime_experiment_started"),
        "compile_started": deployment_behavior.get("compile_started"),
        "remote_file_overwritten_with_backup": deployment_behavior.get(
            "remote_file_overwritten_with_backup"
        ),
    }


def summarize_hbm_load_accounting_contract(contract: dict[str, Any]) -> dict[str, Any]:
    summary = contract.get("summary") or {}
    return {
        "verdict": contract.get("verdict"),
        "source_path": contract.get("source_path"),
        "per_segment_load_accounting_ready": summary.get(
            "per_segment_load_accounting_ready"
        ),
        "group_load_accounting_ready": summary.get("group_load_accounting_ready"),
        "prewarm_accounting_ready": summary.get("prewarm_accounting_ready"),
        "timing_summary_accounts_load_and_prewarm": summary.get(
            "timing_summary_accounts_load_and_prewarm"
        ),
        "prewarm_hbm_default_changed": summary.get("prewarm_hbm_default_changed"),
        "runtime_started": summary.get("runtime_started"),
        "compile_started": summary.get("compile_started"),
        "remote_access_performed": summary.get("remote_access_performed"),
        "accounted_fields": contract.get("accounted_fields") or [],
        "missing_checks": contract.get("missing_checks") or [],
    }


def summarize_post_instrumentation_telemetry_gate(gate: dict[str, Any]) -> dict[str, Any]:
    coverage = gate.get("coverage") or {}
    decision = gate.get("decision") or {}
    next_measurement = decision.get("next_measurement") or {}
    return {
        "verdict": gate.get("verdict"),
        "b4_telemetry_count": coverage.get("b4_telemetry_count"),
        "successful_b4_telemetry_count": coverage.get("successful_b4_telemetry_count"),
        "post_instrumentation_success_count": coverage.get("post_instrumentation_success_count"),
        "baseline_mb512_segment_major_5g_success_count": coverage.get(
            "baseline_mb512_segment_major_5g_success_count"
        ),
        "post_instrumentation_telemetry_ready": decision.get(
            "post_instrumentation_telemetry_ready"
        ),
        "input_output_overhead_quantified": decision.get("input_output_overhead_quantified"),
        "do_not_claim_input_output_overhead_yet": decision.get(
            "do_not_claim_input_output_overhead_yet"
        ),
        "run_more_standard_b4_runtime_sweeps_now": decision.get(
            "run_more_standard_b4_runtime_sweeps_now"
        ),
        "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available": decision.get(
            "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available"
        ),
        "next_measurement_purpose": next_measurement.get("purpose"),
        "next_measurement_is_standard_sweep": next_measurement.get("is_standard_sweep"),
        "next_measurement_microbatch_count": next_measurement.get("microbatch_count"),
        "next_measurement_inner_order": next_measurement.get("inner_order"),
        "next_measurement_groups": next_measurement.get("groups"),
        "next_measurement_command": next_measurement.get("command"),
        "reason": decision.get("reason"),
    }


def summarize_post_instrumentation_overhead_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    totals = analysis.get("totals") or {}
    decision = analysis.get("decision") or {}
    return {
        "verdict": analysis.get("verdict"),
        "ms_per_request": totals.get("ms_per_request"),
        "avg_bpu_loading": totals.get("avg_bpu_loading"),
        "input_prepare_ms_per_request": totals.get("input_prepare_ms_per_request"),
        "output_postprocess_ms_per_request": totals.get("output_postprocess_ms_per_request"),
        "hidden_materialize_ms_per_request": totals.get("hidden_materialize_ms_per_request"),
        "final_output_postprocess_ms_per_request": totals.get(
            "final_output_postprocess_ms_per_request"
        ),
        "final_excess_ms_per_request_vs_hidden": totals.get(
            "final_excess_ms_per_request_vs_hidden"
        ),
        "input_prepare_primary_bottleneck": decision.get("input_prepare_primary_bottleneck"),
        "output_postprocess_primary_bottleneck": decision.get(
            "output_postprocess_primary_bottleneck"
        ),
        "hidden_materialize_buffer_reuse_has_measured_ceiling": decision.get(
            "hidden_materialize_buffer_reuse_has_measured_ceiling"
        ),
        "final_logits_compute_still_primary": decision.get("final_logits_compute_still_primary"),
        "final_logits_output_postprocess_not_primary": decision.get(
            "final_logits_output_postprocess_not_primary"
        ),
        "next_local_runtime_code_target": decision.get("next_local_runtime_code_target"),
        "secondary_local_runtime_code_target": decision.get(
            "secondary_local_runtime_code_target"
        ),
        "do_not_run_more_standard_b4_sweeps_for_input_output_overhead": decision.get(
            "do_not_run_more_standard_b4_sweeps_for_input_output_overhead"
        ),
    }


def summarize_post_instrumentation_segment_attribution(analysis: dict[str, Any]) -> dict[str, Any]:
    run = analysis.get("run") or {}
    totals = analysis.get("totals") or {}
    decision = analysis.get("decision") or {}
    rankings = analysis.get("rankings") or {}
    top_segments = rankings.get("top_segments_by_segment_total_ms_per_request") or []
    top_groups = rankings.get("top_groups_by_segment_total_ms_per_request") or []
    return {
        "verdict": analysis.get("verdict"),
        "microbatch_count": run.get("microbatch_count"),
        "batch_size": run.get("batch_size"),
        "ms_per_request": run.get("ms_per_request"),
        "avg_bpu_loading": run.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": run.get("avg_nonzero_bpu_loading"),
        "primary_single_segment_bottleneck": decision.get("primary_single_segment_bottleneck"),
        "final_logits_compute_still_primary": decision.get(
            "final_logits_compute_still_primary"
        ),
        "final_compute_excess_ms_per_request": totals.get(
            "final_compute_excess_ms_per_request"
        ),
        "final_to_top_hidden_compute_excess_ratio": totals.get(
            "final_to_top_hidden_compute_excess_ratio"
        ),
        "hidden_materialize_ms_per_request": totals.get("hidden_materialize_ms_per_request"),
        "output_postprocess_ms_per_request": totals.get("output_postprocess_ms_per_request"),
        "input_prepare_ms_per_request": totals.get("input_prepare_ms_per_request"),
        "top_segment_index": (top_segments[0] if top_segments else {}).get("index"),
        "top_segment_kind": (top_segments[0] if top_segments else {}).get("kind"),
        "top_segment_total_ms_per_request": (top_segments[0] if top_segments else {}).get(
            "segment_total_ms_per_request"
        ),
        "top_group_by_segment_total": decision.get("top_group_by_segment_total"),
        "top_group_contains_final_logits": decision.get("top_group_contains_final_logits"),
        "top_group_segment_total_ms_per_request": (top_groups[0] if top_groups else {}).get(
            "segment_total_ms_per_request"
        ),
        "group_size_tuning_implication": decision.get("group_size_tuning_implication"),
        "inner_order_tuning_implication": decision.get("inner_order_tuning_implication"),
        "next_code_target": decision.get("next_code_target"),
        "secondary_research_target": decision.get("secondary_research_target"),
        "current_preallocate_hidden_path_should_remain_rejected": decision.get(
            "current_preallocate_hidden_path_should_remain_rejected"
        ),
        "do_not_run_more_standard_b4_group_order_sweeps_now": decision.get(
            "do_not_run_more_standard_b4_group_order_sweeps_now"
        ),
    }


def summarize_hidden_buffer_reuse_decision(decision_payload: dict[str, Any]) -> dict[str, Any]:
    delta = decision_payload.get("latest_prealloc_ab_delta") or {}
    decision = decision_payload.get("decision") or {}
    ref = decision_payload.get("post_instrumentation_reference") or {}
    return {
        "verdict": decision_payload.get("verdict"),
        "hidden_materialize_ms_per_request": ref.get("hidden_materialize_ms_per_request"),
        "final_excess_ms_per_request_vs_hidden": ref.get(
            "final_excess_ms_per_request_vs_hidden"
        ),
        "prealloc_ms_per_request_delta": delta.get("ms_per_request_delta"),
        "prealloc_hidden_materialize_ms_per_request_delta": delta.get(
            "hidden_materialize_ms_per_request_delta"
        ),
        "prealloc_avg_bpu_delta": delta.get("avg_bpu_delta"),
        "prealloc_nonzero_bpu_delta": delta.get("nonzero_bpu_delta"),
        "prealloc_reused_hidden_buffer_count": delta.get("reused_hidden_buffer_count"),
        "hidden_buffer_reuse_default": decision.get("hidden_buffer_reuse_default"),
        "preallocate_hidden_experimental_flag_only": decision.get(
            "preallocate_hidden_experimental_flag_only"
        ),
        "do_not_start_new_preallocate_hidden_runtime_now": decision.get(
            "do_not_start_new_preallocate_hidden_runtime_now"
        ),
        "reuse_buffer_implementation_measured_slower": decision.get(
            "reuse_buffer_implementation_measured_slower"
        ),
        "hidden_materialize_has_measured_ceiling": decision.get(
            "hidden_materialize_has_measured_ceiling"
        ),
        "primary_target_remains_final_logits": decision.get(
            "primary_target_remains_final_logits"
        ),
        "secondary_research_target": decision.get("secondary_research_target"),
    }


def summarize_hidden_materialize_design_contract(contract: dict[str, Any]) -> dict[str, Any]:
    summary = contract.get("summary") or {}
    decision = contract.get("decision") or {}
    audit = contract.get("audit") or {}
    return {
        "verdict": contract.get("verdict"),
        "design_row_count": summary.get("design_row_count"),
        "allowed_design_only_count": summary.get("allowed_design_only_count"),
        "source_anchor_missing_count": summary.get("source_anchor_missing_count"),
        "hidden_materialize_ms_per_request": summary.get(
            "hidden_materialize_ms_per_request"
        ),
        "hidden_materialize_ms_per_item": summary.get(
            "hidden_materialize_ms_per_item"
        ),
        "prealloc_ms_per_request_delta": summary.get(
            "prealloc_ms_per_request_delta"
        ),
        "prealloc_hidden_materialize_ms_per_request_delta": summary.get(
            "prealloc_hidden_materialize_ms_per_request_delta"
        ),
        "current_preallocate_hidden_rejected": summary.get(
            "current_preallocate_hidden_rejected"
        ),
        "preallocate_hidden_experimental_flag_only": summary.get(
            "preallocate_hidden_experimental_flag_only"
        ),
        "hidden_materialize_has_measured_ceiling": summary.get(
            "hidden_materialize_has_measured_ceiling"
        ),
        "primary_target_remains_final_logits": summary.get(
            "primary_target_remains_final_logits"
        ),
        "hidden_to_final_excess_ratio": summary.get("hidden_to_final_excess_ratio"),
        "next_design_only_item": summary.get("next_design_only_item"),
        "next_report_only_item": summary.get("next_report_only_item"),
        "default_runtime_change_allowed_now": summary.get(
            "default_runtime_change_allowed_now"
        ),
        "s100p_runtime_experiment_allowed_now": summary.get(
            "s100p_runtime_experiment_allowed_now"
        ),
        "compile_start_allowed_now": summary.get("compile_start_allowed_now"),
        "allow_local_design_notes_now": decision.get("allow_local_design_notes_now"),
        "allow_report_only_source_contract_followup_now": decision.get(
            "allow_report_only_source_contract_followup_now"
        ),
        "promote_current_preallocate_hidden": decision.get(
            "promote_current_preallocate_hidden"
        ),
        "change_runtime_defaults_now": decision.get("change_runtime_defaults_now"),
        "start_s100p_runtime_now": decision.get("start_s100p_runtime_now"),
        "start_compile_now": decision.get("start_compile_now"),
        "keep_preallocate_hidden_explicit": decision.get(
            "keep_preallocate_hidden_explicit"
        ),
        "next_required_evidence": decision.get("next_required_evidence"),
        "runtime_started": audit.get("runtime_started"),
        "compile_started": audit.get("compile_started"),
        "remote_access_performed": audit.get("remote_access_performed"),
        "failed_checks": contract.get("failed_checks") or [],
    }


def summarize_hidden_materialize_telemetry_contract(contract: dict[str, Any]) -> dict[str, Any]:
    summary = contract.get("summary") or {}
    decision = contract.get("decision") or {}
    audit = contract.get("audit") or {}
    return {
        "verdict": contract.get("verdict"),
        "helper_count": summary.get("helper_count"),
        "required_telemetry_field_count": summary.get(
            "required_telemetry_field_count"
        ),
        "candidate_mode_count": summary.get("candidate_mode_count"),
        "behavior_token_count": summary.get("behavior_token_count"),
        "source_anchor_missing_count": summary.get("source_anchor_missing_count"),
        "current_preallocate_hidden_rejected": summary.get(
            "current_preallocate_hidden_rejected"
        ),
        "next_design_only_item": summary.get("next_design_only_item"),
        "next_report_only_item": summary.get("next_report_only_item"),
        "default_runtime_change_allowed_now": summary.get(
            "default_runtime_change_allowed_now"
        ),
        "s100p_runtime_experiment_allowed_now": summary.get(
            "s100p_runtime_experiment_allowed_now"
        ),
        "compile_start_allowed_now": summary.get("compile_start_allowed_now"),
        "telemetry_source_ready": decision.get("telemetry_source_ready"),
        "deploy_or_run_now": decision.get("deploy_or_run_now"),
        "change_runtime_defaults_now": decision.get("change_runtime_defaults_now"),
        "start_s100p_runtime_now": decision.get("start_s100p_runtime_now"),
        "start_compile_now": decision.get("start_compile_now"),
        "next_evidence_gate": decision.get("next_evidence_gate"),
        "runtime_source_modified_for_telemetry_only": audit.get(
            "runtime_source_modified_for_telemetry_only"
        ),
        "default_behavior_changed": audit.get("default_behavior_changed"),
        "runtime_started": audit.get("runtime_started"),
        "compile_started": audit.get("compile_started"),
        "remote_access_performed": audit.get("remote_access_performed"),
        "failed_checks": contract.get("failed_checks") or [],
    }


def summarize_segment_drag_breakdown(segment_drag: dict[str, Any]) -> dict[str, Any]:
    latest = segment_drag.get("latest_default_focus") or {}
    aggregate_rows = segment_drag.get("aggregate_segments_by_avg_run_ms") or []
    latest_run = segment_drag.get("latest_default_run") or {}
    latest_segments = latest_run.get("segments_by_positive_excess_ms") or []
    top_group = latest.get("top_group_by_accounted_ms") or {}
    default_stability = segment_drag.get("default_collect_stability") or {}
    default_final = default_stability.get("final_excess_ms_per_request") or {}
    default_token = default_stability.get("token_excess_ms_per_request") or {}
    return {
        "verdict": segment_drag.get("verdict"),
        "analyzed_run_count": segment_drag.get("analyzed_run_count"),
        "default_collect_run_count": segment_drag.get("default_collect_run_count"),
        "latest_microbatch_count": latest.get("microbatch_count"),
        "latest_ms_per_request": latest.get("ms_per_request"),
        "latest_avg_bpu_loading": latest.get("avg_bpu_loading"),
        "latest_avg_nonzero_bpu_loading": latest.get("avg_nonzero_bpu_loading"),
        "hidden_mean_avg_run_ms": latest.get("hidden_mean_avg_run_ms"),
        "hidden_stdev_avg_run_ms": latest.get("hidden_stdev_avg_run_ms"),
        "final_avg_run_ms": latest.get("final_avg_run_ms"),
        "final_vs_hidden_mean_ratio": latest.get("final_vs_hidden_mean_ratio"),
        "final_excess_ms_per_request_if_hidden_speed": latest.get(
            "final_excess_ms_per_request_if_hidden_speed"
        ),
        "token_avg_run_ms": latest.get("token_avg_run_ms"),
        "token_vs_hidden_mean_ratio": latest.get("token_vs_hidden_mean_ratio"),
        "token_excess_ms_per_request_if_hidden_speed": latest.get(
            "token_excess_ms_per_request_if_hidden_speed"
        ),
        "top_group_by_accounted_ms": top_group.get("group"),
        "top_group_contains_final_logits": top_group.get("contains_final_logits"),
        "default_collect_final_excess_mean_ms_per_request": default_final.get("mean"),
        "default_collect_final_excess_stdev_ms_per_request": default_final.get("stdev"),
        "default_collect_token_excess_mean_ms_per_request": default_token.get("mean"),
        "default_collect_token_excess_stdev_ms_per_request": default_token.get("stdev"),
        "top_segments_by_avg_run_ms": [
            {
                "rank": rank,
                "index": row.get("index"),
                "kind": row.get("kind"),
                "mean_avg_run_ms": row.get("mean_avg_run_ms"),
                "mean_positive_excess_ms_per_request": row.get(
                    "mean_positive_excess_ms_per_request"
                ),
                "representative_group": row.get("representative_group"),
            }
            for rank, row in enumerate(aggregate_rows[:5], start=1)
        ],
        "latest_top_segments_by_positive_excess": [
            {
                "rank": rank,
                "index": row.get("index"),
                "kind": row.get("kind"),
                "group": row.get("group"),
                "avg_run_ms": row.get("avg_run_ms"),
                "positive_excess_ms_per_request": row.get(
                    "positive_excess_ms_per_request"
                ),
            }
            for rank, row in enumerate(latest_segments[:5], start=1)
        ],
    }


def summarize_segment_stability_audit(audit: dict[str, Any]) -> dict[str, Any]:
    summary = audit.get("summary") or {}
    decision = audit.get("decision") or {}
    leaderboard = audit.get("leaderboard") or []
    final_row = next((row for row in leaderboard if row.get("index") == 27), {})
    token_row = next((row for row in leaderboard if row.get("index") == 0), {})
    hidden_row = next((row for row in leaderboard if row.get("kind") == "hidden_block"), {})
    return {
        "verdict": audit.get("verdict"),
        "analyzed_run_count": summary.get("analyzed_run_count"),
        "ranked_segment_count": summary.get("ranked_segment_count"),
        "stable_primary_bottleneck": decision.get("stable_primary_bottleneck"),
        "final_logits_stable_rank1": decision.get("final_logits_stable_rank1"),
        "final_logits_rank1_rate": summary.get("final_logits_rank1_rate"),
        "final_logits_top2_rate": summary.get("final_logits_top2_rate"),
        "final_logits_mean_positive_excess_ms_per_request": summary.get(
            "final_logits_mean_positive_excess_ms_per_request"
        ),
        "final_logits_cv_positive_excess": summary.get("final_logits_cv_positive_excess"),
        "token_embedding_secondary_not_primary": decision.get(
            "token_embedding_secondary_not_primary"
        ),
        "token_embedding_mean_positive_excess_ms_per_request": summary.get(
            "token_embedding_mean_positive_excess_ms_per_request"
        ),
        "max_hidden_index": summary.get("max_hidden_index"),
        "max_hidden_mean_positive_excess_ms_per_request": summary.get(
            "max_hidden_mean_positive_excess_ms_per_request"
        ),
        "final_to_token_excess_ratio": summary.get("final_to_token_excess_ratio"),
        "final_to_max_hidden_excess_ratio": summary.get("final_to_max_hidden_excess_ratio"),
        "hidden_inner_order_tuning_not_primary": decision.get(
            "hidden_inner_order_tuning_not_primary"
        ),
        "do_not_run_hidden_order_sweeps_now": decision.get("do_not_run_hidden_order_sweeps_now"),
        "do_not_run_standard_b4_sweeps_now": decision.get("do_not_run_standard_b4_sweeps_now"),
        "next_runtime_candidate": decision.get("next_runtime_candidate"),
        "top_final_rank": final_row.get("mean_rank"),
        "top_token_rank": token_row.get("mean_rank"),
        "top_hidden_index": hidden_row.get("index"),
        "top_hidden_mean_rank": hidden_row.get("mean_rank"),
        "reason": decision.get("reason"),
    }


def summarize_compile_capacity(capacity: dict[str, Any]) -> dict[str, Any]:
    current = capacity.get("current_commit") or {}
    projected = capacity.get("projected_after_closing_large_private_processes") or {}
    pagefile = capacity.get("pagefile") or {}
    recommendation = capacity.get("recommendation") or {}
    return {
        "verdict": capacity.get("verdict"),
        "commit_headroom_gb": current.get("commit_headroom_gb"),
        "commit_headroom_deficit_gb": current.get("commit_headroom_deficit_gb"),
        "reclaim_private_gb": projected.get("reclaim_private_gb"),
        "projected_commit_headroom_after_reclaim_gb": projected.get("commit_headroom_gb"),
        "remaining_headroom_deficit_after_reclaim_gb": projected.get("remaining_headroom_deficit_gb"),
        "required_commit_limit_after_reclaim_gb": projected.get("required_commit_limit_gb"),
        "additional_commit_limit_needed_after_reclaim_gb": projected.get("additional_commit_limit_needed_gb"),
        "pagefile_setting_mode": pagefile.get("setting_mode"),
        "current_pagefile_allocated_total_gb": pagefile.get("current_allocated_total_gb"),
        "recommended_additional_commit_limit_with_safety_gb": pagefile.get(
            "recommended_additional_commit_limit_with_safety_gb"
        ),
        "recommended_commit_limit_gb": pagefile.get("recommended_commit_limit_gb"),
        "do_not_start_compile_now": recommendation.get("do_not_start_compile_now"),
        "close_large_private_processes_first": recommendation.get("close_large_private_processes_first"),
        "increase_commit_limit_or_pagefile_before_compile": recommendation.get(
            "increase_commit_limit_or_pagefile_before_compile"
        ),
    }


def summarize_first_response(
    first_response: dict[str, Any],
    routing: dict[str, Any],
    fast_status: dict[str, Any],
    fast_path_regression: dict[str, Any],
) -> dict[str, Any]:
    first_summary = first_response.get("summary") or {}
    fast_decision = fast_status.get("decision") or {}
    routing_decision = routing.get("decision") or {}
    regression_cases = {
        str(case.get("id")): case for case in fast_path_regression.get("cases") or []
    }
    quick_ready = regression_cases.get("quick_ready") or {}
    identity_short = regression_cases.get("identity_short") or {}
    chinese_short = regression_cases.get("chinese_short") or {}
    return {
        "first_response_verdict": first_response.get("verdict"),
        "routing_verdict": routing.get("verdict"),
        "fast_status_verdict": fast_status.get("verdict"),
        "fast_path_regression_verdict": fast_path_regression.get("verdict"),
        "ttft_p50_ms": first_summary.get("ttft_p50_ms"),
        "first_progress_p50_ms": first_summary.get("first_progress_p50_ms"),
        "first_content_p50_ms": first_summary.get("first_content_p50_ms"),
        "first_content_latency_needs_work": (first_response.get("decision") or {}).get(
            "first_content_latency_needs_work"
        ),
        "quick_path_requires_omitting_explicit_max_tokens_and_steps": routing_decision.get(
            "quick_path_requires_omitting_explicit_max_tokens_and_steps"
        ),
        "quick_ready_improved_when_quickpath_enabled": routing_decision.get(
            "quick_ready_improved_when_quickpath_enabled"
        ),
        "localized_status_fast_path_ready": fast_decision.get("localized_status_fast_path_ready"),
        "localized_status_first_content_ms": fast_decision.get("localized_status_first_content_ms"),
        "localized_status_delta_ms": fast_decision.get("localized_status_delta_ms"),
        "identity_fast_path_still_ready": fast_decision.get("identity_fast_path_still_ready"),
        "regression_quick_ready_first_content_ms": quick_ready.get("first_content_ms"),
        "regression_identity_first_content_ms": identity_short.get("first_content_ms"),
        "regression_localized_status_first_content_ms": chinese_short.get("first_content_ms"),
    }


def summarize_first_response_slo_tier_guard(guard: dict[str, Any]) -> dict[str, Any]:
    tiers = guard.get("tiers") or {}
    fast_path = tiers.get("fast_path_first_content") or {}
    progress = tiers.get("sse_progress") or {}
    backend = tiers.get("backend_first_content") or {}
    health = tiers.get("health") or {}
    decision = guard.get("decision") or {}
    audit = guard.get("audit") or {}
    return {
        "verdict": guard.get("verdict"),
        "failed_checks": guard.get("failed_checks") or [],
        "health_ready": health.get("ready"),
        "fast_path_ready": fast_path.get("ready"),
        "fast_path_case_count": fast_path.get("case_count"),
        "fast_path_max_first_content_ms": fast_path.get("max_first_content_ms"),
        "sse_progress_ready": progress.get("ready"),
        "sse_first_progress_p50_ms": progress.get("first_progress_p50_ms"),
        "sse_first_progress_p95_ms": progress.get("first_progress_p95_ms"),
        "backend_first_content_tracked_separately": backend.get("tracked_separately"),
        "backend_first_content_latency_needs_work": backend.get(
            "first_content_latency_needs_work"
        ),
        "explicit_first_content_p50_ms": backend.get("explicit_first_content_p50_ms"),
        "quickpath_first_content_p50_ms": backend.get("quickpath_first_content_p50_ms"),
        "queue_batch_service_remains_default": decision.get(
            "queue_batch_service_remains_default"
        ),
        "fast_paths_satisfy_interactive_first_content_slo": decision.get(
            "fast_paths_satisfy_interactive_first_content_slo"
        ),
        "sse_progress_satisfies_interactive_progress_slo": decision.get(
            "sse_progress_satisfies_interactive_progress_slo"
        ),
        "backend_first_content_latency_is_not_true_batch_work": decision.get(
            "backend_first_content_latency_is_not_true_batch_work"
        ),
        "do_not_promote_true_batch_for_first_response": decision.get(
            "do_not_promote_true_batch_for_first_response"
        ),
        "runtime_started": audit.get("runtime_started"),
        "compile_started": audit.get("compile_started"),
    }


def summarize_first_response_warning_triage(triage: dict[str, Any]) -> dict[str, Any]:
    summary = triage.get("summary") or {}
    decision = triage.get("decision") or {}
    audit = triage.get("audit") or {}
    return {
        "verdict": triage.get("verdict"),
        "failed_checks": triage.get("failed_checks") or [],
        "source_warning_verdict": summary.get("source_warning_verdict"),
        "source_warning_count": summary.get("source_warning_count"),
        "first_content_p50_ms": summary.get("first_content_p50_ms"),
        "first_content_p95_ms": summary.get("first_content_p95_ms"),
        "first_progress_p50_ms": summary.get("first_progress_p50_ms"),
        "explicit_first_content_p50_ms": summary.get("explicit_first_content_p50_ms"),
        "quickpath_first_content_p50_ms": summary.get("quickpath_first_content_p50_ms"),
        "quickpath_delta_ms": summary.get("quickpath_delta_ms"),
        "fast_path_max_first_content_ms": summary.get("fast_path_max_first_content_ms"),
        "backend_first_content_tracked_separately": summary.get(
            "backend_first_content_tracked_separately"
        ),
        "backend_first_content_latency_is_not_true_batch_work": summary.get(
            "backend_first_content_latency_is_not_true_batch_work"
        ),
        "warning_is_product_triaged": decision.get("warning_is_product_triaged"),
        "queue_batch_service_remains_default": decision.get(
            "queue_batch_service_remains_default"
        ),
        "do_not_promote_true_batch_for_first_response": decision.get(
            "do_not_promote_true_batch_for_first_response"
        ),
        "continue_tracking_backend_content_latency": decision.get(
            "continue_tracking_backend_content_latency"
        ),
        "runtime_started": audit.get("runtime_started"),
        "compile_started": audit.get("compile_started"),
    }


def summarize_slo_limited_evidence_triage(triage: dict[str, Any]) -> dict[str, Any]:
    summary = triage.get("summary") or {}
    decision = triage.get("decision") or {}
    audit = triage.get("audit") or {}
    return {
        "verdict": triage.get("verdict"),
        "failed_checks": triage.get("failed_checks") or [],
        "slo_warning_count": summary.get("slo_warning_count"),
        "slo_limited_evidence_count": summary.get("slo_limited_evidence_count"),
        "slo_required_accepted_count": summary.get("slo_required_accepted_count"),
        "slo_required_contract_count": summary.get("slo_required_contract_count"),
        "slo_warnings": summary.get("slo_warnings") or [],
        "concurrency_required": summary.get("concurrency_required"),
        "concurrency_accepted": summary.get("concurrency_accepted"),
        "concurrency_limited": summary.get("concurrency_limited"),
        "concurrency_verdict": summary.get("concurrency_verdict"),
        "concurrency_failure_count": summary.get("concurrency_failure_count"),
        "dialog_health_ok_count": summary.get("dialog_health_ok_count"),
        "dialog_health_error_count": summary.get("dialog_health_error_count"),
        "limited_evidence_triaged": decision.get("limited_evidence_triaged"),
        "release_blocker": decision.get("release_blocker"),
        "queue_batch_service_remains_default": decision.get(
            "queue_batch_service_remains_default"
        ),
        "do_not_promote_true_batch": decision.get("do_not_promote_true_batch"),
        "continue_collecting_production_mixed_concurrency": decision.get(
            "continue_collecting_production_mixed_concurrency"
        ),
        "runtime_started": audit.get("runtime_started"),
        "compile_started": audit.get("compile_started"),
    }


def summarize_queue_health_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    remote = snapshot.get("remote") or {}
    service = remote.get("service") or {}
    queue = remote.get("queue") or {}
    latest_text = remote.get("latest_text_queue_run") or {}
    latest_partial = remote.get("latest_partial_batch_flush") or {}
    fast_path = snapshot.get("fast_path_regression") or {}
    checks = snapshot.get("checks") or {}
    decision = snapshot.get("decision") or {}
    return {
        "verdict": snapshot.get("verdict"),
        "queue_active": service.get("queue_active"),
        "queue_enabled": service.get("queue_enabled"),
        "gateway_active": service.get("gateway_active"),
        "gateway_enabled": service.get("gateway_enabled"),
        "openclaw_gateway_active": service.get("openclaw_gateway_active"),
        "gateway_listener_matches_main_pid": checks.get("gateway_listener_matches_main_pid"),
        "pending_count": queue.get("pending_count"),
        "processing_count": queue.get("processing_count"),
        "queue_idle_at_probe": checks.get("queue_idle_at_probe"),
        "latest_text_queue_run_path": latest_text.get("path"),
        "latest_text_queue_run_verdict": latest_text.get("verdict"),
        "latest_text_queue_job_status": latest_text.get("job_status"),
        "latest_text_queue_ms_per_request": latest_text.get("ms_per_request"),
        "partial_batch_flush_evidence_ready": checks.get("partial_batch_flush_evidence_ready"),
        "partial_batch_flush_run_dir": latest_partial.get("run_dir"),
        "partial_batch_flush_ms_per_request": latest_partial.get("ms_per_request"),
        "true_batch_process_count": len(remote.get("true_batch_processes") or []),
        "no_true_batch_or_compile_process": checks.get("no_true_batch_or_compile_process"),
        "fast_path_regression_verdict": fast_path.get("verdict"),
        "quick_ready_first_content_ms": fast_path.get("quick_ready_first_content_ms"),
        "localized_status_first_content_ms": fast_path.get("localized_status_first_content_ms"),
        "queue_batch_service_remains_default": decision.get("queue_batch_service_remains_default"),
        "do_not_start_true_batch_runtime_now": decision.get("do_not_start_true_batch_runtime_now"),
        "do_not_start_compile_now": decision.get("do_not_start_compile_now"),
    }


def summarize_workstream_overlap_audit(audit: dict[str, Any]) -> dict[str, Any]:
    true_batch = audit.get("true_batch_prior_work") or {}
    queue = audit.get("queue_batch_current_work") or {}
    next_work = audit.get("next_true_batch_work") or {}
    decision = audit.get("decision") or {}
    return {
        "verdict": audit.get("verdict"),
        "current_workstream": decision.get("current_workstream"),
        "queue_batch_work_duplicates_prior_true_batch_rental": decision.get(
            "queue_batch_work_duplicates_prior_true_batch_rental"
        ),
        "do_not_start_standard_true_batch_runtime_now": decision.get(
            "do_not_start_standard_true_batch_runtime_now"
        ),
        "do_not_start_true_batch_compile_now": decision.get(
            "do_not_start_true_batch_compile_now"
        ),
        "remote_group_major_report_count": true_batch.get("remote_group_major_report_count"),
        "remote_group_major_report_json_count": true_batch.get(
            "remote_group_major_report_json_count"
        ),
        "remote_b4_group_major_report_count": true_batch.get("remote_b4_group_major_report_count"),
        "remote_b4_group_major_report_json_count": true_batch.get(
            "remote_b4_group_major_report_json_count"
        ),
        "missing_report_json_dirs": true_batch.get("missing_report_json_dirs") or [],
        "local_b4_json_count": true_batch.get("local_b4_json_count"),
        "b4_hbm_count": true_batch.get("b4_hbm_count"),
        "b4_manifest_count": true_batch.get("b4_manifest_count"),
        "b4_remote_local_count_match": true_batch.get("b4_remote_local_count_match"),
        "b4_remote_json_local_count_match": true_batch.get(
            "b4_remote_json_local_count_match"
        ),
        "b4_history_is_already_mirrored_locally": true_batch.get(
            "b4_history_is_already_mirrored_locally"
        ),
        "run_more_standard_b4_runtime_sweeps_now": true_batch.get(
            "run_more_standard_b4_runtime_sweeps_now"
        ),
        "queue_health_verdict": queue.get("queue_health_verdict"),
        "queue_idle_at_probe": queue.get("queue_idle_at_probe"),
        "no_true_batch_or_compile_process": queue.get("no_true_batch_or_compile_process"),
        "next_nonduplicate_runtime_candidate": next_work.get("next_nonduplicate_runtime_candidate"),
        "s100p_runtime_experiment_now": next_work.get("s100p_runtime_experiment_now"),
        "allowed_experiments": next_work.get("allowed_experiments") or [],
        "last_token_compile_ready": next_work.get("last_token_compile_ready"),
        "last_token_runtime_validation_ready": next_work.get("last_token_runtime_validation_ready"),
        "compile_do_not_start_compile_now": next_work.get("compile_do_not_start_compile_now"),
        "failed_checks": audit.get("failed_checks") or [],
    }


def summarize_tuning_decision_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    decision = matrix.get("decision") or {}
    rows = matrix.get("matrix_rows") or []
    row_by_lever = {str(row.get("lever")): row for row in rows}
    def row_decision(lever: str) -> Any:
        return (row_by_lever.get(lever) or {}).get("decision")

    def row_allowed(lever: str) -> Any:
        return (row_by_lever.get(lever) or {}).get("allowed_now")

    return {
        "verdict": matrix.get("verdict"),
        "row_count": len(rows),
        "recommended_runtime_default": decision.get("recommended_runtime_default"),
        "recommended_true_batch_b4_policy": decision.get("recommended_true_batch_b4_policy"),
        "preferred_group_policy": decision.get("preferred_group_policy"),
        "preferred_inner_order": decision.get("preferred_inner_order"),
        "primary_code_target": decision.get("primary_code_target"),
        "secondary_research_target": decision.get("secondary_research_target"),
        "primary_code_target_projected_saved_ms_per_request": decision.get(
            "primary_code_target_projected_saved_ms_per_request"
        ),
        "primary_code_target_not_bpu_promotion_proof": decision.get(
            "primary_code_target_not_bpu_promotion_proof"
        ),
        "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage": decision.get(
            "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
        ),
        "next_s100p_runtime_experiment_allowed": decision.get(
            "next_s100p_runtime_experiment_allowed"
        ),
        "next_compile_allowed": decision.get("next_compile_allowed"),
        "inner_order_decision": row_decision("inner_order"),
        "inner_order_allowed_now": row_allowed("inner_order"),
        "group_count_decision": row_decision("group_count_mb512"),
        "group_count_allowed_now": row_allowed("group_count_mb512"),
        "final_group_isolation_decision": row_decision("final_logits_group_isolation"),
        "lower_peak_partition_decision": row_decision("lower_peak_hbm_partition"),
        "microbatch_count_decision": row_decision("microbatch_count"),
        "python_gap_decision": row_decision("python_inter_segment_gap"),
        "hidden_reuse_decision": row_decision("hidden_materialize_buffer_reuse"),
        "final_logits_decision": row_decision("final_logits_output_avoidance"),
        "final_logits_primary_evidence": (row_by_lever.get("final_logits_output_avoidance") or {}).get(
            "primary_evidence"
        )
        or {},
        "queue_batch_default_decision": row_decision("queue_batch_production_default"),
        "blockers": matrix.get("blockers") or [],
    }


def summarize_per_run_evidence_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    summary = matrix.get("summary") or {}
    findings = matrix.get("findings") or {}
    slowest = findings.get("slowest_segment_consistency") or {}
    scaling = findings.get("microbatch_scaling") or {}
    inner = findings.get("inner_order_mb512") or {}
    split = (findings.get("group_split_mb512") or {}).get("against_gap_field_baseline") or {}
    admission = findings.get("admission") or {}
    return {
        "verdict": matrix.get("verdict"),
        "run_count": summary.get("run_count"),
        "successful_run_count": summary.get("successful_run_count"),
        "failed_run_count": summary.get("failed_run_count"),
        "baseline_name": summary.get("baseline_name"),
        "baseline_ms_per_request": summary.get("baseline_ms_per_request"),
        "most_common_top_segment": slowest.get("most_common_top_segment"),
        "most_common_top_segment_count": slowest.get("most_common_top_segment_count"),
        "eligible_success_run_count": slowest.get("eligible_success_run_count"),
        "most_common_top_segment_rate": slowest.get("most_common_top_segment_rate"),
        "microbatch_scaling_from_to": scaling.get("from_to"),
        "microbatch_scaling_avg_bpu_delta": scaling.get("avg_bpu_delta"),
        "microbatch_scaling_nonzero_bpu_delta": scaling.get("nonzero_bpu_delta"),
        "microbatch_scaling_ms_per_request_ratio": scaling.get("ms_per_request_ratio"),
        "inner_order_segment_major_delta_ms_per_request": inner.get(
            "segment_major_ms_per_request_delta"
        ),
        "group_split_g6_delta_ms_per_request": split.get(
            "six_group_delta_ms_per_request"
        ),
        "group_split_g7_delta_ms_per_request": split.get(
            "seven_group_delta_ms_per_request"
        ),
        "group_split_final_isolated_delta_ms_per_request": split.get(
            "final_isolated_delta_ms_per_request"
        ),
        "preferred_group_policy": admission.get("preferred_group_policy")
        or summary.get("preferred_group_policy"),
        "preferred_inner_order": admission.get("preferred_inner_order")
        or summary.get("preferred_inner_order"),
        "primary_schedule_bottleneck": admission.get("primary_schedule_bottleneck"),
        "primary_code_target": admission.get("primary_code_target"),
        "standard_b4_runtime_sweep_status": admission.get(
            "standard_b4_runtime_sweep_status"
        )
        or summary.get("standard_b4_runtime_sweep_status"),
        "run_more_standard_group_or_inner_order_sweeps_now": admission.get(
            "run_more_standard_b4_group_or_inner_order_sweeps_now"
        )
        if "run_more_standard_b4_group_or_inner_order_sweeps_now" in admission
        else summary.get("run_more_standard_group_or_inner_order_sweeps_now"),
        "next_nonduplicate_runtime_candidate": admission.get(
            "next_nonduplicate_runtime_candidate"
        )
        or summary.get("next_nonduplicate_runtime_candidate"),
        "would_start_runtime": admission.get("would_start_runtime"),
        "would_start_compile": admission.get("would_start_compile"),
        "failed_checks": matrix.get("failed_checks") or [],
    }


def load_optional(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return read_json(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    parser.add_argument("--analysis-root", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    args = parser.parse_args()

    schedule_path = args.analysis_root / "dream7b_true_batch_b4_schedule_analysis_current.json"
    prealloc_path = args.analysis_root / "dream7b_b4_prealloc_hidden_ab_20260619.json"
    group_split_path = args.analysis_root / "dream7b_b4_mb128_group_split_20260619.json"
    final_logits_path = args.analysis_root / "dream7b_b4_final_logits_breakdown_20260619.json"
    final_output_path = args.analysis_root / "dream7b_b4_final_output_attribution_20260619.json"
    hbm_load_path = args.analysis_root / "dream7b_b4_hbm_load_breakdown_20260619.json"
    bottleneck_closure_path = (
        args.analysis_root / "dream7b_b4_bottleneck_closure_model_20260621.json"
    )
    last_token_sizing_path = args.analysis_root / "dream7b_b4_final_logits_candidate_sizing_20260619.json"
    last_token_experiment_path = args.analysis_root / "dream7b_b4_last_token_final_logits_experiment_20260619.md"
    last_token_readiness_path = args.analysis_root / "dream7b_b4_last_token_compile_readiness_20260619.json"
    last_token_gate_path = args.analysis_root / "dream7b_b4_last_token_experiment_gate_20260620.json"
    last_token_runtime_validation_plan_path = (
        args.analysis_root / "dream7b_b4_last_token_runtime_validation_plan_20260620.json"
    )
    last_token_validation_compare_path = (
        args.analysis_root / "dream7b_b4_last_token_validation_compare_20260620.json"
    )
    final_logits_leverage_model_path = (
        args.analysis_root / "dream7b_b4_final_logits_leverage_model_20260621.json"
    )
    compile_capacity_path = args.analysis_root / "dream7b_b4_compile_capacity_plan_20260619.json"
    saturation_path = args.analysis_root / "dream7b_b4_scaling_saturation_analysis_20260619.json"
    group_switch_path = args.analysis_root / "dream7b_b4_group_switch_accounting_20260619.json"
    runtime_boundary_path = args.analysis_root / "dream7b_b4_runtime_capacity_boundary_20260620.json"
    group_order_path = args.analysis_root / "dream7b_b4_group_order_candidate_analysis_20260620.json"
    group_partition_planner_path = args.analysis_root / "dream7b_b4_group_partition_planner_20260620.json"
    group_inner_order_value_audit_path = (
        args.analysis_root / "dream7b_b4_group_inner_order_value_audit_20260621.json"
    )
    true_batch_nas_inventory_path = latest_json_or_fallback(
        args.analysis_root,
        "dream7b_true_batch_nas_inventory_*.json",
        args.analysis_root / "dream7b_true_batch_nas_inventory_20260620.json",
    )
    runtime_experiment_gate_path = args.analysis_root / "dream7b_b4_runtime_experiment_gate_20260620.json"
    runtime_command_guard_path = args.analysis_root / "dream7b_b4_runtime_command_guard_20260621.json"
    compile_command_guard_path = args.analysis_root / "dream7b_b4_compile_command_guard_20260621.json"
    next_action_admission_pack_path = (
        args.analysis_root / "dream7b_b4_next_action_admission_pack_20260621.json"
    )
    segment_drag_path = args.analysis_root / "dream7b_b4_segment_drag_breakdown_20260619.json"
    segment_bottleneck_path = args.analysis_root / "dream7b_b4_segment_bottleneck_scorecard_20260620.json"
    segment_group_schedule_scorecard_path = (
        args.analysis_root / "dream7b_b4_segment_group_schedule_scorecard_20260621.json"
    )
    per_run_evidence_matrix_path = (
        args.analysis_root / "dream7b_b4_per_run_evidence_matrix_20260622.json"
    )
    segment_stability_audit_path = args.analysis_root / "dream7b_b4_segment_stability_audit_20260620.json"
    scheduler_overhead_path = args.analysis_root / "dream7b_b4_scheduler_overhead_budget_20260620.json"
    runtime_refactor_backlog_path = args.analysis_root / "dream7b_b4_runtime_refactor_backlog_20260621.json"
    runtime_refactor_source_contract_path = (
        args.analysis_root / "dream7b_b4_runtime_refactor_source_contract_20260621.json"
    )
    runtime_refactor_admission_contract_path = (
        args.analysis_root / "dream7b_b4_runtime_refactor_admission_contract_20260621.json"
    )
    runtime_source_implementation_map_path = (
        args.analysis_root / "dream7b_b4_runtime_source_implementation_map_20260621.json"
    )
    runtime_refactor_work_order_path = (
        args.analysis_root / "dream7b_b4_runtime_refactor_work_order_20260622.json"
    )
    runtime_instrumentation_contract_path = (
        args.analysis_root / "dream7b_true_batch_runtime_instrumentation_contract_20260621.json"
    )
    runtime_instrumentation_deployment_path = (
        args.analysis_root / "dream7b_true_batch_runtime_instrumentation_deployment_contract_20260621.json"
    )
    hbm_load_accounting_contract_path = (
        args.analysis_root / "dream7b_true_batch_hbm_load_accounting_contract_20260621.json"
    )
    post_instrumentation_telemetry_gate_path = (
        args.analysis_root / "dream7b_b4_post_instrumentation_telemetry_gate_20260621.json"
    )
    post_instrumentation_overhead_analysis_path = (
        args.analysis_root / "dream7b_b4_post_instrumentation_overhead_analysis_20260621.json"
    )
    post_instrumentation_segment_attribution_path = (
        args.analysis_root / "dream7b_b4_post_instrumentation_segment_attribution_20260621.json"
    )
    hidden_buffer_reuse_decision_path = (
        args.analysis_root / "dream7b_b4_hidden_buffer_reuse_decision_20260621.json"
    )
    hidden_materialize_design_contract_path = (
        args.analysis_root / "dream7b_b4_hidden_materialize_design_contract_20260622.json"
    )
    hidden_materialize_telemetry_contract_path = (
        args.analysis_root
        / "dream7b_b4_hidden_materialize_telemetry_contract_20260622.json"
    )
    tuning_decision_matrix_path = (
        args.analysis_root / "dream7b_b4_tuning_decision_matrix_20260621.json"
    )
    guardrail_path = latest_json(args.snapshot_root, "dream7b_product_guardrail_snapshot_*/dream7b_product_guardrail_snapshot.json")
    slo_path = latest_json_with_verdict(
        args.snapshot_root,
        "operational_slo_rollup_contract_*/operational_slo_rollup_contract.json",
        "ok_ai_nas_operational_slo_rollup_contract",
    )
    portal_path = latest_json_with_verdict(
        args.snapshot_root,
        "operator_portal_contract_*/operator_portal_contract.json",
        "ok_ai_nas_operator_portal_contract",
    )
    partial_batch_flush_path = latest_json(
        args.snapshot_root, "dream7b_queue_partial_batch_flush_probe_*/dream7b_queue_partial_batch_flush_probe.json"
    )
    queue_health_snapshot_path = latest_json(
        args.snapshot_root, "dream7b_queue_health_snapshot_*/dream7b_queue_health_snapshot.json"
    )
    workstream_overlap_audit_path = latest_json(
        args.snapshot_root, "dream7b_workstream_overlap_audit_*/dream7b_workstream_overlap_audit.json"
    )
    first_response_path = latest_json(args.snapshot_root, "dream7b_first_response_packet_*/dream7b_first_response_packet.json")
    first_response_routing_path = latest_json(
        args.snapshot_root, "dream7b_first_response_routing_packet_*/dream7b_first_response_routing_packet.json"
    )
    first_response_fast_status_path = latest_json(
        args.snapshot_root, "dream7b_first_response_fast_status_packet_*/dream7b_first_response_fast_status_packet.json"
    )
    fast_path_regression_path = latest_json(
        args.snapshot_root, "dream7b_fast_path_regression_*/dream7b_fast_path_regression.json"
    )
    first_response_slo_tier_guard_path = (
        args.snapshot_root / "dream7b_first_response_slo_tier_guard_latest.json"
    )
    first_response_warning_triage_path = (
        args.snapshot_root / "dream7b_first_response_warning_triage_latest.json"
    )
    slo_limited_evidence_triage_path = (
        args.snapshot_root / "ai_nas_slo_limited_evidence_triage_latest.json"
    )
    gateway_listener_path = latest_json(
        args.snapshot_root, "dream7b_gateway_listener_ownership_*/dream7b_gateway_listener_ownership.json"
    )
    gateway_listener_drift_path = latest_json(
        args.snapshot_root, "dream7b_gateway_listener_drift_gate_*/dream7b_gateway_listener_drift_gate.json"
    )

    remote = ssh_cmd(
        args,
        "\n".join(
            [
                "set -eu",
                "SERVICE=dream7b-bpu-batch-queue.service",
                'echo service_active=$(systemctl is-active "$SERVICE" 2>/dev/null || true)',
                'echo service_enabled=$(systemctl is-enabled "$SERVICE" 2>/dev/null || true)',
                'echo service_description="$(systemctl show "$SERVICE" -p Description --value 2>/dev/null || true)"',
                'echo service_active_since="$(systemctl show "$SERVICE" -p ActiveEnterTimestamp --value 2>/dev/null || true)"',
                'echo gateway_active="$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service 2>/dev/null || true)"',
                'echo gateway_enabled="$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-enabled dream7b-local-openai-gateway.service 2>/dev/null || true)"',
                'echo rollback_script="$(find /mnt/nas/openclaw -type f -name dream7b-default-rollback 2>/dev/null | sort | tail -1)"',
                'echo status_script="$(find /mnt/nas/openclaw -type f -name dream7b-default-status 2>/dev/null | sort | tail -1)"',
                'QUEUE_SERVICE=/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py',
                'if grep -q partial_batch_flush_timeout "$QUEUE_SERVICE" 2>/dev/null; then echo queue_service_has_partial_batch_flush=true; else echo queue_service_has_partial_batch_flush=false; fi',
                'echo queue_pending_count="$(find /mnt/nas/openclaw/queues/dream7b-bpu/pending -maxdepth 1 -type f 2>/dev/null | wc -l)"',
                'echo queue_processing_count="$(find /mnt/nas/openclaw/queues/dream7b-bpu/processing -maxdepth 1 -type f 2>/dev/null | wc -l)"',
                'QUEUE_SUMMARY=/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/cross_job_queue_service_summary.json',
                'if test -f "$QUEUE_SUMMARY"; then python3 -c \'import json,sys; p=sys.argv[1]; d=json.load(open(p)); runs=d.get("runs") or []; partial=[r for r in runs if r.get("run_reason")=="partial_batch_flush_timeout" and int(r.get("pending_count_at_start") or 0)>1 and int(r.get("returncode") or 0)==0 and str(r.get("runner_verdict"))=="ok_dream7b_bpu_segment_major_load_once_queue_runner"]; last=partial[-1] if partial else {}; print("queue_service_summary_json="+p); print("queue_partial_batch_flush_ready="+str(bool(partial)).lower()); print("queue_partial_batch_last_run_dir="+str(last.get("run_dir") or "")); print("queue_partial_batch_pending_count_at_start="+str(last.get("pending_count_at_start") or "")); print("queue_partial_batch_effective_max_job_count="+str(last.get("effective_max_job_count") or "")); print("queue_partial_batch_processed_request_count="+str(last.get("processed_request_count") or "")); print("queue_partial_batch_ms_per_request="+str(last.get("amortized_wall_ms_per_processed_request") or ""))\' "$QUEUE_SUMMARY"; else echo queue_partial_batch_flush_ready=false; fi',
                'PROBE=/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py',
                'PY=/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python',
                'if "$PY" "$PROBE" --help 2>/dev/null | grep -q -- "--final-hbm-root"; then echo probe_has_final_hbm_root=true; else echo probe_has_final_hbm_root=false; fi',
                'if "$PY" "$PROBE" --help 2>/dev/null | grep -q -- "--final-logits-mode"; then echo probe_has_final_logits_mode=true; else echo probe_has_final_logits_mode=false; fi',
                'ALT=/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final/seg27_28',
                'HBM=$ALT/dream7b_segment_27_28_seq16_b4_q8_last_token_logits.hbm',
                'if test -f "$HBM"; then echo last_token_hbm_exists=true; else echo last_token_hbm_exists=false; fi',
                'if test -d "$ALT" && test -f "$ALT/manifest.sha256" && (cd "$ALT" && sha256sum -c manifest.sha256 >/dev/null 2>&1); then echo last_token_manifest_verified=true; else echo last_token_manifest_verified=false; fi',
            ]
        ),
        timeout=30,
    )
    remote_values = parse_kv(remote["stdout"])

    schedule = read_json(schedule_path)
    prealloc = read_json(prealloc_path)
    group_split = read_json(group_split_path)
    final_logits = read_json(final_logits_path)
    final_output = load_optional(final_output_path)
    hbm_load = load_optional(hbm_load_path)
    bottleneck_closure = load_optional(bottleneck_closure_path)
    last_token_sizing = load_optional(last_token_sizing_path)
    last_token_readiness = load_optional(last_token_readiness_path)
    last_token_gate = load_optional(last_token_gate_path)
    last_token_runtime_validation_plan = load_optional(last_token_runtime_validation_plan_path)
    last_token_validation_compare = load_optional(last_token_validation_compare_path)
    final_logits_leverage_model = load_optional(final_logits_leverage_model_path)
    compile_capacity = load_optional(compile_capacity_path)
    saturation = load_optional(saturation_path)
    group_switch = load_optional(group_switch_path)
    runtime_boundary = load_optional(runtime_boundary_path)
    group_order = load_optional(group_order_path)
    group_partition_planner = load_optional(group_partition_planner_path)
    group_inner_order_value_audit = load_optional(group_inner_order_value_audit_path)
    true_batch_nas_inventory = load_optional(true_batch_nas_inventory_path)
    runtime_experiment_gate = load_optional(runtime_experiment_gate_path)
    runtime_command_guard = load_optional(runtime_command_guard_path)
    compile_command_guard = load_optional(compile_command_guard_path)
    next_action_admission_pack = load_optional(next_action_admission_pack_path)
    segment_drag = load_optional(segment_drag_path)
    segment_bottleneck = load_optional(segment_bottleneck_path)
    segment_group_schedule_scorecard = load_optional(segment_group_schedule_scorecard_path)
    per_run_evidence_matrix = load_optional(per_run_evidence_matrix_path)
    segment_stability_audit = load_optional(segment_stability_audit_path)
    scheduler_overhead = load_optional(scheduler_overhead_path)
    runtime_refactor_backlog = load_optional(runtime_refactor_backlog_path)
    runtime_refactor_source_contract = load_optional(runtime_refactor_source_contract_path)
    runtime_refactor_admission_contract = load_optional(runtime_refactor_admission_contract_path)
    runtime_source_implementation_map = load_optional(runtime_source_implementation_map_path)
    runtime_refactor_work_order = load_optional(runtime_refactor_work_order_path)
    runtime_instrumentation_contract = load_optional(runtime_instrumentation_contract_path)
    runtime_instrumentation_deployment = load_optional(runtime_instrumentation_deployment_path)
    hbm_load_accounting_contract = load_optional(hbm_load_accounting_contract_path)
    post_instrumentation_telemetry_gate = load_optional(post_instrumentation_telemetry_gate_path)
    post_instrumentation_overhead_analysis = load_optional(
        post_instrumentation_overhead_analysis_path
    )
    post_instrumentation_segment_attribution = load_optional(
        post_instrumentation_segment_attribution_path
    )
    hidden_buffer_reuse_decision = load_optional(hidden_buffer_reuse_decision_path)
    hidden_materialize_design_contract = load_optional(
        hidden_materialize_design_contract_path
    )
    hidden_materialize_telemetry_contract = load_optional(
        hidden_materialize_telemetry_contract_path
    )
    tuning_decision_matrix = load_optional(tuning_decision_matrix_path)
    guardrail = load_optional(guardrail_path)
    slo = load_optional(slo_path)
    portal = load_optional(portal_path)
    partial_batch_flush = load_optional(partial_batch_flush_path)
    queue_health_snapshot = load_optional(queue_health_snapshot_path)
    workstream_overlap_audit = load_optional(workstream_overlap_audit_path)
    first_response = load_optional(first_response_path)
    first_response_routing = load_optional(first_response_routing_path)
    first_response_fast_status = load_optional(first_response_fast_status_path)
    fast_path_regression = load_optional(fast_path_regression_path)
    first_response_slo_tier_guard = load_optional(first_response_slo_tier_guard_path)
    first_response_warning_triage = load_optional(first_response_warning_triage_path)
    slo_limited_evidence_triage = load_optional(slo_limited_evidence_triage_path)
    gateway_listener = load_optional(gateway_listener_path)
    gateway_listener_drift = load_optional(gateway_listener_drift_path)

    service_active = remote_values.get("service_active") == "active"
    service_enabled = remote_values.get("service_enabled") == "enabled"
    gateway_active = remote_values.get("gateway_active") == "active"
    gateway_enabled = remote_values.get("gateway_enabled") == "enabled"
    rollback_present = bool(remote_values.get("rollback_script"))
    queue_partial_batch_flush_live_summary_ready = (
        remote_values.get("queue_service_has_partial_batch_flush") == "true"
        and remote_values.get("queue_partial_batch_flush_ready") == "true"
    )
    b4 = summarize_current_b4(schedule)
    b4_below_queue = as_float(b4.get("avg_bpu_gap_points_vs_queue")) < 0.0 and as_float(
        b4.get("nonzero_bpu_gap_points_vs_queue")
    ) < 0.0
    slo_ok = slo.get("verdict") == "ok_ai_nas_operational_slo_rollup_contract"
    portal_ok = portal.get("verdict") == "ok_ai_nas_operator_portal_contract"
    guardrail_ok = guardrail.get("verdict") == "ok_dream7b_product_guardrail_snapshot"
    partial_batch_flush_ok = partial_batch_flush.get("verdict") == "ok_dream7b_queue_partial_batch_flush_probe"
    queue_health_snapshot_ok = queue_health_snapshot.get("verdict") == "ok_dream7b_queue_health_snapshot"
    partial_batch_probe_checks = (partial_batch_flush.get("remote") or {}).get("checks") or {}
    partial_batch_probe_summary = (
        ((partial_batch_flush.get("remote") or {}).get("service_summary") or {}).get(
            "latest_partial_batch_run"
        )
        or {}
    )
    queue_health_partial_ready = (
        (queue_health_snapshot.get("checks") or {}).get("partial_batch_flush_evidence_ready")
        is True
    )
    queue_health_partial = (
        ((queue_health_snapshot.get("remote") or {}).get("latest_partial_batch_flush") or {})
    )
    queue_partial_batch_flush_probe_ready = (
        partial_batch_flush_ok
        and partial_batch_probe_checks.get("partial_batch_flush_evidence_ready") is True
        and int(partial_batch_probe_summary.get("pending_count_at_start") or 0) > 1
        and int(partial_batch_probe_summary.get("effective_max_job_count") or 0)
        == int(partial_batch_probe_summary.get("pending_count_at_start") or 0)
        and int(partial_batch_probe_summary.get("processed_request_count") or 0)
        == int(partial_batch_probe_summary.get("pending_count_at_start") or 0)
    )
    queue_partial_batch_health_ready = (
        queue_health_snapshot_ok
        and queue_health_partial_ready
        and int(queue_health_partial.get("pending_count_at_start") or 0) > 1
        and int(queue_health_partial.get("effective_max_job_count") or 0)
        == int(queue_health_partial.get("pending_count_at_start") or 0)
        and int(queue_health_partial.get("processed_request_count") or 0)
        == int(queue_health_partial.get("pending_count_at_start") or 0)
    )
    queue_partial_batch_flush_ready = (
        queue_partial_batch_flush_live_summary_ready
        or queue_partial_batch_flush_probe_ready
        or queue_partial_batch_health_ready
    )
    workstream_overlap_ok = workstream_overlap_audit.get("verdict") == "ok_dream7b_workstream_overlap_audit"
    first_response_ok = (
        first_response_fast_status.get("verdict") == "ok_dream7b_first_response_fast_status_packet"
        and fast_path_regression.get("verdict") == "ok_dream7b_fast_path_regression"
    )
    first_response_slo_tier_guard_ok = (
        first_response_slo_tier_guard.get("verdict")
        == "ok_dream7b_first_response_slo_tier_guard"
        and not (first_response_slo_tier_guard.get("failed_checks") or [])
        and (first_response_slo_tier_guard.get("decision") or {}).get(
            "queue_batch_service_remains_default"
        )
        is True
        and (first_response_slo_tier_guard.get("decision") or {}).get(
            "fast_paths_satisfy_interactive_first_content_slo"
        )
        is True
        and (first_response_slo_tier_guard.get("decision") or {}).get(
            "sse_progress_satisfies_interactive_progress_slo"
        )
        is True
        and (first_response_slo_tier_guard.get("decision") or {}).get(
            "backend_first_content_latency_is_not_true_batch_work"
        )
        is True
        and (first_response_slo_tier_guard.get("audit") or {}).get("runtime_started")
        is False
        and (first_response_slo_tier_guard.get("audit") or {}).get("compile_started")
        is False
    )
    first_response_warning_triage_ok = (
        first_response_warning_triage.get("verdict")
        == "ok_dream7b_first_response_warning_triage"
        and not (first_response_warning_triage.get("failed_checks") or [])
        and (first_response_warning_triage.get("decision") or {}).get(
            "warning_is_product_triaged"
        )
        is True
        and (first_response_warning_triage.get("decision") or {}).get(
            "queue_batch_service_remains_default"
        )
        is True
        and (first_response_warning_triage.get("decision") or {}).get(
            "do_not_promote_true_batch_for_first_response"
        )
        is True
        and (first_response_warning_triage.get("summary") or {}).get(
            "backend_first_content_latency_is_not_true_batch_work"
        )
        is True
        and (first_response_warning_triage.get("audit") or {}).get("runtime_started")
        is False
        and (first_response_warning_triage.get("audit") or {}).get("compile_started")
        is False
    )
    slo_limited_evidence_triage_ok = (
        slo_limited_evidence_triage.get("verdict")
        == "ok_ai_nas_slo_limited_evidence_triage"
        and not (slo_limited_evidence_triage.get("failed_checks") or [])
        and (slo_limited_evidence_triage.get("decision") or {}).get(
            "limited_evidence_triaged"
        )
        is True
        and (slo_limited_evidence_triage.get("decision") or {}).get("release_blocker")
        is False
        and (slo_limited_evidence_triage.get("summary") or {}).get("slo_warnings")
        == ["concurrency_stability:limited_production_evidence"]
        and (slo_limited_evidence_triage.get("audit") or {}).get("runtime_started")
        is False
        and (slo_limited_evidence_triage.get("audit") or {}).get("compile_started")
        is False
    )
    gateway_listener_ok = (
        gateway_listener.get("verdict") == "ok_dream7b_gateway_listener_ownership"
        and (gateway_listener.get("summary") or {}).get("listener_matches_systemd_main_pid") is True
        and (gateway_listener.get("summary") or {}).get("orphan_listener_detected") is False
    )
    gateway_listener_drift_ok = (
        gateway_listener_drift.get("verdict") == "ok_dream7b_gateway_listener_drift_gate"
        and (gateway_listener_drift.get("summary") or {}).get("live_listener_matches_systemd_main_pid")
        is True
        and (gateway_listener_drift.get("summary") or {}).get("live_orphan_listener_detected")
        is False
        and (gateway_listener_drift.get("summary") or {}).get("live_health_ok") is True
    )
    runtime_instrumentation_ready = (
        runtime_instrumentation_contract.get("verdict")
        == "ok_dream7b_true_batch_runtime_instrumentation_contract"
        and runtime_instrumentation_deployment.get("verdict")
        == "ok_dream7b_true_batch_runtime_instrumentation_deployment_contract"
        and (runtime_instrumentation_contract.get("behavior") or {}).get("default_cli_changed")
        is False
        and (runtime_instrumentation_contract.get("behavior") or {}).get("runtime_order_changed")
        is False
        and (runtime_instrumentation_deployment.get("checks") or {}).get("no_true_batch_runtime_started")
        is True
        and (runtime_instrumentation_deployment.get("checks") or {}).get("no_compile_started")
        is True
    )
    tuning_decision_matrix_ok = (
        tuning_decision_matrix.get("verdict") == "ok_dream7b_b4_tuning_decision_matrix"
        and ((tuning_decision_matrix.get("decision") or {}).get("next_s100p_runtime_experiment_allowed") is False)
        and ((tuning_decision_matrix.get("decision") or {}).get("next_compile_allowed") is False)
    )
    group_inner_order_value_audit_ok = (
        group_inner_order_value_audit.get("verdict")
        == "ok_dream7b_b4_group_inner_order_value_audit"
        and not (group_inner_order_value_audit.get("failed_checks") or [])
        and (group_inner_order_value_audit.get("decision") or {}).get(
            "run_more_group_size_or_inner_order_sweeps_now"
        )
        is False
        and (group_inner_order_value_audit.get("decision") or {}).get(
            "group_size_and_inner_order_are_current_primary_levers"
        )
        is False
        and (group_inner_order_value_audit.get("decision") or {}).get(
            "next_s100p_runtime_experiment_allowed_now"
        )
        is False
        and (group_inner_order_value_audit.get("decision") or {}).get(
            "next_compile_allowed_now"
        )
        is False
        and (group_inner_order_value_audit.get("audit") or {}).get("runtime_started")
        is False
        and (group_inner_order_value_audit.get("audit") or {}).get("compile_started")
        is False
    )
    runtime_command_guard_ok = (
        runtime_command_guard.get("verdict") == "ok_dream7b_b4_runtime_command_guard"
        and (runtime_command_guard.get("guard") or {}).get("command_guard_active") is True
        and (runtime_command_guard.get("guard") or {}).get("standard_sweep_commands_blocked")
        is True
        and (runtime_command_guard.get("guard") or {}).get("command_admitted") is False
        and (runtime_command_guard.get("guard") or {}).get("would_start_runtime") is False
    )
    compile_command_guard_ok = (
        compile_command_guard.get("verdict") == "ok_dream7b_b4_compile_command_guard"
        and (compile_command_guard.get("guard") or {}).get("compile_guard_active") is True
        and (compile_command_guard.get("guard") or {}).get(
            "only_single_segment_last_token_compile_allowed"
        )
        is True
        and (compile_command_guard.get("guard") or {}).get("b8_full_compile_blocked")
        is True
        and (compile_command_guard.get("guard") or {}).get("command_admitted") is False
        and (compile_command_guard.get("guard") or {}).get("would_start_compile") is False
    )
    next_action_admission_pack_ok = (
        next_action_admission_pack.get("verdict")
        == "ok_dream7b_b4_next_action_admission_pack"
        and (next_action_admission_pack.get("summary") or {}).get("would_start_runtime")
        is False
        and (next_action_admission_pack.get("summary") or {}).get("would_start_compile")
        is False
        and (next_action_admission_pack.get("decision") or {}).get(
            "queue_batch_product_work_allowed_now"
        )
        is True
        and (next_action_admission_pack.get("decision") or {}).get(
            "compile_preflight_only_allowed_now"
        )
        is True
        and (next_action_admission_pack.get("summary") or {}).get(
            "per_run_matrix_gate_ready"
        )
        is True
        and (next_action_admission_pack.get("summary") or {}).get(
            "per_run_matrix_standard_sweep_status"
        )
        == "blocked_duplicate"
    )
    runtime_refactor_source_contract_ok = (
        runtime_refactor_source_contract.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_source_contract"
        and (runtime_refactor_source_contract.get("summary") or {}).get(
            "cli_defaults_preserved"
        )
        is True
        and (runtime_refactor_source_contract.get("summary") or {}).get(
            "last_token_path_supported"
        )
        is True
        and (runtime_refactor_source_contract.get("summary") or {}).get(
            "telemetry_contract_ready"
        )
        is True
        and (runtime_refactor_source_contract.get("summary") or {}).get(
            "protected_telemetry_fields_ready"
        )
        is True
        and int(
            (runtime_refactor_source_contract.get("summary") or {}).get(
                "protected_telemetry_field_count"
            )
            or 0
        )
        >= 22
        and int(
            (runtime_refactor_source_contract.get("summary") or {}).get(
                "protected_telemetry_missing_count"
            )
            or 0
        )
        == 0
        and (runtime_refactor_source_contract.get("summary") or {}).get(
            "runtime_order_changed"
        )
        is False
        and (runtime_refactor_source_contract.get("summary") or {}).get(
            "default_promotes_experimental_flags"
        )
        is False
    )
    runtime_refactor_admission_contract_ok = (
        runtime_refactor_admission_contract.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_admission_contract"
        and (runtime_refactor_admission_contract.get("summary") or {}).get(
            "queue_batch_remains_default"
        )
        is True
        and (runtime_refactor_admission_contract.get("summary") or {}).get(
            "local_report_only_refactor_allowed_now"
        )
        is True
        and (runtime_refactor_admission_contract.get("summary") or {}).get(
            "default_runtime_code_change_allowed_now"
        )
        is False
        and (runtime_refactor_admission_contract.get("summary") or {}).get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and (runtime_refactor_admission_contract.get("summary") or {}).get(
            "compile_start_allowed_now"
        )
        is False
        and (runtime_refactor_admission_contract.get("summary") or {}).get(
            "compile_preflight_only_allowed_now"
        )
        is True
        and int(
            (runtime_refactor_admission_contract.get("summary") or {}).get(
                "protected_telemetry_field_count"
            )
            or 0
        )
        >= 22
        and int(
            (runtime_refactor_admission_contract.get("summary") or {}).get(
                "protected_telemetry_missing_count"
            )
            or 0
        )
        == 0
        and not (runtime_refactor_admission_contract.get("failed_checks") or [])
    )
    segment_group_schedule_scorecard_ok = (
        segment_group_schedule_scorecard.get("verdict")
        == "ok_dream7b_b4_segment_group_schedule_scorecard"
        and not (segment_group_schedule_scorecard.get("failed_checks") or [])
        and (segment_group_schedule_scorecard.get("summary") or {}).get(
            "primary_single_segment_bottleneck"
        )
        == "seg27_28_final_logits"
        and (segment_group_schedule_scorecard.get("decision") or {}).get(
            "preferred_group_policy"
        )
        == "keep_existing_5_group_segment_major_default"
        and (segment_group_schedule_scorecard.get("decision") or {}).get(
            "preferred_inner_order"
        )
        == "segment-major"
        and (segment_group_schedule_scorecard.get("decision") or {}).get(
            "run_more_standard_b4_group_or_inner_order_sweeps_now"
        )
        is False
        and (segment_group_schedule_scorecard.get("decision") or {}).get(
            "run_new_group_partition_now"
        )
        is False
        and (segment_group_schedule_scorecard.get("decision") or {}).get(
            "run_s100p_runtime_now"
        )
        is False
        and (segment_group_schedule_scorecard.get("decision") or {}).get(
            "start_compile_now"
        )
        is False
        and (segment_group_schedule_scorecard.get("decision") or {}).get(
            "compile_preflight_only_now"
        )
        is True
        and (segment_group_schedule_scorecard.get("audit") or {}).get("runtime_started")
        is False
        and (segment_group_schedule_scorecard.get("audit") or {}).get("compile_started")
        is False
        and (segment_group_schedule_scorecard.get("audit") or {}).get(
            "remote_access_performed"
        )
        is False
    )
    per_run_evidence_matrix_summary = per_run_evidence_matrix.get("summary") or {}
    per_run_evidence_matrix_audit = per_run_evidence_matrix.get("audit") or {}
    per_run_evidence_matrix_ok = (
        per_run_evidence_matrix.get("verdict")
        == "ok_dream7b_b4_per_run_evidence_matrix"
        and not (per_run_evidence_matrix.get("failed_checks") or [])
        and int(per_run_evidence_matrix_summary.get("run_count") or 0) >= 20
        and int(per_run_evidence_matrix_summary.get("successful_run_count") or 0) >= 19
        and int(per_run_evidence_matrix_summary.get("failed_run_count") or 0) >= 1
        and per_run_evidence_matrix_summary.get("most_common_top_segment")
        == "seg27_final_logits"
        and float(
            per_run_evidence_matrix_summary.get("most_common_top_segment_rate") or 0.0
        )
        == 1.0
        and per_run_evidence_matrix_summary.get("standard_b4_runtime_sweep_status")
        == "blocked_duplicate"
        and per_run_evidence_matrix_summary.get(
            "run_more_standard_group_or_inner_order_sweeps_now"
        )
        is False
        and per_run_evidence_matrix_audit.get("remote_access_performed") is False
        and per_run_evidence_matrix_audit.get("runtime_started") is False
        and per_run_evidence_matrix_audit.get("compile_started") is False
    )
    runtime_source_implementation_map_ok = (
        runtime_source_implementation_map.get("verdict")
        == "ok_dream7b_b4_runtime_source_implementation_map"
        and not (runtime_source_implementation_map.get("failed_checks") or [])
        and not (runtime_source_implementation_map.get("missing_source_patterns") or [])
        and int(
            (runtime_source_implementation_map.get("summary") or {}).get(
                "source_pattern_count"
            )
            or 0
        )
        >= 40
        and int(
            (runtime_source_implementation_map.get("summary") or {}).get(
                "missing_source_pattern_count"
            )
            or 0
        )
        == 0
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "queue_batch_remains_default"
        )
        is True
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "primary_runtime_refactor_target"
        )
        == "seg27_28_last_token_logits_or_output_avoidance"
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "primary_schedule_bottleneck"
        )
        == "seg27_28_final_logits"
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "preferred_group_policy"
        )
        == "keep_existing_5_group_segment_major_default"
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "preferred_inner_order"
        )
        == "segment-major"
        and "segment_gap_and_loaded_segments_telemetry"
        in ((runtime_source_implementation_map.get("summary") or {}).get("allowed_now") or [])
        and "alternative_hidden_materialize_avoidance"
        in ((runtime_source_implementation_map.get("summary") or {}).get("allowed_now") or [])
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "compile_start_allowed_now"
        )
        is False
        and (runtime_source_implementation_map.get("summary") or {}).get(
            "runtime_default_change_allowed_now"
        )
        is False
        and (runtime_source_implementation_map.get("checks") or {}).get(
            "all_required_source_patterns_present"
        )
        is True
        and (runtime_source_implementation_map.get("checks") or {}).get(
            "defaults_preserved"
        )
        is True
        and (runtime_source_implementation_map.get("checks") or {}).get(
            "standard_group_inner_order_sweeps_blocked"
        )
        is True
        and (runtime_source_implementation_map.get("checks") or {}).get(
            "runtime_compile_not_started"
        )
        is True
        and (runtime_source_implementation_map.get("checks") or {}).get(
            "remote_access_not_performed"
        )
        is True
        and (runtime_source_implementation_map.get("audit") or {}).get("source_modified")
        is False
        and (runtime_source_implementation_map.get("audit") or {}).get("runtime_started")
        is False
        and (runtime_source_implementation_map.get("audit") or {}).get("compile_started")
        is False
        and (runtime_source_implementation_map.get("audit") or {}).get(
            "remote_access_performed"
        )
        is False
        and (runtime_source_implementation_map.get("audit") or {}).get(
            "service_restarted"
        )
        is False
    )
    runtime_refactor_work_order_summary = runtime_refactor_work_order.get("summary") or {}
    runtime_refactor_work_order_decision = runtime_refactor_work_order.get("decision") or {}
    runtime_refactor_work_order_audit = runtime_refactor_work_order.get("audit") or {}
    hidden_materialize_design_summary = (
        hidden_materialize_design_contract.get("summary") or {}
    )
    hidden_materialize_design_decision = (
        hidden_materialize_design_contract.get("decision") or {}
    )
    hidden_materialize_design_audit = (
        hidden_materialize_design_contract.get("audit") or {}
    )
    hidden_materialize_telemetry_summary = (
        hidden_materialize_telemetry_contract.get("summary") or {}
    )
    hidden_materialize_telemetry_decision = (
        hidden_materialize_telemetry_contract.get("decision") or {}
    )
    hidden_materialize_telemetry_audit = (
        hidden_materialize_telemetry_contract.get("audit") or {}
    )
    runtime_refactor_work_order_ok = (
        runtime_refactor_work_order.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_work_order"
        and not (runtime_refactor_work_order.get("failed_checks") or [])
        and int(runtime_refactor_work_order_summary.get("work_order_count") or 0) >= 5
        and int(runtime_refactor_work_order_summary.get("allowed_local_work_count") or 0)
        >= 1
        and int(
            runtime_refactor_work_order_summary.get("future_runtime_candidate_count") or 0
        )
        >= 1
        and int(
            runtime_refactor_work_order_summary.get("source_anchor_missing_count") or 0
        )
        == 0
        and int(
            runtime_refactor_work_order_summary.get(
                "source_contract_missing_token_count"
            )
            or 0
        )
        == 0
        and runtime_refactor_work_order_summary.get("most_common_top_segment")
        == "seg27_final_logits"
        and float(
            runtime_refactor_work_order_summary.get("most_common_top_segment_rate")
            or 0.0
        )
        == 1.0
        and runtime_refactor_work_order_summary.get(
            "standard_b4_runtime_sweep_status"
        )
        == "blocked_duplicate"
        and runtime_refactor_work_order_summary.get("queue_batch_remains_default")
        is True
        and runtime_refactor_work_order_summary.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and runtime_refactor_work_order_summary.get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and runtime_refactor_work_order_summary.get("compile_start_allowed_now")
        is False
        and runtime_refactor_work_order_decision.get(
            "do_not_change_runtime_defaults_now"
        )
        is True
        and runtime_refactor_work_order_decision.get("do_not_start_s100p_runtime_now")
        is True
        and runtime_refactor_work_order_decision.get("do_not_start_compile_now")
        is True
        and runtime_refactor_work_order_decision.get(
            "do_not_run_more_standard_b4_runtime_sweeps_now"
        )
        is True
        and runtime_refactor_work_order_decision.get("keep_queue_batch_default")
        is True
        and runtime_refactor_work_order_audit.get("runtime_started") is False
        and runtime_refactor_work_order_audit.get("compile_started") is False
        and runtime_refactor_work_order_audit.get("remote_access_performed") is False
    )
    hidden_materialize_design_contract_ok = (
        hidden_materialize_design_contract.get("verdict")
        == "ok_dream7b_b4_hidden_materialize_design_contract"
        and not (hidden_materialize_design_contract.get("failed_checks") or [])
        and int(
            hidden_materialize_design_summary.get("source_anchor_missing_count") or 0
        )
        == 0
        and int(
            hidden_materialize_design_summary.get("allowed_design_only_count") or 0
        )
        >= 2
        and hidden_materialize_design_summary.get(
            "current_preallocate_hidden_rejected"
        )
        is True
        and hidden_materialize_design_summary.get(
            "preallocate_hidden_experimental_flag_only"
        )
        is True
        and hidden_materialize_design_summary.get(
            "primary_target_remains_final_logits"
        )
        is True
        and hidden_materialize_design_summary.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and hidden_materialize_design_summary.get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and hidden_materialize_design_summary.get("compile_start_allowed_now")
        is False
        and hidden_materialize_design_decision.get(
            "promote_current_preallocate_hidden"
        )
        is False
        and hidden_materialize_design_decision.get("change_runtime_defaults_now")
        is False
        and hidden_materialize_design_decision.get("start_s100p_runtime_now")
        is False
        and hidden_materialize_design_decision.get("start_compile_now") is False
        and hidden_materialize_design_audit.get("runtime_started") is False
        and hidden_materialize_design_audit.get("compile_started") is False
        and hidden_materialize_design_audit.get("remote_access_performed") is False
    )
    hidden_materialize_telemetry_contract_ok = (
        hidden_materialize_telemetry_contract.get("verdict")
        == "ok_dream7b_b4_hidden_materialize_telemetry_contract"
        and not (hidden_materialize_telemetry_contract.get("failed_checks") or [])
        and int(
            hidden_materialize_telemetry_summary.get("source_anchor_missing_count")
            or 0
        )
        == 0
        and int(
            hidden_materialize_telemetry_summary.get(
                "required_telemetry_field_count"
            )
            or 0
        )
        >= 7
        and hidden_materialize_telemetry_summary.get(
            "current_preallocate_hidden_rejected"
        )
        is True
        and hidden_materialize_telemetry_summary.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and hidden_materialize_telemetry_summary.get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and hidden_materialize_telemetry_summary.get("compile_start_allowed_now")
        is False
        and hidden_materialize_telemetry_decision.get("telemetry_source_ready")
        is True
        and hidden_materialize_telemetry_decision.get("deploy_or_run_now") is False
        and hidden_materialize_telemetry_decision.get(
            "change_runtime_defaults_now"
        )
        is False
        and hidden_materialize_telemetry_audit.get("default_behavior_changed")
        is False
        and hidden_materialize_telemetry_audit.get("runtime_started") is False
        and hidden_materialize_telemetry_audit.get("compile_started") is False
        and hidden_materialize_telemetry_audit.get("remote_access_performed") is False
    )
    hbm_load_accounting_contract_ok = (
        hbm_load_accounting_contract.get("verdict")
        == "ok_dream7b_true_batch_hbm_load_accounting_contract"
        and (hbm_load_accounting_contract.get("summary") or {}).get(
            "per_segment_load_accounting_ready"
        )
        is True
        and (hbm_load_accounting_contract.get("summary") or {}).get(
            "group_load_accounting_ready"
        )
        is True
        and (hbm_load_accounting_contract.get("summary") or {}).get(
            "prewarm_accounting_ready"
        )
        is True
        and (hbm_load_accounting_contract.get("summary") or {}).get(
            "timing_summary_accounts_load_and_prewarm"
        )
        is True
        and (hbm_load_accounting_contract.get("summary") or {}).get(
            "prewarm_hbm_default_changed"
        )
        is False
        and (hbm_load_accounting_contract.get("summary") or {}).get("runtime_started")
        is False
        and (hbm_load_accounting_contract.get("summary") or {}).get("compile_started")
        is False
    )
    bottleneck_closure_model_ok = (
        bottleneck_closure.get("verdict") == "ok_dream7b_b4_bottleneck_closure_model"
        and (bottleneck_closure.get("decision") or {}).get(
            "queue_batch_remains_production_default"
        )
        is True
        and (bottleneck_closure.get("decision") or {}).get(
            "true_batch_b4_is_research_artifact"
        )
        is True
        and (bottleneck_closure.get("decision") or {}).get("primary_next_code_target")
        == "seg27_28_last_token_logits"
        and (bottleneck_closure.get("decision") or {}).get(
            "run_more_group_size_or_inner_order_sweeps_now"
        )
        is False
        and (bottleneck_closure.get("decision") or {}).get(
            "projection_is_not_bpu_promotion_proof"
        )
        is True
        and (bottleneck_closure.get("decision") or {}).get(
            "requires_real_runtime_result_before_promotion"
        )
        is True
    )
    queue_should_remain_default = service_active and service_enabled and b4_below_queue

    decision = {
        "production_default": "queue_batch",
        "true_batch_b4_status": "research_artifact_not_promoted",
        "queue_should_remain_default": queue_should_remain_default,
        "queue_partial_batch_flush_ready": queue_partial_batch_flush_ready,
        "queue_health_snapshot_ok": queue_health_snapshot_ok,
        "workstream_overlap_audit_ok": workstream_overlap_ok,
        "do_not_run_long_4_group": True,
        "microbatch_only_sweeps_deprioritized": (
            (saturation.get("decision") or {}).get("microbatch_only_sweeps_deprioritized") is True
        ),
        "do_not_continue_gap_microbatch_sweeps_above_success_boundary": (
            (runtime_boundary.get("decision") or {}).get(
                "do_not_continue_gap_microbatch_sweeps_above_success_boundary"
            )
            is True
        ),
        "do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes": (
            (saturation.get("decision") or {}).get(
                "do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes"
            )
            is True
        ),
        "more_mb512_group_boundary_sweeps_deprioritized": (
            (group_order.get("decision") or {}).get("more_mb512_group_boundary_sweeps_deprioritized")
            is True
        ),
        "no_observed_group_order_variant_beats_baseline": (
            (group_order.get("decision") or {}).get("no_observed_variant_beats_baseline") is True
        ),
        "group_inner_order_value_audit_ok": group_inner_order_value_audit_ok,
        "group_release_and_unaccounted_gap_not_primary": (
            (group_switch.get("decision") or {}).get("group_release_and_unaccounted_gap_not_primary") is True
        ),
        "release_gc_skip_not_primary": (
            b4.get("release_gc_skip_mb512_ms_per_request_delta") is not None
            and as_float(b4.get("release_gc_skip_mb512_ms_per_request_delta")) >= -0.1
        )
        or (
            b4.get("release_gc_skip_mb512_ms_per_request_delta") is None
            and abs(as_float(b4.get("release_gc_skip_mb128_ms_per_request_delta"))) < 0.1
        ),
        "per_segment_hbm_load_telemetry_ready": (
            (hbm_load.get("decision") or {}).get("per_segment_load_telemetry_ready") is True
        ),
        "hbm_load_accounting_contract_ok": hbm_load_accounting_contract_ok,
        "bottleneck_closure_model_ok": bottleneck_closure_model_ok,
        "runtime_refactor_admission_contract_ok": runtime_refactor_admission_contract_ok,
        "runtime_source_implementation_map_ok": runtime_source_implementation_map_ok,
        "runtime_refactor_work_order_ok": runtime_refactor_work_order_ok,
        "hidden_materialize_design_contract_ok": hidden_materialize_design_contract_ok,
        "hidden_materialize_telemetry_contract_ok": hidden_materialize_telemetry_contract_ok,
        "segment_group_schedule_scorecard_ok": segment_group_schedule_scorecard_ok,
        "per_run_evidence_matrix_ok": per_run_evidence_matrix_ok,
        "group_boundary_tuning_alone_not_primary": (
            (hbm_load.get("decision") or {}).get("group_boundary_tuning_alone_not_primary") is True
        ),
        "prewarm_hbm_default": (hbm_load.get("decision") or {}).get("prewarm_hbm_default") is True,
        "preallocate_hidden_default": False,
        "localized_status_fast_path_ready": (
            (first_response_fast_status.get("decision") or {}).get("localized_status_fast_path_ready") is True
        ),
        "first_response_interactive_slo_tiers_ready": first_response_slo_tier_guard_ok,
        "first_response_warning_triaged": first_response_warning_triage_ok,
        "slo_limited_evidence_triaged": slo_limited_evidence_triage_ok,
        "backend_first_content_latency_is_not_true_batch_work": (
            (first_response_slo_tier_guard.get("decision") or {}).get(
                "backend_first_content_latency_is_not_true_batch_work"
            )
            is True
            and (first_response_warning_triage.get("summary") or {}).get(
                "backend_first_content_latency_is_not_true_batch_work"
            )
            is True
        ),
        "s100p_runtime_experiment_now": (
            (runtime_experiment_gate.get("decision") or {}).get("s100p_runtime_experiment_now") is True
        ),
        "allowed_s100p_runtime_experiments": (
            (runtime_experiment_gate.get("decision") or {}).get("allowed_experiments") or []
        ),
        "post_instrumentation_segment_attribution_ready": (
            post_instrumentation_segment_attribution.get("verdict")
            == "ok_dream7b_b4_post_instrumentation_segment_attribution"
        ),
        "tuning_decision_matrix_ok": tuning_decision_matrix_ok,
        "post_instrumentation_segment_primary_bottleneck": (
            post_instrumentation_segment_attribution.get("decision") or {}
        ).get("primary_single_segment_bottleneck"),
        "next_runtime_candidate": (
            (saturation.get("decision") or {}).get("next_runtime_candidate")
            or "final_logits_compute_reduction_or_output_avoidance_before_more_group_boundary_sweeps"
        ),
    }
    verdict = (
        "ok_dream7b_product_decision_packet"
        if service_active
        and service_enabled
        and gateway_active
        and gateway_enabled
        and rollback_present
        and queue_partial_batch_flush_ready
        and b4_below_queue
        and slo_ok
        and portal_ok
        and partial_batch_flush_ok
        and queue_health_snapshot_ok
        and workstream_overlap_ok
        and tuning_decision_matrix_ok
        and group_inner_order_value_audit_ok
        and runtime_command_guard_ok
        and compile_command_guard_ok
        and next_action_admission_pack_ok
        and runtime_refactor_source_contract_ok
        and runtime_refactor_admission_contract_ok
        and runtime_source_implementation_map_ok
        and runtime_refactor_work_order_ok
        and hidden_materialize_design_contract_ok
        and hidden_materialize_telemetry_contract_ok
        and segment_group_schedule_scorecard_ok
        and per_run_evidence_matrix_ok
        and hbm_load_accounting_contract_ok
        and bottleneck_closure_model_ok
        and first_response_ok
        and first_response_slo_tier_guard_ok
        and first_response_warning_triage_ok
        and slo_limited_evidence_triage_ok
        and gateway_listener_ok
        and gateway_listener_drift_ok
        else "warning_dream7b_product_decision_packet"
    )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_product_decision_packet_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "queue_pending_count": remote_values.get("queue_pending_count"),
        "queue_processing_count": remote_values.get("queue_processing_count"),
        "failed_capacity_probe_count": b4.get("failed_capacity_probe_count"),
        "failed_capacity_probe_details": b4.get("failed_capacity_probe_details") or [],
        "source_paths": {
            "schedule": str(schedule_path),
            "prealloc": str(prealloc_path),
            "group_split": str(group_split_path),
            "final_logits": str(final_logits_path),
            "final_output": str(final_output_path) if final_output_path.exists() else None,
            "hbm_load": str(hbm_load_path) if hbm_load_path.exists() else None,
            "bottleneck_closure_model": str(bottleneck_closure_path)
            if bottleneck_closure_path.exists()
            else None,
            "last_token_sizing": str(last_token_sizing_path) if last_token_sizing_path.exists() else None,
            "last_token_experiment": str(last_token_experiment_path) if last_token_experiment_path.exists() else None,
            "last_token_readiness": str(last_token_readiness_path) if last_token_readiness_path.exists() else None,
            "last_token_experiment_gate": str(last_token_gate_path) if last_token_gate_path.exists() else None,
            "last_token_runtime_validation_plan": str(last_token_runtime_validation_plan_path)
            if last_token_runtime_validation_plan_path.exists()
            else None,
            "last_token_validation_compare": str(last_token_validation_compare_path)
            if last_token_validation_compare_path.exists()
            else None,
            "final_logits_leverage_model": str(final_logits_leverage_model_path)
            if final_logits_leverage_model_path.exists()
            else None,
            "compile_capacity": str(compile_capacity_path) if compile_capacity_path.exists() else None,
            "saturation": str(saturation_path) if saturation_path.exists() else None,
            "group_switch": str(group_switch_path) if group_switch_path.exists() else None,
            "runtime_boundary": str(runtime_boundary_path) if runtime_boundary_path.exists() else None,
            "group_order_candidates": str(group_order_path) if group_order_path.exists() else None,
            "group_partition_planner": str(group_partition_planner_path)
            if group_partition_planner_path.exists()
            else None,
            "group_inner_order_value_audit": str(group_inner_order_value_audit_path)
            if group_inner_order_value_audit_path.exists()
            else None,
            "true_batch_nas_inventory": str(true_batch_nas_inventory_path)
            if true_batch_nas_inventory_path.exists()
            else None,
            "runtime_experiment_gate": str(runtime_experiment_gate_path)
            if runtime_experiment_gate_path.exists()
            else None,
            "runtime_command_guard": str(runtime_command_guard_path)
            if runtime_command_guard_path.exists()
            else None,
            "compile_command_guard": str(compile_command_guard_path)
            if compile_command_guard_path.exists()
            else None,
            "next_action_admission_pack": str(next_action_admission_pack_path)
            if next_action_admission_pack_path.exists()
            else None,
            "segment_drag_breakdown": str(segment_drag_path) if segment_drag_path.exists() else None,
            "segment_bottleneck_scorecard": str(segment_bottleneck_path) if segment_bottleneck_path.exists() else None,
            "segment_group_schedule_scorecard": str(segment_group_schedule_scorecard_path)
            if segment_group_schedule_scorecard_path.exists()
            else None,
            "per_run_evidence_matrix": str(per_run_evidence_matrix_path)
            if per_run_evidence_matrix_path.exists()
            else None,
            "segment_stability_audit": str(segment_stability_audit_path)
            if segment_stability_audit_path.exists()
            else None,
            "scheduler_overhead_budget": str(scheduler_overhead_path) if scheduler_overhead_path.exists() else None,
            "runtime_refactor_backlog": str(runtime_refactor_backlog_path)
            if runtime_refactor_backlog_path.exists()
            else None,
            "runtime_refactor_source_contract": str(runtime_refactor_source_contract_path)
            if runtime_refactor_source_contract_path.exists()
            else None,
            "runtime_refactor_admission_contract": str(runtime_refactor_admission_contract_path)
            if runtime_refactor_admission_contract_path.exists()
            else None,
            "runtime_source_implementation_map": str(runtime_source_implementation_map_path)
            if runtime_source_implementation_map_path.exists()
            else None,
            "runtime_refactor_work_order": str(runtime_refactor_work_order_path)
            if runtime_refactor_work_order_path.exists()
            else None,
            "runtime_instrumentation_contract": str(runtime_instrumentation_contract_path)
            if runtime_instrumentation_contract_path.exists()
            else None,
            "runtime_instrumentation_deployment": str(runtime_instrumentation_deployment_path)
            if runtime_instrumentation_deployment_path.exists()
            else None,
            "hbm_load_accounting_contract": str(hbm_load_accounting_contract_path)
            if hbm_load_accounting_contract_path.exists()
            else None,
            "post_instrumentation_telemetry_gate": str(post_instrumentation_telemetry_gate_path)
            if post_instrumentation_telemetry_gate_path.exists()
            else None,
            "post_instrumentation_overhead_analysis": str(
                post_instrumentation_overhead_analysis_path
            )
            if post_instrumentation_overhead_analysis_path.exists()
            else None,
            "post_instrumentation_segment_attribution": str(
                post_instrumentation_segment_attribution_path
            )
            if post_instrumentation_segment_attribution_path.exists()
            else None,
            "hidden_buffer_reuse_decision": str(hidden_buffer_reuse_decision_path)
            if hidden_buffer_reuse_decision_path.exists()
            else None,
            "hidden_materialize_design_contract": str(
                hidden_materialize_design_contract_path
            )
            if hidden_materialize_design_contract_path.exists()
            else None,
            "hidden_materialize_telemetry_contract": str(
                hidden_materialize_telemetry_contract_path
            )
            if hidden_materialize_telemetry_contract_path.exists()
            else None,
            "tuning_decision_matrix": str(tuning_decision_matrix_path)
            if tuning_decision_matrix_path.exists()
            else None,
            "guardrail": str(guardrail_path) if guardrail_path else None,
            "slo": str(slo_path) if slo_path else None,
            "portal": str(portal_path) if portal_path else None,
            "partial_batch_flush": str(partial_batch_flush_path) if partial_batch_flush_path else None,
            "queue_health_snapshot": str(queue_health_snapshot_path) if queue_health_snapshot_path else None,
            "workstream_overlap_audit": str(workstream_overlap_audit_path) if workstream_overlap_audit_path else None,
            "first_response": str(first_response_path) if first_response_path else None,
            "first_response_routing": str(first_response_routing_path) if first_response_routing_path else None,
            "first_response_fast_status": str(first_response_fast_status_path) if first_response_fast_status_path else None,
            "fast_path_regression": str(fast_path_regression_path) if fast_path_regression_path else None,
            "first_response_slo_tier_guard": str(first_response_slo_tier_guard_path)
            if first_response_slo_tier_guard_path.exists()
            else None,
            "first_response_warning_triage": str(first_response_warning_triage_path)
            if first_response_warning_triage_path.exists()
            else None,
            "slo_limited_evidence_triage": str(slo_limited_evidence_triage_path)
            if slo_limited_evidence_triage_path.exists()
            else None,
            "gateway_listener_ownership": str(gateway_listener_path) if gateway_listener_path else None,
            "gateway_listener_drift_gate": str(gateway_listener_drift_path)
            if gateway_listener_drift_path
            else None,
        },
        "service": {
            "active": service_active,
            "enabled": service_enabled,
            "gateway_active": gateway_active,
            "gateway_enabled": gateway_enabled,
            "description": remote_values.get("service_description"),
            "active_since": remote_values.get("service_active_since"),
            "rollback_script": remote_values.get("rollback_script"),
            "status_script": remote_values.get("status_script"),
            "rollback_present": rollback_present,
            "queue_service_has_partial_batch_flush": remote_values.get("queue_service_has_partial_batch_flush") == "true",
            "queue_partial_batch_flush_ready": queue_partial_batch_flush_ready,
            "queue_partial_batch_flush_live_summary_ready": queue_partial_batch_flush_live_summary_ready,
            "queue_partial_batch_flush_probe_ready": queue_partial_batch_flush_probe_ready,
            "queue_partial_batch_flush_health_snapshot_ready": queue_partial_batch_health_ready,
            "queue_partial_batch_flush_readiness_source": (
                "live_summary"
                if queue_partial_batch_flush_live_summary_ready
                else "partial_batch_probe"
                if queue_partial_batch_flush_probe_ready
                else "queue_health_snapshot"
                if queue_partial_batch_health_ready
                else "none"
            ),
            "queue_service_summary_json": remote_values.get("queue_service_summary_json"),
            "queue_partial_batch_last_run_dir": remote_values.get("queue_partial_batch_last_run_dir"),
            "queue_partial_batch_pending_count_at_start": remote_values.get(
                "queue_partial_batch_pending_count_at_start"
            ),
            "queue_partial_batch_effective_max_job_count": remote_values.get(
                "queue_partial_batch_effective_max_job_count"
            ),
            "queue_partial_batch_processed_request_count": remote_values.get(
                "queue_partial_batch_processed_request_count"
            ),
            "queue_partial_batch_ms_per_request": remote_values.get("queue_partial_batch_ms_per_request"),
            "queue_partial_batch_probe_run_dir": partial_batch_probe_summary.get("run_dir"),
            "queue_partial_batch_probe_pending_count_at_start": partial_batch_probe_summary.get("pending_count_at_start"),
            "queue_partial_batch_probe_effective_max_job_count": partial_batch_probe_summary.get("effective_max_job_count"),
            "queue_partial_batch_probe_processed_request_count": partial_batch_probe_summary.get("processed_request_count"),
            "queue_partial_batch_probe_ms_per_request": partial_batch_probe_summary.get("amortized_wall_ms_per_processed_request"),
            "queue_partial_batch_health_run_dir": queue_health_partial.get("run_dir"),
            "queue_partial_batch_health_pending_count_at_start": queue_health_partial.get("pending_count_at_start"),
            "queue_partial_batch_health_effective_max_job_count": queue_health_partial.get("effective_max_job_count"),
            "queue_partial_batch_health_processed_request_count": queue_health_partial.get("processed_request_count"),
            "queue_partial_batch_health_ms_per_request": queue_health_partial.get("ms_per_request"),
            "queue_pending_count": remote_values.get("queue_pending_count"),
            "queue_processing_count": remote_values.get("queue_processing_count"),
        },
        "queue_health_snapshot": summarize_queue_health_snapshot(queue_health_snapshot),
        "workstream_overlap_audit": summarize_workstream_overlap_audit(workstream_overlap_audit),
        "b4_current": b4,
        "prealloc": summarize_prealloc(prealloc),
        "group_split": summarize_group_split(group_split),
        "final_logits": summarize_final_logits(final_logits),
        "final_output": summarize_final_output(final_output),
        "hbm_load": summarize_hbm_load(hbm_load),
        "bottleneck_closure_model": summarize_bottleneck_closure_model(
            bottleneck_closure
        ),
        "last_token_candidate": summarize_last_token_candidate(
            last_token_sizing,
            last_token_experiment_path,
            remote_values,
            last_token_readiness,
        ),
        "last_token_experiment_gate": {
            "verdict": last_token_gate.get("verdict"),
            "code_support_ready": (last_token_gate.get("summary") or {}).get("code_support_ready"),
            "compile_ready": (last_token_gate.get("summary") or {}).get("compile_ready"),
            "manifest_ready": (last_token_gate.get("summary") or {}).get("manifest_ready"),
            "runtime_validation_ready": (last_token_gate.get("summary") or {}).get(
                "runtime_validation_ready"
            ),
            "experiment_ready": (last_token_gate.get("summary") or {}).get("experiment_ready"),
            "gate_blockers": (last_token_gate.get("summary") or {}).get("gate_blockers") or [],
            "target_shape": (last_token_gate.get("candidate_shape") or {}).get("target_shape"),
            "output_element_reduction_vs_current": (
                last_token_gate.get("candidate_shape") or {}
            ).get("output_element_reduction_vs_current"),
            "projection_only_hypothesis_saved_ms_per_request": (
                last_token_gate.get("candidate_shape") or {}
            ).get("projection_only_hypothesis_saved_ms_per_request"),
            "remote_probe_supports_final_hbm_root": (
                ((last_token_gate.get("code_support") or {}).get("remote_probe") or {})
            ).get("supports_final_hbm_root"),
            "remote_probe_supports_final_logits_mode": (
                ((last_token_gate.get("code_support") or {}).get("remote_probe") or {})
            ).get("supports_final_logits_mode"),
        },
        "last_token_runtime_validation_plan": {
            "verdict": last_token_runtime_validation_plan.get("verdict"),
            "plan_generated_at": last_token_runtime_validation_plan.get("generated_at"),
            "validation_ready": (
                last_token_runtime_validation_plan.get("readiness") or {}
            ).get("validation_ready"),
            "blockers": (last_token_runtime_validation_plan.get("readiness") or {}).get(
                "blockers"
            )
            or [],
            "manifest_ready": (
                last_token_runtime_validation_plan.get("readiness") or {}
            ).get("manifest_ready"),
            "queue_idle": (last_token_runtime_validation_plan.get("readiness") or {}).get(
                "queue_idle"
            ),
            "services_ready": (
                last_token_runtime_validation_plan.get("readiness") or {}
            ).get("services_ready"),
            "runtime_tools_ready": (
                last_token_runtime_validation_plan.get("readiness") or {}
            ).get("runtime_tools_ready"),
            "lock_busy": (last_token_runtime_validation_plan.get("readiness") or {}).get(
                "lock_busy"
            ),
            "remote_returncode": (
                last_token_runtime_validation_plan.get("remote_state") or {}
            ).get("returncode"),
            "final_hbm_root_exists": (
                last_token_runtime_validation_plan.get("remote_state") or {}
            ).get("final_hbm_root_exists"),
            "last_token_hbm_exists": (
                last_token_runtime_validation_plan.get("remote_state") or {}
            ).get("last_token_hbm_exists"),
            "manifest_exists": (
                last_token_runtime_validation_plan.get("remote_state") or {}
            ).get("manifest_exists"),
            "manifest_verified": (
                last_token_runtime_validation_plan.get("remote_state") or {}
            ).get("manifest_verified"),
            "hbm_path": (
                last_token_runtime_validation_plan.get("remote_state") or {}
            ).get("hbm_path"),
            "expected_final_shape": (
                last_token_runtime_validation_plan.get("expected") or {}
            ).get("final_shape"),
            "microbatch_count": (
                last_token_runtime_validation_plan.get("expected") or {}
            ).get("microbatch_count"),
            "processed_request_count": (
                last_token_runtime_validation_plan.get("expected") or {}
            ).get("processed_request_count"),
            "runtime_command": (
                last_token_runtime_validation_plan.get("runtime_command") or {}
            ).get("shell"),
        },
        "last_token_validation_compare": summarize_last_token_validation_compare(
            last_token_validation_compare
        ),
        "final_logits_leverage_model": summarize_final_logits_leverage_model(
            final_logits_leverage_model
        ),
        "scaling_saturation": summarize_scaling_saturation(saturation),
        "group_switch_accounting": summarize_group_switch(group_switch),
        "runtime_capacity_boundary": summarize_runtime_boundary(runtime_boundary),
        "group_order_candidates": summarize_group_order_candidates(group_order),
        "group_partition_planner": summarize_group_partition_planner(group_partition_planner),
        "group_inner_order_value_audit": summarize_group_inner_order_value_audit(
            group_inner_order_value_audit
        ),
        "true_batch_nas_inventory": summarize_true_batch_nas_inventory(
            true_batch_nas_inventory
        ),
        "runtime_experiment_gate": summarize_runtime_experiment_gate(runtime_experiment_gate),
        "runtime_command_guard": summarize_runtime_command_guard(runtime_command_guard),
        "compile_command_guard": summarize_compile_command_guard(compile_command_guard),
        "next_action_admission_pack": summarize_next_action_admission_pack(
            next_action_admission_pack
        ),
        "segment_drag_breakdown": summarize_segment_drag_breakdown(segment_drag),
        "segment_bottleneck_scorecard": summarize_segment_bottleneck_scorecard(segment_bottleneck),
        "segment_group_schedule_scorecard": summarize_segment_group_schedule_scorecard(
            segment_group_schedule_scorecard
        ),
        "per_run_evidence_matrix": summarize_per_run_evidence_matrix(
            per_run_evidence_matrix
        ),
        "segment_stability_audit": summarize_segment_stability_audit(segment_stability_audit),
        "scheduler_overhead_budget": {
            "verdict": scheduler_overhead.get("verdict"),
            "primary_code_target": (scheduler_overhead.get("decision") or {}).get(
                "primary_code_target"
            ),
            "next_runtime_experiment": (scheduler_overhead.get("decision") or {}).get(
                "next_runtime_experiment"
            ),
            "deprioritize_python_inter_segment_gap_tuning": (
                scheduler_overhead.get("decision") or {}
            ).get("deprioritize_python_inter_segment_gap_tuning"),
            "deprioritize_more_group_boundary_sweeps": (
                scheduler_overhead.get("decision") or {}
            ).get("deprioritize_more_group_boundary_sweeps"),
            "final_excess_to_group_switch_gap": (scheduler_overhead.get("ratios") or {}).get(
                "final_excess_to_group_switch_gap"
            ),
            "final_excess_to_intra_segment_gap": (scheduler_overhead.get("ratios") or {}).get(
                "final_excess_to_intra_segment_gap"
            ),
            "final_excess_to_gap_residual": (scheduler_overhead.get("ratios") or {}).get(
                "final_excess_to_gap_residual"
            ),
            "final_excess_to_final_python_output_overhead": (
                scheduler_overhead.get("ratios") or {}
            ).get("final_excess_to_final_python_output_overhead"),
            "final_excess_exceeds_group_switch_gap_50x": (
                scheduler_overhead.get("sanity_checks") or {}
            ).get("final_excess_exceeds_group_switch_gap_50x"),
            "group_order_variants_do_not_beat_baseline": (
                scheduler_overhead.get("sanity_checks") or {}
            ).get("group_order_variants_do_not_beat_baseline"),
            "gap_sweeps_above_mb512_blocked": (
                scheduler_overhead.get("sanity_checks") or {}
            ).get("gap_sweeps_above_mb512_blocked"),
        },
        "runtime_instrumentation": summarize_runtime_instrumentation(
            runtime_instrumentation_contract,
            runtime_instrumentation_deployment,
        ),
        "hbm_load_accounting_contract": summarize_hbm_load_accounting_contract(
            hbm_load_accounting_contract
        ),
        "post_instrumentation_telemetry_gate": summarize_post_instrumentation_telemetry_gate(
            post_instrumentation_telemetry_gate
        ),
        "post_instrumentation_overhead_analysis": summarize_post_instrumentation_overhead_analysis(
            post_instrumentation_overhead_analysis
        ),
        "post_instrumentation_segment_attribution": summarize_post_instrumentation_segment_attribution(
            post_instrumentation_segment_attribution
        ),
        "hidden_buffer_reuse_decision": summarize_hidden_buffer_reuse_decision(
            hidden_buffer_reuse_decision
        ),
        "hidden_materialize_design_contract": summarize_hidden_materialize_design_contract(
            hidden_materialize_design_contract
        ),
        "hidden_materialize_telemetry_contract": summarize_hidden_materialize_telemetry_contract(
            hidden_materialize_telemetry_contract
        ),
        "tuning_decision_matrix": summarize_tuning_decision_matrix(tuning_decision_matrix),
        "runtime_refactor_backlog": {
            "verdict": runtime_refactor_backlog.get("verdict"),
            "primary_runtime_refactor_target": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("primary_runtime_refactor_target"),
            "secondary_research_target": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("secondary_research_target"),
            "current_preallocate_hidden_rejected_by_evidence": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("current_preallocate_hidden_rejected_by_evidence"),
            "preallocate_hidden_experimental_flag_only": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("preallocate_hidden_experimental_flag_only"),
            "rank1_projected_saved_ms_per_request": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("rank1_projected_saved_ms_per_request"),
            "rank1_projection_is_not_bpu_promotion_proof": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("rank1_projection_is_not_bpu_promotion_proof"),
            "rank1_blocks_standard_group_or_inner_order_sweeps": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("rank1_blocks_standard_group_or_inner_order_sweeps"),
            "ready_local_refactor_count": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("ready_local_refactor_count"),
            "do_not_change_runtime_defaults_now": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("do_not_change_runtime_defaults_now"),
            "do_not_start_s100p_runtime_now": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("do_not_start_s100p_runtime_now"),
            "queue_batch_remains_default": (
                runtime_refactor_backlog.get("decision") or {}
            ).get("queue_batch_remains_default"),
            "backlog_count": len(runtime_refactor_backlog.get("backlog") or []),
            "top_backlog_items": [
                {
                    "rank": item.get("rank"),
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "expected_ceiling_ms_per_request": item.get(
                        "expected_ceiling_ms_per_request"
                    ),
                    "projected_saved_ms_per_request": item.get(
                        "projected_saved_ms_per_request"
                    ),
                    "projected_latency_reduction_pct": item.get(
                        "projected_latency_reduction_pct"
                    ),
                    "projection_is_not_bpu_promotion_proof": (
                        item.get("evidence") or {}
                    ).get("projection_is_not_bpu_promotion_proof"),
                    "do_not_run_standard_group_or_inner_order_sweeps": (
                        item.get("evidence") or {}
                    ).get("do_not_run_standard_group_or_inner_order_sweeps"),
                    "source_lines": [
                        f"{Path(anchor.get('file') or '').name}:{anchor.get('line')}"
                        for anchor in item.get("source_anchors") or []
                    ],
                }
                for item in (runtime_refactor_backlog.get("backlog") or [])[:3]
            ],
        },
        "runtime_refactor_source_contract": summarize_runtime_refactor_source_contract(
            runtime_refactor_source_contract
        ),
        "runtime_refactor_admission_contract": summarize_runtime_refactor_admission_contract(
            runtime_refactor_admission_contract
        ),
        "runtime_source_implementation_map": summarize_runtime_source_implementation_map(
            runtime_source_implementation_map
        ),
        "runtime_refactor_work_order": summarize_runtime_refactor_work_order(
            runtime_refactor_work_order
        ),
        "compile_capacity": summarize_compile_capacity(compile_capacity),
        "first_response": summarize_first_response(
            first_response,
            first_response_routing,
            first_response_fast_status,
            fast_path_regression,
        ),
        "first_response_slo_tier_guard": summarize_first_response_slo_tier_guard(
            first_response_slo_tier_guard
        ),
        "first_response_warning_triage": summarize_first_response_warning_triage(
            first_response_warning_triage
        ),
        "slo_limited_evidence_triage": summarize_slo_limited_evidence_triage(
            slo_limited_evidence_triage
        ),
        "product_evidence": {
            "guardrail_verdict": guardrail.get("verdict"),
            "guardrail_default_status_contract_ready": (guardrail.get("guardrail") or {}).get(
                "default_status_contract_ready"
            ),
            "guardrail_default_rollback_dry_run_ready": (guardrail.get("guardrail") or {}).get(
                "default_rollback_dry_run_ready"
            ),
            "guardrail_status_script_sha256": (
                (guardrail.get("default_status_contract") or {}).get("script") or {}
            ).get("sha256"),
            "guardrail_rollback_script_sha256": (
                (guardrail.get("default_rollback_contract") or {}).get("script") or {}
            ).get("sha256"),
            "guardrail_rollback_dry_run_stdout": (
                guardrail.get("default_rollback_contract") or {}
            ).get("dry_run_stdout"),
            "slo_verdict": slo.get("verdict"),
            "portal_verdict": portal.get("verdict"),
            "partial_batch_flush_verdict": partial_batch_flush.get("verdict"),
            "queue_partial_batch_flush_ready": queue_partial_batch_flush_ready,
            "queue_partial_batch_flush_live_summary_ready": queue_partial_batch_flush_live_summary_ready,
            "queue_partial_batch_flush_probe_ready": queue_partial_batch_flush_probe_ready,
            "queue_partial_batch_flush_health_snapshot_ready": queue_partial_batch_health_ready,
            "queue_partial_batch_flush_readiness_source": (
                "live_summary"
                if queue_partial_batch_flush_live_summary_ready
                else "partial_batch_probe"
                if queue_partial_batch_flush_probe_ready
                else "queue_health_snapshot"
                if queue_partial_batch_health_ready
                else "none"
            ),
            "queue_partial_batch_probe_run_dir": partial_batch_probe_summary.get("run_dir"),
            "queue_partial_batch_probe_ms_per_request": partial_batch_probe_summary.get(
                "amortized_wall_ms_per_processed_request"
            ),
            "first_response_warning_triage_verdict": first_response_warning_triage.get(
                "verdict"
            ),
            "first_response_warning_triaged": (
                first_response_warning_triage.get("decision") or {}
            ).get("warning_is_product_triaged"),
            "first_response_warning_source_verdict": (
                first_response_warning_triage.get("summary") or {}
            ).get("source_warning_verdict"),
            "first_response_warning_quickpath_delta_ms": (
                first_response_warning_triage.get("summary") or {}
            ).get("quickpath_delta_ms"),
            "first_response_warning_backend_not_true_batch_work": (
                first_response_warning_triage.get("summary") or {}
            ).get("backend_first_content_latency_is_not_true_batch_work"),
            "slo_limited_evidence_triage_verdict": slo_limited_evidence_triage.get(
                "verdict"
            ),
            "slo_limited_evidence_triaged": (
                slo_limited_evidence_triage.get("decision") or {}
            ).get("limited_evidence_triaged"),
            "slo_limited_evidence_release_blocker": (
                slo_limited_evidence_triage.get("decision") or {}
            ).get("release_blocker"),
            "slo_limited_warning_count": (
                slo_limited_evidence_triage.get("summary") or {}
            ).get("slo_warning_count"),
            "slo_limited_warnings": (
                slo_limited_evidence_triage.get("summary") or {}
            ).get("slo_warnings"),
            "runtime_refactor_work_order_verdict": runtime_refactor_work_order.get(
                "verdict"
            ),
            "runtime_refactor_work_order_count": runtime_refactor_work_order_summary.get(
                "work_order_count"
            ),
            "runtime_refactor_work_order_allowed_local_count": runtime_refactor_work_order_summary.get(
                "allowed_local_work_count"
            ),
            "runtime_refactor_work_order_source_anchor_missing_count": runtime_refactor_work_order_summary.get(
                "source_anchor_missing_count"
            ),
            "runtime_refactor_work_order_primary_local_design_item": runtime_refactor_work_order_summary.get(
                "primary_local_design_item"
            ),
            "runtime_refactor_work_order_primary_future_runtime_candidate": runtime_refactor_work_order_summary.get(
                "primary_future_runtime_candidate"
            ),
            "runtime_refactor_work_order_default_runtime_change_allowed_now": runtime_refactor_work_order_summary.get(
                "default_runtime_change_allowed_now"
            ),
            "runtime_refactor_work_order_s100p_runtime_allowed_now": runtime_refactor_work_order_summary.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "runtime_refactor_work_order_compile_start_allowed_now": runtime_refactor_work_order_summary.get(
                "compile_start_allowed_now"
            ),
            "hidden_materialize_design_contract_verdict": hidden_materialize_design_contract.get(
                "verdict"
            ),
            "hidden_materialize_design_allowed_design_only_count": hidden_materialize_design_summary.get(
                "allowed_design_only_count"
            ),
            "hidden_materialize_design_source_anchor_missing_count": hidden_materialize_design_summary.get(
                "source_anchor_missing_count"
            ),
            "hidden_materialize_design_current_preallocate_hidden_rejected": hidden_materialize_design_summary.get(
                "current_preallocate_hidden_rejected"
            ),
            "hidden_materialize_design_next_design_only_item": hidden_materialize_design_summary.get(
                "next_design_only_item"
            ),
            "hidden_materialize_design_next_report_only_item": hidden_materialize_design_summary.get(
                "next_report_only_item"
            ),
            "hidden_materialize_design_default_runtime_change_allowed_now": hidden_materialize_design_summary.get(
                "default_runtime_change_allowed_now"
            ),
            "hidden_materialize_design_s100p_runtime_allowed_now": hidden_materialize_design_summary.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "hidden_materialize_design_compile_start_allowed_now": hidden_materialize_design_summary.get(
                "compile_start_allowed_now"
            ),
            "hidden_materialize_telemetry_contract_verdict": hidden_materialize_telemetry_contract.get(
                "verdict"
            ),
            "hidden_materialize_telemetry_required_field_count": hidden_materialize_telemetry_summary.get(
                "required_telemetry_field_count"
            ),
            "hidden_materialize_telemetry_source_anchor_missing_count": hidden_materialize_telemetry_summary.get(
                "source_anchor_missing_count"
            ),
            "hidden_materialize_telemetry_source_ready": hidden_materialize_telemetry_decision.get(
                "telemetry_source_ready"
            ),
            "hidden_materialize_telemetry_default_runtime_change_allowed_now": hidden_materialize_telemetry_summary.get(
                "default_runtime_change_allowed_now"
            ),
            "hidden_materialize_telemetry_s100p_runtime_allowed_now": hidden_materialize_telemetry_summary.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "hidden_materialize_telemetry_compile_start_allowed_now": hidden_materialize_telemetry_summary.get(
                "compile_start_allowed_now"
            ),
            "gateway_listener_ownership_verdict": gateway_listener.get("verdict"),
            "gateway_listener_pid": (gateway_listener.get("summary") or {}).get("listener_pid"),
            "gateway_main_pid": (gateway_listener.get("summary") or {}).get("gateway_main_pid"),
            "gateway_listener_matches_systemd_main_pid": (gateway_listener.get("summary") or {}).get(
                "listener_matches_systemd_main_pid"
            ),
            "gateway_orphan_listener_detected": (gateway_listener.get("summary") or {}).get(
                "orphan_listener_detected"
            ),
            "gateway_listener_health_ok": (gateway_listener.get("summary") or {}).get("health_ok"),
            "gateway_listener_drift_gate_verdict": gateway_listener_drift.get("verdict"),
            "gateway_listener_drift_snapshot_ok": (
                gateway_listener_drift.get("summary") or {}
            ).get("snapshot_ok"),
            "gateway_listener_drift_live_matches_systemd_main_pid": (
                gateway_listener_drift.get("summary") or {}
            ).get("live_listener_matches_systemd_main_pid"),
            "gateway_listener_drift_live_orphan_detected": (
                gateway_listener_drift.get("summary") or {}
            ).get("live_orphan_listener_detected"),
            "gateway_listener_drift_live_health_ok": (
                gateway_listener_drift.get("summary") or {}
            ).get("live_health_ok"),
            "gateway_listener_drift_warning_count": (
                gateway_listener_drift.get("summary") or {}
            ).get("warning_count"),
            "slo_required_accepted_count": (slo.get("summary") or {}).get("required_accepted_count"),
            "slo_required_contract_count": (slo.get("summary") or {}).get("required_contract_count"),
            "slo_warning_count": (slo.get("summary") or {}).get("warning_count"),
            "slo_blocker_count": (slo.get("summary") or {}).get("blocker_count"),
            "portal_result_count": (portal.get("summary") or {}).get("result_count"),
            "portal_failure_count": (portal.get("summary") or {}).get("failure_count"),
            "portal_execution_performed": (portal.get("summary") or {}).get("execution_performed"),
            "partial_batch_flush_latest_text_queue_run": (
                (partial_batch_flush.get("remote") or {}).get("latest_text_queue_run") or {}
            ).get("path"),
            "queue_health_snapshot_verdict": queue_health_snapshot.get("verdict"),
            "queue_health_snapshot_queue_idle": (queue_health_snapshot.get("checks") or {}).get(
                "queue_idle_at_probe"
            ),
            "queue_health_snapshot_no_true_batch_or_compile_process": (
                queue_health_snapshot.get("checks") or {}
            ).get("no_true_batch_or_compile_process"),
            "workstream_overlap_audit_verdict": workstream_overlap_audit.get("verdict"),
            "workstream_overlap_no_duplicate": (
                workstream_overlap_audit.get("decision") or {}
            ).get("queue_batch_work_duplicates_prior_true_batch_rental")
            is False,
            "group_inner_order_value_audit_verdict": group_inner_order_value_audit.get(
                "verdict"
            ),
            "group_inner_order_value_audit_best_delta_ms_per_request": (
                group_inner_order_value_audit.get("summary") or {}
            ).get("best_nonbaseline_delta_ms_per_request"),
            "group_inner_order_value_audit_run_more_sweeps_now": (
                group_inner_order_value_audit.get("decision") or {}
            ).get("run_more_group_size_or_inner_order_sweeps_now"),
            "per_run_evidence_matrix_verdict": per_run_evidence_matrix.get("verdict"),
            "per_run_evidence_matrix_run_count": per_run_evidence_matrix_summary.get(
                "run_count"
            ),
            "per_run_evidence_matrix_successful_run_count": per_run_evidence_matrix_summary.get(
                "successful_run_count"
            ),
            "per_run_evidence_matrix_failed_run_count": per_run_evidence_matrix_summary.get(
                "failed_run_count"
            ),
            "per_run_evidence_matrix_top_segment": per_run_evidence_matrix_summary.get(
                "most_common_top_segment"
            ),
            "per_run_evidence_matrix_top_segment_rate": per_run_evidence_matrix_summary.get(
                "most_common_top_segment_rate"
            ),
            "per_run_evidence_matrix_standard_sweep_status": per_run_evidence_matrix_summary.get(
                "standard_b4_runtime_sweep_status"
            ),
            "first_response_slo_tier_guard_verdict": first_response_slo_tier_guard.get(
                "verdict"
            ),
            "first_response_slo_tier_fast_path_ready": (
                (first_response_slo_tier_guard.get("tiers") or {})
                .get("fast_path_first_content", {})
                .get("ready")
            ),
            "first_response_slo_tier_backend_not_true_batch_work": (
                first_response_slo_tier_guard.get("decision") or {}
            ).get("backend_first_content_latency_is_not_true_batch_work"),
        },
        "decision": decision,
        "checks": {
            "service_active_enabled": service_active and service_enabled,
            "gateway_active_enabled": gateway_active and gateway_enabled,
            "rollback_present": rollback_present,
            "queue_partial_batch_flush_ready": queue_partial_batch_flush_ready,
            "queue_partial_batch_flush_live_summary_ready": queue_partial_batch_flush_live_summary_ready,
            "queue_partial_batch_flush_probe_ready": queue_partial_batch_flush_probe_ready,
            "queue_partial_batch_flush_health_snapshot_ready": queue_partial_batch_health_ready,
            "b4_below_queue": b4_below_queue,
            "guardrail_ok": guardrail_ok,
            "slo_ok": slo_ok,
            "portal_ok": portal_ok,
            "partial_batch_flush_ok": partial_batch_flush_ok,
            "queue_health_snapshot_ok": queue_health_snapshot_ok,
            "workstream_overlap_audit_ok": workstream_overlap_ok,
            "first_response_ok": first_response_ok,
            "first_response_slo_tier_guard_ok": first_response_slo_tier_guard_ok,
            "first_response_warning_triage_ok": first_response_warning_triage_ok,
            "slo_limited_evidence_triage_ok": slo_limited_evidence_triage_ok,
            "gateway_listener_ok": gateway_listener_ok,
            "gateway_listener_drift_ok": gateway_listener_drift_ok,
            "runtime_instrumentation_ready": runtime_instrumentation_ready,
            "post_instrumentation_telemetry_ready": (
                post_instrumentation_telemetry_gate.get("decision") or {}
            ).get("post_instrumentation_telemetry_ready"),
            "input_output_overhead_quantified": (
                post_instrumentation_telemetry_gate.get("decision") or {}
            ).get("input_output_overhead_quantified"),
            "post_instrumentation_overhead_analysis_ok": post_instrumentation_overhead_analysis.get(
                "verdict"
            )
            == "ok_dream7b_b4_post_instrumentation_overhead_analysis",
            "post_instrumentation_segment_attribution_ok": post_instrumentation_segment_attribution.get(
                "verdict"
            )
            == "ok_dream7b_b4_post_instrumentation_segment_attribution",
            "hidden_buffer_reuse_decision_ok": hidden_buffer_reuse_decision.get("verdict")
            == "ok_dream7b_b4_hidden_buffer_reuse_decision",
            "tuning_decision_matrix_ok": tuning_decision_matrix_ok,
            "group_inner_order_value_audit_ok": group_inner_order_value_audit_ok,
            "runtime_command_guard_ok": runtime_command_guard_ok,
            "compile_command_guard_ok": compile_command_guard_ok,
            "next_action_admission_pack_ok": next_action_admission_pack_ok,
            "runtime_refactor_source_contract_ok": runtime_refactor_source_contract_ok,
            "runtime_refactor_admission_contract_ok": runtime_refactor_admission_contract_ok,
            "runtime_source_implementation_map_ok": runtime_source_implementation_map_ok,
            "runtime_refactor_work_order_ok": runtime_refactor_work_order_ok,
            "hidden_materialize_design_contract_ok": hidden_materialize_design_contract_ok,
            "hidden_materialize_telemetry_contract_ok": hidden_materialize_telemetry_contract_ok,
            "segment_group_schedule_scorecard_ok": segment_group_schedule_scorecard_ok,
            "per_run_evidence_matrix_ok": per_run_evidence_matrix_ok,
            "hbm_load_accounting_contract_ok": hbm_load_accounting_contract_ok,
            "bottleneck_closure_model_ok": bottleneck_closure_model_ok,
        },
        "remote_command": remote,
    }

    out_json = out_dir / "dream7b_product_decision_packet.json"
    out_md = out_dir / "dream7b_product_decision_packet.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Dream7B Product Decision Packet",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {verdict}",
        f"- production_default: {decision['production_default']}",
        f"- true_batch_b4_status: {decision['true_batch_b4_status']}",
        f"- queue_should_remain_default: {decision['queue_should_remain_default']}",
        "",
        "## Service Guardrail",
        "",
        f"- active: {service_active}",
        f"- enabled: {service_enabled}",
        f"- rollback_present: {rollback_present}",
        f"- rollback_script: {remote_values.get('rollback_script')}",
        f"- gateway_active: {gateway_active}",
        f"- gateway_enabled: {gateway_enabled}",
        f"- queue_partial_batch_flush_ready: {queue_partial_batch_flush_ready}",
        f"- queue_partial_batch_flush_live_summary_ready: {queue_partial_batch_flush_live_summary_ready}",
        f"- queue_partial_batch_flush_probe_ready: {queue_partial_batch_flush_probe_ready}",
        f"- queue_partial_batch_flush_health_snapshot_ready: {queue_partial_batch_health_ready}",
        f"- queue_partial_batch_flush_readiness_source: {payload['service']['queue_partial_batch_flush_readiness_source']}",
        f"- queue_partial_batch_pending_count_at_start: {remote_values.get('queue_partial_batch_pending_count_at_start')}",
        f"- queue_partial_batch_processed_request_count: {remote_values.get('queue_partial_batch_processed_request_count')}",
        f"- queue_partial_batch_ms_per_request: {remote_values.get('queue_partial_batch_ms_per_request')}",
        f"- queue_partial_batch_probe_run_dir: {payload['service']['queue_partial_batch_probe_run_dir']}",
        f"- queue_partial_batch_probe_pending_count_at_start: {payload['service']['queue_partial_batch_probe_pending_count_at_start']}",
        f"- queue_partial_batch_probe_processed_request_count: {payload['service']['queue_partial_batch_probe_processed_request_count']}",
        f"- queue_partial_batch_probe_ms_per_request: {payload['service']['queue_partial_batch_probe_ms_per_request']}",
        f"- queue_pending_count: {remote_values.get('queue_pending_count')}",
        f"- queue_processing_count: {remote_values.get('queue_processing_count')}",
        f"- queue_health_snapshot_verdict: {payload['queue_health_snapshot']['verdict']}",
        f"- queue_health_snapshot_queue_idle: {payload['queue_health_snapshot']['queue_idle_at_probe']}",
        f"- queue_health_snapshot_no_true_batch_or_compile_process: {payload['queue_health_snapshot']['no_true_batch_or_compile_process']}",
        f"- queue_health_snapshot_fast_quick_ready_ms: {payload['queue_health_snapshot']['quick_ready_first_content_ms']}",
        f"- queue_health_snapshot_latest_text_queue_ms_per_request: {payload['queue_health_snapshot']['latest_text_queue_ms_per_request']}",
        f"- workstream_overlap_audit_verdict: {payload['workstream_overlap_audit']['verdict']}",
        f"- workstream_current_workstream: {payload['workstream_overlap_audit']['current_workstream']}",
        f"- workstream_queue_work_duplicates_true_batch_rental: {payload['workstream_overlap_audit']['queue_batch_work_duplicates_prior_true_batch_rental']}",
        f"- workstream_remote_b4_records: {payload['workstream_overlap_audit']['remote_b4_group_major_report_count']}",
        f"- workstream_local_b4_records: {payload['workstream_overlap_audit']['local_b4_json_count']}",
        f"- tuning_decision_matrix_verdict: {payload['tuning_decision_matrix']['verdict']}",
        f"- tuning_preferred_group_policy: {payload['tuning_decision_matrix']['preferred_group_policy']}",
        f"- tuning_preferred_inner_order: {payload['tuning_decision_matrix']['preferred_inner_order']}",
        f"- tuning_primary_code_target: {payload['tuning_decision_matrix']['primary_code_target']}",
        f"- tuning_primary_code_target_projected_saved_ms_per_request: {payload['tuning_decision_matrix']['primary_code_target_projected_saved_ms_per_request']}",
        f"- tuning_primary_code_target_not_bpu_promotion_proof: {payload['tuning_decision_matrix']['primary_code_target_not_bpu_promotion_proof']}",
        f"- tuning_standard_sweeps_blocked_by_final_logits_leverage: {payload['tuning_decision_matrix']['standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage']}",
        f"- tuning_next_s100p_runtime_experiment_allowed: {payload['tuning_decision_matrix']['next_s100p_runtime_experiment_allowed']}",
        f"- tuning_next_compile_allowed: {payload['tuning_decision_matrix']['next_compile_allowed']}",
        f"- segment_group_schedule_scorecard_ok: {decision['segment_group_schedule_scorecard_ok']}",
        f"- final_logits_leverage_verdict: {payload['final_logits_leverage_model']['verdict']}",
        f"- final_logits_leverage_projection_saved_ms_per_request: {payload['final_logits_leverage_model']['projection_saved_ms_per_request']}",
        f"- final_logits_leverage_projection_capture_pct: {payload['final_logits_leverage_model']['projection_capture_of_final_excess_pct']}",
        f"- final_logits_leverage_not_bpu_promotion_proof: {payload['final_logits_leverage_model']['projection_is_not_bpu_promotion_proof']}",
        "",
        "## B4 Current Evidence",
        "",
        f"- telemetry_count: {b4['telemetry_count']}",
        f"- successful_run_count: {b4['successful_run_count']}",
        f"- failed_capacity_probe_count: {b4['failed_capacity_probe_count']}",
        f"- per_run_evidence_matrix_verdict: {payload['per_run_evidence_matrix']['verdict']}",
        f"- per_run_evidence_matrix_run_count: {payload['per_run_evidence_matrix']['run_count']}",
        f"- per_run_evidence_matrix_successful_run_count: {payload['per_run_evidence_matrix']['successful_run_count']}",
        f"- per_run_evidence_matrix_failed_run_count: {payload['per_run_evidence_matrix']['failed_run_count']}",
        f"- per_run_evidence_matrix_top_segment: {payload['per_run_evidence_matrix']['most_common_top_segment']}",
        f"- per_run_evidence_matrix_top_segment_rate: {payload['per_run_evidence_matrix']['most_common_top_segment_rate']}",
        f"- per_run_evidence_matrix_standard_sweep_status: {payload['per_run_evidence_matrix']['standard_b4_runtime_sweep_status']}",
        f"- latest_microbatch_count: {b4['latest_microbatch_count']}",
        f"- latest_avg_bpu_loading: {b4['latest_avg_bpu_loading']}",
        f"- latest_avg_nonzero_bpu_loading: {b4['latest_avg_nonzero_bpu_loading']}",
        f"- avg_bpu_gap_points_vs_queue: {b4['avg_bpu_gap_points_vs_queue']}",
        f"- nonzero_bpu_gap_points_vs_queue: {b4['nonzero_bpu_gap_points_vs_queue']}",
        f"- mb512_six_group_ms_per_request_delta_vs_5_group: {b4['mb512_six_group_ms_per_request_delta_vs_5_group']}",
        f"- mb512_six_group_avg_bpu_delta_vs_5_group: {b4['mb512_six_group_avg_bpu_delta_vs_5_group']}",
        f"- mb512_final_isolated_ms_per_request_delta_vs_5_group: {b4['mb512_final_isolated_ms_per_request_delta_vs_5_group']}",
        f"- mb512_final_isolated_avg_bpu_delta_vs_5_group: {b4['mb512_final_isolated_avg_bpu_delta_vs_5_group']}",
        f"- mb512_seven_group_ms_per_request_delta_vs_5_group: {b4['mb512_seven_group_ms_per_request_delta_vs_5_group']}",
        f"- release_gc_skip_mb128_ms_per_request_delta: {b4['release_gc_skip_mb128_ms_per_request_delta']}",
        f"- release_gc_skip_mb128_avg_bpu_delta: {b4['release_gc_skip_mb128_avg_bpu_delta']}",
        f"- release_gc_skip_mb128_nonzero_bpu_delta: {b4['release_gc_skip_mb128_nonzero_bpu_delta']}",
        f"- release_gc_skip_mb128_group_release_ms_delta: {b4['release_gc_skip_mb128_group_release_ms_delta']}",
        f"- release_gc_skip_mb512_ms_per_request_delta: {b4['release_gc_skip_mb512_ms_per_request_delta']}",
        f"- release_gc_skip_mb512_avg_bpu_delta: {b4['release_gc_skip_mb512_avg_bpu_delta']}",
        f"- release_gc_skip_mb512_nonzero_bpu_delta: {b4['release_gc_skip_mb512_nonzero_bpu_delta']}",
        f"- release_gc_skip_mb512_group_release_ms_delta: {b4['release_gc_skip_mb512_group_release_ms_delta']}",
        "",
        "### Failed Capacity Probe Details",
        "",
        "| file | microbatches | completed_groups | failed_segment | processed_requests |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for row in b4.get("failed_capacity_probe_details") or []:
        lines.append(
            f"| {Path(str(row.get('file') or '')).name} | {row.get('microbatch_count')} | "
            f"{row.get('completed_group_count')} | {row.get('failed_segment')} | "
            f"{row.get('processed_request_count')} |"
        )
    lines.extend(
        [
            "",
            "## Runtime Decisions",
            "",
            f"- queue_health_snapshot_ok: {decision['queue_health_snapshot_ok']}",
            f"- workstream_overlap_audit_ok: {decision['workstream_overlap_audit_ok']}",
            f"- tuning_decision_matrix_ok: {decision['tuning_decision_matrix_ok']}",
            f"- preallocate_hidden_default: {decision['preallocate_hidden_default']}",
            f"- prealloc_ms_per_request_delta: {payload['prealloc']['ms_per_request_delta']}",
            f"- do_not_run_long_4_group: {decision['do_not_run_long_4_group']}",
            f"- microbatch_only_sweeps_deprioritized: {decision['microbatch_only_sweeps_deprioritized']}",
            f"- do_not_continue_gap_microbatch_sweeps_above_success_boundary: {decision['do_not_continue_gap_microbatch_sweeps_above_success_boundary']}",
            f"- do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes: {decision['do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes']}",
            f"- more_mb512_group_boundary_sweeps_deprioritized: {decision['more_mb512_group_boundary_sweeps_deprioritized']}",
            f"- no_observed_group_order_variant_beats_baseline: {decision['no_observed_group_order_variant_beats_baseline']}",
            f"- group_release_and_unaccounted_gap_not_primary: {decision['group_release_and_unaccounted_gap_not_primary']}",
            f"- release_gc_skip_not_primary: {decision['release_gc_skip_not_primary']}",
            f"- per_segment_hbm_load_telemetry_ready: {decision['per_segment_hbm_load_telemetry_ready']}",
            f"- hbm_load_accounting_contract_ok: {decision['hbm_load_accounting_contract_ok']}",
            f"- bottleneck_closure_model_ok: {decision['bottleneck_closure_model_ok']}",
            f"- runtime_refactor_admission_contract_ok: {decision['runtime_refactor_admission_contract_ok']}",
            f"- group_boundary_tuning_alone_not_primary: {decision['group_boundary_tuning_alone_not_primary']}",
            f"- prewarm_hbm_default: {decision['prewarm_hbm_default']}",
            f"- g4_error: {payload['group_split']['g4_error']}",
            f"- s100p_runtime_experiment_now: {decision['s100p_runtime_experiment_now']}",
            f"- allowed_s100p_runtime_experiments: {decision['allowed_s100p_runtime_experiments']}",
            f"- next_runtime_candidate: {decision['next_runtime_candidate']}",
            "",
        ]
    )
    lines.extend(
        [
            "## Scaling Saturation",
        "",
        f"- saturation_verdict: {payload['scaling_saturation']['verdict']}",
        f"- latest_microbatch_count: {payload['scaling_saturation']['latest_microbatch_count']}",
        f"- latest_avg_bpu_loading: {payload['scaling_saturation']['latest_avg_bpu_loading']}",
        f"- latest_avg_nonzero_bpu_loading: {payload['scaling_saturation']['latest_avg_nonzero_bpu_loading']}",
        f"- required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction: {payload['scaling_saturation']['required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction']}",
        f"- projected_max_avg_bpu_if_nonzero_unchanged: {payload['scaling_saturation']['projected_max_avg_bpu_if_nonzero_unchanged']}",
        f"- projected_max_still_below_93: {payload['scaling_saturation']['projected_max_still_below_93']}",
        f"- microbatch_only_sweeps_deprioritized: {payload['scaling_saturation']['microbatch_only_sweeps_deprioritized']}",
        f"- do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes: {payload['scaling_saturation']['do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes']}",
        "",
        "## Group Switch Accounting",
        "",
        f"- group_switch_verdict: {payload['group_switch_accounting']['verdict']}",
        f"- latest_microbatch_count: {payload['group_switch_accounting']['latest_microbatch_count']}",
        f"- group_load_ms_per_request: {payload['group_switch_accounting']['group_load_ms_per_request']}",
        f"- group_switch_gap_ms_per_request: {payload['group_switch_accounting']['group_switch_gap_ms_per_request']}",
        f"- group_release_ms_per_request: {payload['group_switch_accounting']['group_release_ms_per_request']}",
        f"- unaccounted_gap_ms_per_request: {payload['group_switch_accounting']['unaccounted_gap_ms_per_request']}",
        f"- inter_segment_first_run_gap_ms_per_request: {payload['group_switch_accounting']['inter_segment_first_run_gap_ms_per_request']}",
        f"- intra_segment_run_gap_ms_per_request: {payload['group_switch_accounting']['intra_segment_run_gap_ms_per_request']}",
        f"- segment_overhead_excluding_hidden_materialize_ms_per_request: {payload['group_switch_accounting']['segment_overhead_excluding_hidden_materialize_ms_per_request']}",
        f"- segment_overhead_excluding_measured_gaps_ms_per_request: {payload['group_switch_accounting']['segment_overhead_excluding_measured_gaps_ms_per_request']}",
        f"- latest_gap_microbatch_count: {payload['group_switch_accounting']['latest_gap_microbatch_count']}",
        f"- latest_gap_ms_per_request: {payload['group_switch_accounting']['latest_gap_ms_per_request']}",
        f"- latest_gap_avg_bpu_loading: {payload['group_switch_accounting']['latest_gap_avg_bpu_loading']}",
        f"- latest_gap_inter_segment_first_run_gap_ms_per_request: {payload['group_switch_accounting']['latest_gap_inter_segment_first_run_gap_ms_per_request']}",
        f"- latest_gap_intra_segment_run_gap_ms_per_request: {payload['group_switch_accounting']['latest_gap_intra_segment_run_gap_ms_per_request']}",
        f"- latest_gap_residual_after_gaps_ms_per_request: {payload['group_switch_accounting']['latest_gap_residual_after_gaps_ms_per_request']}",
        f"- final_logits_excess_ms_per_request_if_hidden_speed: {payload['group_switch_accounting']['final_logits_excess_ms_per_request_if_hidden_speed']}",
        f"- final_excess_to_switch_gap_ratio: {payload['group_switch_accounting']['final_excess_to_switch_gap_ratio']}",
        f"- group_release_and_unaccounted_gap_not_primary: {payload['group_switch_accounting']['group_release_and_unaccounted_gap_not_primary']}",
        f"- scheduler_followup: {payload['group_switch_accounting']['scheduler_followup']}",
        "",
        "## Scheduler Overhead Budget",
        "",
        f"- scheduler_budget_verdict: {payload['scheduler_overhead_budget']['verdict']}",
        f"- primary_code_target: {payload['scheduler_overhead_budget']['primary_code_target']}",
        f"- next_runtime_experiment: {payload['scheduler_overhead_budget']['next_runtime_experiment']}",
        f"- final_excess_to_group_switch_gap: {payload['scheduler_overhead_budget']['final_excess_to_group_switch_gap']}",
        f"- final_excess_to_intra_segment_gap: {payload['scheduler_overhead_budget']['final_excess_to_intra_segment_gap']}",
        f"- final_excess_to_gap_residual: {payload['scheduler_overhead_budget']['final_excess_to_gap_residual']}",
        f"- final_excess_to_final_python_output_overhead: {payload['scheduler_overhead_budget']['final_excess_to_final_python_output_overhead']}",
        f"- deprioritize_python_inter_segment_gap_tuning: {payload['scheduler_overhead_budget']['deprioritize_python_inter_segment_gap_tuning']}",
        f"- deprioritize_more_group_boundary_sweeps: {payload['scheduler_overhead_budget']['deprioritize_more_group_boundary_sweeps']}",
        f"- gap_sweeps_above_mb512_blocked: {payload['scheduler_overhead_budget']['gap_sweeps_above_mb512_blocked']}",
        "",
        "## Runtime Instrumentation",
        "",
        f"- instrumentation_contract_verdict: {payload['runtime_instrumentation']['contract_verdict']}",
        f"- instrumentation_deployment_verdict: {payload['runtime_instrumentation']['deployment_verdict']}",
        f"- new_telemetry_fields: {payload['runtime_instrumentation']['new_telemetry_fields']}",
        f"- default_cli_changed: {payload['runtime_instrumentation']['default_cli_changed']}",
        f"- runtime_order_changed: {payload['runtime_instrumentation']['runtime_order_changed']}",
        f"- requires_s100p_runtime: {payload['runtime_instrumentation']['requires_s100p_runtime']}",
        f"- remote_probe: {payload['runtime_instrumentation']['remote_probe']}",
        f"- remote_probe_sha256: {payload['runtime_instrumentation']['remote_probe_sha256']}",
        f"- remote_backup: {payload['runtime_instrumentation']['remote_backup']}",
        f"- active_true_batch_python: {payload['runtime_instrumentation']['active_true_batch_python']}",
        f"- active_compile_true_batch: {payload['runtime_instrumentation']['active_compile_true_batch']}",
        "",
        "## Bottleneck Closure Model",
        "",
        f"- bottleneck_closure_verdict: {payload['bottleneck_closure_model']['verdict']}",
        f"- latest_ms_per_request: {payload['bottleneck_closure_model']['latest_ms_per_request']}",
        f"- latest_avg_bpu_gap_to_queue_points: {payload['bottleneck_closure_model']['latest_avg_bpu_gap_to_queue_points']}",
        f"- latest_nonzero_shortfall_points_for_93_avg: {payload['bottleneck_closure_model']['latest_nonzero_shortfall_points_for_93_avg']}",
        f"- primary_next_code_target: {payload['bottleneck_closure_model']['primary_next_code_target']}",
        f"- final_logits_projection_saved_ms_per_request: {payload['bottleneck_closure_model']['final_logits_projection_saved_ms_per_request']}",
        f"- hbm_group_load_ms_per_request: {payload['bottleneck_closure_model']['hbm_group_load_ms_per_request']}",
        f"- release_plus_unaccounted_group_gap_ms_per_request: {payload['bottleneck_closure_model']['release_plus_unaccounted_group_gap_ms_per_request']}",
        f"- small_python_and_gap_optimizations_combined_ms_per_request: {payload['bottleneck_closure_model']['small_python_and_gap_optimizations_combined_ms_per_request']}",
        f"- group_size_or_inner_order_current_primary_lever: {payload['bottleneck_closure_model']['group_size_or_inner_order_current_primary_lever']}",
        f"- projection_is_not_bpu_promotion_proof: {payload['bottleneck_closure_model']['projection_is_not_bpu_promotion_proof']}",
        f"- requires_real_runtime_result_before_promotion: {payload['bottleneck_closure_model']['requires_real_runtime_result_before_promotion']}",
        "",
        "## HBM Load Accounting Contract",
        "",
        f"- hbm_load_accounting_contract_verdict: {payload['hbm_load_accounting_contract']['verdict']}",
        f"- per_segment_load_accounting_ready: {payload['hbm_load_accounting_contract']['per_segment_load_accounting_ready']}",
        f"- group_load_accounting_ready: {payload['hbm_load_accounting_contract']['group_load_accounting_ready']}",
        f"- prewarm_accounting_ready: {payload['hbm_load_accounting_contract']['prewarm_accounting_ready']}",
        f"- timing_summary_accounts_load_and_prewarm: {payload['hbm_load_accounting_contract']['timing_summary_accounts_load_and_prewarm']}",
        f"- prewarm_hbm_default_changed: {payload['hbm_load_accounting_contract']['prewarm_hbm_default_changed']}",
        f"- runtime_started: {payload['hbm_load_accounting_contract']['runtime_started']}",
        f"- compile_started: {payload['hbm_load_accounting_contract']['compile_started']}",
        "",
        "## Post-Instrumentation Telemetry Gate",
        "",
        f"- post_instrumentation_gate_verdict: {payload['post_instrumentation_telemetry_gate']['verdict']}",
        f"- post_instrumentation_success_count: {payload['post_instrumentation_telemetry_gate']['post_instrumentation_success_count']}",
        f"- baseline_mb512_segment_major_5g_success_count: {payload['post_instrumentation_telemetry_gate']['baseline_mb512_segment_major_5g_success_count']}",
        f"- post_instrumentation_telemetry_ready: {payload['post_instrumentation_telemetry_gate']['post_instrumentation_telemetry_ready']}",
        f"- input_output_overhead_quantified: {payload['post_instrumentation_telemetry_gate']['input_output_overhead_quantified']}",
        f"- do_not_claim_input_output_overhead_yet: {payload['post_instrumentation_telemetry_gate']['do_not_claim_input_output_overhead_yet']}",
        f"- run_more_standard_b4_runtime_sweeps_now: {payload['post_instrumentation_telemetry_gate']['run_more_standard_b4_runtime_sweeps_now']}",
        f"- allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available: {payload['post_instrumentation_telemetry_gate']['allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available']}",
        f"- next_measurement_purpose: {payload['post_instrumentation_telemetry_gate']['next_measurement_purpose']}",
        f"- next_measurement_command: {payload['post_instrumentation_telemetry_gate']['next_measurement_command']}",
        "",
        "## Post-Instrumentation Overhead Analysis",
        "",
        f"- post_instrumentation_overhead_verdict: {payload['post_instrumentation_overhead_analysis']['verdict']}",
        f"- input_prepare_ms_per_request: {payload['post_instrumentation_overhead_analysis']['input_prepare_ms_per_request']}",
        f"- output_postprocess_ms_per_request: {payload['post_instrumentation_overhead_analysis']['output_postprocess_ms_per_request']}",
        f"- hidden_materialize_ms_per_request: {payload['post_instrumentation_overhead_analysis']['hidden_materialize_ms_per_request']}",
        f"- final_output_postprocess_ms_per_request: {payload['post_instrumentation_overhead_analysis']['final_output_postprocess_ms_per_request']}",
        f"- final_excess_ms_per_request_vs_hidden: {payload['post_instrumentation_overhead_analysis']['final_excess_ms_per_request_vs_hidden']}",
        f"- input_prepare_primary_bottleneck: {payload['post_instrumentation_overhead_analysis']['input_prepare_primary_bottleneck']}",
        f"- output_postprocess_primary_bottleneck: {payload['post_instrumentation_overhead_analysis']['output_postprocess_primary_bottleneck']}",
        f"- hidden_materialize_buffer_reuse_has_measured_ceiling: {payload['post_instrumentation_overhead_analysis']['hidden_materialize_buffer_reuse_has_measured_ceiling']}",
        f"- final_logits_compute_still_primary: {payload['post_instrumentation_overhead_analysis']['final_logits_compute_still_primary']}",
        f"- next_local_runtime_code_target: {payload['post_instrumentation_overhead_analysis']['next_local_runtime_code_target']}",
        f"- secondary_local_runtime_code_target: {payload['post_instrumentation_overhead_analysis']['secondary_local_runtime_code_target']}",
        "",
        "## Post-Instrumentation Segment Attribution",
        "",
        f"- segment_attribution_verdict: {payload['post_instrumentation_segment_attribution']['verdict']}",
        f"- microbatch_count: {payload['post_instrumentation_segment_attribution']['microbatch_count']}",
        f"- primary_single_segment_bottleneck: {payload['post_instrumentation_segment_attribution']['primary_single_segment_bottleneck']}",
        f"- final_compute_excess_ms_per_request: {payload['post_instrumentation_segment_attribution']['final_compute_excess_ms_per_request']}",
        f"- final_to_top_hidden_compute_excess_ratio: {payload['post_instrumentation_segment_attribution']['final_to_top_hidden_compute_excess_ratio']}",
        f"- top_segment: {payload['post_instrumentation_segment_attribution']['top_segment_index']} {payload['post_instrumentation_segment_attribution']['top_segment_kind']}",
        f"- top_segment_total_ms_per_request: {payload['post_instrumentation_segment_attribution']['top_segment_total_ms_per_request']}",
        f"- top_group_by_segment_total: {payload['post_instrumentation_segment_attribution']['top_group_by_segment_total']}",
        f"- top_group_contains_final_logits: {payload['post_instrumentation_segment_attribution']['top_group_contains_final_logits']}",
        f"- top_group_segment_total_ms_per_request: {payload['post_instrumentation_segment_attribution']['top_group_segment_total_ms_per_request']}",
        f"- group_size_tuning_implication: {payload['post_instrumentation_segment_attribution']['group_size_tuning_implication']}",
        f"- inner_order_tuning_implication: {payload['post_instrumentation_segment_attribution']['inner_order_tuning_implication']}",
        f"- next_code_target: {payload['post_instrumentation_segment_attribution']['next_code_target']}",
        f"- secondary_research_target: {payload['post_instrumentation_segment_attribution']['secondary_research_target']}",
        "",
        "## Hidden Buffer Reuse Decision",
        "",
        f"- hidden_buffer_reuse_verdict: {payload['hidden_buffer_reuse_decision']['verdict']}",
        f"- hidden_buffer_reuse_default: {payload['hidden_buffer_reuse_decision']['hidden_buffer_reuse_default']}",
        f"- preallocate_hidden_experimental_flag_only: {payload['hidden_buffer_reuse_decision']['preallocate_hidden_experimental_flag_only']}",
        f"- prealloc_ms_per_request_delta: {payload['hidden_buffer_reuse_decision']['prealloc_ms_per_request_delta']}",
        f"- prealloc_hidden_materialize_ms_per_request_delta: {payload['hidden_buffer_reuse_decision']['prealloc_hidden_materialize_ms_per_request_delta']}",
        f"- prealloc_reused_hidden_buffer_count: {payload['hidden_buffer_reuse_decision']['prealloc_reused_hidden_buffer_count']}",
        f"- reuse_buffer_implementation_measured_slower: {payload['hidden_buffer_reuse_decision']['reuse_buffer_implementation_measured_slower']}",
        f"- do_not_start_new_preallocate_hidden_runtime_now: {payload['hidden_buffer_reuse_decision']['do_not_start_new_preallocate_hidden_runtime_now']}",
        f"- secondary_research_target: {payload['hidden_buffer_reuse_decision']['secondary_research_target']}",
        f"- hidden_materialize_design_contract_verdict: {payload['hidden_materialize_design_contract']['verdict']}",
        f"- hidden_materialize_design_allowed_design_only_count: {payload['hidden_materialize_design_contract']['allowed_design_only_count']}",
        f"- hidden_materialize_design_source_anchor_missing_count: {payload['hidden_materialize_design_contract']['source_anchor_missing_count']}",
        f"- hidden_materialize_design_current_preallocate_hidden_rejected: {payload['hidden_materialize_design_contract']['current_preallocate_hidden_rejected']}",
        f"- hidden_materialize_design_next_design_only_item: {payload['hidden_materialize_design_contract']['next_design_only_item']}",
        f"- hidden_materialize_design_next_report_only_item: {payload['hidden_materialize_design_contract']['next_report_only_item']}",
        f"- hidden_materialize_design_default_runtime_change_allowed_now: {payload['hidden_materialize_design_contract']['default_runtime_change_allowed_now']}",
        f"- hidden_materialize_design_s100p_runtime_allowed_now: {payload['hidden_materialize_design_contract']['s100p_runtime_experiment_allowed_now']}",
        f"- hidden_materialize_design_compile_start_allowed_now: {payload['hidden_materialize_design_contract']['compile_start_allowed_now']}",
        f"- hidden_materialize_telemetry_contract_verdict: {payload['hidden_materialize_telemetry_contract']['verdict']}",
        f"- hidden_materialize_telemetry_required_field_count: {payload['hidden_materialize_telemetry_contract']['required_telemetry_field_count']}",
        f"- hidden_materialize_telemetry_source_anchor_missing_count: {payload['hidden_materialize_telemetry_contract']['source_anchor_missing_count']}",
        f"- hidden_materialize_telemetry_source_ready: {payload['hidden_materialize_telemetry_contract']['telemetry_source_ready']}",
        f"- hidden_materialize_telemetry_default_runtime_change_allowed_now: {payload['hidden_materialize_telemetry_contract']['default_runtime_change_allowed_now']}",
        f"- hidden_materialize_telemetry_s100p_runtime_allowed_now: {payload['hidden_materialize_telemetry_contract']['s100p_runtime_experiment_allowed_now']}",
        f"- hidden_materialize_telemetry_compile_start_allowed_now: {payload['hidden_materialize_telemetry_contract']['compile_start_allowed_now']}",
        "",
        "## Runtime Refactor Backlog",
        "",
        f"- runtime_refactor_backlog_verdict: {payload['runtime_refactor_backlog']['verdict']}",
        f"- primary_runtime_refactor_target: {payload['runtime_refactor_backlog']['primary_runtime_refactor_target']}",
        f"- secondary_research_target: {payload['runtime_refactor_backlog']['secondary_research_target']}",
        f"- current_preallocate_hidden_rejected_by_evidence: {payload['runtime_refactor_backlog']['current_preallocate_hidden_rejected_by_evidence']}",
        f"- preallocate_hidden_experimental_flag_only: {payload['runtime_refactor_backlog']['preallocate_hidden_experimental_flag_only']}",
        f"- runtime_refactor_rank1_projected_saved_ms_per_request: {payload['runtime_refactor_backlog']['rank1_projected_saved_ms_per_request']}",
        f"- runtime_refactor_rank1_not_bpu_promotion_proof: {payload['runtime_refactor_backlog']['rank1_projection_is_not_bpu_promotion_proof']}",
        f"- runtime_refactor_rank1_blocks_standard_sweeps: {payload['runtime_refactor_backlog']['rank1_blocks_standard_group_or_inner_order_sweeps']}",
        f"- ready_local_refactor_count: {payload['runtime_refactor_backlog']['ready_local_refactor_count']}",
        f"- do_not_change_runtime_defaults_now: {payload['runtime_refactor_backlog']['do_not_change_runtime_defaults_now']}",
        f"- do_not_start_s100p_runtime_now: {payload['runtime_refactor_backlog']['do_not_start_s100p_runtime_now']}",
        f"- runtime_refactor_backlog_count: {payload['runtime_refactor_backlog']['backlog_count']}",
        f"- top_backlog_items: {payload['runtime_refactor_backlog']['top_backlog_items']}",
        f"- runtime_refactor_source_contract_verdict: {payload['runtime_refactor_source_contract']['verdict']}",
        f"- runtime_refactor_source_cli_defaults_preserved: {payload['runtime_refactor_source_contract']['cli_defaults_preserved']}",
        f"- runtime_refactor_source_last_token_path_supported: {payload['runtime_refactor_source_contract']['last_token_path_supported']}",
        f"- runtime_refactor_source_telemetry_contract_ready: {payload['runtime_refactor_source_contract']['telemetry_contract_ready']}",
        f"- runtime_refactor_source_protected_telemetry_field_count: {payload['runtime_refactor_source_contract']['protected_telemetry_field_count']}",
        f"- runtime_refactor_source_protected_telemetry_missing_count: {payload['runtime_refactor_source_contract']['protected_telemetry_missing_count']}",
        f"- runtime_refactor_source_runtime_order_changed: {payload['runtime_refactor_source_contract']['runtime_order_changed']}",
        f"- runtime_refactor_source_default_promotes_experimental_flags: {payload['runtime_refactor_source_contract']['default_promotes_experimental_flags']}",
        f"- runtime_refactor_source_missing_checks: {payload['runtime_refactor_source_contract']['missing_checks']}",
        f"- runtime_refactor_source_missing_telemetry_fields: {payload['runtime_refactor_source_contract']['missing_telemetry_fields']}",
        f"- runtime_source_implementation_map_verdict: {payload['runtime_source_implementation_map']['verdict']}",
        f"- runtime_source_implementation_area_count: {payload['runtime_source_implementation_map']['implementation_area_count']}",
        f"- runtime_source_pattern_count: {payload['runtime_source_implementation_map']['source_pattern_count']}",
        f"- runtime_source_missing_source_pattern_count: {payload['runtime_source_implementation_map']['missing_source_pattern_count']}",
        f"- runtime_source_primary_runtime_refactor_target: {payload['runtime_source_implementation_map']['primary_runtime_refactor_target']}",
        f"- runtime_source_allowed_now: {payload['runtime_source_implementation_map']['allowed_now']}",
        f"- runtime_source_duplicate_or_blocked_area_count: {payload['runtime_source_implementation_map']['duplicate_or_blocked_area_count']}",
        f"- runtime_source_s100p_runtime_allowed_now: {payload['runtime_source_implementation_map']['s100p_runtime_experiment_allowed_now']}",
        f"- runtime_source_compile_start_allowed_now: {payload['runtime_source_implementation_map']['compile_start_allowed_now']}",
        f"- runtime_source_runtime_default_change_allowed_now: {payload['runtime_source_implementation_map']['runtime_default_change_allowed_now']}",
        f"- runtime_source_standard_sweeps_blocked: {payload['runtime_source_implementation_map']['standard_group_inner_order_sweeps_blocked']}",
        f"- runtime_source_failed_checks: {payload['runtime_source_implementation_map']['failed_checks']}",
        f"- runtime_refactor_work_order_verdict: {payload['runtime_refactor_work_order']['verdict']}",
        f"- runtime_refactor_work_order_count: {payload['runtime_refactor_work_order']['work_order_count']}",
        f"- runtime_refactor_work_order_allowed_local_work_count: {payload['runtime_refactor_work_order']['allowed_local_work_count']}",
        f"- runtime_refactor_work_order_source_anchor_missing_count: {payload['runtime_refactor_work_order']['source_anchor_missing_count']}",
        f"- runtime_refactor_work_order_primary_local_design_item: {payload['runtime_refactor_work_order']['primary_local_design_item']}",
        f"- runtime_refactor_work_order_primary_future_runtime_candidate: {payload['runtime_refactor_work_order']['primary_future_runtime_candidate']}",
        f"- runtime_refactor_work_order_next_local_work: {payload['runtime_refactor_work_order']['next_local_work']}",
        f"- runtime_refactor_work_order_hidden_materialize_design_contract_verdict: {payload['runtime_refactor_work_order']['hidden_materialize_design_contract_verdict']}",
        f"- runtime_refactor_work_order_hidden_materialize_next_design_only_item: {payload['runtime_refactor_work_order']['hidden_materialize_next_design_only_item']}",
        f"- runtime_refactor_work_order_hidden_materialize_next_report_only_item: {payload['runtime_refactor_work_order']['hidden_materialize_next_report_only_item']}",
        f"- runtime_refactor_work_order_hidden_materialize_telemetry_contract_verdict: {payload['runtime_refactor_work_order']['hidden_materialize_telemetry_contract_verdict']}",
        f"- runtime_refactor_work_order_hidden_materialize_telemetry_source_ready: {payload['runtime_refactor_work_order']['hidden_materialize_telemetry_source_ready']}",
        f"- runtime_refactor_work_order_hidden_materialize_next_evidence_gate: {payload['runtime_refactor_work_order']['hidden_materialize_next_evidence_gate']}",
        f"- runtime_refactor_work_order_default_runtime_change_allowed_now: {payload['runtime_refactor_work_order']['default_runtime_change_allowed_now']}",
        f"- runtime_refactor_work_order_s100p_runtime_allowed_now: {payload['runtime_refactor_work_order']['s100p_runtime_experiment_allowed_now']}",
        f"- runtime_refactor_work_order_compile_start_allowed_now: {payload['runtime_refactor_work_order']['compile_start_allowed_now']}",
        f"- runtime_refactor_admission_contract_verdict: {payload['runtime_refactor_admission_contract']['verdict']}",
        f"- runtime_refactor_admission_local_report_only_allowed_now: {payload['runtime_refactor_admission_contract']['local_report_only_refactor_allowed_now']}",
        f"- runtime_refactor_admission_design_only_hidden_materialize_allowed_now: {payload['runtime_refactor_admission_contract']['design_only_hidden_materialize_allowed_now']}",
        f"- runtime_refactor_admission_default_runtime_change_allowed_now: {payload['runtime_refactor_admission_contract']['default_runtime_code_change_allowed_now']}",
        f"- runtime_refactor_admission_s100p_runtime_allowed_now: {payload['runtime_refactor_admission_contract']['s100p_runtime_experiment_allowed_now']}",
        f"- runtime_refactor_admission_compile_start_allowed_now: {payload['runtime_refactor_admission_contract']['compile_start_allowed_now']}",
        f"- runtime_refactor_admission_compile_preflight_only_allowed_now: {payload['runtime_refactor_admission_contract']['compile_preflight_only_allowed_now']}",
        f"- runtime_refactor_admission_allowed_now_count: {payload['runtime_refactor_admission_contract']['allowed_now_count']}",
        f"- runtime_refactor_admission_block_standard_sweeps: {payload['runtime_refactor_admission_contract']['block_standard_group_or_inner_order_sweeps']}",
        f"- runtime_refactor_admission_block_prewarm_or_cache_default: {payload['runtime_refactor_admission_contract']['block_prewarm_or_cache_default']}",
        f"- runtime_refactor_admission_failed_checks: {payload['runtime_refactor_admission_contract']['failed_checks']}",
        "",
        "## Segment/Group Schedule Scorecard",
        "",
        f"- segment_group_schedule_scorecard_verdict: {payload['segment_group_schedule_scorecard']['verdict']}",
        f"- segment_group_primary_schedule_bottleneck: {payload['segment_group_schedule_scorecard']['primary_schedule_bottleneck']}",
        f"- segment_group_primary_code_target: {payload['segment_group_schedule_scorecard']['primary_code_target']}",
        f"- segment_group_preferred_group_policy: {payload['segment_group_schedule_scorecard']['preferred_group_policy']}",
        f"- segment_group_preferred_inner_order: {payload['segment_group_schedule_scorecard']['preferred_inner_order']}",
        f"- segment_group_run_more_standard_sweeps_now: {payload['segment_group_schedule_scorecard']['run_more_standard_b4_group_or_inner_order_sweeps_now']}",
        f"- segment_group_run_new_group_partition_now: {payload['segment_group_schedule_scorecard']['run_new_group_partition_now']}",
        f"- segment_group_run_s100p_runtime_now: {payload['segment_group_schedule_scorecard']['run_s100p_runtime_now']}",
        f"- segment_group_start_compile_now: {payload['segment_group_schedule_scorecard']['start_compile_now']}",
        f"- segment_group_compile_preflight_only_now: {payload['segment_group_schedule_scorecard']['compile_preflight_only_now']}",
        f"- segment_group_final_logits_compute_excess_ms_per_request: {payload['segment_group_schedule_scorecard']['final_logits_compute_excess_ms_per_request']}",
        f"- segment_group_final_to_top_hidden_compute_excess_ratio: {payload['segment_group_schedule_scorecard']['final_to_top_hidden_compute_excess_ratio']}",
        f"- segment_group_final_excess_to_group_switch_gap_ratio: {payload['segment_group_schedule_scorecard']['final_excess_to_group_switch_gap_ratio']}",
        f"- segment_group_best_nonbaseline_group_delta_ms_per_request: {payload['segment_group_schedule_scorecard']['best_nonbaseline_group_delta_ms_per_request']}",
        f"- segment_group_top_scorecard_target: {payload['segment_group_schedule_scorecard']['top_scorecard_target']}",
        f"- segment_group_top_scorecard_status: {payload['segment_group_schedule_scorecard']['top_scorecard_status']}",
        f"- segment_group_recommended_next: {payload['segment_group_schedule_scorecard']['recommended_next']}",
        f"- segment_group_failed_checks: {payload['segment_group_schedule_scorecard']['failed_checks']}",
        "",
        "## Runtime Capacity Boundary",
        "",
        f"- boundary_verdict: {payload['runtime_capacity_boundary']['verdict']}",
        f"- latest_successful_microbatch_count: {payload['runtime_capacity_boundary']['latest_successful_microbatch_count']}",
        f"- latest_gap_success_microbatch_count: {payload['runtime_capacity_boundary']['latest_gap_success_microbatch_count']}",
        f"- first_gap_failure_microbatch_count: {payload['runtime_capacity_boundary']['first_gap_failure_microbatch_count']}",
        f"- gap_instrumented_success_boundary_microbatch_count: {payload['runtime_capacity_boundary']['gap_instrumented_success_boundary_microbatch_count']}",
        f"- gap_instrumented_first_failed_microbatch_count: {payload['runtime_capacity_boundary']['gap_instrumented_first_failed_microbatch_count']}",
        f"- do_not_continue_gap_microbatch_sweeps_above_success_boundary: {payload['runtime_capacity_boundary']['do_not_continue_gap_microbatch_sweeps_above_success_boundary']}",
        f"- continue_prioritizing_final_logits_candidate: {payload['runtime_capacity_boundary']['continue_prioritizing_final_logits_candidate']}",
        f"- reason: {payload['runtime_capacity_boundary']['reason']}",
        "",
        "## Group/Order Candidates",
        "",
        f"- group_order_verdict: {payload['group_order_candidates']['verdict']}",
        f"- baseline: {payload['group_order_candidates']['baseline']}",
        f"- baseline_ms_per_request: {payload['group_order_candidates']['baseline_ms_per_request']}",
        f"- segment_major_preferred_over_microbatch_major: {payload['group_order_candidates']['segment_major_preferred_over_microbatch_major']}",
        f"- best_nonbaseline_observed_variant: {payload['group_order_candidates']['best_nonbaseline_observed_variant']}",
        f"- best_nonbaseline_observed_variant_delta_ms_per_request: {payload['group_order_candidates']['best_nonbaseline_observed_variant_delta_ms_per_request']}",
        f"- no_observed_variant_beats_baseline: {payload['group_order_candidates']['no_observed_variant_beats_baseline']}",
        f"- observed_group_order_variants_within_noise_band: {payload['group_order_candidates']['observed_group_order_variants_within_noise_band']}",
        f"- more_mb512_group_boundary_sweeps_deprioritized: {payload['group_order_candidates']['more_mb512_group_boundary_sweeps_deprioritized']}",
        f"- mb768_or_higher_group_sweeps_blocked_by_capacity_boundary: {payload['group_order_candidates']['mb768_or_higher_group_sweeps_blocked_by_capacity_boundary']}",
        f"- only_capacity_probe_if_needed: {payload['group_order_candidates']['only_capacity_probe_if_needed']}",
        f"- observed_success_peak_group_hbm_mib: {payload['group_order_candidates']['observed_success_peak_group_hbm_mib']}",
        f"- observed_failed_g4_peak_group_hbm_mib: {payload['group_order_candidates']['observed_failed_g4_peak_group_hbm_mib']}",
        f"- reason: {payload['group_order_candidates']['reason']}",
        "",
        "## Group Partition Planner",
        "",
        f"- planner_verdict: {payload['group_partition_planner']['verdict']}",
        f"- candidate_count: {payload['group_partition_planner']['candidate_count']}",
        f"- run_new_partition_now: {payload['group_partition_planner']['run_new_partition_now']}",
        f"- only_probe_if_memory_plan_changes: {payload['group_partition_planner']['only_probe_if_memory_plan_changes']}",
        f"- baseline_group_ranges: {payload['group_partition_planner']['baseline_group_ranges']}",
        f"- baseline_max_group_hbm_mib: {payload['group_partition_planner']['baseline_max_group_hbm_mib']}",
        f"- observed_failed_g4_peak_group_hbm_mib: {payload['group_partition_planner']['observed_failed_g4_peak_group_hbm_mib']}",
        f"- top_capacity_probe_groups: {payload['group_partition_planner']['top_capacity_probe_groups']}",
        f"- top_capacity_probe_max_group_hbm_mib: {payload['group_partition_planner']['top_capacity_probe_max_group_hbm_mib']}",
        f"- top_capacity_probe_peak_delta_pct: {payload['group_partition_planner']['top_capacity_probe_peak_delta_pct']}",
        f"- top_capacity_probe_release_delta_ms_per_request: {payload['group_partition_planner']['top_capacity_probe_release_delta_ms_per_request']}",
        f"- observed_nonbaseline_count: {payload['group_partition_planner']['observed_nonbaseline_count']}",
        f"- best_observed_nonbaseline_delta_ms_per_request: {payload['group_partition_planner']['best_observed_nonbaseline_delta_ms_per_request']}",
        f"- capacity_probe_only_count: {payload['group_partition_planner']['capacity_probe_only_count']}",
        f"- do_not_run_more_group_switches_count: {payload['group_partition_planner']['do_not_run_more_group_switches_count']}",
        f"- reason: {payload['group_partition_planner']['reason']}",
        f"- group_inner_order_value_audit_verdict: {payload['group_inner_order_value_audit']['verdict']}",
        f"- group_inner_order_best_nonbaseline_variant: {payload['group_inner_order_value_audit']['best_nonbaseline_variant']}",
        f"- group_inner_order_best_nonbaseline_delta_ms_per_request: {payload['group_inner_order_value_audit']['best_nonbaseline_delta_ms_per_request']}",
        f"- group_inner_order_slower_or_equal_nonbaseline_count: {payload['group_inner_order_value_audit']['slower_or_equal_nonbaseline_count']}",
        f"- group_inner_order_capacity_probe_only_candidate_count: {payload['group_inner_order_value_audit']['capacity_probe_only_candidate_count']}",
        f"- group_inner_order_final_to_token_excess_ratio: {payload['group_inner_order_value_audit']['final_to_token_excess_ratio']}",
        f"- group_inner_order_final_to_max_hidden_excess_ratio: {payload['group_inner_order_value_audit']['final_to_max_hidden_excess_ratio']}",
        f"- group_inner_order_run_more_sweeps_now: {payload['group_inner_order_value_audit']['run_more_group_size_or_inner_order_sweeps_now']}",
        f"- group_inner_order_current_primary_levers: {payload['group_inner_order_value_audit']['group_size_and_inner_order_are_current_primary_levers']}",
        f"- group_inner_order_top_value_lever: {payload['group_inner_order_value_audit']['top_value_lever']}",
        f"- group_inner_order_next_runtime_allowed_now: {payload['group_inner_order_value_audit']['next_s100p_runtime_experiment_allowed_now']}",
        f"- group_inner_order_next_compile_allowed_now: {payload['group_inner_order_value_audit']['next_compile_allowed_now']}",
        "",
        "## True-Batch NAS Inventory",
        "",
        f"- inventory_verdict: {payload['true_batch_nas_inventory']['verdict']}",
        f"- remote_group_major_report_count: {payload['true_batch_nas_inventory']['remote_group_major_report_count']}",
        f"- remote_group_major_report_json_count: {payload['true_batch_nas_inventory']['remote_group_major_report_json_count']}",
        f"- remote_batch_counts: {payload['true_batch_nas_inventory']['remote_batch_counts']}",
        f"- remote_report_json_batch_counts: {payload['true_batch_nas_inventory']['remote_report_json_batch_counts']}",
        f"- missing_report_json_dirs: {payload['true_batch_nas_inventory']['missing_report_json_dirs']}",
        f"- remote_b4_group_major_report_count: {payload['true_batch_nas_inventory']['remote_b4_group_major_report_count']}",
        f"- remote_b4_group_major_report_json_count: {payload['true_batch_nas_inventory']['remote_b4_group_major_report_json_count']}",
        f"- local_b4_json_count: {payload['true_batch_nas_inventory']['local_b4_json_count']}",
        f"- local_b4_successful_count: {payload['true_batch_nas_inventory']['local_b4_successful_count']}",
        f"- local_b4_failed_count: {payload['true_batch_nas_inventory']['local_b4_failed_count']}",
        f"- local_b4_by_microbatch_count: {payload['true_batch_nas_inventory']['local_b4_by_microbatch_count']}",
        f"- local_b4_by_group_count: {payload['true_batch_nas_inventory']['local_b4_by_group_count']}",
        f"- b4_hbm_count: {payload['true_batch_nas_inventory']['b4_hbm_count']}",
        f"- b4_manifest_count: {payload['true_batch_nas_inventory']['b4_manifest_count']}",
        f"- last_token_file_count: {payload['true_batch_nas_inventory']['last_token_file_count']}",
        f"- b4_remote_local_count_match: {payload['true_batch_nas_inventory']['b4_remote_local_count_match']}",
        f"- b4_remote_json_local_count_match: {payload['true_batch_nas_inventory']['b4_remote_json_local_count_match']}",
        f"- b4_history_is_already_mirrored_locally: {payload['true_batch_nas_inventory']['b4_history_is_already_mirrored_locally']}",
        f"- last_token_candidate_already_ran: {payload['true_batch_nas_inventory']['last_token_candidate_already_ran']}",
        f"- run_more_standard_b4_runtime_sweeps_now: {payload['true_batch_nas_inventory']['run_more_standard_b4_runtime_sweeps_now']}",
        f"- duplicate_stop_rules: {payload['true_batch_nas_inventory']['duplicate_stop_rules']}",
        f"- remaining_nonduplicate_work: {payload['true_batch_nas_inventory']['remaining_nonduplicate_work']}",
        "",
        "## Segment Drag Breakdown",
        "",
        f"- segment_drag_verdict: {payload['segment_drag_breakdown']['verdict']}",
        f"- segment_drag_analyzed_run_count: {payload['segment_drag_breakdown']['analyzed_run_count']}",
        f"- segment_drag_latest_microbatch_count: {payload['segment_drag_breakdown']['latest_microbatch_count']}",
        f"- segment_drag_final_avg_run_ms: {payload['segment_drag_breakdown']['final_avg_run_ms']}",
        f"- segment_drag_hidden_mean_avg_run_ms: {payload['segment_drag_breakdown']['hidden_mean_avg_run_ms']}",
        f"- segment_drag_final_vs_hidden_mean_ratio: {payload['segment_drag_breakdown']['final_vs_hidden_mean_ratio']}",
        f"- segment_drag_final_excess_ms_per_request_if_hidden_speed: {payload['segment_drag_breakdown']['final_excess_ms_per_request_if_hidden_speed']}",
        f"- segment_drag_token_excess_ms_per_request_if_hidden_speed: {payload['segment_drag_breakdown']['token_excess_ms_per_request_if_hidden_speed']}",
        f"- segment_drag_top_group_by_accounted_ms: {payload['segment_drag_breakdown']['top_group_by_accounted_ms']}",
        f"- segment_drag_top_group_contains_final_logits: {payload['segment_drag_breakdown']['top_group_contains_final_logits']}",
        f"- segment_drag_top_segments_by_avg_run_ms: {payload['segment_drag_breakdown']['top_segments_by_avg_run_ms']}",
        "",
        "## Runtime Experiment Gate",
        "",
        f"- runtime_gate_verdict: {payload['runtime_experiment_gate']['verdict']}",
        f"- s100p_runtime_experiment_now: {payload['runtime_experiment_gate']['s100p_runtime_experiment_now']}",
        f"- allowed_experiments: {payload['runtime_experiment_gate']['allowed_experiments']}",
        f"- run_standard_b4_sweeps_now: {payload['runtime_experiment_gate']['run_standard_b4_sweeps_now']}",
        f"- run_last_token_mb512_validation_now: {payload['runtime_experiment_gate']['run_last_token_mb512_validation_now']}",
        f"- run_capacity_partition_probe_now: {payload['runtime_experiment_gate']['run_capacity_partition_probe_now']}",
        f"- post_segment_blocks_standard_group_sweeps: {payload['runtime_experiment_gate']['post_segment_blocks_standard_group_sweeps']}",
        f"- post_segment_group_size_tuning_implication: {payload['runtime_experiment_gate']['post_segment_group_size_tuning_implication']}",
        f"- post_segment_inner_order_tuning_implication: {payload['runtime_experiment_gate']['post_segment_inner_order_tuning_implication']}",
        f"- service_gate_ready: {payload['runtime_experiment_gate']['service_gate_ready']}",
        f"- slo_freshness_accepted: {payload['runtime_experiment_gate']['slo_freshness_accepted']}",
        f"- runtime_gate_admission_evidence_ready: {payload['runtime_experiment_gate']['admission_evidence_ready']}",
        f"- runtime_gate_final_logits_leverage_gate_ready: {payload['runtime_experiment_gate']['final_logits_leverage_gate_ready']}",
        f"- runtime_gate_runtime_refactor_gate_ready: {payload['runtime_experiment_gate']['runtime_refactor_gate_ready']}",
        f"- runtime_gate_tuning_matrix_gate_ready: {payload['runtime_experiment_gate']['tuning_matrix_gate_ready']}",
        f"- runtime_gate_per_run_matrix_gate_ready: {payload['runtime_experiment_gate']['per_run_matrix_gate_ready']}",
        f"- runtime_gate_per_run_matrix_runs: {payload['runtime_experiment_gate']['per_run_matrix_run_count']} total, {payload['runtime_experiment_gate']['per_run_matrix_successful_run_count']} ok, {payload['runtime_experiment_gate']['per_run_matrix_failed_run_count']} failed",
        f"- runtime_gate_per_run_matrix_top_segment: {payload['runtime_experiment_gate']['per_run_matrix_top_segment']} @ {payload['runtime_experiment_gate']['per_run_matrix_top_segment_rate']}",
        f"- runtime_gate_per_run_matrix_standard_sweep_status: {payload['runtime_experiment_gate']['per_run_matrix_standard_sweep_status']}",
        f"- runtime_gate_admission_projected_saved_ms_per_request: {payload['runtime_experiment_gate']['admission_projected_saved_ms_per_request']}",
        f"- runtime_gate_admission_not_bpu_promotion_proof: {payload['runtime_experiment_gate']['admission_not_bpu_promotion_proof']}",
        f"- runtime_gate_admission_standard_sweeps_blocked: {payload['runtime_experiment_gate']['admission_standard_sweeps_blocked']}",
        f"- runtime_command_guard_verdict: {payload['runtime_command_guard']['verdict']}",
        f"- runtime_command_guard_active: {payload['runtime_command_guard']['command_guard_active']}",
        f"- runtime_command_guard_standard_sweeps_blocked: {payload['runtime_command_guard']['standard_sweep_commands_blocked']}",
        f"- runtime_command_guard_command_admitted: {payload['runtime_command_guard']['command_admitted']}",
        f"- runtime_command_guard_would_start_runtime: {payload['runtime_command_guard']['would_start_runtime']}",
        f"- last_token_compile_ready: {payload['runtime_experiment_gate']['last_token_compile_ready']}",
        f"- last_token_manifest_ready: {payload['runtime_experiment_gate']['last_token_manifest_ready']}",
        f"- last_token_runtime_validation_ready: {payload['runtime_experiment_gate']['last_token_runtime_validation_ready']}",
        f"- runtime_gate_blockers: {payload['runtime_experiment_gate']['blockers']}",
        f"- runtime_gate_reason: {payload['runtime_experiment_gate']['reason']}",
        f"- runtime_command_guard_classification_blockers: {payload['runtime_command_guard']['classification_blockers']}",
        "",
        "## Compile Command Guard",
        "",
        f"- compile_command_guard_verdict: {payload['compile_command_guard']['verdict']}",
        f"- compile_guard_active: {payload['compile_command_guard']['compile_guard_active']}",
        f"- compile_command_guard_only_single_segment_last_token_compile_allowed: {payload['compile_command_guard']['only_single_segment_last_token_compile_allowed']}",
        f"- compile_command_guard_b8_full_compile_blocked: {payload['compile_command_guard']['b8_full_compile_blocked']}",
        f"- compile_command_guard_blocked_now_by_readiness: {payload['compile_command_guard']['blocked_now_by_readiness']}",
        f"- compile_command_guard_blocked_now_by_capacity: {payload['compile_command_guard']['blocked_now_by_capacity']}",
        f"- compile_command_guard_command_admitted: {payload['compile_command_guard']['command_admitted']}",
        f"- compile_command_guard_preflight_admitted: {payload['compile_command_guard']['preflight_admitted']}",
        f"- compile_command_guard_would_start_compile: {payload['compile_command_guard']['would_start_compile']}",
        f"- compile_command_guard_commit_headroom_gb: {payload['compile_command_guard']['commit_headroom_gb']}",
        f"- compile_command_guard_required_commit_headroom_gb: {payload['compile_command_guard']['required_commit_headroom_gb']}",
        f"- compile_command_guard_large_private_process_count: {payload['compile_command_guard']['large_private_process_count']}",
        f"- compile_command_guard_classification_blockers: {payload['compile_command_guard']['classification_blockers']}",
        "",
        "## Next-Action Admission Pack",
        "",
        f"- next_action_admission_pack_verdict: {payload['next_action_admission_pack']['verdict']}",
        f"- next_action_allowed_now_count: {payload['next_action_admission_pack']['allowed_now_count']}",
        f"- next_action_preflight_only_count: {payload['next_action_admission_pack']['preflight_only_count']}",
        f"- next_action_blocked_action_count: {payload['next_action_admission_pack']['blocked_action_count']}",
        f"- next_action_would_start_runtime: {payload['next_action_admission_pack']['would_start_runtime']}",
        f"- next_action_would_start_compile: {payload['next_action_admission_pack']['would_start_compile']}",
        f"- next_action_per_run_matrix_gate_ready: {payload['next_action_admission_pack']['per_run_matrix_gate_ready']}",
        f"- next_action_per_run_matrix_runs: {payload['next_action_admission_pack']['per_run_matrix_run_count']} total, {payload['next_action_admission_pack']['per_run_matrix_successful_run_count']} ok, {payload['next_action_admission_pack']['per_run_matrix_failed_run_count']} failed",
        f"- next_action_per_run_matrix_top_segment: {payload['next_action_admission_pack']['per_run_matrix_top_segment']} @ {payload['next_action_admission_pack']['per_run_matrix_top_segment_rate']}",
        f"- next_action_per_run_matrix_standard_sweep_status: {payload['next_action_admission_pack']['per_run_matrix_standard_sweep_status']}",
        f"- next_action_queue_batch_product_work_allowed_now: {payload['next_action_admission_pack']['queue_batch_product_work_allowed_now']}",
        f"- next_action_local_runtime_refactor_analysis_allowed_now: {payload['next_action_admission_pack']['local_runtime_refactor_analysis_allowed_now']}",
        f"- next_action_compile_preflight_only_allowed_now: {payload['next_action_admission_pack']['compile_preflight_only_allowed_now']}",
        f"- next_action_only_future_runtime_candidate: {payload['next_action_admission_pack']['only_future_runtime_candidate']}",
        f"- next_action_failed_checks: {payload['next_action_admission_pack']['failed_checks']}",
        "",
        "## Segment Bottleneck Scorecard",
        "",
        f"- scorecard_verdict: {payload['segment_bottleneck_scorecard']['verdict']}",
        f"- primary_runtime_lever: {payload['segment_bottleneck_scorecard']['primary_runtime_lever']}",
        f"- preferred_inner_order: {payload['segment_bottleneck_scorecard']['preferred_inner_order']}",
        f"- preferred_group_policy: {payload['segment_bottleneck_scorecard']['preferred_group_policy']}",
        f"- avoid_more_mb512_boundary_sweeps: {payload['segment_bottleneck_scorecard']['avoid_more_mb512_boundary_sweeps']}",
        f"- avoid_gap_microbatch_sweeps_above_mb512: {payload['segment_bottleneck_scorecard']['avoid_gap_microbatch_sweeps_above_mb512']}",
        f"- next_runtime_candidate: {payload['segment_bottleneck_scorecard']['next_runtime_candidate']}",
        f"- analyzed_segment_major_run_count: {payload['segment_bottleneck_scorecard']['analyzed_segment_major_run_count']}",
        f"- default_collect_run_count: {payload['segment_bottleneck_scorecard']['default_collect_run_count']}",
        f"- default_collect_final_excess_mean_ms_per_request: {payload['segment_bottleneck_scorecard']['default_collect_final_excess_mean_ms_per_request']}",
        f"- default_collect_final_excess_stdev_ms_per_request: {payload['segment_bottleneck_scorecard']['default_collect_final_excess_stdev_ms_per_request']}",
        f"- all_segment_major_final_excess_mean_ms_per_request: {payload['segment_bottleneck_scorecard']['all_segment_major_final_excess_mean_ms_per_request']}",
        f"- all_segment_major_final_excess_stdev_ms_per_request: {payload['segment_bottleneck_scorecard']['all_segment_major_final_excess_stdev_ms_per_request']}",
        f"- final_excess_ms_per_request: {payload['segment_bottleneck_scorecard']['final_excess_ms_per_request']}",
        f"- final_load_ms_per_request: {payload['segment_bottleneck_scorecard']['final_load_ms_per_request']}",
        f"- token_excess_ms_per_request: {payload['segment_bottleneck_scorecard']['token_excess_ms_per_request']}",
        f"- token_load_ms_per_request: {payload['segment_bottleneck_scorecard']['token_load_ms_per_request']}",
        f"- max_hidden_index: {payload['segment_bottleneck_scorecard']['max_hidden_index']}",
        f"- max_hidden_excess_ms_per_request: {payload['segment_bottleneck_scorecard']['max_hidden_excess_ms_per_request']}",
        f"- g7_even_delta_ms_per_request: {payload['segment_bottleneck_scorecard']['g7_even_delta_ms_per_request']}",
        f"- microbatch_major_delta_ms_per_request: {payload['segment_bottleneck_scorecard']['microbatch_major_delta_ms_per_request']}",
        f"- no_observed_variant_beats_baseline: {payload['segment_bottleneck_scorecard']['no_observed_variant_beats_baseline']}",
        f"- top_action: {payload['segment_bottleneck_scorecard']['top_action']}",
        f"- top_action_reason: {payload['segment_bottleneck_scorecard']['top_action_reason']}",
        "",
        "## Segment Stability Audit",
        "",
        f"- stability_verdict: {payload['segment_stability_audit']['verdict']}",
        f"- analyzed_run_count: {payload['segment_stability_audit']['analyzed_run_count']}",
        f"- stable_primary_bottleneck: {payload['segment_stability_audit']['stable_primary_bottleneck']}",
        f"- final_logits_rank1_rate: {payload['segment_stability_audit']['final_logits_rank1_rate']}",
        f"- final_logits_top2_rate: {payload['segment_stability_audit']['final_logits_top2_rate']}",
        f"- final_logits_mean_positive_excess_ms_per_request: {payload['segment_stability_audit']['final_logits_mean_positive_excess_ms_per_request']}",
        f"- final_logits_cv_positive_excess: {payload['segment_stability_audit']['final_logits_cv_positive_excess']}",
        f"- final_to_token_excess_ratio: {payload['segment_stability_audit']['final_to_token_excess_ratio']}",
        f"- final_to_max_hidden_excess_ratio: {payload['segment_stability_audit']['final_to_max_hidden_excess_ratio']}",
        f"- do_not_run_hidden_order_sweeps_now: {payload['segment_stability_audit']['do_not_run_hidden_order_sweeps_now']}",
        f"- do_not_run_standard_b4_sweeps_now: {payload['segment_stability_audit']['do_not_run_standard_b4_sweeps_now']}",
        f"- next_runtime_candidate: {payload['segment_stability_audit']['next_runtime_candidate']}",
        f"- stability_reason: {payload['segment_stability_audit']['reason']}",
        "",
        "## HBM Load",
        "",
        f"- hbm_load_verdict: {payload['hbm_load']['verdict']}",
        f"- latest_microbatch_count: {payload['hbm_load']['latest_microbatch_count']}",
        f"- total_group_load_ms_per_request: {payload['hbm_load']['total_group_load_ms_per_request']}",
        f"- token_load_ms: {payload['hbm_load']['token_load_ms']}",
        f"- final_load_ms: {payload['hbm_load']['final_load_ms']}",
        f"- hidden_mean_load_ms: {payload['hbm_load']['hidden_mean_load_ms']}",
        f"- final_vs_hidden_load_ratio: {payload['hbm_load']['final_vs_hidden_load_ratio']}",
        f"- slowest_load_segment: {payload['hbm_load']['slowest_load_segment']}",
        f"- second_slowest_load_segment: {payload['hbm_load']['second_slowest_load_segment']}",
        f"- largest_load_group: {payload['hbm_load']['largest_load_group']}",
        f"- final_group_is_largest_load_group: {payload['hbm_load']['final_group_is_largest_load_group']}",
        f"- group_boundary_tuning_alone_not_primary: {payload['hbm_load']['group_boundary_tuning_alone_not_primary']}",
        f"- prewarm_hbm_default: {payload['hbm_load']['prewarm_hbm_default']}",
        f"- prewarm_wall_ms_per_request_delta: {payload['hbm_load']['prewarm_wall_ms_per_request_delta']}",
        f"- prewarm_group_load_ms_delta: {payload['hbm_load']['prewarm_group_load_ms_delta']}",
        f"- prewarm_group_load_ms_per_request_delta: {payload['hbm_load']['prewarm_group_load_ms_per_request_delta']}",
        f"- prewarm_ms: {payload['hbm_load']['prewarm_ms']}",
        f"- prewarm_mib: {payload['hbm_load']['prewarm_mib']}",
        f"- prewarm_net_prewarm_plus_group_load_ms_delta: {payload['hbm_load']['prewarm_net_prewarm_plus_group_load_ms_delta']}",
        "",
        "## Final Logits",
        "",
        f"- final_avg_run_ms: {payload['final_logits']['final_avg_run_ms']}",
        f"- hidden_mean_avg_run_ms: {payload['final_logits']['hidden_mean_avg_run_ms']}",
        f"- final_vs_hidden_avg_run_ratio: {payload['final_logits']['final_vs_hidden_avg_run_ratio']}",
        f"- final_segment_total_fraction: {payload['final_logits']['final_segment_total_fraction_of_all_segment_total']}",
        f"- final_output_verdict: {payload['final_output']['verdict']}",
        f"- latest_final_run_ms_per_request: {payload['final_output']['latest_final_run_ms_per_request']}",
        f"- latest_final_segment_overhead_ms_per_request: {payload['final_output']['latest_final_segment_overhead_ms_per_request']}",
        f"- latest_final_excess_ms_per_request_if_hidden_speed: {payload['final_output']['latest_final_excess_ms_per_request_if_hidden_speed']}",
        f"- final_output_recommended_next: {payload['final_output']['recommended_next']}",
        "",
        "## Last-Token Final Candidate",
        "",
        f"- sizing_verdict: {payload['last_token_candidate']['sizing_verdict']}",
        f"- readiness_verdict: {payload['last_token_candidate']['readiness_verdict']}",
        f"- status: {payload['last_token_candidate']['status']}",
        f"- compile_started: {payload['last_token_candidate']['compile_started']}",
        f"- compile_ready: {payload['last_token_candidate']['compile_ready']}",
        f"- runtime_validation_ready: {payload['last_token_candidate']['runtime_validation_ready']}",
        f"- readiness_blockers: {', '.join(payload['last_token_candidate']['readiness_blockers'])}",
        f"- remote_final_probe_has_final_hbm_root: {payload['last_token_candidate']['remote_final_probe_has_final_hbm_root']}",
        f"- remote_final_probe_has_final_logits_mode: {payload['last_token_candidate']['remote_final_probe_has_final_logits_mode']}",
        f"- remote_last_token_hbm_exists: {payload['last_token_candidate']['remote_last_token_hbm_exists']}",
        f"- remote_last_token_manifest_verified: {payload['last_token_candidate']['remote_last_token_manifest_verified']}",
        f"- current_final_shape: {payload['last_token_candidate']['current_final_shape']}",
        f"- candidate_target_shape: {payload['last_token_candidate']['candidate_target_shape']}",
        f"- output_element_reduction_vs_current: {payload['last_token_candidate']['output_element_reduction_vs_current']}",
        f"- projection_only_hypothesis_saved_ms_per_request: {payload['last_token_candidate']['projection_only_hypothesis_saved_ms_per_request']}",
        f"- preflight_commit_headroom_gb: {payload['last_token_candidate']['preflight_commit_headroom_gb']}",
        f"- preflight_min_commit_headroom_gb: {payload['last_token_candidate']['preflight_min_commit_headroom_gb']}",
        f"- preflight_commit_headroom_deficit_gb: {payload['last_token_candidate']['latest_preflight_commit_headroom_deficit_gb']}",
        f"- preflight_physical_available_gb: {payload['last_token_candidate']['latest_preflight_physical_available_gb']}",
        f"- largest_private_process: {payload['last_token_candidate']['largest_private_process']}",
        f"- next_gate: {payload['last_token_candidate']['next_gate']}",
        f"- experiment_gate_verdict: {payload['last_token_experiment_gate']['verdict']}",
        f"- experiment_gate_code_support_ready: {payload['last_token_experiment_gate']['code_support_ready']}",
        f"- experiment_gate_compile_ready: {payload['last_token_experiment_gate']['compile_ready']}",
        f"- experiment_gate_manifest_ready: {payload['last_token_experiment_gate']['manifest_ready']}",
        f"- experiment_gate_runtime_validation_ready: {payload['last_token_experiment_gate']['runtime_validation_ready']}",
        f"- experiment_gate_experiment_ready: {payload['last_token_experiment_gate']['experiment_ready']}",
        f"- experiment_gate_blockers: {payload['last_token_experiment_gate']['gate_blockers']}",
        f"- experiment_gate_remote_probe_supports_final_hbm_root: {payload['last_token_experiment_gate']['remote_probe_supports_final_hbm_root']}",
        f"- experiment_gate_remote_probe_supports_final_logits_mode: {payload['last_token_experiment_gate']['remote_probe_supports_final_logits_mode']}",
        f"- runtime_validation_plan_verdict: {payload['last_token_runtime_validation_plan']['verdict']}",
        f"- runtime_validation_plan_generated_at: {payload['last_token_runtime_validation_plan']['plan_generated_at']}",
        f"- runtime_validation_plan_ready: {payload['last_token_runtime_validation_plan']['validation_ready']}",
        f"- runtime_validation_plan_blockers: {payload['last_token_runtime_validation_plan']['blockers']}",
        f"- runtime_validation_plan_manifest_ready: {payload['last_token_runtime_validation_plan']['manifest_ready']}",
        f"- runtime_validation_plan_queue_idle: {payload['last_token_runtime_validation_plan']['queue_idle']}",
        f"- runtime_validation_plan_services_ready: {payload['last_token_runtime_validation_plan']['services_ready']}",
        f"- runtime_validation_plan_runtime_tools_ready: {payload['last_token_runtime_validation_plan']['runtime_tools_ready']}",
        f"- runtime_validation_plan_lock_busy: {payload['last_token_runtime_validation_plan']['lock_busy']}",
        f"- runtime_validation_plan_final_hbm_root_exists: {payload['last_token_runtime_validation_plan']['final_hbm_root_exists']}",
        f"- runtime_validation_plan_last_token_hbm_exists: {payload['last_token_runtime_validation_plan']['last_token_hbm_exists']}",
        f"- runtime_validation_plan_manifest_exists: {payload['last_token_runtime_validation_plan']['manifest_exists']}",
        f"- runtime_validation_plan_manifest_verified: {payload['last_token_runtime_validation_plan']['manifest_verified']}",
        f"- runtime_validation_plan_hbm_path: {payload['last_token_runtime_validation_plan']['hbm_path']}",
        f"- runtime_validation_plan_expected_final_shape: {payload['last_token_runtime_validation_plan']['expected_final_shape']}",
        f"- runtime_validation_plan_microbatch_count: {payload['last_token_runtime_validation_plan']['microbatch_count']}",
        f"- runtime_validation_plan_command: {payload['last_token_runtime_validation_plan']['runtime_command']}",
        f"- validation_compare_verdict: {payload['last_token_validation_compare']['verdict']}",
        f"- validation_compare_decision: {payload['last_token_validation_compare']['decision']}",
        f"- validation_compare_candidate_exists: {payload['last_token_validation_compare']['candidate_exists']}",
        f"- validation_compare_candidate_path: {payload['last_token_validation_compare']['candidate_path']}",
        f"- validation_compare_baseline_path: {payload['last_token_validation_compare']['baseline_path']}",
        f"- validation_compare_candidate_final_shape: {payload['last_token_validation_compare']['candidate_final_shape']}",
        f"- validation_compare_candidate_final_logits_mode: {payload['last_token_validation_compare']['candidate_final_logits_mode']}",
        f"- validation_compare_structural_ok: {payload['last_token_validation_compare']['structural_ok']}",
        f"- validation_compare_performance_ok: {payload['last_token_validation_compare']['performance_ok']}",
        f"- validation_compare_ms_per_request_delta: {payload['last_token_validation_compare']['ms_per_request_delta']}",
        f"- validation_compare_avg_bpu_loading_delta: {payload['last_token_validation_compare']['avg_bpu_loading_delta']}",
        f"- validation_compare_avg_nonzero_bpu_loading_delta: {payload['last_token_validation_compare']['avg_nonzero_bpu_loading_delta']}",
        f"- validation_compare_final_run_ms_per_request_delta: {payload['last_token_validation_compare']['final_run_ms_per_request_delta']}",
        "",
        "## Final-Logits Leverage Model",
        "",
        f"- leverage_verdict: {payload['final_logits_leverage_model']['verdict']}",
        f"- primary_candidate: {payload['final_logits_leverage_model']['primary_candidate']}",
        f"- projection_saved_ms_per_request: {payload['final_logits_leverage_model']['projection_saved_ms_per_request']}",
        f"- final_excess_ms_per_request_if_hidden_speed: {payload['final_logits_leverage_model']['final_excess_ms_per_request_if_hidden_speed']}",
        f"- projection_capture_of_final_excess_pct: {payload['final_logits_leverage_model']['projection_capture_of_final_excess_pct']}",
        f"- latest_projected_ms_per_request_if_saved: {payload['final_logits_leverage_model']['latest_projected_ms_per_request_if_saved']}",
        f"- latest_projected_latency_reduction_pct: {payload['final_logits_leverage_model']['latest_projected_latency_reduction_pct']}",
        f"- latest_nonzero_shortfall_points: {payload['final_logits_leverage_model']['latest_nonzero_shortfall_points']}",
        f"- low_load_nonzero_shortfall_points: {payload['final_logits_leverage_model']['low_load_nonzero_shortfall_points']}",
        f"- projected_max_avg_bpu_if_nonzero_unchanged: {payload['final_logits_leverage_model']['projected_max_avg_bpu_if_nonzero_unchanged']}",
        f"- projected_max_still_below_93: {payload['final_logits_leverage_model']['projected_max_still_below_93']}",
        f"- projection_is_latency_meaningful: {payload['final_logits_leverage_model']['projection_is_latency_meaningful']}",
        f"- projection_is_not_bpu_promotion_proof: {payload['final_logits_leverage_model']['projection_is_not_bpu_promotion_proof']}",
        f"- do_not_promote_without_runtime_result: {payload['final_logits_leverage_model']['do_not_promote_without_runtime_result']}",
        f"- do_not_run_standard_group_or_inner_order_sweeps: {payload['final_logits_leverage_model']['do_not_run_standard_group_or_inner_order_sweeps']}",
        f"- validation_threshold_wall_ms_per_request: {payload['final_logits_leverage_model']['min_wall_improvement_ms_per_request']}",
        f"- validation_threshold_final_run_ms_per_request: {payload['final_logits_leverage_model']['min_final_run_improvement_ms_per_request']}",
        f"- validation_threshold_max_nonzero_bpu_regression_points: {payload['final_logits_leverage_model']['max_nonzero_bpu_regression_points']}",
        "",
        "## Compile Capacity",
        "",
        f"- capacity_verdict: {payload['compile_capacity']['verdict']}",
        f"- commit_headroom_gb: {payload['compile_capacity']['commit_headroom_gb']}",
        f"- commit_headroom_deficit_gb: {payload['compile_capacity']['commit_headroom_deficit_gb']}",
        f"- reclaim_private_gb: {payload['compile_capacity']['reclaim_private_gb']}",
        f"- projected_commit_headroom_after_reclaim_gb: {payload['compile_capacity']['projected_commit_headroom_after_reclaim_gb']}",
        f"- remaining_headroom_deficit_after_reclaim_gb: {payload['compile_capacity']['remaining_headroom_deficit_after_reclaim_gb']}",
        f"- required_commit_limit_after_reclaim_gb: {payload['compile_capacity']['required_commit_limit_after_reclaim_gb']}",
        f"- additional_commit_limit_needed_after_reclaim_gb: {payload['compile_capacity']['additional_commit_limit_needed_after_reclaim_gb']}",
        f"- pagefile_setting_mode: {payload['compile_capacity']['pagefile_setting_mode']}",
        f"- current_pagefile_allocated_total_gb: {payload['compile_capacity']['current_pagefile_allocated_total_gb']}",
        f"- recommended_additional_commit_limit_with_safety_gb: {payload['compile_capacity']['recommended_additional_commit_limit_with_safety_gb']}",
        f"- recommended_commit_limit_gb: {payload['compile_capacity']['recommended_commit_limit_gb']}",
        f"- do_not_start_compile_now: {payload['compile_capacity']['do_not_start_compile_now']}",
        f"- increase_commit_limit_or_pagefile_before_compile: {payload['compile_capacity']['increase_commit_limit_or_pagefile_before_compile']}",
        "",
        "## First Response",
        "",
        f"- first_response_verdict: {payload['first_response']['first_response_verdict']}",
        f"- routing_verdict: {payload['first_response']['routing_verdict']}",
        f"- fast_status_verdict: {payload['first_response']['fast_status_verdict']}",
        f"- fast_path_regression_verdict: {payload['first_response']['fast_path_regression_verdict']}",
        f"- ttft_p50_ms: {payload['first_response']['ttft_p50_ms']}",
        f"- first_progress_p50_ms: {payload['first_response']['first_progress_p50_ms']}",
        f"- first_content_p50_ms: {payload['first_response']['first_content_p50_ms']}",
        f"- localized_status_fast_path_ready: {payload['first_response']['localized_status_fast_path_ready']}",
        f"- localized_status_first_content_ms: {payload['first_response']['localized_status_first_content_ms']}",
        f"- localized_status_delta_ms: {payload['first_response']['localized_status_delta_ms']}",
        f"- regression_quick_ready_first_content_ms: {payload['first_response']['regression_quick_ready_first_content_ms']}",
        f"- regression_identity_first_content_ms: {payload['first_response']['regression_identity_first_content_ms']}",
        f"- regression_localized_status_first_content_ms: {payload['first_response']['regression_localized_status_first_content_ms']}",
        f"- first_response_slo_tier_guard_verdict: {payload['first_response_slo_tier_guard']['verdict']}",
        f"- first_response_slo_fast_path_ready: {payload['first_response_slo_tier_guard']['fast_path_ready']}",
        f"- first_response_slo_fast_path_max_first_content_ms: {payload['first_response_slo_tier_guard']['fast_path_max_first_content_ms']}",
        f"- first_response_slo_sse_progress_ready: {payload['first_response_slo_tier_guard']['sse_progress_ready']}",
        f"- first_response_slo_sse_first_progress_p50_ms: {payload['first_response_slo_tier_guard']['sse_first_progress_p50_ms']}",
        f"- first_response_backend_tracked_separately: {payload['first_response_slo_tier_guard']['backend_first_content_tracked_separately']}",
        f"- first_response_backend_not_true_batch_work: {payload['first_response_slo_tier_guard']['backend_first_content_latency_is_not_true_batch_work']}",
        f"- first_response_warning_triage_verdict: {payload['first_response_warning_triage']['verdict']}",
        f"- first_response_warning_triaged: {payload['first_response_warning_triage']['warning_is_product_triaged']}",
        f"- first_response_warning_source_verdict: {payload['first_response_warning_triage']['source_warning_verdict']}",
        f"- first_response_warning_quickpath_delta_ms: {payload['first_response_warning_triage']['quickpath_delta_ms']}",
        f"- first_response_warning_backend_not_true_batch_work: {payload['first_response_warning_triage']['backend_first_content_latency_is_not_true_batch_work']}",
        f"- slo_limited_evidence_triage_verdict: {payload['slo_limited_evidence_triage']['verdict']}",
        f"- slo_limited_evidence_triaged: {payload['slo_limited_evidence_triage']['limited_evidence_triaged']}",
        f"- slo_limited_evidence_release_blocker: {payload['slo_limited_evidence_triage']['release_blocker']}",
        f"- slo_limited_warnings: {payload['slo_limited_evidence_triage']['slo_warnings']}",
        f"- slo_limited_concurrency_verdict: {payload['slo_limited_evidence_triage']['concurrency_verdict']}",
        f"- slo_limited_dialog_health_errors: {payload['slo_limited_evidence_triage']['dialog_health_error_count']}",
        f"- first_response_slo_runtime_started: {payload['first_response_slo_tier_guard']['runtime_started']}",
        f"- first_response_slo_compile_started: {payload['first_response_slo_tier_guard']['compile_started']}",
        "",
        "## Product Evidence",
        "",
        f"- guardrail_verdict: {payload['product_evidence']['guardrail_verdict']}",
        f"- guardrail_default_status_contract_ready: {payload['product_evidence']['guardrail_default_status_contract_ready']}",
        f"- guardrail_default_rollback_dry_run_ready: {payload['product_evidence']['guardrail_default_rollback_dry_run_ready']}",
        f"- guardrail_status_script_sha256: {payload['product_evidence']['guardrail_status_script_sha256']}",
        f"- guardrail_rollback_script_sha256: {payload['product_evidence']['guardrail_rollback_script_sha256']}",
        f"- gateway_listener_ownership_verdict: {payload['product_evidence']['gateway_listener_ownership_verdict']}",
        f"- gateway_listener_pid: {payload['product_evidence']['gateway_listener_pid']}",
        f"- gateway_main_pid: {payload['product_evidence']['gateway_main_pid']}",
        f"- gateway_listener_matches_systemd_main_pid: {payload['product_evidence']['gateway_listener_matches_systemd_main_pid']}",
        f"- gateway_orphan_listener_detected: {payload['product_evidence']['gateway_orphan_listener_detected']}",
        f"- gateway_listener_health_ok: {payload['product_evidence']['gateway_listener_health_ok']}",
        f"- gateway_listener_drift_gate_verdict: {payload['product_evidence']['gateway_listener_drift_gate_verdict']}",
        f"- gateway_listener_drift_snapshot_ok: {payload['product_evidence']['gateway_listener_drift_snapshot_ok']}",
        f"- gateway_listener_drift_live_matches_systemd_main_pid: {payload['product_evidence']['gateway_listener_drift_live_matches_systemd_main_pid']}",
        f"- gateway_listener_drift_live_orphan_detected: {payload['product_evidence']['gateway_listener_drift_live_orphan_detected']}",
        f"- gateway_listener_drift_live_health_ok: {payload['product_evidence']['gateway_listener_drift_live_health_ok']}",
        f"- gateway_listener_drift_warning_count: {payload['product_evidence']['gateway_listener_drift_warning_count']}",
        f"- slo_verdict: {payload['product_evidence']['slo_verdict']}",
        f"- slo_required_accepted_count: {payload['product_evidence']['slo_required_accepted_count']}",
        f"- slo_required_contract_count: {payload['product_evidence']['slo_required_contract_count']}",
        f"- slo_blocker_count: {payload['product_evidence']['slo_blocker_count']}",
        f"- portal_verdict: {payload['product_evidence']['portal_verdict']}",
        f"- portal_result_count: {payload['product_evidence']['portal_result_count']}",
        f"- portal_failure_count: {payload['product_evidence']['portal_failure_count']}",
        f"- portal_execution_performed: {payload['product_evidence']['portal_execution_performed']}",
        f"- partial_batch_flush_verdict: {payload['product_evidence']['partial_batch_flush_verdict']}",
        f"- partial_batch_flush_latest_text_queue_run: {payload['product_evidence']['partial_batch_flush_latest_text_queue_run']}",
        f"- hidden_materialize_design_contract_verdict: {payload['product_evidence']['hidden_materialize_design_contract_verdict']}",
        f"- hidden_materialize_design_current_preallocate_hidden_rejected: {payload['product_evidence']['hidden_materialize_design_current_preallocate_hidden_rejected']}",
        f"- hidden_materialize_design_default_runtime_change_allowed_now: {payload['product_evidence']['hidden_materialize_design_default_runtime_change_allowed_now']}",
        f"- hidden_materialize_design_s100p_runtime_allowed_now: {payload['product_evidence']['hidden_materialize_design_s100p_runtime_allowed_now']}",
        f"- hidden_materialize_design_compile_start_allowed_now: {payload['product_evidence']['hidden_materialize_design_compile_start_allowed_now']}",
        f"- hidden_materialize_telemetry_contract_verdict: {payload['product_evidence']['hidden_materialize_telemetry_contract_verdict']}",
        f"- hidden_materialize_telemetry_source_ready: {payload['product_evidence']['hidden_materialize_telemetry_source_ready']}",
        f"- hidden_materialize_telemetry_default_runtime_change_allowed_now: {payload['product_evidence']['hidden_materialize_telemetry_default_runtime_change_allowed_now']}",
        f"- hidden_materialize_telemetry_s100p_runtime_allowed_now: {payload['product_evidence']['hidden_materialize_telemetry_s100p_runtime_allowed_now']}",
        f"- hidden_materialize_telemetry_compile_start_allowed_now: {payload['product_evidence']['hidden_materialize_telemetry_compile_start_allowed_now']}",
        "",
        "## Source Paths",
        "",
    ]
    )
    lines.extend(f"- {key}: {value}" for key, value in payload["source_paths"].items())
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if verdict.startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
