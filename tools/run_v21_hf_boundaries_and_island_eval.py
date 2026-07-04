#!/usr/bin/env python3
"""Export HF truth/boundaries and evaluate BPU island outputs with HF suffix.

Offline logits-only research runner. It does not run generation or touch
product routes.
"""
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def normalized_entropy(logits: np.ndarray) -> float:
    x = np.asarray(logits, dtype=np.float64).reshape(-1)
    x = x - np.max(x)
    p = np.exp(x)
    p = p / np.sum(p)
    ent = -float(np.sum(p * np.log(p + 1e-300)))
    return ent / math.log(float(p.size))


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
    return {
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
        "candidate_normalized_entropy": normalized_entropy(c),
        "reference_normalized_entropy": normalized_entropy(r),
        "candidate_stats": stats(c.astype(np.float32)),
        "reference_stats": stats(r.astype(np.float32)),
    }


def strict_pass(metrics: dict[str, Any]) -> bool:
    return bool(
        metrics.get("shape_match")
        and metrics.get("reference_top1_in_candidate_top5")
        and metrics.get("cosine") is not None
        and metrics["cosine"] >= 0.95
        and metrics.get("relative_l2") is not None
        and metrics["relative_l2"] <= 0.30
        and not metrics.get("candidate_stats", {}).get("allzero")
        and not metrics.get("candidate_stats", {}).get("constant")
    )


def map_device(model: Any, module_name: str) -> Any:
    import torch

    device_map = getattr(model, "hf_device_map", {}) or {}
    raw = device_map.get(module_name)
    if raw is None:
        # Find the closest parent assignment if accelerate collapsed the map.
        parts = module_name.split(".")
        for end in range(len(parts) - 1, 0, -1):
            raw = device_map.get(".".join(parts[:end]))
            if raw is not None:
                break
    if raw is None:
        return torch.device("cpu")
    if isinstance(raw, int):
        return torch.device(f"cuda:{raw}")
    if str(raw).isdigit():
        return torch.device(f"cuda:{raw}")
    return torch.device(str(raw))


def run_suffix(model: Any, hidden_np: np.ndarray, start_layer: int, dtype: Any, seq_len: int = 128) -> np.ndarray:
    import torch

    hidden = torch.tensor(np.asarray(hidden_np, dtype=np.float32), dtype=dtype).unsqueeze(0)
    with torch.no_grad():
        for layer_idx in range(start_layer, 28):
            layer = model.model.layers[layer_idx]
            dev = map_device(model, f"model.layers.{layer_idx}")
            hidden = hidden.to(dev)
            pos = torch.arange(seq_len, dtype=torch.long, device=dev).unsqueeze(0)
            cache_position = torch.arange(seq_len, dtype=torch.long, device=dev)
            hidden = layer(
                hidden,
                attention_mask=None,
                position_ids=pos,
                past_key_value=None,
                output_attentions=False,
                use_cache=False,
                cache_position=cache_position,
                position_embeddings=None,
            )[0]
        norm_dev = map_device(model, "model.norm")
        hidden = hidden.to(norm_dev)
        normed = model.model.norm(hidden)
        head_dev = map_device(model, "lm_head")
        normed = normed.to(head_dev)
        logits_t = model.lm_head(normed[:, -1:, :])[0, -1]
    return tensor_to_numpy(logits_t)


