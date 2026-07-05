#!/usr/bin/env python3
"""Validate the Dream7B 31-row truth export."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_COUNTS = {
    "semantic_original": 8,
    "canonical": 3,
    "block_wise": 4,
    "revision": 4,
    "fixed_output": 4,
    "infill": 4,
    "control_command": 4,
}
VALID_DTYPES = {"bfloat16", "float32", "bf16|fp32"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT / path


def check_array(info: dict[str, Any], expected_rank: int | None, errors: list[str], label: str) -> dict[str, Any]:
    path = resolve(info.get("path", ""))
    result: dict[str, Any] = {"path": str(path), "exists": path.exists(), "label": label}
    if not path.exists():
        errors.append(f"{label}: missing array {path}")
        return result
    actual_sha = sha256_file(path)
    result["sha256"] = actual_sha
    if info.get("sha256") and actual_sha != info["sha256"]:
        errors.append(f"{label}: sha256 mismatch")
    try:
        arr = np.load(path)
        result["shape"] = list(arr.shape)
        result["dtype"] = str(arr.dtype)
        result["finite"] = bool(np.isfinite(arr.astype(np.float64, copy=False)).all())
        result["nan_count"] = int(np.isnan(arr.astype(np.float64, copy=False)).sum())
        result["inf_count"] = int(np.isinf(arr.astype(np.float64, copy=False)).sum())
        if expected_rank is not None and arr.ndim != expected_rank:
            errors.append(f"{label}: rank {arr.ndim} != {expected_rank}")
        if not result["finite"]:
            errors.append(f"{label}: non-finite values")
    except Exception as exc:
        errors.append(f"{label}: failed to load array {type(exc).__name__}: {exc}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth-jsonl", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31.jsonl"))
    ap.add_argument("--report-json", default=str(ROOT / "dream_s100p_lladacpp" / "reports" / "30220_full_truth_31_validation_gate.json"))
    ap.add_argument("--report-md", default=str(ROOT / "dream_s100p_lladacpp" / "reports" / "30220_full_truth_31_validation_gate.md"))
    args = ap.parse_args()

    rows = read_jsonl(Path(args.truth_jsonl))
    errors: list[str] = []
    counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    array_checks = []
    for row in rows:
        cid = row.get("case_id", "<missing>")
        ctype = row.get("case_type", "<missing>")
        counts[ctype] = counts.get(ctype, 0) + 1
        if cid in seen_ids:
            errors.append(f"duplicate case_id {cid}")
        seen_ids.add(cid)
        for key in ["input_ids", "attention_mask", "position_ids", "diffusion_mask", "committed_token_mask", "revision_mask"]:
            if len(row.get(key, [])) != 128:
                errors.append(f"{cid}: {key} length {len(row.get(key, []))} != 128")
        if row.get("dtype") not in VALID_DTYPES:
            errors.append(f"{cid}: invalid dtype {row.get('dtype')}")
        if not row.get("model_identity"):
            errors.append(f"{cid}: missing model_identity")
        if not row.get("tokenizer_identity"):
            errors.append(f"{cid}: missing tokenizer_identity")
        if not isinstance(row.get("top1"), int):
            errors.append(f"{cid}: top1 missing")
        if len(row.get("top5", [])) != 5:
            errors.append(f"{cid}: top5 length != 5")
        probs = row.get("probabilities", {}).get("top5_probabilities", [])
        if len(probs) != 5 or not all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in probs):
            errors.append(f"{cid}: invalid top5 probabilities")
        array_checks.append(check_array(row.get("logits", {}), 1, errors, f"{cid}:logits"))
        array_checks.append(check_array(row.get("selected_layer_hidden", {}), 2, errors, f"{cid}:selected_layer_hidden"))
    if len(rows) != 31:
        errors.append(f"truth_row_count expected 31 got {len(rows)}")
    for ctype, expected in REQUIRED_COUNTS.items():
        if counts.get(ctype, 0) != expected:
            errors.append(f"{ctype}: expected {expected}, got {counts.get(ctype, 0)}")

    report = {
        "schema_version": "dream7b_s100p_lladacpp_full_truth_31_validation_gate_v1",
        "truth_jsonl": str(Path(args.truth_jsonl)),
        "truth_row_count": len(rows),
        "case_type_counts": counts,
        "required_counts": REQUIRED_COUNTS,
        "case_type_coverage_complete": all(counts.get(k, 0) == v for k, v in REQUIRED_COUNTS.items()),
        "array_checks": array_checks,
        "errors": errors,
        "full_truth_valid": not errors,
        "verdict": "full_truth_31_valid" if not errors else "external_truth_missing_after_exhaustive_attempts_review_required",
        "safety": {
            "generation_quality_run": False,
            "product_routes_18888_18889_touched": False,
            "dream7b_frontend_openclaw_traffic_touched": False,
            "harness_qwen_openclaw_defaults_modified": False,
        },
    }
    write_json(Path(args.report_json), report)
    md = [
        "# Full Truth 31 Validation Gate",
        "",
        f"- Verdict: `{report['verdict']}`",
        f"- Full truth valid: `{report['full_truth_valid']}`",
        f"- Truth rows: `{len(rows)}`",
        f"- Case type coverage complete: `{report['case_type_coverage_complete']}`",
    ]
    if errors:
        md.append("")
        md.append("## Errors")
        md.extend(f"- {err}" for err in errors[:50])
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"full_truth_valid": report["full_truth_valid"], "truth_row_count": len(rows)}, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
