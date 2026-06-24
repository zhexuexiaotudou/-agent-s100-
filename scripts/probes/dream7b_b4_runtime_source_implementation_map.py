#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_runtime_source_implementation_map"
DEFAULT_ANALYSIS_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SOURCE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_SOURCE_CONTRACT = (
    DEFAULT_ANALYSIS_ROOT / "dream7b_b4_runtime_refactor_source_contract_20260621.json"
)
DEFAULT_SCORECARD = (
    DEFAULT_ANALYSIS_ROOT / "dream7b_b4_segment_group_schedule_scorecard_20260621.json"
)
DEFAULT_OUT_JSON = (
    DEFAULT_ANALYSIS_ROOT / "dream7b_b4_runtime_source_implementation_map_20260621.json"
)
DEFAULT_OUT_MD = (
    DEFAULT_ANALYSIS_ROOT / "dream7b_b4_runtime_source_implementation_map_20260621.md"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def line_number(lines: list[str], token: str) -> int | None:
    for lineno, line in enumerate(lines, start=1):
        if token in line:
            return lineno
    return None


def source_refs(lines: list[str], tokens: dict[str, str]) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for name, token in tokens.items():
        line = line_number(lines, token)
        refs[name] = {
            "token": token,
            "present": line is not None,
            "line": line,
        }
    return refs


def present_all(refs: dict[str, dict[str, Any]]) -> bool:
    return all(row.get("present") is True for row in refs.values())


def line_span(refs: dict[str, dict[str, Any]]) -> str | None:
    lines = [
        int(row["line"])
        for row in refs.values()
        if isinstance(row.get("line"), int)
    ]
    if not lines:
        return None
    if min(lines) == max(lines):
        return str(min(lines))
    return f"{min(lines)}-{max(lines)}"


def compact_refs(refs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_line_span": line_span(refs),
        "source_lines": {
            name: row.get("line")
            for name, row in refs.items()
            if row.get("line") is not None
        },
        "missing_source_tokens": [
            name for name, row in refs.items() if row.get("present") is not True
        ],
    }


def row(
    *,
    implementation_area: str,
    class_name: str,
    refs: dict[str, dict[str, Any]],
    current_default_safe: bool,
    allowed_now: bool,
    allowed_scope: str,
    runtime_or_compile_required: bool,
    duplicate_with_prior_runtime: bool,
    evidence: dict[str, Any],
    next_gate: str,
) -> dict[str, Any]:
    compact = compact_refs(refs)
    return {
        "implementation_area": implementation_area,
        "class": class_name,
        **compact,
        "source_contract_present": present_all(refs),
        "current_default_safe": current_default_safe,
        "allowed_now": allowed_now,
        "allowed_scope": allowed_scope,
        "runtime_or_compile_required": runtime_or_compile_required,
        "duplicate_with_prior_true_batch_runtime_work": duplicate_with_prior_runtime,
        "evidence": evidence,
        "next_gate": next_gate,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_text = args.source.read_text(encoding="utf-8")
    lines = source_text.splitlines()
    source_contract = read_json(args.source_contract_json)
    scorecard = read_json(args.scorecard_json)
    source_summary = source_contract.get("summary") or {}
    source_local = source_contract.get("local_refactor_contract") or {}
    source_audit = source_contract.get("audit") or {}
    score_summary = scorecard.get("summary") or {}
    score_decision = scorecard.get("decision") or {}
    score_checks = scorecard.get("checks") or {}
    score_audit = scorecard.get("audit") or {}
    score_rows = scorecard.get("scorecard_rows") or []

    source_ref_sets = {
        "final_logits_last_token_path": source_refs(
            lines,
            {
                "final_logits_suffix": 'return "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""',
                "final_logits_seq_len": 'return 1 if final_logits_mode == "last-token" else seq_len',
                "hbm_path_final_root": "base = final_root if index == 27 and final_root is not None else root",
                "model_name_suffix": "suffix = final_logits_suffix(final_logits_mode, index)",
                "final_hbm_root_arg": 'parser.add_argument("--final-hbm-root", default=""',
                "final_logits_mode_arg": 'parser.add_argument("--final-logits-mode", choices=["full", "last-token"], default="full")',
                "expected_final_shape": "expected_final_shape = [args.batch_size, final_logits_seq_len(args.seq_len, args.final_logits_mode), args.vocab_size]",
            },
        ),
        "group_major_scheduling_loop": source_refs(
            lines,
            {
                "group_loop_start": "group_loop_start = time.perf_counter()",
                "load_group_call": "loaded = load_group(",
                "inner_order_branch": 'if args.inner_order == "microbatch-major":',
                "segment_major_call": "group_final_shape, segment_rows, segment_errors = run_group_segment_major(",
                "release_gc_mode_arg": 'parser.add_argument("--release-gc-mode", choices=["collect", "skip"], default="collect")',
                "gc_collect": "gc.collect()",
                "group_loop_ms": 'group_rows[-1]["group_loop_ms"] = round(group_loop_ms, 3)',
            },
        ),
        "segment_gap_and_loaded_segments_telemetry": source_refs(
            lines,
            {
                "loaded_segments": '"loaded_segments": loaded_segment_summary(loaded),',
                "inter_segment_gap_summary": '"total_inter_segment_first_run_gap_ms"',
                "intra_segment_gap_summary": '"total_intra_segment_run_gap_ms"',
                "inter_segment_gap_row": '"inter_segment_first_run_gap_ms":',
                "intra_segment_gap_row": '"intra_segment_run_gap_ms":',
                "avg_input_prepare": '"avg_input_prepare_ms":',
                "avg_output_postprocess": '"avg_output_postprocess_ms":',
                "group_loop_ms": '"group_loop_ms"',
            },
        ),
        "hidden_materialize_path": source_refs(
            lines,
            {
                "materialize_hidden_def": "def materialize_hidden(",
                "copyto_reusable": "np.copyto(reusable, arr, casting=\"unsafe\")",
                "multiply_reusable": "np.multiply(arr, float(scale), out=reusable, casting=\"unsafe\")",
                "preallocate_hidden_arg": 'parser.add_argument("--preallocate-hidden", action="store_true")',
                "hidden_buffers_alloc": "hidden_buffers = [",
                "hidden_materialize_ms": '"hidden_materialize_ms": round(sum(materialize_times), 3),',
            },
        ),
        "hbm_prewarm_and_io_cache": source_refs(
            lines,
            {
                "prewarm_hbm_files_def": "def prewarm_hbm_files(paths: list[Path], chunk_bytes: int) -> dict[str, Any]:",
                "prewarm_hbm_arg": 'parser.add_argument("--prewarm-hbm", action="store_true"',
                "prewarm_chunk_arg": 'parser.add_argument("--prewarm-chunk-mib", type=int, default=32)',
                "prewarm_call": "prewarm_row = prewarm_hbm_files(",
                "group_hbm_paths_call": "group_hbm_paths(",
                "total_hbm_prewarm_ms": '"total_hbm_prewarm_ms"',
            },
        ),
        "release_gc_and_group_switch_accounting": source_refs(
            lines,
            {
                "release_gc_mode_arg": 'parser.add_argument("--release-gc-mode", choices=["collect", "skip"], default="collect")',
                "release_start": "release_start = time.perf_counter()",
                "gc_collect": "gc.collect()",
                "group_release_ms": 'group_rows[-1]["group_release_ms"] = round(group_release_ms, 3)',
                "release_gc_mode_reported": 'group_rows[-1]["release_gc_mode"] = args.release_gc_mode',
                "group_loop_ms": 'group_rows[-1]["group_loop_ms"] = round(group_loop_ms, 3)',
            },
        ),
    }

    top_scorecard = score_rows[0] if score_rows else {}
    implementation_rows = [
        row(
            implementation_area="seg27_28_last_token_logits_or_output_avoidance",
            class_name="future_runtime_candidate",
            refs=source_ref_sets["final_logits_last_token_path"],
            current_default_safe=bool(source_summary.get("cli_defaults_preserved"))
            and source_summary.get("default_promotes_experimental_flags") is False,
            allowed_now=False,
            allowed_scope="blocked_until_last_token_hbm_manifest_and_runtime_validation",
            runtime_or_compile_required=True,
            duplicate_with_prior_runtime=False,
            evidence={
                "primary_schedule_bottleneck": score_decision.get(
                    "primary_schedule_bottleneck"
                ),
                "projected_saved_ms_per_request": score_summary.get(
                    "primary_code_target_projected_saved_ms_per_request"
                ),
                "final_excess_to_group_switch_gap_ratio": score_summary.get(
                    "final_excess_to_group_switch_gap_ratio"
                ),
                "top_scorecard_status": top_scorecard.get("status"),
                "compile_start_allowed_now": score_decision.get("start_compile_now"),
                "s100p_runtime_allowed_now": score_decision.get("run_s100p_runtime_now"),
            },
            next_gate="compile preflight only, then last-token HBM manifest, then S100P runtime validation",
        ),
        row(
            implementation_area="group_major_scheduling_loop",
            class_name="scheduler_policy",
            refs=source_ref_sets["group_major_scheduling_loop"],
            current_default_safe=bool(source_summary.get("cli_defaults_preserved")),
            allowed_now=False,
            allowed_scope="do_not_change_default_order_or_group_policy_now",
            runtime_or_compile_required=True,
            duplicate_with_prior_runtime=True,
            evidence={
                "preferred_group_policy": score_decision.get("preferred_group_policy"),
                "preferred_inner_order": score_decision.get("preferred_inner_order"),
                "observed_nonbaseline_group_or_order_count": score_summary.get(
                    "observed_nonbaseline_group_or_order_count"
                ),
                "best_nonbaseline_group_delta_ms_per_request": score_summary.get(
                    "best_nonbaseline_group_delta_ms_per_request"
                ),
                "run_more_standard_sweeps_now": score_decision.get(
                    "run_more_standard_b4_group_or_inner_order_sweeps_now"
                ),
            },
            next_gate="only revisit after final logits path changes the active profile",
        ),
        row(
            implementation_area="segment_gap_and_loaded_segments_telemetry",
            class_name="telemetry_contract",
            refs=source_ref_sets["segment_gap_and_loaded_segments_telemetry"],
            current_default_safe=True,
            allowed_now=True,
            allowed_scope="local_report_only_analysis_and_packet_checks",
            runtime_or_compile_required=False,
            duplicate_with_prior_runtime=False,
            evidence={
                "protected_telemetry_fields_ready": source_summary.get(
                    "protected_telemetry_fields_ready"
                ),
                "protected_telemetry_field_count": source_summary.get(
                    "protected_telemetry_field_count"
                ),
                "group_switch_gap_ms_per_request": score_summary.get(
                    "group_switch_gap_ms_per_request"
                ),
                "group_switch_not_primary": score_checks.get("group_switch_not_primary"),
            },
            next_gate="keep these fields stable for every later runtime experiment",
        ),
        row(
            implementation_area="alternative_hidden_materialize_avoidance",
            class_name="local_design_only",
            refs=source_ref_sets["hidden_materialize_path"],
            current_default_safe=bool(source_summary.get("cli_defaults_preserved")),
            allowed_now=bool(
                source_local.get("hidden_materialize_can_be_measured_before_any_promotion")
            ),
            allowed_scope="design_notes_only_no_default_runtime_change",
            runtime_or_compile_required=True,
            duplicate_with_prior_runtime=False,
            evidence={
                "current_preallocate_path_explicit": source_local.get(
                    "preallocate_hidden_must_remain_explicit"
                ),
                "scorecard_status": "design_only_allowed_current_preallocate_path_rejected",
                "estimated_ceiling_ms_per_request": next(
                    (
                        item.get("estimated_saved_ms_per_request")
                        for item in score_rows
                        if item.get("target") == "hidden_materialize_alternative_design"
                    ),
                    None,
                ),
            },
            next_gate="new design sketch first; no promotion until measured faster than current explicit flag",
        ),
        row(
            implementation_area="hbm_prewarm_or_io_cache",
            class_name="blocked_default_cache_change",
            refs=source_ref_sets["hbm_prewarm_and_io_cache"],
            current_default_safe=bool(source_summary.get("cli_defaults_preserved")),
            allowed_now=False,
            allowed_scope="keep_explicit_flag_off_by_default",
            runtime_or_compile_required=True,
            duplicate_with_prior_runtime=True,
            evidence={
                "prewarm_hbm_must_remain_explicit": source_local.get(
                    "prewarm_hbm_must_remain_explicit"
                ),
                "run_new_group_partition_now": score_decision.get(
                    "run_new_group_partition_now"
                ),
                "capacity_probe_only_candidate_count": score_summary.get(
                    "capacity_probe_only_candidate_count"
                ),
            },
            next_gate="memory residency plan must change before cache/prewarm default work",
        ),
        row(
            implementation_area="release_gc_and_group_switch_accounting",
            class_name="low_value_scheduler_gap",
            refs=source_ref_sets["release_gc_and_group_switch_accounting"],
            current_default_safe=bool(source_summary.get("cli_defaults_preserved")),
            allowed_now=False,
            allowed_scope="no_release_gc_default_change_now",
            runtime_or_compile_required=True,
            duplicate_with_prior_runtime=True,
            evidence={
                "group_switch_gap_ms_per_request": score_summary.get(
                    "group_switch_gap_ms_per_request"
                ),
                "final_excess_to_group_switch_gap_ratio": score_summary.get(
                    "final_excess_to_group_switch_gap_ratio"
                ),
                "group_switch_not_primary": score_checks.get("group_switch_not_primary"),
            },
            next_gate="defer until the final-logits outlier is removed or proven irrelevant",
        ),
    ]

    all_source_refs = {
        f"{area}.{name}": row
        for area, refs in source_ref_sets.items()
        for name, row in refs.items()
    }
    missing_source_patterns = [
        name for name, ref in all_source_refs.items() if ref.get("present") is not True
    ]
    checks = {
        "source_contract_ok": source_contract.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_source_contract",
        "scorecard_ok": scorecard.get("verdict")
        == "ok_dream7b_b4_segment_group_schedule_scorecard",
        "all_required_source_patterns_present": not missing_source_patterns,
        "defaults_preserved": source_summary.get("cli_defaults_preserved") is True
        and source_summary.get("runtime_order_changed") is False
        and source_summary.get("default_promotes_experimental_flags") is False,
        "queue_batch_remains_default": score_decision.get("production_default")
        == "queue_batch",
        "standard_group_inner_order_sweeps_blocked": score_decision.get(
            "run_more_standard_b4_group_or_inner_order_sweeps_now"
        )
        is False,
        "runtime_compile_not_started": source_audit.get("runtime_started") is False
        and source_audit.get("compile_started") is False
        and score_audit.get("runtime_started") is False
        and score_audit.get("compile_started") is False,
        "remote_access_not_performed": score_audit.get("remote_access_performed") is False,
    }
    failed_checks = [name for name, value in checks.items() if value is not True]
    verdict = (
        "ok_dream7b_b4_runtime_source_implementation_map"
        if not failed_checks
        else "failed_dream7b_b4_runtime_source_implementation_map"
    )
    allowed_now = [
        item["implementation_area"]
        for item in implementation_rows
        if item.get("allowed_now") is True
    ]
    duplicate_or_blocked = [
        item["implementation_area"]
        for item in implementation_rows
        if item.get("duplicate_with_prior_true_batch_runtime_work") is True
        or item.get("allowed_now") is False
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_paths": {
            "runtime_source": str(args.source),
            "runtime_refactor_source_contract": str(args.source_contract_json),
            "segment_group_schedule_scorecard": str(args.scorecard_json),
        },
        "summary": {
            "implementation_area_count": len(implementation_rows),
            "source_pattern_count": len(all_source_refs),
            "missing_source_pattern_count": len(missing_source_patterns),
            "queue_batch_remains_default": checks["queue_batch_remains_default"],
            "primary_runtime_refactor_target": score_decision.get(
                "primary_code_target"
            ),
            "primary_schedule_bottleneck": score_decision.get(
                "primary_schedule_bottleneck"
            ),
            "preferred_group_policy": score_decision.get("preferred_group_policy"),
            "preferred_inner_order": score_decision.get("preferred_inner_order"),
            "allowed_now_count": len(allowed_now),
            "allowed_now": allowed_now,
            "duplicate_or_blocked_area_count": len(duplicate_or_blocked),
            "s100p_runtime_experiment_allowed_now": False,
            "compile_start_allowed_now": False,
            "compile_preflight_only_now": score_decision.get(
                "compile_preflight_only_now"
            ),
            "runtime_default_change_allowed_now": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
            "service_restarted": False,
        },
        "implementation_rows": implementation_rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "missing_source_patterns": missing_source_patterns,
        "audit": {
            "source_modified": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown runtime source implementation map only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B B=4 Runtime Source Implementation Map",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- runtime_source: `{payload['source_paths']['runtime_source']}`",
        f"- primary_schedule_bottleneck: `{summary['primary_schedule_bottleneck']}`",
        f"- primary_runtime_refactor_target: `{summary['primary_runtime_refactor_target']}`",
        f"- queue_batch_remains_default: `{summary['queue_batch_remains_default']}`",
        f"- preferred_group_policy: `{summary['preferred_group_policy']}`",
        f"- preferred_inner_order: `{summary['preferred_inner_order']}`",
        f"- source_pattern_count: `{summary['source_pattern_count']}`",
        f"- missing_source_pattern_count: `{summary['missing_source_pattern_count']}`",
        f"- allowed_now: `{summary['allowed_now']}`",
        f"- s100p_runtime_experiment_allowed_now: `{summary['s100p_runtime_experiment_allowed_now']}`",
        f"- compile_start_allowed_now: `{summary['compile_start_allowed_now']}`",
        f"- compile_preflight_only_now: `{summary['compile_preflight_only_now']}`",
        f"- runtime_default_change_allowed_now: `{summary['runtime_default_change_allowed_now']}`",
        "",
        "## Implementation Rows",
        "",
    ]
    for item in payload["implementation_rows"]:
        lines.extend(
            [
                f"### {item['implementation_area']}",
                "",
                f"- class: `{item['class']}`",
                f"- source_line_span: `{item['source_line_span']}`",
                f"- source_contract_present: `{item['source_contract_present']}`",
                f"- current_default_safe: `{item['current_default_safe']}`",
                f"- allowed_now: `{item['allowed_now']}`",
                f"- allowed_scope: `{item['allowed_scope']}`",
                f"- runtime_or_compile_required: `{item['runtime_or_compile_required']}`",
                f"- duplicate_with_prior_true_batch_runtime_work: `{item['duplicate_with_prior_true_batch_runtime_work']}`",
                f"- next_gate: `{item['next_gate']}`",
                f"- missing_source_tokens: `{item['missing_source_tokens']}`",
                "",
            ]
        )
    lines.extend(["## Checks", ""])
    lines.extend(f"- {name}: `{value}`" for name, value in payload["checks"].items())
    if payload["failed_checks"]:
        lines.extend(["", "## Failed Checks", ""])
        lines.extend(f"- {item}" for item in payload["failed_checks"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map Dream7B B=4 runtime optimization candidates to source lines and safe action boundaries."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--source-contract-json", type=Path, default=DEFAULT_SOURCE_CONTRACT
    )
    parser.add_argument("--scorecard-json", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()
    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
