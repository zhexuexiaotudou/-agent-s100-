#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_workstream_overlap_audit"


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def latest_json(root: Path, pattern: str) -> Path | None:
    paths = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime)
    return paths[-1] if paths else None


def latest_json_or_fallback(root: Path, pattern: str, fallback: Path) -> Path:
    return latest_json(root, pattern) or fallback


def as_bool(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    inventory_path = latest_json_or_fallback(
        args.analysis_root,
        "dream7b_true_batch_nas_inventory_*.json",
        args.analysis_root / "dream7b_true_batch_nas_inventory_20260620.json",
    )
    runtime_gate_path = args.analysis_root / "dream7b_b4_runtime_experiment_gate_20260620.json"
    last_token_readiness_path = args.analysis_root / "dream7b_b4_last_token_compile_readiness_20260619.json"
    compile_capacity_path = args.analysis_root / "dream7b_b4_compile_capacity_plan_20260619.json"
    queue_health_path = latest_json(
        args.snapshot_root, "dream7b_queue_health_snapshot_*/dream7b_queue_health_snapshot.json"
    )
    product_path = latest_json(
        args.snapshot_root, "dream7b_product_decision_packet_*/dream7b_product_decision_packet.json"
    )

    inventory = read_json(inventory_path)
    runtime_gate = read_json(runtime_gate_path)
    last_token_readiness = read_json(last_token_readiness_path)
    compile_capacity = read_json(compile_capacity_path)
    queue_health = read_json(queue_health_path)
    product = read_json(product_path)

    inventory_decision = inventory.get("decision") or {}
    inventory_remote = inventory.get("remote") or {}
    inventory_local = inventory.get("local_coverage") or {}
    runtime_decision = runtime_gate.get("decision") or {}
    runtime_summary = runtime_gate.get("summary") or {}
    last_token_summary = last_token_readiness.get("summary") or last_token_readiness
    compile_recommendation = compile_capacity.get("recommendation") or {}
    product_decision = product.get("decision") or {}
    queue_health_summary = product.get("queue_health_snapshot") or {}
    if not queue_health_summary:
        queue_health_summary = {
            "verdict": queue_health.get("verdict"),
            "queue_idle_at_probe": (queue_health.get("checks") or {}).get("queue_idle_at_probe"),
            "no_true_batch_or_compile_process": (queue_health.get("checks") or {}).get(
                "no_true_batch_or_compile_process"
            ),
            "quick_ready_first_content_ms": (
                queue_health.get("fast_path_regression") or {}
            ).get("quick_ready_first_content_ms"),
            "latest_text_queue_ms_per_request": (
                (queue_health.get("remote") or {}).get("latest_text_queue_run") or {}
            ).get("ms_per_request"),
        }

    duplicate_stop_rules = inventory_decision.get("duplicate_stop_rules") or []
    remaining_nonduplicate_work = inventory_decision.get("remaining_nonduplicate_work") or []
    standard_sweeps_blocked = (
        inventory_decision.get("run_more_standard_b4_runtime_sweeps_now") is False
        and runtime_decision.get("run_standard_b4_sweeps_now") is False
        and runtime_decision.get("s100p_runtime_experiment_now") is False
        and (runtime_decision.get("allowed_experiments") or []) == []
    )
    b4_rental_records_present = (
        int(inventory_remote.get("b4_group_major_report_count") or 0) > 0
        and int(inventory_remote.get("b4_group_major_report_json_count") or 0) > 0
        and int(inventory_remote.get("b4_hbm_count") or 0) == 28
        and int(inventory_remote.get("b4_manifest_count") or 0) == 28
    )
    b4_records_mirrored = (
        inventory_decision.get("b4_remote_local_count_match") is True
        and inventory_decision.get("b4_remote_json_local_count_match") is True
        and inventory_decision.get("b4_history_is_already_mirrored_locally") is True
    )
    queue_work_is_not_true_batch_rerun = (
        queue_health_summary.get("verdict") == "ok_dream7b_queue_health_snapshot"
        and queue_health_summary.get("queue_idle_at_probe") is True
        and queue_health_summary.get("no_true_batch_or_compile_process") is True
        and product_decision.get("production_default") == "queue_batch"
        and product_decision.get("queue_should_remain_default") is True
    )
    last_token_only_is_blocked_until_compile_ready = (
        runtime_decision.get("next_nonduplicate_runtime_candidate") == "seg27_28_last_token_logits"
        and last_token_summary.get("compile_ready") is False
        and last_token_summary.get("runtime_validation_ready") is False
        and compile_recommendation.get("do_not_start_compile_now") is True
    )
    checks = {
        "b4_true_batch_rental_records_present": b4_rental_records_present,
        "b4_true_batch_records_mirrored_locally": b4_records_mirrored,
        "standard_true_batch_sweeps_blocked_as_duplicates": standard_sweeps_blocked,
        "current_queue_work_is_not_true_batch_rerun": queue_work_is_not_true_batch_rerun,
        "last_token_only_is_blocked_until_compile_ready": last_token_only_is_blocked_until_compile_ready,
    }
    failed_checks = [key for key, value in checks.items() if not value]
    verdict = "ok_dream7b_workstream_overlap_audit" if not failed_checks else "warning_dream7b_workstream_overlap_audit"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_paths": {
            "true_batch_nas_inventory": str(inventory_path),
            "runtime_experiment_gate": str(runtime_gate_path),
            "last_token_compile_readiness": str(last_token_readiness_path),
            "compile_capacity_plan": str(compile_capacity_path),
            "queue_health_snapshot": str(queue_health_path) if queue_health_path else None,
            "product_decision_packet": str(product_path) if product_path else None,
        },
        "true_batch_prior_work": {
            "remote_group_major_report_count": inventory_remote.get("group_major_report_count"),
            "remote_group_major_report_json_count": inventory_remote.get(
                "group_major_report_json_count"
            ),
            "remote_batch_counts": inventory_remote.get("batch_counts") or {},
            "remote_report_json_batch_counts": inventory_remote.get(
                "report_json_batch_counts"
            )
            or {},
            "missing_report_json_dirs": inventory_remote.get("missing_report_json_dirs") or [],
            "remote_b4_group_major_report_count": inventory_remote.get("b4_group_major_report_count"),
            "remote_b4_group_major_report_json_count": inventory_remote.get(
                "b4_group_major_report_json_count"
            ),
            "local_b4_json_count": inventory_local.get("local_b4_json_count"),
            "local_b4_successful_count": inventory_local.get("successful_count"),
            "local_b4_failed_count": inventory_local.get("failed_count"),
            "b4_hbm_count": inventory_remote.get("b4_hbm_count"),
            "b4_manifest_count": inventory_remote.get("b4_manifest_count"),
            "b4_remote_local_count_match": inventory_decision.get("b4_remote_local_count_match"),
            "b4_remote_json_local_count_match": inventory_decision.get(
                "b4_remote_json_local_count_match"
            ),
            "b4_history_is_already_mirrored_locally": inventory_decision.get(
                "b4_history_is_already_mirrored_locally"
            ),
            "run_more_standard_b4_runtime_sweeps_now": inventory_decision.get(
                "run_more_standard_b4_runtime_sweeps_now"
            ),
            "duplicate_stop_rule_count": len(duplicate_stop_rules),
            "duplicate_stop_rules": duplicate_stop_rules,
        },
        "queue_batch_current_work": {
            "production_default": product_decision.get("production_default"),
            "queue_should_remain_default": product_decision.get("queue_should_remain_default"),
            "queue_health_verdict": queue_health_summary.get("verdict"),
            "queue_idle_at_probe": queue_health_summary.get("queue_idle_at_probe"),
            "no_true_batch_or_compile_process": queue_health_summary.get(
                "no_true_batch_or_compile_process"
            ),
            "quick_ready_first_content_ms": queue_health_summary.get("quick_ready_first_content_ms"),
            "latest_text_queue_ms_per_request": queue_health_summary.get(
                "latest_text_queue_ms_per_request"
            ),
        },
        "next_true_batch_work": {
            "next_nonduplicate_runtime_candidate": runtime_decision.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "s100p_runtime_experiment_now": runtime_decision.get("s100p_runtime_experiment_now"),
            "allowed_experiments": runtime_decision.get("allowed_experiments") or [],
            "runtime_gate_verdict": runtime_gate.get("verdict"),
            "runtime_gate_blockers": runtime_summary.get("blockers") or runtime_gate.get("blockers") or [],
            "last_token_compile_ready": last_token_summary.get("compile_ready"),
            "last_token_runtime_validation_ready": last_token_summary.get(
                "runtime_validation_ready"
            ),
            "compile_do_not_start_compile_now": compile_recommendation.get(
                "do_not_start_compile_now"
            ),
            "remaining_nonduplicate_work": remaining_nonduplicate_work,
        },
        "decision": {
            "current_workstream": "queue_batch_product_guardrail_and_nonduplicate_gate",
            "true_batch_standard_sweeps_already_ran": standard_sweeps_blocked,
            "queue_batch_work_duplicates_prior_true_batch_rental": False,
            "do_not_start_standard_true_batch_runtime_now": standard_sweeps_blocked,
            "do_not_start_true_batch_compile_now": compile_recommendation.get(
                "do_not_start_compile_now"
            )
            is True,
            "next_allowed_true_batch_work": "seg27_28_last_token_logits_after_compile_manifest_ready",
        },
        "checks": checks,
        "failed_checks": failed_checks,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    true_batch = payload["true_batch_prior_work"]
    queue = payload["queue_batch_current_work"]
    next_work = payload["next_true_batch_work"]
    decision = payload["decision"]
    lines = [
        "# Dream7B Workstream Overlap Audit",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- current_workstream: `{decision['current_workstream']}`",
        f"- queue_batch_work_duplicates_prior_true_batch_rental: `{decision['queue_batch_work_duplicates_prior_true_batch_rental']}`",
        f"- do_not_start_standard_true_batch_runtime_now: `{decision['do_not_start_standard_true_batch_runtime_now']}`",
        f"- do_not_start_true_batch_compile_now: `{decision['do_not_start_true_batch_compile_now']}`",
        "",
        "## True-Batch Prior Work",
        "",
        f"- remote_group_major_report_count: `{true_batch['remote_group_major_report_count']}`",
        f"- remote_group_major_report_json_count: `{true_batch['remote_group_major_report_json_count']}`",
        f"- remote_batch_counts: `{true_batch['remote_batch_counts']}`",
        f"- remote_report_json_batch_counts: `{true_batch['remote_report_json_batch_counts']}`",
        f"- missing_report_json_dirs: `{true_batch['missing_report_json_dirs']}`",
        f"- remote_b4_group_major_report_count: `{true_batch['remote_b4_group_major_report_count']}`",
        f"- remote_b4_group_major_report_json_count: `{true_batch['remote_b4_group_major_report_json_count']}`",
        f"- local_b4_json_count: `{true_batch['local_b4_json_count']}`",
        f"- local_b4_successful_count: `{true_batch['local_b4_successful_count']}`",
        f"- local_b4_failed_count: `{true_batch['local_b4_failed_count']}`",
        f"- b4_hbm_count: `{true_batch['b4_hbm_count']}`",
        f"- b4_manifest_count: `{true_batch['b4_manifest_count']}`",
        f"- b4_remote_local_count_match: `{true_batch['b4_remote_local_count_match']}`",
        f"- b4_remote_json_local_count_match: `{true_batch['b4_remote_json_local_count_match']}`",
        f"- b4_history_is_already_mirrored_locally: `{true_batch['b4_history_is_already_mirrored_locally']}`",
        f"- run_more_standard_b4_runtime_sweeps_now: `{true_batch['run_more_standard_b4_runtime_sweeps_now']}`",
        "",
        "## Queue-Batch Current Work",
        "",
        f"- production_default: `{queue['production_default']}`",
        f"- queue_should_remain_default: `{queue['queue_should_remain_default']}`",
        f"- queue_health_verdict: `{queue['queue_health_verdict']}`",
        f"- queue_idle_at_probe: `{queue['queue_idle_at_probe']}`",
        f"- no_true_batch_or_compile_process: `{queue['no_true_batch_or_compile_process']}`",
        f"- quick_ready_first_content_ms: `{queue['quick_ready_first_content_ms']}`",
        f"- latest_text_queue_ms_per_request: `{queue['latest_text_queue_ms_per_request']}`",
        "",
        "## Next True-Batch Gate",
        "",
        f"- next_nonduplicate_runtime_candidate: `{next_work['next_nonduplicate_runtime_candidate']}`",
        f"- s100p_runtime_experiment_now: `{next_work['s100p_runtime_experiment_now']}`",
        f"- allowed_experiments: `{next_work['allowed_experiments']}`",
        f"- last_token_compile_ready: `{next_work['last_token_compile_ready']}`",
        f"- last_token_runtime_validation_ready: `{next_work['last_token_runtime_validation_ready']}`",
        f"- compile_do_not_start_compile_now: `{next_work['compile_do_not_start_compile_now']}`",
        "",
        "## Duplicate Stop Rules",
        "",
    ]
    lines.extend(f"- {item}" for item in true_batch["duplicate_stop_rules"])
    lines.extend(["", "## Remaining Non-Duplicate Work", ""])
    lines.extend(f"- {item}" for item in next_work["remaining_nonduplicate_work"])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit whether current Dream7B work duplicates prior true-batch rental/NAS evidence."
    )
    parser.add_argument("--analysis-root", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    args = parser.parse_args()

    payload = build_payload(args)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_workstream_overlap_audit_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_workstream_overlap_audit.json"
    out_md = out_dir / "dream7b_workstream_overlap_audit.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(out_md, payload)
    print(out_json)
    print(out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
