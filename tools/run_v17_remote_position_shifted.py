#!/usr/bin/env python3
"""Add v17 shifted-position seg00_01 probes.

Offline single-segment HBM runtime only. No generation, no product routes.
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


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def stats(x: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(x)
    if arr.size == 0:
        return {"shape": list(arr.shape), "dtype": str(arr.dtype), "size": 0}
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "size": int(arr.size),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "abs_max": float(np.max(np.abs(finite))),
        "nonzero_count": int(np.count_nonzero(arr)),
        "allzero": bool(np.count_nonzero(arr) == 0),
        "constant": bool(arr.size > 0 and np.all(arr == arr.flat[0])),
    }


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "sha256": sha256_file(path), "stats": stats(arr)}


def quant_metadata(runtime: Any, model_name: str) -> dict[str, Any]:
    try:
        qp = runtime.output_quants[model_name]["_output_0"]
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken/seg00_01/dream7b_segment_0_1_seq128_q8.hbm")
    ap.add_argument("--model-name", default="dream_segment_00_01")
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--output-scale", type=float, default=6.062494503566995e-05)
    args = ap.parse_args()

    from hbm_runtime import HB_HBMRuntime

    started = time.time()
    root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v17_position_shifted",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "rows": [],
        "errors": [],
        "skipped": [
            {
                "variant": "constant_128_positions",
                "reason": "out-of-range position id may be unsafe for HBM runtime; skipped by design",
            },
            {
                "variant": "constant_255_positions",
                "reason": "out-of-range position id may be unsafe for HBM runtime; skipped by design",
            },
        ],
        "safety": dict(SAFETY),
        "status": "started",
    }
    write_json(root / "position_shifted_report.json", report)
    try:
        runtime = HB_HBMRuntime(str(Path(args.hbm)))
        qmeta = quant_metadata(runtime, args.model_name)
        scale = float(qmeta.get("scale_first") or args.output_scale)
        variants = {
            "shifted_plus_2_positions": np.arange(args.seq_len, dtype=np.int32) + 2,
            "shifted_plus_16_positions": np.arange(args.seq_len, dtype=np.int32) + 16,
        }
        cases = [c for c in read_jsonl(Path(args.cases)) if c.get("case_id") in CASE_IDS]
        for case in cases:
            cid = case["case_id"]
            token_ids = np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len)
            zero_path = Path(args.output_root) / cid / "position_variants" / "all_zero_positions" / "dequant_output.npy"
            zero = np.load(zero_path).astype(np.float32) if zero_path.exists() else None
            for name, positions in variants.items():
                vdir = root / cid / "position_variants" / name
                out = runtime.run({"_input_0": token_ids, "_input_1": positions}, model_name=args.model_name)
                raw = out[args.model_name]["_output_0"]
                deq = raw.astype(np.float32) * scale
                row = {
                    "case_id": cid,
                    "variant": name,
                    "positions": save_array(vdir / "positions.npy", positions),
                    "raw_output": save_array(vdir / "raw_output.npy", raw),
                    "dequant_output": save_array(vdir / "dequant_output.npy", deq),
                }
                if zero is not None:
                    delta = deq - zero
                    row["delta_vs_all_zero_positions"] = save_array(vdir / "delta_vs_all_zero_positions.npy", delta)
                    row["delta_abs_max"] = float(np.max(np.abs(delta)))
                    row["delta_norm"] = float(np.linalg.norm(delta.reshape(-1)))
                report["rows"].append(row)
                write_json(vdir / "metadata.json", row)
                write_json(root / "position_shifted_report.json", report)
        report["status"] = "pass"
        report["quant_metadata"] = qmeta
        del runtime
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(root / "position_shifted_report.json", report)
    (root / "position_shifted_report.md").write_text(
        "# v17 Shifted Position Probe\n\n"
        f"- status: `{report.get('status')}`\n"
        f"- rows: `{len(report.get('rows', []))}`\n"
        f"- skipped: `{len(report.get('skipped', []))}`\n"
        "- generation_quality_run: `False`\n"
        "- product_routes_18888_18889_touched: `False`\n",
        encoding="utf-8",
    )
    print(root / "position_shifted_report.json", flush=True)
    return 0 if report.get("rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
