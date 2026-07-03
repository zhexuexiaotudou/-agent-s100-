#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np

from common_artifact_utils import array_stats, entropy_metrics, topk, utc_now_iso, write_json
from run_s100p_hbm_chain_dump_logits import hbm_path, model_name, quant_metadata
from hbm_runtime import HB_HBMRuntime


def make_variants(x: np.ndarray, raw: np.ndarray | None) -> list[tuple[str, np.ndarray, str]]:
    x = np.asarray(x, dtype=np.float32)
    variants: list[tuple[str, np.ndarray, str]] = [("real_x", x, "real seg26 dequant output")]
    for d in [2, 4, 8, 16, 32, 64]:
        variants.append((f"real_x_div_{d}", x / float(d), f"real seg26 dequant divided by {d}"))
    for c in [16, 8, 4, 2, 1]:
        variants.append((f"real_x_clip_{c}", np.clip(x, -float(c), float(c)), f"real seg26 dequant clipped to +/-{c}"))
    mean = float(np.mean(x))
    std = float(np.std(x)) or 1.0
    variants.append(("real_x_z_normalized", ((x - mean) / std).astype(np.float32), "z-normalized real seg26 dequant output"))
    rng = np.random.default_rng(20260701)
    variants.append(("synthetic_match_mean_std_normal", rng.normal(mean, std, size=x.shape).astype(np.float32), "synthetic normal with real mean/std"))
    variants.append(("synthetic_match_min_max_uniform", rng.uniform(float(np.min(x)), float(np.max(x)), size=x.shape).astype(np.float32), "synthetic uniform with real min/max"))
    variants.append(("synthetic_zeros", np.zeros_like(x, dtype=np.float32), "zeros control"))
    variants.append(("synthetic_ones", np.ones_like(x, dtype=np.float32), "ones control"))
    variants.append(("synthetic_ramp", (np.arange(x.size, dtype=np.float32).reshape(x.shape) % 127) / 127.0, "prior ramp control"))
    impulse = np.zeros_like(x, dtype=np.float32)
    impulse[-1, : min(128, impulse.shape[-1])] = 1.0
    variants.append(("synthetic_last_token_impulse", impulse, "last-token impulse control"))
    if raw is not None:
        variants.append(("real_raw_int16_as_input", np.asarray(raw), "raw seg26 int16 tensor fed directly if runtime accepts it"))
    return variants


def logits_stats(raw: np.ndarray, dequant: np.ndarray) -> dict[str, Any]:
    flat = dequant.reshape(-1)
    soft = entropy_metrics(flat)
    return {
        "raw_output_stats": array_stats(raw),
        "dequant_output_stats": array_stats(dequant),
        "entropy": soft["entropy"],
        "normalized_entropy": soft["normalized_entropy"],
        "top1_probability": soft["top1_probability"],
        "top20_logits": topk(flat, 20),
    }


def is_nonconstant_success(row: dict[str, Any]) -> bool:
    stats = row.get("dequant_output_stats") or {}
    return row.get("run_status") == "pass" and stats.get("constant") is False and stats.get("allzero") is False


