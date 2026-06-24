#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PREFLIGHT_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_preflight_runner_latest.json")
DEFAULT_PACK_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_candidate_pack_latest.json")
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

$processes = @()
Get-Process | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First 12 | ForEach-Object {
    $path = $null
    try { $path = $_.Path } catch { $path = $null }
    $privateGB = [double]($_.PrivateMemorySize64) / $gb
    $workingGB = [double]($_.WorkingSet64) / $gb
    $processes += [ordered]@{
        pid = $_.Id
        process_name = $_.ProcessName
        path = $path
        private_gb = Round2 $privateGB
        working_gb = Round2 $workingGB
    }
}

function Query-CimJson([string]$className, [string[]]$properties) {
    $result = [ordered]@{ ok = $false; rows = @(); error = "" }
    try {
        $rows = Get-CimInstance $className -ErrorAction Stop | Select-Object $properties
        if ($null -eq $rows) {
            $result.ok = $true
            return $result
        }
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

$pagefileUsage = Query-CimJson "Win32_PageFileUsage" @("Name", "AllocatedBaseSize", "CurrentUsage", "PeakUsage")
$pagefileSettings = Query-CimJson "Win32_PageFileSetting" @("Name", "InitialSize", "MaximumSize")

[ordered]@{
    generated_at = (Get-Date).ToString("o")
    commit = $commit
    top_private_processes = $processes
    pagefile_usage = $pagefileUsage
    pagefile_settings = $pagefileSettings
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


def run_powershell_audit(timeout: int) -> dict[str, Any]:
    result = run_cmd(["powershell.exe", "-NoProfile", "-Command", POWERSHELL_AUDIT], timeout=timeout)
    if result["returncode"] != 0:
        return {"ok": False, "run": result, "error": "powershell_audit_failed"}
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return {"ok": False, "run": result, "error": f"powershell_json_decode_failed:{exc}"}
    payload["ok"] = True
    payload["run"] = {"returncode": result["returncode"], "stderr": result["stderr"]}
    return payload


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def round2(value: float) -> float:
    return round(value, 2)


def normalize_pagefile_usage(query: dict[str, Any]) -> list[dict[str, Any]]:
    rows = query.get("rows") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "name": row.get("Name"),
                "allocated_base_gb": round2(as_float(row.get("AllocatedBaseSize")) / 1024.0),
                "current_usage_gb": round2(as_float(row.get("CurrentUsage")) / 1024.0),
                "peak_usage_gb": round2(as_float(row.get("PeakUsage")) / 1024.0),
            }
        )
    return out


def normalize_pagefile_settings(query: dict[str, Any]) -> list[dict[str, Any]]:
    rows = query.get("rows") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "name": row.get("Name"),
                "initial_size_gb": round2(as_float(row.get("InitialSize")) / 1024.0),
                "maximum_size_gb": round2(as_float(row.get("MaximumSize")) / 1024.0),
            }
        )
    return out


def first_compile_preflight_fields(preflight: dict[str, Any]) -> dict[str, Any]:
    for result in preflight.get("results") or []:
        compile_preflight = result.get("compile_preflight")
        if compile_preflight:
            return (compile_preflight.get("parsed") or {}).get("fields") or {}
    return {}


