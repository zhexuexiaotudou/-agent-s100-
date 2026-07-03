#!/usr/bin/env python3
"""Export Dream7B full-reference last-token logits for canonical seq128 cases.

This is an offline reference exporter. It runs no generation loop and does not
touch product routes.
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
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("case_id") in wanted:
            rows.append(item)
    order = {cid: i for i, cid in enumerate(DEFAULT_CASES)}
    return sorted(rows, key=lambda x: order.get(x.get("case_id", ""), 999))


def array_stats(x: np.ndarray) -> dict[str, Any]:
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


def tensor_to_numpy_1d(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def model_hashes(model_dir: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"model_dir": str(model_dir), "files": []}
    for name in ["SHA256SUMS", "config.json", "model.safetensors.index.json", "tokenizer_config.json", "vocab.json", "merges.txt", "tokenization_dream.py"]:
        path = model_dir / name
        if path.exists():
            out["files"].append({"name": name, "path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--case-ids", default=",".join(DEFAULT_CASES))
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=4)
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v10_full_truth_reference",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "model_dir": args.model_dir,
        "cases_path": args.cases,
        "requested_case_ids": [x for x in args.case_ids.split(",") if x],
        "dtype_requested": args.dtype,
        "torch_threads_requested": args.torch_threads,
        "full_truth_rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(Path(args.report_json), report)
    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        report["runtime_versions"] = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "numpy": np.__version__,
        }
        report["torch_num_threads"] = torch.get_num_threads()
        report["model_hashes"] = model_hashes(Path(args.model_dir))
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        print(f"[v10-full-truth] loading model {args.model_dir} dtype={args.dtype}", flush=True)
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
        report["status"] = "model_loaded"
        write_json(Path(args.report_json), report)
        cases = read_cases(Path(args.cases), set(report["requested_case_ids"]))
        out_root = Path(args.output_root)
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                print(f"[v10-full-truth] running case={cid}", flush=True)
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
                    "num_logits_to_keep": 1,
                }
                try:
                    out = model(**kwargs)
                except TypeError:
                    kwargs.pop("num_logits_to_keep", None)
                    out = model(**kwargs)
                logits_t = out.logits[0, -1]
                logits = tensor_to_numpy_1d(logits_t)
                case_dir = out_root / "evidence" / "full_truth_v10" / cid
                case_dir.mkdir(parents=True, exist_ok=True)
                logits_path = case_dir / "full_truth_logits.npy"
                np.save(logits_path, logits)
                meta = {
                    "case_id": cid,
                    "truth_row_type": f"HF/PyTorch {args.dtype}",
                    "dtype": args.dtype,
                    "device": "cpu",
                    "seq_len": int(input_ids.shape[1]),
                    "last_token_index": int(case.get("last_token_index", case.get("expected_last_token_index", input_ids.shape[1] - 1))),
                    "vocab_size": int(logits.reshape(-1).shape[0]),
                    "token_ids_sha256": case.get("token_ids_sha256"),
                    "tokenizer_manifest_sha256": case.get("tokenizer_manifest_sha256"),
                    "model_hashes": report["model_hashes"],
                    "logits_path": str(logits_path),
                    "logits_sha256": sha256_file(logits_path),
                    "logits_stats": array_stats(logits),
                    "top10": topk(logits, 10),
                    "elapsed_seconds": round(time.time() - t0, 3),
                }
                write_json(case_dir / "metadata.json", meta)
                report["full_truth_rows"].append(meta)
                report["status"] = "running"
                write_json(Path(args.report_json), report)
                print(f"[v10-full-truth] complete case={cid} seconds={meta['elapsed_seconds']}", flush=True)
        report["status"] = "pass" if len(report["full_truth_rows"]) == len(report["requested_case_ids"]) else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        print(f"[v10-full-truth] ERROR {type(exc).__name__}: {exc}", flush=True)
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(Path(args.report_json), report)
    lines = [
        "# Full Truth Reference v10",
        "",
        f"- status: `{report.get('status')}`",
        f"- full_truth_rows: `{len(report.get('full_truth_rows', []))}`",
        f"- dtype: `{args.dtype}`",
        f"- errors: `{len(report.get('errors', []))}`",
    ]
    if report.get("errors"):
        lines.append(f"- first_error: `{report['errors'][0]}`")
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.report_json, flush=True)
    return 0 if len(report.get("full_truth_rows", [])) == len(report["requested_case_ids"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
