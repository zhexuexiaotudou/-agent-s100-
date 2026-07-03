#!/usr/bin/env python3
"""Run HF suffixes from selected BPU boundary hidden states.

Offline only. Inputs are dequantized BPU boundary tensors; outputs are logits
for comparison with full BF16 truth.
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
BOUNDARIES = [8, 11, 12, 13, 20, 26]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--boundary-root", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=4)
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v11_hf_suffix_route",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "model_dir": args.model_dir,
        "boundary_root": args.boundary_root,
        "dtype_requested": args.dtype,
        "boundaries": BOUNDARIES,
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
        print(f"[v11-suffix] loading model dtype={args.dtype}", flush=True)
        model = AutoModel.from_pretrained(args.model_dir, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.eval()
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["status"] = "model_loaded"
        write_json(Path(args.report_json), report)
        pos = torch.arange(128, dtype=torch.long).unsqueeze(0)
        cache_position = torch.arange(128, dtype=torch.long)
        out_root = Path(args.output_root)
        boundary_root = Path(args.boundary_root)
        with torch.no_grad():
            for cid in CASE_IDS:
                for boundary in BOUNDARIES:
                    hp = boundary_root / cid / f"seg_{boundary:02d}_output.npy"
                    if not hp.exists():
                        report["errors"].append({"type": "MissingBoundary", "message": str(hp)})
                        continue
                    print(f"[v11-suffix] case={cid} boundary=seg{boundary:02d}", flush=True)
                    t0 = time.time()
                    hidden_np = np.load(hp).astype(np.float32)
                    hidden = torch.tensor(hidden_np.tolist(), dtype=dtype).unsqueeze(0)
                    position_embeddings = model.model.rotary_emb(hidden, pos)
                    for layer_idx in range(boundary + 1, 28):
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
                    logits = tensor_to_numpy(logits_t)
                    row_dir = out_root / "evidence" / "hf_suffix_route_v11" / cid / f"seg_{boundary:02d}_to_logits"
                    row_dir.mkdir(parents=True, exist_ok=True)
                    lp = row_dir / "suffix_logits.npy"
                    np.save(lp, logits)
                    meta = {
                        "case_id": cid,
                        "bpu_boundary_segment": boundary,
                        "hf_suffix_layers": list(range(boundary + 1, 28)),
                        "input_hidden_path": str(hp),
                        "input_hidden_sha256": sha256_file(hp),
                        "input_hidden_stats": stats(hidden_np),
                        "logits_path": str(lp),
                        "logits_sha256": sha256_file(lp),
                        "logits_stats": stats(logits),
                        "top10": topk(logits, 10),
                        "elapsed_seconds": round(time.time() - t0, 3),
                    }
                    write_json(row_dir / "metadata.json", meta)
                    report["rows"].append(meta)
                    report["status"] = "running"
                    write_json(Path(args.report_json), report)
        report["status"] = "pass" if len(report["rows"]) == len(CASE_IDS) * len(BOUNDARIES) else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        print(f"[v11-suffix] ERROR {type(exc).__name__}: {exc}", flush=True)
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(Path(args.report_json), report)
    lines = [
        "# HF Suffix Route v11",
        "",
        f"- status: `{report.get('status')}`",
        f"- rows: `{len(report.get('rows', []))}`",
        f"- errors: `{len(report.get('errors', []))}`",
    ]
    if report.get("errors"):
        lines.append(f"- first_error: `{report['errors'][0]}`")
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.report_json, flush=True)
    return 0 if report.get("rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
