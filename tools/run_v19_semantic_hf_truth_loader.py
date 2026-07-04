#!/usr/bin/env python3
"""Dream7B/S100P v19 semantic HF truth loader.

This is an offline logits-only research runner. It does not call generation,
product routes, OpenClaw foreground traffic, or ports 18888/18889.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

import numpy as np


SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}


def now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


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
    rows: list[dict[str, Any]] = []
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


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "stats": stats(arr)}


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def log_stage(report: dict[str, Any], out_root: Path, stage: str, extra: dict[str, Any] | None = None) -> None:
    row = {"stage": stage, "at_utc": now()}
    if extra:
        row.update(extra)
    report.setdefault("stage_log", []).append(row)
    report["status"] = stage
    write_json(out_root / "semantic_hf_truth_loader_report.json", report)
    print(json.dumps(row, ensure_ascii=False), flush=True)


def mem_snapshot() -> dict[str, Any]:
    try:
        out = subprocess.run(["free", "-b"], text=True, capture_output=True, check=False)
        return {"returncode": out.returncode, "stdout": out.stdout.strip(), "stderr": out.stderr.strip()}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}:{exc}"}


def install_transformers_compat_shims() -> None:
    import numpy as _np
    import torch as _torch

    if not hasattr(_torch, "autocast"):
        class _NoOpAutocast:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def __enter__(self) -> None:
                return None

            def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                return False

        _torch.autocast = _NoOpAutocast

    if not hasattr(_torch.nn.functional, "scaled_dot_product_attention"):
        def _scaled_dot_product_attention_compat(
            query: Any,
            key: Any,
            value: Any,
            attn_mask: Any | None = None,
            dropout_p: float = 0.0,
            is_causal: bool = False,
            scale: float | None = None,
        ) -> Any:
            import math

            scale_factor = scale if scale is not None else 1.0 / math.sqrt(query.size(-1))
            scores = _torch.matmul(query, key.transpose(-2, -1)) * scale_factor
            if is_causal:
                q_len = query.size(-2)
                k_len = key.size(-2)
                causal = _torch.ones((q_len, k_len), dtype=_torch.bool, device=query.device).tril(diagonal=0)
                scores = scores.masked_fill(~causal, float("-inf"))
            if attn_mask is not None:
                scores = scores + attn_mask
            probs = _torch.nn.functional.softmax(scores, dim=-1, dtype=_torch.float32).to(query.dtype)
            if dropout_p and dropout_p > 0:
                probs = _torch.nn.functional.dropout(probs, p=dropout_p, training=True)
            return _torch.matmul(probs, value)

        _torch.nn.functional.scaled_dot_product_attention = _scaled_dot_product_attention_compat

    if not hasattr(_torch, "frombuffer"):
        def _torch_frombuffer_compat(buffer: Any, *, dtype: Any, count: int = -1, offset: int = 0, requires_grad: bool = False) -> Any:
            dtype_map = {
                getattr(_torch, "float32", None): _np.float32,
                getattr(_torch, "float", None): _np.float32,
                getattr(_torch, "float16", None): _np.float16,
                getattr(_torch, "half", None): _np.float16,
                getattr(_torch, "int64", None): _np.int64,
                getattr(_torch, "long", None): _np.int64,
                getattr(_torch, "int32", None): _np.int32,
                getattr(_torch, "int", None): _np.int32,
                getattr(_torch, "int16", None): _np.int16,
                getattr(_torch, "short", None): _np.int16,
                getattr(_torch, "int8", None): _np.int8,
                getattr(_torch, "uint8", None): _np.uint8,
                getattr(_torch, "bool", None): _np.bool_,
            }
            if dtype == getattr(_torch, "bfloat16", object()):
                arr = _np.frombuffer(buffer, dtype=_np.int16, count=count, offset=offset)
                tensor = _torch.from_numpy(arr.copy()).view(_torch.bfloat16)
            else:
                np_dtype = dtype_map.get(dtype)
                if np_dtype is None:
                    raise TypeError(f"torch.frombuffer compat does not support dtype={dtype}")
                arr = _np.frombuffer(buffer, dtype=np_dtype, count=count, offset=offset)
                tensor = _torch.from_numpy(arr.copy())
            if requires_grad and tensor.is_floating_point():
                tensor.requires_grad_(True)
            return tensor

        _torch.frombuffer = _torch_frombuffer_compat

    try:
        import transformers.utils as _tf_utils

        if not hasattr(_tf_utils, "is_flash_attn_2_available"):
            _tf_utils.is_flash_attn_2_available = lambda: False
        if not hasattr(_tf_utils, "is_flash_attn_greater_or_equal_2_10"):
            _tf_utils.is_flash_attn_greater_or_equal_2_10 = lambda: False
        if not hasattr(_tf_utils, "is_torchdynamo_compiling"):
            _tf_utils.is_torchdynamo_compiling = lambda: False
    except Exception:
        pass

    if importlib.util.find_spec("transformers.cache_utils") is None:
        cache_module = types.ModuleType("transformers.cache_utils")

        class Cache:
            def get_seq_length(self) -> int:
                return 0

            def update(self, key_states: Any, value_states: Any, layer_idx: int, cache_kwargs: Any | None = None) -> tuple[Any, Any]:
                return key_states, value_states

        class DynamicCache(Cache):
            pass

        cache_module.Cache = Cache
        cache_module.DynamicCache = DynamicCache
        sys.modules["transformers.cache_utils"] = cache_module

    if importlib.util.find_spec("transformers.modeling_rope_utils") is None:
        module = types.ModuleType("transformers.modeling_rope_utils")

        def rope_config_validation(config: Any, ignore_keys: Any | None = None) -> None:
            return None

        def _compute_default_rope_parameters(config: Any | None = None, device: Any | None = None, seq_len: Any | None = None, **rope_kwargs: Any) -> tuple[Any, float]:
            import torch

            if config is None:
                base = rope_kwargs.get("base", 10000)
                dim = rope_kwargs["dim"]
            else:
                base = getattr(config, "rope_theta", 10000)
                dim = getattr(config, "hidden_size") // getattr(config, "num_attention_heads")
            inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.int64, device=device).float() / dim))
            return inv_freq, 1.0

        module.rope_config_validation = rope_config_validation
        module.ROPE_INIT_FUNCTIONS = {
            "default": _compute_default_rope_parameters,
            "linear": _compute_default_rope_parameters,
            "dynamic": _compute_default_rope_parameters,
            "yarn": _compute_default_rope_parameters,
            "longrope": _compute_default_rope_parameters,
            "llama3": _compute_default_rope_parameters,
        }
        sys.modules["transformers.modeling_rope_utils"] = module


def route_a_streaming_safetensors(args: argparse.Namespace, report: dict[str, Any], out_root: Path) -> bool:
    import torch
    import transformers
    from safetensors import safe_open
    from transformers import AutoConfig, AutoModel
    from transformers.modeling_utils import no_init_weights

    log_stage(report, out_root, "route_a_start", {"memory": mem_snapshot()})
    install_transformers_compat_shims()
    torch.set_num_threads(args.torch_threads)
    dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
    model_dir = Path(args.model_dir)
    index_path = model_dir / "model.safetensors.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    weight_map: dict[str, str] = index.get("weight_map", {})
    shard_names = sorted(set(weight_map.values()))
    report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
    report["model_files"] = {
        "config": {"path": str(model_dir / "config.json"), "sha256": sha256_file(model_dir / "config.json")},
        "index": {"path": str(index_path), "sha256": sha256_file(index_path), "weight_count": len(weight_map), "shards": shard_names},
    }
    for name in ["tokenizer_config.json", "vocab.json", "merges.txt", "modeling_dream.py", "configuration_dream.py"]:
        p = model_dir / name
        if p.exists():
            report["model_files"][name] = {"path": str(p), "sha256": sha256_file(p), "size_bytes": p.stat().st_size}

    config = AutoConfig.from_pretrained(str(model_dir), trust_remote_code=True)
    if not hasattr(config, "_attn_implementation"):
        setattr(config, "_attn_implementation", "eager")
    log_stage(report, out_root, "route_a_config_loaded", {"config_class": type(config).__name__, "memory": mem_snapshot()})

    old_dtype = torch.get_default_dtype()
    torch.set_default_dtype(dtype)
    try:
        t0 = time.time()
        with no_init_weights(_enable=True):
            model = AutoModel.from_config(config, trust_remote_code=True)
        model.eval()
    finally:
        torch.set_default_dtype(old_dtype)
    report["model_class"] = type(model).__name__
    report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
    report["parameter_dtypes_after_init"] = sorted({str(p.dtype) for p in model.parameters()})
    log_stage(report, out_root, "route_a_model_no_init_created", {"seconds": round(time.time() - t0, 3), "memory": mem_snapshot()})

    state = model.state_dict()
    missing_in_model = []
    loaded = 0
    load_errors = []
    for shard_name in shard_names:
        shard_path = model_dir / shard_name
        t0 = time.time()
        shard_loaded = 0
        with safe_open(str(shard_path), framework="pt", device="cpu") as sf:
            for key in sf.keys():
                if key not in state:
                    missing_in_model.append(key)
                    continue
                try:
                    tensor = sf.get_tensor(key)
                    target = state[key]
                    if tensor.dtype != target.dtype:
                        tensor = tensor.to(dtype=target.dtype)
                    if tensor.shape != target.shape:
                        load_errors.append({"key": key, "error": "shape_mismatch", "source_shape": list(tensor.shape), "target_shape": list(target.shape)})
                        continue
                    target.copy_(tensor)
                    loaded += 1
                    shard_loaded += 1
                    del tensor
                except Exception as exc:
                    load_errors.append({"key": key, "error": f"{type(exc).__name__}:{exc}"})
                if loaded % 50 == 0:
                    gc.collect()
        gc.collect()
        log_stage(
            report,
            out_root,
            "route_a_shard_loaded",
            {"shard": shard_name, "loaded_in_shard": shard_loaded, "loaded_total": loaded, "seconds": round(time.time() - t0, 3), "memory": mem_snapshot()},
        )
    expected = len(weight_map)
    report["route_a_load_summary"] = {
        "expected_weight_keys": expected,
        "loaded_weight_keys": loaded,
        "missing_in_model_count": len(missing_in_model),
        "missing_in_model_sample": missing_in_model[:20],
        "load_error_count": len(load_errors),
        "load_error_sample": load_errors[:20],
        "parameter_dtypes_after_load": sorted({str(p.dtype) for p in model.parameters()}),
    }
    if load_errors or loaded < expected:
        log_stage(report, out_root, "route_a_load_incomplete", report["route_a_load_summary"])
        return False

    cases = read_jsonl(Path(args.cases_jsonl))
    report["cases_jsonl"] = {"path": args.cases_jsonl, "sha256": sha256_file(Path(args.cases_jsonl)), "case_count": len(cases)}
    log_stage(report, out_root, "route_a_forward_start", {"case_count": len(cases), "memory": mem_snapshot()})
    hf_rows = []
    with torch.no_grad():
        for case in cases:
            cid = case["case_id"]
            case_dir = out_root / cid
            log_stage(report, out_root, "route_a_case_start", {"case_id": cid, "hf_rows": len(hf_rows), "memory": mem_snapshot()})
            input_ids = torch.tensor([case["token_ids"]], dtype=torch.long)
            position_ids = torch.tensor([case.get("position_ids", list(range(args.seq_len)))], dtype=torch.long)
            attention_mask = torch.tensor([case.get("attention_mask", [1] * args.seq_len)], dtype=torch.bool)
            kwargs = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "position_ids": position_ids,
                "use_cache": False,
                "return_dict": True,
                "output_hidden_states": True,
                "num_logits_to_keep": 1,
            }
            t0 = time.time()
            try:
                outputs = model(**kwargs)
            except TypeError:
                kwargs.pop("num_logits_to_keep", None)
                outputs = model(**kwargs)
            hidden_states = getattr(outputs, "hidden_states", None)
            logits = tensor_to_numpy(outputs.logits[0, -1])
            row = {
                "case_id": cid,
                "elapsed_seconds": round(time.time() - t0, 3),
                "semantic_or_diagnostic": case.get("semantic_or_diagnostic", "semantic"),
                "token_ids_sha256": case.get("token_ids_sha256"),
                "logits": save_array(case_dir / "hf_truth" / "bf16_full_truth_logits.npy", logits),
                "top10": np.argsort(logits.reshape(-1))[-10:][::-1].astype(int).tolist(),
                "status": "pass",
            }
            if hidden_states is not None:
                boundary_dir = case_dir / "hf_boundaries"
                for idx, name in [(0, "embedding_output"), (1, "layer_00_output"), (2, "layer_01_output"), (3, "layer_02_output")]:
                    if idx < len(hidden_states):
                        row.setdefault("boundaries", {})[name] = save_array(boundary_dir / f"{name}.npy", tensor_to_numpy(hidden_states[idx][0]))
            write_json(case_dir / "hf_truth" / "metadata.json", row)
            hf_rows.append(row)
            report["hf_rows"] = hf_rows
            log_stage(report, out_root, "route_a_case_done", {"case_id": cid, "hf_rows": len(hf_rows), "memory": mem_snapshot()})
            gc.collect()
    report["hf_rows"] = hf_rows
    report["status"] = "pass" if len(hf_rows) >= args.min_rows else "partial"
    write_json(out_root / "semantic_hf_truth_loader_report.json", report)
    return len(hf_rows) >= args.min_rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases-jsonl", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=4)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--min-rows", type=int, default=8)
    args = ap.parse_args()

    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v19_semantic_hf_truth_loader",
        "created_at_utc": now(),
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": dict(SAFETY),
        "hf_rows": [],
        "errors": [],
        "status": "started",
        "routes_attempted": ["route_a_safetensors_direct_loader"],
    }
    write_json(out_root / "semantic_hf_truth_loader_report.json", report)
    ok = False
    try:
        ok = route_a_streaming_safetensors(args, report, out_root)
    except BaseException as exc:
        report["status"] = "fail"
        report["errors"].append({"route": "route_a_safetensors_direct_loader", "type": type(exc).__name__, "message": str(exc)})
        log_stage(report, out_root, "route_a_exception", {"error_type": type(exc).__name__, "message": str(exc), "memory": mem_snapshot()})
    report["final_status"] = "pass" if ok else "fail"
    report["hf_truth_rows"] = len(report.get("hf_rows", []))
    write_json(out_root / "semantic_hf_truth_loader_report.json", report)
    (out_root / "semantic_hf_truth_loader_report.md").write_text(
        "# v19 Semantic HF Truth Loader\n\n"
        f"- final_status: `{report['final_status']}`\n"
        f"- hf_truth_rows: `{report['hf_truth_rows']}`\n"
        f"- errors: `{len(report.get('errors', []))}`\n"
        "- generation_quality_run: `False`\n"
        "- product_routes_18888_18889_touched: `False`\n",
        encoding="utf-8",
    )
    print(out_root / "semantic_hf_truth_loader_report.json", flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
