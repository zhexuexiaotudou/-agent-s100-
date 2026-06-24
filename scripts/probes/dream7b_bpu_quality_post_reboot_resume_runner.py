#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dream7b_bpu_quality_validation_common import (
    DEFAULT_CANDIDATE_ID,
    DEFAULT_KNOWN_HOSTS,
    DEFAULT_OUT_ROOT,
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_REPORT_ROOT,
    DEFAULT_SSH_KEY,
    generated_at,
    read_json,
    now_stamp,
    sync_to_nas,
    write_latest,
)


STEM = "dream7b_bpu_quality_post_reboot_resume_runner"
PYTHON_EXE = r"C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
DEFAULT_PREFLIGHT_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_preflight_runner_latest.json"
DEFAULT_FINAL_AUDIT_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_final_goal_audit_latest.json"


def run_step(step_id: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        elapsed = round(time.perf_counter() - started, 3)
        stdout = completed.stdout.strip()
        payload: dict[str, Any] | None = None
        try:
            payload = json.loads(stdout) if stdout else None
        except json.JSONDecodeError:
            payload = None
        return {
            "id": step_id,
            "command": command,
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "verdict": payload.get("verdict") if payload else None,
            "ready": payload.get("ready") if payload else None,
            "report_dir": payload.get("report_dir") if payload else None,
            "sync_remote_dir": ((payload.get("sync") or {}).get("remote_dir") if payload else None),
            "errors": payload.get("errors") if payload else None,
            "blockers": payload.get("blockers") if payload else None,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": completed.stderr.strip()[-4000:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - started, 3)
        return {
            "id": step_id,
            "command": command,
            "returncode": None,
            "elapsed_seconds": elapsed,
            "verdict": None,
            "ready": None,
            "report_dir": None,
            "sync_remote_dir": None,
            "errors": ["timeout"],
            "blockers": ["timeout"],
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "timed_out": True,
        }


def build_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    base = [PYTHON_EXE]
    steps: list[dict[str, Any]] = [
        {
            "id": "capacity_post_reboot_verifier",
            "command": base + ["scripts/probes/dream7b_bpu_quality_capacity_post_reboot_verifier.py"],
            "timeout": args.light_timeout,
            "required_for_compile": True,
        },
        {
            "id": "capacity_unblock_plan",
            "command": base + ["scripts/probes/dream7b_bpu_quality_capacity_unblock_plan.py"],
            "timeout": args.light_timeout,
            "required_for_compile": True,
        },
    ]
    if args.run_preflight:
        command = base + [
            "scripts/probes/dream7b_bpu_quality_preflight_runner.py",
            "--candidate-id",
            args.candidate_id,
            "--run-state-dict",
            "--run-compile-preflight",
        ]
        if not args.run_state_dict:
            command.remove("--run-state-dict")
            command.append("--no-run-state-dict")
        steps.append(
            {
                "id": "rank1_preflight_runner",
                "command": command,
                "timeout": args.preflight_timeout,
                "required_for_compile": True,
            }
        )
    else:
        steps.append(
            {
                "id": "rank1_preflight_runner",
                "command": [],
                "timeout": 0,
                "required_for_compile": True,
                "skipped": True,
                "skip_reason": "use --run-preflight after the pagefile reboot when compile-preflight should be refreshed",
            }
        )
    steps.extend(
        [
            {
                "id": "compile_admission_guard",
                "command": base + ["scripts/probes/dream7b_bpu_quality_compile_admission_guard.py"],
                "timeout": args.light_timeout,
                "required_for_compile": True,
            },
            {
                "id": "post_compile_validation_matrix",
                "command": base + ["scripts/probes/dream7b_bpu_quality_post_compile_validation_matrix.py"],
                "timeout": args.light_timeout,
                "required_for_promotion": True,
            },
            {
                "id": "promotion_gate",
                "command": base + ["scripts/probes/dream7b_bpu_quality_promotion_gate.py"],
                "timeout": args.light_timeout,
                "required_for_promotion": True,
            },
            {
                "id": "goal_status_packet",
                "command": base + ["scripts/probes/dream7b_ai_nas_goal_status_packet.py"],
                "timeout": args.light_timeout,
                "required_for_acceptance": True,
            },
            {
                "id": "acceptance_packet",
                "command": base + ["scripts/probes/dream7b_ai_nas_acceptance_packet.py"],
                "timeout": args.light_timeout,
                "required_for_acceptance": True,
            },
            {
                "id": "final_goal_audit",
                "command": base + ["scripts/probes/dream7b_ai_nas_final_goal_audit.py"],
                "timeout": args.light_timeout,
                "required_for_acceptance": True,
            },
        ]
    )
    return steps


def latest_preflight_state(candidate_id: str) -> dict[str, Any]:
    payload = read_json(DEFAULT_PREFLIGHT_JSON)
    selected = [str(item) for item in (payload or {}).get("selected_candidate_ids") or []]
    return {
        "path": str(DEFAULT_PREFLIGHT_JSON),
        "exists": DEFAULT_PREFLIGHT_JSON.exists(),
        "verdict": (payload or {}).get("verdict"),
        "selected_candidate_ids": selected,
        "matches_candidate": candidate_id in selected,
    }


def latest_final_audit_summary() -> dict[str, Any]:
    payload = read_json(DEFAULT_FINAL_AUDIT_JSON)
    return {
        "path": str(DEFAULT_FINAL_AUDIT_JSON),
        "exists": DEFAULT_FINAL_AUDIT_JSON.exists(),
        "verdict": (payload or {}).get("verdict"),
        "all_complete": (payload or {}).get("all_complete"),
        "demo_delivery_ready": (payload or {}).get("demo_delivery_ready"),
        "summary": (payload or {}).get("summary") or {},
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    planned_steps = build_steps(args)
    results: list[dict[str, Any]] = []
    for step in planned_steps:
        if step.get("skipped"):
            results.append(
                {
                    "id": step["id"],
                    "skipped": True,
                    "skip_reason": step["skip_reason"],
                    "command": step["command"],
                    "returncode": None,
                    "verdict": None,
                    "ready": None,
                    "errors": [],
                    "blockers": [],
                }
            )
            continue
        results.append(run_step(step["id"], step["command"], step["timeout"]))

    by_id = {row["id"]: row for row in results}
    capacity_ready = (
        by_id.get("capacity_post_reboot_verifier", {}).get("verdict")
        == "ready_dream7b_bpu_quality_capacity_post_reboot_verifier"
        and by_id.get("capacity_unblock_plan", {}).get("verdict")
        == "ready_dream7b_bpu_quality_capacity_unblock_plan"
    )
    admission_ok = by_id.get("compile_admission_guard", {}).get("verdict") == "ok_dream7b_bpu_quality_compile_admission_guard"
    matrix_ready = (
        by_id.get("post_compile_validation_matrix", {}).get("verdict")
        == "ready_dream7b_bpu_quality_post_compile_validation_matrix"
    )
    acceptance_verdict = by_id.get("acceptance_packet", {}).get("verdict")
    final_audit = latest_final_audit_summary()
    preflight_state = latest_preflight_state(args.candidate_id)
    demo_delivery_ready = acceptance_verdict in (
        "partial_dream7b_ai_nas_acceptance_packet_route_a_ready_route_b_blocked",
        "complete_dream7b_ai_nas_acceptance_packet",
    )
    full_goal_complete = acceptance_verdict == "complete_dream7b_ai_nas_acceptance_packet"
    hard_failures = [
        row["id"]
        for row in results
        if row.get("returncode") not in (0, None) and row.get("verdict") is None and not row.get("skipped")
    ]
    verdict = (
        "complete_dream7b_bpu_quality_post_reboot_resume_runner"
        if full_goal_complete
        else "ready_for_compile_dream7b_bpu_quality_post_reboot_resume_runner"
        if capacity_ready and admission_ok
        else "blocked_dream7b_bpu_quality_post_reboot_resume_runner"
    )
    if hard_failures:
        verdict = "error_dream7b_bpu_quality_post_reboot_resume_runner"
    return {
        "generated_at": generated_at(),
        "verdict": verdict,
        "candidate_id": args.candidate_id,
        "run_preflight": args.run_preflight,
        "run_state_dict": args.run_state_dict,
        "summary": {
            "capacity_ready": capacity_ready,
            "compile_admission_guard_ok": admission_ok,
            "post_compile_matrix_ready": matrix_ready,
            "demo_delivery_ready": demo_delivery_ready,
            "full_goal_complete": full_goal_complete,
            "rank1_preflight_matches_candidate": preflight_state["matches_candidate"],
            "latest_preflight_selected_candidate_ids": preflight_state["selected_candidate_ids"],
            "final_audit_verdict": final_audit["verdict"],
            "final_audit_required_pass_count": final_audit["summary"].get("required_pass_count"),
            "final_audit_required_blocked_count": final_audit["summary"].get("required_blocked_count"),
            "final_audit_required_fail_count": final_audit["summary"].get("required_fail_count"),
            "hard_failures": hard_failures,
            "step_count": len(results),
            "executed_step_count": sum(1 for row in results if not row.get("skipped")),
        },
        "latest_preflight": preflight_state,
        "latest_final_audit": final_audit,
        "steps": results,
        "next_actions": [
            "If capacity is still blocked, apply the capacity operator handoff from elevated PowerShell and reboot.",
            "After reboot, rerun this script with --run-preflight to refresh rank-1 state-dict and compile-preflight before compile admission; this is required if latest_preflight.selected_candidate_ids does not contain the rank-1 candidate.",
            "Start HBM compile only if capacity is ready and compile admission admits exactly the rank-1 sentinel.",
            "After compile, rerun rollback, logits, generation, same-workload, promotion, goal-status, and acceptance packets.",
        ],
        "policy": {
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
            "production_write_performed_by_this_probe": False,
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B BPU Quality Post-Reboot Resume Runner",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate_id: `{payload['candidate_id']}`",
        f"- run_preflight: `{payload['run_preflight']}`",
        f"- run_state_dict: `{payload['run_state_dict']}`",
        f"- capacity_ready: `{summary['capacity_ready']}`",
        f"- compile_admission_guard_ok: `{summary['compile_admission_guard_ok']}`",
        f"- post_compile_matrix_ready: `{summary['post_compile_matrix_ready']}`",
        f"- demo_delivery_ready: `{summary['demo_delivery_ready']}`",
        f"- full_goal_complete: `{summary['full_goal_complete']}`",
        f"- rank1_preflight_matches_candidate: `{summary['rank1_preflight_matches_candidate']}`",
        f"- latest_preflight_selected_candidate_ids: `{summary['latest_preflight_selected_candidate_ids']}`",
        f"- final_audit_verdict: `{summary['final_audit_verdict']}`",
        "- compile_started_by_this_probe: `False`",
        "- service_restarted_by_this_probe: `False`",
        "",
        "## Steps",
        "",
    ]
    for row in payload["steps"]:
        lines.append(
            f"- {row['id']}: skipped=`{row.get('skipped', False)}` returncode=`{row.get('returncode')}` "
            f"verdict=`{row.get('verdict')}` remote=`{row.get('sync_remote_dir')}`"
        )
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument("--run-preflight", action="store_true")
    parser.add_argument("--run-state-dict", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--light-timeout", type=int, default=120)
    parser.add_argument("--preflight-timeout", type=int, default=600)
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
    return 0 if payload["verdict"].startswith(("complete_", "ready_for_compile_")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
