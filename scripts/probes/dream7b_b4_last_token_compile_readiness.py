#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def run_cmd(args: list[str], timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_kv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.startswith("preflight_"):
            continue
        values[key] = value.strip()
    return values


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def powershell_json(script: str, timeout: int = 30) -> Any:
    result = run_cmd(["powershell.exe", "-NoProfile", "-Command", script], timeout=timeout)
    if result["returncode"] != 0:
        return {"error": result["stderr"] or result["stdout"], "returncode": result["returncode"]}
    text = result["stdout"].strip()
    if not text:
        return None
    return json.loads(text)


def top_private_processes(limit: int, warn_private_gb: float) -> list[dict[str, Any]]:
    script = rf"""
Get-Process |
  Sort-Object PrivateMemorySize64 -Descending |
  Select-Object -First {limit} Id,ProcessName,Path,
    @{{Name='PrivateGB';Expression={{[math]::Round($_.PrivateMemorySize64 / 1GB, 2)}}}},
    @{{Name='WorkingGB';Expression={{[math]::Round($_.WorkingSet64 / 1GB, 2)}}}} |
  ConvertTo-Json -Depth 4
"""
    payload = powershell_json(script)
    if payload is None:
        return []
    if isinstance(payload, dict) and "error" in payload:
        return [payload]
    rows = payload if isinstance(payload, list) else [payload]
    result: list[dict[str, Any]] = []
    for row in rows:
        private_gb = as_float(row.get("PrivateGB"))
        result.append(
            {
                "pid": row.get("Id"),
                "process_name": row.get("ProcessName"),
                "path": row.get("Path"),
                "private_gb": private_gb,
                "working_gb": as_float(row.get("WorkingGB")),
                "above_warn_threshold": private_gb is not None and private_gb >= warn_private_gb,
            }
        )
    return result


def run_preflight(args: argparse.Namespace) -> dict[str, Any]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(args.compile_wrapper),
        "-Segments",
        "27:28",
        "-BatchSize",
        str(args.batch_size),
        "-SeqLen",
        str(args.seq_len),
        "-FinalLogitsMode",
        "last-token",
        "-MinCommitHeadroomGB",
        str(args.min_commit_headroom_gb),
        "-WarnProcessPrivateGB",
        str(args.warn_process_private_gb),
        "-PreflightOnly",
    ]
    result = run_cmd(command, timeout=args.preflight_timeout_sec)
    values = parse_kv(result["stdout"] + "\n" + result["stderr"])
    headroom = as_float(values.get("preflight_commit_headroom_gb"))
    required = as_float(values.get("preflight_min_commit_headroom_gb"))
    return {
        "command": command,
        "returncode": result["returncode"],
        "passed": result["returncode"] == 0,
        "raw_stdout": result["stdout"],
        "raw_stderr": result["stderr"],
        "values": {
            "commit_total_gb": as_float(values.get("preflight_commit_total_gb")),
            "commit_limit_gb": as_float(values.get("preflight_commit_limit_gb")),
            "commit_headroom_gb": headroom,
            "commit_peak_gb": as_float(values.get("preflight_commit_peak_gb")),
            "physical_available_gb": as_float(values.get("preflight_physical_available_gb")),
            "stage_free_gb": as_float(values.get("preflight_stage_free_gb")),
            "model_drive_free_gb": as_float(values.get("preflight_model_drive_free_gb")),
            "min_commit_headroom_gb": required,
            "commit_headroom_deficit_gb": round_or_none(required - headroom if required is not None and headroom is not None else None, 2),
        },
    }


