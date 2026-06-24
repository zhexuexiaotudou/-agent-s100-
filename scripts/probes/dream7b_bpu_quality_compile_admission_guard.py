#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PACK_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_candidate_pack_latest.json")
DEFAULT_CAPACITY_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_capacity_unblock_plan_latest.json")
DEFAULT_PREFLIGHT_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_preflight_runner_latest.json")
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
ALLOWED_FIRST_CANDIDATE = "seg27_28_lmheadq16_last_token_sentinel"


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


def split_command(command: str) -> list[str]:
    if not command.strip():
        return []
    try:
        return [token.strip("'\"") for token in shlex.split(command, posix=False)]
    except ValueError:
        return [token.strip("'\"") for token in command.split()]


def option_map(tokens: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("-"):
            values: list[str] = []
            cursor = index + 1
            while cursor < len(tokens) and not tokens[cursor].startswith("-"):
                values.append(tokens[cursor].strip("'\""))
                cursor += 1
            key = token.lower()
            if not values:
                options[key] = True
            elif len(values) == 1:
                options[key] = values[0]
            else:
                options[key] = values
            index = cursor
        else:
            index += 1
    return options


def as_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value is True:
            return default
        return int(str(value))
    except ValueError:
        return default


def values_list(value: Any) -> list[str]:
    if value is None or value is True:
        return []
    raw = value if isinstance(value, list) else [value]
    values: list[str] = []
    for item in raw:
        values.extend(part.strip() for part in str(item).split(",") if part.strip())
    return values


def preflight_covers_candidate(preflight: dict[str, Any], candidate_id: str | None) -> bool:
    selected = [str(item) for item in preflight.get("selected_candidate_ids") or []]
    return bool(candidate_id) and candidate_id in selected


def candidate_by_id(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(candidate.get("id")): candidate for candidate in pack.get("candidates") or []}


def candidate_for_command(command: str, pack: dict[str, Any]) -> str | None:
    for candidate in pack.get("candidates") or []:
        commands = candidate.get("commands") or {}
        if command.strip() == str(commands.get("compile_after_capacity_gate_only") or "").strip():
            return str(candidate.get("id"))
    return None


def classify_command(command: str, pack: dict[str, Any], capacity: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    tokens = split_command(command)
    options = option_map(tokens)
    candidate_id = candidate_for_command(command, pack)
    candidates = candidate_by_id(pack)
    candidate = candidates.get(candidate_id or "")
    capacity_ready = capacity.get("verdict") == "ready_dream7b_bpu_quality_capacity_unblock_plan"
    capacity_blocks_compile = (capacity.get("recommendation") or {}).get("do_not_start_compile_now") is True
    preflight_ok = preflight.get("verdict") == "ok_dream7b_bpu_quality_preflight_runner"
    preflight_candidate_ok = preflight_covers_candidate(preflight, candidate_id)
    is_compile_wrapper = any("compile-dreamtruebatchsegments.ps1" in token.lower() for token in tokens)
    parsed = {
        "segments": values_list(options.get("-segments")),
        "batch_size": as_int(options.get("-batchsize")),
        "seq_len": as_int(options.get("-seqlen")),
        "w_bits": as_int(options.get("-wbits")),
        "lm_head_w_bits": as_int(options.get("-lmheadwbits"), 0),
        "final_logits_mode": str(options.get("-finallogitsmode") or "full"),
        "preflight_only": options.get("-preflightonly") is True,
        "force": options.get("-force") is True,
        "skip_preflight": options.get("-skippreflight") is True,
    }
    blockers: list[str] = []
    if not command.strip():
        blockers.append("no_command_proposed")
    if command.strip() and not is_compile_wrapper:
        blockers.append("not_compile_wrapper")
    if command.strip() and not candidate_id:
        blockers.append("not_in_candidate_pack")
    if candidate_id and candidate_id != ALLOWED_FIRST_CANDIDATE:
        blockers.append("only_rank1_sentinel_allowed_first")
    if parsed["preflight_only"]:
        blockers.append("preflight_only_is_not_hbm_compile")
    if parsed["force"]:
        blockers.append("force_blocked")
    if parsed["skip_preflight"]:
        blockers.append("skip_preflight_blocked")
    if not capacity_ready or capacity_blocks_compile:
        blockers.append("capacity_unblock_not_ready")
    if not preflight_ok:
        blockers.append("preflight_runner_not_ok")
    if candidate_id and not preflight_candidate_ok:
        blockers.append("preflight_candidate_mismatch")

    expected_scope = (candidate or {}).get("scope") or {}
    if candidate:
        if parsed["segments"] != values_list(expected_scope.get("segments")):
            blockers.append("segments_mismatch")
        if parsed["batch_size"] != int(expected_scope.get("batch_size")):
            blockers.append("batch_size_mismatch")
        if parsed["seq_len"] != int(expected_scope.get("seq_len")):
            blockers.append("seq_len_mismatch")
        if parsed["w_bits"] != int(expected_scope.get("w_bits")):
            blockers.append("w_bits_mismatch")
        if parsed["lm_head_w_bits"] != int(expected_scope.get("lm_head_w_bits")):
            blockers.append("lm_head_w_bits_mismatch")
        if parsed["final_logits_mode"] != str(expected_scope.get("final_logits_mode")):
            blockers.append("final_logits_mode_mismatch")

    command_admitted = (
        bool(command.strip())
        and is_compile_wrapper
        and candidate_id == ALLOWED_FIRST_CANDIDATE
        and capacity_ready
        and not capacity_blocks_compile
        and preflight_ok
        and not parsed["preflight_only"]
        and not parsed["force"]
        and not parsed["skip_preflight"]
        and not blockers
    )
    return {
        "proposed_command": command,
        "tokens": tokens,
        "parsed_options": parsed,
        "candidate_id": candidate_id,
        "is_compile_wrapper": is_compile_wrapper,
        "capacity_ready": capacity_ready,
        "capacity_blocks_compile": capacity_blocks_compile,
        "preflight_ok": preflight_ok,
        "preflight_selected_candidate_ids": preflight.get("selected_candidate_ids") or [],
        "preflight_candidate_ok": preflight_candidate_ok,
        "command_admitted": command_admitted,
        "would_start_compile": command_admitted,
        "blockers": sorted(set(blockers)),
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    pack = json.loads(Path(args.pack_json).read_text(encoding="utf-8"))
    capacity = json.loads(Path(args.capacity_json).read_text(encoding="utf-8"))
    preflight = json.loads(Path(args.preflight_json).read_text(encoding="utf-8"))
    proposed_commands = list(args.proposed_command or [])
    if args.include_candidate_commands:
        for candidate in pack.get("candidates") or []:
            command = ((candidate.get("commands") or {}).get("compile_after_capacity_gate_only") or "").strip()
            if command:
                proposed_commands.append(command)
        proposed_commands.append("")
    classifications = [classify_command(command, pack, capacity, preflight) for command in proposed_commands]
    errors: list[str] = []
    if pack.get("verdict") != "ok_dream7b_bpu_quality_candidate_pack":
        errors.append("candidate_pack_not_ok")
    if not classifications:
        errors.append("no_command_classified")
    admitted = [item for item in classifications if item.get("command_admitted")]
    unsafe_admitted = [
        item for item in classifications
        if item.get("command_admitted") and item.get("candidate_id") != ALLOWED_FIRST_CANDIDATE
    ]
    if unsafe_admitted:
        errors.append("unsafe_command_admitted")
    if capacity.get("verdict") != "ready_dream7b_bpu_quality_capacity_unblock_plan" and admitted:
        errors.append("capacity_blocked_but_command_admitted")
    verdict = "ok_dream7b_bpu_quality_compile_admission_guard" if not errors else "blocked_dream7b_bpu_quality_compile_admission_guard"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "errors": errors,
        "source_paths": {
            "candidate_pack_json": str(args.pack_json),
            "capacity_json": str(args.capacity_json),
            "preflight_json": str(args.preflight_json),
        },
        "policy": {
            "allowed_first_candidate": ALLOWED_FIRST_CANDIDATE,
            "compile_started": False,
            "runtime_started": False,
            "service_restarted": False,
            "production_write_performed": False,
            "only_rank1_compile_after_capacity_ready": True,
        },
        "inputs": {
            "candidate_pack_verdict": pack.get("verdict"),
            "capacity_verdict": capacity.get("verdict"),
            "preflight_verdict": preflight.get("verdict"),
        },
        "classifications": classifications,
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B BPU Quality Compile Admission Guard",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- allowed_first_candidate: `{payload['policy']['allowed_first_candidate']}`",
        "- compile_started: `False`",
        "- service_restarted: `False`",
        "- production_write_performed: `False`",
        "",
        "## Inputs",
        "",
    ]
    for key, value in payload["inputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Classifications", ""])
    for item in payload["classifications"]:
        command_label = item.get("candidate_id") or "no_candidate"
        lines.append(f"### {command_label}")
        lines.append(f"- command_admitted: `{item.get('command_admitted')}`")
        lines.append(f"- would_start_compile: `{item.get('would_start_compile')}`")
        lines.append(f"- blockers: `{item.get('blockers')}`")
        lines.append(f"- preflight_selected_candidate_ids: `{item.get('preflight_selected_candidate_ids')}`")
        parsed = item.get("parsed_options") or {}
        lines.append(
            f"- shape: segments=`{parsed.get('segments')}`, batch=`{parsed.get('batch_size')}`, "
            f"seq=`{parsed.get('seq_len')}`, w_bits=`{parsed.get('w_bits')}`, "
            f"lm_head=`{parsed.get('lm_head_w_bits')}`, final=`{parsed.get('final_logits_mode')}`"
        )
        lines.append("")
    lines.extend(["## Errors", ""])
    if payload["errors"]:
        lines.extend(f"- `{error}`" for error in payload["errors"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ssh_command(args: argparse.Namespace, command: str, timeout: int = 60) -> dict[str, Any]:
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
            str(report_dir / "dream7b_bpu_quality_compile_admission_guard.json"),
            str(report_dir / "dream7b_bpu_quality_compile_admission_guard.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-json", default=str(DEFAULT_PACK_JSON))
    parser.add_argument("--capacity-json", default=str(DEFAULT_CAPACITY_JSON))
    parser.add_argument("--preflight-json", default=str(DEFAULT_PREFLIGHT_JSON))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--proposed-command", action="append", default=[])
    parser.add_argument("--include-candidate-commands", action=argparse.BooleanOptionalAction, default=True)
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
    report_dir = Path(args.out_root) / f"dream7b_bpu_quality_compile_admission_guard_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_compile_admission_guard.json"
    md_path = report_dir / "dream7b_bpu_quality_compile_admission_guard.md"
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
    latest_json = Path(args.out_root) / "dream7b_bpu_quality_compile_admission_guard_latest.json"
    latest_md = Path(args.out_root) / "dream7b_bpu_quality_compile_admission_guard_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
