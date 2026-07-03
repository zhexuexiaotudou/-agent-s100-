#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from dream7b_seq128_s100p_runtime_gate import (
    expected_shape,
    hbm_path,
    model_name,
    position_ids,
    first_quant_scale,
)
from hbm_runtime import HB_HBMRuntime


def json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def token_case(case_id: str, seq_len: int, vocab_size: int) -> list[int]:
    if case_id == "zeros":
        return [0] * seq_len
    if case_id == "ramp":
        return [1 + (i % min(997, vocab_size - 2)) for i in range(seq_len)]
    if case_id == "late_special_mix":
        base = [0] * seq_len
        tail = [151643, 151644, 151645, 151646]
        for offset, value in enumerate(tail, start=seq_len - len(tail)):
            if 0 <= value < vocab_size:
                base[offset] = value
        return base
    raise ValueError(f"unknown case id: {case_id}")


def run_cmd(args: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def read_logits_bin(path: Path) -> np.ndarray:
    with path.open("rb") as handle:
        header = np.fromfile(handle, dtype=np.int32, count=2)
        if header.size != 2:
            raise RuntimeError(f"invalid logits header in {path}")
        n_tokens, n_vocab = int(header[0]), int(header[1])
        data = np.fromfile(handle, dtype=np.float32)
    expected = n_tokens * n_vocab
    if data.size != expected:
        raise RuntimeError(f"invalid logits size in {path}: expected={expected} actual={data.size}")
    return data.reshape(n_tokens, n_vocab)


def topk(values: np.ndarray, k: int = 5) -> list[dict[str, float | int]]:
    indices = np.argpartition(values, -k)[-k:]
    indices = indices[np.argsort(values[indices])[::-1]]
    return [{"token": int(index), "logit": float(values[index])} for index in indices]


def softmax_stats(values: np.ndarray) -> dict[str, float]:
    shifted = values.astype(np.float64) - float(np.max(values))
    exp = np.exp(shifted)
    probs = exp / float(np.sum(exp))
    top1_prob = float(np.max(probs))
    entropy = float(-np.sum(probs * np.log(probs + 1e-300)))
    return {
        "top1_probability": top1_prob,
        "entropy": entropy,
        "normalized_entropy": entropy / math.log(values.size),
    }


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    left = a.astype(np.float64)
    right = b.astype(np.float64)
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denom) if denom else 0.0


def run_gguf_reference(args: argparse.Namespace, tokens: list[int], case_dir: Path) -> tuple[np.ndarray, dict[str, Any]]:
    out_path = case_dir / "gguf_logits.bin"
    cmd = [
        args.dump_logits,
        "-m",
        args.gguf_model,
        "--tokens",
        ",".join(str(item) for item in tokens),
        "-o",
        str(out_path),
        "-t",
        str(args.gguf_threads),
    ]
    started = time.perf_counter()
    result = run_cmd(cmd, timeout=args.gguf_timeout)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if result["returncode"] != 0:
        raise RuntimeError(f"dump-logits failed:{result}")
    logits = read_logits_bin(out_path)
    return logits[-1].astype(np.float32, copy=False), {
        "command": result,
        "elapsed_ms": round(elapsed_ms, 3),
        "logits_bin": str(out_path),
        "shape": list(logits.shape),
    }


def run_bpu_chain(args: argparse.Namespace, tokens: list[int]) -> tuple[np.ndarray, list[dict[str, Any]]]:
    hidden: np.ndarray | None = None
    rows: list[dict[str, Any]] = []
    pos = position_ids(args)
    for index in range(args.layer_count):
        path = hbm_path(args, index)
        name = model_name(args, index)
        if not path.is_file():
            raise FileNotFoundError(path)
        load_start = time.perf_counter()
        runtime = HB_HBMRuntime(str(path))
        load_end = time.perf_counter()
        model_names = list(getattr(runtime, "model_names", []))
        if name not in model_names:
            raise RuntimeError(f"missing model name {name}; available={model_names}")
        if index == 0:
            token_array = np.asarray(tokens, dtype=np.int32).reshape(1, args.seq_len)
            inputs = {"_input_0": token_array, "_input_1": pos}
        else:
            if hidden is None:
                raise RuntimeError(f"missing hidden before segment {index}")
            inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": pos}
        run_start = time.perf_counter()
        output = runtime.run(inputs, model_name=name)
        run_end = time.perf_counter()
        arr = output[name]["_output_0"]
        scale = first_quant_scale(runtime, name)
        actual_shape = [int(dim) for dim in arr.shape]
        expected = expected_shape(args, index)
        if actual_shape != expected:
            raise RuntimeError(f"shape mismatch {name}: expected={expected} actual={actual_shape}")
        rows.append(
            {
                "index": index,
                "model_name": name,
                "hbm_path": str(path),
                "output_shape": actual_shape,
                "output_dtype": str(arr.dtype),
                "output_quant_scale": scale,
                "load_ms": round((load_end - load_start) * 1000, 3),
                "run_ms": round((run_end - run_start) * 1000, 3),
            }
        )
        if index == args.layer_count - 1:
            logits = arr.astype(np.float32, copy=False) * scale if scale is not None else arr.astype(np.float32, copy=True)
        else:
            hidden = arr.astype(np.float32, copy=False) * scale if scale is not None else arr.astype(np.float32, copy=True)
        del output
        del runtime
    return logits.reshape(-1).astype(np.float32, copy=False), rows


