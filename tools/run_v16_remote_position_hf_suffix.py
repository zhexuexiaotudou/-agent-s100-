#!/usr/bin/env python3
"""Dream7B/S100P v16 neutralized-position seg00 -> HF suffix logits test."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
VARIANTS = ["canonical_0_to_127", "all_zero_positions", "all_one_positions", "one_indexed_1_to_128"]
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


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "sha256": sha256_file(path), "stats": stats(arr)}


def stats(x: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(x)
    if arr.size == 0:
        return {"shape": list(arr.shape), "dtype": str(arr.dtype), "size": 0}
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
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
        "constant": bool(arr.size > 0 and np.all(arr == arr.flat[0])),
        "nan_count": int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
    }


def entropy(logits: np.ndarray) -> dict[str, float]:
    v = np.asarray(logits, dtype=np.float64).reshape(-1)
    v = v - np.max(v)
    e = np.exp(v)
    p = e / max(float(np.sum(e)), 1e-300)
    ent = -float(np.sum(p * np.log(p + 1e-300)))
    return {"entropy": ent, "normalized_entropy": ent / math.log(p.size), "top1_probability": float(np.max(p))}


def compare(ref: np.ndarray, cand: np.ndarray, topk: int = 5) -> dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {"shape_match": False, "reference_shape": list(r.shape), "candidate_shape": list(c.shape)}
    rt = np.argsort(r)[-topk:][::-1].astype(int)
    ct = np.argsort(c)[-topk:][::-1].astype(int)
    r0 = r - r.mean()
    c0 = c - c.mean()
    rn = np.linalg.norm(r)
    cn = np.linalg.norm(c)
    r0n = np.linalg.norm(r0)
    c0n = np.linalg.norm(c0)
    out = {
        "shape_match": True,
        "reference_top1": int(rt[0]),
        "candidate_top1": int(ct[0]),
        "top1_agreement": bool(rt[0] == ct[0]),
        "reference_top1_in_candidate_top5": bool(rt[0] in ct),
        "top5_overlap": int(len(set(rt.tolist()) & set(ct.tolist()))),
        "cosine": float(np.dot(r, c) / (rn * cn)) if rn and cn else None,
        "pearson_centered": float(np.dot(r0, c0) / (r0n * c0n)) if r0n and c0n else None,
        "relative_l2": float(np.linalg.norm(r - c) / (rn + 1e-12)),
        "max_abs_error": float(np.max(np.abs(r - c))),
        "mean_abs_error": float(np.mean(np.abs(r - c))),
        "candidate_stats": stats(c.astype(np.float32)),
        "reference_stats": stats(r.astype(np.float32)),
    }
    out.update({f"candidate_{k}": v for k, v in entropy(c).items()})
    return out


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def run_hf_suffix(model: Any, hidden_np: np.ndarray, start_layer: int, dtype: Any, seq_len: int) -> np.ndarray:
    import torch

    hidden = torch.tensor(np.asarray(hidden_np, dtype=np.float32).tolist(), dtype=dtype).unsqueeze(0)
    pos = torch.arange(seq_len, dtype=torch.long).unsqueeze(0)
    cache_position = torch.arange(seq_len, dtype=torch.long)
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
    logits_t = model.lm_head(normed[:, -1:, :])[0, -1]
    return tensor_to_numpy(logits_t)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--position-root", required=True)
    ap.add_argument("--truth-root", default="/mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/full_truth_repeat_v11")
    ap.add_argument("--hf-boundary-root", default="/mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/hf_boundaries_v11")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=4)
    args = ap.parse_args()

    started = time.time()
    report = {
        "schema_version": "dream7b_s100p_v16_position_hf_suffix",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "rows": [],
        "errors": [],
        "safety": dict(SAFETY),
        "status": "started",
        "route": "BPU seg00_01 position-variant output -> HF/PyTorch BF16 suffix layers 1..27 + final norm + lm_head",
    }
    out_root = Path(args.output_root)
    write_json(out_root / "position_hf_suffix_report.json", report)
    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        model = AutoModel.from_pretrained(args.model_dir, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.eval()
        report["status"] = "model_loaded"
        write_json(out_root / "position_hf_suffix_report.json", report)
        with torch.no_grad():
            for cid in CASE_IDS:
                ref = np.load(Path(args.truth_root) / cid / "repeat_full_truth_logits.npy")
                hf_layer0 = np.load(Path(args.hf_boundary_root) / cid / "layer_00_output.npy")
                hf_embedding = np.load(Path(args.hf_boundary_root) / cid / "embedding_output.npy")
                for variant in VARIANTS:
                    try:
                        hidden_path = Path(args.position_root) / cid / "position_variants" / variant / "dequant_output.npy"
                        hidden = np.load(hidden_path).astype(np.float32)
                        logits = run_hf_suffix(model, hidden, 1, dtype, args.seq_len)
                        row_dir = out_root / "evidence" / "neutralized_position_seg00_v16" / cid / variant
                        logits_info = save_array(row_dir / "suffix_logits.npy", logits)
                        row = {
                            "case_id": cid,
                            "position_variant": variant,
                            "input_boundary": {"path": str(hidden_path), "sha256": sha256_file(hidden_path), "stats": stats(hidden)},
                            "logits": logits_info,
                            "final_metrics": compare(ref, logits),
                            "boundary_vs_hf_layer0_output": compare(hf_layer0, hidden),
                            "boundary_vs_hf_embedding_output": compare(hf_embedding, hidden),
                            "status": "pass",
                        }
                        write_json(row_dir / "metadata.json", row)
                        report["rows"].append(row)
                    except Exception as exc:
                        report["errors"].append({"case_id": cid, "variant": variant, "type": type(exc).__name__, "message": str(exc)})
                    write_json(out_root / "position_hf_suffix_report.json", report)
        report["status"] = "pass" if len(report["rows"]) == len(CASE_IDS) * len(VARIANTS) and not report["errors"] else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(out_root / "position_hf_suffix_report.json", report)
    (out_root / "position_hf_suffix_report.md").write_text(
        "# v16 Neutralized Position seg00 HF Suffix\n\n"
        f"- status: `{report.get('status')}`\n"
        f"- rows: `{len(report.get('rows', []))}`\n"
        f"- errors: `{len(report.get('errors', []))}`\n"
        f"- elapsed_total_seconds: `{report.get('elapsed_total_seconds')}`\n"
        "- generation_quality_run: `False`\n"
        "- product_routes_18888_18889_touched: `False`\n"
        "- dream7b_frontend_openclaw_traffic_touched: `False`\n",
        encoding="utf-8",
    )
    print(out_root / "position_hf_suffix_report.json", flush=True)
    return 0 if report.get("rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
