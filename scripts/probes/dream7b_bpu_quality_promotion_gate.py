#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_PACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_candidate_pack_latest.json"
DEFAULT_CAPACITY_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_capacity_unblock_plan_latest.json"
DEFAULT_ADMISSION_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_compile_admission_guard_latest.json"
DEFAULT_PREFLIGHT_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_preflight_runner_latest.json"
DEFAULT_GOAL_STATUS_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_goal_status_packet_latest.json"
DEFAULT_LOGITS_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_logits_diagnostics_latest.json"
DEFAULT_GENERATION_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_generation_quality_latest.json"
DEFAULT_SAME_WORKLOAD_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_same_workload_compare_latest.json"
DEFAULT_ROLLBACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_rollback_report_latest.json"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
ALLOWED_FIRST_CANDIDATE = "seg27_28_lmheadq16_last_token_sentinel"


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def get_path(payload: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    cursor: Any = payload
    for key in keys:
        if not isinstance(cursor, dict):
            return default
        cursor = cursor.get(key)
    return default if cursor is None else cursor


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def report_ref(path: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "loaded": payload is not None,
        "verdict": payload.get("verdict") if payload else None,
        "summary": payload.get("summary") if payload else {},
        "decision": payload.get("decision") if payload else {},
        "errors": payload.get("errors") if payload else [],
    }


def candidate_by_id(pack: dict[str, Any] | None, candidate_id: str) -> dict[str, Any]:
    for candidate in (pack or {}).get("candidates") or []:
        if candidate.get("id") == candidate_id:
            return candidate
    return {}


def preflight_covers_candidate(preflight: dict[str, Any] | None, candidate_id: str) -> bool:
    selected = [str(item) for item in get_path(preflight, "selected_candidate_ids", default=[]) or []]
    return candidate_id in selected


def admitted_count(admission: dict[str, Any] | None) -> int:
    return sum(1 for row in (admission or {}).get("classifications") or [] if row.get("command_admitted"))


def check_logit_gate(payload: dict[str, Any] | None, args: argparse.Namespace) -> dict[str, Any]:
    if payload is None:
        return {"ok": False, "blockers": ["logits_diagnostics_missing"], "evidence": {}}
    summary = payload.get("summary") or payload
    argmax_agreement = as_float(summary.get("argmax_agreement"), -1.0)
    top1_probability = as_float(summary.get("top1_probability"), -1.0)
    non_uniform = summary.get("non_uniform_top_probabilities")
    if non_uniform is None:
        non_uniform = top1_probability > 0.0
    blockers = []
    if argmax_agreement < args.min_argmax_agreement:
        blockers.append("argmax_agreement_below_threshold")
    if top1_probability < args.min_top1_probability:
        blockers.append("top1_probability_below_threshold")
    if non_uniform is not True:
        blockers.append("top_probabilities_not_non_uniform")
    return {
        "ok": not blockers,
        "blockers": blockers,
        "evidence": {
            "verdict": payload.get("verdict"),
            "argmax_agreement": argmax_agreement,
            "top1_probability": top1_probability,
            "non_uniform_top_probabilities": non_uniform,
            "thresholds": {
                "min_argmax_agreement": args.min_argmax_agreement,
                "min_top1_probability": args.min_top1_probability,
            },
        },
    }


def check_generation_gate(payload: dict[str, Any] | None, args: argparse.Namespace) -> dict[str, Any]:
    if payload is None:
        return {"ok": False, "blockers": ["generation_quality_missing"], "evidence": {}}
    summary = payload.get("summary") or payload
    readable_count = as_int(summary.get("readable_chinese_prompt_count"), 0)
    failed_count = as_int(summary.get("failed_prompt_count"), 0)
    blockers = []
    if readable_count < args.min_readable_chinese_prompts:
        blockers.append("readable_chinese_prompt_count_below_threshold")
    if failed_count != 0:
        blockers.append("generation_failed_prompt_count_nonzero")
    return {
        "ok": not blockers,
        "blockers": blockers,
        "evidence": {
            "verdict": payload.get("verdict"),
            "readable_chinese_prompt_count": readable_count,
            "failed_prompt_count": failed_count,
            "thresholds": {
                "min_readable_chinese_prompts": args.min_readable_chinese_prompts,
            },
        },
    }


def check_same_workload_gate(payload: dict[str, Any] | None, args: argparse.Namespace) -> dict[str, Any]:
    if payload is None:
        return {"ok": False, "blockers": ["same_workload_compare_missing"], "evidence": {}}
    summary = payload.get("summary") or payload
    same_workload = summary.get("same_workload")
    candidate_ms = as_float(summary.get("candidate_ms_per_request"), 1e9)
    baseline_ms = as_float(summary.get("baseline_ms_per_request"), 0.0)
    processed = as_int(summary.get("processed_request_count"), 0)
    complements = summary.get("complements_baseline")
    blockers = []
    if same_workload is not True:
        blockers.append("not_same_workload")
    if processed < args.min_same_workload_requests:
        blockers.append("processed_request_count_below_threshold")
    if baseline_ms <= 0:
        blockers.append("baseline_ms_per_request_missing")
    if candidate_ms > baseline_ms and complements is not True:
        blockers.append("candidate_slower_without_complement_reason")
    return {
        "ok": not blockers,
        "blockers": blockers,
        "evidence": {
            "verdict": payload.get("verdict"),
            "same_workload": same_workload,
            "processed_request_count": processed,
            "candidate_ms_per_request": candidate_ms,
            "baseline_ms_per_request": baseline_ms,
            "complements_baseline": complements,
            "thresholds": {
                "min_same_workload_requests": args.min_same_workload_requests,
            },
        },
    }


def check_rollback_gate(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"ok": False, "blockers": ["rollback_report_missing"], "evidence": {}}
    summary = payload.get("summary") or payload
    rollback_ready = summary.get("rollback_ready")
    production_unchanged = summary.get("production_path_unchanged")
    service_restarted = summary.get("service_restarted")
    overwrote_18888 = summary.get("overwrote_18888")
    seq16_deleted = summary.get("seq16_baseline_deleted")
    candidate_artifact_present = summary.get("candidate_artifact_present")
    candidate_manifest_verified = summary.get("candidate_manifest_verified")
    blockers = []
    if rollback_ready is not True:
        blockers.append("rollback_not_ready")
    if production_unchanged is not True:
        blockers.append("production_path_changed")
    if service_restarted is True:
        blockers.append("service_restarted")
    if overwrote_18888 is True:
        blockers.append("overwrote_18888")
    if seq16_deleted is True:
        blockers.append("seq16_baseline_deleted")
    if candidate_artifact_present is not True:
        blockers.append("rollback_candidate_artifact_missing")
    if candidate_manifest_verified is not True:
        blockers.append("rollback_candidate_manifest_not_verified")
    return {
        "ok": not blockers,
        "blockers": blockers,
        "evidence": {
            "verdict": payload.get("verdict"),
            "rollback_ready": rollback_ready,
            "production_path_unchanged": production_unchanged,
            "service_restarted": service_restarted,
            "overwrote_18888": overwrote_18888,
            "seq16_baseline_deleted": seq16_deleted,
            "candidate_artifact_present": candidate_artifact_present,
            "candidate_manifest_verified": candidate_manifest_verified,
        },
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    pack = read_json(args.pack_json)
    capacity = read_json(args.capacity_json)
    admission = read_json(args.admission_json)
    preflight = read_json(args.preflight_json)
    goal = read_json(args.goal_status_json)
    logits = read_json(args.logits_json)
    generation = read_json(args.generation_json)
    same_workload = read_json(args.same_workload_json)
    rollback = read_json(args.rollback_json)
    candidate = candidate_by_id(pack, args.candidate_id)

    preconditions = {
        "candidate_pack_ok": get_path(pack, "verdict") == "ok_dream7b_bpu_quality_candidate_pack",
        "candidate_is_rank1": args.candidate_id == ALLOWED_FIRST_CANDIDATE,
        "candidate_present": bool(candidate),
        "capacity_ready": get_path(capacity, "verdict") == "ready_dream7b_bpu_quality_capacity_unblock_plan",
        "compile_admitted": admitted_count(admission) == 1,
        "preflight_ok": get_path(preflight, "verdict") == "ok_dream7b_bpu_quality_preflight_runner",
        "preflight_matches_candidate": preflight_covers_candidate(preflight, args.candidate_id),
        "route_a_still_ready": get_path(goal, "evaluation", "route_a", "ready") is True,
        "goal_not_already_complete": get_path(goal, "evaluation", "goal_complete") is False,
    }
    gates = {
        "logits": check_logit_gate(logits, args),
        "generation": check_generation_gate(generation, args),
        "same_workload": check_same_workload_gate(same_workload, args),
        "rollback": check_rollback_gate(rollback),
    }
    precondition_blocker_labels = {
        "candidate_pack_ok": "candidate_pack_not_ok",
        "candidate_is_rank1": "candidate_not_allowed_first_rank",
        "candidate_present": "candidate_missing_from_pack",
        "capacity_ready": "capacity_not_ready",
        "compile_admitted": "compile_not_admitted",
        "preflight_ok": "preflight_not_ok",
        "preflight_matches_candidate": "preflight_candidate_mismatch",
        "route_a_still_ready": "route_a_not_ready",
        "goal_not_already_complete": "goal_already_complete_or_unreadable",
    }
    blockers = [precondition_blocker_labels[key] for key, ok in preconditions.items() if not ok]
    for gate_name, gate in gates.items():
        blockers.extend(f"{gate_name}:{item}" for item in gate["blockers"])
    promotion_admitted = not blockers
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ready_dream7b_bpu_quality_promotion_gate" if promotion_admitted else "blocked_dream7b_bpu_quality_promotion_gate",
        "candidate_id": args.candidate_id,
        "promotion_admitted": promotion_admitted,
        "production_change_allowed": False,
        "blockers": blockers,
        "source_reports": {
            "candidate_pack": report_ref(args.pack_json, pack),
            "capacity": report_ref(args.capacity_json, capacity),
            "compile_admission": report_ref(args.admission_json, admission),
            "preflight": report_ref(args.preflight_json, preflight),
            "goal_status": report_ref(args.goal_status_json, goal),
            "logits": report_ref(args.logits_json, logits),
            "generation": report_ref(args.generation_json, generation),
            "same_workload": report_ref(args.same_workload_json, same_workload),
            "rollback": report_ref(args.rollback_json, rollback),
        },
        "candidate": {
            "present": bool(candidate),
            "rank": candidate.get("rank"),
            "scope": candidate.get("scope"),
            "remote_output_root": candidate.get("remote_output_root"),
            "remote_report_root": candidate.get("remote_report_root"),
            "verification_after_compile": (pack or {}).get("verification_after_compile"),
        },
        "preconditions": preconditions,
        "gates": gates,
        "policy": {
            "allowed_first_candidate": ALLOWED_FIRST_CANDIDATE,
            "route_a_must_remain_default": True,
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B BPU Quality Promotion Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate_id: `{payload['candidate_id']}`",
        f"- promotion_admitted: `{payload['promotion_admitted']}`",
        "- production_change_allowed: `False`",
        "",
        "## Preconditions",
        "",
    ]
    for key, value in payload["preconditions"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Gates", ""])
    for key, gate in payload["gates"].items():
        lines.append(f"- {key}: ok=`{gate['ok']}` blockers=`{gate['blockers']}`")
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{item}`" for item in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Source Reports", ""])
    for key, ref in payload["source_reports"].items():
        lines.append(f"- {key}: exists=`{ref['exists']}` verdict=`{ref['verdict']}` path=`{ref['path']}`")
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_cmd(command: list[str], timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "args": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_command(args: argparse.Namespace, command: str, timeout: int = 90) -> dict[str, Any]:
    return run_cmd(
        [
            "ssh.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            command,
        ],
        timeout,
    )


def sync_to_nas(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    remote_dir = f"{args.remote_report_root.rstrip('/')}/{report_dir.name}"
    mkdir = ssh_command(args, f"mkdir -p {remote_dir}", timeout=30)
    if mkdir["returncode"] != 0:
        return {"ok": False, "remote_dir": remote_dir, "mkdir": mkdir}
    scp = run_cmd(
        [
            "scp.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            str(report_dir / "dream7b_bpu_quality_promotion_gate.json"),
            str(report_dir / "dream7b_bpu_quality_promotion_gate.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", default=ALLOWED_FIRST_CANDIDATE)
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--capacity-json", type=Path, default=DEFAULT_CAPACITY_JSON)
    parser.add_argument("--admission-json", type=Path, default=DEFAULT_ADMISSION_JSON)
    parser.add_argument("--preflight-json", type=Path, default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--goal-status-json", type=Path, default=DEFAULT_GOAL_STATUS_JSON)
    parser.add_argument("--logits-json", type=Path, default=DEFAULT_LOGITS_JSON)
    parser.add_argument("--generation-json", type=Path, default=DEFAULT_GENERATION_JSON)
    parser.add_argument("--same-workload-json", type=Path, default=DEFAULT_SAME_WORKLOAD_JSON)
    parser.add_argument("--rollback-json", type=Path, default=DEFAULT_ROLLBACK_JSON)
    parser.add_argument("--min-argmax-agreement", type=float, default=0.80)
    parser.add_argument("--min-top1-probability", type=float, default=0.05)
    parser.add_argument("--min-readable-chinese-prompts", type=int, default=3)
    parser.add_argument("--min-same-workload-requests", type=int, default=12288)
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
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = args.out_root / f"dream7b_bpu_quality_promotion_gate_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_promotion_gate.json"
    md_path = report_dir / "dream7b_bpu_quality_promotion_gate.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    if not args.no_sync:
        sync = sync_to_nas(args, report_dir)
        payload["sync"] = sync
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(md_path, payload)
        if sync.get("ok") is False:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
    latest_json = args.out_root / "dream7b_bpu_quality_promotion_gate_latest.json"
    latest_md = args.out_root / "dream7b_bpu_quality_promotion_gate_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