def compare_case(args: argparse.Namespace, case_id: str, run_dir: Path) -> dict[str, Any]:
    tokens = token_case(case_id, args.seq_len, args.vocab_size)
    case_dir = run_dir / f"case_{case_id}"
    case_dir.mkdir(parents=True, exist_ok=False)
    (case_dir / "tokens.txt").write_text(",".join(str(item) for item in tokens) + "\n", encoding="utf-8")
    ref_logits, ref_info = run_gguf_reference(args, tokens, case_dir)
    bpu_logits, segment_rows = run_bpu_chain(args, tokens)
    np.save(case_dir / "gguf_last_logits.npy", ref_logits)
    np.save(case_dir / "bpu_last_logits.npy", bpu_logits)

    ref_top = topk(ref_logits, 5)
    bpu_top = topk(bpu_logits, 5)
    ref_top1 = int(ref_top[0]["token"])
    bpu_top1 = int(bpu_top[0]["token"])
    bpu_top5 = {int(item["token"]) for item in bpu_top}
    ref_stats = softmax_stats(ref_logits)
    bpu_stats = softmax_stats(bpu_logits)
    return {
        "case_id": case_id,
        "token_count": len(tokens),
        "reference": ref_info,
        "bpu": {
            "segment_count": len(segment_rows),
            "total_load_ms": round(sum(float(row["load_ms"]) for row in segment_rows), 3),
            "total_run_ms": round(sum(float(row["run_ms"]) for row in segment_rows), 3),
            "segments": segment_rows,
        },
        "metrics": {
            "ref_top1": ref_top1,
            "bpu_top1": bpu_top1,
            "top1_match": ref_top1 == bpu_top1,
            "ref_top1_in_bpu_top5": ref_top1 in bpu_top5,
            "cosine": cosine(ref_logits, bpu_logits),
            "ref_top5": ref_top,
            "bpu_top5": bpu_top,
            "ref_top1_probability": ref_stats["top1_probability"],
            "bpu_top1_probability": bpu_stats["top1_probability"],
            "ref_normalized_entropy": ref_stats["normalized_entropy"],
            "bpu_normalized_entropy": bpu_stats["normalized_entropy"],
        },
        "artifacts": {
            "tokens": str(case_dir / "tokens.txt"),
            "gguf_last_logits_npy": str(case_dir / "gguf_last_logits.npy"),
            "bpu_last_logits_npy": str(case_dir / "bpu_last_logits.npy"),
        },
    }


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(cases: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    metrics = [case["metrics"] for case in cases]
    top1_match_rate = mean([1.0 if item["top1_match"] else 0.0 for item in metrics]) or 0.0
    ref_top1_in_bpu_top5_rate = mean([1.0 if item["ref_top1_in_bpu_top5"] else 0.0 for item in metrics]) or 0.0
    cosine_values = [float(item["cosine"]) for item in metrics]
    bpu_top1_probs = [float(item["bpu_top1_probability"]) for item in metrics]
    bpu_entropy = [float(item["bpu_normalized_entropy"]) for item in metrics]
    errors = []
    if top1_match_rate < args.min_top1_agreement:
        errors.append("top1_agreement_below_threshold")
    if ref_top1_in_bpu_top5_rate < args.min_ref_top1_in_bpu_top5:
        errors.append("ref_top1_in_bpu_top5_below_threshold")
    if (mean(cosine_values) or 0.0) < args.min_mean_cosine:
        errors.append("mean_cosine_below_threshold")
    if min(bpu_top1_probs or [0.0]) < args.min_bpu_top1_probability:
        errors.append("bpu_top1_probability_below_threshold")
    if max(bpu_entropy or [1.0]) > args.max_normalized_entropy:
        errors.append("bpu_entropy_too_uniform")
    return {
        "case_count": len(cases),
        "reference": "gguf_q4km_dump_logits",
        "top1_agreement": top1_match_rate,
        "ref_top1_in_bpu_top5": ref_top1_in_bpu_top5_rate,
        "mean_cosine": mean(cosine_values),
        "min_cosine": min(cosine_values) if cosine_values else None,
        "mean_bpu_top1_probability": mean(bpu_top1_probs),
        "min_bpu_top1_probability": min(bpu_top1_probs) if bpu_top1_probs else None,
        "max_bpu_normalized_entropy": max(bpu_entropy) if bpu_entropy else None,
        "errors": errors,
        "thresholds": {
            "min_top1_agreement": args.min_top1_agreement,
            "min_ref_top1_in_bpu_top5": args.min_ref_top1_in_bpu_top5,
            "min_mean_cosine": args.min_mean_cosine,
            "min_bpu_top1_probability": args.min_bpu_top1_probability,
            "max_normalized_entropy": args.max_normalized_entropy,
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B Seq128 Logits Reference Compare",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- reference: `{summary['reference']}`",
        f"- case_count: `{summary['case_count']}`",
        f"- top1_agreement: `{summary['top1_agreement']}`",
        f"- ref_top1_in_bpu_top5: `{summary['ref_top1_in_bpu_top5']}`",
        f"- mean_cosine: `{summary['mean_cosine']}`",
        f"- min_bpu_top1_probability: `{summary['min_bpu_top1_probability']}`",
        f"- max_bpu_normalized_entropy: `{summary['max_bpu_normalized_entropy']}`",
        "",
        "## Cases",
        "",
        "| case | ref_top1 | bpu_top1 | top1_match | ref_top1_in_bpu_top5 | cosine | bpu_top1_prob | bpu_entropy |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for case in payload["cases"]:
        metrics = case["metrics"]
        lines.append(
            f"| `{case['case_id']}` | {metrics['ref_top1']} | {metrics['bpu_top1']} | "
            f"{metrics['top1_match']} | {metrics['ref_top1_in_bpu_top5']} | "
            f"{metrics['cosine']:.6f} | {metrics['bpu_top1_probability']:.6f} | "
            f"{metrics['bpu_normalized_entropy']:.6f} |"
        )
    lines.extend(["", "## Errors", ""])
    if summary["errors"]:
        lines.extend(f"- `{item}`" for item in summary["errors"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This compares seq128 BPU HBM against the local GGUF q4km dump-logits reference, not BF16.",
            "- Passing this gate would support continuing to generation quality; failing it blocks product promotion but does not alone prove the HBM graph is mathematically wrong versus BF16.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare seq128 BPU last-token logits against GGUF dump-logits reference.")
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--gguf-model", default="/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf")
    parser.add_argument("--dump-logits", default="/mnt/nas/openclaw/runtimes/diffuse-cpp/build/dump-logits")
    parser.add_argument("--report-root", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--cases", default="zeros,ramp")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--artifact-mode", choices=["segmented", "batch"], default="segmented")
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--layer-count", type=int, default=28)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", choices=["full", "last-token"], default="last-token")
    parser.add_argument("--gguf-threads", type=int, default=4)
    parser.add_argument("--gguf-timeout", type=int, default=900)
    parser.add_argument("--min-top1-agreement", type=float, default=0.80)
    parser.add_argument("--min-ref-top1-in-bpu-top5", type=float, default=0.95)
    parser.add_argument("--min-mean-cosine", type=float, default=0.95)
    parser.add_argument("--min-bpu-top1-probability", type=float, default=0.05)
    parser.add_argument("--max-normalized-entropy", type=float, default=0.95)
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.report_root) / f"dream7b_seq128_logits_reference_compare_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    for case_id in [item.strip() for item in args.cases.split(",") if item.strip()]:
        try:
            case = compare_case(args, case_id, run_dir)
            cases.append(case)
            print(json.dumps({"case": case_id, "metrics": case["metrics"]}, ensure_ascii=False, default=json_default), flush=True)
        except Exception as exc:
            errors.append(f"case_exception:{case_id}:{type(exc).__name__}:{exc}")
            break
    summary = summarize(cases, args)
    summary["errors"].extend(errors)
    verdict = "ok_dream7b_seq128_logits_reference_compare" if cases and not summary["errors"] else "blocked_dream7b_seq128_logits_reference_compare"
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "hbm_root": args.hbm_root,
        "gguf_model": args.gguf_model,
        "dump_logits": args.dump_logits,
        "seq_len": args.seq_len,
        "summary": summary,
        "cases": cases,
        "wall_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    out_json = run_dir / "seq128_logits_reference_compare.json"
    out_md = run_dir / "seq128_logits_reference_compare.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    write_markdown(out_md, payload)
    print(out_json)
    print(out_md)
    return 0 if verdict.startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
