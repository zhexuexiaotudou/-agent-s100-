#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import time
from pathlib import Path

import numpy as np

from dream7b_research_common import iter_jsonl, now_iso, tensor_stats, write_json, write_text
from run_s100p_hbm_chain_dump_logits import hbm_path, model_name, quant_metadata
from hbm_runtime import HB_HBMRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump S100P seq128 segment boundary tensors.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--layer-count", type=int, default=28)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", default="last-token")
    args = parser.parse_args()
    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    errors = []
    for case in iter_jsonl(Path(args.cases)):
        case_dir = out_root / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        hidden = None
        pos = np.arange(args.seq_len, dtype=np.int32)
        seg_rows = []
        try:
            for index in range(args.layer_count):
                path = hbm_path(args, index)
                name = model_name(args, index)
                load_start = time.perf_counter()
                runtime = HB_HBMRuntime(str(path))
                load_ms = (time.perf_counter() - load_start) * 1000
                inputs = {"_input_0": np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len), "_input_1": pos} if index == 0 else {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": pos}
                run_start = time.perf_counter()
                output = runtime.run(inputs, model_name=name)
                run_ms = (time.perf_counter() - run_start) * 1000
                raw = output[name]["_output_0"]
                qmeta = quant_metadata(runtime, name)
                scale = qmeta.get("scale_first")
                dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
                raw_path = case_dir / f"seg_{index:02d}_raw_output.npy"
                deq_path = case_dir / f"seg_{index:02d}_output.npy"
                np.save(raw_path, raw)
                np.save(deq_path, dequant)
                seg_rows.append(
                    {
                        "segment": index,
                        "model_name": name,
                        "raw_output": str(raw_path),
                        "dequant_output": str(deq_path),
                        "raw_stats": tensor_stats(raw),
                        "dequant_stats": tensor_stats(dequant),
                        "quant_metadata": qmeta,
                        "load_ms": round(load_ms, 3),
                        "run_ms": round(run_ms, 3),
                    }
                )
                if index != args.layer_count - 1:
                    hidden = dequant.copy()
                del output
                del runtime
                gc.collect()
            rows.append({"case_id": case["case_id"], "case_dir": str(case_dir), "segments": seg_rows})
        except Exception as exc:
            errors.append(f"{case['case_id']}:{type(exc).__name__}:{exc}")
            break
    payload = {"created_at": now_iso(), "verdict": "ok_s100p_boundary_dump" if not errors else "failed_s100p_boundary_dump", "case_count": len(rows), "errors": errors, "cases": rows}
    write_json(Path(args.report_json), payload)
    write_text(Path(args.report_md), "# S100P Boundary Dump\n\n" + f"- verdict: `{payload['verdict']}`\n- case_count: `{len(rows)}`\n- errors: `{';'.join(errors) if errors else 'none'}`\n")
    print(args.report_json)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

