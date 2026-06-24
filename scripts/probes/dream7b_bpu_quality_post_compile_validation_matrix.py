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
DEFAULT_ROLLBACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_rollback_report_latest.json"
DEFAULT_PROMOTION_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_promotion_gate_latest.json"
DEFAULT_LOGITS_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_logits_diagnostics_latest.json"
DEFAULT_GENERATION_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_generation_quality_latest.json"
DEFAULT_SAME_WORKLOAD_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_same_workload_compare_latest.json"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_CANDIDATE_ID = "seg27_28_lmheadq16_last_token_sentinel"
PYTHON_EXE = r"C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"


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


def preflight_covers_candidate(preflight: dict[str, Any] | None, candidate_id: str) -> bool:
    selected = [str(item) for item in get_path(preflight, "selected_candidate_ids", default=[]) or []]
    return candidate_id in selected


def admitted_count(admission: dict[str, Any] | None) -> int:
    return sum(1 for row in (admission or {}).get("classifications") or [] if row.get("command_admitted"))


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


def validation_item(
    *,
    item_id: str,
    title: str,
    target_json: Path,
    payload: dict[str, Any] | None,
    required_fields: dict[str, Any],
    thresholds: dict[str, Any],
    producer_command: str,
    must_run_after: list[str],
) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "target_json": str(target_json),
        "exists": target_json.exists(),
        "verdict": payload.get("verdict") if payload else None,
        "ready": False,
        "required_fields": required_fields,
        "thresholds": thresholds,
        "producer_command": producer_command,
        "must_run_after": must_run_after,
    }


def evaluate_logits_report(payload: dict[str, Any] | None, args: argparse.Namespace) -> dict[str, Any]:
    if payload is None:
        return {"ready": False, "blockers": ["logits_diagnostics_missing"], "evidence": {}}
    summary = payload.get("summary") or payload
    argmax_agreement = as_float(summary.get("argmax_agreement"), -1.0)
    top1_probability = as_float(summary.get("top1_probability"), -1.0)
    non_uniform = summary.get("non_uniform_top_probabilities")
    if non_uniform is None:
        non_uniform = top1_probability > 0.0
    blockers: list[str] = []
    if argmax_agreement < args.min_argmax_agreement:
        blockers.append("argmax_agreement_below_threshold")
    if top1_probability < args.min_top1_probability:
        blockers.append("top1_probability_below_threshold")
    if non_uniform is not True:
        blockers.append("top_probabilities_not_non_uniform")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "evidence": {
            "argmax_agreement": argmax_agreement,
            "top1_probability": top1_probability,
            "non_uniform_top_probabilities": non_uniform,
        },
    }


def evaluate_generation_report(payload: dict[str, Any] | None, args: argparse.Namespace) -> dict[str, Any]:
    if payload is None:
        return {"ready": False, "blockers": ["generation_quality_missing"], "evidence": {}}
    summary = payload.get("summary") or payload
    readable_count = as_int(summary.get("readable_chinese_prompt_count"), 0)
    failed_count = as_int(summary.get("failed_prompt_count"), 0)
    blockers: list[str] = []
    if readable_count < args.min_readable_chinese_prompts:
        blockers.append("readable_chinese_prompt_count_below_threshold")
    if failed_count != 0:
        blockers.append("generation_failed_prompt_count_nonzero")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "evidence": {
            "readable_chinese_prompt_count": readable_count,
            "failed_prompt_count": failed_count,
        },
    }


