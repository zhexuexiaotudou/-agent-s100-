#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_bpu_quality_capacity_post_reboot_verifier"
DEFAULT_HANDOFF_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_capacity_operator_handoff_latest.json")
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"


POWERSHELL_AUDIT = r'''
$ErrorActionPreference = "SilentlyContinue"
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

namespace NativeMethods {
    [StructLayout(LayoutKind.Sequential)]
    public struct PERFORMANCE_INFORMATION {
        public uint cb;
        public UIntPtr CommitTotal;
        public UIntPtr CommitLimit;
        public UIntPtr CommitPeak;
        public UIntPtr PhysicalTotal;
        public UIntPtr PhysicalAvailable;
        public UIntPtr SystemCache;
        public UIntPtr KernelTotal;
        public UIntPtr KernelPaged;
        public UIntPtr KernelNonpaged;
        public UIntPtr PageSize;
        public uint HandleCount;
        public uint ProcessCount;
        public uint ThreadCount;
    }

    public static class PerformanceInfo {
        [DllImport("psapi.dll", SetLastError = true)]
        public static extern bool GetPerformanceInfo(out PERFORMANCE_INFORMATION info, uint size);
    }
}
"@

function Round2([double]$value) {
    return [math]::Round($value, 2)
}

function Query-CimJson([string]$className, [string[]]$properties) {
    $result = [ordered]@{ ok = $false; rows = @(); error = "" }
    try {
        $rows = Get-CimInstance $className -ErrorAction Stop | Select-Object $properties
        foreach ($row in @($rows)) {
            $entry = [ordered]@{}
            foreach ($prop in $properties) {
                $entry[$prop] = $row.$prop
            }
            $result.rows += $entry
        }
        $result.ok = $true
    } catch {
        $result.error = $_.Exception.Message
    }
    return $result
}

$gb = 1024.0 * 1024.0 * 1024.0
$info = New-Object NativeMethods.PERFORMANCE_INFORMATION
$ok = [NativeMethods.PerformanceInfo]::GetPerformanceInfo([ref]$info, [System.Runtime.InteropServices.Marshal]::SizeOf([type][NativeMethods.PERFORMANCE_INFORMATION]))
$commit = $null
if ($ok) {
    $pageSize = [double]$info.PageSize.ToUInt64()
    $commitTotalGB = ([double]$info.CommitTotal.ToUInt64() * $pageSize) / $gb
    $commitLimitGB = ([double]$info.CommitLimit.ToUInt64() * $pageSize) / $gb
    $commitPeakGB = ([double]$info.CommitPeak.ToUInt64() * $pageSize) / $gb
    $physicalTotalGB = ([double]$info.PhysicalTotal.ToUInt64() * $pageSize) / $gb
    $physicalAvailableGB = ([double]$info.PhysicalAvailable.ToUInt64() * $pageSize) / $gb
    $commit = [ordered]@{
        commit_total_gb = Round2 $commitTotalGB
        commit_limit_gb = Round2 $commitLimitGB
        commit_headroom_gb = Round2 ($commitLimitGB - $commitTotalGB)
        commit_peak_gb = Round2 $commitPeakGB
        physical_total_gb = Round2 $physicalTotalGB
        physical_available_gb = Round2 $physicalAvailableGB
    }
}

$drives = @()
Get-PSDrive -PSProvider FileSystem | ForEach-Object {
    $drives += [ordered]@{
        name = $_.Name
        root = $_.Root
        used_gb = Round2 ([double]$_.Used / $gb)
        free_gb = Round2 ([double]$_.Free / $gb)
    }
}

$compileProcesses = @()
$currentPid = $PID
Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $currentPid -and
    ($_.CommandLine -match "Compile-DreamTrueBatchSegments|compile_dream|oellm|hbdk|wsl_compile_dream")
} | ForEach-Object {
    $compileProcesses += [ordered]@{
        pid = $_.ProcessId
        name = $_.Name
        command_line = $_.CommandLine
    }
}

[ordered]@{
    generated_at = (Get-Date).ToString("o")
    commit = $commit
    operating_system = Query-CimJson "Win32_OperatingSystem" @("LastBootUpTime")
    pagefile_usage = Query-CimJson "Win32_PageFileUsage" @("Name", "AllocatedBaseSize", "CurrentUsage", "PeakUsage")
    pagefile_settings = Query-CimJson "Win32_PageFileSetting" @("Name", "InitialSize", "MaximumSize")
    drives = $drives
    compile_processes = $compileProcesses
} | ConvertTo-Json -Depth 8
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


def run_audit(timeout: int) -> dict[str, Any]:
    result = run_cmd(["powershell.exe", "-NoProfile", "-Command", POWERSHELL_AUDIT], timeout=timeout)
    if result["returncode"] != 0:
        return {"ok": False, "error": "powershell_audit_failed", "run": result}
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"powershell_json_decode_failed:{exc}", "run": result}
    payload["ok"] = True
    payload["run"] = {"returncode": result["returncode"], "stderr": result["stderr"]}
    return payload


def normalize_pagefile_rows(query: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in query.get("rows") or []:
        item = {"name": row.get("Name")}
        if "AllocatedBaseSize" in row:
            item["allocated_mb"] = int(as_float(row.get("AllocatedBaseSize")))
        if "CurrentUsage" in row:
            item["current_usage_mb"] = int(as_float(row.get("CurrentUsage")))
        if "PeakUsage" in row:
            item["peak_usage_mb"] = int(as_float(row.get("PeakUsage")))
        if "InitialSize" in row:
            item["initial_size_mb"] = int(as_float(row.get("InitialSize")))
        if "MaximumSize" in row:
            item["maximum_size_mb"] = int(as_float(row.get("MaximumSize")))
        out.append(item)
    return out


def find_pagefile(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    expected = name.lower()
    for row in rows:
        if str(row.get("name") or "").lower() == expected:
            return row
    return None


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    handoff_path = Path(args.handoff_json)
    handoff = read_json(handoff_path)
    audit = run_audit(args.timeout)
    target = handoff.get("target") or {}
    expected_pagefile = str(target.get("selected_additional_pagefile_name") or "")
    expected_pagefile_mb = int(as_float(target.get("additional_pagefile_mb")))
    target_commit_limit_gb = as_float(target.get("target_commit_limit_gb"))
    required_headroom_gb = as_float(target.get("required_commit_headroom_gb"), 64.0)
    usage_rows = normalize_pagefile_rows(audit.get("pagefile_usage") or {}) if audit.get("ok") else []
    setting_rows = normalize_pagefile_rows(audit.get("pagefile_settings") or {}) if audit.get("ok") else []
    active_pagefile = find_pagefile(usage_rows, expected_pagefile)
    configured_pagefile = find_pagefile(setting_rows, expected_pagefile)
    commit = audit.get("commit") or {}
    commit_limit_gb = as_float(commit.get("commit_limit_gb"))
    commit_headroom_gb = as_float(commit.get("commit_headroom_gb"))
    active_allocated_mb = int(as_float((active_pagefile or {}).get("allocated_mb")))
    configured_max_mb = int(as_float((configured_pagefile or {}).get("maximum_size_mb")))
    pagefile_active = active_pagefile is not None and active_allocated_mb >= expected_pagefile_mb
    pagefile_configured = configured_pagefile is not None and configured_max_mb >= expected_pagefile_mb
    commit_limit_ready = commit_limit_gb >= target_commit_limit_gb
    commit_headroom_ready = commit_headroom_gb >= required_headroom_gb
    no_compile_process = not (audit.get("compile_processes") or [])

    errors: list[str] = []
    if handoff.get("verdict") != "ok_dream7b_bpu_quality_capacity_operator_handoff":
        errors.append("handoff_not_ok")
    if not audit.get("ok"):
        errors.append(audit.get("error", "audit_failed"))
    if audit.get("ok") and not pagefile_configured:
        errors.append("target_pagefile_not_configured")
    if audit.get("ok") and not pagefile_active:
        errors.append("target_pagefile_not_active_after_reboot")
    if audit.get("ok") and not commit_limit_ready:
        errors.append("commit_limit_below_target")
    if audit.get("ok") and not commit_headroom_ready:
        errors.append("commit_headroom_below_required")
    if audit.get("ok") and not no_compile_process:
        errors.append("compile_process_active")

    ready = not errors
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": "ready_dream7b_bpu_quality_capacity_post_reboot_verifier" if ready else "blocked_dream7b_bpu_quality_capacity_post_reboot_verifier",
        "ready": ready,
        "errors": errors,
        "source_paths": {
            "handoff_json": str(handoff_path),
        },
        "target": {
            "expected_pagefile": expected_pagefile,
            "expected_pagefile_mb": expected_pagefile_mb,
            "target_commit_limit_gb": target_commit_limit_gb,
            "required_commit_headroom_gb": required_headroom_gb,
        },
        "checks": {
            "handoff_ok": handoff.get("verdict") == "ok_dream7b_bpu_quality_capacity_operator_handoff",
            "pagefile_configured": pagefile_configured,
            "pagefile_active_after_reboot": pagefile_active,
            "commit_limit_ready": commit_limit_ready,
            "commit_headroom_ready": commit_headroom_ready,
            "no_compile_process": no_compile_process,
        },
        "observed": {
            "commit": commit,
            "active_pagefile": active_pagefile,
            "configured_pagefile": configured_pagefile,
            "pagefile_usage": usage_rows,
            "pagefile_settings": setting_rows,
            "compile_processes": audit.get("compile_processes") or [],
            "operating_system": audit.get("operating_system") or {},
            "drives": audit.get("drives") or [],
        },
        "next_actions": [
            "If blocked, execute the capacity operator handoff from an elevated PowerShell session and reboot.",
            "After this verifier is ready, rerun capacity_unblock_plan and rank-1 compile preflight.",
            "Only after compile admission admits the rank-1 sentinel should HBM compile be started.",
        ],
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
    checks = payload["checks"]
    target = payload["target"]
    observed = payload["observed"]
    lines = [
        "# Dream7B BPU Quality Capacity Post-Reboot Verifier",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- ready: `{payload['ready']}`",
        "- compile_started: `False`",
        "- service_restarted: `False`",
        "- production_write_performed: `False`",
        "- system_setting_changed: `False`",
        "",
        "## Target",
        "",
        f"- expected_pagefile: `{target['expected_pagefile']}`",
        f"- expected_pagefile_mb: `{target['expected_pagefile_mb']}`",
        f"- target_commit_limit_gb: `{target['target_commit_limit_gb']}`",
        f"- required_commit_headroom_gb: `{target['required_commit_headroom_gb']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in checks.items())
    lines.extend(
        [
            "",
            "## Observed",
            "",
            f"- commit_limit_gb: `{(observed['commit'] or {}).get('commit_limit_gb')}`",
            f"- commit_headroom_gb: `{(observed['commit'] or {}).get('commit_headroom_gb')}`",
            f"- active_pagefile: `{observed.get('active_pagefile')}`",
            f"- configured_pagefile: `{observed.get('configured_pagefile')}`",
            f"- compile_process_count: `{len(observed.get('compile_processes') or [])}`",
            "",
            "## Next Actions",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["next_actions"])
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
            str(report_dir / "dream7b_bpu_quality_capacity_post_reboot_verifier.json"),
            str(report_dir / "dream7b_bpu_quality_capacity_post_reboot_verifier.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff-json", default=str(DEFAULT_HANDOFF_JSON))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--timeout", type=int, default=45)
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
    report_dir = Path(args.out_root) / f"dream7b_bpu_quality_capacity_post_reboot_verifier_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_capacity_post_reboot_verifier.json"
    md_path = report_dir / "dream7b_bpu_quality_capacity_post_reboot_verifier.md"
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
    latest_json = Path(args.out_root) / "dream7b_bpu_quality_capacity_post_reboot_verifier_latest.json"
    latest_md = Path(args.out_root) / "dream7b_bpu_quality_capacity_post_reboot_verifier_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
