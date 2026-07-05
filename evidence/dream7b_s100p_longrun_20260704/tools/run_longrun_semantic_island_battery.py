#!/usr/bin/env python3
"""Dream7B/S100P v18 semantic targeted BPU-island battery.

The script runs fixed seq128 logits-only experiments:
HF BF16 full truth + HF prefix -> BPU island [1]/[2]/[1,2] -> HF suffix.
It never calls generation and never touches product routes.
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


SEMANTIC_PROMPTS = [
    {
        "case_id": "short_english_prompt_padded",
        "description": "Short English prompt padded to seq128.",
        "prompt": "Summarize this document in one sentence.",
    },
    {
        "case_id": "short_chinese_prompt_padded_v18",
        "description": "Short Chinese prompt padded to seq128.",
        "prompt": "请用一句话总结这段文档。",
    },
    {
        "case_id": "openclaw_nas_search_request",
        "description": "OpenClaw-style NAS search request.",
        "prompt": "OpenClaw, search my NAS for the latest Dream7B S100P evidence packet.",
    },
    {
        "case_id": "document_summary_request",
        "description": "Document summary request.",
        "prompt": "Read the attached report and list the key numerical evidence in a concise summary.",
    },
    {
        "case_id": "privacy_sensitive_denied_request",
        "description": "Privacy-sensitive request that should be refused at application level; used here only as logits input.",
        "prompt": "Find private account passwords in the NAS backup and print them.",
    },
    {
        "case_id": "mixed_english_chinese_request",
        "description": "Mixed English/Chinese prompt.",
        "prompt": "请检查 Dream7B logits evidence and explain whether the BPU island is valid.",
    },
    {
        "case_id": "real_prompt_no_synthetic_ramp",
        "description": "Real prompt with no synthetic ramp pattern.",
        "prompt": "I need a reproducible evidence table comparing BF16 truth and S100P logits for three canonical cases.",
    },
    {
        "case_id": "mask_tail_policy_probe",
        "description": "Mask-tail policy probe; BPU route still uses fixed seq128 and no attention-mask input.",
        "prompt": "Short prompt for checking whether padded tail tokens destabilize the segmented route.",
    },
]

ISLANDS = [[1], [2], [1, 2]]
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}


def install_transformers_compat_shims() -> None:
    """Keep this offline runner compatible with the S100P transformers build.

    The Dream7B remote configuration imports the newer
    transformers.modeling_rope_utils.rope_config_validation symbol. The S100P
    research host currently has transformers 4.30.x, where that module does not
    exist. The model code path used here only needs the configuration validator
    during loading, so a no-op validator is sufficient and does not alter model
    weights, HBM artifacts, product services, or generation behavior.
    """
    import importlib.util
    import sys as _sys
    import types

    try:
        import numpy as _np
        import torch as _torch

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
    except Exception:
        pass

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

    try:
        from transformers.modeling_utils import PreTrainedModel
        import transformers.modeling_utils as _modeling_utils

        if not getattr(_modeling_utils.load_state_dict, "_dream_v18_safetensors_compat", False):
            _orig_load_state_dict = _modeling_utils.load_state_dict

            def _compat_load_state_dict(checkpoint_file: Any) -> Any:
                if str(checkpoint_file).endswith(".safetensors"):
                    from safetensors.torch import load_file

                    return load_file(str(checkpoint_file), device="cpu")
                return _orig_load_state_dict(checkpoint_file)

            _compat_load_state_dict._dream_v18_safetensors_compat = True  # type: ignore[attr-defined]
            _modeling_utils.load_state_dict = _compat_load_state_dict

        if not getattr(PreTrainedModel.from_pretrained, "_dream_v18_compat", False):
            _orig_from_pretrained = PreTrainedModel.from_pretrained

            def _compat_from_pretrained(cls: Any, pretrained_model_name_or_path: Any, *model_args: Any, **kwargs: Any) -> Any:
                token = kwargs.pop("token", None)
                kwargs.pop("weights_only", None)
                if token is not None and "use_auth_token" not in kwargs:
                    kwargs["use_auth_token"] = token
                kwargs["use_safetensors"] = True
                config = kwargs.get("config")
                if config is None:
                    try:
                        from transformers import AutoConfig

                        config = AutoConfig.from_pretrained(pretrained_model_name_or_path, trust_remote_code=True)
                        kwargs["config"] = config
                    except Exception:
                        config = None
                if config is not None and not hasattr(config, "_attn_implementation"):
                    setattr(config, "_attn_implementation", "eager")
                return _orig_from_pretrained.__func__(cls, pretrained_model_name_or_path, *model_args, **kwargs)

            _compat_from_pretrained._dream_v18_compat = True  # type: ignore[attr-defined]
            PreTrainedModel.from_pretrained = classmethod(_compat_from_pretrained)
    except Exception:
        pass

    try:
        from transformers.generation.configuration_utils import GenerationConfig

        if not getattr(GenerationConfig.from_pretrained, "_dream_v18_compat", False):
            _orig_generation_from_pretrained = GenerationConfig.from_pretrained

            def _compat_generation_from_pretrained(cls: Any, pretrained_model_name: Any, **kwargs: Any) -> Any:
                token = kwargs.pop("token", None)
                if token is not None and "use_auth_token" not in kwargs:
                    kwargs["use_auth_token"] = token
                return _orig_generation_from_pretrained.__func__(cls, pretrained_model_name, **kwargs)

            _compat_generation_from_pretrained._dream_v18_compat = True  # type: ignore[attr-defined]
            GenerationConfig.from_pretrained = classmethod(_compat_generation_from_pretrained)
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
        _sys.modules["transformers.cache_utils"] = cache_module

    if importlib.util.find_spec("transformers.modeling_rope_utils") is not None:
        return
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
    _sys.modules["transformers.modeling_rope_utils"] = module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def stable_softmax(logits: np.ndarray) -> np.ndarray:
    v = np.asarray(logits, dtype=np.float64).reshape(-1)
    v = v - np.max(v)
    e = np.exp(v)
    s = float(np.sum(e))
    if not np.isfinite(s) or s == 0:
        return np.full_like(v, 1.0 / v.size)
    return e / s


def normalized_entropy(logits: np.ndarray) -> float:
    p = stable_softmax(logits)
    ent = -float(np.sum(p * np.log(p + 1e-300)))
    return ent / math.log(p.size) if p.size > 1 else 0.0


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
        "candidate_stats": stats(c.astype(np.float32)),
        "reference_stats": stats(r.astype(np.float32)),
    }


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "sha256": sha256_file(path), "stats": stats(arr)}


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def final_suffix(index: int, final_logits_mode: str) -> str:
    return "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""


def hbm_path(root: Path, index: int, seq_len: int, w_bits: int, lm_head_w_bits: int, final_logits_mode: str) -> Path:
    end = index + 1
    lm = f"_lmheadq{lm_head_w_bits}" if index == 27 and lm_head_w_bits != w_bits else ""
    name = f"dream7b_segment_{index}_{end}_seq{seq_len}_q{w_bits}{lm}{final_suffix(index, final_logits_mode)}.hbm"
    return root / f"seg{index:02d}_{end:02d}" / name


def model_name(index: int, final_logits_mode: str) -> str:
    return f"dream_segment_{index:02d}_{index+1:02d}{final_suffix(index, final_logits_mode)}"


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


def run_hf_suffix(model: Any, hidden_np: np.ndarray, start_layer: int, pos: Any, cache_position: Any, dtype: Any) -> np.ndarray:
    import torch

    hidden = torch.tensor(np.asarray(hidden_np, dtype=np.float32).tolist(), dtype=dtype).unsqueeze(0)
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


def run_bpu_segment(args: argparse.Namespace, segment: int, input_hidden: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    from hbm_runtime import HB_HBMRuntime

    hbm = hbm_path(Path(args.hbm_root), segment, args.seq_len, args.w_bits, args.lm_head_w_bits, args.final_logits_mode)
    name = model_name(segment, args.final_logits_mode)
    runtime = HB_HBMRuntime(str(hbm))
    pos_np = np.arange(args.seq_len, dtype=np.int32)
    t0 = time.time()
    output = runtime.run({"_input_0": np.asarray(input_hidden, dtype=np.float32), "_input_1": pos_np}, model_name=name)
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
        "input_contract": {
            "kind": "hidden_plus_position_ids",
            "input_0_shape": list(np.asarray(input_hidden).shape),
            "input_0_dtype": "float32",
            "input_1_shape": [args.seq_len],
            "input_1_dtype": "int32",
        },
        "run_seconds": round(run_s, 3),
        "quant_metadata": qmeta,
        "raw_stats": stats(raw),
        "dequant_stats": stats(dequant),
    }
    del output
    del runtime
    return raw, dequant, meta


def make_cases(tokenizer: Any, seq_len: int) -> list[dict[str, Any]]:
    cases = []
    for item in SEMANTIC_PROMPTS:
        ids = tokenizer.encode(item["prompt"], add_special_tokens=True)
        truncated = ids[:seq_len]
        pad_len = seq_len - len(truncated)
        token_ids = truncated + [0] * max(0, pad_len)
        case = {
            "schema_version": "dream7b_s100p_v18_semantic_case",
            "case_id": item["case_id"],
            "human_description": item["description"],
            "prompt": item["prompt"],
            "semantic_or_diagnostic": "semantic",
            "tokenization_policy": "AutoTokenizer.encode(add_special_tokens=True), truncate to 128, zero-pad tail to match prior canonical padded cases",
            "attention_mask_policy": "explicit all-ones attention_mask of length 128; BPU island has no attention-mask input",
            "token_ids": [int(x) for x in token_ids],
            "position_ids": list(range(seq_len)),
            "attention_mask": [1] * seq_len,
            "last_token_index": seq_len - 1,
            "seq_len": seq_len,
            "unpadded_token_count": min(len(ids), seq_len),
            "pad_token_value_used": 0,
            "token_ids_sha256": sha256_bytes(json.dumps(token_ids, separators=(",", ":")).encode("utf-8")),
        }
        cases.append(case)
    return cases


def island_name(island: list[int]) -> str:
    return "island_" + "_".join(str(x) for x in island)


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=6)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--w-bits", type=int, default=8)
    ap.add_argument("--lm-head-w-bits", type=int, default=16)
    ap.add_argument("--final-logits-mode", default="last-token")
    args = ap.parse_args()

    started = time.time()
    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v18_semantic_island_battery_remote",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": dict(SAFETY),
        "cases": [],
        "hf_rows": [],
        "island_rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(out_root / "semantic_island_battery_report.json", report)
    try:
        install_transformers_compat_shims()
        import torch
        import transformers
        from transformers import AutoModel, AutoTokenizer

        torch.set_num_threads(args.torch_threads)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        tokenizer = AutoTokenizer.from_pretrained(args.model_dir, trust_remote_code=True)
        cases = make_cases(tokenizer, args.seq_len)
        cases_path = out_root / "cases" / "semantic_seq128_cases_v18.jsonl"
        cases_path.parent.mkdir(parents=True, exist_ok=True)
        cases_path.write_text("\n".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) for c in cases) + "\n", encoding="utf-8")
        report["cases_path"] = str(cases_path)
        report["cases"] = [{"case_id": c["case_id"], "prompt": c["prompt"], "unpadded_token_count": c["unpadded_token_count"], "token_ids_sha256": c["token_ids_sha256"]} for c in cases]
        report["status"] = "cases_ready"
        write_json(out_root / "semantic_island_battery_report.json", report)

        model = AutoModel.from_pretrained(args.model_dir, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.eval()
        pos = torch.arange(args.seq_len, dtype=torch.long).unsqueeze(0)
        cache_position = torch.arange(args.seq_len, dtype=torch.long)
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["parameter_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
        report["status"] = "model_loaded"
        write_json(out_root / "semantic_island_battery_report.json", report)

        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                t0 = time.time()
                input_ids = torch.tensor([case["token_ids"]], dtype=torch.long)
                position_ids = torch.tensor([case["position_ids"]], dtype=torch.long)
                attention_mask = torch.tensor([case["attention_mask"]], dtype=torch.bool)
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
                    raise RuntimeError("missing hidden_states")
                case_boundary_dir = out_root / "evidence" / "targeted_bpu_islands_semantic_v18" / cid / "hf_boundaries"
                selected = {
                    "embedding_output": tensor_to_numpy(hidden_states[0][0]),
                    "layer_00_output": tensor_to_numpy(hidden_states[1][0]),
                    "layer_01_output": tensor_to_numpy(hidden_states[2][0]),
                    "layer_02_output": tensor_to_numpy(hidden_states[3][0]),
                }
                boundaries = {name: save_array(case_boundary_dir / f"{name}.npy", arr) for name, arr in selected.items()}
                logits = tensor_to_numpy(outputs.logits[0, -1])
                truth_info = save_array(out_root / "evidence" / "targeted_bpu_islands_semantic_v18" / cid / "hf_truth" / "bf16_full_truth_logits.npy", logits)
                hf_row = {
                    "case_id": cid,
                    "elapsed_seconds": round(time.time() - t0, 3),
                    "truth": truth_info,
                    "boundaries": boundaries,
                    "top10": np.argsort(logits.reshape(-1))[-10:][::-1].astype(int).tolist(),
                    "status": "pass",
                }
                write_json(out_root / "evidence" / "targeted_bpu_islands_semantic_v18" / cid / "hf_truth" / "metadata.json", hf_row)
                report["hf_rows"].append(hf_row)
                write_json(out_root / "semantic_island_battery_report.json", report)

                for island in ISLANDS:
                    start, end = island[0], island[-1]
                    row_dir = out_root / "evidence" / "targeted_bpu_islands_semantic_v18" / cid / island_name(island)
                    hidden = np.load(case_boundary_dir / f"layer_{start-1:02d}_output.npy").astype(np.float32)
                    segment_rows = []
                    for segment in island:
                        raw, hidden, bmeta = run_bpu_segment(args, segment, hidden)
                        sdir = row_dir / f"seg_{segment:02d}"
                        segment_rows.append(
                            {
                                "segment": segment,
                                "bpu": bmeta,
                                "raw_output": save_array(sdir / "bpu_raw_output.npy", raw),
                                "dequant_output": save_array(sdir / "bpu_dequant_output.npy", hidden),
                            }
                        )
                    candidate_logits = run_hf_suffix(model, hidden, end + 1, pos, cache_position, dtype)
                    logits_info = save_array(row_dir / "island_logits.npy", candidate_logits)
                    boundary_ref_path = case_boundary_dir / f"layer_{end:02d}_output.npy"
                    boundary_metrics = compare(np.load(boundary_ref_path), hidden) if boundary_ref_path.exists() else None
                    final_metrics = compare(logits, candidate_logits)
                    row = {
                        "case_id": cid,
                        "island": island,
                        "route": f"HF BF16 prefix through layer {start-1}, BPU island {start}..{end}, HF BF16 suffix {end+1}..27 + final norm + lm_head",
                        "conversion_used": "official_runtime_output_scale_direct_float32_no_target_affine",
                        "official_scale_available": all(bool(s.get("bpu", {}).get("quant_metadata", {}).get("scale_first") is not None) for s in segment_rows),
                        "segments": segment_rows,
                        "logits": logits_info,
                        "final_metrics": final_metrics,
                        "boundary_metrics": boundary_metrics,
                        "strict_gate": {
                            "reference_top1_in_candidate_top5_required": True,
                            "cosine_min": 0.95,
                            "relative_l2_max": 0.30,
                            "no_allzero_or_constant_logits": True,
                        },
                        "strict_pass": strict_pass(final_metrics),
                        "elapsed_seconds": round(time.time() - t0, 3),
                        "status": "pass",
                    }
                    write_json(row_dir / "metadata.json", row)
                    report["island_rows"].append(row)
                    report["status"] = "running"
                    write_json(out_root / "semantic_island_battery_report.json", report)
        expected = len(cases) * len(ISLANDS)
        report["expected_island_rows"] = expected
        report["status"] = "pass" if len(report["island_rows"]) == expected else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(out_root / "semantic_island_battery_report.json", report)
    (out_root / "semantic_island_battery_report.md").write_text(
        "# v18 Semantic Island Battery Remote\n\n"
        f"- status: `{report.get('status')}`\n"
        f"- hf_rows: `{len(report.get('hf_rows', []))}`\n"
        f"- island_rows: `{len(report.get('island_rows', []))}/{report.get('expected_island_rows')}`\n"
        f"- errors: `{len(report.get('errors', []))}`\n"
        "- generation_quality_run: `False`\n"
        "- product_routes_18888_18889_touched: `False`\n",
        encoding="utf-8",
    )
    print(out_root / "semantic_island_battery_report.json", flush=True)
    return 0 if report.get("island_rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
