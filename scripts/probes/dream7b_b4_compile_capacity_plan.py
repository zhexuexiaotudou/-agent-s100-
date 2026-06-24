#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_powershell_json(script: str, timeout: int = 30) -> Any:
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    text = completed.stdout.strip()
    if not text:
        return None
    return json.loads(text)


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def round2(value: float) -> float:
    return round(value, 2)


def pagefile_usage() -> list[dict[str, Any]]:
    payload = run_powershell_json(
        "Get-CimInstance Win32_PageFileUsage | "
        "Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | ConvertTo-Json -Depth 4"
    )
    if payload is None:
        return []
    if isinstance(payload, dict) and "returncode" in payload:
        return []
    rows = payload if isinstance(payload, list) else [payload]
    result: list[dict[str, Any]] = []
    for row in rows:
        allocated_gb = as_float(row.get("AllocatedBaseSize")) / 1024.0
        current_gb = as_float(row.get("CurrentUsage")) / 1024.0
        peak_gb = as_float(row.get("PeakUsage")) / 1024.0
        result.append(
            {
                "name": row.get("Name"),
                "allocated_base_gb": round2(allocated_gb),
                "current_usage_gb": round2(current_gb),
                "peak_usage_gb": round2(peak_gb),
            }
        )
    return result


def pagefile_settings() -> list[dict[str, Any]]:
    payload = run_powershell_json(
        "Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue | "
        "Select-Object Name,InitialSize,MaximumSize | ConvertTo-Json -Depth 4"
    )
    if payload is None:
        return []
    if isinstance(payload, dict) and "returncode" in payload:
        return []
    rows = payload if isinstance(payload, list) else [payload]
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "name": row.get("Name"),
                "initial_size_gb": round2(as_float(row.get("InitialSize")) / 1024.0),
                "maximum_size_gb": round2(as_float(row.get("MaximumSize")) / 1024.0),
            }
        )
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    readiness = read_json(args.readiness_json)
    values = (readiness.get("preflight") or {}).get("values") or {}
    processes = readiness.get("top_private_processes") or []
    large_processes = readiness.get("large_private_processes") or []

    commit_total = as_float(values.get("commit_total_gb"))
    commit_limit = as_float(values.get("commit_limit_gb"))
    headroom = as_float(values.get("commit_headroom_gb"))
    required_headroom = as_float(values.get("min_commit_headroom_gb")) or float(args.min_commit_headroom_gb)
    reclaim_private_gb = sum(as_float(row.get("private_gb")) for row in large_processes)
    projected_commit_total_after_reclaim = max(0.0, commit_total - reclaim_private_gb)
    projected_headroom_after_reclaim = commit_limit - projected_commit_total_after_reclaim
    remaining_deficit_after_reclaim = max(0.0, required_headroom - projected_headroom_after_reclaim)
    required_commit_limit_after_reclaim = projected_commit_total_after_reclaim + required_headroom
    additional_commit_limit_needed_now = max(0.0, required_commit_limit_after_reclaim - commit_limit)
    recommended_additional_commit_limit = additional_commit_limit_needed_now + args.safety_margin_gb
    recommended_commit_limit = commit_limit + recommended_additional_commit_limit

    usage_payload = run_powershell_json(
        "Get-CimInstance Win32_PageFileUsage | "
        "Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | ConvertTo-Json -Depth 4"
    )
    settings_payload = run_powershell_json(
        "Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue | "
        "Select-Object Name,InitialSize,MaximumSize | ConvertTo-Json -Depth 4"
    )
    usage_query_error = usage_payload if isinstance(usage_payload, dict) and "returncode" in usage_payload else None
    settings_query_error = (
        settings_payload if isinstance(settings_payload, dict) and "returncode" in settings_payload else None
    )
    usage = []
    if usage_payload is not None and usage_query_error is None:
        rows = usage_payload if isinstance(usage_payload, list) else [usage_payload]
        for row in rows:
            usage.append(
                {
                    "name": row.get("Name"),
                    "allocated_base_gb": round2(as_float(row.get("AllocatedBaseSize")) / 1024.0),
                    "current_usage_gb": round2(as_float(row.get("CurrentUsage")) / 1024.0),
                    "peak_usage_gb": round2(as_float(row.get("PeakUsage")) / 1024.0),
                }
            )
    settings = []
    if settings_payload is not None and settings_query_error is None:
        rows = settings_payload if isinstance(settings_payload, list) else [settings_payload]
        for row in rows:
            settings.append(
                {
                    "name": row.get("Name"),
                    "initial_size_gb": round2(as_float(row.get("InitialSize")) / 1024.0),
                    "maximum_size_gb": round2(as_float(row.get("MaximumSize")) / 1024.0),
                }
            )
    current_pagefile_allocated = sum(as_float(row.get("allocated_base_gb")) for row in usage)
    explicit_pagefile_setting_present = bool(settings)
    if usage_query_error or settings_query_error:
        setting_mode = "unknown_query_failed"
    else:
        setting_mode = "explicit" if explicit_pagefile_setting_present else "system_managed_or_unspecified"
    recommendation = {
        "do_not_start_compile_now": True,
        "close_large_private_processes_first": bool(large_processes),
        "increase_commit_limit_or_pagefile_before_compile": remaining_deficit_after_reclaim > 0,
        "rerun_readiness_after_changes": True,
        "single_segment_compile_gate": "compile_ready must be true and remote manifest must be absent or intentionally overwritten",
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "blocked_dream7b_b4_compile_capacity_plan"
        if remaining_deficit_after_reclaim > 0
        else "ready_after_large_process_reclaim_dream7b_b4_compile_capacity_plan",
        "source_paths": {"readiness_json": str(args.readiness_json)},
        "compile_guard": {
            "required_commit_headroom_gb": required_headroom,
            "safety_margin_gb": args.safety_margin_gb,
        },
        "current_commit": {
            "commit_total_gb": commit_total,
            "commit_limit_gb": commit_limit,
            "commit_headroom_gb": headroom,
            "commit_headroom_deficit_gb": max(0.0, required_headroom - headroom),
        },
        "large_private_processes": large_processes,
        "projected_after_closing_large_private_processes": {
            "reclaim_private_gb": round2(reclaim_private_gb),
            "commit_total_gb": round2(projected_commit_total_after_reclaim),
            "commit_headroom_gb": round2(projected_headroom_after_reclaim),
            "remaining_headroom_deficit_gb": round2(remaining_deficit_after_reclaim),
            "required_commit_limit_gb": round2(required_commit_limit_after_reclaim),
            "additional_commit_limit_needed_gb": round2(additional_commit_limit_needed_now),
        },
        "pagefile": {
            "usage": usage,
            "settings": settings,
            "usage_query_error": usage_query_error,
            "settings_query_error": settings_query_error,
            "current_allocated_total_gb": round2(current_pagefile_allocated),
            "explicit_pagefile_setting_present": explicit_pagefile_setting_present,
            "setting_mode": setting_mode,
            "recommended_additional_commit_limit_with_safety_gb": round2(recommended_additional_commit_limit),
            "recommended_commit_limit_gb": round2(recommended_commit_limit),
        },
        "top_private_processes": processes,
        "recommendation": recommendation,
        "next_actions": [
            "Close the large tf2 Python process or otherwise reclaim equivalent commit.",
            "Increase Windows commit limit/pagefile by at least the remaining deficit plus safety margin before compiling.",
            "Re-run dream7b_b4_last_token_compile_readiness.py and require compile_ready=true.",
            "Start only the seg27_28 last-token compile after the readiness gate passes.",
        ],
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    current = payload["current_commit"]
    projected = payload["projected_after_closing_large_private_processes"]
    pagefile = payload["pagefile"]
    largest = next(iter(payload["large_private_processes"]), {})
    lines = [
        "# Dream7B B4 Compile Capacity Plan",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        "",
        "## Current Commit",
        "",
        f"- commit_total_gb: {current['commit_total_gb']}",
        f"- commit_limit_gb: {current['commit_limit_gb']}",
        f"- commit_headroom_gb: {current['commit_headroom_gb']}",
        f"- required_commit_headroom_gb: {payload['compile_guard']['required_commit_headroom_gb']}",
        f"- commit_headroom_deficit_gb: {current['commit_headroom_deficit_gb']}",
        "",
        "## Largest Reclaim Candidate",
        "",
        f"- pid: {largest.get('pid')}",
        f"- process_name: {largest.get('process_name')}",
        f"- path: {largest.get('path')}",
        f"- private_gb: {largest.get('private_gb')}",
        f"- working_gb: {largest.get('working_gb')}",
        "",
        "## Projection After Closing Large Private Processes",
        "",
        f"- reclaim_private_gb: {projected['reclaim_private_gb']}",
        f"- projected_commit_total_gb: {projected['commit_total_gb']}",
        f"- projected_commit_headroom_gb: {projected['commit_headroom_gb']}",
        f"- remaining_headroom_deficit_gb: {projected['remaining_headroom_deficit_gb']}",
        f"- required_commit_limit_gb: {projected['required_commit_limit_gb']}",
        f"- additional_commit_limit_needed_gb: {projected['additional_commit_limit_needed_gb']}",
        "",
        "## Pagefile",
        "",
        f"- setting_mode: {pagefile['setting_mode']}",
        f"- current_allocated_total_gb: {pagefile['current_allocated_total_gb']}",
        f"- recommended_additional_commit_limit_with_safety_gb: {pagefile['recommended_additional_commit_limit_with_safety_gb']}",
        f"- recommended_commit_limit_gb: {pagefile['recommended_commit_limit_gb']}",
        "",
    ]
    if pagefile.get("usage_query_error") or pagefile.get("settings_query_error"):
        lines.extend(
            [
                "- query_status: failed",
                f"- usage_query_returncode: {(pagefile.get('usage_query_error') or {}).get('returncode')}",
                f"- settings_query_returncode: {(pagefile.get('settings_query_error') or {}).get('returncode')}",
            ]
        )
    elif pagefile["usage"]:
        lines.extend(
            [
                "| name | allocated_gb | current_usage_gb | peak_usage_gb |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for row in pagefile["usage"]:
            lines.append(
                f"| {row.get('name')} | {row.get('allocated_base_gb')} | "
                f"{row.get('current_usage_gb')} | {row.get('peak_usage_gb')} |"
            )
    else:
        lines.append("- query_status: ok_no_usage_rows")
    lines.extend(["", "## Recommendation", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["recommendation"].items())
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["source_paths"].items())
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan Windows commit/pagefile capacity for B4 last-token compile.")
    parser.add_argument(
        "--readiness-json",
        type=Path,
        default=Path("tmp/b4_runtime_schedule_analysis_20260619/dream7b_b4_last_token_compile_readiness_20260619.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_compile_capacity_plan_20260619")
    parser.add_argument("--min-commit-headroom-gb", type=int, default=64)
    parser.add_argument("--safety-margin-gb", type=int, default=8)
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
