#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
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
    get_path,
    now_stamp,
    read_json,
    sync_to_nas,
    write_latest,
)


STEM = "dream7b_bpu_quality_safe_compile_handoff"
DEFAULT_PACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_candidate_pack_latest.json"
DEFAULT_CAPACITY_VERIFIER_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_capacity_post_reboot_verifier_latest.json"
DEFAULT_CAPACITY_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_capacity_unblock_plan_latest.json"
DEFAULT_PREFLIGHT_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_preflight_runner_latest.json"
DEFAULT_ADMISSION_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_compile_admission_guard_latest.json"
DEFAULT_POST_REBOOT_RUNNER_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_post_reboot_resume_runner_latest.json"


def report_ref(path: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "loaded": payload is not None,
        "verdict": payload.get("verdict") if payload else None,
        "summary": payload.get("summary") if payload else {},
        "errors": payload.get("errors") if payload else [],
        "blockers": payload.get("blockers") if payload else [],
    }


def candidate_by_id(pack: dict[str, Any] | None, candidate_id: str) -> dict[str, Any]:
    for candidate in (pack or {}).get("candidates") or []:
        if candidate.get("id") == candidate_id:
            return candidate
    return {}


def selected_candidate_ids(preflight: dict[str, Any] | None) -> list[str]:
    return [str(item) for item in (preflight or {}).get("selected_candidate_ids") or []]


