#!/usr/bin/env python3
"""Dream7B/S100P v14 early BPU island diagnostic calibration.

This is diagnostic only. Per-channel affine fits are explicitly marked as
non-deployable. No generation and no product route interaction.
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

from run_v12r_remote_reconstruction import CASE_IDS, compare, iter_jsonl, save_array, sha256_file, stats, write_json


ISLANDS = [[1], [2], [1, 2], [1, 2, 3, 4]]


def island_name(island: list[int]) -> str:
    return "island_" + "_".join(f"{x:02d}" for x in island)


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def run_hf_suffix_batch(model: Any, hidden_batch: np.ndarray, start_layer: int, pos: Any, cache_position: Any, dtype: Any) -> np.ndarray:
    import torch

    hidden = torch.tensor(np.asarray(hidden_batch, dtype=np.float32).tolist(), dtype=dtype)
    position_embeddings = model.model.rotary_emb(hidden, pos)
    for layer_idx in range(start_layer, 28):
        hidden = model.model.layers[layer_idx](
            hidden,
            attention_mask=None,
            position_ids=pos,
            past_key_value=None,
            output_attentions=False,
            use_cache=False,
            cache_position=cache_position,
            position_embeddings=position_embeddings,
        )[0]
    normed = model.model.norm(hidden)
    logits_t = model.lm_head(normed[:, -1:, :])[:, -1, :]
    return tensor_to_numpy(logits_t)


def correction_variants(bpu: np.ndarray, hf: np.ndarray) -> list[dict[str, Any]]:
    eps = 1e-6
    rows = []
    b = bpu.astype(np.float32)
    h = hf.astype(np.float32)
    rows.append({"name": "no_correction_baseline", "kind": "baseline", "deployable": True, "boundary": b})
    rows.append({"name": "global_mean_std_rescale_to_hf", "kind": "known_scale_like_diagnostic", "deployable": False, "boundary": ((b - b.mean()) / max(float(b.std()), eps) * float(h.std()) + float(h.mean())).astype(np.float32)})
    bt_mean = b.mean(axis=1, keepdims=True)
    bt_std = b.std(axis=1, keepdims=True)
    ht_mean = h.mean(axis=1, keepdims=True)
    ht_std = h.std(axis=1, keepdims=True)
    rows.append({"name": "per_token_mean_std_rescale_to_hf", "kind": "diagnostic_fit", "deployable": False, "boundary": ((b - bt_mean) / np.maximum(bt_std, eps) * ht_std + ht_mean).astype(np.float32)})
    bx = b - b.mean(axis=0, keepdims=True)
    hx = h - h.mean(axis=0, keepdims=True)
    denom = np.sum(bx * bx, axis=0, keepdims=True)
    slope = np.sum(bx * hx, axis=0, keepdims=True) / np.maximum(denom, eps)
    intercept = h.mean(axis=0, keepdims=True) - slope * b.mean(axis=0, keepdims=True)
    rows.append({"name": "per_channel_affine_fit_diagnostic", "kind": "diagnostic_fit", "deployable": False, "boundary": (b * slope + intercept).astype(np.float32), "fit_stats": {"slope_mean": float(np.mean(slope)), "slope_std": float(np.std(slope)), "intercept_mean": float(np.mean(intercept)), "intercept_std": float(np.std(intercept))}})
    lo, hi = np.percentile(h, [1, 99])
    rows.append({"name": "clip_to_hf_p01_p99", "kind": "diagnostic_clip", "deployable": False, "boundary": np.clip(b, lo, hi).astype(np.float32), "clip_range": [float(lo), float(hi)]})
    return rows


def load_bpu_boundary(args: argparse.Namespace, cid: str, island: list[int]) -> tuple[Path, np.ndarray]:
    end = island[-1]
    if len(island) == 1:
        p = Path(args.v12r_root) / "evidence" / "single_segment_substitution_v12r" / cid / f"seg_{end:02d}" / "bpu_dequant_output.npy"
    else:
        p = Path(args.v13_root) / "evidence" / "bpu_island_reconstruction_v13" / cid / island_name(island) / f"seg_{end:02d}" / "bpu_dequant_output.npy"
    return p, np.load(p).astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--hf-boundary-root", required=True)
    ap.add_argument("--full-truth-root", required=True)
    ap.add_argument("--v12r-root", default="/mnt/nas/openclaw/reports/models/dream7b_s100p_v12r_execution_20260702")
    ap.add_argument("--v13-root", default="/mnt/nas/openclaw/reports/models/dream7b_s100p_v13_execution_20260703")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=6)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v14_bpu_island_diagnostic_calibration",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "rows": [],
        "errors": [],
        "islands": ISLANDS,
        "safety": {"generation_quality_run": False, "product_routes_18888_18889_touched": False, "dream7b_frontend_openclaw_traffic_touched": False},
    }
    write_json(Path(args.report_json), report)
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
        report["status"] = "model_loaded"
        write_json(Path(args.report_json), report)
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                ref = np.load(truth_root / cid / "repeat_full_truth_logits.npy")
                for island in ISLANDS:
                    t0 = time.time()
                    start, end = island[0], island[-1]
                    print(f"[v14] calibration case={cid} island={island}", flush=True)
                    try:
                        bpu_path, bpu = load_bpu_boundary(args, cid, island)
                        hf_path = hf_root / cid / f"layer_{end:02d}_output.npy"
                        hf = np.load(hf_path).astype(np.float32)
                        variants = correction_variants(bpu, hf)
                        batch = np.stack([v["boundary"] for v in variants], axis=0)
                        logits_batch = run_hf_suffix_batch(model, batch, end + 1, pos, cache_position, dtype)
                        row_dir = out_root / "evidence" / "bpu_island_diagnostic_calibration_v14" / cid / island_name(island)
                        island_rows = []
                        for idx, variant in enumerate(variants):
                            vdir = row_dir / variant["name"]
                            boundary_info = save_array(vdir / "corrected_boundary.npy", variant["boundary"])
                            logits_info = save_array(vdir / "suffix_logits.npy", logits_batch[idx])
                            bmetrics = compare(hf, variant["boundary"])
                            fmetrics = compare(ref, logits_batch[idx])
                            row = {
                                "case_id": cid,
                                "island": island,
                                "variant": variant["name"],
                                "kind": variant["kind"],
                                "deployable": variant["deployable"],
                                "bpu_boundary_source": {"path": str(bpu_path), "sha256": sha256_file(bpu_path)},
                                "hf_boundary_source": {"path": str(hf_path), "sha256": sha256_file(hf_path)},
                                "boundary": boundary_info,
                                "logits": logits_info,
                                "boundary_metrics": bmetrics,
                                "final_metrics": fmetrics,
                                "fit_stats": variant.get("fit_stats"),
                                "clip_range": variant.get("clip_range"),
                            }
                            island_rows.append(row)
                            report["rows"].append(row)
                        write_json(row_dir / "metadata.json", {"case_id": cid, "island": island, "rows": island_rows, "elapsed_seconds": round(time.time() - t0, 3)})
                    except Exception as exc:
                        err = {"case_id": cid, "island": island, "type": type(exc).__name__, "message": str(exc)}
                        report["errors"].append(err)
                        print(f"[v14] ERROR {err}", flush=True)
                    report["status"] = "running"
                    write_json(Path(args.report_json), report)
        expected = len(cases) * len(ISLANDS) * 5
        report["expected_rows"] = expected
        report["status"] = "pass" if len(report["rows"]) == expected and not report["errors"] else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(Path(args.report_json), report)
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(
        "\n".join([
            "# v14 BPU Island Diagnostic Calibration Remote",
            "",
            f"- status: `{report.get('status')}`",
            f"- rows: `{len(report.get('rows', []))}/{report.get('expected_rows')}`",
            f"- errors: `{len(report.get('errors', []))}`",
            "- generation_quality_run: `False`",
            "- product_routes_18888_18889_touched: `False`",
        ]) + "\n",
        encoding="utf-8",
    )
    print(args.report_json, flush=True)
    return 0 if report.get("rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
