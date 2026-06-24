#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import json
import re
import statistics
import subprocess
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


def hbm_path(root: Path, index: int, seq_len: int, batch_size: int, w_bits: int) -> Path:
    end = index + 1
    return root / f"seg{index:02d}_{end:02d}" / f"dream7b_segment_{index}_{end}_seq{seq_len}_b{batch_size}_q{w_bits}.hbm"


def model_name(index: int, batch_size: int) -> str:
    return f"dream_batch_segment_{index:02d}_{index + 1:02d}_b{batch_size}"


def output_scale(runtime: HB_HBMRuntime, name: str) -> float | None:
    try:
        quant = runtime.output_quants[name]["_output_0"]
        scale = np.asarray(quant.scale).reshape(-1)
        if scale.size:
            return float(scale[0])
    except Exception:
        return None
    return None


def parse_bpu_samples(text: str) -> list[float]:
    return [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", text)]


def run_chain(
    loaded: list[dict[str, Any]],
    tokens: np.ndarray,
    position_ids: np.ndarray,
    batch_size: int,
    seq_len: int,
    hidden_size: int,
    vocab_size: int,
    validate: bool,
) -> tuple[dict[str, Any], list[str]]:
    hidden: np.ndarray | None = None
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    chain_start = time.perf_counter()
    final_shape: tuple[int, ...] | None = None
    final_dtype: str | None = None

    for item in loaded:
        index = int(item["index"])
        runtime: HB_HBMRuntime = item["runtime"]
        name = str(item["model_name"])
        scale = item["output_quant_scale"]
        if index == 0:
            inputs = {"_input_0": tokens, "_input_1": position_ids}
            input_shapes = {"_input_0": list(tokens.shape), "_input_1": list(position_ids.shape)}
        else:
            if hidden is None:
                raise RuntimeError(f"missing hidden before segment {index}")
            hidden_input = hidden.astype(np.float32, copy=False)
            inputs = {"_input_0": hidden_input, "_input_1": position_ids}
            input_shapes = {"_input_0": list(hidden_input.shape), "_input_1": list(position_ids.shape)}

        run_start = time.perf_counter()
        out = runtime.run(inputs, model_name=name)
        run_end = time.perf_counter()
        arr = out[name]["_output_0"]
        actual_shape = tuple(int(dim) for dim in arr.shape)
        expected_shape = (
            (batch_size, seq_len, vocab_size)
            if index == len(loaded) - 1
            else (batch_size, seq_len, hidden_size)
        )
        if validate and actual_shape != expected_shape:
            errors.append(f"shape_mismatch:{name}:expected={expected_shape}:actual={actual_shape}")
        rows.append(
            {
                "index": index,
                "model_name": name,
                "input_shapes": input_shapes,
                "output_shape": list(actual_shape),
                "output_dtype": str(arr.dtype),
                "run_ms": round((run_end - run_start) * 1000, 3),
            }
        )
        if index == len(loaded) - 1:
            final_shape = actual_shape
            final_dtype = str(arr.dtype)
        else:
            if scale is None:
                hidden = arr.astype(np.float32, copy=True)
            else:
                hidden = arr.astype(np.float32, copy=False) * float(scale)
        del out

    return (
        {
            "chain_ms": round((time.perf_counter() - chain_start) * 1000, 3),
            "segment_run_ms": rows,
            "final_shape": list(final_shape) if final_shape is not None else None,
            "final_dtype": final_dtype,
        },
        errors,
    )


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
    parser.add_argument("--warmup-iterations", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=128)
    parser.add_argument("--monitor-delay-ms", type=int, default=100)
    parser.add_argument("--monitor-samples", type=int, default=2400)
    args = parser.parse_args()

    hbm_root = Path(args.hbm_root)
    report_root = Path(args.report_root)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = report_root / f"dream7b_true_batch_load_once_telemetry_{stamp}_b{args.batch_size}"
    run_dir.mkdir(parents=True, exist_ok=False)
    monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
    monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"

    errors: list[str] = []
    loaded: list[dict[str, Any]] = []
    tokens = np.zeros((args.batch_size, args.seq_len), dtype=np.int32)
    position_ids = np.tile(np.arange(args.seq_len, dtype=np.int32), (args.batch_size, 1))

    load_start = time.perf_counter()
    try:
        for index in range(args.layer_count):
            path = hbm_path(hbm_root, index, args.seq_len, args.batch_size, args.w_bits)
            name = model_name(index, args.batch_size)
            segment_load_start = time.perf_counter()
            runtime = HB_HBMRuntime(str(path))
            segment_load_ms = (time.perf_counter() - segment_load_start) * 1000
            model_names = list(getattr(runtime, "model_names", []))
            if name not in model_names:
                errors.append(f"missing_model_name:{name}:available={model_names}")
            loaded.append(
                {
                    "index": index,
                    "model_name": name,
                    "hbm_path": str(path),
                    "runtime": runtime,
                    "load_ms": round(segment_load_ms, 3),
                    "model_names": model_names,
                    "output_quant_scale": output_scale(runtime, name),
                }
            )
            print(
                json.dumps(
                    {
                        "event": "loaded",
                        "index": index,
                        "model_name": name,
                        "load_ms": round(segment_load_ms, 3),
                        "hbm_path": str(path),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    except Exception as exc:
        errors.append(f"load_exception:{type(exc).__name__}:{exc}")

    load_ms = (time.perf_counter() - load_start) * 1000
    warmup_rows: list[dict[str, Any]] = []
    measured_rows: list[dict[str, Any]] = []
    monitor_proc: subprocess.Popen[str] | None = None
    runner_start = time.perf_counter()

    try:
        if not errors:
            for iteration in range(args.warmup_iterations):
                row, chain_errors = run_chain(
                    loaded,
                    tokens,
                    position_ids,
                    args.batch_size,
                    args.seq_len,
                    args.hidden_size,
                    args.vocab_size,
                    validate=iteration == 0,
                )
                row["iteration"] = iteration
                warmup_rows.append(row)
                errors.extend(chain_errors)
                gc.collect()

        if not errors:
            with monitor_stdout.open("w", encoding="utf-8") as stdout, monitor_stderr.open("w", encoding="utf-8") as stderr:
                monitor_proc = subprocess.Popen(
                    [
                        "hrt_ucp_monitor",
                        "-b",
                        "-e",
                        "bpu",
                        "-d",
                        str(args.monitor_delay_ms),
                        "-n",
                        str(args.monitor_samples),
                    ],
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                )
                time.sleep(max(0.2, args.monitor_delay_ms / 1000.0 * 2))
                for iteration in range(args.iterations):
                    row, chain_errors = run_chain(
                        loaded,
                        tokens,
                        position_ids,
                        args.batch_size,
                        args.seq_len,
                        args.hidden_size,
                        args.vocab_size,
                        validate=iteration == 0,
                    )
                    row["iteration"] = iteration
                    measured_rows.append(row)
                    errors.extend(chain_errors)
                    if chain_errors:
                        break
    finally:
        if monitor_proc is not None and monitor_proc.poll() is None:
            monitor_proc.terminate()
            try:
                monitor_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                monitor_proc.kill()
                monitor_proc.wait(timeout=5)

    wall_ms = (time.perf_counter() - runner_start) * 1000
    monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.exists() else ""
    samples = parse_bpu_samples(monitor_text)
    nonzero = [item for item in samples if item > 0.0]
    if not samples and not errors:
        errors.append("no_bpu_monitor_samples")

    final_shape = measured_rows[-1]["final_shape"] if measured_rows else (warmup_rows[-1]["final_shape"] if warmup_rows else None)
    if final_shape != [args.batch_size, args.seq_len, args.vocab_size] and not any(item.startswith("shape_mismatch") for item in errors):
        errors.append(f"final_shape={final_shape}")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_true_batch_load_once_telemetry" if not errors else "failed_dream7b_true_batch_load_once_telemetry",
        "runtime_version": getattr(HB_HBMRuntime, "version", None),
        "hbm_root": str(hbm_root),
        "batch_size": args.batch_size,
        "seq_len": args.seq_len,
        "layer_count": args.layer_count,
        "loaded_count": len(loaded),
        "load_ms": round(load_ms, 3),
        "warmup_iterations": args.warmup_iterations,
        "measured_iterations": len(measured_rows),
        "requested_iterations": args.iterations,
        "wall_ms_after_load": round(wall_ms, 3),
        "avg_chain_ms": round(statistics.fmean(row["chain_ms"] for row in measured_rows), 3) if measured_rows else None,
        "min_chain_ms": round(min(row["chain_ms"] for row in measured_rows), 3) if measured_rows else None,
        "max_chain_ms": round(max(row["chain_ms"] for row in measured_rows), 3) if measured_rows else None,
        "final_shape": final_shape,
        "bpu_loading_sample_count": len(samples),
        "nonzero_bpu_loading_sample_count": len(nonzero),
        "avg_bpu_loading": round(statistics.fmean(samples), 3) if samples else 0.0,
        "avg_nonzero_bpu_loading": round(statistics.fmean(nonzero), 3) if nonzero else 0.0,
        "max_bpu_loading": max(samples) if samples else 0.0,
        "load_rows": [{k: v for k, v in item.items() if k != "runtime"} for item in loaded],
        "warmup_rows": warmup_rows,
        "measured_rows_preview": measured_rows[:3] + measured_rows[-3:] if len(measured_rows) > 6 else measured_rows,
        "errors": errors,
    }

    report_json = run_dir / "true_batch_load_once_telemetry.json"
    report_md = run_dir / "true_batch_load_once_telemetry.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B True Batch Load-Once Telemetry",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- loaded_count: {payload['loaded_count']}",
        f"- load_ms: {payload['load_ms']}",
        f"- measured_iterations: {payload['measured_iterations']}",
        f"- avg_chain_ms: {payload['avg_chain_ms']}",
        f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
        f"- avg_nonzero_bpu_loading: {payload['avg_nonzero_bpu_loading']}",
        f"- max_bpu_loading: {payload['max_bpu_loading']}",
        f"- final_shape: {payload['final_shape']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_json, flush=True)
    print(report_md, flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
