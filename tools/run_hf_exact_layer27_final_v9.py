#!/usr/bin/env python3
"""Attempt Dream7B HF full logits and isolated final-segment references.

This script is deliberately offline: it reads local/NAS HF safetensors and
canonical token IDs, runs no generation loop, and does not touch product routes.
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


DEFAULT_CASES = ["zeros", "ramp", "short_chinese_prompt_padded"]
DEFAULT_VARIANTS = [
    "real_x",
    "real_x_div_2",
    "real_x_div_2p25",
    "real_x_div_2p5",
    "real_x_div_2p75",
    "real_x_div_3",
    "real_x_div_3p25",
    "real_x_div_3p5",
    "real_x_div_4",
    "real_x_clip_8",
    "real_x_clip_6",
    "real_x_clip_5",
    "real_x_clip_4",
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


def read_cases(path: Path, wanted: set[str]) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("case_id") in wanted:
            rows.append(item)
    return rows


def array_stats(x: np.ndarray) -> dict[str, Any]:
    y = x.reshape(-1)
    return {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "abs_max": float(np.max(np.abs(y))),
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.all(y == 0)),
        "constant": bool(np.all(y == y.flat[0])),
    }


def topk(x: np.ndarray, k: int = 10) -> list[int]:
    return np.argsort(x.reshape(-1))[-k:][::-1].astype(int).tolist()


def tensor_to_numpy_1d(tensor: Any) -> np.ndarray:
    """Convert a 1D torch tensor to numpy without relying on torch's numpy bridge."""
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--endpoint-root", default="/mnt/nas/openclaw/reports/models/dream7b_s100p_v5_execution_20260701/evidence/final_segment_dense_sweep_v5")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--case-ids", default=",".join(DEFAULT_CASES))
    ap.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--full-forward", action="store_true")
    ap.add_argument("--isolated-final", action="store_true")
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v8_hf_full_and_isolated_final",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "model_dir": args.model_dir,
        "cases_path": args.cases,
        "endpoint_root": args.endpoint_root,
        "requested_case_ids": [x for x in args.case_ids.split(",") if x],
        "requested_variants": [x for x in args.variants.split(",") if x],
        "dtype_requested": args.dtype,
        "full_forward_requested": args.full_forward,
        "isolated_final_requested": args.isolated_final,
        "full_forward_rows": [],
        "isolated_final_rows": [],
        "errors": [],
    }
    try:
        import torch
        import transformers
        from transformers import AutoModel

        report["runtime_versions"] = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "numpy": np.__version__,
        }
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        load_start = time.time()
        model = AutoModel.from_pretrained(
            args.model_dir,
            trust_remote_code=True,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        )
        model.eval()
        report["model_load_seconds"] = round(time.time() - load_start, 3)
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["parameter_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
        cases = read_cases(Path(args.cases), set(report["requested_case_ids"]))
        out_root = Path(args.output_root)
        endpoint_root = Path(args.endpoint_root)
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                input_ids = torch.tensor([case["token_ids"]], dtype=torch.long)
                position_ids = torch.arange(input_ids.shape[1], dtype=torch.long).unsqueeze(0)
                if args.full_forward:
                    t0 = time.time()
                    out = model(
                        input_ids=input_ids,
                        position_ids=position_ids,
                        use_cache=False,
                        num_logits_to_keep=1,
                        return_dict=True,
                    )
                    logits = tensor_to_numpy_1d(out.logits[0, -1])
                    lp = out_root / "full_reference_v8" / f"hf_{args.dtype}" / cid / "last_logits.npy"
                    lp.parent.mkdir(parents=True, exist_ok=True)
                    np.save(lp, logits)
                    meta = {
                        "case_id": cid,
                        "dtype": args.dtype,
                        "last_token_index": 127,
                        "logits_path": str(lp),
                        "logits_sha256": sha256_file(lp),
                        "logits_stats": array_stats(logits),
                        "top10": topk(logits, 10),
                        "elapsed_seconds": round(time.time() - t0, 3),
                        "token_ids_sha256": hashlib.sha256(json.dumps(case["token_ids"], separators=(",", ":")).encode()).hexdigest(),
                    }
                    write_json(lp.with_name("metadata.json"), meta)
                    report["full_forward_rows"].append(meta)
                if args.isolated_final:
                    pos = torch.arange(128, dtype=torch.long).unsqueeze(0)
                    cache_position = torch.arange(128, dtype=torch.long)
                    for variant in report["requested_variants"]:
                        hp = endpoint_root / cid / variant / "input.npy"
                        hidden_np = np.load(hp).astype(np.float32)
                        hidden = torch.tensor(hidden_np.tolist(), dtype=dtype).unsqueeze(0)
                        t0 = time.time()
                        position_embeddings = model.model.rotary_emb(hidden, pos)
                        layer_out = model.model.layers[-1](
                            hidden,
                            attention_mask=None,
                            position_ids=pos,
                            past_key_value=None,
                            output_attentions=False,
                            use_cache=False,
                            cache_position=cache_position,
                            position_embeddings=position_embeddings,
                        )[0]
                        normed = model.model.norm(layer_out)
                        logits_t = model.lm_head(normed[:, -1:, :])[0, -1]
                        logits = tensor_to_numpy_1d(logits_t)
                        lp = out_root / "hf_isolated_final_segment_v8" / cid / variant / "layer27_norm_lmhead_logits.npy"
                        lp.parent.mkdir(parents=True, exist_ok=True)
                        np.save(lp, logits)
                        meta = {
                            "case_id": cid,
                            "variant": variant,
                            "boundary_hypothesis": "seg27_28 == final_decoder_layer_27 + final_rmsnorm + lm_head",
                            "input_hidden_path": str(hp),
                            "input_hidden_stats": array_stats(hidden_np),
                            "dtype": args.dtype,
                            "logits_path": str(lp),
                            "logits_sha256": sha256_file(lp),
                            "logits_stats": array_stats(logits),
                            "top10": topk(logits, 10),
                            "elapsed_seconds": round(time.time() - t0, 3),
                        }
                        write_json(lp.with_name("metadata.json"), meta)
                        report["isolated_final_rows"].append(meta)
        report["status"] = "pass"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(Path(args.report_json), report)
    lines = [
        "# HF Full and Isolated Final v8",
        "",
        f"- status: `{report.get('status')}`",
        f"- full_forward_rows: `{len(report.get('full_forward_rows', []))}`",
        f"- isolated_final_rows: `{len(report.get('isolated_final_rows', []))}`",
        f"- errors: `{len(report.get('errors', []))}`",
    ]
    if report.get("errors"):
        lines.append(f"- first_error: `{report['errors'][0]}`")
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.report_json)
    return 0 if report.get("full_forward_rows") or report.get("isolated_final_rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
