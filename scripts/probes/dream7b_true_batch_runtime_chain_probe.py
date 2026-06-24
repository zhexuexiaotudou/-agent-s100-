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


def first_quant_scale(runtime: HB_HBMRuntime, model_name: str) -> float | None:
    try:
        quant = runtime.output_quants[model_name]["_output_0"]
    except Exception:
        return None
    try:
        scale = np.asarray(quant.scale).reshape(-1)
    except Exception:
        return None
    if scale.size == 0:
        return None
    return float(scale[0])


def hbm_path(root: Path, index: int, seq_len: int, batch_size: int, w_bits: int) -> Path:
    end = index + 1
    return root / f"seg{index:02d}_{end:02d}" / f"dream7b_segment_{index}_{end}_seq{seq_len}_b{batch_size}_q{w_bits}.hbm"


def model_name(index: int, batch_size: int) -> str:
    return f"dream_batch_segment_{index:02d}_{index + 1:02d}_b{batch_size}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2")
    parser.add_argument("--report-root", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--layer-count", type=int, default=28)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    hbm_root = Path(args.hbm_root)
    report_root = Path(args.report_root)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = report_root / f"dream7b_true_batch_runtime_chain_{stamp}_b{args.batch_size}"
    run_dir.mkdir(parents=True, exist_ok=False)

    errors: list[str] = []
    segment_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    hidden: np.ndarray | None = None
    final_shape: tuple[int, ...] | None = None
    final_dtype: str | None = None

    tokens = np.zeros((args.batch_size, args.seq_len), dtype=np.int32)
    position_ids = np.tile(np.arange(args.seq_len, dtype=np.int32), (args.batch_size, 1))

    print("runtime", HB_HBMRuntime.version, flush=True)
    print("hbm_root", hbm_root, flush=True)

    try:
        for index in range(args.layer_count):
            path = hbm_path(hbm_root, index, args.seq_len, args.batch_size, args.w_bits)
            name = model_name(index, args.batch_size)
            if not path.exists():
                raise FileNotFoundError(path)

            load_start = time.perf_counter()
            runtime = HB_HBMRuntime(str(path))
            load_end = time.perf_counter()

            model_names = list(getattr(runtime, "model_names", []))
            if name not in model_names:
                errors.append(f"missing_model_name:{name}:available={model_names}")

            if index == 0:
                inputs = {"_input_0": tokens, "_input_1": position_ids}
                input_shapes = {"_input_0": list(tokens.shape), "_input_1": list(position_ids.shape)}
            else:
                if hidden is None:
                    raise RuntimeError(f"missing hidden before segment {index}")
                hidden_input = hidden.astype(np.float32, copy=False)
                inputs = {"_input_0": hidden_input, "_input_1": position_ids}
                input_shapes = {"_input_0": list(hidden_input.shape), "_input_1": list(position_ids.shape)}

            output = None
            run_times_ms = []
            for repeat_index in range(args.repeat):
                run_start = time.perf_counter()
                output = runtime.run(inputs, model_name=name)
                run_end = time.perf_counter()
                run_times_ms.append((run_end - run_start) * 1000)
                if repeat_index + 1 < args.repeat:
                    del output
                    gc.collect()

            if output is None:
                raise RuntimeError(f"no output from segment {index}")
            arr = output[name]["_output_0"]
            scale = first_quant_scale(runtime, name)
            expected_shape = (
                (args.batch_size, args.seq_len, args.vocab_size)
                if index == args.layer_count - 1
                else (args.batch_size, args.seq_len, args.hidden_size)
            )
            actual_shape = tuple(int(dim) for dim in arr.shape)
            if actual_shape != expected_shape:
                errors.append(f"shape_mismatch:{name}:expected={expected_shape}:actual={actual_shape}")

            row = {
                "index": index,
                "model_name": name,
                "hbm_path": str(path),
                "model_names": model_names,
                "input_shapes": input_shapes,
                "output_shape": list(actual_shape),
                "output_dtype": str(arr.dtype),
                "output_quant_scale": scale,
                "load_ms": round((load_end - load_start) * 1000, 3),
                "run_ms": round(run_times_ms[-1], 3),
                "repeat_run_ms": [round(item, 3) for item in run_times_ms],
            }
            segment_rows.append(row)
            print(json.dumps(row, ensure_ascii=False, default=json_default), flush=True)

            if index == args.layer_count - 1:
                final_shape = actual_shape
                final_dtype = str(arr.dtype)
            else:
                if scale is None:
                    hidden = arr.astype(np.float32, copy=True)
                else:
                    hidden = arr.astype(np.float32, copy=False) * scale

            del output
            del runtime
            gc.collect()
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")

    elapsed_ms = (time.perf_counter() - started) * 1000
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_true_batch_runtime_chain" if not errors else "failed_dream7b_true_batch_runtime_chain",
        "runtime_version": getattr(HB_HBMRuntime, "version", None),
        "hbm_root": str(hbm_root),
        "batch_size": args.batch_size,
        "seq_len": args.seq_len,
        "hidden_size": args.hidden_size,
        "vocab_size": args.vocab_size,
        "layer_count": args.layer_count,
        "segment_count_executed": len(segment_rows),
        "final_shape": list(final_shape) if final_shape is not None else None,
        "final_dtype": final_dtype,
        "total_load_ms": round(sum(float(row["load_ms"]) for row in segment_rows), 3),
        "total_run_ms": round(sum(float(row["run_ms"]) for row in segment_rows), 3),
        "wall_ms": round(elapsed_ms, 3),
        "segments": segment_rows,
        "errors": errors,
    }
    report_json = run_dir / "true_batch_runtime_chain.json"
    report_md = run_dir / "true_batch_runtime_chain.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    report_md.write_text(
        "\n".join(
            [
                "# Dream7B True Batch Runtime Chain",
                "",
                f"- generated_at: {payload['generated_at']}",
                f"- verdict: {payload['verdict']}",
                f"- batch_size: {payload['batch_size']}",
                f"- seq_len: {payload['seq_len']}",
                f"- segment_count_executed: {payload['segment_count_executed']}",
                f"- final_shape: {payload['final_shape']}",
                f"- total_load_ms: {payload['total_load_ms']}",
                f"- total_run_ms: {payload['total_run_ms']}",
                f"- wall_ms: {payload['wall_ms']}",
                "",
                "## Errors",
                "",
                *(f"- {item}" for item in errors),
                *(["- none"] if not errors else []),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(report_json, flush=True)
    print(report_md, flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
