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


STEM = "dream7b_ai_nas_acceptance_packet"
DEFAULT_GOAL_STATUS_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_goal_status_packet_latest.json"
DEFAULT_ROUTE_A_BOUNDARY_JSON = DEFAULT_OUT_ROOT / "dream7b_route_a_quality_boundary_packet_latest.json"
DEFAULT_ROUTE_A_DEMO_JSON = DEFAULT_OUT_ROOT / "ai_nas_route_a_demo_readiness_packet_latest.json"
DEFAULT_MATRIX_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_post_compile_validation_matrix_latest.json"
DEFAULT_PROMOTION_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_promotion_gate_latest.json"
DEFAULT_ROLLBACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_rollback_report_latest.json"
DEFAULT_CAPACITY_HANDOFF_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_capacity_operator_handoff_latest.json"
DEFAULT_SAFE_COMPILE_HANDOFF_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_safe_compile_handoff_latest.json"


def report_ref(path: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "loaded": payload is not None,
        "verdict": payload.get("verdict") if payload else None,
        "summary": payload.get("summary") if payload else {},
        "evaluation": payload.get("evaluation") if payload else {},
        "errors": payload.get("errors") if payload else [],
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    goal = read_json(args.goal_status_json)
    route_a_boundary = read_json(args.route_a_boundary_json)
    route_a_demo = read_json(args.route_a_demo_json)
    matrix = read_json(args.matrix_json)
    promotion = read_json(args.promotion_json)
    rollback = read_json(args.rollback_json)
    capacity_handoff = read_json(args.capacity_handoff_json)
    safe_compile_handoff = read_json(args.safe_compile_handoff_json)

    goal_eval = (goal or {}).get("evaluation") or {}
    remote = (goal or {}).get("remote") or {}
    reports = remote.get("reports") or {}
    health = remote.get("health") or {}
    services = remote.get("services") or {}
    audit = remote.get("audit") or {}
    route_a_eval = goal_eval.get("route_a") or {}
    route_b_eval = goal_eval.get("route_b") or {}
    rollback_summary = (rollback or {}).get("summary") or {}

    route_a_demo_ready = (
        route_a_eval.get("ready") is True
        and get_path(route_a_boundary, "evaluation", "ready_for_demo") is True
        and get_path(route_a_boundary, "evaluation", "fast_path", "ready") is True
        and get_path(route_a_boundary, "evaluation", "generic_generation_boundary", "promotion_claim") is False
        and get_path(route_a_demo, "verdict") == "ok_ai_nas_route_a_demo_readiness_packet"
        and get_path(health, "gateway_18888", "ok") is True
        and get_path(health, "openclaw_18789", "ok") is True
    )
    route_b_isolated = (
        rollback_summary.get("production_path_unchanged") is True
        and rollback_summary.get("service_restarted") is False
        and rollback_summary.get("overwrote_18888") is False
        and rollback_summary.get("seq16_baseline_deleted") is False
        and audit.get("compile_started") is False
        and audit.get("runtime_started") is False
        and audit.get("service_restarted") is False
        and audit.get("production_write_performed") is False
        and get_path(remote, "compile_processes", "active") is False
    )
    route_b_promotion_ready = route_b_eval.get("ready_for_promotion") is True
    route_b_compile_locked = (
        (safe_compile_handoff or {}).get("verdict") == "blocked_dream7b_bpu_quality_safe_compile_handoff"
        and (safe_compile_handoff or {}).get("operator_may_run_compile") is False
        and get_path(remote, "compile_processes", "active") is False
    )
    full_goal_complete = goal_eval.get("goal_complete") is True and route_a_demo_ready and route_b_promotion_ready
    demo_delivery_ready = route_a_demo_ready and route_b_isolated

    route_a_boundary_eval = (route_a_boundary or {}).get("evaluation") or {}
    fast_path = route_a_boundary_eval.get("fast_path") or {}
    generic_boundary = route_a_boundary_eval.get("generic_generation_boundary") or {}
    generic_cases = generic_boundary.get("cases") or []
    capacity_target = (capacity_handoff or {}).get("target") or {}

    if full_goal_complete:
        verdict = "complete_dream7b_ai_nas_acceptance_packet"
        status = "full_goal_complete"
    elif demo_delivery_ready:
        verdict = "partial_dream7b_ai_nas_acceptance_packet_route_a_ready_route_b_blocked"
        status = "route_a_demo_deliverable_route_b_research_blocked"
    else:
        verdict = "blocked_dream7b_ai_nas_acceptance_packet"
        status = "acceptance_blocked"

    return {
        "generated_at": generated_at(),
        "verdict": verdict,
        "status": status,
        "full_goal_complete": full_goal_complete,
        "demo_delivery_ready": demo_delivery_ready,
        "route_a_demo_ready": route_a_demo_ready,
        "route_b_isolated": route_b_isolated,
        "route_b_promotion_ready": route_b_promotion_ready,
        "summary": {
            "route_a_status": route_a_eval.get("status"),
            "route_b_status": route_b_eval.get("status"),
            "route_b_errors": route_b_eval.get("errors"),
            "gateway_18888_ok": get_path(health, "gateway_18888", "ok"),
            "openclaw_18789_ok": get_path(health, "openclaw_18789", "ok"),
            "fast_path_max_first_content_ms": fast_path.get("max_first_content_ms"),
            "generic_generation_elapsed_ms": generic_cases[0].get("elapsed_ms") if generic_cases else None,
            "generic_generation_promotion_claim": generic_boundary.get("promotion_claim"),
            "capacity_target_commit_limit_gb": capacity_target.get("target_commit_limit_gb"),
            "capacity_selected_pagefile": capacity_target.get("selected_additional_pagefile_name"),
            "post_compile_matrix_verdict": (matrix or {}).get("verdict"),
            "promotion_gate_verdict": (promotion or {}).get("verdict"),
            "rollback_verdict": (rollback or {}).get("verdict"),
            "safe_compile_handoff_verdict": (safe_compile_handoff or {}).get("verdict"),
            "operator_may_run_compile": (safe_compile_handoff or {}).get("operator_may_run_compile"),
        },
        "requirements": {
            "route_a_openclaw_health_live": {
                "ok": get_path(health, "openclaw_18789", "ok") is True,
                "evidence": get_path(health, "openclaw_18789", "json"),
            },
            "route_a_dream7b_health_live": {
                "ok": get_path(health, "gateway_18888", "ok") is True,
                "evidence": get_path(health, "gateway_18888", "json"),
            },
            "route_a_fast_path_demo_ready": {
                "ok": route_a_demo_ready,
                "evidence": {
                    "route_a_boundary_verdict": (route_a_boundary or {}).get("verdict"),
                    "route_a_demo_verdict": (route_a_demo or {}).get("verdict"),
                    "fast_path_max_first_content_ms": fast_path.get("max_first_content_ms"),
                    "generic_promotion_claim": generic_boundary.get("promotion_claim"),
                },
            },
            "route_b_queue_baseline_preserved": {
                "ok": get_path(services, "dream7b_bpu_batch_queue", "active") is True
                and rollback_summary.get("seq16_baseline_deleted") is False,
                "evidence": {
                    "dream7b_bpu_batch_queue_active": get_path(services, "dream7b_bpu_batch_queue", "active"),
                    "seq16_baseline_deleted": rollback_summary.get("seq16_baseline_deleted"),
                },
            },
            "route_b_production_guardrail_preserved": {
                "ok": route_b_isolated,
                "evidence": {
                    "production_path_unchanged": rollback_summary.get("production_path_unchanged"),
                    "service_restarted": rollback_summary.get("service_restarted"),
                    "overwrote_18888": rollback_summary.get("overwrote_18888"),
                    "compile_process_active": get_path(remote, "compile_processes", "active"),
                    "audit": audit,
                },
            },
            "route_b_compile_handoff_locked_until_ready": {
                "ok": route_b_compile_locked or route_b_promotion_ready,
                "evidence": {
                    "safe_compile_handoff_verdict": (safe_compile_handoff or {}).get("verdict"),
                    "operator_may_run_compile": (safe_compile_handoff or {}).get("operator_may_run_compile"),
                    "safe_compile_blockers": (safe_compile_handoff or {}).get("blockers"),
                    "compile_process_active": get_path(remote, "compile_processes", "active"),
                },
            },
            "route_b_promotion_ready": {
                "ok": route_b_promotion_ready,
                "evidence": {
                    "matrix_verdict": (matrix or {}).get("verdict"),
                    "matrix_blockers": (matrix or {}).get("blockers"),
                    "promotion_gate_verdict": (promotion or {}).get("verdict"),
                    "promotion_blockers": (promotion or {}).get("blockers"),
                    "route_b_errors": route_b_eval.get("errors"),
                },
            },
        },
        "source_reports": {
            "goal_status": report_ref(args.goal_status_json, goal),
            "route_a_quality_boundary": report_ref(args.route_a_boundary_json, route_a_boundary),
            "route_a_demo_readiness": report_ref(args.route_a_demo_json, route_a_demo),
            "post_compile_validation_matrix": report_ref(args.matrix_json, matrix),
            "promotion_gate": report_ref(args.promotion_json, promotion),
            "rollback_report": report_ref(args.rollback_json, rollback),
            "capacity_operator_handoff": report_ref(args.capacity_handoff_json, capacity_handoff),
            "safe_compile_handoff": report_ref(args.safe_compile_handoff_json, safe_compile_handoff),
            "goal_status_remote_reports": reports,
        },
        "next_actions": [
            "Keep Route A as the demo/product path: OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF.",
            "Execute the prepared pagefile handoff outside this probe if the operator approves: keep C:\\pagefile.sys=27648 MB and add F:\\pagefile.sys=49152 MB, then reboot.",
            "After reboot, run capacity_post_reboot_verifier, capacity_unblock_plan, rank-1 preflight, compile_admission_guard, and safe_compile_handoff in order.",
            "Only after safe_compile_handoff reports operator_may_run_compile=true, build the rank-1 seg27_28_lmheadq16 last-token candidate and rerun rollback, logits, generation, same-workload, promotion, goal-status, and acceptance packets.",
        ],
        "policy": {
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
            "production_write_performed_by_this_probe": False,
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
            "route_a_must_remain_default_until_route_b_promotion": True,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B AI-NAS Acceptance Packet",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- status: `{payload['status']}`",
        f"- full_goal_complete: `{payload['full_goal_complete']}`",
        f"- demo_delivery_ready: `{payload['demo_delivery_ready']}`",
        f"- route_a_demo_ready: `{payload['route_a_demo_ready']}`",
        f"- route_b_isolated: `{payload['route_b_isolated']}`",
        f"- route_b_promotion_ready: `{payload['route_b_promotion_ready']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Requirements", ""])
    for key, item in payload["requirements"].items():
        lines.append(f"- {key}: ok=`{item['ok']}`")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.extend(["", "## Source Reports", ""])
    for key, ref in payload["source_reports"].items():
        if key == "goal_status_remote_reports":
            continue
        lines.append(f"- {key}: exists=`{ref['exists']}` verdict=`{ref['verdict']}` path=`{ref['path']}`")
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal-status-json", type=Path, default=DEFAULT_GOAL_STATUS_JSON)
    parser.add_argument("--route-a-boundary-json", type=Path, default=DEFAULT_ROUTE_A_BOUNDARY_JSON)
    parser.add_argument("--route-a-demo-json", type=Path, default=DEFAULT_ROUTE_A_DEMO_JSON)
    parser.add_argument("--matrix-json", type=Path, default=DEFAULT_MATRIX_JSON)
    parser.add_argument("--promotion-json", type=Path, default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--rollback-json", type=Path, default=DEFAULT_ROLLBACK_JSON)
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
    return 0 if payload["demo_delivery_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
