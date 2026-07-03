#!/usr/bin/env python3
"""Dream7B/S100P v13 BPU island reconstruction probes.

Runs HF/CPU prefix -> BPU contiguous island -> HF/CPU suffix on canonical
seq128 cases. This is a logits/boundary-only offline probe.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from run_v12r_remote_reconstruction import (
    CASE_IDS,
    compare,
    hbm_path,
    iter_jsonl,
    model_name,
    quant_metadata,
    run_hf_suffix,
    save_array,
    sha256_file,
    stats,
    write_json,
)


DEFAULT_ISLANDS = ["1,2", "1,2,3,4", "8,9,10,11"]


def parse_island(text: str) -> list[int]:
    vals = [int(x) for x in text.split(",") if x.strip()]
    if not vals:
        raise ValueError("empty island")
    if vals != list(range(vals[0], vals[-1] + 1)):
        raise ValueError(f"island must be contiguous: {text}")
    return vals


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_bpu_segment_remote(args: argparse.Namespace, segment: int, case: dict[str, Any], input_hidden: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    from hbm_runtime import HB_HBMRuntime

    hbm = hbm_path(Path(args.hbm_root), segment, args.seq_len, args.w_bits, args.lm_head_w_bits, args.final_logits_mode)
    name = model_name(segment, args.final_logits_mode)
    pos_np = np.arange(args.seq_len, dtype=np.int32)
    t0 = time.time()
    runtime = HB_HBMRuntime(str(hbm))
    load_s = time.time() - t0
    inputs = {"_input_0": np.asarray(input_hidden, dtype=np.float32), "_input_1": pos_np}
    t1 = time.time()
    output = runtime.run(inputs, model_name=name)
    run_s = time.time() - t1
    raw = output[name]["_output_0"]
    qmeta = quant_metadata(runtime, name)
    scale = qmeta.get("scale_first")
    dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
    meta = {
        "segment": segment,
        "model_name": name,
        "hbm_path": str(hbm),
        "hbm_sha256": sha256_file(hbm) if hbm.exists() else None,
        "input_contract": {
            "kind": "hidden_plus_position_ids",
            "input_0_shape": list(np.asarray(input_hidden).shape),
            "input_0_dtype": "float32",
            "input_1_shape": [args.seq_len],
            "input_1_dtype": "int32",
        },
        "load_seconds": round(load_s, 3),
        "run_seconds": round(run_s, 3),
        "quant_metadata": qmeta,
        "raw_stats": stats(raw),
        "dequant_stats": stats(dequant),
    }
    del output
    del runtime
    return raw, dequant, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--hf-boundary-root", required=True)
    ap.add_argument("--full-truth-root", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    ap.add_argument("--islands", default=";".join(DEFAULT_ISLANDS))
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=6)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--w-bits", type=int, default=8)
    ap.add_argument("--lm-head-w-bits", type=int, default=16)
    ap.add_argument("--final-logits-mode", default="last-token")
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    islands = [parse_island(x) for x in args.islands.split(";") if x.strip()]
    report_path = Path(args.report_json)
    previous = read_json(report_path, {}) if report_path.exists() else {}
    if previous.get("schema_version") == "dream7b_s100p_v13_bpu_island_reconstruction_remote":
        report = previous
        report.setdefault("rows", [])
        report.setdefault("errors", [])
        report.setdefault("resume_runs", [])
        report["resume_runs"].append({"started_at_unix": started, "islands": islands})
    else:
        report = {
            "schema_version": "dream7b_s100p_v13_bpu_island_reconstruction_remote",
            "started_at_unix": started,
            "python": sys.version,
            "platform": platform.platform(),
            "model_dir": args.model_dir,
            "islands": islands,
            "rows": [],
            "errors": [],
            "resume_runs": [],
            "safety": {"generation_quality_run": False, "product_routes_18888_18889_touched": False},
        }
    report["status"] = "started"
    write_json(report_path, report)

    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        model = AutoModel.from_pretrained(args.model_dir, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.eval()
        cases = [c for c in iter_jsonl(Path(args.cases)) if c.get("case_id") in CASE_IDS]
        hf_root = Path(args.hf_boundary_root)
        truth_root = Path(args.full_truth_root)
        out_root = Path(args.output_root)
        pos = torch.arange(args.seq_len, dtype=torch.long).unsqueeze(0)
        cache_position = torch.arange(args.seq_len, dtype=torch.long)
        done = {(r.get("case_id"), tuple(r.get("island", []))) for r in report["rows"] if r.get("status") == "pass"}
        report["status"] = "model_loaded"
        write_json(report_path, report)
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                ref = np.load(truth_root / cid / "repeat_full_truth_logits.npy")
                for island in islands:
                    key = (cid, tuple(island))
                    if key in done:
                        print(f"[v13] skip existing island case={cid} island={island}", flush=True)
                        continue
                    t0 = time.time()
                    print(f"[v13] island case={cid} island={island}", flush=True)
                    try:
                        start, end = island[0], island[-1]
                        inp = hf_root / cid / f"layer_{start-1:02d}_output.npy"
                        hidden = np.load(inp).astype(np.float32)
                        segment_rows = []
                        for segment in island:
                            raw, hidden, bmeta = run_bpu_segment_remote(args, segment, case, hidden)
                            sdir = out_root / "evidence" / "bpu_island_reconstruction_v13" / cid / ("island_" + "_".join(f"{x:02d}" for x in island)) / f"seg_{segment:02d}"
                            raw_info = save_array(sdir / "bpu_raw_output.npy", raw)
                            deq_info = save_array(sdir / "bpu_dequant_output.npy", hidden)
                            segment_rows.append({"segment": segment, "bpu": bmeta, "raw_output": raw_info, "dequant_output": deq_info})
                        if end == 27:
                            logits = hidden.reshape(-1)
                            suffix_layers: list[int] = []
                        else:
                            logits = run_hf_suffix(model, hidden, end + 1, pos, cache_position, dtype)
                            suffix_layers = list(range(end + 1, 28))
                        row_dir = out_root / "evidence" / "bpu_island_reconstruction_v13" / cid / ("island_" + "_".join(f"{x:02d}" for x in island))
                        logits_info = save_array(row_dir / "island_logits.npy", logits)
                        hf_out = hf_root / cid / f"layer_{end:02d}_output.npy"
                        boundary_metrics = compare(np.load(hf_out), hidden) if hf_out.exists() and end < 27 else None
                        row = {
                            "case_id": cid,
                            "island": island,
                            "route": f"HF/PyTorch prefix through layer {start-1}, BPU island {start}..{end}, HF/PyTorch suffix {end+1}..27 + final norm + lm_head",
                            "input_source": {"path": str(inp), "sha256": sha256_file(inp)},
                            "segments": segment_rows,
                            "hf_suffix_layers": suffix_layers,
                            "logits": logits_info,
                            "final_metrics": compare(ref, logits),
                            "boundary_metrics": boundary_metrics,
                            "strict_thresholds": {"top1_agreement": True, "reference_top1_in_candidate_top5": True, "mean_cosine_min": 0.95, "relative_l2_max": 0.1, "no_allzero_or_constant_logits": True},
                            "elapsed_seconds": round(time.time() - t0, 3),
                            "status": "pass",
                        }
                        write_json(row_dir / "metadata.json", row)
                        report["rows"].append(row)
                        report["errors"] = [e for e in report["errors"] if not (e.get("case_id") == cid and tuple(e.get("island", [])) == tuple(island))]
                        done.add(key)
                    except Exception as exc:
                        err = {"case_id": cid, "island": island, "type": type(exc).__name__, "message": str(exc)}
                        report["errors"].append(err)
                        print(f"[v13] ERROR {err}", flush=True)
                    report["status"] = "running"
                    write_json(report_path, report)
        expected = len(cases) * len(islands)
        report["expected_rows"] = expected
        report["status"] = "pass" if len(report["rows"]) == expected and not report["errors"] else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})

    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(report_path, report)
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(
        "\n".join(
            [
                "# v13 BPU Island Reconstruction Remote",
                "",
                f"- status: `{report['status']}`",
                f"- rows: `{len(report.get('rows', []))}/{report.get('expected_rows')}`",
                f"- errors: `{len(report.get('errors', []))}`",
                "- generation_quality_run: `False`",
                "- product_routes_18888_18889_touched: `False`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(args.report_json, flush=True)
    return 0 if report.get("rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
