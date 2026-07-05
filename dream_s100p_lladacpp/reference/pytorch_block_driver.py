#!/usr/bin/env python3
"""Truth replay block driver for the Dream7B llada.cpp-style track.

This is a PyTorch-reference gate over exported truth rows. It does not run BPU
graphs and does not claim product generation.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def resolve(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT / path


def load_logits(row: dict[str, Any]) -> np.ndarray:
    return np.load(resolve(row["logits"]["path"])).astype(np.float64)


def compute_token_confidence(logits: np.ndarray) -> float:
    x = logits.reshape(-1)
    x = x - float(np.max(x))
    exp = np.exp(x)
    return float(np.max(exp / np.sum(exp)))


def replay_truth_case(row: dict[str, Any]) -> dict[str, Any]:
    logits = load_logits(row)
    confidence = compute_token_confidence(logits)
    block_state = row.get("block_token_states", {})
    target_positions = block_state.get("target_positions", [])
    committed_mask = row.get("committed_token_mask", [])
    revision_mask = row.get("revision_mask", [])
    errors = []
    if logits.ndim != 1:
        errors.append("logits_rank_not_1")
    if len(committed_mask) != 128:
        errors.append("committed_mask_len_invalid")
    if len(revision_mask) != 128:
        errors.append("revision_mask_len_invalid")
    if row["case_type"] in {"block_wise", "revision", "fixed_output", "infill", "control_command"} and not target_positions:
        errors.append("target_positions_missing")
    if row["case_type"] == "revision" and not any(revision_mask):
        errors.append("revision_mask_empty")
    return {
        "case_id": row["case_id"],
        "case_type": row["case_type"],
        "block_size": block_state.get("block_size"),
        "target_position_count": len(target_positions),
        "committed_token_count": int(sum(int(x) for x in committed_mask)),
        "revision_token_count": int(sum(int(x) for x in revision_mask)),
        "top1": row.get("top1"),
        "top5": row.get("top5"),
        "last_token_confidence": confidence,
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth-jsonl", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31.jsonl"))
    ap.add_argument("--trace-jsonl", default=str(ROOT / "dream_s100p_lladacpp" / "reports" / "pytorch_block_driver_traces.jsonl"))
    ap.add_argument("--report-json", default=str(ROOT / "dream_s100p_lladacpp" / "reports" / "30230_pytorch_block_driver_gate.json"))
    ap.add_argument("--report-md", default=str(ROOT / "dream_s100p_lladacpp" / "reports" / "30230_pytorch_block_driver_gate.md"))
    args = ap.parse_args()

    started = time.time()
    rows = read_jsonl(Path(args.truth_jsonl))
    traces = [replay_truth_case(row) for row in rows]
    write_jsonl(Path(args.trace_jsonl), traces)
    failures = [row for row in traces if row["status"] != "pass"]
    counts: dict[str, int] = {}
    pass_counts: dict[str, int] = {}
    for trace in traces:
        ctype = trace["case_type"]
        counts[ctype] = counts.get(ctype, 0) + 1
        if trace["status"] == "pass":
            pass_counts[ctype] = pass_counts.get(ctype, 0) + 1
    required_truth_replay_types = ["block_wise", "revision", "fixed_output", "infill", "control_command"]
    replay_types_pass = all(counts.get(t, 0) > 0 and counts.get(t, 0) == pass_counts.get(t, 0) for t in required_truth_replay_types)
    gate_pass = len(rows) == 31 and not failures and replay_types_pass
    report = {
        "schema_version": "dream7b_s100p_lladacpp_pytorch_block_driver_gate_v1",
        "truth_row_count": len(rows),
        "trace_jsonl": str(Path(args.trace_jsonl)),
        "case_type_counts": counts,
        "case_type_pass_counts": pass_counts,
        "all_31_truth_rows_replayed": len(rows) == 31 and not failures,
        "block_revision_fixed_infill_control_pass": replay_types_pass,
        "failures": failures,
        "gate_pass": gate_pass,
        "verdict": "pytorch_block_driver_truth_replay_pass" if gate_pass else "fixed_block_tasks_failed_review_required",
        "claim_boundary": "This is exported-truth replay of block/revision masks, not a BPU runtime or product generation claim.",
        "elapsed_seconds": round(time.time() - started, 3),
        "safety": {
            "generation_quality_run": False,
            "product_routes_18888_18889_touched": False,
            "dream7b_frontend_openclaw_traffic_touched": False,
            "harness_qwen_openclaw_defaults_modified": False,
        },
    }
    write_json(Path(args.report_json), report)
    md = [
        "# PyTorch Block Driver Gate",
        "",
        f"- Verdict: `{report['verdict']}`",
        f"- Gate pass: `{gate_pass}`",
        f"- Truth rows replayed: `{len(rows)}`",
        f"- Claim boundary: {report['claim_boundary']}",
    ]
    if failures:
        md.append("")
        md.append("## Failures")
        md.extend(f"- `{f['case_id']}`: {f['errors']}" for f in failures[:50])
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"gate_pass": gate_pass, "truth_rows": len(rows)}, ensure_ascii=False))
    return 0 if gate_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
