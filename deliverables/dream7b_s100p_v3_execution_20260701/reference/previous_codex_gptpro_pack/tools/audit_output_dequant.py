#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dream7b_research_common import compare_vectors, iter_jsonl, now_iso, softmax_stats, tensor_stats, topk, write_json, write_text


def variants(raw: np.ndarray, scale: float | None, zero_point: float | None) -> dict[str, np.ndarray]:
    raw_i = raw.reshape(-1)
    out = {"identity_float": raw_i.astype(np.float32)}
    if scale is not None:
        out["scale_x"] = raw_i.astype(np.float32) * float(scale)
        zp = float(zero_point or 0.0)
        out["scale_x_minus_zero_point"] = (raw_i.astype(np.float32) - zp) * float(scale)
    if raw_i.dtype == np.int16:
        out["uint16_reinterpret"] = raw_i.view(np.uint16).astype(np.float32) * float(scale or 1.0)
        out["byteswap_int16"] = raw_i.byteswap().astype(np.float32) * float(scale or 1.0)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit BPU raw-output to float-logits dequantization variants.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--bpu-root", required=True)
    parser.add_argument("--gguf-root", default="")
    parser.add_argument("--bf16-root", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    rows = []
    errors = []
    for case in iter_jsonl(Path(args.cases)):
        case_id = case["case_id"]
        case_dir = Path(args.bpu_root) / case_id
        raw_path = case_dir / "raw_output.npy"
        meta_path = case_dir / "tensor_metadata.json"
        if not raw_path.is_file() or not meta_path.is_file():
            errors.append(f"bpu_raw_or_metadata_missing:{case_id}")
            continue
        raw = np.load(raw_path)
        import json

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        q = meta["final_segment"]["quant_metadata"]
        scale = q.get("scale_first")
        zero = (q.get("zero_point") or [None])[0] if isinstance(q.get("zero_point"), list) else q.get("zero_point")
        ref = None
        ref_type = None
        gguf = Path(args.gguf_root) / case_id / "gguf_last_logits.npy" if args.gguf_root else None
        bf16 = Path(args.bf16_root) / case_id / "bf16_last_logits.npy" if args.bf16_root else None
        if bf16 and bf16.is_file():
            ref = np.load(bf16)
            ref_type = "bf16"
        elif gguf and gguf.is_file():
            ref = np.load(gguf)
            ref_type = "gguf_q4km"
        variant_rows = []
        best = None
        for name, arr in variants(raw, scale, zero).items():
            row = {"variant": name, "stats": tensor_stats(arr), "softmax": softmax_stats(arr), "top5": topk(arr, 5)}
            if ref is not None:
                row["compare_to_reference"] = compare_vectors(ref, arr)
            variant_rows.append(row)
            cos = ((row.get("compare_to_reference") or {}).get("cosine") if ref is not None else None)
            if cos is not None and (best is None or cos > best.get("cosine", -999)):
                best = {"variant": name, "cosine": cos}
        official = next((v for v in variant_rows if v["variant"] == "scale_x"), variant_rows[0] if variant_rows else None)
        rows.append(
            {
                "case_id": case_id,
                "reference_type": ref_type,
                "raw_stats": tensor_stats(raw),
                "scale": scale,
                "zero_point": zero,
                "official_variant": "scale_x" if scale is not None else "identity_float",
                "official_entropy": (official or {}).get("softmax", {}).get("normalized_entropy"),
                "best_variant": best,
                "variants": variant_rows,
            }
        )
    raw_constant_cases = [row["case_id"] for row in rows if row["raw_stats"]["constant"]]
    verdict = "upstream_graph_or_runtime_issue_raw_constant" if raw_constant_cases else "dequant_audit_no_raw_constant"
    payload = {"created_at": now_iso(), "verdict": verdict, "case_count": len(rows), "raw_constant_cases": raw_constant_cases, "errors": errors, "cases": rows}
    write_json(Path(args.output_json), payload)
    lines = ["# Dequant Audit", "", f"- verdict: `{verdict}`", f"- raw_constant_cases: `{raw_constant_cases}`", "", "| case | scale | raw_constant | official_entropy | best_variant |", "| --- | ---: | --- | ---: | --- |"]
    for row in rows:
        lines.append(f"| `{row['case_id']}` | {row['scale']} | {row['raw_stats']['constant']} | {row['official_entropy']} | `{row['best_variant']}` |")
    write_text(Path(args.output_md), "\n".join(lines) + "\n")
    print(args.output_json)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