def find_compile_preflight_json(default_path: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    preflight = json.loads(default_path.read_text(encoding="utf-8"))
    fields = first_compile_preflight_fields(preflight)
    if fields:
        return default_path, preflight, fields
    search_root = default_path.parent
    candidates = sorted(
        search_root.glob("dream7b_bpu_quality_preflight_runner_*/dream7b_bpu_quality_preflight_runner.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        fields = first_compile_preflight_fields(payload)
        if fields:
            return candidate, payload, fields
    return default_path, preflight, {}


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    preflight_path, preflight, previous_fields = find_compile_preflight_json(Path(args.preflight_json))
    pack = json.loads(Path(args.pack_json).read_text(encoding="utf-8"))
    audit = run_powershell_audit(timeout=args.timeout)
    errors: list[str] = []
    if not audit.get("ok"):
        errors.append(audit.get("error", "audit_failed"))
    if pack.get("verdict") != "ok_dream7b_bpu_quality_candidate_pack":
        errors.append("candidate_pack_not_ok")

    required_headroom = as_float(previous_fields.get("preflight_min_commit_headroom_gb"), args.required_headroom_gb)
    commit = audit.get("commit") or {}
    current_headroom = as_float(commit.get("commit_headroom_gb"))
    current_limit = as_float(commit.get("commit_limit_gb"))
    current_total = as_float(commit.get("commit_total_gb"))
    deficit_now = max(0.0, required_headroom - current_headroom)

    top_processes = audit.get("top_private_processes") or []
    large_processes = [p for p in top_processes if as_float(p.get("private_gb")) >= args.large_process_threshold_gb]
    reclaimable = sum(as_float(p.get("private_gb")) for p in large_processes)
    projected_total = max(0.0, current_total - reclaimable)
    projected_headroom = current_limit - projected_total
    projected_deficit = max(0.0, required_headroom - projected_headroom)
    recommended_additional_commit = projected_deficit + args.safety_margin_gb if projected_deficit > 0 else 0.0
    recommended_commit_limit = current_limit + recommended_additional_commit

    pagefile_usage_query = audit.get("pagefile_usage") or {}
    pagefile_settings_query = audit.get("pagefile_settings") or {}
    pagefile_usage = normalize_pagefile_usage(pagefile_usage_query)
    pagefile_settings = normalize_pagefile_settings(pagefile_settings_query)
    verdict = (
        "ready_dream7b_bpu_quality_capacity_unblock_plan"
        if audit.get("ok") and deficit_now <= 0
        else "blocked_dream7b_bpu_quality_capacity_unblock_plan"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "errors": errors,
        "source_paths": {
            "requested_preflight_json": str(args.preflight_json),
            "compile_preflight_json": str(preflight_path),
            "candidate_pack_json": str(args.pack_json),
        },
        "capacity_guard": {
            "required_commit_headroom_gb": required_headroom,
            "safety_margin_gb": args.safety_margin_gb,
            "large_process_threshold_gb": args.large_process_threshold_gb,
        },
        "previous_compile_preflight": {
            "verdict": preflight.get("verdict"),
            "selected_candidate_ids": preflight.get("selected_candidate_ids"),
            "fields": previous_fields,
        },
        "current_audit": audit,
        "current_commit": {
            "commit_total_gb": current_total,
            "commit_limit_gb": current_limit,
            "commit_headroom_gb": current_headroom,
            "commit_headroom_deficit_gb": round2(deficit_now),
        },
        "large_private_processes": large_processes,
        "projected_after_closing_large_private_processes": {
            "reclaim_private_gb": round2(reclaimable),
            "commit_total_gb": round2(projected_total),
            "commit_headroom_gb": round2(projected_headroom),
            "remaining_headroom_deficit_gb": round2(projected_deficit),
            "recommended_additional_commit_limit_with_safety_gb": round2(recommended_additional_commit),
            "recommended_commit_limit_gb": round2(recommended_commit_limit),
        },
        "pagefile": {
            "usage_query_ok": pagefile_usage_query.get("ok") is True,
            "settings_query_ok": pagefile_settings_query.get("ok") is True,
            "usage_query_error": pagefile_usage_query.get("error") or "",
            "settings_query_error": pagefile_settings_query.get("error") or "",
            "usage": pagefile_usage,
            "settings": pagefile_settings,
            "allocated_total_gb": round2(sum(as_float(row.get("allocated_base_gb")) for row in pagefile_usage)),
        },
        "recommendation": {
            "do_not_start_compile_now": deficit_now > 0,
            "close_large_private_processes_first": bool(large_processes),
            "increase_commit_limit_or_pagefile_before_compile": projected_deficit > 0,
            "rerun_preflight_after_changes": True,
            "compile_admission_rule": "fresh preflight must report verdict=preflight_ok before any HBM compile command",
        },
        "next_actions": [
            "Do not run compile commands while commit headroom is below 64 GB.",
            "Close or pause large private-memory processes if they are nonessential.",
            "Increase Windows commit limit/pagefile enough to cover the remaining deficit plus the safety margin.",
            "Re-run dream7b_bpu_quality_preflight_runner.py with compile preflight enabled.",
            "Only after preflight_ok, compile the rank-1 seg27_28_lmheadq16 last-token sentinel first.",
        ],
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    current = payload["current_commit"]
    projection = payload["projected_after_closing_large_private_processes"]
    pagefile = payload["pagefile"]
    lines = [
        "# Dream7B BPU Quality Capacity Unblock Plan",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        "- compile_started: `False`",
        "- service_restarted: `False`",
        "- production_write_performed: `False`",
        "",
        "## Current Commit",
        "",
        f"- commit_total_gb: `{current['commit_total_gb']}`",
        f"- commit_limit_gb: `{current['commit_limit_gb']}`",
        f"- commit_headroom_gb: `{current['commit_headroom_gb']}`",
        f"- required_commit_headroom_gb: `{payload['capacity_guard']['required_commit_headroom_gb']}`",
        f"- commit_headroom_deficit_gb: `{current['commit_headroom_deficit_gb']}`",
        "",
        "## Projection",
        "",
        f"- large_private_process_count: `{len(payload['large_private_processes'])}`",
        f"- reclaim_private_gb: `{projection['reclaim_private_gb']}`",
        f"- projected_commit_headroom_gb: `{projection['commit_headroom_gb']}`",
        f"- remaining_headroom_deficit_gb: `{projection['remaining_headroom_deficit_gb']}`",
        f"- recommended_additional_commit_limit_with_safety_gb: `{projection['recommended_additional_commit_limit_with_safety_gb']}`",
        f"- recommended_commit_limit_gb: `{projection['recommended_commit_limit_gb']}`",
        "",
        "## Large Private Processes",
        "",
    ]
    if payload["large_private_processes"]:
        lines.extend(["| pid | process | private_gb | working_gb | path |", "| ---: | --- | ---: | ---: | --- |"])
        for proc in payload["large_private_processes"]:
            lines.append(
                f"| {proc.get('pid')} | {proc.get('process_name')} | {proc.get('private_gb')} | "
                f"{proc.get('working_gb')} | {proc.get('path')} |"
            )
    else:
        lines.append("- none above threshold")
    lines.extend(["", "## Pagefile", ""])
    lines.append(f"- usage_query_ok: `{pagefile['usage_query_ok']}`")
    lines.append(f"- settings_query_ok: `{pagefile['settings_query_ok']}`")
    lines.append(f"- allocated_total_gb: `{pagefile['allocated_total_gb']}`")
    if pagefile["usage_query_error"]:
        lines.append(f"- usage_query_error: `{pagefile['usage_query_error']}`")
    if pagefile["settings_query_error"]:
        lines.append(f"- settings_query_error: `{pagefile['settings_query_error']}`")
    if pagefile["usage"]:
        lines.extend(["", "| name | allocated_gb | current_usage_gb | peak_usage_gb |", "| --- | ---: | ---: | ---: |"])
        for row in pagefile["usage"]:
            lines.append(
                f"| {row.get('name')} | {row.get('allocated_base_gb')} | "
                f"{row.get('current_usage_gb')} | {row.get('peak_usage_gb')} |"
            )
    lines.extend(["", "## Recommendation", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["recommendation"].items())
    lines.extend(["", "## Next Actions", ""])
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
            str(report_dir / "dream7b_bpu_quality_capacity_unblock_plan.json"),
            str(report_dir / "dream7b_bpu_quality_capacity_unblock_plan.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-json", default=str(DEFAULT_PREFLIGHT_JSON))
    parser.add_argument("--pack-json", default=str(DEFAULT_PACK_JSON))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--required-headroom-gb", type=float, default=64.0)
    parser.add_argument("--safety-margin-gb", type=float, default=8.0)
    parser.add_argument("--large-process-threshold-gb", type=float, default=12.0)
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
    report_dir = Path(args.out_root) / f"dream7b_bpu_quality_capacity_unblock_plan_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_capacity_unblock_plan.json"
    md_path = report_dir / "dream7b_bpu_quality_capacity_unblock_plan.md"
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
    latest_json = Path(args.out_root) / "dream7b_bpu_quality_capacity_unblock_plan_latest.json"
    latest_md = Path(args.out_root) / "dream7b_bpu_quality_capacity_unblock_plan_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["verdict"].startswith("ready_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
