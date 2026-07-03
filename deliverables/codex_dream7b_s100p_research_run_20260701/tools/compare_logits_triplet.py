#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dream7b_research_common import compare_vectors, iter_jsonl, now_iso, write_json, write_text


def load_npy(path: Path) -> np.ndarray | None:
    return np.load(path) if path.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare BF16, GGUF, and BPU logits for seq128 cases.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--bf16-root", required=True)
    parser.add_argument("--gguf-root", required=True)
    parser.add_argument("--bpu-root", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    rows = []
    errors = []
    for case in iter_jsonl(Path(args.cases)):
        case_id = case["case_id"]
        bf16 = load_npy(Path(args.bf16_root) / case_id / "bf16_last_logits.npy")
        gguf = load_npy(Path(args.gguf_root) / case_id / "gguf_last_logits.npy")
        bpu = load_npy(Path(args.bpu_root) / case_id / "dequant_logits.npy")
        row = {"case_id": case_id, "has_bf16": bf16 is not None, "has_gguf": gguf is not None, "has_bpu": bpu is not None, "comparisons": {}}
        if bf16 is not None and gguf is not None:
            row["comparisons"]["bf16_vs_gguf"] = compare_vectors(bf16, gguf)
        if bf16 is not None and bpu is not None:
            row["comparisons"]["bf16_vs_bpu"] = compare_vectors(bf16, bpu)
        if gguf is not None and bpu is not None:
            row["comparisons"]["gguf_vs_bpu"] = compare_vectors(gguf, bpu)
        if bf16 is None:
            errors.append(f"bf16_missing:{case_id}")
        if gguf is None:
            errors.append(f"gguf_missing:{case_id}")
        if bpu is None:
            errors.append(f"bpu_missing:{case_id}")
        rows.append(row)
    semantic = [r for r in rows if any(c["case_id"] == r["case_id"] and c.get("is_semantic") for c in iter_jsonl(Path(args.cases)))]
    gguf_bpu = [r["comparisons"].get("gguf_vs_bpu") for r in rows if r["comparisons"].get("gguf_vs_bpu")]
    mean_cosine = None
    if gguf_bpu:
        vals = [x.get("cosine") for x in gguf_bpu if x.get("cosine") is not None]
        mean_cosine = sum(vals) / len(vals) if vals else None
    payload = {
        "created_at": now_iso(),
        "verdict": "inconclusive_triplet_compare_bf16_missing" if any(e.startswith("bf16_missing") for e in errors) else ("ok_triplet_compare" if not errors else "blocked_triplet_compare"),
        "case_count": len(rows),
        "semantic_case_count": len(semantic),
        "gguf_vs_bpu_mean_cosine": mean_cosine,
        "errors": sorted(set(errors)),
        "cases": rows,
    }
    write_json(Path(args.output_json), payload)
    lines = [
        "# Triplet Logits Compare",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- case_count: `{len(rows)}`",
        f"- gguf_vs_bpu_mean_cosine: `{mean_cosine}`",
        "",
        "## Cases",
        "",
        "| case | bf16 | gguf | bpu | gguf_vs_bpu_cosine | gguf_top1 | bpu_top1 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        cmp = row["comparisons"].get("gguf_vs_bpu") or {}
        lines.append(
            f"| `{row['case_id']}` | {row['has_bf16']} | {row['has_gguf']} | {row['has_bpu']} | "
            f"{cmp.get('cosine')} | {cmp.get('ref_top1')} | {cmp.get('candidate_top1')} |"
        )
    lines.extend(["", "## Errors", ""])
    lines.extend(f"- `{e}`" for e in payload["errors"]) if payload["errors"] else lines.append("- none")
    write_text(Path(args.output_md), "\n".join(lines) + "\n")
    print(args.output_json)
    return 0 if payload["verdict"].startswith("ok_") else 2


if __name__ == "__main__":
    raise SystemExit(main())

