#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dream7b_bpu_quality_validation_common import (
    DEFAULT_KNOWN_HOSTS,
    DEFAULT_OUT_ROOT,
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_REPORT_ROOT,
    DEFAULT_SSH_KEY,
    generated_at,
    get_path,
    now_stamp,
    read_json,
    sync_to_nas,
    write_latest,
)


STEM = "dream7b_ai_nas_final_goal_audit"
DEFAULT_ACCEPTANCE_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_acceptance_packet_latest.json"
DEFAULT_GOAL_STATUS_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_goal_status_packet_latest.json"
DEFAULT_ROUTE_A_BOUNDARY_JSON = DEFAULT_OUT_ROOT / "dream7b_route_a_quality_boundary_packet_latest.json"
DEFAULT_CANDIDATE_PACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_candidate_pack_latest.json"
DEFAULT_MATRIX_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_post_compile_validation_matrix_latest.json"
DEFAULT_PROMOTION_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_promotion_gate_latest.json"
DEFAULT_ROLLBACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_rollback_report_latest.json"
DEFAULT_CAPACITY_VERIFIER_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_capacity_post_reboot_verifier_latest.json"
DEFAULT_CAPACITY_HANDOFF_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_capacity_operator_handoff_latest.json"
DEFAULT_SAFE_COMPILE_HANDOFF_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_safe_compile_handoff_latest.json"


def status(ok: bool, *, blocked: bool = False) -> str:
    if ok:
        return "pass"
    if blocked:
        return "blocked"
    return "fail"


def source_ref(path: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "loaded": payload is not None,
        "verdict": payload.get("verdict") if payload else None,
    }


def candidate_ids(candidate_pack: dict[str, Any] | None) -> list[str]:
    return [str(item.get("id")) for item in (candidate_pack or {}).get("candidates") or [] if item.get("id")]


