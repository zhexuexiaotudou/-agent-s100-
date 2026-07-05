#!/usr/bin/env python3
"""Export Dream7B semantic HF/PyTorch truth logits on x86/GPU or torch2 CPU.

Offline logits-only runner. It does not call generation or product routes.
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--cases-jsonl", default="semantic_cases.jsonl")
    ap.add_argument("--output-root", default="semantic_truth_output")
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--device-map", default="", help="Optional transformers device_map value, e.g. auto")
    ap.add_argument("--torch-threads", type=int, default=8)
    ap.add_argument("--fallback-fp32", action="store_true")
    args = ap.parse_args()

    started = time.time()
    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v20_x86_gpu_semantic_truth_export",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": {
            "generation_quality_run": False,
            "product_routes_18888_18889_touched": False,
            "dream7b_frontend_openclaw_traffic_touched": False,
            "harness_qwen_openclaw_defaults_modified": False,
        },
        "hf_rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(out_root / "semantic_truth_export_report.json", report)
    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        device = "cuda" if args.device == "auto" and torch.cuda.is_available() else ("cpu" if args.device == "auto" else args.device)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        report["device_selected"] = device
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
        write_json(out_root / "semantic_truth_export_report.json", report)
        try:
            model = AutoModel.from_pretrained(args.model_dir, **load_kwargs)
        except Exception:
            if not args.fallback_fp32 or args.dtype == "float32":
                raise
            dtype = torch.float32
            report["fallback_used"] = "float32"
            load_kwargs["torch_dtype"] = dtype
            model = AutoModel.from_pretrained(args.model_dir, **load_kwargs)
        if not args.device_map:
            model = model.to(device)
        model.eval()
        report["status"] = "model_loaded"
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["parameter_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
        write_json(out_root / "semantic_truth_export_report.json", report)

        cases = read_jsonl(Path(args.cases_jsonl))
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                t0 = time.time()
                input_ids = torch.tensor([case["token_ids"]], dtype=torch.long, device=device if not args.device_map else None)
                position_ids = torch.tensor([case.get("position_ids", list(range(input_ids.shape[1])))], dtype=torch.long, device=device if not args.device_map else None)
                attention_mask = torch.tensor([case.get("attention_mask", [1] * input_ids.shape[1])], dtype=torch.bool, device=device if not args.device_map else None)
                kwargs = {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "position_ids": position_ids,
                    "use_cache": False,
                    "return_dict": True,
                    "output_hidden_states": False,
                    "num_logits_to_keep": 1,
                }
                try:
                    outputs = model(**kwargs)
                except TypeError:
                    kwargs.pop("num_logits_to_keep", None)
                    outputs = model(**kwargs)
                logits = tensor_to_numpy(outputs.logits[0, -1])
                row = {
                    "case_id": cid,
                    "semantic_or_diagnostic": case.get("semantic_or_diagnostic", "semantic"),
                    "truth_row_type": f"HF/PyTorch {str(dtype).replace('torch.', '')}",
                    "elapsed_seconds": round(time.time() - t0, 3),
                    "token_ids_sha256": case.get("token_ids_sha256"),
                    "logits": save_array(out_root / cid / "hf_truth_logits.npy", logits),
                    "top10": np.argsort(logits.reshape(-1))[-10:][::-1].astype(int).tolist(),
                    "status": "pass",
                }
                write_json(out_root / cid / "metadata.json", row)
                report["hf_rows"].append(row)
                report["status"] = "running"
                report["hf_truth_rows"] = len(report["hf_rows"])
                write_json(out_root / "semantic_truth_export_report.json", report)
        report["status"] = "pass" if len(report["hf_rows"]) == len(cases) else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["hf_truth_rows"] = len(report.get("hf_rows", []))
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(out_root / "semantic_truth_export_report.json", report)
    return 0 if report["hf_truth_rows"] >= 8 else 2


if __name__ == "__main__":
    raise SystemExit(main())
