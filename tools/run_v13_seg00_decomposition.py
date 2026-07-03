#!/usr/bin/env python3
"""Dream7B/S100P v13 seg00_01 decomposition probes.

This script runs only offline boundary/logits-free probes. It never calls
generation and never touches product routes.
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

from run_v12r_remote_reconstruction import (
    CASE_IDS,
    hbm_path,
    iter_jsonl,
    model_name,
    quant_metadata,
    save_array,
    sha256_file,
    stats,
    tensor_to_numpy,
    write_json,
)


def run_seg0_variant(args: argparse.Namespace, case: dict[str, Any], variant: str) -> dict[str, Any]:
    from hbm_runtime import HB_HBMRuntime

    hbm = hbm_path(Path(args.hbm_root), 0, args.seq_len, args.w_bits, args.lm_head_w_bits, args.final_logits_mode)
    name = model_name(0, args.final_logits_mode)
    runtime = HB_HBMRuntime(str(hbm))
    token_ids = np.asarray(case["token_ids"], dtype=np.int32)
    pos = np.arange(args.seq_len, dtype=np.int32)
    if variant == "canonical_pos_128":
        inputs = {"_input_0": token_ids.reshape(1, args.seq_len), "_input_1": pos}
    elif variant == "position_1x128":
        inputs = {"_input_0": token_ids.reshape(1, args.seq_len), "_input_1": pos.reshape(1, args.seq_len)}
    elif variant == "token_only":
        inputs = {"_input_0": token_ids.reshape(1, args.seq_len)}
    elif variant == "input0_flat_pos_128":
        inputs = {"_input_0": token_ids, "_input_1": pos}
    else:
        raise ValueError(variant)
    out = runtime.run(inputs, model_name=name)
    raw = out[name]["_output_0"]
    qmeta = quant_metadata(runtime, name)
    scale = qmeta.get("scale_first")
    deq = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
    meta = {
        "variant": variant,
        "model_name": name,
        "hbm_path": str(hbm),
        "hbm_sha256": sha256_file(hbm) if hbm.exists() else None,
        "inputs": {k: {"shape": list(v.shape), "dtype": str(v.dtype)} for k, v in inputs.items()},
        "quant_metadata": qmeta,
        "raw_stats": stats(raw),
        "dequant_stats": stats(deq),
    }
    del out
    del runtime
    return {"raw": raw, "dequant": deq, "metadata": meta}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=6)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--w-bits", type=int, default=8)
    ap.add_argument("--lm-head-w-bits", type=int, default=16)
    ap.add_argument("--final-logits-mode", default="last-token")
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v13_seg00_decomposition_remote",
        "python": sys.version,
        "platform": platform.platform(),
        "model_dir": args.model_dir,
        "rows": [],
        "errors": [],
        "safety": {"generation_quality_run": False, "product_routes_18888_18889_touched": False},
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
        model = AutoModel.from_pretrained(args.model_dir, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.eval()
        cases = [c for c in iter_jsonl(Path(args.cases)) if c.get("case_id") in CASE_IDS]
        out_root = Path(args.output_root) / "evidence" / "seg00_01_decomposition_v13"
        pos = torch.arange(args.seq_len, dtype=torch.long).unsqueeze(0)
        cache_position = torch.arange(args.seq_len, dtype=torch.long)
        layer = model.model.layers[0]
        report["layer0_module_tree"] = [(name, type(mod).__name__) for name, mod in layer.named_modules() if name]
        report["status"] = "model_loaded"
        write_json(Path(args.report_json), report)

        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                case_dir = out_root / cid
                input_ids = torch.tensor(case["token_ids"], dtype=torch.long).reshape(1, args.seq_len)
                embedding = model.model.embed_tokens(input_ids)
                position_embeddings = model.model.rotary_emb(embedding, pos)
                pre_attn_norm = layer.input_layernorm(embedding)
                attn_out = layer.self_attn(
                    hidden_states=pre_attn_norm,
                    attention_mask=None,
                    position_ids=pos,
                    past_key_value=None,
                    output_attentions=False,
                    use_cache=False,
                    cache_position=cache_position,
                    position_embeddings=position_embeddings,
                )[0]
                post_attn_residual = embedding + attn_out
                pre_mlp_norm = layer.post_attention_layernorm(post_attn_residual)
                mlp_out = layer.mlp(pre_mlp_norm)
                layer0_final = post_attn_residual + mlp_out
                hf_boundaries = {
                    "token_embedding_output": embedding[0],
                    "rotary_cos": position_embeddings[0][0],
                    "rotary_sin": position_embeddings[1][0],
                    "layer0_pre_attention_norm_output": pre_attn_norm[0],
                    "layer0_attention_output": attn_out[0],
                    "layer0_post_attention_residual": post_attn_residual[0],
                    "layer0_pre_mlp_norm_output": pre_mlp_norm[0],
                    "layer0_mlp_output": mlp_out[0],
                    "layer0_final_output": layer0_final[0],
                }
                hf_rows = {}
                for name, tensor in hf_boundaries.items():
                    arr = tensor_to_numpy(tensor)
                    hf_rows[name] = save_array(case_dir / "hf" / f"{name}.npy", arr)

                bpu_rows = []
                for variant in ["canonical_pos_128", "position_1x128", "token_only", "input0_flat_pos_128"]:
                    try:
                        result = run_seg0_variant(args, case, variant)
                        vdir = case_dir / "bpu" / variant
                        raw_info = save_array(vdir / "bpu_raw_output.npy", result["raw"])
                        deq_info = save_array(vdir / "bpu_dequant_output.npy", result["dequant"])
                        row = result["metadata"]
                        row.update({"status": "pass", "raw_output": raw_info, "dequant_output": deq_info})
                    except Exception as exc:
                        row = {"variant": variant, "status": "fail", "type": type(exc).__name__, "message": str(exc)}
                    bpu_rows.append(row)
                row = {"case_id": cid, "hf_boundaries": hf_rows, "bpu_variants": bpu_rows}
                write_json(case_dir / "metadata.json", row)
                report["rows"].append(row)
                report["status"] = "running"
                write_json(Path(args.report_json), report)
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})

    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    if report["rows"] and not report["errors"]:
        report["status"] = "pass"
    write_json(Path(args.report_json), report)
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(
        "\n".join(
            [
                "# v13 seg00_01 Decomposition Remote",
                "",
                f"- status: `{report['status']}`",
                f"- rows: `{len(report['rows'])}`",
                f"- errors: `{len(report['errors'])}`",
                "- generation_quality_run: `False`",
                "- product_routes_18888_18889_touched: `False`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(args.report_json, flush=True)
    return 0 if report["rows"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
