#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_bpu_quality_capacity_operator_handoff"
DEFAULT_CAPACITY_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_capacity_unblock_plan_latest.json")
DEFAULT_ADMISSION_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_compile_admission_guard_latest.json")
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
RANK1_CANDIDATE = "seg27_28_lmheadq16_last_token_sentinel"


DISK_AUDIT_PS = r'''
$ErrorActionPreference = "Stop"
$drives = @()
Get-PSDrive -PSProvider FileSystem | ForEach-Object {
    $drives += [ordered]@{
        name = $_.Name
        root = $_.Root
        used_gb = [math]::Round($_.Used / 1GB, 2)
        free_gb = [math]::Round($_.Free / 1GB, 2)
    }
}
[ordered]@{
    drives = $drives
} | ConvertTo-Json -Depth 6
'''


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def round2(value: float) -> float:
    return round(value, 2)


def ceil_to_multiple(value: float, multiple: float) -> float:
    if multiple <= 0:
        return value
    return math.ceil(value / multiple) * multiple


def run_disk_audit() -> dict[str, Any]:
    result = run_cmd(["powershell.exe", "-NoProfile", "-Command", DISK_AUDIT_PS], timeout=30)
    if result["returncode"] != 0:
        return {"ok": False, "error": "disk_audit_failed", "run": result}
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"disk_audit_json_decode_failed:{exc}", "run": result}
    payload["ok"] = True
    return payload


def admitted_count(admission: dict[str, Any]) -> int:
    return sum(1 for row in admission.get("classifications") or [] if row.get("command_admitted"))


