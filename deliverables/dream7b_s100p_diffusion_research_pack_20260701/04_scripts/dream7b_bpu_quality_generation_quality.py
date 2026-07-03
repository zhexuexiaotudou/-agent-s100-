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


STEM = "dream7b_bpu_quality_generation_quality"
DEFAULT_PROMPTS = [
    "请用一句话说明你是谁。",
    "请用两句话解释本地 NAS 智能层的作用。",
    "请给出一个文件去重前的安全检查步骤。",
]


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    rollback = rollback_context(args.rollback_json)
    results = read_json(args.results_json) if args.results_json else None
    summary = (results or {}).get("summary") or results or {}
    prompt_results = (results or {}).get("prompt_results") or []
    readable_count = as_int(summary.get("readable_chinese_prompt_count"), 0)
    failed_count = as_int(summary.get("failed_prompt_count"), len(DEFAULT_PROMPTS))

    errors: list[str] = []
    if rollback["candidate_artifact_present"] is not True:
        errors.append("candidate_artifact_missing")
    if rollback["candidate_manifest_verified"] is not True:
        errors.append("candidate_manifest_not_verified")
    if results is None:
        errors.append("results_json_missing")
    if readable_count < args.min_readable_chinese_prompts:
        errors.append("readable_chinese_prompt_count_below_threshold")
    if failed_count != 0:
        errors.append("generation_failed_prompt_count_nonzero")

    ready = not errors
    return {
        "generated_at": generated_at(),
        "verdict": f"ready_{STEM}" if ready else f"blocked_{STEM}",
        "candidate_id": args.candidate_id,
        "ready": ready,
        "errors": errors,
        "summary": {
            "readable_chinese_prompt_count": readable_count,
            "failed_prompt_count": failed_count,
            "prompt_count": summary.get("prompt_count", len(DEFAULT_PROMPTS)),
        },
        "thresholds": {
            "min_readable_chinese_prompts": args.min_readable_chinese_prompts,
            "failed_prompt_count": 0,
        },
        "prompts": DEFAULT_PROMPTS,
        "prompt_results": prompt_results,
        "source": {
            "rollback": rollback,
            "results_json": str(args.results_json) if args.results_json else None,
            "results_loaded": results is not None,
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
        "# Dream7B BPU Quality Generation Quality",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate_id: `{payload['candidate_id']}`",
        f"- ready: `{payload['ready']}`",
        f"- readable_chinese_prompt_count: `{summary['readable_chinese_prompt_count']}`",
        f"- failed_prompt_count: `{summary['failed_prompt_count']}`",
        "- compile_started_by_this_probe: `False`",
        "- service_restarted_by_this_probe: `False`",
        "",
        "## Prompts",
        "",
    ]
    lines.extend(f"- {prompt}" for prompt in payload["prompts"])
    lines.extend(["", "## Errors", ""])
    if payload["errors"]:
        lines.extend(f"- `{item}`" for item in payload["errors"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument("--rollback-json", type=Path, default=DEFAULT_ROLLBACK_JSON)
    parser.add_argument("--results-json", type=Path)
    parser.add_argument("--min-readable-chinese-prompts", type=int, default=3)
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
