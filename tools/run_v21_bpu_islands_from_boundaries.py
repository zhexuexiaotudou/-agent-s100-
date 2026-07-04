#!/usr/bin/env python3
"""Run Dream7B S100P BPU islands [1], [2], [1,2] from HF boundary tensors.

This is an offline logits-evidence helper. It only runs HBM segments and never
touches generation, product routes, OpenClaw foreground traffic, or ports
18888/18889.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}
ISLANDS = [[1], [2], [1, 2]]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def stats(arr: np.ndarray) -> dict[str, Any]:
    x = np.asarray(arr)
    y = x.reshape(-1)
    return {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "size": int(x.size),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "abs_max": float(np.max(np.abs(y))),
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.all(y == 0)),
        "constant": bool(np.all(y == y.flat[0])),
        "nan_count": int(np.isnan(y.astype(np.float64, copy=False)).sum()),
        "inf_count": int(np.isinf(y.astype(np.float64, copy=False)).sum()),
    }


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "stats": stats(arr)}


def hbm_path(root: Path, index: int, seq_len: int, w_bits: int, lm_head_w_bits: int, final_logits_mode: str) -> Path:
    end = index + 1
    suffix = "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""
    lm = f"_lmheadq{lm_head_w_bits}" if index == 27 and lm_head_w_bits != w_bits else ""
    return root / f"seg{index:02d}_{end:02d}" / f"dream7b_segment_{index}_{end}_seq{seq_len}_q{w_bits}{lm}{suffix}.hbm"


def model_name(index: int, final_logits_mode: str) -> str:
    suffix = "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""
    return f"dream_segment_{index:02d}_{index+1:02d}{suffix}"


def quant_metadata(runtime: Any, name: str) -> dict[str, Any]:
    try:
        qp = runtime.output_quants[name]["_output_0"]
        scale = np.asarray(getattr(qp, "scale", [])).reshape(-1)
        zero = getattr(qp, "zero_point", None)
        return {
            "available": True,
            "scale": scale.astype(float).tolist(),
            "scale_first": float(scale[0]) if scale.size else None,
            "zero_point": np.asarray(zero).reshape(-1).astype(float).tolist() if zero is not None else None,
            "repr": repr(qp),
        }
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}:{exc}"}


def run_segment(args: argparse.Namespace, segment: int, hidden: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    from hbm_runtime import HB_HBMRuntime

    hbm = hbm_path(Path(args.hbm_root), segment, args.seq_len, args.w_bits, args.lm_head_w_bits, args.final_logits_mode)
    name = model_name(segment, args.final_logits_mode)
    runtime = HB_HBMRuntime(str(hbm))
    pos_np = np.arange(args.seq_len, dtype=np.int32)
    t0 = time.time()
    output = runtime.run({"_input_0": np.asarray(hidden, dtype=np.float32), "_input_1": pos_np}, model_name=name)
    run_s = time.time() - t0
    raw = output[name]["_output_0"]
    qmeta = quant_metadata(runtime, name)
    scale = qmeta.get("scale_first")
    dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
    meta = {
        "segment": segment,
        "model_name": name,
        "hbm_path": str(hbm),
        "hbm_sha256": sha256_file(hbm) if hbm.exists() else None,
        "run_seconds": round(run_s, 6),
        "quant_metadata": qmeta,
        "input_stats": stats(np.asarray(hidden, dtype=np.float32)),
        "raw_stats": stats(raw),
        "dequant_stats": stats(dequant),
    }
    del output
    del runtime
    return raw, dequant, meta


def island_name(island: list[int]) -> str:
    return "island_" + "_".join(str(x) for x in island)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--w-bits", type=int, default=8)
    ap.add_argument("--lm-head-w-bits", type=int, default=16)
    ap.add_argument("--final-logits-mode", default="last-token")
    args = ap.parse_args()

    started = time.time()
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v21_bpu_islands_from_boundaries",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": dict(SAFETY),
        "case_rows": [],
        "island_rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(output_root / "bpu_island_segments_report.json", report)
    try:
        case_dirs = sorted([p for p in input_root.iterdir() if p.is_dir()])
        for case_dir in case_dirs:
            cid = case_dir.name
            case_row = {"case_id": cid, "available_boundaries": sorted(p.name for p in case_dir.glob("layer_*_output.npy"))}
            report["case_rows"].append(case_row)
            write_json(output_root / "bpu_island_segments_report.json", report)
            for island in ISLANDS:
                start = island[0]
                input_boundary = case_dir / f"layer_{start-1:02d}_output.npy"
                if not input_boundary.exists():
                    report["errors"].append({"case_id": cid, "island": island, "type": "MissingBoundary", "message": str(input_boundary)})
                    continue
                hidden = np.load(input_boundary).astype(np.float32)
                segment_rows = []
                row_dir = output_root / cid / island_name(island)
                for segment in island:
                    raw, hidden, meta = run_segment(args, segment, hidden)
                    sdir = row_dir / f"seg_{segment:02d}"
                    segment_rows.append(
                        {
                            "segment": segment,
                            "bpu": meta,
                            "raw_output": save_array(sdir / "bpu_raw_output.npy", raw),
                            "dequant_output": save_array(sdir / "bpu_dequant_output.npy", hidden),
                        }
                    )
                final = save_array(row_dir / "island_final_hidden.npy", hidden)
                row = {
                    "case_id": cid,
                    "island": island,
                    "input_boundary": str(input_boundary),
                    "segments": segment_rows,
                    "final_hidden": final,
                    "status": "pass",
                }
                write_json(row_dir / "metadata.json", row)
                report["island_rows"].append(row)
                report["status"] = "running"
                write_json(output_root / "bpu_island_segments_report.json", report)
        report["status"] = "pass" if report["island_rows"] else "fail"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 6)
    write_json(output_root / "bpu_island_segments_report.json", report)
    print(output_root / "bpu_island_segments_report.json", flush=True)
    return 0 if report["island_rows"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
