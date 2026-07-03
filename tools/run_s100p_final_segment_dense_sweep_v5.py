#!/usr/bin/env python3
"""Run a dense offline seg27_28 input sweep for Dream7B/S100P v5.

This script is intended to run on the S100P research host from the v3
execution directory, where `hbm_runtime` and the prior helper modules are
available. It does not start services or touch product routing.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from hbm_runtime import HB_HBMRuntime


DIVISORS = [
    1.0,
    1.125,
    1.25,
    1.375,
    1.5,
    1.75,
    2.0,
    2.25,
    2.5,
    2.75,
    3.0,
    3.25,
    3.5,
    3.75,
    4.0,
    4.25,
    4.5,
    5.0,
    6.0,
    8.0,
    12.0,
    16.0,
    32.0,
]

CLIPS = [16, 14, 12, 10, 8, 6, 5, 4.5, 4, 3.5, 3, 2, 1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def stats(x: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(x)
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    if arr.size == 0:
        return {
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "size": 0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "abs_max": None,
            "nonzero_count": 0,
            "allzero": True,
            "constant": True,
            "nan_count": 0,
            "inf_count": 0,
        }
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "size": int(arr.size),
        "min": float(np.min(finite)) if finite.size else None,
        "max": float(np.max(finite)) if finite.size else None,
        "mean": float(np.mean(finite)) if finite.size else None,
        "std": float(np.std(finite)) if finite.size else None,
        "abs_max": float(np.max(np.abs(finite))) if finite.size else None,
        "nonzero_count": int(np.count_nonzero(arr)),
        "allzero": bool(np.count_nonzero(arr) == 0),
        "constant": bool(np.all(arr == arr.flat[0])),
        "nan_count": int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
    }


def entropy_metrics(logits: np.ndarray) -> dict[str, float]:
    v = np.asarray(logits, dtype=np.float64).reshape(-1)
    v = v - np.max(v)
    e = np.exp(v)
    total = np.sum(e)
    if not np.isfinite(total) or total == 0:
        p = np.full_like(v, 1.0 / v.size)
    else:
        p = e / total
    ent = -float(np.sum(p * np.log(p + 1e-300)))
    return {
        "entropy": ent,
        "normalized_entropy": ent / math.log(v.size) if v.size > 1 else 0.0,
        "top1_probability": float(np.max(p)),
    }


def topk(logits: np.ndarray, k: int = 10) -> list[dict[str, float | int]]:
    v = np.asarray(logits).reshape(-1)
    idx = np.argsort(v)[-k:][::-1]
    return [{"token": int(i), "logit": float(v[i])} for i in idx]


def quant_metadata(runtime: HB_HBMRuntime, model_name: str) -> dict[str, Any]:
    try:
        qp = runtime.get_output_quant_params(model_name, "_output_0")
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}:{exc}"}
    scale = getattr(qp, "scale", None)
    zp = getattr(qp, "zero_point", None)
    scale_list = [float(x) for x in np.asarray(scale).reshape(-1)] if scale is not None else []
    zp_list = [float(x) for x in np.asarray(zp).reshape(-1)] if zp is not None else []
    return {
        "available": True,
        "repr": repr(qp),
        "scale": scale_list,
        "scale_first": scale_list[0] if scale_list else None,
        "zero_point": zp_list,
    }


def variant_name(prefix: str, value: float) -> str:
    text = ("%g" % value).replace(".", "p")
    return f"{prefix}_{text}"


def make_variants(x: np.ndarray) -> list[tuple[str, np.ndarray, str]]:
    x = np.asarray(x, dtype=np.float32)
    variants: list[tuple[str, np.ndarray, str]] = []
    for divisor in DIVISORS:
        name = "real_x" if divisor == 1.0 else variant_name("real_x_div", divisor)
        variants.append((name, x / np.float32(divisor), f"real seg26 hidden divided by {divisor}"))
    for clip in CLIPS:
        variants.append((variant_name("real_x_clip", clip), np.clip(x, -clip, clip), f"real seg26 hidden clipped to +/-{clip}"))
    mean = float(np.mean(x))
    std = float(np.std(x)) or 1.0
    variants.append(("real_x_z_normalized", ((x - mean) / std).astype(np.float32), "z-normalized real seg26 hidden"))
    variants.append(("real_x_mean_centered", (x - mean).astype(np.float32), "mean-centered real seg26 hidden"))
    return variants


def run_variant(
    runtime: HB_HBMRuntime,
    model_name: str,
    scale: float | None,
    pos: np.ndarray,
    out_root: Path,
    name: str,
    arr: np.ndarray,
    why: str,
) -> dict[str, Any]:
    vdir = out_root / name
    vdir.mkdir(parents=True, exist_ok=True)
    input_path = vdir / "input.npy"
    raw_path = vdir / "raw_output.npy"
    dequant_path = vdir / "dequant_logits.npy"
    meta_path = vdir / "metadata.json"
    np.save(input_path, arr)
    row: dict[str, Any] = {
        "variant_id": name,
        "why_included": why,
        "input_path": str(input_path),
        "raw_output_path": str(raw_path),
        "dequant_logits_path": str(dequant_path),
        "metadata_path": str(meta_path),
        "input_stats": stats(arr),
        "run_status": "not_run",
        "runtime_exception": None,
    }
    try:
        output = runtime.run({"_input_0": arr, "_input_1": pos}, model_name=model_name)
        raw = output[model_name]["_output_0"]
        dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
        dequant = dequant.reshape(-1)
        np.save(raw_path, raw)
        np.save(dequant_path, dequant)
        row.update(
            {
                "run_status": "pass",
                "raw_output_stats": stats(raw),
                "dequant_output_stats": stats(dequant),
                "softmax": entropy_metrics(dequant),
                "top10_logits": topk(dequant, 10),
            }
        )
    except Exception as exc:
        row["run_status"] = "fail"
        row["runtime_exception"] = f"{type(exc).__name__}:{exc}"
    write_json(meta_path, row)
    return row


def is_nonzero(row: dict[str, Any]) -> bool:
    ds = row.get("dequant_output_stats") or {}
    return row.get("run_status") == "pass" and ds.get("allzero") is False and ds.get("constant") is False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real-seg26-dequant", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--output-json", required=True)
    ap.add_argument("--output-md", required=True)
    ap.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    ap.add_argument("--seq-len", type=int, default=128)
    args = ap.parse_args()

    hbm_path = Path(args.hbm_root) / "seg27_28" / "dream7b_segment_27_28_seq128_q8_lmheadq16_last_token_logits.hbm"
    model_name = "dream_segment_27_28_last_token_logits"
    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    x = np.load(args.real_seg26_dequant)
    runtime = HB_HBMRuntime(str(hbm_path))
    qmeta = quant_metadata(runtime, model_name)
    scale = qmeta.get("scale_first")
    pos = np.arange(args.seq_len, dtype=np.int32)
    rows = [run_variant(runtime, model_name, scale, pos, out_root, name, arr, why) for name, arr, why in make_variants(x)]

    divisor_rows = [r for r in rows if r["variant_id"] == "real_x" or r["variant_id"].startswith("real_x_div_")]
    clip_rows = [r for r in rows if r["variant_id"].startswith("real_x_clip_")]
    first_nonzero_divisor = next((r["variant_id"] for r in divisor_rows if is_nonzero(r)), None)
    first_nonzero_clip = next((r["variant_id"] for r in clip_rows if is_nonzero(r)), None)
    payload = {
        "schema_version": "dream7b_s100p_final_segment_dense_sweep_v5",
        "created_at_utc": utc_now(),
        "hbm_path": str(hbm_path),
        "model_name": model_name,
        "real_seg26_dequant_source": args.real_seg26_dequant,
        "quant_metadata": qmeta,
        "summary": {
            "first_nonzero_divisor_variant": first_nonzero_divisor,
            "first_nonzero_clip_variant": first_nonzero_clip,
            "nonzero_recovery_is_correctness": False,
            "reference_compare_status": "blocked_reference_logits_unavailable_in_this_sweep",
            "contract_hypothesis": "seg26 dequant/input magnitude is above seg27_28 accepted float input range; /4 or tighter clipping restores nonzero diagnostic output only.",
        },
        "variants": rows,
    }
    write_json(Path(args.output_json), payload)

    lines = [
        "# Final Segment Dense Sweep v5",
        "",
        f"- first_nonzero_divisor_variant: `{first_nonzero_divisor}`",
        f"- first_nonzero_clip_variant: `{first_nonzero_clip}`",
        "- nonzero_recovery_is_correctness: `False`",
        "",
        "| variant | status | input_abs_max | out_allzero | out_nonzero | out_std | norm_entropy |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        ins = row.get("input_stats") or {}
        ds = row.get("dequant_output_stats") or {}
        soft = row.get("softmax") or {}
        lines.append(
            f"| `{row['variant_id']}` | `{row['run_status']}` | {ins.get('abs_max')} | "
            f"{ds.get('allzero')} | {ds.get('nonzero_count')} | {ds.get('std')} | {soft.get('normalized_entropy')} |"
        )
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
