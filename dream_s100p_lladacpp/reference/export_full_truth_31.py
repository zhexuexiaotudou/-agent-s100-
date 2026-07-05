#!/usr/bin/env python3
"""Export Dream7B 31-row HF/PyTorch reference truth.

This script exports last-token logits and a selected final hidden state for
prebuilt cases. It is logits-only and never calls generation or product routes.
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


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_COUNTS = {
    "semantic_original": 8,
    "canonical": 3,
    "block_wise": 4,
    "revision": 4,
    "fixed_output": 4,
    "infill": 4,
    "control_command": 4,
}
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def stats(arr: np.ndarray) -> dict[str, Any]:
    x = np.asarray(arr)
    y = x.reshape(-1)
    yf = y.astype(np.float64, copy=False)
    return {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "size": int(x.size),
        "min": float(np.min(yf)),
        "max": float(np.max(yf)),
        "mean": float(np.mean(yf)),
        "std": float(np.std(yf)),
        "abs_max": float(np.max(np.abs(yf))),
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.all(y == 0)),
        "constant": bool(np.all(y == y.flat[0])),
        "nan_count": int(np.isnan(yf).sum()),
        "inf_count": int(np.isinf(yf).sum()),
    }


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": rel(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "stats": stats(arr)}


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def softmax_top_probs(logits: np.ndarray, top_indices: list[int]) -> list[float]:
    x = np.asarray(logits, dtype=np.float64).reshape(-1)
    x = x - float(np.max(x))
    exp = np.exp(x)
    probs = exp / float(np.sum(exp))
    return [float(probs[idx]) for idx in top_indices]


def map_device(model: Any, module_name: str) -> Any:
    import torch

    device_map = getattr(model, "hf_device_map", {}) or {}
    raw = device_map.get(module_name)
    if raw is None:
        parts = module_name.split(".")
        for end in range(len(parts) - 1, 0, -1):
            raw = device_map.get(".".join(parts[:end]))
            if raw is not None:
                break
    if raw is None:
        return torch.device("cpu")
    if isinstance(raw, int) or str(raw).isdigit():
        return torch.device(f"cuda:{raw}")
    return torch.device(str(raw))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default=str(ROOT / "tmp" / "true_batch_inputs" / "dream7b-hf"))
    ap.add_argument("--cases-jsonl", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31_cases.jsonl"))
    ap.add_argument("--output-root", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31_arrays"))
    ap.add_argument("--truth-jsonl", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31.jsonl"))
    ap.add_argument("--manifest", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31_manifest.json"))
    ap.add_argument("--report-json", default=str(ROOT / "dream_s100p_lladacpp" / "reports" / "30210_full_truth_31_export_gate.json"))
    ap.add_argument("--report-md", default=str(ROOT / "dream_s100p_lladacpp" / "reports" / "30210_full_truth_31_export_gate.md"))
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--device-map", default="auto")
    ap.add_argument("--torch-threads", type=int, default=8)
    args = ap.parse_args()

    started = time.time()
    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_lladacpp_full_truth_31_export_gate_v1",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": SAFETY,
        "rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(Path(args.report_json), report)
    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        report["cuda_available"] = bool(torch.cuda.is_available())
        report["cuda_device_count"] = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
        if torch.cuda.is_available():
            report["cuda_device_name"] = torch.cuda.get_device_name(0)
        model_dir = Path(args.model_dir)
        report["model_files"] = {}
        for name in [
            "SHA256SUMS",
            "config.json",
            "model.safetensors.index.json",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
            "tokenization_dream.py",
            "modeling_dream.py",
            "configuration_dream.py",
        ]:
            path = model_dir / name
            if path.exists():
                report["model_files"][name] = {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        cases = read_jsonl(Path(args.cases_jsonl))
        report["case_count_requested"] = len(cases)
        report["case_type_counts_requested"] = {}
        for case in cases:
            ctype = case["case_type"]
            report["case_type_counts_requested"][ctype] = report["case_type_counts_requested"].get(ctype, 0) + 1

        load_kwargs: dict[str, Any] = {
            "trust_remote_code": True,
            "torch_dtype": dtype,
            "low_cpu_mem_usage": True,
            "use_safetensors": True,
        }
        if args.device_map:
            load_kwargs["device_map"] = args.device_map
        report["status"] = "model_load_start"
        write_json(Path(args.report_json), report)
        model = AutoModel.from_pretrained(str(model_dir), **load_kwargs)
        model.eval()
        report["status"] = "model_loaded"
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["parameter_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
        report["hf_device_map"] = {str(k): str(v) for k, v in getattr(model, "hf_device_map", {}).items()}
        write_json(Path(args.report_json), report)

        truth_rows: list[dict[str, Any]] = []
        input_device = None if args.device_map else map_device(model, "model.embed_tokens")
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                t0 = time.time()
                input_ids = torch.tensor([case["token_ids"]], dtype=torch.long, device=input_device)
                position_ids = torch.tensor([case["position_ids"]], dtype=torch.long, device=input_device)
                attention_mask = torch.tensor([case["attention_mask"]], dtype=torch.bool, device=input_device)
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
                logits = tensor_to_numpy(outputs.logits[0, -1])
                if getattr(outputs, "hidden_states", None) is None:
                    raise RuntimeError(f"{cid}: output_hidden_states missing")
                hidden = tensor_to_numpy(outputs.hidden_states[-1][0])
                top5 = np.argsort(logits.reshape(-1))[-5:][::-1].astype(int).tolist()
                top1 = int(top5[0])
                top_probs = softmax_top_probs(logits, top5)
                logits_info = save_array(out_root / cid / "logits.npy", logits)
                hidden_info = save_array(out_root / cid / "selected_final_hidden.npy", hidden)
                row = {
                    "schema_version": "dream7b_s100p_lladacpp_full_truth_row_v1",
                    "case_id": cid,
                    "case_type": case["case_type"],
                    "prompt": case.get("prompt"),
                    "input_ids": case["token_ids"],
                    "attention_mask": case["attention_mask"],
                    "position_ids": case["position_ids"],
                    "diffusion_mask": case["diffusion_mask"],
                    "timestep_or_noise_schedule": case["timestep_or_noise_schedule"],
                    "selected_layer_hidden": hidden_info,
                    "logits": logits_info,
                    "top1": top1,
                    "top5": top5,
                    "probabilities": {"top5_indices": top5, "top5_probabilities": top_probs},
                    "prob_checksum": sha256_json({"top5": top5, "top5_probabilities": top_probs}),
                    "block_token_states": case["block_token_states"],
                    "confidence_scores": {"last_token_top1_probability": top_probs[0]},
                    "committed_token_mask": case["committed_token_mask"],
                    "revision_mask": case["revision_mask"],
                    "dtype": str(dtype).replace("torch.", ""),
                    "model_identity": {
                        "model_dir": str(model_dir),
                        "model_class": type(model).__name__,
                        "parameter_count": int(sum(p.numel() for p in model.parameters())),
                        "model_files": report["model_files"],
                    },
                    "tokenizer_identity": {
                        "token_ids_sha256": case["token_ids_sha256"],
                        "source_case_sha256": case["case_sha256"],
                    },
                    "elapsed_seconds": round(time.time() - t0, 3),
                    "sha256": "",
                    "status": "pass",
                }
                row["sha256"] = sha256_json({k: v for k, v in row.items() if k != "sha256"})
                truth_rows.append(row)
                report["rows"].append(
                    {
                        "case_id": cid,
                        "case_type": case["case_type"],
                        "status": "pass",
                        "elapsed_seconds": row["elapsed_seconds"],
                        "logits_sha256": logits_info["sha256"],
                        "hidden_sha256": hidden_info["sha256"],
                        "top1": top1,
                    }
                )
                report["truth_row_count"] = len(truth_rows)
                report["status"] = "running"
                write_json(Path(args.report_json), report)

        write_jsonl(Path(args.truth_jsonl), truth_rows)
        counts: dict[str, int] = {}
        for row in truth_rows:
            counts[row["case_type"]] = counts.get(row["case_type"], 0) + 1
        errors = []
        if len(truth_rows) != 31:
            errors.append(f"truth_row_count expected 31 got {len(truth_rows)}")
        for case_type, expected in REQUIRED_COUNTS.items():
            if counts.get(case_type, 0) != expected:
                errors.append(f"{case_type} expected {expected} got {counts.get(case_type, 0)}")
        manifest = {
            "schema_version": "dream7b_s100p_lladacpp_full_truth_31_manifest_v1",
            "truth_row_count": len(truth_rows),
            "case_type_counts": counts,
            "required_counts": REQUIRED_COUNTS,
            "truth_jsonl": rel(Path(args.truth_jsonl)),
            "truth_jsonl_sha256": sha256_file(Path(args.truth_jsonl)),
            "array_root": rel(out_root),
            "dtype": str(dtype).replace("torch.", ""),
            "runtime_versions": report["runtime_versions"],
            "cuda_available": report.get("cuda_available"),
            "model_identity": report.get("model_files", {}),
            "safety": SAFETY,
            "errors": errors,
            "status": "pass" if not errors else "fail",
        }
        write_json(Path(args.manifest), manifest)
        report["manifest"] = manifest
        report["truth_row_count"] = len(truth_rows)
        report["case_type_counts"] = counts
        report["status"] = "pass" if not errors else "fail"
        report["verdict"] = "full_truth_31_export_pass" if not errors else "full_truth_31_export_failed"
    except Exception as exc:
        report["status"] = "fail"
        report["verdict"] = "full_truth_31_export_failed"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(Path(args.report_json), report)
    md = [
        "# Full Truth 31 Export Gate",
        "",
        f"- Verdict: `{report.get('verdict', report['status'])}`",
        f"- Status: `{report['status']}`",
        f"- Truth rows: `{report.get('truth_row_count', 0)}`",
        f"- Runtime: `{report.get('runtime_versions')}`",
        f"- CUDA: `{report.get('cuda_available')}` `{report.get('cuda_device_name', '')}`",
        f"- Safety: generation/product/OpenClaw touched = `False`",
    ]
    if report.get("errors"):
        md.append("")
        md.append("## Errors")
        md.extend(f"- `{err.get('type')}`: {err.get('message')}" for err in report["errors"])
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
