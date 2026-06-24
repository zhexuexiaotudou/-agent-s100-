#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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
    now_stamp,
    read_json,
    sync_to_nas,
    write_latest,
)


STEM = "dream7b_ai_nas_delivery_manifest"
DEFAULT_GOAL_STATUS_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_goal_status_packet_latest.json"
DEFAULT_ACCEPTANCE_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_acceptance_packet_latest.json"
DEFAULT_FINAL_AUDIT_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_final_goal_audit_latest.json"
DEFAULT_RESUME_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_post_reboot_resume_runner_latest.json"
DEFAULT_SAFE_COMPILE_HANDOFF_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_safe_compile_handoff_latest.json"

RELEASE_FILES = [
    "scripts/probes/dream7b_perf_identity_probe.py",
    "scripts/probes/dream7b_openclaw_default_latency_probe.py",
    "scripts/probes/dream7b_fast_path_regression_probe.py",
    "scripts/probes/dream7b_first_response_slo_tier_guard.py",
    "scripts/probes/dream7b_route_a_quality_boundary_packet.py",
    "scripts/probes/ai_nas_route_a_demo_readiness_packet.py",
    "scripts/probes/ai_nas_edge_cloud_router_probe.py",
    "scripts/probes/ai_nas_allowlisted_tool.sh",
    "scripts/probes/dream7b_bpu_quality_candidate_gate.py",
    "scripts/probes/dream7b_bpu_quality_candidate_pack.py",
    "scripts/probes/dream7b_bpu_quality_preflight_runner.py",
    "scripts/probes/dream7b_bpu_quality_capacity_unblock_plan.py",
    "scripts/probes/dream7b_bpu_quality_capacity_operator_handoff.py",
    "scripts/probes/dream7b_bpu_quality_capacity_post_reboot_verifier.py",
    "scripts/probes/dream7b_bpu_quality_post_reboot_resume_runner.py",
    "scripts/probes/dream7b_bpu_quality_compile_admission_guard.py",
    "scripts/probes/dream7b_bpu_quality_validation_common.py",
    "scripts/probes/dream7b_bpu_quality_logits_diagnostics.py",
    "scripts/probes/dream7b_bpu_quality_generation_quality.py",
    "scripts/probes/dream7b_bpu_quality_same_workload_compare.py",
    "scripts/probes/dream7b_bpu_quality_rollback_report.py",
    "scripts/probes/dream7b_bpu_quality_promotion_gate.py",
    "scripts/probes/dream7b_bpu_quality_post_compile_validation_matrix.py",
    "scripts/probes/dream7b_bpu_quality_safe_compile_handoff.py",
    "scripts/probes/dream7b_ai_nas_goal_status_packet.py",
    "scripts/probes/dream7b_ai_nas_acceptance_packet.py",
    "scripts/probes/dream7b_ai_nas_final_goal_audit.py",
    "scripts/probes/dream7b_ai_nas_delivery_manifest.py",
    "完全基于agent的s100使用和链路打通/scripts/dream7b_local_openai_gateway.py",
    "scripts/diffuse_resident.cpp",
    "configs/systemd/dream7b-local-openai-gateway.service",
    "configs/systemd/openclaw-gateway.service",
    "docs/dream7b_s100p_next_work_runbook.md",
    "docs/dream7b_openclaw_fast_path_fix_2026-06-22.md",
    "docs/community/dream7b-s100-bpu-deploy/SKILL.md",
]


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_ref(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256_file(path),
    }