def blockers_by_candidate(admission: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in admission.get("classifications") or []:
        key = row.get("candidate_id") or "none"
        out[str(key)] = list(row.get("blockers") or [])
    return out


def select_pagefile_drive(disk: dict[str, Any], required_additional_gb: float, minimum_free_after_gb: float) -> dict[str, Any]:
    drives = disk.get("drives") or []
    usable: list[dict[str, Any]] = []
    for drive in drives:
        name = str(drive.get("name") or "")
        free_gb = as_float(drive.get("free_gb"))
        if not name or free_gb <= 0:
            continue
        projected_free = free_gb - required_additional_gb
        row = {
            "name": name,
            "root": drive.get("root"),
            "free_gb": free_gb,
            "projected_free_after_additional_pagefile_gb": round2(projected_free),
            "satisfies_minimum_free_after": projected_free >= minimum_free_after_gb,
        }
        usable.append(row)
    non_c = [row for row in usable if row["name"].upper() != "C" and row["satisfies_minimum_free_after"]]
    c_rows = [row for row in usable if row["name"].upper() == "C" and row["satisfies_minimum_free_after"]]
    if non_c:
        selected = sorted(non_c, key=lambda row: row["free_gb"], reverse=True)[0]
    elif c_rows:
        selected = c_rows[0]
    else:
        selected = None
    return {
        "all_drives": usable,
        "selected": selected,
        "disk_space_ok": selected is not None,
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    capacity_path = Path(args.capacity_json)
    admission_path = Path(args.admission_json)
    capacity = read_json(capacity_path)
    admission = read_json(admission_path)
    disk = run_disk_audit()
    current_commit = capacity.get("current_commit") or {}
    current_audit = capacity.get("current_audit") or {}
    current_audit_commit = current_audit.get("commit") or {}
    projection = capacity.get("projected_after_closing_large_private_processes") or {}
    pagefile = capacity.get("pagefile") or {}
    pagefile_allocated_gb = as_float(pagefile.get("allocated_total_gb"))
    physical_total_gb = as_float(current_audit_commit.get("physical_total_gb"))
    recommended_commit_limit_gb = as_float(projection.get("recommended_commit_limit_gb"))
    required_headroom_gb = as_float((capacity.get("capacity_guard") or {}).get("required_commit_headroom_gb"), 64.0)
    commit_total_gb = as_float(current_commit.get("commit_total_gb"))
    required_commit_limit_by_headroom_gb = commit_total_gb + required_headroom_gb
    target_commit_limit_gb = max(recommended_commit_limit_gb, required_commit_limit_by_headroom_gb)
    target_pagefile_gb_raw = max(0.0, target_commit_limit_gb - physical_total_gb)
    target_pagefile_gb = ceil_to_multiple(target_pagefile_gb_raw, args.pagefile_round_up_gb)
    target_pagefile_mb = int(round(target_pagefile_gb * 1024))
    additional_pagefile_gb = max(0.0, target_pagefile_gb - pagefile_allocated_gb)
    additional_pagefile_gb_rounded = ceil_to_multiple(additional_pagefile_gb, args.pagefile_round_up_gb)
    additional_pagefile_mb = int(round(additional_pagefile_gb_rounded * 1024))
    minimum_free_after_gb = args.minimum_c_free_after_gb
    drive_choice = (
        select_pagefile_drive(disk, additional_pagefile_gb_rounded, minimum_free_after_gb)
        if disk.get("ok")
        else {"all_drives": [], "selected": None, "disk_space_ok": False}
    )
    selected_drive = drive_choice.get("selected") or {}
    disk_space_ok = bool(drive_choice.get("disk_space_ok"))
    c_drive = next((drive for drive in drive_choice.get("all_drives") or [] if drive.get("name") == "C"), {})
    selected_pagefile_name = f"{selected_drive.get('name')}:\\pagefile.sys" if selected_drive else ""
    current_c_pagefile_mb = int(round(pagefile_allocated_gb * 1024))

    errors: list[str] = []
    if capacity.get("verdict") != "blocked_dream7b_bpu_quality_capacity_unblock_plan":
        errors.append("capacity_report_not_current_blocked_shape")
    if admission.get("verdict") != "ok_dream7b_bpu_quality_compile_admission_guard":
        errors.append("admission_guard_not_ok")
    if admitted_count(admission) != 0:
        errors.append("compile_command_already_admitted")
    if target_pagefile_mb <= 0:
        errors.append("target_pagefile_not_computable")
    if not disk.get("ok"):
        errors.append("disk_free_not_verified")
    if disk.get("ok") and not disk_space_ok:
        errors.append("insufficient_c_free_space_for_target_pagefile")

    elevated_commands = [
        "Get-CimInstance Win32_ComputerSystem | Select-Object AutomaticManagedPagefile",
        "Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage",
        "Get-CimInstance Win32_PageFileSetting | Select-Object Name,InitialSize,MaximumSize",
        "$CurrentCPagefileMb = " + str(current_c_pagefile_mb),
        "$AdditionalPagefileMb = " + str(additional_pagefile_mb),
        "$AdditionalPagefileName = '" + selected_pagefile_name + "'",
        "$ComputerSystem = Get-CimInstance Win32_ComputerSystem",
        "Set-CimInstance -InputObject $ComputerSystem -Property @{ AutomaticManagedPagefile = $false }",
        "function Set-PageFileFixedSize([string]$Name, [int]$SizeMb) { $FilterName = $Name.Replace('\\', '\\\\'); $PageFile = Get-CimInstance Win32_PageFileSetting -Filter \"Name='$FilterName'\"; if ($null -eq $PageFile) { New-CimInstance -ClassName Win32_PageFileSetting -Property @{ Name = $Name; InitialSize = $SizeMb; MaximumSize = $SizeMb } } else { Set-CimInstance -InputObject $PageFile -Property @{ InitialSize = $SizeMb; MaximumSize = $SizeMb } } }",
        "Set-PageFileFixedSize 'C:\\pagefile.sys' $CurrentCPagefileMb",
        "Set-PageFileFixedSize $AdditionalPagefileName $AdditionalPagefileMb",
        "Get-CimInstance Win32_PageFileSetting | Select-Object Name,InitialSize,MaximumSize",
        "Restart-Computer",
    ]
    post_reboot_commands = [
        "& 'C:\\Users\\zhexu\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' scripts\\probes\\dream7b_bpu_quality_capacity_post_reboot_verifier.py",
        "& 'C:\\Users\\zhexu\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' scripts\\probes\\dream7b_bpu_quality_capacity_unblock_plan.py",
        "& 'C:\\Users\\zhexu\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' scripts\\probes\\dream7b_bpu_quality_preflight_runner.py --candidate-id seg27_28_lmheadq16_last_token_sentinel --run-state-dict --run-compile-preflight",
        "& 'C:\\Users\\zhexu\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' scripts\\probes\\dream7b_bpu_quality_compile_admission_guard.py",
        "& 'C:\\Users\\zhexu\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' scripts\\probes\\dream7b_ai_nas_goal_status_packet.py",
    ]
    verdict = "ok_dream7b_bpu_quality_capacity_operator_handoff" if not errors else "blocked_dream7b_bpu_quality_capacity_operator_handoff"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "errors": errors,
        "source_paths": {
            "capacity_json": str(capacity_path),
            "admission_json": str(admission_path),
        },
        "current_state": {
            "capacity_verdict": capacity.get("verdict"),
            "admission_verdict": admission.get("verdict"),
            "admitted_count": admitted_count(admission),
            "blockers_by_candidate": blockers_by_candidate(admission),
            "commit_total_gb": current_commit.get("commit_total_gb"),
            "commit_limit_gb": current_commit.get("commit_limit_gb"),
            "commit_headroom_gb": current_commit.get("commit_headroom_gb"),
            "commit_headroom_deficit_gb": current_commit.get("commit_headroom_deficit_gb"),
            "physical_total_gb": physical_total_gb,
            "pagefile_allocated_total_gb": pagefile_allocated_gb,
            "c_drive_free_gb": c_drive.get("free_gb") if disk.get("ok") else None,
        },
        "target": {
            "required_commit_headroom_gb": required_headroom_gb,
            "recommended_commit_limit_gb": recommended_commit_limit_gb,
            "target_commit_limit_gb": round2(target_commit_limit_gb),
            "target_pagefile_gb": round2(target_pagefile_gb),
            "target_pagefile_mb": target_pagefile_mb,
            "additional_pagefile_gb": round2(additional_pagefile_gb),
            "additional_pagefile_gb_rounded": round2(additional_pagefile_gb_rounded),
            "additional_pagefile_mb": additional_pagefile_mb,
            "selected_additional_pagefile_name": selected_pagefile_name,
            "selected_additional_pagefile_drive": selected_drive,
            "minimum_c_free_after_gb": minimum_free_after_gb,
            "disk_space_ok": disk_space_ok,
            "drive_candidates": drive_choice.get("all_drives") or [],
        },
        "operator_handoff": {
            "admin_required": True,
            "reboot_required": True,
            "would_modify_system": False,
            "execute_commands_by_this_probe": False,
            "elevated_powershell_commands": elevated_commands,
            "post_reboot_verification_commands": post_reboot_commands,
            "promotion_boundary": [
                "Do not start HBM compile until capacity_unblock is ready and compile_admission admits exactly the rank-1 sentinel command.",
                "Do not replace 18888 during Route B experiments.",
                "Do not delete seq16 queue-batch baselines.",
                "After compile, run logits diagnostics, three-prompt Chinese generation, same-workload comparison, and rollback report before promotion.",
            ],
        },
        "audit": {
            "compile_started": False,
            "runtime_started": False,
            "service_restarted": False,
            "production_write_performed": False,
            "system_setting_changed": False,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    state = payload["current_state"]
    target = payload["target"]
    handoff = payload["operator_handoff"]
    lines = [
        "# Dream7B BPU Quality Capacity Operator Handoff",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        "- compile_started: `False`",
        "- service_restarted: `False`",
        "- production_write_performed: `False`",
        "- system_setting_changed: `False`",
        "",
        "## Current State",
        "",
        f"- capacity_verdict: `{state['capacity_verdict']}`",
        f"- admission_verdict: `{state['admission_verdict']}`",
        f"- admitted_count: `{state['admitted_count']}`",
        f"- commit_headroom_gb: `{state['commit_headroom_gb']}`",
        f"- commit_headroom_deficit_gb: `{state['commit_headroom_deficit_gb']}`",
        f"- pagefile_allocated_total_gb: `{state['pagefile_allocated_total_gb']}`",
        f"- c_drive_free_gb: `{state['c_drive_free_gb']}`",
        "",
        "## Target",
        "",
        f"- target_commit_limit_gb: `{target['target_commit_limit_gb']}`",
        f"- target_pagefile_gb_if_single_file: `{target['target_pagefile_gb']}`",
        f"- target_pagefile_mb_if_single_file: `{target['target_pagefile_mb']}`",
        f"- additional_pagefile_gb: `{target['additional_pagefile_gb']}`",
        f"- additional_pagefile_gb_rounded: `{target['additional_pagefile_gb_rounded']}`",
        f"- selected_additional_pagefile_name: `{target['selected_additional_pagefile_name']}`",
        f"- disk_space_ok: `{target['disk_space_ok']}`",
        "",
        "## Elevated PowerShell Commands",
        "",
        "Run only from an elevated PowerShell session after choosing to change the system pagefile.",
        "",
        "```powershell",
        *handoff["elevated_powershell_commands"],
        "```",
        "",
        "## Post-Reboot Verification",
        "",
        "Run from the workspace after the reboot.",
        "",
        "```powershell",
        *handoff["post_reboot_verification_commands"],
        "```",
        "",
        "## Promotion Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in handoff["promotion_boundary"])
    lines.extend(["", "## Errors", ""])
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
            str(report_dir / "dream7b_bpu_quality_capacity_operator_handoff.json"),
            str(report_dir / "dream7b_bpu_quality_capacity_operator_handoff.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity-json", default=str(DEFAULT_CAPACITY_JSON))
    parser.add_argument("--admission-json", default=str(DEFAULT_ADMISSION_JSON))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--pagefile-round-up-gb", type=float, default=4.0)
    parser.add_argument("--minimum-c-free-after-gb", type=float, default=20.0)
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
    report_dir = Path(args.out_root) / f"dream7b_bpu_quality_capacity_operator_handoff_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_capacity_operator_handoff.json"
    md_path = report_dir / "dream7b_bpu_quality_capacity_operator_handoff.md"
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
    latest_json = Path(args.out_root) / "dream7b_bpu_quality_capacity_operator_handoff_latest.json"
    latest_md = Path(args.out_root) / "dream7b_bpu_quality_capacity_operator_handoff_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