def evaluate_same_workload_report(payload: dict[str, Any] | None, args: argparse.Namespace) -> dict[str, Any]:
    if payload is None:
        return {"ready": False, "blockers": ["same_workload_compare_missing"], "evidence": {}}
    summary = payload.get("summary") or payload
    same_workload = summary.get("same_workload")
    processed = as_int(summary.get("processed_request_count"), 0)
    baseline_ms = as_float(summary.get("baseline_ms_per_request"), 0.0)
    candidate_ms = as_float(summary.get("candidate_ms_per_request"), 1e9)
    complements = summary.get("complements_baseline")
    blockers: list[str] = []
    if same_workload is not True:
        blockers.append("not_same_workload")
    if processed < args.min_same_workload_requests:
        blockers.append("processed_request_count_below_threshold")
    if baseline_ms <= 0:
        blockers.append("baseline_ms_per_request_missing")
    if candidate_ms > baseline_ms and complements is not True:
        blockers.append("candidate_slower_without_complement_reason")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "evidence": {
            "same_workload": same_workload,
            "processed_request_count": processed,
            "baseline_ms_per_request": baseline_ms,
            "candidate_ms_per_request": candidate_ms,
            "complements_baseline": complements,
        },
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    pack = read_json(args.pack_json)
    capacity = read_json(args.capacity_json)
    admission = read_json(args.admission_json)
    preflight = read_json(args.preflight_json)
    rollback = read_json(args.rollback_json)
    promotion = read_json(args.promotion_json)
    logits = read_json(args.logits_json)
    generation = read_json(args.generation_json)
    same_workload = read_json(args.same_workload_json)
    candidate = candidate_by_id(pack, args.candidate_id)

    preconditions = {
        "candidate_pack_ok": get_path(pack, "verdict") == "ok_dream7b_bpu_quality_candidate_pack",
        "candidate_present": bool(candidate),
        "candidate_is_rank1": get_path(candidate, "rank") == 1,
        "capacity_ready": get_path(capacity, "verdict") == "ready_dream7b_bpu_quality_capacity_unblock_plan",
        "rank1_preflight_ok": get_path(preflight, "verdict") == "ok_dream7b_bpu_quality_preflight_runner",
        "rank1_preflight_matches_candidate": preflight_covers_candidate(preflight, args.candidate_id),
        "compile_admitted": admitted_count(admission) == 1,
        "candidate_artifact_present": get_path(rollback, "summary", "candidate_artifact_present") is True,
        "candidate_manifest_verified": get_path(rollback, "summary", "candidate_manifest_verified") is True,
        "rollback_ready": get_path(rollback, "summary", "rollback_ready") is True,
        "promotion_ready": get_path(promotion, "verdict") == "ready_dream7b_bpu_quality_promotion_gate",
    }
    compile_allowed_now = (
        preconditions["candidate_pack_ok"]
        and preconditions["candidate_present"]
        and preconditions["candidate_is_rank1"]
        and preconditions["capacity_ready"]
        and preconditions["rank1_preflight_ok"]
        and preconditions["rank1_preflight_matches_candidate"]
        and preconditions["compile_admitted"]
    )

    target_reports = {
        "logits_diagnostics": validation_item(
            item_id="logits_diagnostics",
            title="BPU logits diagnostic against GGUF reference",
            target_json=args.logits_json,
            payload=logits,
            required_fields={
                "summary.argmax_agreement": "float",
                "summary.top1_probability": "float",
                "summary.non_uniform_top_probabilities": "bool",
            },
            thresholds={
                "argmax_agreement_min": args.min_argmax_agreement,
                "top1_probability_min": args.min_top1_probability,
                "non_uniform_top_probabilities": True,
            },
            producer_command=(
                f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_logits_diagnostics.py"
            ),
            must_run_after=["candidate artifact manifest verified", "candidate runtime smoke started outside production"],
        ),
        "generation_quality": validation_item(
            item_id="generation_quality",
            title="Three-prompt Chinese generation quality",
            target_json=args.generation_json,
            payload=generation,
            required_fields={
                "summary.readable_chinese_prompt_count": "int",
                "summary.failed_prompt_count": "int",
            },
            thresholds={
                "readable_chinese_prompt_count_min": args.min_readable_chinese_prompts,
                "failed_prompt_count": 0,
            },
            producer_command=(
                f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_generation_quality.py"
            ),
            must_run_after=["candidate runtime smoke started outside production", "logits diagnostics not obviously saturated"],
        ),
        "same_workload_compare": validation_item(
            item_id="same_workload_compare",
            title="Same-workload latency and throughput compare",
            target_json=args.same_workload_json,
            payload=same_workload,
            required_fields={
                "summary.same_workload": "bool",
                "summary.processed_request_count": "int",
                "summary.baseline_ms_per_request": "float",
                "summary.candidate_ms_per_request": "float",
                "summary.complements_baseline": "bool",
            },
            thresholds={
                "same_workload": True,
                "processed_request_count_min": args.min_same_workload_requests,
                "candidate_must_not_be_slower_unless_complements_baseline": True,
            },
            producer_command=(
                f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_same_workload_compare.py"
            ),
            must_run_after=["logits diagnostics pass", "generation quality pass"],
        ),
        "rollback_report": {
            "id": "rollback_report",
            "title": "Rollback and production isolation report",
            "target_json": str(args.rollback_json),
            "exists": args.rollback_json.exists(),
            "verdict": rollback.get("verdict") if rollback else None,
            "ready": get_path(rollback, "summary", "rollback_ready") is True,
            "required_fields": {
                "summary.rollback_ready": "bool",
                "summary.production_path_unchanged": "bool",
                "summary.service_restarted": "bool",
                "summary.overwrote_18888": "bool",
                "summary.seq16_baseline_deleted": "bool",
                "summary.candidate_artifact_present": "bool",
                "summary.candidate_manifest_verified": "bool",
            },
            "thresholds": {
                "rollback_ready": True,
                "production_path_unchanged": True,
                "service_restarted": False,
                "overwrote_18888": False,
                "seq16_baseline_deleted": False,
                "candidate_artifact_present": True,
                "candidate_manifest_verified": True,
            },
            "producer_command": f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_rollback_report.py",
            "must_run_after": ["candidate artifact produced", "manifest written"],
        },
    }
    evaluations = {
        "logits_diagnostics": evaluate_logits_report(logits, args),
        "generation_quality": evaluate_generation_report(generation, args),
        "same_workload_compare": evaluate_same_workload_report(same_workload, args),
    }
    for item_id, evaluation in evaluations.items():
        target_reports[item_id]["ready"] = evaluation["ready"]
        target_reports[item_id]["blockers"] = evaluation["blockers"]
        target_reports[item_id]["evidence"] = evaluation["evidence"]

    missing_validation_reports = [
        item_id for item_id, item in target_reports.items() if item.get("ready") is not True
    ]
    blockers = [f"precondition:{key}" for key, ok in preconditions.items() if not ok]
    blockers.extend(f"validation:{item_id}_not_ready" for item_id in missing_validation_reports)
    ready_for_promotion_check = not blockers

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": (
            "ready_dream7b_bpu_quality_post_compile_validation_matrix"
            if ready_for_promotion_check
            else "blocked_dream7b_bpu_quality_post_compile_validation_matrix"
        ),
        "candidate_id": args.candidate_id,
        "compile_allowed_now": compile_allowed_now,
        "ready_for_promotion_check": ready_for_promotion_check,
        "preconditions": preconditions,
        "blockers": blockers,
        "source_reports": {
            "candidate_pack": report_ref(args.pack_json, pack),
            "capacity": report_ref(args.capacity_json, capacity),
            "compile_admission": report_ref(args.admission_json, admission),
            "preflight": report_ref(args.preflight_json, preflight),
            "rollback": report_ref(args.rollback_json, rollback),
            "promotion": report_ref(args.promotion_json, promotion),
            "logits": report_ref(args.logits_json, logits),
            "generation": report_ref(args.generation_json, generation),
            "same_workload": report_ref(args.same_workload_json, same_workload),
        },
        "candidate": {
            "present": bool(candidate),
            "rank": candidate.get("rank"),
            "scope": candidate.get("scope"),
            "remote_output_root": candidate.get("remote_output_root"),
            "remote_report_root": candidate.get("remote_report_root"),
            "compile_after_capacity_gate_only": get_path(candidate, "commands", "compile_after_capacity_gate_only"),
        },
        "validation_reports": target_reports,
        "command_sequence_after_capacity_handoff": [
            f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_capacity_post_reboot_verifier.py",
            f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_capacity_unblock_plan.py",
            f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_preflight_runner.py --candidate-id {args.candidate_id} --run-state-dict --run-compile-preflight",
            f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_compile_admission_guard.py",
            get_path(candidate, "commands", "compile_after_capacity_gate_only"),
            f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_rollback_report.py",
            target_reports["logits_diagnostics"]["producer_command"],
            target_reports["generation_quality"]["producer_command"],
            target_reports["same_workload_compare"]["producer_command"],
            f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_bpu_quality_promotion_gate.py",
            f"& '{PYTHON_EXE}' scripts\\probes\\dream7b_ai_nas_goal_status_packet.py",
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
        "# Dream7B BPU Quality Post-Compile Validation Matrix",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate_id: `{payload['candidate_id']}`",
        f"- compile_allowed_now: `{payload['compile_allowed_now']}`",
        f"- ready_for_promotion_check: `{payload['ready_for_promotion_check']}`",
        "- compile_started_by_this_probe: `False`",
        "- service_restarted_by_this_probe: `False`",
        "- production_write_performed_by_this_probe: `False`",
        "",
        "## Preconditions",
        "",
    ]
    for key, value in payload["preconditions"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Validation Reports", ""])
    for item in payload["validation_reports"].values():
        lines.append(
            f"- {item['id']}: ready=`{item['ready']}` exists=`{item['exists']}` "
            f"verdict=`{item['verdict']}` target=`{item['target_json']}`"
        )
    lines.extend(["", "## Command Sequence After Capacity Handoff", "", "```powershell"])
    lines.extend(str(command) for command in payload["command_sequence_after_capacity_handoff"] if command)
    lines.extend(["```", "", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{item}`" for item in payload["blockers"])
    else:
        lines.append("- none")
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
            str(report_dir / "dream7b_bpu_quality_post_compile_validation_matrix.json"),
            str(report_dir / "dream7b_bpu_quality_post_compile_validation_matrix.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--capacity-json", type=Path, default=DEFAULT_CAPACITY_JSON)
    parser.add_argument("--admission-json", type=Path, default=DEFAULT_ADMISSION_JSON)
    parser.add_argument("--preflight-json", type=Path, default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--rollback-json", type=Path, default=DEFAULT_ROLLBACK_JSON)
    parser.add_argument("--promotion-json", type=Path, default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--logits-json", type=Path, default=DEFAULT_LOGITS_JSON)
    parser.add_argument("--generation-json", type=Path, default=DEFAULT_GENERATION_JSON)
    parser.add_argument("--same-workload-json", type=Path, default=DEFAULT_SAME_WORKLOAD_JSON)
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
    report_dir = args.out_root / f"dream7b_bpu_quality_post_compile_validation_matrix_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_post_compile_validation_matrix.json"
    md_path = report_dir / "dream7b_bpu_quality_post_compile_validation_matrix.md"
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
    latest_json = args.out_root / "dream7b_bpu_quality_post_compile_validation_matrix_latest.json"
    latest_md = args.out_root / "dream7b_bpu_quality_post_compile_validation_matrix_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["verdict"].startswith("ready_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
