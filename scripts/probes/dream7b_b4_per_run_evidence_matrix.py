#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_per_run_evidence_matrix"
DEFAULT_ANALYSIS_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return round(number, digits) if number is not None else None


def delta(value: Any, baseline: Any, digits: int = 6) -> float | None:
    left = as_float(value)
    right = as_float(baseline)
    if left is None or right is None:
        return None
    return round(left - right, digits)


def is_success(row: dict[str, Any]) -> bool:
    return str(row.get("verdict") or "").startswith("ok_")


def group_signature(row: dict[str, Any]) -> str:
    return ",".join(str(item) for item in row.get("group_ranges") or [])


def bool_value(row: dict[str, Any], key: str) -> bool:
    return bool(row.get(key))


def scenario(row: dict[str, Any]) -> str:
    name = str(row.get("name") or "")
    if not is_success(row):
        if "capacity" in name or row.get("processed_request_count") in (0, None):
            return "capacity_failure"
        return "failed_runtime"
    if bool_value(row, "prewarm_hbm"):
        return "prewarm_hbm"
    if bool_value(row, "preallocate_hidden"):
        return "preallocate_hidden"
    if row.get("release_gc_mode") == "skip":
        return "release_gc_skip"
    if row.get("inner_order") == "microbatch-major":
        return "microbatch_major_order"
    signature = group_signature(row)
    if "24:27,27:28" in signature:
        return "final_logits_isolated_group"
    group_count = as_int(row.get("group_count"))
    if group_count and group_count != 5:
        return f"{group_count}_group_split"
    return "standard_5_group_segment_major"


