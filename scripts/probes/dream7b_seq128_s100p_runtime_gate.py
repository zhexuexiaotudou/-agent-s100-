#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from hbm_runtime import HB_HBMRuntime


def json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def final_suffix(index: int, final_logits_mode: str) -> str:
    return "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""


def lm_head_suffix(index: int, w_bits: int, lm_head_w_bits: int) -> str:
    return f"_lmheadq{lm_head_w_bits}" if index == 27 and lm_head_w_bits != w_bits else ""


def hbm_path(args: argparse.Namespace, index: int) -> Path:
    end = index + 1
    if args.batch_size == 1 and args.artifact_mode == "segmented":
        name = (
            f"dream7b_segment_{index}_{end}_seq{args.seq_len}_q{args.w_bits}"
            f"{lm_head_suffix(index, args.w_bits, args.lm_head_w_bits)}"
            f"{final_suffix(index, args.final_logits_mode)}.hbm"
        )
    else:
        name = (
            f"dream7b_segment_{index}_{end}_seq{args.seq_len}_b{args.batch_size}_q{args.w_bits}"
            f"{lm_head_suffix(index, args.w_bits, args.lm_head_w_bits)}"
            f"{final_suffix(index, args.final_logits_mode)}.hbm"
        )
    return Path(args.hbm_root) / f"seg{index:02d}_{end:02d}" / name


def model_name(args: argparse.Namespace, index: int) -> str:
    end = index + 1
    suffix = final_suffix(index, args.final_logits_mode)
    if args.batch_size == 1 and args.artifact_mode == "segmented":
        return f"dream_segment_{index:02d}_{end:02d}{suffix}"
    return f"dream_batch_segment_{index:02d}_{end:02d}_b{args.batch_size}{suffix}"


def first_quant_scale(runtime: HB_HBMRuntime, name: str) -> float | None:
    try:
        scale = np.asarray(runtime.output_quants[name]["_output_0"].scale).reshape(-1)
    except Exception:
        return None
    return float(scale[0]) if scale.size else None


def position_ids(args: argparse.Namespace) -> np.ndarray:
    if args.batch_size == 1 and args.artifact_mode == "segmented":
        return np.arange(args.seq_len, dtype=np.int32)
    return np.tile(np.arange(args.seq_len, dtype=np.int32), (args.batch_size, 1))


def zero_inputs(args: argparse.Namespace, index: int, hidden: np.ndarray | None = None) -> tuple[dict[str, np.ndarray], dict[str, list[int]]]:
    pos = position_ids(args)
    if index == 0:
        tokens = np.zeros((1, args.seq_len), dtype=np.int32) if args.batch_size == 1 and args.artifact_mode == "segmented" else np.zeros((args.batch_size, args.seq_len), dtype=np.int32)
        inputs = {"_input_0": tokens, "_input_1": pos}
    else:
        if hidden is None:
            hidden = (
                np.zeros((args.seq_len, args.hidden_size), dtype=np.float32)
                if args.batch_size == 1 and args.artifact_mode == "segmented"
                else np.zeros((args.batch_size, args.seq_len, args.hidden_size), dtype=np.float32)
            )
        inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": pos}
    return inputs, {key: list(value.shape) for key, value in inputs.items()}


def expected_shape(args: argparse.Namespace, index: int) -> list[int]:
    if index == args.layer_count - 1:
        if args.final_logits_mode == "last-token":
            return [1, args.vocab_size] if args.batch_size == 1 and args.artifact_mode == "segmented" else [args.batch_size, 1, args.vocab_size]
        return [args.seq_len, args.vocab_size] if args.batch_size == 1 and args.artifact_mode == "segmented" else [args.batch_size, args.seq_len, args.vocab_size]
    return [args.seq_len, args.hidden_size] if args.batch_size == 1 and args.artifact_mode == "segmented" else [args.batch_size, args.seq_len, args.hidden_size]


def run_segment(args: argparse.Namespace, index: int, hidden: np.ndarray | None = None) -> tuple[dict[str, Any], np.ndarray | None, list[str]]:
    errors: list[str] = []
    path = hbm_path(args, index)
    name = model_name(args, index)
    if not path.is_file():
        return (
            {
                "index": index,
                "model_name": name,
                "hbm_path": str(path),
                "error": "hbm_missing",
            },
            hidden,
            [f"hbm_missing:{path}"],
        )

    load_start = time.perf_counter()
    runtime = HB_HBMRuntime(str(path))
    load_end = time.perf_counter()
    model_names = list(getattr(runtime, "model_names", []))
    if name not in model_names:
        errors.append(f"missing_model_name:{name}:available={model_names}")

    inputs, input_shapes = zero_inputs(args, index, hidden)
    output = None
    run_times_ms: list[float] = []
    for repeat_index in range(args.repeat):
        run_start = time.perf_counter()
        output = runtime.run(inputs, model_name=name)
        run_end = time.perf_counter()
        run_times_ms.append((run_end - run_start) * 1000)
        if repeat_index + 1 < args.repeat:
            del output
            gc.collect()
    if output is None:
        raise RuntimeError(f"no output from {name}")
    arr = output[name]["_output_0"]
    scale = first_quant_scale(runtime, name)
    actual_shape = [int(dim) for dim in arr.shape]
    expected = expected_shape(args, index)
    if actual_shape != expected:
        errors.append(f"shape_mismatch:{name}:expected={expected}:actual={actual_shape}")

    row = {
        "index": index,
        "model_name": name,
        "hbm_path": str(path),
        "model_names": model_names,
        "input_shapes": input_shapes,
        "output_shape": actual_shape,
        "expected_shape": expected,
        "output_dtype": str(arr.dtype),
        "output_quant_scale": scale,
        "load_ms": round((load_end - load_start) * 1000, 3),
        "run_ms": round(run_times_ms[-1], 3),
        "repeat_run_ms": [round(item, 3) for item in run_times_ms],
        "hbm_size_bytes": path.stat().st_size,
    }

    next_hidden: np.ndarray | None = hidden
    if index != args.layer_count - 1:
        next_hidden = arr.astype(np.float32, copy=False) * scale if scale is not None else arr.astype(np.float32, copy=True)
    del output
    del runtime
    gc.collect()
    return row, next_hidden, errors