def island_name(island: list[int]) -> str:
    return "island_" + "_".join(str(x) for x in island)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--cases-jsonl", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--bpu-root")
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--device-map", default="auto")
    ap.add_argument("--torch-threads", type=int, default=8)
    args = ap.parse_args()

    started = time.time()
    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v21_hf_boundaries_and_island_eval",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": dict(SAFETY),
        "hf_rows": [],
        "island_rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(out_root / "hf_boundaries_and_island_eval_report.json", report)
    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        report["cuda_available"] = bool(torch.cuda.is_available())
        report["model_files"] = {}
        model_dir = Path(args.model_dir)
        for name in ["config.json", "model.safetensors.index.json", "tokenizer_config.json", "vocab.json", "merges.txt", "modeling_dream.py", "configuration_dream.py"]:
            p = model_dir / name
            if p.exists():
                report["model_files"][name] = {"path": str(p), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)}
        load_kwargs: dict[str, Any] = {
            "trust_remote_code": True,
            "torch_dtype": dtype,
            "low_cpu_mem_usage": True,
            "use_safetensors": True,
        }
        if args.device_map:
            load_kwargs["device_map"] = args.device_map
        report["status"] = "model_load_start"
        write_json(out_root / "hf_boundaries_and_island_eval_report.json", report)
        model = AutoModel.from_pretrained(args.model_dir, **load_kwargs)
        model.eval()
        report["status"] = "model_loaded"
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["parameter_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
        report["hf_device_map"] = {str(k): str(v) for k, v in getattr(model, "hf_device_map", {}).items()}
        write_json(out_root / "hf_boundaries_and_island_eval_report.json", report)

        cases = read_jsonl(Path(args.cases_jsonl))
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                t0 = time.time()
                input_ids = torch.tensor([case["token_ids"]], dtype=torch.long)
                position_ids = torch.tensor([case.get("position_ids", list(range(input_ids.shape[1])))], dtype=torch.long)
                attention_mask = torch.tensor([case.get("attention_mask", [1] * input_ids.shape[1])], dtype=torch.bool)
                kwargs = {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "position_ids": position_ids,
                    "use_cache": False,
                    "return_dict": True,
                    "output_hidden_states": True,
                    "num_logits_to_keep": 1,
                }
                try:
                    outputs = model(**kwargs)
                except TypeError:
                    kwargs.pop("num_logits_to_keep", None)
                    outputs = model(**kwargs)
                hidden_states = getattr(outputs, "hidden_states", None)
                if hidden_states is None:
                    raise RuntimeError("missing hidden states")
                case_dir = out_root / cid
                boundaries = {}
                for layer_idx in range(3):
                    arr = tensor_to_numpy(hidden_states[layer_idx + 1][0])
                    boundaries[f"layer_{layer_idx:02d}_output"] = save_array(case_dir / "hf_boundaries" / f"layer_{layer_idx:02d}_output.npy", arr)
                logits = tensor_to_numpy(outputs.logits[0, -1])
                truth = save_array(case_dir / "hf_truth" / "hf_truth_logits.npy", logits)
                row = {
                    "case_id": cid,
                    "semantic_or_diagnostic": case.get("semantic_or_diagnostic", "semantic"),
                    "elapsed_seconds": round(time.time() - t0, 6),
                    "token_ids_sha256": case.get("token_ids_sha256"),
                    "truth": truth,
                    "boundaries": boundaries,
                    "top10": np.argsort(logits.reshape(-1))[-10:][::-1].astype(int).tolist(),
                    "status": "pass",
                }
                write_json(case_dir / "hf_truth" / "metadata.json", row)
                report["hf_rows"].append(row)
                report["status"] = "hf_running"
                report["hf_truth_rows"] = len(report["hf_rows"])
                write_json(out_root / "hf_boundaries_and_island_eval_report.json", report)

        if args.bpu_root:
            bpu_root = Path(args.bpu_root)
            for hf_row in report["hf_rows"]:
                cid = hf_row["case_id"]
                ref_logits = np.load(out_root / cid / "hf_truth" / "hf_truth_logits.npy")
                for island in ISLANDS:
                    end = island[-1]
                    bpu_hidden_path = bpu_root / cid / island_name(island) / "island_final_hidden.npy"
                    row_dir = out_root / cid / island_name(island)
                    if not bpu_hidden_path.exists():
                        report["errors"].append({"case_id": cid, "island": island, "type": "MissingBpuHidden", "message": str(bpu_hidden_path)})
                        continue
                    t0 = time.time()
                    hidden = np.load(bpu_hidden_path)
                    cand_logits = run_suffix(model, hidden, end + 1, dtype)
                    logits_info = save_array(row_dir / "island_logits.npy", cand_logits)
                    boundary_ref = out_root / cid / "hf_boundaries" / f"layer_{end:02d}_output.npy"
                    boundary_metrics = compare(np.load(boundary_ref), hidden) if boundary_ref.exists() else None
                    final_metrics = compare(ref_logits, cand_logits)
                    row = {
                        "case_id": cid,
                        "island": island,
                        "semantic_or_diagnostic": hf_row.get("semantic_or_diagnostic", "semantic"),
                        "route": f"HF torch2 prefix through layer {island[0]-1}, S100P BPU island {island[0]}..{end}, HF torch2 suffix {end+1}..27 + final norm + lm_head",
                        "conversion_used": "official_runtime_output_scale_direct_float32_no_target_affine",
                        "bpu_hidden_path": str(bpu_hidden_path),
                        "logits": logits_info,
                        "final_metrics": final_metrics,
                        "boundary_metrics": boundary_metrics,
                        "strict_gate": {"reference_top1_in_candidate_top5_required": True, "cosine_min": 0.95, "relative_l2_max": 0.30, "no_allzero_or_constant_logits": True},
                        "strict_pass": strict_pass(final_metrics),
                        "elapsed_seconds": round(time.time() - t0, 6),
                        "status": "pass",
                    }
                    write_json(row_dir / "metadata.json", row)
                    report["island_rows"].append(row)
                    report["status"] = "island_eval_running"
                    report["island_row_count"] = len(report["island_rows"])
                    write_json(out_root / "hf_boundaries_and_island_eval_report.json", report)
        report["status"] = "pass"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["hf_truth_rows"] = len(report.get("hf_rows", []))
    report["island_row_count"] = len(report.get("island_rows", []))
    report["elapsed_total_seconds"] = round(time.time() - started, 6)
    write_json(out_root / "hf_boundaries_and_island_eval_report.json", report)
    print(out_root / "hf_boundaries_and_island_eval_report.json", flush=True)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