def build_requirements(
    acceptance: dict[str, Any] | None,
    goal_status: dict[str, Any] | None,
    route_a_boundary: dict[str, Any] | None,
    candidate_pack: dict[str, Any] | None,
    matrix: dict[str, Any] | None,
    promotion: dict[str, Any] | None,
    rollback: dict[str, Any] | None,
    capacity_verifier: dict[str, Any] | None,
    capacity_handoff: dict[str, Any] | None,
    safe_compile_handoff: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    goal_eval = (goal_status or {}).get("evaluation") or {}
    route_a_eval = goal_eval.get("route_a") or {}
    route_b_eval = goal_eval.get("route_b") or {}
    remote = (goal_status or {}).get("remote") or {}
    health = remote.get("health") or {}
    services = remote.get("services") or {}
    audit = remote.get("audit") or {}
    compile_processes = remote.get("compile_processes") or {}
    route_a_boundary_eval = (route_a_boundary or {}).get("evaluation") or {}
    fast_path = route_a_boundary_eval.get("fast_path") or {}
    generic = route_a_boundary_eval.get("generic_generation_boundary") or {}
    generic_cases = generic.get("cases") or []
    rollback_summary = (rollback or {}).get("summary") or {}
    capacity_target = (capacity_handoff or {}).get("target") or {}
    capacity_checks = (capacity_verifier or {}).get("checks") or {}
    candidate_list = candidate_ids(candidate_pack)
    promotion_blockers = (promotion or {}).get("blockers") or []
    safe_compile_locked = (
        (safe_compile_handoff or {}).get("verdict") == "blocked_dream7b_bpu_quality_safe_compile_handoff"
        and (safe_compile_handoff or {}).get("operator_may_run_compile") is False
        and compile_processes.get("active") is False
    )
    safe_compile_ready = (
        (safe_compile_handoff or {}).get("verdict") == "ready_dream7b_bpu_quality_safe_compile_handoff"
        and (safe_compile_handoff or {}).get("operator_may_run_compile") is True
    )

    route_a_live = (
        get_path(health, "openclaw_18789", "ok") is True
        and get_path(health, "gateway_18888", "ok") is True
        and get_path(services, "dream7b_local_openai_gateway", "active") is True
        and get_path(services, "openclaw_gateway", "active") is True
    )
    fast_path_ok = (
        route_a_boundary_eval.get("ready_for_demo") is True
        and fast_path.get("ready") is True
        and (fast_path.get("max_first_content_ms") or 10**9) <= 100.0
    )
    generic_boundary_ok = (
        bool(generic_cases)
        and generic.get("promotion_claim") is False
        and generic_cases[0].get("elapsed_ms") is not None
    )
    bpu_baseline_ok = (
        get_path(services, "dream7b_bpu_batch_queue", "active") is True
        and rollback_summary.get("seq16_baseline_deleted") is False
    )
    guardrail_ok = (
        rollback_summary.get("production_path_unchanged") is True
        and rollback_summary.get("service_restarted") is False
        and rollback_summary.get("overwrote_18888") is False
        and audit.get("compile_started") is False
        and audit.get("runtime_started") is False
        and audit.get("service_restarted") is False
        and audit.get("production_write_performed") is False
        and compile_processes.get("active") is False
    )
    candidate_plan_ok = (
        (candidate_pack or {}).get("verdict") == "ok_dream7b_bpu_quality_candidate_pack"
        and "seg27_28_lmheadq16_last_token_sentinel" in candidate_list
        and "seg21_28_lateq16_quality_set" in candidate_list
        and "seg27_28_seq128_lmheadq16_state_dict_sentinel" in candidate_list
        and "seg27_28_seq256_lmheadq16_state_dict_sentinel" in candidate_list
    )
    capacity_handoff_ok = (
        (capacity_handoff or {}).get("verdict") == "ok_dream7b_bpu_quality_capacity_operator_handoff"
        and capacity_target.get("selected_additional_pagefile_name") == r"F:\pagefile.sys"
        and capacity_target.get("additional_pagefile_mb") == 49152
        and get_path(capacity_handoff, "audit", "system_setting_changed") is False
    )
    capacity_ready = (capacity_verifier or {}).get("ready") is True
    route_b_promotion_ready = route_b_eval.get("ready_for_promotion") is True
    full_goal_complete = (acceptance or {}).get("full_goal_complete") is True and route_b_promotion_ready

    return [
        {
            "id": "route_a_live_http_openclaw_and_gateway",
            "status": status(route_a_live),
            "required_for_full_goal": True,
            "evidence": {
                "openclaw_18789_ok": get_path(health, "openclaw_18789", "ok"),
                "gateway_18888_ok": get_path(health, "gateway_18888", "ok"),
                "dream7b_local_openai_gateway_active": get_path(services, "dream7b_local_openai_gateway", "active"),
                "openclaw_gateway_active": get_path(services, "openclaw_gateway", "active"),
            },
        },
        {
            "id": "route_a_fast_path_identity_status_ready",
            "status": status(fast_path_ok),
            "required_for_full_goal": True,
            "evidence": {
                "route_a_boundary_verdict": (route_a_boundary or {}).get("verdict"),
                "fast_path_ready": fast_path.get("ready"),
                "fast_path_max_first_content_ms": fast_path.get("max_first_content_ms"),
                "max_allowed_ms": 100.0,
            },
        },
        {
            "id": "route_a_generic_generation_boundary_recorded",
            "status": status(generic_boundary_ok),
            "required_for_full_goal": True,
            "evidence": {
                "generic_case_count": len(generic_cases),
                "generic_elapsed_ms": generic_cases[0].get("elapsed_ms") if generic_cases else None,
                "promotion_claim": generic.get("promotion_claim"),
            },
        },
        {
            "id": "route_b_queue_batch_baseline_preserved",
            "status": status(bpu_baseline_ok),
            "required_for_full_goal": True,
            "evidence": {
                "dream7b_bpu_batch_queue_active": get_path(services, "dream7b_bpu_batch_queue", "active"),
                "seq16_baseline_deleted": rollback_summary.get("seq16_baseline_deleted"),
            },
        },
        {
            "id": "route_b_production_guardrails_preserved",
            "status": status(guardrail_ok),
            "required_for_full_goal": True,
            "evidence": {
                "production_path_unchanged": rollback_summary.get("production_path_unchanged"),
                "service_restarted": rollback_summary.get("service_restarted"),
                "overwrote_18888": rollback_summary.get("overwrote_18888"),
                "compile_process_active": compile_processes.get("active"),
                "audit": audit,
            },
        },
        {
            "id": "route_b_lmhead_late_segment_seq128_seq256_candidate_plan",
            "status": status(candidate_plan_ok),
            "required_for_full_goal": True,
            "evidence": {
                "candidate_pack_verdict": (candidate_pack or {}).get("verdict"),
                "candidate_ids": candidate_list,
            },
        },
        {
            "id": "route_b_capacity_handoff_prepared_not_executed",
            "status": status(capacity_handoff_ok),
            "required_for_full_goal": False,
            "evidence": {
                "capacity_handoff_verdict": (capacity_handoff or {}).get("verdict"),
                "selected_pagefile": capacity_target.get("selected_additional_pagefile_name"),
                "additional_pagefile_mb": capacity_target.get("additional_pagefile_mb"),
                "system_setting_changed": get_path(capacity_handoff, "audit", "system_setting_changed"),
            },
        },
        {
            "id": "route_b_safe_compile_handoff_enforced",
            "status": status(safe_compile_locked or safe_compile_ready),
            "required_for_full_goal": False,
            "evidence": {
                "safe_compile_handoff_verdict": (safe_compile_handoff or {}).get("verdict"),
                "operator_may_run_compile": (safe_compile_handoff or {}).get("operator_may_run_compile"),
                "safe_compile_blockers": (safe_compile_handoff or {}).get("blockers"),
                "compile_process_active": compile_processes.get("active"),
            },
        },
        {
            "id": "route_b_capacity_ready_after_reboot",
            "status": status(capacity_ready, blocked=True),
            "required_for_full_goal": True,
            "evidence": {
                "capacity_verifier_verdict": (capacity_verifier or {}).get("verdict"),
                "ready": (capacity_verifier or {}).get("ready"),
                "pagefile_active_after_reboot": capacity_checks.get("pagefile_active_after_reboot"),
                "commit_headroom_ready": capacity_checks.get("commit_headroom_ready"),
            },
        },
        {
            "id": "route_b_post_compile_quality_latency_rollback_gates",
            "status": status(route_b_promotion_ready, blocked=True),
            "required_for_full_goal": True,
            "evidence": {
                "matrix_verdict": (matrix or {}).get("verdict"),
                "promotion_verdict": (promotion or {}).get("verdict"),
                "promotion_blockers": promotion_blockers,
                "route_b_errors": route_b_eval.get("errors"),
            },
        },
        {
            "id": "final_goal_complete",
            "status": status(full_goal_complete, blocked=True),
            "required_for_full_goal": True,
            "evidence": {
                "acceptance_verdict": (acceptance or {}).get("verdict"),
                "acceptance_full_goal_complete": (acceptance or {}).get("full_goal_complete"),
                "goal_status_goal_complete": goal_eval.get("goal_complete"),
                "route_a_status": route_a_eval.get("status"),
                "route_b_status": route_b_eval.get("status"),
            },
        },
    ]


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    acceptance = read_json(args.acceptance_json)
    goal_status = read_json(args.goal_status_json)
    route_a_boundary = read_json(args.route_a_boundary_json)
    candidate_pack = read_json(args.candidate_pack_json)
    matrix = read_json(args.matrix_json)
    promotion = read_json(args.promotion_json)
    rollback = read_json(args.rollback_json)
    capacity_verifier = read_json(args.capacity_verifier_json)
    capacity_handoff = read_json(args.capacity_handoff_json)
    safe_compile_handoff = read_json(args.safe_compile_handoff_json)
    requirements = build_requirements(
        acceptance,
        goal_status,
        route_a_boundary,
        candidate_pack,
        matrix,
        promotion,
        rollback,
        capacity_verifier,
        capacity_handoff,
        safe_compile_handoff,
    )
    full_required = [item for item in requirements if item["required_for_full_goal"]]
    passed_required = [item for item in full_required if item["status"] == "pass"]
    blocked_required = [item for item in full_required if item["status"] == "blocked"]
    failed_required = [item for item in full_required if item["status"] == "fail"]
    demo_ready = (acceptance or {}).get("demo_delivery_ready") is True
    all_complete = len(passed_required) == len(full_required)
    if all_complete:
        verdict = "complete_dream7b_ai_nas_final_goal_audit"
    elif demo_ready and blocked_required and not failed_required:
        verdict = "partial_dream7b_ai_nas_final_goal_audit_route_a_ready_route_b_blocked"
    else:
        verdict = "blocked_dream7b_ai_nas_final_goal_audit"

    return {
        "generated_at": generated_at(),
        "verdict": verdict,
        "all_complete": all_complete,
        "demo_delivery_ready": demo_ready,
        "summary": {
            "required_count": len(full_required),
            "required_pass_count": len(passed_required),
            "required_blocked_count": len(blocked_required),
            "required_fail_count": len(failed_required),
            "blocked_requirement_ids": [item["id"] for item in blocked_required],
            "failed_requirement_ids": [item["id"] for item in failed_required],
        },
        "requirements": requirements,
        "source_reports": {
            "acceptance": source_ref(args.acceptance_json, acceptance),
            "goal_status": source_ref(args.goal_status_json, goal_status),
            "route_a_boundary": source_ref(args.route_a_boundary_json, route_a_boundary),
            "candidate_pack": source_ref(args.candidate_pack_json, candidate_pack),
            "post_compile_matrix": source_ref(args.matrix_json, matrix),
            "promotion_gate": source_ref(args.promotion_json, promotion),
            "rollback": source_ref(args.rollback_json, rollback),
            "capacity_verifier": source_ref(args.capacity_verifier_json, capacity_verifier),
            "capacity_handoff": source_ref(args.capacity_handoff_json, capacity_handoff),
            "safe_compile_handoff": source_ref(args.safe_compile_handoff_json, safe_compile_handoff),
        },
        "next_actions": [
            "Keep Route A as the current demo and product path.",
            "Do not replace 18888, restart production services, or delete seq16 BPU baselines during Route B work.",
            "After operator-approved pagefile handoff and reboot, rerun post_reboot_resume_runner with --run-preflight, then rerun safe_compile_handoff.",
            "Promote Route B only after capacity, compile admission, logits, Chinese generation, same-workload, and rollback gates pass.",
        ],
        "policy": {
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
            "production_write_performed_by_this_probe": False,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B AI-NAS Final Goal Audit",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- all_complete: `{payload['all_complete']}`",
        f"- demo_delivery_ready: `{payload['demo_delivery_ready']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Requirements", ""])
    for item in payload["requirements"]:
        lines.append(
            f"- {item['id']}: status=`{item['status']}` required_for_full_goal=`{item['required_for_full_goal']}`"
        )
    lines.extend(["", "## Source Reports", ""])
    for key, ref in payload["source_reports"].items():
        lines.append(f"- {key}: exists=`{ref['exists']}` verdict=`{ref['verdict']}` path=`{ref['path']}`")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance-json", type=Path, default=DEFAULT_ACCEPTANCE_JSON)
    parser.add_argument("--goal-status-json", type=Path, default=DEFAULT_GOAL_STATUS_JSON)
    parser.add_argument("--route-a-boundary-json", type=Path, default=DEFAULT_ROUTE_A_BOUNDARY_JSON)
    parser.add_argument("--candidate-pack-json", type=Path, default=DEFAULT_CANDIDATE_PACK_JSON)
    parser.add_argument("--matrix-json", type=Path, default=DEFAULT_MATRIX_JSON)
    parser.add_argument("--promotion-json", type=Path, default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--rollback-json", type=Path, default=DEFAULT_ROLLBACK_JSON)
    parser.add_argument("--capacity-verifier-json", type=Path, default=DEFAULT_CAPACITY_VERIFIER_JSON)
    parser.add_argument("--capacity-handoff-json", type=Path, default=DEFAULT_CAPACITY_HANDOFF_JSON)
    parser.add_argument("--safe-compile-handoff-json", type=Path, default=DEFAULT_SAFE_COMPILE_HANDOFF_JSON)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    report_dir = args.out_root / f"{STEM}_{now_stamp()}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / f"{STEM}.json"
    md_path = report_dir / f"{STEM}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    if not args.no_sync:
        sync = sync_to_nas(args, report_dir, f"{STEM}.json", f"{STEM}.md")
        payload["sync"] = sync
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(md_path, payload)
        if sync.get("ok") is False:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
    write_latest(args.out_root, STEM, json_path, md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
