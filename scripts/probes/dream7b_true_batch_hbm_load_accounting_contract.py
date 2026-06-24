#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_true_batch_hbm_load_accounting_contract"
DEFAULT_SOURCE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_OUT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")


def line_number(lines: list[str], token: str) -> int | None:
    for lineno, line in enumerate(lines, start=1):
        if token in line:
            return lineno
    return None


def token_check(lines: list[str], token: str) -> dict[str, Any]:
    line = line_number(lines, token)
    return {"token": token, "present": line is not None, "line": line}


def build_payload(source_path: Path) -> dict[str, Any]:
    text = source_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    required_tokens = {
        "hbm_runtime_load_timed": "runtime = HB_HBMRuntime(str(path))",
        "per_segment_load_ms": '"load_ms": round(load_ms, 3),',
        "per_segment_hbm_path": '"hbm_path": str(path),',
        "per_segment_hbm_size_bytes": '"hbm_size_bytes": hbm_size_bytes,',
        "per_segment_hbm_size_mib": '"hbm_size_mib": round(hbm_size_bytes / 1024 / 1024, 3) if hbm_size_bytes is not None else None,',
        "loaded_segment_summary_path": '"hbm_path": str(item["hbm_path"]),',
        "loaded_segment_summary_size": '"hbm_size_mib": item.get("hbm_size_mib"),',
        "loaded_segment_summary_load": '"load_ms": item.get("load_ms"),',
        "group_load_timer": "group_load_ms = (time.perf_counter() - load_start) * 1000",
        "group_load_reported": '"group_load_ms": round(group_load_ms, 3),',
        "loaded_count_reported": '"loaded_count": len(loaded),',
        "loaded_segments_reported": '"loaded_segments": loaded_segment_summary(loaded),',
        "group_release_timer": "group_release_ms = (time.perf_counter() - release_start) * 1000",
        "group_release_reported": 'group_rows[-1]["group_release_ms"] = round(group_release_ms, 3)',
        "release_gc_mode_reported": 'group_rows[-1]["release_gc_mode"] = args.release_gc_mode',
        "prewarm_explicit_flag": 'parser.add_argument("--prewarm-hbm", action="store_true"',
        "prewarm_files_function": "def prewarm_hbm_files(paths: list[Path], chunk_bytes: int) -> dict[str, Any]:",
        "prewarm_file_ms": '"prewarm_ms": round((time.perf_counter() - file_started) * 1000, 3),',
        "prewarm_total_ms": '"hbm_prewarm_ms": round((time.perf_counter() - started) * 1000, 3),',
        "prewarm_total_bytes": '"hbm_prewarm_bytes": total_bytes,',
        "prewarm_files_reported": '"hbm_prewarm_files": files,',
        "timing_total_group_load": '"total_group_load_ms": round(total_group_load_ms, 3),',
        "timing_group_load_fraction": '"group_load_fraction_of_wall": round(total_group_load_ms / wall_ms, 4) if wall_ms > 0 else None,',
        "timing_hbm_prewarm_fraction": '"hbm_prewarm_fraction_of_wall": round(total_hbm_prewarm_ms / wall_ms, 4) if wall_ms > 0 and total_hbm_prewarm_ms else None,',
        "host_gap_subtracts_load": "wall_ms - total_hbm_prewarm_ms - total_group_load_ms - measured_active_ms",
    }
    checks = {name: token_check(lines, token) for name, token in required_tokens.items()}
    missing = [name for name, row in checks.items() if not row["present"]]
    per_segment_ready = all(
        checks[name]["present"]
        for name in [
            "hbm_runtime_load_timed",
            "per_segment_load_ms",
            "per_segment_hbm_path",
            "per_segment_hbm_size_bytes",
            "per_segment_hbm_size_mib",
            "loaded_segment_summary_path",
            "loaded_segment_summary_size",
            "loaded_segment_summary_load",
        ]
    )
    group_ready = all(
        checks[name]["present"]
        for name in [
            "group_load_timer",
            "group_load_reported",
            "loaded_count_reported",
            "loaded_segments_reported",
            "group_release_timer",
            "group_release_reported",
            "release_gc_mode_reported",
        ]
    )
    prewarm_ready = all(
        checks[name]["present"]
        for name in [
            "prewarm_explicit_flag",
            "prewarm_files_function",
            "prewarm_file_ms",
            "prewarm_total_ms",
            "prewarm_total_bytes",
            "prewarm_files_reported",
        ]
    )
    timing_ready = all(
        checks[name]["present"]
        for name in [
            "timing_total_group_load",
            "timing_group_load_fraction",
            "timing_hbm_prewarm_fraction",
            "host_gap_subtracts_load",
        ]
    )
    verdict = (
        "ok_dream7b_true_batch_hbm_load_accounting_contract"
        if not missing and per_segment_ready and group_ready and prewarm_ready and timing_ready
        else "failed_dream7b_true_batch_hbm_load_accounting_contract"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_path": str(source_path),
        "checks": checks,
        "missing_checks": missing,
        "summary": {
            "per_segment_load_accounting_ready": per_segment_ready,
            "group_load_accounting_ready": group_ready,
            "prewarm_accounting_ready": prewarm_ready,
            "timing_summary_accounts_load_and_prewarm": timing_ready,
            "prewarm_hbm_default_changed": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
        },
        "accounted_fields": [
            "loaded_segments[].hbm_path",
            "loaded_segments[].hbm_size_bytes",
            "loaded_segments[].hbm_size_mib",
            "loaded_segments[].load_ms",
            "group_rows[].group_load_ms",
            "group_rows[].group_release_ms",
            "group_rows[].release_gc_mode",
            "group_rows[].hbm_prewarm_ms",
            "group_rows[].hbm_prewarm_bytes",
            "group_rows[].hbm_prewarm_files",
            "timing_summary.total_group_load_ms",
            "timing_summary.group_load_fraction_of_wall",
            "timing_summary.hbm_prewarm_fraction_of_wall",
        ],
        "purpose": (
            "Keep HBM load, optional prewarm, and group release time separately attributable "
            "in true-batch B=4 telemetry before changing scheduling policy or queue-batch "
            "production defaults."
        ),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B True-Batch HBM Load Accounting Contract",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- source_path: `{payload['source_path']}`",
        f"- per_segment_load_accounting_ready: `{summary['per_segment_load_accounting_ready']}`",
        f"- group_load_accounting_ready: `{summary['group_load_accounting_ready']}`",
        f"- prewarm_accounting_ready: `{summary['prewarm_accounting_ready']}`",
        f"- timing_summary_accounts_load_and_prewarm: `{summary['timing_summary_accounts_load_and_prewarm']}`",
        f"- prewarm_hbm_default_changed: `{summary['prewarm_hbm_default_changed']}`",
        f"- runtime_started: `{summary['runtime_started']}`",
        f"- compile_started: `{summary['compile_started']}`",
        "",
        "## Accounted Fields",
        "",
    ]
    lines.extend(f"- `{field}`" for field in payload["accounted_fields"])
    lines.extend(["", "## Checks", ""])
    for name, row in payload["checks"].items():
        lines.append(f"- {name}: present `{row['present']}` line `{row['line']}`")
    if payload["missing_checks"]:
        lines.extend(["", "## Missing", ""])
        lines.extend(f"- {item}" for item in payload["missing_checks"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate static HBM load/prewarm/group-release accounting in the true-batch telemetry probe."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    args = parser.parse_args()

    payload = build_payload(args.source)
    args.out_root.mkdir(parents=True, exist_ok=True)
    json_path = args.out_root / "dream7b_true_batch_hbm_load_accounting_contract_20260621.json"
    md_path = args.out_root / "dream7b_true_batch_hbm_load_accounting_contract_20260621.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    print(json_path)
    print(md_path)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