def admitted_rows(admission: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [row for row in (admission or {}).get("classifications") or [] if row.get("command_admitted")]


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    pack = read_json(args.pack_json)
    verifier = read_json(args.capacity_verifier_json)
    capacity = read_json(args.capacity_json)
    preflight = read_json(args.preflight_json)
    admission = read_json(args.admission_json)
    runner = read_json(args.post_reboot_runner_json)
    candidate = candidate_by_id(pack, args.candidate_id)
    selected = selected_candidate_ids(preflight)
    admitted = admitted_rows(admission)
    admitted_candidate_ids = [row.get("candidate_id") for row in admitted]
    admitted_compile_command = admitted[0].get("proposed_command") if len(admitted) == 1 else ""
    rank1_compile_command = str(get_path(candidate, "commands", "compile_after_capacity_gate_only", default="") or "")

    checks = {
        "candidate_pack_ok": get_path(pack, "verdict") == "ok_dream7b_bpu_quality_candidate_pack",
        "candidate_present": bool(candidate),
        "candidate_is_rank1": get_path(candidate, "rank") == 1,
        "capacity_post_reboot_verifier_ready": get_path(verifier, "verdict")
        == "ready_dream7b_bpu_quality_capacity_post_reboot_verifier",
        "capacity_unblock_ready": get_path(capacity, "verdict") == "ready_dream7b_bpu_quality_capacity_unblock_plan",
        "capacity_does_not_block_compile": get_path(capacity, "recommendation", "do_not_start_compile_now") is False,
        "preflight_ok": get_path(preflight, "verdict") == "ok_dream7b_bpu_quality_preflight_runner",
        "preflight_matches_rank1_candidate": args.candidate_id in selected,
        "preflight_includes_state_dict": get_path(preflight, "run_state_dict") is True,
        "preflight_includes_compile_preflight": get_path(preflight, "run_compile_preflight") is True,
        "admission_guard_ok": get_path(admission, "verdict") == "ok_dream7b_bpu_quality_compile_admission_guard",
        "exactly_one_command_admitted": len(admitted) == 1,
        "admitted_command_is_rank1": admitted_candidate_ids == [args.candidate_id],
        "admitted_command_matches_pack": bool(admitted_compile_command)
        and admitted_compile_command.strip() == rank1_compile_command.strip(),
        "post_reboot_runner_ran_preflight": get_path(runner, "run_preflight") is True,
        "post_reboot_runner_compile_ready": get_path(runner, "verdict")
        == "ready_for_compile_dream7b_bpu_quality_post_reboot_resume_runner",
    }
    required_keys = [
        "candidate_pack_ok",
        "candidate_present",
        "candidate_is_rank1",
        "capacity_post_reboot_verifier_ready",
        "capacity_unblock_ready",
        "capacity_does_not_block_compile",
        "preflight_ok",
        "preflight_matches_rank1_candidate",
        "preflight_includes_state_dict",
        "preflight_includes_compile_preflight",
        "admission_guard_ok",
        "exactly_one_command_admitted",
        "admitted_command_is_rank1",
        "admitted_command_matches_pack",
    ]
    blockers = [key for key in required_keys if checks.get(key) is not True]
    advisory_blockers = [
        key
        for key in ("post_reboot_runner_ran_preflight", "post_reboot_runner_compile_ready")
        if checks.get(key) is not True
    ]
    operator_may_run_compile = not blockers
    verdict = (
        "ready_dream7b_bpu_quality_safe_compile_handoff"
        if operator_may_run_compile
        else "blocked_dream7b_bpu_quality_safe_compile_handoff"
    )
    return {
        "generated_at": generated_at(),
        "verdict": verdict,
        "candidate_id": args.candidate_id,
        "operator_may_run_compile": operator_may_run_compile,
        "admitted_compile_command": admitted_compile_command if operator_may_run_compile else "",
        "rank1_compile_command_under_lock": rank1_compile_command,
        "blockers": blockers,
        "advisory_blockers": advisory_blockers,
        "checks": checks,
        "admitted_candidate_ids": admitted_candidate_ids,
        "latest_preflight_selected_candidate_ids": selected,
        "source_reports": {
            "candidate_pack": report_ref(args.pack_json, pack),
            "capacity_post_reboot_verifier": report_ref(args.capacity_verifier_json, verifier),
            "capacity_unblock": report_ref(args.capacity_json, capacity),
            "preflight": report_ref(args.preflight_json, preflight),
            "compile_admission": report_ref(args.admission_json, admission),
            "post_reboot_resume_runner": report_ref(args.post_reboot_runner_json, runner),
        },
        "next_actions": [
            "Do not run the rank-1 HBM compile command until operator_may_run_compile is true.",
            "If blocked by capacity, apply the approved pagefile handoff from elevated PowerShell, reboot, then rerun post_reboot_resume_runner.py --run-preflight.",
            "If blocked by preflight_candidate_mismatch, rerun rank-1 state-dict and compile-preflight before admission.",
            "After a compile finishes, run rollback, logits, Chinese generation, same-workload, promotion, goal-status, acceptance, final-audit, and delivery-manifest reports.",
        ],
        "policy": {
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
            "production_write_performed_by_this_probe": False,
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
            "route_a_must_remain_default": True,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B BPU Quality Safe Compile Handoff",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate_id: `{payload['candidate_id']}`",
        f"- operator_may_run_compile: `{payload['operator_may_run_compile']}`",
        "- compile_started_by_this_probe: `False`",
        "- service_restarted_by_this_probe: `False`",
        "- production_write_performed_by_this_probe: `False`",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{item}`" for item in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Advisory Blockers", ""])
    if payload["advisory_blockers"]:
        lines.extend(f"- `{item}`" for item in payload["advisory_blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Rank-1 Command Under Lock", "", "```powershell"])
    lines.append(payload["rank1_compile_command_under_lock"] or "")
    lines.extend(["```", "", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--capacity-verifier-json", type=Path, default=DEFAULT_CAPACITY_VERIFIER_JSON)
    parser.add_argument("--capacity-json", type=Path, default=DEFAULT_CAPACITY_JSON)
    parser.add_argument("--preflight-json", type=Path, default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--admission-json", type=Path, default=DEFAULT_ADMISSION_JSON)
    parser.add_argument("--post-reboot-runner-json", type=Path, default=DEFAULT_POST_REBOOT_RUNNER_JSON)
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
    return 0 if payload["operator_may_run_compile"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
