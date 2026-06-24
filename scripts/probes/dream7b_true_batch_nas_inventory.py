#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SNAPSHOT_LABEL = datetime.now().strftime("%Y%m%d")


def default_out_json(label: str) -> Path:
    return DEFAULT_OUT_ROOT / f"dream7b_true_batch_nas_inventory_{label}.json"


def default_out_md(label: str) -> Path:
    return DEFAULT_OUT_ROOT / f"dream7b_true_batch_nas_inventory_{label}.md"


def run_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def parse_batch_from_name(name: str) -> int | None:
    match = re.search(r"_b(\d+)(?:$|[^\d])", name)
    return int(match.group(1)) if match else None


def parse_microbatch_from_name(name: str) -> int | None:
    match = re.search(r"_mb(\d+)", name)
    return int(match.group(1)) if match else None


def parse_inner_order_from_name(name: str) -> str | None:
    if "microbatch_major" in name:
        return "microbatch-major"
    if "segment_major" in name:
        return "segment-major"
    return None


def remote_inventory(args: argparse.Namespace) -> dict[str, Any]:
    remote_script = "\n".join(
        [
            "set -u",
            "REPORT_ROOT=/mnt/nas/openclaw/reports/models",
            "MODEL_ROOT=/mnt/nas/openclaw/models/dream7b-hbm",
            "LAST_ROOT=/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final",
            "echo __REPORT_DIRS__",
            "find \"$REPORT_ROOT\" -maxdepth 1 -type d -name 'dream7b_true_batch_group_major_telemetry_*' -printf '%f\\n' 2>/dev/null | sort",
            "echo __REPORT_JSON_DIRS__",
            "find \"$REPORT_ROOT\" -maxdepth 2 -type f -name 'true_batch_group_major_telemetry.json' -printf '%h\\n' 2>/dev/null | xargs -r -n1 basename | sort",
            "echo __HBM_ROOTS__",
            "find \"$MODEL_ROOT\" -maxdepth 1 -type d -name 'true-batch-seq16-b*' -printf '%f\\n' 2>/dev/null | sort",
            "echo __B4_HBM_COUNT__",
            "find \"$MODEL_ROOT/true-batch-seq16-b4\" -maxdepth 2 -type f -name '*.hbm' 2>/dev/null | wc -l",
            "echo __B4_MANIFEST_COUNT__",
            "find \"$MODEL_ROOT/true-batch-seq16-b4\" -maxdepth 2 -type f -name 'manifest.sha256' 2>/dev/null | wc -l",
            "echo __LAST_TOKEN_FILES__",
            "find \"$LAST_ROOT\" -maxdepth 3 -type f -printf '%f\\n' 2>/dev/null | sort || true",
        ]
    )
    result = ssh_cmd(args, remote_script, timeout=args.remote_timeout_sec)
    sections: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    for raw_line in result["stdout"].splitlines():
        line = raw_line.strip()
        if line.startswith("__") and line.endswith("__"):
            current = line.strip("_").lower()
            continue
        if current is not None and line:
            sections[current].append(line)

    report_dirs = sections.get("report_dirs", [])
    report_json_dirs = sections.get("report_json_dirs", [])
    hbm_roots = sections.get("hbm_roots", [])
    batch_counts = Counter()
    for name in report_dirs:
        batch = parse_batch_from_name(name)
        if batch is not None:
            batch_counts[f"b{batch}"] += 1
    report_json_batch_counts = Counter()
    for name in report_json_dirs:
        batch = parse_batch_from_name(name)
        if batch is not None:
            report_json_batch_counts[f"b{batch}"] += 1
    missing_json_dirs = sorted(set(report_dirs) - set(report_json_dirs))
    return {
        "command": remote_script,
        "returncode": result["returncode"],
        "stderr": result["stderr"],
        "report_dirs": report_dirs,
        "report_json_dirs": report_json_dirs,
        "missing_report_json_dirs": missing_json_dirs,
        "hbm_roots": hbm_roots,
        "group_major_report_count": len(report_dirs),
        "group_major_report_json_count": len(report_json_dirs),
        "batch_counts": dict(sorted(batch_counts.items(), key=lambda item: int(item[0][1:]))),
        "report_json_batch_counts": dict(
            sorted(report_json_batch_counts.items(), key=lambda item: int(item[0][1:]))
        ),
        "b4_group_major_report_count": batch_counts.get("b4", 0),
        "b4_group_major_report_json_count": report_json_batch_counts.get("b4", 0),
        "b4_hbm_count": as_int(next(iter(sections.get("b4_hbm_count", [])), None)),
        "b4_manifest_count": as_int(next(iter(sections.get("b4_manifest_count", [])), None)),
        "last_token_file_count": len(sections.get("last_token_files", [])),
        "last_token_files": sections.get("last_token_files", []),
    }


def group_ranges(payload: dict[str, Any]) -> list[str]:
    ranges = []
    for group in payload.get("group_rows") or []:
        ranges.append(f"{group.get('group_start')}:{group.get('group_end')}")
    return ranges


