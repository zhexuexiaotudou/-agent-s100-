#!/usr/bin/env python3
"""Export v11 HF BF16 repeat truth and all-layer boundaries.

Offline only: no generation loop and no product route interaction.
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


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
SOURCE_FILES = [
    "config.json",
    "configuration_dream.py",
    "modeling_dream.py",
    "generation_utils.py",
    "tokenization_dream.py",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "model.safetensors.index.json",
    "SHA256SUMS",
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
    order = {cid: i for i, cid in enumerate(CASE_IDS)}
    return sorted(rows, key=lambda item: order.get(item.get("case_id", ""), 999))


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def stats(x: np.ndarray) -> dict[str, Any]:
    y = x.reshape(-1)
    return {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "size": int(y.size),
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


def topk(x: np.ndarray, k: int = 10) -> list[int]:
    return np.argsort(x.reshape(-1))[-k:][::-1].astype(int).tolist()


def model_source_hashes(model_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for name in SOURCE_FILES:
        path = model_dir / name
        rows.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "sha256": sha256_file(path) if path.exists() else None,
            }
        )
    return rows


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "sha256": sha256_file(path), "stats": stats(arr)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=4)
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v11_hf_boundaries_repeat",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "model_dir": args.model_dir,
        "cases_path": args.cases,
        "dtype_requested": args.dtype,
        "case_ids": CASE_IDS,
        "source_hashes": [],
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
        model_dir = Path(args.model_dir)
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        report["torch_num_threads"] = torch.get_num_threads()
        report["source_hashes"] = model_source_hashes(model_dir)
        print(f"[v11-hf-boundaries] loading model dtype={args.dtype}", flush=True)
        load_t0 = time.time()
        model = AutoModel.from_pretrained(model_dir, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.eval()
        report["model_load_seconds"] = round(time.time() - load_t0, 3)
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["parameter_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
        report["status"] = "model_loaded"
        write_json(Path(args.report_json), report)

        cases = read_cases(Path(args.cases), set(CASE_IDS))
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                print(f"[v11-hf-boundaries] running case={cid}", flush=True)
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
                    raise RuntimeError("model output has no hidden_states despite output_hidden_states=True")
                case_dir = out_root / "evidence" / "hf_boundaries_v11" / cid
                truth_dir = out_root / "evidence" / "full_truth_repeat_v11" / cid
                boundaries = []
                emb = tensor_to_numpy(hidden_states[0][0])
                boundaries.append({"boundary": "embedding_output", **save_array(case_dir / "embedding_output.npy", emb)})
                for layer_idx in range(28):
                    arr = tensor_to_numpy(hidden_states[layer_idx + 1][0])
                    boundaries.append({"boundary": f"layer_{layer_idx:02d}_output", "layer_index": layer_idx, **save_array(case_dir / f"layer_{layer_idx:02d}_output.npy", arr)})
                final_norm_t = model.model.norm(hidden_states[-1])
                final_norm = tensor_to_numpy(final_norm_t[0])
                boundaries.append({"boundary": "final_norm_output", **save_array(case_dir / "final_norm_output.npy", final_norm)})
                logits_t = getattr(outputs, "logits")[0, -1]
                logits = tensor_to_numpy(logits_t)
                truth = save_array(truth_dir / "repeat_full_truth_logits.npy", logits)
                meta = {
                    "case_id": cid,
                    "truth_row_type": f"HF/PyTorch repeat {args.dtype}",
                    "dtype": args.dtype,
                    "device": "cpu",
                    "seq_len": int(input_ids.shape[1]),
                    "last_token_index": int(case.get("last_token_index", 127)),
                    "vocab_size": int(logits.reshape(-1).shape[0]),
                    "token_ids_sha256": case.get("token_ids_sha256"),
                    "logits": truth,
                    "top10": topk(logits, 10),
                    "elapsed_seconds": round(time.time() - t0, 3),
                }
                write_json(truth_dir / "metadata.json", meta)
                row = {
                    "case_id": cid,
                    "elapsed_seconds": meta["elapsed_seconds"],
                    "hidden_states_count": len(hidden_states),
                    "boundaries": boundaries,
                    "repeat_truth": meta,
                }
                write_json(case_dir / "metadata.json", row)
                report["rows"].append(row)
                report["status"] = "running"
                write_json(Path(args.report_json), report)
                print(f"[v11-hf-boundaries] complete case={cid} seconds={meta['elapsed_seconds']}", flush=True)
        report["status"] = "pass" if len(report["rows"]) == len(CASE_IDS) else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        print(f"[v11-hf-boundaries] ERROR {type(exc).__name__}: {exc}", flush=True)
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(Path(args.report_json), report)
    lines = [
        "# HF Boundaries and Repeat Truth v11",
        "",
        f"- status: `{report.get('status')}`",
        f"- rows: `{len(report.get('rows', []))}`",
        f"- dtype: `{args.dtype}`",
        f"- errors: `{len(report.get('errors', []))}`",
    ]
    if report.get("errors"):
        lines.append(f"- first_error: `{report['errors'][0]}`")
    write_json(Path(args.report_json), report)
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.report_json, flush=True)
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
