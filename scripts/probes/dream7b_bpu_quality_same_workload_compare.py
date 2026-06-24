#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dream7b_bpu_quality_validation_common import (
    DEFAULT_CANDIDATE_ID,
    DEFAULT_KNOWN_HOSTS,
    DEFAULT_OUT_ROOT,
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_REPORT_ROOT,
    DEFAULT_ROLLBACK_JSON,
    DEFAULT_SSH_KEY,
    generated_at,
    read_json,
    rollback_context,
    sync_to_nas,
    now_stamp,
    write_latest,
)


STEM = "dream7b_bpu_quality_same_workload_compare"


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


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    rollback = rollback_context(args.rollback_json)
    metrics = read_json(args.metrics_json) if args.metrics_json else None
    summary = (metrics or {}).get("summary") or metrics or {}
    same_workload = summary.get("same_workload")
    processed = as_int(summary.get("processed_request_count"), 0)
    baseline_ms = as_float(summary.get("baseline_ms_per_request"), 0.0)
    candidate_ms = as_float(summary.get("candidate_ms_per_request"), 1e9)
    complements = summary.get("complements_baseline")

    errors: list[str] = []
    if rollback["candidate_artifact_present"] is not True:
        errors.append("candidate_artifact_missing")
    if rollback["candidate_manifest_verified"] is not True:
        errors.append("candidate_manifest_not_verified")
    if metrics is None:
        errors.append("metrics_json_missing")
    if same_workload is not True:
        errors.append("not_same_workload")
    if processed < args.min_same_workload_requests:
        errors.append("processed_request_count_below_threshold")
    if baseline_ms <= 0:
        errors.append("baseline_ms_per_request_missing")
    if candidate_ms > baseline_ms and complements is not True:
        errors.append("candidate_slower_without_complement_reason")

    ready = not errors
    return {
        "generated_at": generated_at(),
        "verdict": f"ready_{STEM}" if ready else f"blocked_{STEM}",
        "candidate_id": args.candidate_id,
        "ready": ready,
        "errors": errors,
        "summary": {
            "same_workload": same_workload,
            "processed_request_count": processed,
            "baseline_ms_per_request": baseline_ms,
            "candidate_ms_per_request": candidate_ms,
            "complements_baseline": complements,
        },
        "thresholds": {
            "same_workload": True,
            "min_same_workload_requests": args.min_same_workload_requests,
            "candidate_must_not_be_slower_unless_complements_baseline": True,
        },
        "source": {
            "rollback": rollback,
            "metrics_json": str(args.metrics_json) if args.metrics_json else None,
            "metrics_loaded": metrics is not None,
        },
        "policy": {
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
            "production_write_performed_by_this_probe": False,
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B BPU Quality Same-Workload Compare",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate_id: `{payload['candidate_id']}`",
        f"- ready: `{payload['ready']}`",
        f"- same_workload: `{summary['same_workload']}`",
        f"- processed_request_count: `{summary['processed_request_count']}`",
        f"- baseline_ms_per_request: `{summary['baseline_ms_per_request']}`",
        f"- candidate_ms_per_request: `{summary['candidate_ms_per_request']}`",
        f"- complements_baseline: `{summary['complements_baseline']}`",
        "- compile_started_by_this_probe: `False`",
        "- service_restarted_by_this_probe: `False`",
        "",
        "## Errors",
        "",
    ]
    if payload["errors"]:
        lines.extend(f"- `{item}`" for item in payload["errors"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument("--rollback-json", type=Path, default=DEFAULT_ROLLBACK_JSON)
    parser.add_argument("--metrics-json", type=Path)
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
    report_dir = args.out_root / f"{STEM}_{now_stamp()}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / f"{STEM}.json"
    md_path = report_dir / f"{STEM}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    if not args.no_sync:
        sync = sync_to_nas(args, report_dir, f"{STEM}.json", f"{STEM}.md")
        payload["sync"] = sync
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(md_path, payload)
        if sync.get("ok") is False:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
    write_latest(args.out_root, STEM, json_path, md_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
