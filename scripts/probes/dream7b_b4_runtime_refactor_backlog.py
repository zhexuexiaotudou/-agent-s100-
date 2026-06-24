#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SCHEDULER = DEFAULT_ROOT / "dream7b_b4_scheduler_overhead_budget_20260620.json"
DEFAULT_GROUP_SWITCH = DEFAULT_ROOT / "dream7b_b4_group_switch_accounting_20260619.json"
DEFAULT_LAST_TOKEN_GATE = DEFAULT_ROOT / "dream7b_b4_last_token_experiment_gate_20260620.json"
DEFAULT_NAS_INVENTORY = DEFAULT_ROOT / "dream7b_true_batch_nas_inventory_20260620.json"
DEFAULT_POST_INSTRUMENTATION_OVERHEAD = (
    DEFAULT_ROOT / "dream7b_b4_post_instrumentation_overhead_analysis_20260621.json"
)
DEFAULT_HIDDEN_BUFFER_DECISION = DEFAULT_ROOT / "dream7b_b4_hidden_buffer_reuse_decision_20260621.json"
DEFAULT_FINAL_LOGITS_LEVERAGE = DEFAULT_ROOT / "dream7b_b4_final_logits_leverage_model_20260621.json"
DEFAULT_RUNTIME_PROBE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_backlog_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_backlog_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def line_of(lines: list[str], needle: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if needle in line:
            return index
    return None


def source_anchors(path: Path) -> dict[str, dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    anchors = {
        "final_logits_path_selection": "def hbm_path(",
        "final_logits_shape_gate": "def final_logits_seq_len(",
        "segment_major_loop": "def run_group_segment_major(",
        "runtime_run_call": "out = runtime.run(inputs, model_name=name)",
        "hidden_materialize": "def materialize_hidden(",
        "prewarm_hbm": "def prewarm_hbm_files(",
        "group_load": "def load_group(",
        "release_gc": "if args.release_gc_mode == \"collect\":",
        "payload_loaded_segments": "\"loaded_segments\": loaded_segment_summary(loaded),",
        "final_logits_arg": "parser.add_argument(\"--final-logits-mode\"",
    }
    return {
        name: {
            "file": str(path),
            "line": line_of(lines, needle),
            "needle": needle,
        }
        for name, needle in anchors.items()
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    scheduler = read_json(args.scheduler_json)
    group_switch = read_json(args.group_switch_json)
    last_token_gate = read_json(args.last_token_gate_json)
    nas_inventory = read_json(args.nas_inventory_json)
    post_overhead = read_json(args.post_instrumentation_overhead_json)
    hidden_buffer_decision_payload = read_json(args.hidden_buffer_decision_json)
    final_logits_leverage = read_json(args.final_logits_leverage_json)
    anchors = source_anchors(args.runtime_probe)
    ratios = scheduler.get("ratios") or {}
    budget_rows = {row.get("name"): row for row in scheduler.get("budget_rows") or []}
    decision = scheduler.get("decision") or {}
    group_decision = group_switch.get("decision") or {}
    inventory_decision = nas_inventory.get("decision") or {}
    last_token_decision = last_token_gate.get("decision") or {}
    post_totals = post_overhead.get("totals") or {}
    post_decision = post_overhead.get("decision") or {}
    hidden_buffer_decision = hidden_buffer_decision_payload.get("decision") or {}
    prealloc_delta = hidden_buffer_decision_payload.get("latest_prealloc_ab_delta") or {}
    final_leverage = final_logits_leverage.get("leverage") or {}
    final_bpu_gap = final_logits_leverage.get("bpu_promotion_gap") or {}
    final_leverage_decision = final_logits_leverage.get("decision") or {}
    final_validation_thresholds = final_logits_leverage.get("validation_thresholds") or {}
    last_token_blockers = last_token_decision.get("gate_blockers") or []

    backlog = [
        {
            "rank": 1,
            "id": "final_logits_last_token_path",
            "status": "blocked_by_compile_manifest",
            "source_anchors": [
                anchors["final_logits_path_selection"],
                anchors["final_logits_shape_gate"],
                anchors["final_logits_arg"],
            ],
            "expected_ceiling_ms_per_request": (budget_rows.get("final_logits_active_excess") or {}).get(
                "ms_per_request"
            ),
            "projected_saved_ms_per_request": final_leverage.get(
                "projection_saved_ms_per_request"
            ),
            "projected_latency_reduction_pct": final_leverage.get(
                "latest_projected_latency_reduction_pct"
            ),
            "evidence": {
                "final_excess_to_group_switch_gap": ratios.get("final_excess_to_group_switch_gap"),
                "final_excess_to_intra_segment_gap": ratios.get("final_excess_to_intra_segment_gap"),
                "final_logits_leverage_verdict": final_logits_leverage.get("verdict"),
                "projection_capture_of_final_excess_pct": final_leverage.get(
                    "projection_capture_of_final_excess_pct"
                ),
                "projection_is_not_bpu_promotion_proof": final_leverage_decision.get(
                    "projection_is_not_bpu_promotion_proof"
                ),
                "do_not_promote_without_runtime_result": final_leverage_decision.get(
                    "do_not_promote_without_runtime_result"
                ),
                "do_not_run_standard_group_or_inner_order_sweeps": final_leverage_decision.get(
                    "do_not_run_standard_group_or_inner_order_sweeps"
                ),
                "latest_nonzero_shortfall_points": final_bpu_gap.get(
                    "latest_nonzero_shortfall_points"
                ),
                "last_token_gate_verdict": last_token_gate.get("verdict"),
                "last_token_gate_blockers": last_token_blockers,
            },
            "next_action": "Do not change scheduling defaults; compile/verify seg27_28 last-token HBM first, then run the existing mb512 validation path.",
            "acceptance": [
                "remote last-token manifest verifies",
                "candidate telemetry exists at b4_mb512_segment_major_last_token_true_batch_group_major_telemetry.json",
                "dream7b_b4_last_token_validation_compare.py reports structural_ok and performance_ok",
                f"wall improvement is at least {final_validation_thresholds.get('min_wall_improvement_ms_per_request')} ms/request",
                f"final-run improvement is at least {final_validation_thresholds.get('min_final_run_improvement_ms_per_request')} ms/request",
                f"nonzero BPU regression is no more than {final_validation_thresholds.get('max_nonzero_bpu_regression_points')} points",
            ],
        },
        {
            "rank": 2,
            "id": "alternative_hidden_materialize_avoidance",
            "status": "research_only_current_preallocate_hidden_rejected",
            "source_anchors": [
                anchors["hidden_materialize"],
                anchors["segment_major_loop"],
            ],
            "expected_ceiling_ms_per_request": post_totals.get(
                "hidden_materialize_ms_per_request",
                (budget_rows.get("hidden_materialize") or {}).get("ms_per_request"),
            ),
            "evidence": {
                "post_instrumentation_overhead_verdict": post_overhead.get("verdict"),
                "hidden_materialize_has_measured_ceiling": hidden_buffer_decision.get(
                    "hidden_materialize_has_measured_ceiling"
                ),
                "hidden_materialize_ms_per_request": post_totals.get(
                    "hidden_materialize_ms_per_request"
                ),
                "final_excess_ms_per_request_vs_hidden": post_totals.get(
                    "final_excess_ms_per_request_vs_hidden"
                ),
                "preallocate_hidden_experimental_flag_only": hidden_buffer_decision.get(
                    "preallocate_hidden_experimental_flag_only"
                ),
                "reuse_buffer_implementation_measured_slower": hidden_buffer_decision.get(
                    "reuse_buffer_implementation_measured_slower"
                ),
                "preallocate_hidden_ms_per_request_delta": prealloc_delta.get(
                    "ms_per_request_delta"
                ),
                "preallocate_hidden_materialize_delta": prealloc_delta.get(
                    "hidden_materialize_ms_per_request_delta"
                ),
                "secondary_research_target": hidden_buffer_decision.get(
                    "secondary_research_target"
                ),
            },
            "next_action": "Do not promote the current preallocate-hidden path; only investigate a different hidden-materialize avoidance design that avoids preallocated copyto overhead.",
            "acceptance": [
                "no default behavior change and --preallocate-hidden stays experimental",
                "new candidate is not the measured-slower preallocated copyto implementation",
                "report keeps reused_hidden_buffer_count and hidden_materialize_ms_per_item",
                "mb512 A/B must beat baseline before any promotion",
            ],
        },
        {
            "rank": 3,
            "id": "segment_loop_bookkeeping",
            "status": "defer_until_final_logits_path_changes",
            "source_anchors": [
                anchors["segment_major_loop"],
                anchors["runtime_run_call"],
            ],
            "expected_ceiling_ms_per_request": (
                budget_rows.get("segment_overhead_excluding_hidden_materialize") or {}
            ).get("ms_per_request"),
            "evidence": {
                "gap_residual_ms_per_request": (
                    budget_rows.get("gap_instrumented_residual_after_measured_gaps") or {}
                ).get("ms_per_request"),
                "final_excess_to_gap_residual": ratios.get("final_excess_to_gap_residual"),
            },
            "next_action": "Avoid broad loop rewrites while final logits remains dominant; only make small readability-safe instrumentation changes.",
            "acceptance": [
                "segment_rows still include completed_microbatch_count",
                "inter_segment_first_run_gap_ms and intra_segment_run_gap_ms remain present",
            ],
        },
        {
            "rank": 4,
            "id": "group_switch_release_gc",
            "status": "deprioritized",
            "source_anchors": [
                anchors["group_load"],
                anchors["release_gc"],
                anchors["payload_loaded_segments"],
            ],
            "expected_ceiling_ms_per_request": (budget_rows.get("group_switch_gap") or {}).get(
                "ms_per_request"
            ),
            "evidence": {
                "group_release_and_unaccounted_gap_not_primary": group_decision.get(
                    "group_release_and_unaccounted_gap_not_primary"
                ),
                "final_excess_to_group_switch_gap": ratios.get("final_excess_to_group_switch_gap"),
            },
            "next_action": "Keep release_gc skip and more group-boundary partitions as profiling-only unless memory residency changes.",
            "acceptance": [
                "run_more_standard_b4_runtime_sweeps_now remains false",
                "queue-batch remains production default",
            ],
        },
        {
            "rank": 5,
            "id": "hbm_prewarm_or_io_cache",
            "status": "blocked_by_negative_existing_evidence",
            "source_anchors": [
                anchors["prewarm_hbm"],
                anchors["group_load"],
            ],
            "expected_ceiling_ms_per_request": (budget_rows.get("group_hbm_load_amortization") or {}).get(
                "ms_per_request"
            ),
            "evidence": {
                "recommendation": (budget_rows.get("group_hbm_load_amortization") or {}).get(
                    "recommendation"
                ),
                "b4_history_is_already_mirrored_locally": inventory_decision.get(
                    "b4_history_is_already_mirrored_locally"
                ),
            },
            "next_action": "Do not add prewarm/cache as a default; revisit only if a memory plan keeps more groups resident.",
            "acceptance": [
                "prewarm_hbm_default remains false",
                "new cache behavior has an explicit off switch and a telemetry field",
            ],
        },
    ]

    ready_now = [
        item
        for item in backlog
        if item["status"]
        in {
            "research_only_current_preallocate_hidden_rejected",
            "defer_until_final_logits_path_changes",
        }
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_runtime_refactor_backlog",
        "scope": "source-anchored B=4 runtime scheduling backlog from existing telemetry only",
        "source_paths": {
            "scheduler": str(args.scheduler_json),
            "group_switch": str(args.group_switch_json),
            "last_token_gate": str(args.last_token_gate_json),
            "nas_inventory": str(args.nas_inventory_json),
            "post_instrumentation_overhead": str(args.post_instrumentation_overhead_json),
            "hidden_buffer_decision": str(args.hidden_buffer_decision_json),
            "final_logits_leverage": str(args.final_logits_leverage_json),
            "runtime_probe": str(args.runtime_probe),
        },
        "decision": {
            "primary_runtime_refactor_target": backlog[0]["id"],
            "secondary_research_target": hidden_buffer_decision.get(
                "secondary_research_target"
            ),
            "current_preallocate_hidden_rejected_by_evidence": hidden_buffer_decision.get(
                "reuse_buffer_implementation_measured_slower"
            ),
            "preallocate_hidden_experimental_flag_only": hidden_buffer_decision.get(
                "preallocate_hidden_experimental_flag_only"
            ),
            "rank1_projected_saved_ms_per_request": backlog[0].get(
                "projected_saved_ms_per_request"
            ),
            "rank1_projection_is_not_bpu_promotion_proof": (
                backlog[0].get("evidence") or {}
            ).get("projection_is_not_bpu_promotion_proof"),
            "rank1_blocks_standard_group_or_inner_order_sweeps": (
                backlog[0].get("evidence") or {}
            ).get("do_not_run_standard_group_or_inner_order_sweeps"),
            "ready_local_refactor_count": len(ready_now),
            "do_not_change_runtime_defaults_now": True,
            "do_not_start_s100p_runtime_now": True,
            "queue_batch_remains_default": True,
            "reason": "final-logits leverage is the only current material runtime refactor target, but it is latency evidence only until last-token runtime validation; current preallocate-hidden worsened mb512 A/B and remains experimental",
        },
        "backlog": backlog,
        "source_anchors": anchors,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B B4 Runtime Refactor Backlog",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- primary_runtime_refactor_target: `{payload['decision']['primary_runtime_refactor_target']}`",
        f"- secondary_research_target: `{payload['decision']['secondary_research_target']}`",
        f"- current_preallocate_hidden_rejected_by_evidence: `{payload['decision']['current_preallocate_hidden_rejected_by_evidence']}`",
        f"- preallocate_hidden_experimental_flag_only: `{payload['decision']['preallocate_hidden_experimental_flag_only']}`",
        f"- rank1_projected_saved_ms_per_request: `{payload['decision']['rank1_projected_saved_ms_per_request']}`",
        f"- rank1_projection_is_not_bpu_promotion_proof: `{payload['decision']['rank1_projection_is_not_bpu_promotion_proof']}`",
        f"- rank1_blocks_standard_group_or_inner_order_sweeps: `{payload['decision']['rank1_blocks_standard_group_or_inner_order_sweeps']}`",
        f"- do_not_change_runtime_defaults_now: `{payload['decision']['do_not_change_runtime_defaults_now']}`",
        f"- do_not_start_s100p_runtime_now: `{payload['decision']['do_not_start_s100p_runtime_now']}`",
        f"- reason: {payload['decision']['reason']}",
        "",
        "## Backlog",
        "",
        "| rank | id | status | ceiling ms/request | source lines | next action |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    for item in payload["backlog"]:
        lines_text = ", ".join(
            f"{Path(anchor['file']).name}:{anchor['line']}" for anchor in item["source_anchors"]
        )
        lines.append(
            f"| {item['rank']} | {item['id']} | {item['status']} | "
            f"{item.get('projected_saved_ms_per_request', item['expected_ceiling_ms_per_request'])} | {lines_text} | {item['next_action']} |"
        )
    lines.extend(["", "## Acceptance Gates", ""])
    for item in payload["backlog"]:
        lines.append(f"### {item['id']}")
        for gate in item["acceptance"]:
            lines.append(f"- {gate}")
        lines.append("")
    lines.extend(["## Source Paths", ""])
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a source-anchored Dream7B B=4 runtime refactor backlog from existing telemetry."
    )
    parser.add_argument("--scheduler-json", type=Path, default=DEFAULT_SCHEDULER)
    parser.add_argument("--group-switch-json", type=Path, default=DEFAULT_GROUP_SWITCH)
    parser.add_argument("--last-token-gate-json", type=Path, default=DEFAULT_LAST_TOKEN_GATE)
    parser.add_argument("--nas-inventory-json", type=Path, default=DEFAULT_NAS_INVENTORY)
    parser.add_argument(
        "--post-instrumentation-overhead-json",
        type=Path,
        default=DEFAULT_POST_INSTRUMENTATION_OVERHEAD,
    )
    parser.add_argument(
        "--hidden-buffer-decision-json",
        type=Path,
        default=DEFAULT_HIDDEN_BUFFER_DECISION,
    )
    parser.add_argument(
        "--final-logits-leverage-json",
        type=Path,
        default=DEFAULT_FINAL_LOGITS_LEVERAGE,
    )
    parser.add_argument("--runtime-probe", type=Path, default=DEFAULT_RUNTIME_PROBE)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_md)
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
