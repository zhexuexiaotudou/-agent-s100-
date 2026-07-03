#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dream7b_research_common import compare_vectors, iter_jsonl, now_iso, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare BF16 and S100P boundary activations.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--bf16-root", required=True)
    parser.add_argument("--s100p-root", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    rows = []
    errors = []
    first_divergent = None
    for case in iter_jsonl(Path(args.cases)):
        case_id = case["case_id"]
        seg_rows = []
        for i in range(28):
            bf16_path = Path(args.bf16_root) / case_id / f"seg_{i:02d}_output.npy"
            s100p_path = Path(args.s100p_root) / case_id / f"seg_{i:02d}_output.npy"
            if not bf16_path.is_file() or not s100p_path.is_file():
                errors.append(f"boundary_missing:{case_id}:seg{i:02d}")
                continue
            cmp = compare_vectors(np.load(bf16_path), np.load(s100p_path))
            seg_rows.append({"segment": i, "compare": cmp})
            if first_divergent is None and cmp.get("cosine") is not None and cmp.get("cosine") < 0.95:
                first_divergent = {"case_id": case_id, "segment": i, "cosine": cmp.get("cosine")}
        rows.append({"case_id": case_id, "segments": seg_rows})
    verdict = "inconclusive_boundary_compare_bf16_missing" if errors and all(e.startswith("boundary_missing") for e in errors) else ("ok_boundary_compare" if not errors and first_divergent is None else "failed_boundary_compare")
    payload = {"created_at": now_iso(), "verdict": verdict, "first_divergent_segment": first_divergent, "errors": sorted(set(errors)), "cases": rows}
    write_json(Path(args.output_json), payload)
    write_text(Path(args.output_md), "# Segment Boundary Compare\n\n" + f"- verdict: `{verdict}`\n- first_divergent_segment: `{first_divergent}`\n- error_count: `{len(payload['errors'])}`\n")
    print(args.output_json)
    return 0 if verdict.startswith("ok_") else 2


if __name__ == "__main__":
    raise SystemExit(main())

