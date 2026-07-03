#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dream7b_research_common import now_iso, softmax_stats, tensor_stats, topk, write_json, write_text
from run_s100p_hbm_chain_dump_logits import hbm_path, model_name, quant_metadata
from hbm_runtime import HB_HBMRuntime


def synthetic_hidden(kind: str, seq_len: int, hidden_size: int) -> np.ndarray:
    if kind == "zeros":
        return np.zeros((seq_len, hidden_size), dtype=np.float32)
    if kind == "ones":
        return np.ones((seq_len, hidden_size), dtype=np.float32)
    if kind == "ramp":
        return (np.arange(seq_len * hidden_size, dtype=np.float32).reshape(seq_len, hidden_size) % 127) / 127.0
    if kind == "last_token_impulse":
        arr = np.zeros((seq_len, hidden_size), dtype=np.float32)
        arr[-1, : min(128, hidden_size)] = 1.0
        return arr
    raise ValueError(kind)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final segment seg27_28 in isolation.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--seg26-output", default="")
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", default="last-token")
    args = parser.parse_args()
    args.layer_count = 28
    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    hbm = hbm_path(args, 27)
    name = model_name(args, 27)
    try:
        runtime = HB_HBMRuntime(str(hbm))
    except Exception as exc:  # pragma: no cover - depends on S100P runtime state.
        payload = {
            "created_at": now_iso(),
            "verdict": "blocked_final_segment_load_error",
            "hbm_path": str(hbm),
            "model_name": name,
            "runtime_load_error": repr(exc),
            "top1_changes_with_input": False,
            "cases": [],
        }
        write_json(Path(args.report_json), payload)
        write_text(
            Path(args.report_md),
            "# Final Segment Isolated Audit\n\n"
            f"- verdict: `{payload['verdict']}`\n"
            f"- runtime_load_error: `{payload['runtime_load_error']}`\n",
        )
        print(args.report_json)
        return 2
    pos = np.arange(args.seq_len, dtype=np.int32)
    inputs = []
    for kind in ["zeros", "ones", "ramp", "last_token_impulse"]:
        inputs.append((kind, synthetic_hidden(kind, args.seq_len, args.hidden_size)))
    if args.seg26_output and Path(args.seg26_output).is_file():
        inputs.append(("real_bpu_seg26_output", np.load(args.seg26_output).astype(np.float32)))
    rows = []
    for kind, hidden in inputs:
        case_dir = out_root / kind
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            output = runtime.run({"_input_0": hidden.astype(np.float32, copy=False), "_input_1": pos}, model_name=name)
        except Exception as exc:  # pragma: no cover - depends on S100P runtime state.
            rows.append(
                {
                    "input_kind": kind,
                    "hidden_stats": tensor_stats(hidden),
                    "runtime_error": repr(exc),
                }
            )
            continue
        raw = output[name]["_output_0"]
        qmeta = quant_metadata(runtime, name)
        scale = qmeta.get("scale_first")
        dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
        np.save(case_dir / "raw_logits.npy", raw)
        np.save(case_dir / "dequant_logits.npy", dequant.reshape(-1))
        rows.append(
            {
                "input_kind": kind,
                "hidden_stats": tensor_stats(hidden),
                "raw_stats": tensor_stats(raw),
                "dequant_stats": tensor_stats(dequant),
                "softmax": softmax_stats(dequant.reshape(-1)),
                "top5": topk(dequant.reshape(-1), 5),
                "quant_metadata": qmeta,
                "raw_logits": str(case_dir / "raw_logits.npy"),
                "dequant_logits": str(case_dir / "dequant_logits.npy"),
            }
        )
    top1s = [row["top5"][0]["token"] if row.get("top5") else None for row in rows if "top5" in row]
    raw_constant = [row["raw_stats"]["constant"] for row in rows if "raw_stats" in row]
    run_errors = [row for row in rows if "runtime_error" in row]
    payload = {
        "created_at": now_iso(),
        "verdict": (
            "blocked_final_segment_run_error"
            if run_errors
            else ("blocked_final_segment_constant_or_uniform" if any(raw_constant) else "ok_final_segment_nonconstant")
        ),
        "top1_changes_with_input": len(set(top1s)) > 1,
        "cases": rows,
    }
    write_json(Path(args.report_json), payload)
    lines = ["# Final Segment Isolated Audit", "", f"- verdict: `{payload['verdict']}`", f"- top1_changes_with_input: `{payload['top1_changes_with_input']}`", "", "| input | raw_constant | entropy | top1 |", "| --- | --- | ---: | ---: |"]
    for row in rows:
        if "runtime_error" in row:
            lines.append(f"| `{row['input_kind']}` | runtime_error |  |  |")
            continue
        lines.append(f"| `{row['input_kind']}` | {row['raw_stats']['constant']} | {row['softmax']['normalized_entropy']:.6f} | {row['top5'][0]['token'] if row['top5'] else None} |")
    write_text(Path(args.report_md), "\n".join(lines) + "\n")
    print(args.report_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