def local_b4_rows(telemetry_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(telemetry_dir.glob("*.json")):
        payload = read_json(path)
        if as_int(payload.get("batch_size")) != 4:
            continue
        rows.append(
            {
                "file": str(path),
                "name": path.name,
                "generated_at": payload.get("generated_at"),
                "verdict": payload.get("verdict"),
                "microbatch_count": payload.get("microbatch_count"),
                "inner_order": payload.get("inner_order") or parse_inner_order_from_name(path.name),
                "group_count": len(payload.get("group_rows") or []),
                "group_ranges": group_ranges(payload),
                "processed_request_count": payload.get("processed_request_count"),
                "failed_job_count": payload.get("failed_job_count"),
                "ms_per_request": payload.get("amortized_wall_ms_per_request"),
                "avg_bpu_loading": payload.get("avg_bpu_loading"),
                "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
                "final_logits_mode": payload.get("final_logits_mode") or "legacy_full",
                "release_gc_mode": payload.get("release_gc_mode") or "legacy_collect",
                "prewarm_hbm": payload.get("prewarm_hbm"),
                "preallocate_hidden": payload.get("preallocate_hidden"),
            }
        )
    return rows


def local_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_microbatch = Counter(str(row.get("microbatch_count")) for row in rows)
    by_order = Counter(str(row.get("inner_order")) for row in rows)
    by_group_count = Counter(str(row.get("group_count")) for row in rows)
    successful = [row for row in rows if str(row.get("verdict", "")).startswith("ok_")]
    failed = [row for row in rows if not str(row.get("verdict", "")).startswith("ok_")]
    return {
        "local_b4_json_count": len(rows),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "by_microbatch_count": dict(sorted(by_microbatch.items(), key=lambda item: int(item[0]))),
        "by_inner_order": dict(sorted(by_order.items())),
        "by_group_count": dict(sorted(by_group_count.items(), key=lambda item: int(item[0]))),
        "has_mb512_segment_major_5_group": any(
            row.get("microbatch_count") == 512
            and row.get("inner_order") == "segment-major"
            and row.get("group_count") == 5
            and str(row.get("verdict", "")).startswith("ok_")
            for row in rows
        ),
        "has_mb512_microbatch_major": any(
            row.get("microbatch_count") == 512
            and row.get("inner_order") == "microbatch-major"
            and str(row.get("verdict", "")).startswith("ok_")
            for row in rows
        ),
        "has_mb512_nonbaseline_group_splits": any(
            row.get("microbatch_count") == 512
            and row.get("inner_order") == "segment-major"
            and as_int(row.get("group_count")) not in (None, 5)
            and str(row.get("verdict", "")).startswith("ok_")
            for row in rows
        ),
        "has_gap_field_capacity_failures": any(
            row.get("microbatch_count") in (768, 1024)
            and not str(row.get("verdict", "")).startswith("ok_")
            for row in rows
        ),
        "has_last_token_candidate_result": any(
            row.get("final_logits_mode") == "last-token" for row in rows
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    remote = remote_inventory(args)
    rows = local_b4_rows(args.telemetry_dir)
    coverage = local_coverage(rows)
    b4_remote_count = remote.get("b4_group_major_report_count")
    b4_remote_json_count = remote.get("b4_group_major_report_json_count")
    local_count = coverage.get("local_b4_json_count")
    b4_remote_local_count_match = b4_remote_count == local_count
    b4_remote_json_local_count_match = b4_remote_json_count == local_count
    last_token_present = coverage["has_last_token_candidate_result"] or remote["last_token_file_count"] > 0
    duplicate_stop_rules = [
        "Do not rerun mb512 segment-major 5-group baseline; local and NAS evidence already cover it.",
        "Do not rerun mb512 microbatch-major versus segment-major; local and NAS evidence already cover it.",
        "Do not rerun normal mb512 group-boundary sweeps; g6, g7, and final-isolated variants are already covered and did not beat baseline.",
        "Do not rerun gap-field capacity probes at mb768/mb1024 until the memory plan changes; existing B=4 probes failed in current memory state.",
        "Do not rerun prealloc/prewarm/release-GC policy sweeps as normal tuning; existing evidence keeps them experimental or profiling-only.",
    ]
    remaining_nonduplicate = [
        "Compile seg27_28 last-token final logits only after local commit/pagefile readiness passes.",
        "Run mb512 last-token validation only after the remote last-token HBM manifest verifies.",
        "Use dream7b_b4_last_token_validation_compare.py on the resulting telemetry before expanding any runtime sweep.",
        "Queue-batch remains the production baseline unless true-batch evidence clearly beats the gate.",
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_true_batch_nas_inventory",
        "source_paths": {
            "telemetry_dir": str(args.telemetry_dir),
            "remote_report_root": "/mnt/nas/openclaw/reports/models",
            "remote_hbm_root": "/mnt/nas/openclaw/models/dream7b-hbm",
        },
        "remote": remote,
        "local_coverage": coverage,
        "local_b4_rows": rows,
        "decision": {
            "b4_remote_local_count_match": b4_remote_local_count_match,
            "b4_remote_json_local_count_match": b4_remote_json_local_count_match,
            "b4_history_is_already_mirrored_locally": b4_remote_local_count_match
            and b4_remote_json_local_count_match
            and as_int(remote.get("b4_hbm_count")) == 28
            and as_int(remote.get("b4_manifest_count")) == 28,
            "last_token_candidate_already_ran": last_token_present,
            "run_more_standard_b4_runtime_sweeps_now": False,
            "duplicate_stop_rules": duplicate_stop_rules,
            "remaining_nonduplicate_work": remaining_nonduplicate,
        },
    }


def render_md(path: Path, payload: dict[str, Any]) -> None:
    remote = payload["remote"]
    coverage = payload["local_coverage"]
    decision = payload["decision"]
    lines = [
        "# Dream7B True-Batch NAS Inventory",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- remote_group_major_report_count: `{remote['group_major_report_count']}`",
        f"- remote_group_major_report_json_count: `{remote['group_major_report_json_count']}`",
        f"- remote_b4_group_major_report_count: `{remote['b4_group_major_report_count']}`",
        f"- remote_b4_group_major_report_json_count: `{remote['b4_group_major_report_json_count']}`",
        f"- local_b4_json_count: `{coverage['local_b4_json_count']}`",
        f"- b4_remote_local_count_match: `{decision['b4_remote_local_count_match']}`",
        f"- b4_remote_json_local_count_match: `{decision['b4_remote_json_local_count_match']}`",
        f"- b4_history_is_already_mirrored_locally: `{decision['b4_history_is_already_mirrored_locally']}`",
        f"- b4_hbm_count: `{remote['b4_hbm_count']}`",
        f"- b4_manifest_count: `{remote['b4_manifest_count']}`",
        f"- last_token_file_count: `{remote['last_token_file_count']}`",
        f"- last_token_candidate_already_ran: `{decision['last_token_candidate_already_ran']}`",
        f"- run_more_standard_b4_runtime_sweeps_now: `{decision['run_more_standard_b4_runtime_sweeps_now']}`",
        "",
        "## Remote Batch Counts",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in remote["batch_counts"].items())
    lines.extend(["", "## Remote JSON Batch Counts", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in remote["report_json_batch_counts"].items())
    lines.extend(["", "## Missing Report JSON Dirs", ""])
    if remote["missing_report_json_dirs"]:
        lines.extend(f"- `{item}`" for item in remote["missing_report_json_dirs"])
    else:
        lines.append("- none")
    lines.extend(["", "## Local B4 Coverage", ""])
    for key in [
        "successful_count",
        "failed_count",
        "by_microbatch_count",
        "by_inner_order",
        "by_group_count",
        "has_mb512_segment_major_5_group",
        "has_mb512_microbatch_major",
        "has_mb512_nonbaseline_group_splits",
        "has_gap_field_capacity_failures",
        "has_last_token_candidate_result",
    ]:
        lines.append(f"- {key}: `{coverage[key]}`")
    lines.extend(["", "## Duplicate Stop Rules", ""])
    lines.extend(f"- {item}" for item in decision["duplicate_stop_rules"])
    lines.extend(["", "## Remaining Non-Duplicate Work", ""])
    lines.extend(f"- {item}" for item in decision["remaining_nonduplicate_work"])
    lines.extend(
        [
            "",
            "## Local B4 Rows",
            "",
            "| file | verdict | mb | order | groups | ms/request | avg BPU | nonzero BPU | final mode |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in sorted(
        payload["local_b4_rows"],
        key=lambda item: (
            as_int(item.get("microbatch_count")) or -1,
            str(item.get("inner_order")),
            as_int(item.get("group_count")) or -1,
            str(item.get("name")),
        ),
    ):
        lines.append(
            f"| {row['name']} | {row['verdict']} | {row['microbatch_count']} | "
            f"{row['inner_order']} | {row['group_count']} | {row['ms_per_request']} | "
            f"{row['avg_bpu_loading']} | {row['avg_nonzero_bpu_loading']} | "
            f"{row['final_logits_mode']} |"
        )
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory NAS true-batch runs and compare them with local B4 telemetry mirrors."
    )
    parser.add_argument("--telemetry-dir", type=Path, default=Path("tmp/remote_true_batch_reports"))
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--known-hosts", type=Path, default=Path(r"C:\Users\zhexu\.ssh\known_hosts"))
    parser.add_argument("--remote-timeout-sec", type=int, default=30)
    parser.add_argument("--snapshot-label", default=DEFAULT_SNAPSHOT_LABEL)
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()
    if args.out_json is None:
        args.out_json = default_out_json(args.snapshot_label)
    if args.out_md is None:
        args.out_md = default_out_md(args.snapshot_label)

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_md(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
