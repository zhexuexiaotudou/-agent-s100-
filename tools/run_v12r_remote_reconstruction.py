#!/usr/bin/env python3
"""Offline v12R reconstruction probes for Dream7B/S100P.

Runs on the S100P/NAS research host. It never calls generation APIs and never
touches product routes. The script has two independent matrices:

1. HF-prefix -> BPU single segment -> HF suffix.
2. BPU-prefix boundary -> HF suffix.
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


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
SINGLE_SEGMENTS = [0, 1, 2, 4, 8, 11, 12, 13, 20, 25, 26, 27]
PREFIX_CUTS = [0, 1, 2, 4, 8, 11, 12, 13, 20, 25, 26]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def stats(x: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(x)
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    if arr.size == 0:
        return {"shape": list(arr.shape), "dtype": str(arr.dtype), "size": 0}
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
    s = np.sum(e)
    if not np.isfinite(s) or s == 0:
        return np.full_like(v, 1.0 / v.size)
    return e / s


def entropy(logits: np.ndarray) -> dict[str, float]:
    p = stable_softmax(logits)
    ent = -float(np.sum(p * np.log(p + 1e-300)))
    return {
        "entropy": ent,
        "normalized_entropy": ent / math.log(p.size) if p.size > 1 else 0.0,
        "top1_probability": float(np.max(p)),
    }


def compare(ref: np.ndarray, cand: np.ndarray, topk: int = 5) -> dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {"shape_match": False, "reference_shape": list(r.shape), "candidate_shape": list(c.shape)}
    rt = np.argsort(r)[-topk:][::-1].astype(int)
    ct = np.argsort(c)[-topk:][::-1].astype(int)
    r0 = r - np.mean(r)
    c0 = c - np.mean(c)
    rnorm = np.linalg.norm(r)
    cnorm = np.linalg.norm(c)
    r0norm = np.linalg.norm(r0)
    c0norm = np.linalg.norm(c0)
    return {
        "shape_match": True,
        "reference_top1": int(rt[0]),
        "candidate_top1": int(ct[0]),
        "top1_agreement": bool(rt[0] == ct[0]),
        "reference_top1_in_candidate_top5": bool(rt[0] in ct),
        "top5_overlap": int(len(set(rt.tolist()) & set(ct.tolist()))),
        "cosine": float(np.dot(r, c) / (rnorm * cnorm)) if rnorm and cnorm else None,
        "pearson_centered": float(np.dot(r0, c0) / (r0norm * c0norm)) if r0norm and c0norm else None,
        "relative_l2": float(np.linalg.norm(r - c) / (rnorm + 1e-12)),
        "max_abs_error": float(np.max(np.abs(r - c))),
        "mean_abs_error": float(np.mean(np.abs(r - c))),
        "candidate_normalized_entropy": entropy(c)["normalized_entropy"],
        "candidate_stats": stats(c.astype(np.float32)),
        "reference_stats": stats(r.astype(np.float32)),
    }


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


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


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


def run_bpu_segment(args: argparse.Namespace, segment: int, case: dict[str, Any], input_hidden: np.ndarray | None) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    from hbm_runtime import HB_HBMRuntime

    hbm = hbm_path(Path(args.hbm_root), segment, args.seq_len, args.w_bits, args.lm_head_w_bits, args.final_logits_mode)
    name = model_name(segment, args.final_logits_mode)
    pos_np = np.arange(args.seq_len, dtype=np.int32)
    t0 = time.time()
    runtime = HB_HBMRuntime(str(hbm))
    load_s = time.time() - t0
    if segment == 0:
        inputs = {"_input_0": np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len), "_input_1": pos_np}
        input_contract = {"kind": "token_ids_plus_position_ids", "input_0_shape": [1, args.seq_len], "input_0_dtype": "int32", "input_1_shape": [args.seq_len], "input_1_dtype": "int32"}
    else:
        if input_hidden is None:
            raise RuntimeError(f"missing HF input hidden for segment {segment}")
        inputs = {"_input_0": np.asarray(input_hidden, dtype=np.float32), "_input_1": pos_np}
        input_contract = {"kind": "hidden_plus_position_ids", "input_0_shape": list(np.asarray(input_hidden).shape), "input_0_dtype": "float32", "input_1_shape": [args.seq_len], "input_1_dtype": "int32"}
    t1 = time.time()
    output = runtime.run(inputs, model_name=name)
    run_s = time.time() - t1
    raw = output[name]["_output_0"]
    qmeta = quant_metadata(runtime, name)
    scale = qmeta.get("scale_first")
    dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
    meta = {
        "segment": segment,
        "model_name": name,
        "hbm_path": str(hbm),
        "hbm_sha256": sha256_file(hbm) if hbm.exists() else None,
        "input_contract": input_contract,
        "load_seconds": round(load_s, 3),
        "run_seconds": round(run_s, 3),
        "quant_metadata": qmeta,
        "raw_stats": stats(raw),
        "dequant_stats": stats(dequant),
    }
    del output
    del runtime
    return raw, dequant, meta


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "sha256": sha256_file(path), "stats": stats(arr)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default="/mnt/nas/openclaw/models/dream7b-hf")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--hf-boundary-root", required=True)
    ap.add_argument("--bpu-boundary-root", required=True)
    ap.add_argument("--full-truth-root", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    ap.add_argument("--segments", default=",".join(str(x) for x in SINGLE_SEGMENTS))
    ap.add_argument("--cuts", default=",".join(str(x) for x in PREFIX_CUTS))
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--torch-threads", type=int, default=4)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--w-bits", type=int, default=8)
    ap.add_argument("--lm-head-w-bits", type=int, default=16)
    ap.add_argument("--final-logits-mode", default="last-token")
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    segments = [int(x) for x in args.segments.split(",") if x.strip()]
    cuts = [int(x) for x in args.cuts.split(",") if x.strip()]
    report_path = Path(args.report_json)
    previous = read_json(report_path, {}) if report_path.exists() else {}
    if previous.get("schema_version") == "dream7b_s100p_v12r_remote_reconstruction":
        report = previous
        report.setdefault("single_segment_rows", [])
        report.setdefault("hybrid_prefix_rows", [])
        report.setdefault("errors", [])
        report.setdefault("resume_runs", [])
        report["resume_runs"].append({"started_at_unix": started, "segments": segments, "cuts": cuts})
        report["status"] = "resumed"
    else:
        report = {
            "schema_version": "dream7b_s100p_v12r_remote_reconstruction",
            "started_at_unix": started,
            "python": sys.version,
            "platform": platform.platform(),
            "model_dir": args.model_dir,
            "segments": segments,
            "cuts": cuts,
            "single_segment_rows": [],
            "hybrid_prefix_rows": [],
            "errors": [],
            "resume_runs": [],
            "status": "started",
            "safety": {"generation_quality_run": False, "product_routes_18888_18889_touched": False},
        }
    report["python"] = sys.version
    report["platform"] = platform.platform()
    report["model_dir"] = args.model_dir
    report["segments"] = segments
    report["cuts"] = cuts
    report["safety"] = {"generation_quality_run": False, "product_routes_18888_18889_touched": False}
    write_json(report_path, report)

    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        print(f"[v12r] loading HF model dtype={args.dtype}", flush=True)
        model = AutoModel.from_pretrained(args.model_dir, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.eval()
        pos = torch.arange(args.seq_len, dtype=torch.long).unsqueeze(0)
        cache_position = torch.arange(args.seq_len, dtype=torch.long)
        cases = [c for c in iter_jsonl(Path(args.cases)) if c.get("case_id") in CASE_IDS]
        out_root = Path(args.output_root)
        hf_root = Path(args.hf_boundary_root)
        bpu_root = Path(args.bpu_boundary_root)
        truth_root = Path(args.full_truth_root)
        report["status"] = "model_loaded"
        write_json(report_path, report)

        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                ref = np.load(truth_root / cid / "repeat_full_truth_logits.npy")
                done_single = {(r.get("case_id"), int(r.get("segment"))) for r in report["single_segment_rows"] if r.get("status") == "pass" and r.get("segment") is not None}
                for segment in segments:
                    if (cid, segment) in done_single:
                        print(f"[v12r] skip existing single case={cid} seg={segment:02d}", flush=True)
                        continue
                    print(f"[v12r] single case={cid} seg={segment:02d}", flush=True)
                    t0 = time.time()
                    try:
                        input_hidden = None
                        input_source: dict[str, Any]
                        if segment == 0:
                            input_source = {"kind": "canonical_token_ids", "case_id": cid}
                        else:
                            inp = hf_root / cid / f"layer_{segment-1:02d}_output.npy"
                            input_hidden = np.load(inp).astype(np.float32)
                            input_source = {"kind": "hf_layer_output", "path": str(inp), "sha256": sha256_file(inp)}
                        raw, deq, bmeta = run_bpu_segment(args, segment, case, input_hidden)
                        row_dir = out_root / "evidence" / "single_segment_substitution_v12r" / cid / f"seg_{segment:02d}"
                        raw_info = save_array(row_dir / "bpu_raw_output.npy", raw)
                        deq_info = save_array(row_dir / "bpu_dequant_output.npy", deq)
                        if segment == 27:
                            logits = np.asarray(deq, dtype=np.float32).reshape(-1)
                            suffix_info = {"kind": "bpu_final_segment_logits", "hf_suffix_layers": []}
                        else:
                            logits = run_hf_suffix(model, deq, segment + 1, pos, cache_position, dtype)
                            suffix_info = {"kind": "hf_suffix", "hf_suffix_layers": list(range(segment + 1, 28))}
                        logits_info = save_array(row_dir / "substitution_logits.npy", logits)
                        hf_out = hf_root / cid / f"layer_{segment:02d}_output.npy"
                        boundary_metrics = compare(np.load(hf_out), deq) if hf_out.exists() and segment < 27 else None
                        row = {
                            "case_id": cid,
                            "segment": segment,
                            "input_source": input_source,
                            "layout_scale_variant_used": "direct_float32_seq_hidden_or_token_ids",
                            "bpu": bmeta,
                            "raw_output": raw_info,
                            "dequant_output": deq_info,
                            "suffix": suffix_info,
                            "logits": logits_info,
                            "final_metrics": compare(ref, logits),
                            "boundary_metrics": boundary_metrics,
                            "elapsed_seconds": round(time.time() - t0, 3),
                            "status": "pass",
                        }
                        write_json(row_dir / "metadata.json", row)
                        report["single_segment_rows"].append(row)
                        done_single.add((cid, segment))
                        report["errors"] = [
                            e
                            for e in report["errors"]
                            if not (e.get("matrix") == "single_segment" and e.get("case_id") == cid and e.get("segment") == segment)
                        ]
                    except Exception as exc:
                        err = {"matrix": "single_segment", "case_id": cid, "segment": segment, "type": type(exc).__name__, "message": str(exc)}
                        report["errors"].append(err)
                        print(f"[v12r] ERROR {err}", flush=True)
                    report["status"] = "running"
                    write_json(report_path, report)

                done_hybrid = {(r.get("case_id"), int(r.get("cut"))) for r in report["hybrid_prefix_rows"] if r.get("status") == "pass" and r.get("cut") is not None}
                for cut in cuts:
                    if (cid, cut) in done_hybrid:
                        print(f"[v12r] skip existing hybrid case={cid} cut={cut:02d}", flush=True)
                        continue
                    print(f"[v12r] hybrid case={cid} cut={cut:02d}", flush=True)
                    t0 = time.time()
                    try:
                        bp = bpu_root / cid / f"seg_{cut:02d}_output.npy"
                        hidden = np.load(bp).astype(np.float32)
                        if cut == 27:
                            logits = hidden.reshape(-1)
                            suffix_layers: list[int] = []
                        else:
                            logits = run_hf_suffix(model, hidden, cut + 1, pos, cache_position, dtype)
                            suffix_layers = list(range(cut + 1, 28))
                        row_dir = out_root / "evidence" / "hybrid_routes_v12r" / cid / f"cut_{cut:02d}"
                        logits_info = save_array(row_dir / "hybrid_logits.npy", logits)
                        hf_out = hf_root / cid / f"layer_{cut:02d}_output.npy"
                        boundary_metrics = compare(np.load(hf_out), hidden) if hf_out.exists() else None
                        row = {
                            "case_id": cid,
                            "cut": cut,
                            "route": f"BPU segments 0..{cut} then HF/PyTorch CPU suffix {cut+1}..27 + final norm + lm_head",
                            "input_boundary": {"path": str(bp), "sha256": sha256_file(bp), "stats": stats(hidden)},
                            "hf_suffix_layers": suffix_layers,
                            "logits": logits_info,
                            "final_metrics": compare(ref, logits),
                            "boundary_metrics": boundary_metrics,
                            "layout_scale_variant_used": "existing_full_chain_bpu_dequant_boundary_direct_float32_seq_hidden",
                            "elapsed_seconds": round(time.time() - t0, 3),
                            "status": "pass",
                        }
                        write_json(row_dir / "metadata.json", row)
                        report["hybrid_prefix_rows"].append(row)
                        done_hybrid.add((cid, cut))
                        report["errors"] = [
                            e
                            for e in report["errors"]
                            if not (e.get("matrix") == "hybrid_prefix" and e.get("case_id") == cid and e.get("cut") == cut)
                        ]
                    except Exception as exc:
                        err = {"matrix": "hybrid_prefix", "case_id": cid, "cut": cut, "type": type(exc).__name__, "message": str(exc)}
                        report["errors"].append(err)
                        print(f"[v12r] ERROR {err}", flush=True)
                    report["status"] = "running"
                    write_json(report_path, report)

        expected_single = len(cases) * len(segments)
        expected_hybrid = len(cases) * len(cuts)
        report["expected_single_segment_rows"] = expected_single
        report["expected_hybrid_prefix_rows"] = expected_hybrid
        if len(report["single_segment_rows"]) == expected_single and len(report["hybrid_prefix_rows"]) == expected_hybrid:
            report["status"] = "pass" if not report["errors"] else "pass_with_unresolved_errors"
        else:
            report["status"] = "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"matrix": "setup", "type": type(exc).__name__, "message": str(exc)})
        print(f"[v12r] SETUP ERROR {type(exc).__name__}: {exc}", flush=True)

    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(report_path, report)
    lines = [
        "# v12R Remote Reconstruction",
        "",
        f"- status: `{report.get('status')}`",
        f"- single_segment_rows: `{len(report.get('single_segment_rows', []))}`",
        f"- hybrid_prefix_rows: `{len(report.get('hybrid_prefix_rows', []))}`",
        f"- errors: `{len(report.get('errors', []))}`",
        f"- generation_quality_run: `{report['safety']['generation_quality_run']}`",
        f"- product_routes_18888_18889_touched: `{report['safety']['product_routes_18888_18889_touched']}`",
    ]
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.report_json, flush=True)
    return 0 if report.get("single_segment_rows") or report.get("hybrid_prefix_rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