def parse_segments(text: str) -> list[int]:
    return [int(part.strip()) for part in text.split(",") if part.strip()]


def contains_resource_exhausted(errors: list[str]) -> bool:
    return any("RESOURCE_EXHAUSTED" in item or "Cannot allocate memory" in item or "ION_ALLOCATOR" in item for item in errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated seq128 Dream7B HBM load/run gates on S100P.")
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--report-root", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--artifact-mode", choices=["segmented", "batch"], default="segmented")
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--layer-count", type=int, default=28)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", choices=["full", "last-token"], default="last-token")
    parser.add_argument("--representative-segments", default="0,5,27")
    parser.add_argument("--run-full-chain", action="store_true")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.report_root) / f"dream7b_seq128_s100p_runtime_gate_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    representative_errors: list[str] = []
    full_errors: list[str] = []
    representative_rows: list[dict[str, Any]] = []
    full_rows: list[dict[str, Any]] = []
    final_shape: list[int] | None = None

    print("runtime", HB_HBMRuntime.version, flush=True)
    print("hbm_root", args.hbm_root, flush=True)

    for index in parse_segments(args.representative_segments):
        try:
            row, _hidden, row_errors = run_segment(args, index, None)
            representative_rows.append(row)
            representative_errors.extend(row_errors)
            print(json.dumps({"representative": row}, ensure_ascii=False, default=json_default), flush=True)
        except Exception as exc:
            message = f"representative_exception:seg{index:02d}:{type(exc).__name__}:{exc}"
            representative_errors.append(message)
            representative_rows.append({"index": index, "error": message})

    full_chain_attempted = bool(args.run_full_chain)
    if args.run_full_chain and not representative_errors:
        hidden: np.ndarray | None = None
        for index in range(args.layer_count):
            try:
                row, hidden, row_errors = run_segment(args, index, hidden)
                full_rows.append(row)
                full_errors.extend(row_errors)
                if index == args.layer_count - 1:
                    final_shape = row.get("output_shape")
                print(json.dumps({"full_chain": row}, ensure_ascii=False, default=json_default), flush=True)
                if row_errors:
                    break
            except Exception as exc:
                message = f"full_chain_exception:seg{index:02d}:{type(exc).__name__}:{exc}"
                full_errors.append(message)
                full_rows.append({"index": index, "error": message})
                break
    elif args.run_full_chain and representative_errors:
        full_errors.append("full_chain_skipped_because_representative_gate_failed")

    representative_pass = bool(representative_rows) and not any(row.get("error") for row in representative_rows) and not representative_errors
    full_pass = (not full_chain_attempted) or (len(full_rows) == args.layer_count and final_shape == expected_shape(args, args.layer_count - 1) and not full_errors)
    errors = representative_errors + full_errors
    verdict = "ok_dream7b_seq128_s100p_runtime_gate" if representative_pass and full_pass else "failed_dream7b_seq128_s100p_runtime_gate"
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "runtime_version": getattr(HB_HBMRuntime, "version", None),
        "hbm_root": str(args.hbm_root),
        "seq_len": args.seq_len,
        "batch_size": args.batch_size,
        "artifact_mode": args.artifact_mode,
        "final_logits_mode": args.final_logits_mode,
        "lm_head_w_bits": args.lm_head_w_bits,
        "representative_segments": parse_segments(args.representative_segments),
        "gate_results": {
            "representative_segments": {
                "pass": representative_pass,
                "executed_count": len(representative_rows),
            },
            "full_chain": {
                "attempted": full_chain_attempted,
                "pass": full_pass if full_chain_attempted else None,
                "executed_count": len(full_rows),
                "final_shape": final_shape,
            },
        },
        "timing": {
            "representative_total_load_ms": round(sum(float(row.get("load_ms") or 0.0) for row in representative_rows), 3),
            "representative_total_run_ms": round(sum(float(row.get("run_ms") or 0.0) for row in representative_rows), 3),
            "full_chain_total_load_ms": round(sum(float(row.get("load_ms") or 0.0) for row in full_rows), 3),
            "full_chain_total_run_ms": round(sum(float(row.get("run_ms") or 0.0) for row in full_rows), 3),
            "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        },
        "representative_rows": representative_rows,
        "full_chain_rows": full_rows,
        "errors": errors,
        "representative_errors": representative_errors,
        "full_chain_errors": full_errors,
        "resource_exhausted_observed": contains_resource_exhausted(errors),
    }
    report_json = run_dir / "seq128_s100p_runtime_gate.json"
    report_md = run_dir / "seq128_s100p_runtime_gate.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B Seq128 S100P Runtime Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- hbm_root: `{payload['hbm_root']}`",
        f"- representative_pass: `{payload['gate_results']['representative_segments']['pass']}`",
        f"- full_chain_attempted: `{payload['gate_results']['full_chain']['attempted']}`",
        f"- full_chain_pass: `{payload['gate_results']['full_chain']['pass']}`",
        f"- resource_exhausted_observed: `{payload['resource_exhausted_observed']}`",
        f"- wall_ms: `{payload['timing']['wall_ms']}`",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors)
    if not errors:
        lines.append("- none")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_json, flush=True)
    print(report_md, flush=True)
    return 0 if verdict.startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
