#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_next_action_admission_pack_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_next_action_admission_pack_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_json(root: Path, pattern: str) -> Path | None:
    paths = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime)
    return paths[-1] if paths else None


def latest_product_packet(snapshot_root: Path) -> Path | None:
    return latest_json(snapshot_root, "dream7b_product_decision_packet_*/dream7b_product_decision_packet.json")


def latest_freshness(snapshot_root: Path) -> Path:
    return snapshot_root / "dream7b_default_service_freshness_gate_latest.json"


def bool_get(payload: dict[str, Any], *path: str) -> bool:
    cursor: Any = payload
    for key in path:
        if not isinstance(cursor, dict):
            return False
        cursor = cursor.get(key)
    return cursor is True


def command_status(
    *,
    action_id: str,
    label: str,
    status: str,
    reason: str,
    evidence: list[str],
    blockers: list[str] | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "status": status,
        "reason": reason,
        "blockers": blockers or [],
        "command": command,
        "evidence": evidence,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    inventory_path = args.analysis_root / "dream7b_true_batch_nas_inventory_20260620.json"
    runtime_gate_path = args.analysis_root / "dream7b_b4_runtime_experiment_gate_20260620.json"
    runtime_guard_path = args.analysis_root / "dream7b_b4_runtime_command_guard_20260621.json"
    compile_guard_path = args.analysis_root / "dream7b_b4_compile_command_guard_20260621.json"
    compile_guard_preflight_path = (
        args.analysis_root / "dream7b_b4_compile_command_guard_preflight_probe_tmp.json"
    )
    compile_readiness_path = args.analysis_root / "dream7b_b4_last_token_compile_readiness_20260619.json"
    compile_capacity_path = args.analysis_root / "dream7b_b4_compile_capacity_plan_20260619.json"
    tuning_path = args.analysis_root / "dream7b_b4_tuning_decision_matrix_20260621.json"
    refactor_path = args.analysis_root / "dream7b_b4_runtime_refactor_backlog_20260621.json"
    leverage_path = args.analysis_root / "dream7b_b4_final_logits_leverage_model_20260621.json"
    per_run_evidence_matrix_path = (
        args.analysis_root / "dream7b_b4_per_run_evidence_matrix_20260622.json"
    )
    product_path = latest_product_packet(args.snapshot_root)
    freshness_path = latest_freshness(args.snapshot_root)

    inventory = read_json(inventory_path)
    runtime_gate = read_json(runtime_gate_path)
    runtime_guard = read_json(runtime_guard_path)
    compile_guard = read_json(compile_guard_path)
    compile_guard_preflight = read_json(compile_guard_preflight_path)
    compile_readiness = read_json(compile_readiness_path)
    compile_capacity = read_json(compile_capacity_path)
    tuning = read_json(tuning_path)
    refactor = read_json(refactor_path)
    leverage = read_json(leverage_path)
    per_run_evidence_matrix = read_json(per_run_evidence_matrix_path)
    product = read_json(product_path) if product_path else {}
    freshness = read_json(freshness_path) if freshness_path.exists() else {}

    inventory_decision = inventory.get("decision") or {}
    runtime_decision = runtime_gate.get("decision") or {}
    runtime_last_token = runtime_gate.get("last_token_candidate") or {}
    runtime_guard_decision = runtime_guard.get("guard") or {}
    compile_guard_decision = compile_guard.get("guard") or {}
    compile_preflight_guard = compile_guard_preflight.get("guard") or {}
    compile_preflight_classification = compile_guard_preflight.get("classification") or {}
    capacity_recommendation = compile_capacity.get("recommendation") or {}
    tuning_decision = tuning.get("decision") or {}
    refactor_decision = refactor.get("decision") or {}
    leverage_decision = leverage.get("decision") or {}
    per_run_summary = per_run_evidence_matrix.get("summary") or {}
    per_run_findings = per_run_evidence_matrix.get("findings") or {}
    per_run_admission = per_run_findings.get("admission") or {}
    per_run_audit = per_run_evidence_matrix.get("audit") or {}
    product_decision = product.get("decision") or {}
    product_queue_health = product.get("queue_health_snapshot") or {}
    per_run_matrix_gate_ready = (
        per_run_evidence_matrix.get("verdict") == "ok_dream7b_b4_per_run_evidence_matrix"
        and not (per_run_evidence_matrix.get("failed_checks") or [])
        and int(per_run_summary.get("run_count") or 0) >= 20
        and int(per_run_summary.get("successful_run_count") or 0) >= 19
        and int(per_run_summary.get("failed_run_count") or 0) >= 1
        and per_run_summary.get("most_common_top_segment") == "seg27_final_logits"
        and float(per_run_summary.get("most_common_top_segment_rate") or 0.0) == 1.0
        and per_run_summary.get("standard_b4_runtime_sweep_status")
        == "blocked_duplicate"
        and per_run_summary.get("run_more_standard_group_or_inner_order_sweeps_now")
        is False
        and per_run_admission.get("would_start_runtime") is False
        and per_run_admission.get("would_start_compile") is False
        and per_run_audit.get("remote_access_performed") is False
        and per_run_audit.get("runtime_started") is False
        and per_run_audit.get("compile_started") is False
    )

    safe_compile_preflight_command = (
        "powershell.exe -NoProfile -File scripts\\probes\\Compile-DreamTrueBatchSegments.ps1 "
        "-Segments 27:28 -BatchSize 4 -SeqLen 16 -FinalLogitsMode last-token -PreflightOnly"
    )
    actions = [
        command_status(
            action_id="standard_b4_runtime_sweep",
            label="Run another standard B=4 true-batch runtime sweep",
            status="blocked_duplicate",
            reason="B=4 standard schedule, inner-order, and group-boundary evidence already exists locally and on NAS.",
            blockers=[
                "standard_b4_sweeps_already_covered_by_nas_and_local_inventory",
                "runtime_command_guard_blocks_standard_sweeps",
            ],
            evidence=[
                f"remote_b4_group_major_report_count={((inventory.get('remote') or {}).get('b4_group_major_report_count'))}",
                f"local_b4_json_count={((inventory.get('local_coverage') or {}).get('local_b4_json_count'))}",
                f"run_more_standard_b4_runtime_sweeps_now={inventory_decision.get('run_more_standard_b4_runtime_sweeps_now')}",
                f"standard_sweep_commands_blocked={runtime_guard_decision.get('standard_sweep_commands_blocked')}",
                f"per_run_matrix_verdict={per_run_evidence_matrix.get('verdict')}",
                f"per_run_matrix_run_count={per_run_summary.get('run_count')}",
                f"per_run_matrix_top_segment={per_run_summary.get('most_common_top_segment')}",
                f"per_run_matrix_standard_sweep_status={per_run_summary.get('standard_b4_runtime_sweep_status')}",
            ],
        ),
        command_status(
            action_id="last_token_runtime_validation",
            label="Run mb512 last-token runtime validation",
            status="blocked_waiting_for_manifest",
            reason="The nonduplicate runtime candidate is correct, but it needs a verified remote last-token HBM manifest first.",
            blockers=runtime_gate.get("blockers") or [],
            evidence=[
                f"next_nonduplicate_runtime_candidate={runtime_decision.get('next_nonduplicate_runtime_candidate')}",
                f"run_last_token_mb512_validation_now={runtime_decision.get('run_last_token_mb512_validation_now')}",
                f"last_token_manifest_ready={runtime_last_token.get('manifest_ready')}",
                f"runtime_gate_allows_experiments={runtime_guard_decision.get('runtime_gate_allows_experiments')}",
            ],
        ),
        command_status(
            action_id="last_token_compile_start",
            label="Start B=4 seg27_28 last-token compile",
            status="blocked_waiting_for_local_capacity",
            reason="The compile shape is the only allowed shape, but current Windows readiness and commit capacity still block starting it.",
            blockers=[
                "compile_readiness_not_ready",
                "compile_capacity_plan_blocks_compile",
            ],
            evidence=[
                f"compile_ready={compile_readiness.get('compile_ready')}",
                f"do_not_start_compile_now={capacity_recommendation.get('do_not_start_compile_now')}",
                f"commit_headroom_gb={(compile_readiness.get('preflight') or {}).get('values', {}).get('commit_headroom_gb')}",
                f"required_commit_headroom_gb={(compile_capacity.get('compile_guard') or {}).get('required_commit_headroom_gb')}",
                f"command_admitted={compile_guard_decision.get('command_admitted')}",
                f"would_start_compile={compile_guard_decision.get('would_start_compile')}",
            ],
        ),
        command_status(
            action_id="last_token_compile_preflight",
            label="Run B=4 seg27_28 last-token compile preflight only",
            status="admitted_preflight_only",
            reason="The preflight-only shape is accepted by the command guard and does not start compilation.",
            command=safe_compile_preflight_command,
            evidence=[
                f"matches_allowed_shape={compile_preflight_classification.get('matches_allowed_single_segment_last_token_shape')}",
                f"preflight_admitted={compile_preflight_guard.get('preflight_admitted')}",
                f"would_start_compile={compile_preflight_guard.get('would_start_compile')}",
            ],
        ),
        command_status(
            action_id="b8_full_compile",
            label="Start B=8 or full-final-logits compile",
            status="blocked_policy",
            reason="Current policy and command guard reject B=8 or full-final-logits compile on this machine.",
            blockers=["b8_or_larger_compile_blocked", "full_final_logits_compile_blocked"],
            evidence=[
                f"b8_full_compile_blocked={compile_guard_decision.get('b8_full_compile_blocked')}",
                f"only_single_segment_last_token_compile_allowed={compile_guard_decision.get('only_single_segment_last_token_compile_allowed')}",
            ],
        ),
        command_status(
            action_id="queue_batch_product_evidence",
            label="Continue queue-batch product evidence and Portal/SLO guardrails",
            status="allowed_now",
            reason="This workstream does not duplicate prior true-batch rental work and keeps the production default stable.",
            evidence=[
                f"product_verdict={product.get('verdict')}",
                f"freshness_verdict={freshness.get('verdict')}",
                f"freshness_failed_checks={freshness.get('failed_checks')}",
                f"production_default={product_decision.get('production_default')}",
                f"queue_should_remain_default={product_decision.get('queue_should_remain_default')}",
                f"queue_health_no_true_batch_or_compile_process={product_queue_health.get('no_true_batch_or_compile_process')}",
            ],
        ),
        command_status(
            action_id="local_runtime_refactor_analysis",
            label="Continue local runtime refactor analysis around final logits and hidden materialization",
            status="allowed_now",
            reason="The rank-1 target is local-analysis/code-review friendly and does not require starting S100P runtime.",
            evidence=[
                f"primary_runtime_refactor_target={refactor_decision.get('primary_runtime_refactor_target')}",
                f"secondary_research_target={refactor_decision.get('secondary_research_target')}",
                f"rank1_projected_saved_ms_per_request={refactor_decision.get('rank1_projected_saved_ms_per_request')}",
                f"projection_is_not_bpu_promotion_proof={leverage_decision.get('projection_is_not_bpu_promotion_proof')}",
                f"do_not_start_s100p_runtime_now={refactor_decision.get('do_not_start_s100p_runtime_now')}",
            ],
        ),
    ]

    allowed_now = [item for item in actions if item["status"] == "allowed_now"]
    preflight_only = [item for item in actions if item["status"] == "admitted_preflight_only"]
    blocked = [item for item in actions if item["status"].startswith("blocked_")]
    checks = {
        "product_queue_batch_default_ok": product.get("verdict")
        == "ok_dream7b_product_decision_packet"
        and product_decision.get("production_default") == "queue_batch"
        and product_decision.get("queue_should_remain_default") is True,
        "freshness_ok": freshness.get("verdict") == "ok_dream7b_default_service_freshness_gate"
        and not freshness.get("failed_checks"),
        "runtime_guard_starts_no_runtime": runtime_guard_decision.get("command_admitted") is False
        and runtime_guard_decision.get("would_start_runtime") is False,
        "compile_guard_starts_no_compile": compile_guard_decision.get("command_admitted") is False
        and compile_guard_decision.get("would_start_compile") is False,
        "preflight_only_does_not_start_compile": compile_preflight_guard.get("preflight_admitted")
        is True
        and compile_preflight_guard.get("would_start_compile") is False,
        "standard_sweeps_blocked_as_duplicates": inventory_decision.get(
            "run_more_standard_b4_runtime_sweeps_now"
        )
        is False
        and runtime_guard_decision.get("standard_sweep_commands_blocked") is True,
        "per_run_matrix_blocks_standard_sweeps": per_run_matrix_gate_ready,
        "last_token_runtime_waits_for_manifest": runtime_decision.get(
            "run_last_token_mb512_validation_now"
        )
        is False
        and runtime_last_token.get("manifest_ready") is False,
        "compile_start_waits_for_capacity": compile_readiness.get("compile_ready") is False
        and capacity_recommendation.get("do_not_start_compile_now") is True,
        "tuning_keeps_group_order_default": tuning_decision.get("preferred_group_policy")
        == "keep_existing_5_group_segment_major_default"
        and tuning_decision.get("preferred_inner_order") == "segment-major",
    }
    failed_checks = [key for key, value in checks.items() if not value]
    verdict = "ok_dream7b_b4_next_action_admission_pack" if not failed_checks else "warning_dream7b_b4_next_action_admission_pack"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "true_batch_nas_inventory": str(inventory_path),
            "runtime_experiment_gate": str(runtime_gate_path),
            "runtime_command_guard": str(runtime_guard_path),
            "compile_command_guard": str(compile_guard_path),
            "compile_command_guard_preflight_fixture": str(compile_guard_preflight_path),
            "last_token_compile_readiness": str(compile_readiness_path),
            "compile_capacity_plan": str(compile_capacity_path),
            "tuning_decision_matrix": str(tuning_path),
            "runtime_refactor_backlog": str(refactor_path),
            "final_logits_leverage_model": str(leverage_path),
            "per_run_evidence_matrix": str(per_run_evidence_matrix_path),
            "product_decision_packet": str(product_path) if product_path else None,
            "freshness_gate": str(freshness_path) if freshness_path.exists() else None,
        },
        "summary": {
            "production_default": product_decision.get("production_default"),
            "queue_should_remain_default": product_decision.get("queue_should_remain_default"),
            "next_nonduplicate_runtime_candidate": runtime_decision.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "allowed_now_count": len(allowed_now),
            "preflight_only_count": len(preflight_only),
            "blocked_action_count": len(blocked),
            "would_start_runtime": False,
            "would_start_compile": False,
            "per_run_matrix_gate_ready": per_run_matrix_gate_ready,
            "per_run_matrix_verdict": per_run_evidence_matrix.get("verdict"),
            "per_run_matrix_run_count": per_run_summary.get("run_count"),
            "per_run_matrix_successful_run_count": per_run_summary.get(
                "successful_run_count"
            ),
            "per_run_matrix_failed_run_count": per_run_summary.get("failed_run_count"),
            "per_run_matrix_top_segment": per_run_summary.get("most_common_top_segment"),
            "per_run_matrix_top_segment_rate": per_run_summary.get(
                "most_common_top_segment_rate"
            ),
            "per_run_matrix_standard_sweep_status": per_run_summary.get(
                "standard_b4_runtime_sweep_status"
            ),
            "safe_compile_preflight_command": safe_compile_preflight_command,
        },
        "actions": actions,
        "allowed_now": allowed_now,
        "preflight_only": preflight_only,
        "blocked": blocked,
        "checks": checks,
        "failed_checks": failed_checks,
        "decision": {
            "do_not_run_standard_true_batch_runtime_now": True,
            "do_not_start_compile_now": True,
            "do_not_promote_true_batch_now": True,
            "queue_batch_product_work_allowed_now": True,
            "local_runtime_refactor_analysis_allowed_now": True,
            "compile_preflight_only_allowed_now": True,
            "only_future_runtime_candidate": "seg27_28_last_token_logits_after_manifest_ready",
        },
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "remote_write_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown next-action admission pack only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Next-Action Admission Pack",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- production_default: `{summary['production_default']}`",
        f"- queue_should_remain_default: `{summary['queue_should_remain_default']}`",
        f"- next_nonduplicate_runtime_candidate: `{summary['next_nonduplicate_runtime_candidate']}`",
        f"- allowed_now_count: `{summary['allowed_now_count']}`",
        f"- preflight_only_count: `{summary['preflight_only_count']}`",
        f"- blocked_action_count: `{summary['blocked_action_count']}`",
        f"- would_start_runtime: `{summary['would_start_runtime']}`",
        f"- would_start_compile: `{summary['would_start_compile']}`",
        f"- per_run_matrix_gate_ready: `{summary['per_run_matrix_gate_ready']}`",
        f"- per_run_matrix_verdict: `{summary['per_run_matrix_verdict']}`",
        f"- per_run_matrix_runs: `{summary['per_run_matrix_run_count']} total, {summary['per_run_matrix_successful_run_count']} ok, {summary['per_run_matrix_failed_run_count']} failed`",
        f"- per_run_matrix_top_segment: `{summary['per_run_matrix_top_segment']} @ {summary['per_run_matrix_top_segment_rate']}`",
        f"- per_run_matrix_standard_sweep_status: `{summary['per_run_matrix_standard_sweep_status']}`",
        f"- compile_preflight_only_allowed_now: `{decision['compile_preflight_only_allowed_now']}`",
        f"- only_future_runtime_candidate: `{decision['only_future_runtime_candidate']}`",
        "",
        "## Allowed Now",
        "",
    ]
    for item in payload["allowed_now"]:
        lines.append(f"- {item['id']}: `{item['reason']}`")
    lines.extend(["", "## Preflight Only", ""])
    for item in payload["preflight_only"]:
        lines.append(f"- {item['id']}: `{item['reason']}`")
        if item.get("command"):
            lines.append(f"  - command: `{item['command']}`")
    lines.extend(["", "## Blocked", ""])
    for item in payload["blocked"]:
        lines.append(f"- {item['id']}: `{item['status']}`; {item['reason']}")
        if item.get("blockers"):
            lines.append(f"  - blockers: `{item['blockers']}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify the next Dream7B B=4 actions without starting runtime or compile."
    )
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