def ssh_cmd(args: argparse.Namespace, remote_command: str, timeout: int = 30) -> dict[str, Any]:
    return run_cmd(
        [
            "ssh.exe",
            "-i",
            str(args.ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            remote_command,
        ],
        timeout=timeout,
    )


def check_remote(args: argparse.Namespace) -> dict[str, Any]:
    seg_dir = f"{args.remote_final_hbm_root}/seg27_28"
    hbm_path = (
        f"{seg_dir}/dream7b_segment_27_28_seq{args.seq_len}_b{args.batch_size}_q{args.w_bits}_last_token_logits.hbm"
    )
    remote_command = "\n".join(
        [
            "set -u",
            f"SEG_DIR='{seg_dir}'",
            f"HBM='{hbm_path}'",
            "echo final_hbm_root_exists=$(test -d \"$SEG_DIR\" && echo true || echo false)",
            "echo last_token_hbm_exists=$(test -f \"$HBM\" && echo true || echo false)",
            "echo manifest_exists=$(test -f \"$SEG_DIR/manifest.sha256\" && echo true || echo false)",
            "if cd \"$SEG_DIR\" 2>/dev/null && test -f manifest.sha256 && sha256sum -c manifest.sha256 >/dev/null 2>&1; then echo manifest_verified=true; else echo manifest_verified=false; fi",
            "echo hbm_path=\"$HBM\"",
        ]
    )
    result = ssh_cmd(args, remote_command, timeout=args.remote_timeout_sec)
    values: dict[str, str] = {}
    for line in result["stdout"].splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"')
    return {
        "command": remote_command,
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "final_hbm_root": args.remote_final_hbm_root,
        "segment_dir": seg_dir,
        "hbm_path": hbm_path,
        "final_hbm_root_exists": values.get("final_hbm_root_exists") == "true",
        "last_token_hbm_exists": values.get("last_token_hbm_exists") == "true",
        "manifest_exists": values.get("manifest_exists") == "true",
        "manifest_verified": values.get("manifest_verified") == "true",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    preflight = run_preflight(args)
    processes = top_private_processes(args.top_process_count, args.warn_process_private_gb)
    remote = check_remote(args)
    blockers: list[str] = []
    if not preflight["passed"]:
        blockers.append("windows_compile_preflight_failed")
    values = preflight["values"]
    if values.get("commit_headroom_deficit_gb") and values["commit_headroom_deficit_gb"] > 0:
        blockers.append("insufficient_windows_commit_headroom")
    large = [row for row in processes if row.get("above_warn_threshold")]
    if large:
        blockers.append("large_private_process_present")
    if not remote["manifest_verified"]:
        blockers.append("remote_last_token_manifest_missing")

    compile_ready = preflight["passed"] and not large
    runtime_validation_ready = remote["manifest_verified"]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ready_dream7b_b4_last_token_compile" if compile_ready else "blocked_dream7b_b4_last_token_compile",
        "candidate": "seg27_28_last_token_logits",
        "batch_size": args.batch_size,
        "seq_len": args.seq_len,
        "w_bits": args.w_bits,
        "preflight": preflight,
        "top_private_processes": processes,
        "large_private_processes": large,
        "remote": remote,
        "compile_ready": compile_ready,
        "runtime_validation_ready": runtime_validation_ready,
        "blockers": blockers,
        "next_actions": [
            "Free Windows commit headroom before starting compile.",
            "Re-run this readiness probe.",
            "Run the single seg27_28 last-token compile only after compile_ready is true.",
            "Run mb512 S100P validation only after the remote manifest verifies.",
        ],
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    values = payload["preflight"]["values"]
    remote = payload["remote"]
    largest = payload["top_private_processes"][0] if payload["top_private_processes"] else {}
    lines = [
        "# Dream7B B4 Last-Token Compile Readiness",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- candidate: {payload['candidate']}",
        f"- compile_ready: {payload['compile_ready']}",
        f"- runtime_validation_ready: {payload['runtime_validation_ready']}",
        f"- blockers: {', '.join(payload['blockers']) if payload['blockers'] else 'none'}",
        "",
        "## Windows Compile Preflight",
        "",
        f"- preflight_passed: {payload['preflight']['passed']}",
        f"- preflight_returncode: {payload['preflight']['returncode']}",
        f"- commit_total_gb: {values['commit_total_gb']}",
        f"- commit_limit_gb: {values['commit_limit_gb']}",
        f"- commit_headroom_gb: {values['commit_headroom_gb']}",
        f"- min_commit_headroom_gb: {values['min_commit_headroom_gb']}",
        f"- commit_headroom_deficit_gb: {values['commit_headroom_deficit_gb']}",
        f"- physical_available_gb: {values['physical_available_gb']}",
        f"- stage_free_gb: {values['stage_free_gb']}",
        f"- model_drive_free_gb: {values['model_drive_free_gb']}",
        "",
        "## Largest Private Process",
        "",
        f"- pid: {largest.get('pid')}",
        f"- process_name: {largest.get('process_name')}",
        f"- path: {largest.get('path')}",
        f"- private_gb: {largest.get('private_gb')}",
        f"- working_gb: {largest.get('working_gb')}",
        f"- above_warn_threshold: {largest.get('above_warn_threshold')}",
        "",
        "## Remote Final HBM",
        "",
        f"- final_hbm_root: {remote['final_hbm_root']}",
        f"- segment_dir: {remote['segment_dir']}",
        f"- hbm_path: {remote['hbm_path']}",
        f"- final_hbm_root_exists: {remote['final_hbm_root_exists']}",
        f"- last_token_hbm_exists: {remote['last_token_hbm_exists']}",
        f"- manifest_exists: {remote['manifest_exists']}",
        f"- manifest_verified: {remote['manifest_verified']}",
        "",
        "## Top Private Processes",
        "",
        "| rank | pid | process | private_gb | working_gb | path |",
        "| ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for rank, row in enumerate(payload["top_private_processes"], start=1):
        lines.append(
            f"| {rank} | {row.get('pid')} | {row.get('process_name')} | {row.get('private_gb')} | "
            f"{row.get('working_gb')} | {row.get('path')} |"
        )
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether B4 last-token final logits compile can start safely.")
    parser.add_argument("--compile-wrapper", type=Path, default=Path("scripts/probes/Compile-DreamTrueBatchSegments.ps1"))
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_last_token_compile_readiness_20260619")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--min-commit-headroom-gb", type=int, default=64)
    parser.add_argument("--warn-process-private-gb", type=int, default=12)
    parser.add_argument("--top-process-count", type=int, default=8)
    parser.add_argument("--preflight-timeout-sec", type=int, default=120)
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--known-hosts", type=Path, default=Path(r"C:\Users\zhexu\.ssh\known_hosts"))
    parser.add_argument(
        "--remote-final-hbm-root",
        default="/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final",
    )
    parser.add_argument("--remote-timeout-sec", type=int, default=30)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / f"{args.out_stem}.json"
    out_md = args.out_dir / f"{args.out_stem}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_md(payload, out_md)
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