def report_remote_path(payload: dict[str, Any] | None, stem: str) -> str | None:
    remote_dir = ((payload or {}).get("sync") or {}).get("remote_dir")
    if not remote_dir:
        return None
    return f"{str(remote_dir).rstrip('/')}/{stem}.json"


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    goal = read_json(args.goal_status_json)
    acceptance = read_json(args.acceptance_json)
    final_audit = read_json(args.final_audit_json)
    resume = read_json(args.resume_json)
    safe_compile_handoff = read_json(args.safe_compile_handoff_json)
    release_files = [file_ref(Path(item)) for item in RELEASE_FILES]
    missing_files = [item["path"] for item in release_files if not item["is_file"]]
    acceptance_summary = (acceptance or {}).get("summary") or {}
    audit_summary = (final_audit or {}).get("summary") or {}
    resume_summary = (resume or {}).get("summary") or {}
    route_b_errors = acceptance_summary.get("route_b_errors") or []
    demo_delivery_ready = (acceptance or {}).get("demo_delivery_ready") is True
    full_goal_complete = (acceptance or {}).get("full_goal_complete") is True
    delivery_manifest_ready = demo_delivery_ready and not missing_files
    if full_goal_complete and not missing_files:
        verdict = "complete_dream7b_ai_nas_delivery_manifest"
    elif delivery_manifest_ready:
        verdict = "partial_dream7b_ai_nas_delivery_manifest_route_a_ready_route_b_blocked"
    else:
        verdict = "blocked_dream7b_ai_nas_delivery_manifest"

    return {
        "generated_at": generated_at(),
        "verdict": verdict,
        "delivery_manifest_ready": delivery_manifest_ready,
        "demo_delivery_ready": demo_delivery_ready,
        "full_goal_complete": full_goal_complete,
        "summary": {
            "release_file_count": len(release_files),
            "missing_release_file_count": len(missing_files),
            "route_a_status": acceptance_summary.get("route_a_status"),
            "route_b_status": acceptance_summary.get("route_b_status"),
            "route_b_errors": route_b_errors,
            "final_audit_required_pass_count": audit_summary.get("required_pass_count"),
            "final_audit_required_blocked_count": audit_summary.get("required_blocked_count"),
            "final_audit_required_fail_count": audit_summary.get("required_fail_count"),
            "rank1_preflight_matches_candidate": resume_summary.get("rank1_preflight_matches_candidate"),
            "latest_preflight_selected_candidate_ids": resume_summary.get("latest_preflight_selected_candidate_ids"),
        },
        "release_files": release_files,
        "missing_release_files": missing_files,
        "nas_evidence": {
            "goal_status": {
                "local_latest": str(args.goal_status_json),
                "remote_json": report_remote_path(goal, "dream7b_ai_nas_goal_status_packet"),
                "verdict": (goal or {}).get("verdict"),
            },
            "acceptance": {
                "local_latest": str(args.acceptance_json),
                "remote_json": report_remote_path(acceptance, "dream7b_ai_nas_acceptance_packet"),
                "verdict": (acceptance or {}).get("verdict"),
            },
            "final_audit": {
                "local_latest": str(args.final_audit_json),
                "remote_json": report_remote_path(final_audit, "dream7b_ai_nas_final_goal_audit"),
                "verdict": (final_audit or {}).get("verdict"),
            },
            "post_reboot_resume_runner": {
                "local_latest": str(args.resume_json),
                "remote_json": report_remote_path(resume, "dream7b_bpu_quality_post_reboot_resume_runner"),
                "verdict": (resume or {}).get("verdict"),
            },
            "safe_compile_handoff": {
                "local_latest": str(args.safe_compile_handoff_json),
                "remote_json": report_remote_path(safe_compile_handoff, "dream7b_bpu_quality_safe_compile_handoff"),
                "verdict": (safe_compile_handoff or {}).get("verdict"),
                "operator_may_run_compile": (safe_compile_handoff or {}).get("operator_may_run_compile"),
            },
        },
        "delivery_boundaries": {
            "route_a_deliverable_now": demo_delivery_ready,
            "route_b_promotion_ready": (acceptance or {}).get("route_b_promotion_ready") is True,
            "generic_generation_promotion_claim": acceptance_summary.get("generic_generation_promotion_claim"),
            "generic_generation_elapsed_ms": acceptance_summary.get("generic_generation_elapsed_ms"),
            "do_not_claim_full_goal_complete": not full_goal_complete,
        },
        "exclusions": [
            "private NAS contents",
            "private keys and tokens",
            "raw personal logs",
            "oversized generated model artifacts",
            "candidate HBM artifacts until manifest verification passes",
        ],
        "next_actions": [
            "Use Route A as the current demo package.",
            "Apply the pagefile handoff only from an operator-approved elevated PowerShell session, then reboot.",
        "After reboot, run dream7b_bpu_quality_post_reboot_resume_runner.py --run-preflight so rank-1 state-dict and compile-preflight evidence match the rank-1 candidate.",
            "Do not start HBM compile until capacity is ready and compile admission admits exactly the rank-1 candidate.",
            "Promote Route B only after rollback, logits, Chinese generation, same-workload, promotion, goal-status, acceptance, and final-audit reports pass.",
        ],
        "policy": {
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
            "production_write_performed_by_this_probe": False,
            "private_data_packaged_by_this_probe": False,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B AI-NAS Delivery Manifest",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- delivery_manifest_ready: `{payload['delivery_manifest_ready']}`",
        f"- demo_delivery_ready: `{payload['demo_delivery_ready']}`",
        f"- full_goal_complete: `{payload['full_goal_complete']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## NAS Evidence", ""])
    for key, item in payload["nas_evidence"].items():
        lines.append(f"- {key}: verdict=`{item['verdict']}` remote_json=`{item['remote_json']}`")
    lines.extend(["", "## Release Files", ""])
    for item in payload["release_files"]:
        lines.append(
            f"- `{item['path']}` exists=`{item['exists']}` size=`{item['size_bytes']}` sha256=`{item['sha256']}`"
        )
    lines.extend(["", "## Exclusions", ""])
    lines.extend(f"- {item}" for item in payload["exclusions"])
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal-status-json", type=Path, default=DEFAULT_GOAL_STATUS_JSON)
    parser.add_argument("--acceptance-json", type=Path, default=DEFAULT_ACCEPTANCE_JSON)
    parser.add_argument("--final-audit-json", type=Path, default=DEFAULT_FINAL_AUDIT_JSON)
    parser.add_argument("--resume-json", type=Path, default=DEFAULT_RESUME_JSON)
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
    return 0 if payload["delivery_manifest_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
