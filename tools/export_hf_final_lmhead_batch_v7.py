#!/usr/bin/env python3
"""Export Dream7B HF final-norm + lm_head logits for BPU hidden inputs.

This avoids full Dream forward. It loads only `model.norm.weight` and
`lm_head.weight` from the HF safetensors checkpoint and applies RMSNorm plus
chunked projection to final-segment input tensors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_CASES = ["zeros", "ramp", "short_chinese_prompt_padded"]
DEFAULT_VARIANTS = [
    "real_x",
    "real_x_div_2",
    "real_x_div_2p5",
    "real_x_div_2p75",
    "real_x_div_3",
    "real_x_clip_8",
    "real_x_clip_6",
    "real_x_clip_5",
    "real_x_z_normalized",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def torch_frombuffer_compat() -> None:
    import torch

    if hasattr(torch, "frombuffer"):
        return

    def _frombuffer(buffer, dtype, count=-1, offset=0, requires_grad=False):  # type: ignore[no-untyped-def]
        mapping = {
            torch.float32: np.float32,
            torch.float16: np.float16,
            torch.bfloat16: np.uint16,
            torch.int64: np.int64,
            torch.int32: np.int32,
            torch.int16: np.int16,
            torch.int8: np.int8,
            torch.uint8: np.uint8,
            torch.bool: np.bool_,
        }
        if dtype not in mapping:
            raise TypeError(f"unsupported dtype for torch.frombuffer shim: {dtype}")
        arr = np.frombuffer(buffer, dtype=mapping[dtype], count=count, offset=offset)
        if dtype is torch.bfloat16:
            arr32 = (arr.astype(np.uint32) << 16).view(np.float32)
            return torch.from_numpy(arr32).to(torch.bfloat16)
        return torch.from_numpy(arr)

    torch.frombuffer = _frombuffer  # type: ignore[attr-defined]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_tensor(index: dict[str, Any], candidates: list[str], contains: list[str]) -> tuple[str, str]:
    weight_map = index.get("weight_map", {})
    for name in candidates:
        if name in weight_map:
            return name, weight_map[name]
    matches = []
    for name, shard in weight_map.items():
        low = name.lower()
        if all(token.lower() in low for token in contains):
            matches.append((name, shard))
    if len(matches) == 1:
        return matches[0]
    raise KeyError(f"ambiguous/missing tensor candidates={candidates}, contains={contains}, matches={matches[:20]}")


def tensor_stats(x: np.ndarray) -> dict[str, Any]:
    y = x.reshape(-1)
    finite = y[np.isfinite(y)] if np.issubdtype(y.dtype, np.floating) else y
    return {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "size": int(y.size),
        "min": float(np.min(finite)) if finite.size else None,
        "max": float(np.max(finite)) if finite.size else None,
        "mean": float(np.mean(finite)) if finite.size else None,
        "std": float(np.std(finite)) if finite.size else None,
        "abs_max": float(np.max(np.abs(finite))) if finite.size else None,
        "nonzero_count": int(np.count_nonzero(y)),
        "constant": bool(y.size > 0 and np.all(y == y.flat[0])),
        "allzero": bool(y.size > 0 and np.all(y == 0)),
        "nan_count": int(np.isnan(y).sum()) if np.issubdtype(y.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(y).sum()) if np.issubdtype(y.dtype, np.floating) else 0,
    }


def topk(x: np.ndarray, k: int = 10) -> list[dict[str, Any]]:
    y = x.reshape(-1)
    idx = np.argsort(y)[-k:][::-1]
    return [{"token": int(i), "logit": float(y[i])} for i in idx]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    parser.add_argument("--endpoint-root", default="/mnt/nas/openclaw/reports/models/dream7b_s100p_v5_execution_20260701/evidence/final_segment_dense_sweep_v5")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--cases", default=",".join(DEFAULT_CASES))
    parser.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    parser.add_argument("--last-token-index", type=int, default=127)
    parser.add_argument("--chunk-size", type=int, default=8192)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    args = parser.parse_args()

    torch_frombuffer_compat()
    import torch
    from safetensors import safe_open

    model_dir = Path(args.model_dir)
    endpoint_root = Path(args.endpoint_root)
    output_root = Path(args.output_root)
    index = load_json(model_dir / "model.safetensors.index.json")
    config = load_json(model_dir / "config.json")
    norm_name, norm_shard = find_tensor(
        index,
        ["model.norm.weight", "norm.weight", "transformer.norm.weight", "model.final_layernorm.weight"],
        ["norm", "weight"],
    )
    lm_name, lm_shard = find_tensor(
        index,
        ["lm_head.weight", "model.embed_tokens.weight", "transformer.wte.weight", "embed_tokens.weight"],
        ["lm_head", "weight"],
    )
    norm_path = model_dir / norm_shard
    lm_path = model_dir / lm_shard
    with safe_open(str(norm_path), framework="pt", device="cpu") as f:
        norm_weight = f.get_tensor(norm_name).float().cpu()
    with safe_open(str(lm_path), framework="pt", device="cpu") as f:
        lm_weight = f.get_tensor(lm_name).cpu()

    eps = float(config.get("rms_norm_eps", config.get("layer_norm_eps", 1e-6)))
    hidden_size = int(config.get("hidden_size", norm_weight.numel()))
    vocab_size = int(config.get("vocab_size", lm_weight.shape[0]))
    cases = [x.strip() for x in args.cases.split(",") if x.strip()]
    variants = [x.strip() for x in args.variants.split(",") if x.strip()]

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for case_id in cases:
        for variant in variants:
            input_path = endpoint_root / case_id / variant / "input.npy"
            out_dir = output_root / case_id / variant
            logits_path = out_dir / "hf_final_lmhead_logits.npy"
            metadata_path = out_dir / "metadata.json"
            try:
                hidden = np.load(input_path).astype(np.float32)
                if hidden.shape != (128, hidden_size):
                    raise ValueError(f"expected hidden shape (128,{hidden_size}), got {hidden.shape}")
                last_np = hidden[args.last_token_index]
                last = torch.from_numpy(last_np).float()
                denom = torch.sqrt(torch.mean(last * last) + eps)
                normed = (last / denom) * norm_weight
                logits = np.empty((vocab_size,), dtype=np.float32)
                if lm_weight.shape[-1] == hidden_size:
                    for start in range(0, vocab_size, args.chunk_size):
                        end = min(start + args.chunk_size, vocab_size)
                        logits[start:end] = torch.mv(lm_weight[start:end].float(), normed).cpu().numpy()
                elif lm_weight.shape[0] == hidden_size:
                    for start in range(0, vocab_size, args.chunk_size):
                        end = min(start + args.chunk_size, vocab_size)
                        logits[start:end] = torch.mv(lm_weight[:, start:end].t().float(), normed).cpu().numpy()
                else:
                    raise ValueError(f"lm tensor shape {tuple(lm_weight.shape)} incompatible with hidden {hidden_size}")
                out_dir.mkdir(parents=True, exist_ok=True)
                np.save(logits_path, logits)
                meta = {
                    "case_id": case_id,
                    "variant": variant,
                    "model_dir": str(model_dir),
                    "endpoint_input_path": str(input_path),
                    "last_token_index": args.last_token_index,
                    "norm_type": "rms_norm",
                    "eps": eps,
                    "norm_tensor": norm_name,
                    "norm_shape": list(norm_weight.shape),
                    "norm_shard": norm_shard,
                    "norm_shard_sha256": sha256_file(norm_path),
                    "lm_tensor": lm_name,
                    "lm_shape": list(lm_weight.shape),
                    "lm_shard": lm_shard,
                    "lm_shard_sha256": sha256_file(lm_path),
                    "hidden_stats": tensor_stats(hidden),
                    "logits_path": str(logits_path),
                    "logits_sha256": sha256_file(logits_path),
                    "logits_stats": tensor_stats(logits),
                    "top10": topk(logits, 10),
                }
                write_json(metadata_path, meta)
                rows.append(meta)
            except Exception as exc:
                err = {"case_id": case_id, "variant": variant, "input_path": str(input_path), "error": f"{type(exc).__name__}: {exc}"}
                errors.append(err)
                write_json(out_dir / "error.json", err)

    report = {
        "schema_version": "dream7b_s100p_v7_hf_final_lmhead_batch",
        "model_dir": str(model_dir),
        "endpoint_root": str(endpoint_root),
        "output_root": str(output_root),
        "cases": cases,
        "variants": variants,
        "norm_tensor": norm_name,
        "lm_tensor": lm_name,
        "eps": eps,
        "hidden_size": hidden_size,
        "vocab_size": vocab_size,
        "completed": len(rows),
        "failed": len(errors),
        "rows": rows,
        "errors": errors,
        "verdict": "pass_hf_final_lmhead_only_logits_exported" if rows and not errors else ("partial_weights_found_but_matmul_blocked" if rows else "fail_tensor_names_or_shapes_unresolved"),
    }
    write_json(Path(args.report_json), report)
    lines = [
        "# HF Final Norm + LM Head Only Export v7",
        "",
        f"- verdict: `{report['verdict']}`",
        f"- completed: `{len(rows)}`",
        f"- failed: `{len(errors)}`",
        f"- norm_tensor: `{norm_name}`",
        f"- lm_tensor: `{lm_name}`",
        "",
        "| case | variant | allzero | nonzero | top1 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        stats = row["logits_stats"]
        top1 = row["top10"][0]["token"] if row["top10"] else None
        lines.append(f"| `{row['case_id']}` | `{row['variant']}` | `{stats['allzero']}` | {stats['nonzero_count']} | {top1} |")
    write_json(output_root / "MANIFEST_REPORT_POINTER.json", {"report_json": str(args.report_json), "report_md": str(args.report_md)})
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.report_json)
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