def same_mb_baselines(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    by_mb: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        mb = as_int(row.get("microbatch_count"))
        if mb is None or not is_success(row):
            continue
        if (
            row.get("inner_order") == "segment-major"
            and as_int(row.get("group_count")) == 5
            and not bool_value(row, "preallocate_hidden")
            and not bool_value(row, "prewarm_hbm")
            and row.get("release_gc_mode") == "collect"
        ):
            by_mb[mb].append(row)
    return {
        mb: min(candidates, key=lambda item: as_float(item.get("amortized_wall_ms_per_request")) or 1e30)
        for mb, candidates in by_mb.items()
    }


def find_baseline(rows: list[dict[str, Any]], comparisons: dict[str, Any]) -> dict[str, Any] | None:
    split = comparisons.get("group_split_mb512_segment_major") or {}
    baseline_file = str(split.get("five_group_file") or "").replace("\\", "/")
    for row in rows:
        if baseline_file and str(row.get("file") or "").replace("\\", "/") == baseline_file:
            return row
    for row in rows:
        if (
            is_success(row)
            and as_int(row.get("microbatch_count")) == 512
            and row.get("inner_order") == "segment-major"
            and as_int(row.get("group_count")) == 5
            and not bool_value(row, "preallocate_hidden")
            and not bool_value(row, "prewarm_hbm")
        ):
            return row
    return None


def compact_row(
    row: dict[str, Any],
    baseline: dict[str, Any] | None,
    same_mb_baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    slowest = (row.get("slowest_segments") or [{}])[0]
    ms_per_request = row.get("amortized_wall_ms_per_request")
    return {
        "name": row.get("name"),
        "status": "ok" if is_success(row) else "failed",
        "scenario": scenario(row),
        "microbatch_count": row.get("microbatch_count"),
        "processed_request_count": row.get("processed_request_count"),
        "inner_order": row.get("inner_order"),
        "group_count": row.get("group_count"),
        "group_signature": group_signature(row),
        "preallocate_hidden": row.get("preallocate_hidden"),
        "prewarm_hbm": row.get("prewarm_hbm"),
        "release_gc_mode": row.get("release_gc_mode"),
        "ms_per_request": round_or_none(ms_per_request, 6),
        "delta_vs_mb512_gap_baseline_ms_per_request": delta(
            ms_per_request,
            baseline.get("amortized_wall_ms_per_request") if baseline else None,
        ),
        "delta_vs_same_microbatch_best_5g_ms_per_request": delta(
            ms_per_request,
            same_mb_baseline.get("amortized_wall_ms_per_request") if same_mb_baseline else None,
        ),
        "avg_bpu": round_or_none(row.get("avg_bpu_loading"), 6),
        "nonzero_bpu": round_or_none(row.get("avg_nonzero_bpu_loading"), 6),
        "group_load_ms_per_request": round_or_none(row.get("group_load_ms_per_request"), 6),
        "group_load_fraction_of_wall": round_or_none(row.get("group_load_fraction_of_wall"), 6),
        "measured_active_fraction_of_wall": round_or_none(
            row.get("measured_active_fraction_of_wall"), 6
        ),
        "estimated_host_gap_fraction_of_wall": round_or_none(
            row.get("estimated_host_gap_fraction_of_wall"), 6
        ),
        "estimated_unaccounted_gap_fraction_of_wall": round_or_none(
            row.get("estimated_unaccounted_gap_fraction_of_wall"), 6
        ),
        "required_nonzero_bpu_for_93_avg": round_or_none(
            row.get("required_nonzero_bpu_for_93_avg"), 6
        ),
        "slowest_segment": {
            "index": slowest.get("index"),
            "kind": slowest.get("kind"),
            "group": slowest.get("group"),
            "avg_run_ms": slowest.get("avg_run_ms"),
            "completed_microbatch_count": slowest.get("completed_microbatch_count"),
        },
        "errors": row.get("errors") or [],
    }


def top_segment_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    examples: dict[str, dict[str, Any]] = {}
    eligible = 0
    for row in rows:
        if not is_success(row):
            continue
        slowest = row.get("slowest_segments") or []
        if not slowest:
            continue
        eligible += 1
        top = slowest[0]
        key = f"seg{int(top.get('index')):02d}_{top.get('kind')}"
        counter[key] += 1
        examples.setdefault(
            key,
            {
                "run": row.get("name"),
                "avg_run_ms": top.get("avg_run_ms"),
                "group": top.get("group"),
            },
        )
    top_key, top_count = counter.most_common(1)[0] if counter else (None, 0)
    return {
        "eligible_success_run_count": eligible,
        "top_segment_counts": dict(counter),
        "most_common_top_segment": top_key,
        "most_common_top_segment_count": top_count,
        "most_common_top_segment_rate": round(top_count / eligible, 6) if eligible else None,
        "examples": examples,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = args.analysis_root
    schedule_path = root / "dream7b_true_batch_schedule_analysis_20260620.json"
    tuning_path = root / "dream7b_b4_tuning_decision_matrix_20260621.json"
    next_action_path = root / "dream7b_b4_next_action_admission_pack_20260621.json"
    scorecard_path = root / "dream7b_b4_segment_group_schedule_scorecard_20260621.json"
    schedule = read_json(schedule_path)
    tuning = read_json(tuning_path)
    next_action = read_json(next_action_path)
    scorecard = read_json(scorecard_path)
    runs = schedule.get("b4_true_batch_runs") or []
    comparisons = schedule.get("comparisons") or {}
    baseline = find_baseline(runs, comparisons)
    same_baselines = same_mb_baselines(runs)
    matrix_rows = [
        compact_row(row, baseline, same_baselines.get(as_int(row.get("microbatch_count")) or -1))
        for row in sorted(
            runs,
            key=lambda item: (
                as_int(item.get("microbatch_count")) or -1,
                str(item.get("inner_order") or ""),
                as_int(item.get("group_count")) or -1,
                str(item.get("name") or ""),
            ),
        )
    ]

    successful_rows = [row for row in matrix_rows if row["status"] == "ok"]
    failed_rows = [row for row in matrix_rows if row["status"] != "ok"]
    scenario_counts = Counter(row["scenario"] for row in matrix_rows)
    microbatch_success_counts = Counter(
        str(row["microbatch_count"]) for row in successful_rows
    )
    mb512_nonbaseline = [
        row
        for row in successful_rows
        if row["microbatch_count"] == 512
        and row["scenario"] != "standard_5_group_segment_major"
    ]
    mb512_slowest_nonbaseline = sorted(
        mb512_nonbaseline,
        key=lambda row: as_float(row["delta_vs_same_microbatch_best_5g_ms_per_request"]) or 1e30,
    )
    scaling_delta = comparisons.get("segment_major_5_group_scaling_delta") or {}
    split = comparisons.get("group_split_mb512_segment_major") or {}
    inner = comparisons.get("inner_order_mb512_5_groups") or {}
    tuning_decision = tuning.get("decision") or {}
    next_summary = next_action.get("summary") or {}
    standard_sweep_action = next(
        (
            action
            for action in next_action.get("actions") or []
            if action.get("id") == "standard_b4_runtime_sweep"
        ),
        {},
    )
    scorecard_decision = scorecard.get("decision") or {}

    findings = {
        "slowest_segment_consistency": top_segment_distribution(runs),
        "microbatch_scaling": {
            "from_to": scaling_delta.get("microbatch_count_from_to"),
            "avg_bpu_delta": scaling_delta.get("avg_bpu_delta"),
            "nonzero_bpu_delta": scaling_delta.get("nonzero_bpu_delta"),
            "ms_per_request_ratio": scaling_delta.get("ms_per_request_ratio"),
            "interpretation": "microbatch scaling mainly amortizes fixed load; nonzero BPU intensity changes little.",
        },
        "inner_order_mb512": {
            "segment_major_ms_per_request_delta": inner.get(
                "segment_major_ms_per_request_delta"
            ),
            "segment_major_avg_bpu_delta": inner.get("segment_major_avg_bpu_delta"),
            "decision": "keep_segment_major",
        },
        "group_split_mb512": {
            "against_gap_field_baseline": {
                "six_group_delta_ms_per_request": split.get(
                    "six_group_ms_per_request_delta"
                ),
                "seven_group_delta_ms_per_request": split.get(
                    "seven_group_ms_per_request_delta"
                ),
                "final_isolated_delta_ms_per_request": split.get(
                    "final_isolated_group_ms_per_request_delta"
                ),
            },
            "against_best_same_microbatch_baseline": [
                {
                    "name": row["name"],
                    "scenario": row["scenario"],
                    "delta_ms_per_request": row[
                        "delta_vs_same_microbatch_best_5g_ms_per_request"
                    ],
                    "avg_bpu_delta_vs_same_baseline": None,
                }
                for row in mb512_slowest_nonbaseline[:8]
            ],
            "decision": "do_not_run_more_standard_group_or_inner_order_sweeps_now",
        },
        "admission": {
            "production_default": next_summary.get("production_default"),
            "queue_should_remain_default": next_summary.get("queue_should_remain_default"),
            "next_nonduplicate_runtime_candidate": next_summary.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "would_start_runtime": next_summary.get("would_start_runtime"),
            "would_start_compile": next_summary.get("would_start_compile"),
            "primary_schedule_bottleneck": scorecard_decision.get(
                "primary_schedule_bottleneck"
            ),
            "primary_code_target": scorecard_decision.get("primary_code_target"),
            "preferred_group_policy": scorecard_decision.get("preferred_group_policy"),
            "preferred_inner_order": scorecard_decision.get("preferred_inner_order"),
            "run_more_standard_b4_group_or_inner_order_sweeps_now": scorecard_decision.get(
                "run_more_standard_b4_group_or_inner_order_sweeps_now"
            ),
            "standard_b4_runtime_sweep_status": standard_sweep_action.get("status"),
        },
    }

    checks = {
        "schedule_report_found": schedule_path.exists(),
        "has_b4_runs": len(runs) >= 1,
        "has_successful_runs": len(successful_rows) >= 1,
        "has_failed_capacity_rows_preserved": any(
            row["scenario"] == "capacity_failure" for row in matrix_rows
        ),
        "baseline_found": baseline is not None,
        "slowest_segment_distribution_ready": bool(
            findings["slowest_segment_consistency"]["top_segment_counts"]
        ),
        "final_logits_is_consistent_top_segment": findings[
            "slowest_segment_consistency"
        ]["most_common_top_segment"]
        == "seg27_final_logits"
        and findings["slowest_segment_consistency"]["most_common_top_segment_rate"]
        == 1.0,
        "matrix_contains_mb512_group_variants": any(
            row["microbatch_count"] == 512 and row["scenario"].endswith("_group_split")
            for row in matrix_rows
        )
        and any(
            row["microbatch_count"] == 512
            and row["scenario"] == "final_logits_isolated_group"
            for row in matrix_rows
        ),
        "matrix_contains_inner_order_variant": any(
            row["scenario"] == "microbatch_major_order" for row in matrix_rows
        ),
        "standard_sweeps_blocked_by_admission": next_summary.get(
            "would_start_runtime"
        )
        is False
        and str(standard_sweep_action.get("status") or "").startswith("blocked")
        and scorecard_decision.get(
            "run_more_standard_b4_group_or_inner_order_sweeps_now"
        )
        is False,
    }
    failed_checks = [key for key, value in checks.items() if not value]

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_per_run_evidence_matrix"
        if not failed_checks
        else "warning_dream7b_b4_per_run_evidence_matrix",
        "source_paths": {
            "schedule_analysis": str(schedule_path),
            "tuning_decision_matrix": str(tuning_path),
            "next_action_admission_pack": str(next_action_path),
            "segment_group_schedule_scorecard": str(scorecard_path),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "summary": {
            "run_count": len(matrix_rows),
            "successful_run_count": len(successful_rows),
            "failed_run_count": len(failed_rows),
            "scenario_counts": dict(sorted(scenario_counts.items())),
            "microbatch_success_counts": dict(
                sorted(microbatch_success_counts.items(), key=lambda item: int(item[0]))
            ),
            "baseline_name": baseline.get("name") if baseline else None,
            "baseline_ms_per_request": baseline.get("amortized_wall_ms_per_request")
            if baseline
            else None,
            "most_common_top_segment": findings["slowest_segment_consistency"][
                "most_common_top_segment"
            ],
            "most_common_top_segment_rate": findings["slowest_segment_consistency"][
                "most_common_top_segment_rate"
            ],
            "next_nonduplicate_runtime_candidate": next_summary.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "standard_b4_runtime_sweep_status": standard_sweep_action.get("status"),
            "run_more_standard_group_or_inner_order_sweeps_now": scorecard_decision.get(
                "run_more_standard_b4_group_or_inner_order_sweeps_now"
            ),
            "preferred_group_policy": scorecard_decision.get("preferred_group_policy"),
            "preferred_inner_order": scorecard_decision.get("preferred_inner_order"),
        },
        "findings": findings,
        "matrix_rows": matrix_rows,
        "audit": {
            "remote_access_performed": False,
            "runtime_started": False,
            "compile_started": False,
            "source_files_modified_by_probe": False,
        },
    }


def render_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    findings = payload["findings"]
    lines = [
        "# Dream7B B=4 Per-Run Evidence Matrix",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- failed_checks: `{payload['failed_checks']}`",
        f"- run_count: `{summary['run_count']}`",
        f"- successful_run_count: `{summary['successful_run_count']}`",
        f"- failed_run_count: `{summary['failed_run_count']}`",
        f"- baseline: `{summary['baseline_name']}` at `{summary['baseline_ms_per_request']}` ms/request",
        f"- most_common_top_segment: `{summary['most_common_top_segment']}` rate `{summary['most_common_top_segment_rate']}`",
        f"- preferred_group_policy: `{summary['preferred_group_policy']}`",
        f"- preferred_inner_order: `{summary['preferred_inner_order']}`",
        f"- next_nonduplicate_runtime_candidate: `{summary['next_nonduplicate_runtime_candidate']}`",
        f"- standard_b4_runtime_sweep_status: `{summary['standard_b4_runtime_sweep_status']}`",
        f"- run_more_standard_group_or_inner_order_sweeps_now: `{summary['run_more_standard_group_or_inner_order_sweeps_now']}`",
        "",
        "## Findings",
        "",
        f"- slowest segment: `{findings['slowest_segment_consistency']['most_common_top_segment']}` in "
        f"`{findings['slowest_segment_consistency']['most_common_top_segment_count']}` / "
        f"`{findings['slowest_segment_consistency']['eligible_success_run_count']}` successful runs with segment timing.",
        f"- microbatch scaling: `{findings['microbatch_scaling']['from_to']}` changes avg BPU by "
        f"`{findings['microbatch_scaling']['avg_bpu_delta']}` points, nonzero BPU by "
        f"`{findings['microbatch_scaling']['nonzero_bpu_delta']}` points, and ms/request ratio is "
        f"`{findings['microbatch_scaling']['ms_per_request_ratio']}`.",
        f"- inner order mb512: segment-major delta is `{findings['inner_order_mb512']['segment_major_ms_per_request_delta']}` ms/request versus microbatch-major.",
        f"- group split mb512: g6 `{findings['group_split_mb512']['against_gap_field_baseline']['six_group_delta_ms_per_request']}`, "
        f"g7 `{findings['group_split_mb512']['against_gap_field_baseline']['seven_group_delta_ms_per_request']}`, "
        f"final-isolated `{findings['group_split_mb512']['against_gap_field_baseline']['final_isolated_delta_ms_per_request']}` ms/request versus the gap-field baseline.",
        f"- admission: runtime `{findings['admission']['would_start_runtime']}`, compile `{findings['admission']['would_start_compile']}`, primary target `{findings['admission']['primary_code_target']}`.",
        "",
        "## Matrix",
        "",
        "| run | status | scenario | mb | groups | order | ms/request | delta vs mb512 gap | delta vs same-mb best 5g | avg BPU | nonzero BPU | load ms/request | active frac | host-gap frac | top segment |",
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["matrix_rows"]:
        top = row["slowest_segment"]
        top_label = (
            f"seg{top.get('index')}_{top.get('kind')}"
            if top.get("index") is not None
            else ""
        )
        lines.append(
            f"| `{row['name']}` | {row['status']} | {row['scenario']} | "
            f"{row['microbatch_count']} | {row['group_count']} | {row['inner_order']} | "
            f"{row['ms_per_request']} | {row['delta_vs_mb512_gap_baseline_ms_per_request']} | "
            f"{row['delta_vs_same_microbatch_best_5g_ms_per_request']} | {row['avg_bpu']} | "
            f"{row['nonzero_bpu']} | {row['group_load_ms_per_request']} | "
            f"{row['measured_active_fraction_of_wall']} | {row['estimated_host_gap_fraction_of_wall']} | "
            f"{top_label} |"
        )
    lines.extend(
        [
            "",
            "## Audit",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in payload["audit"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    payload = build_payload(args)
    json_path = args.output_json or (
        args.analysis_root / "dream7b_b4_per_run_evidence_matrix_20260622.json"
    )
    md_path = args.output_md or json_path.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_md(md_path, payload)
    print(json_path)
    print(md_path)
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