def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    real_x = next((r for r in rows if r["variant_id"] == "real_x"), {})
    real_constant = (real_x.get("dequant_output_stats") or {}).get("constant")
    synthetic_success = [r["variant_id"] for r in rows if r["variant_id"].startswith("synthetic") and is_nonconstant_success(r)]
    recovery_order = [
        "real_x",
        "real_x_div_2",
        "real_x_div_4",
        "real_x_div_8",
        "real_x_div_16",
        "real_x_div_32",
        "real_x_div_64",
        "real_x_clip_16",
        "real_x_clip_8",
        "real_x_clip_4",
        "real_x_clip_2",
        "real_x_clip_1",
        "real_x_z_normalized",
        "real_raw_int16_as_input",
    ]
    recovery = None
    for vid in recovery_order:
        row = next((r for r in rows if r["variant_id"] == vid), None)
        if row and is_nonconstant_success(row):
            recovery = vid
            break
    if recovery and "raw_int16" in recovery:
        issue = "dtype_or_quant_contract"
    elif recovery and ("div_" in recovery or "clip_" in recovery or "z_normalized" in recovery):
        issue = "input_range_or_scale"
    elif not recovery and synthetic_success:
        issue = "layout_or_distribution_specific"
    elif not synthetic_success:
        issue = "final_segment_runtime_kernel"
    else:
        issue = "inconclusive"
    verdict = "pass" if recovery else ("inconclusive" if synthetic_success else "blocked")
    return {
        "final_segment_input_sweep_verdict": verdict,
        "real_hidden_constant_output": real_constant,
        "synthetic_controls_nonconstant": bool(synthetic_success),
        "synthetic_nonconstant_variants": synthetic_success,
        "smallest_recovery_variant": recovery,
        "likely_issue_class": issue,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final segment seg27_28 input sweep.")
    parser.add_argument("--real-seg26-dequant", required=True)
    parser.add_argument("--real-seg26-raw", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", default="last-token")
    args = parser.parse_args()
    args.layer_count = 28
    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    x = np.load(args.real_seg26_dequant)
    raw_input = np.load(args.real_seg26_raw) if args.real_seg26_raw and Path(args.real_seg26_raw).is_file() else None
    hbm = hbm_path(args, 27)
    name = model_name(args, 27)
    pos = np.arange(args.seq_len, dtype=np.int32)
    rows: list[dict[str, Any]] = []
    try:
        runtime = HB_HBMRuntime(str(hbm))
        qmeta = quant_metadata(runtime, name)
        scale = qmeta.get("scale_first")
    except Exception as exc:
        payload = {
            "schema_version": "dream7b_s100p_final_segment_input_sweep_v3",
            "created_at_utc": utc_now_iso(),
            "run_id": out_root.name,
            "final_segment_input_sweep_verdict": "blocked",
            "runtime_load_error": f"{type(exc).__name__}:{exc}",
            "variants": [],
        }
        write_json(Path(args.output_json), payload)
        Path(args.output_md).write_text(f"# Final Segment Input Sweep V3\n\n- verdict: `blocked`\n- runtime_load_error: `{payload['runtime_load_error']}`\n", encoding="utf-8")
        print(args.output_json)
        return 2

    for vid, arr, why in make_variants(x, raw_input):
        vdir = out_root / vid
        vdir.mkdir(parents=True, exist_ok=True)
        input_path = vdir / "input.npy"
        raw_out = vdir / "raw_output.npy"
        deq_out = vdir / "dequant_logits.npy"
        meta_path = vdir / "metadata.json"
        np.save(input_path, arr)
        row: dict[str, Any] = {
            "variant_id": vid,
            "why_included": why,
            "input_path": str(input_path),
            "raw_output_path": str(raw_out),
            "dequant_logits_path": str(deq_out),
            "metadata_path": str(meta_path),
            "input_stats": array_stats(arr),
            "run_status": "not_run",
            "runtime_exception": None,
        }
        try:
            output = runtime.run({"_input_0": arr, "_input_1": pos}, model_name=name)
            raw = output[name]["_output_0"]
            dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
            np.save(raw_out, raw)
            np.save(deq_out, dequant.reshape(-1))
            row.update(logits_stats(raw, dequant.reshape(-1)))
            row["run_status"] = "pass"
            row["quant_metadata"] = qmeta
        except Exception as exc:
            row["run_status"] = "fail"
            row["runtime_exception"] = f"{type(exc).__name__}:{exc}"
        write_json(meta_path, row)
        rows.append(row)

    analysis = classify(rows)
    payload = {
        "schema_version": "dream7b_s100p_final_segment_input_sweep_v3",
        "created_at_utc": utc_now_iso(),
        "run_id": out_root.name,
        "hbm_path": str(hbm),
        "model_name": name,
        "real_seg26_dequant_source": args.real_seg26_dequant,
        "real_seg26_raw_source": args.real_seg26_raw,
        **analysis,
        "variants": rows,
    }
    write_json(Path(args.output_json), payload)
    lines = [
        "# Final Segment Input Sweep V3",
        "",
        f"- verdict: `{analysis['final_segment_input_sweep_verdict']}`",
        f"- real_hidden_constant_output: `{analysis['real_hidden_constant_output']}`",
        f"- synthetic_controls_nonconstant: `{analysis['synthetic_controls_nonconstant']}`",
        f"- smallest_recovery_variant: `{analysis['smallest_recovery_variant']}`",
        f"- likely_issue_class: `{analysis['likely_issue_class']}`",
        "",
        "| variant | status | constant | allzero | nonzero | std | norm_entropy | top1 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        ds = r.get("dequant_output_stats") or {}
        top = (r.get("top20_logits") or [{}])[0].get("index")
        lines.append(
            f"| `{r['variant_id']}` | `{r['run_status']}` | {ds.get('constant')} | {ds.get('allzero')} | "
            f"{ds.get('nonzero_count')} | {ds.get('std')} | {r.get('normalized_entropy')} | {top} |"
        )
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
