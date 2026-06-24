#!/usr/bin/env python3
import argparse
import gc
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from hbm_runtime import HB_HBMRuntime


SEGMENTS6 = [
    ("seg00_04", "base", "dream7b_segment_0_4_seq16_q8.hbm", "dream_segment_00_04", "tokens"),
    ("seg04_07", "base", "dream7b_segment_4_7_seq16_q8.hbm", "dream_segment_04_07", "hidden"),
    ("seg07_14", "base", "dream7b_segment_7_14_seq16_q8.hbm", "dream_segment_07_14", "hidden"),
    ("seg14_21", "base", "dream7b_segment_14_21_seq16_q8.hbm", "dream_segment_14_21", "hidden"),
    ("seg21_24", "base", "dream7b_segment_21_24_seq16_q8.hbm", "dream_segment_21_24", "hidden"),
    ("seg24_28", "base", "dream7b_segment_24_28_seq16_q8.hbm", "dream_segment_24_28", "hidden"),
]

FINE_ADJACENT_SEGMENTS = [
    ("seg00_02", "fine", "seg00_02/dream7b_segment_0_2_seq16_q8.hbm", "dream_segment_00_02", "tokens"),
    ("seg02_04", "fine", "seg02_04/dream7b_segment_2_4_seq16_q8.hbm", "dream_segment_02_04", "hidden"),
    ("seg04_07", "base", "dream7b_segment_4_7_seq16_q8.hbm", "dream_segment_04_07", "hidden"),
    ("seg07_10", "fine", "seg07_10/dream7b_segment_7_10_seq16_q8.hbm", "dream_segment_07_10", "hidden"),
    ("seg10_14", "fine", "seg10_14/dream7b_segment_10_14_seq16_q8.hbm", "dream_segment_10_14", "hidden"),
    ("seg14_17", "fine", "seg14_17/dream7b_segment_14_17_seq16_q8.hbm", "dream_segment_14_17", "hidden"),
    ("seg17_21", "fine", "seg17_21/dream7b_segment_17_21_seq16_q8.hbm", "dream_segment_17_21", "hidden"),
    ("seg21_24", "base", "dream7b_segment_21_24_seq16_q8.hbm", "dream_segment_21_24", "hidden"),
    ("seg24_26", "fine", "seg24_26/dream7b_segment_24_26_seq16_q8.hbm", "dream_segment_24_26", "hidden"),
    ("seg26_28", "fine", "seg26_28/dream7b_segment_26_28_seq16_q8.hbm", "dream_segment_26_28", "hidden"),
]

RESPLIT_ADJACENT_SEGMENTS = [
    ("seg00_01", "resplit", "seg00_01/dream7b_segment_0_1_seq16_q8.hbm", "dream_segment_00_01", "tokens"),
    ("seg01_02", "resplit", "seg01_02/dream7b_segment_1_2_seq16_q8.hbm", "dream_segment_01_02", "hidden"),
    ("seg02_04", "fine", "seg02_04/dream7b_segment_2_4_seq16_q8.hbm", "dream_segment_02_04", "hidden"),
    ("seg04_07", "base", "dream7b_segment_4_7_seq16_q8.hbm", "dream_segment_04_07", "hidden"),
    ("seg07_10", "fine", "seg07_10/dream7b_segment_7_10_seq16_q8.hbm", "dream_segment_07_10", "hidden"),
    ("seg10_12", "resplit", "seg10_12/dream7b_segment_10_12_seq16_q8.hbm", "dream_segment_10_12", "hidden"),
    ("seg12_14", "resplit", "seg12_14/dream7b_segment_12_14_seq16_q8.hbm", "dream_segment_12_14", "hidden"),
    ("seg14_17", "fine", "seg14_17/dream7b_segment_14_17_seq16_q8.hbm", "dream_segment_14_17", "hidden"),
    ("seg17_19", "resplit", "seg17_19/dream7b_segment_17_19_seq16_q8.hbm", "dream_segment_17_19", "hidden"),
    ("seg19_21", "resplit", "seg19_21/dream7b_segment_19_21_seq16_q8.hbm", "dream_segment_19_21", "hidden"),
    ("seg21_24", "base", "dream7b_segment_21_24_seq16_q8.hbm", "dream_segment_21_24", "hidden"),
    ("seg24_26", "fine", "seg24_26/dream7b_segment_24_26_seq16_q8.hbm", "dream_segment_24_26", "hidden"),
    ("seg26_27", "resplit", "seg26_27/dream7b_segment_26_27_seq16_q8.hbm", "dream_segment_26_27", "hidden"),
    ("seg27_28", "resplit", "seg27_28/dream7b_segment_27_28_seq16_q8.hbm", "dream_segment_27_28", "hidden"),
]

RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS = [
    ("seg00_01", "resplit", "seg00_01/dream7b_segment_0_1_seq16_q8.hbm", "dream_segment_00_01", "tokens"),
    ("seg01_02", "resplit", "seg01_02/dream7b_segment_1_2_seq16_q8.hbm", "dream_segment_01_02", "hidden"),
    ("seg02_04", "fine", "seg02_04/dream7b_segment_2_4_seq16_q8.hbm", "dream_segment_02_04", "hidden"),
    ("seg04_07", "base", "dream7b_segment_4_7_seq16_q8.hbm", "dream_segment_04_07", "hidden"),
    ("seg07_08", "topwindow", "seg07_08/dream7b_segment_7_8_seq16_q8.hbm", "dream_segment_07_08", "hidden"),
    ("seg08_10", "topwindow", "seg08_10/dream7b_segment_8_10_seq16_q8.hbm", "dream_segment_08_10", "hidden"),
    ("seg10_12", "resplit", "seg10_12/dream7b_segment_10_12_seq16_q8.hbm", "dream_segment_10_12", "hidden"),
    ("seg12_14", "resplit", "seg12_14/dream7b_segment_12_14_seq16_q8.hbm", "dream_segment_12_14", "hidden"),
    ("seg14_17", "fine", "seg14_17/dream7b_segment_14_17_seq16_q8.hbm", "dream_segment_14_17", "hidden"),
    ("seg17_19", "resplit", "seg17_19/dream7b_segment_17_19_seq16_q8.hbm", "dream_segment_17_19", "hidden"),
    ("seg19_21", "resplit", "seg19_21/dream7b_segment_19_21_seq16_q8.hbm", "dream_segment_19_21", "hidden"),
    ("seg21_22", "topwindow", "seg21_22/dream7b_segment_21_22_seq16_q8.hbm", "dream_segment_21_22", "hidden"),
    ("seg22_24", "topwindow", "seg22_24/dream7b_segment_22_24_seq16_q8.hbm", "dream_segment_22_24", "hidden"),
    ("seg24_26", "fine", "seg24_26/dream7b_segment_24_26_seq16_q8.hbm", "dream_segment_24_26", "hidden"),
    ("seg26_27", "resplit", "seg26_27/dream7b_segment_26_27_seq16_q8.hbm", "dream_segment_26_27", "hidden"),
    ("seg27_28", "resplit", "seg27_28/dream7b_segment_27_28_seq16_q8.hbm", "dream_segment_27_28", "hidden"),
]


WINDOW_CHILD_CODE = r"""
import json
import sys
import time

import numpy as np
from hbm_runtime import HB_HBMRuntime


def first_scale(runtime, model_name, output_name):
    quant = runtime.output_quants[model_name][output_name]
    scale = np.asarray(quant.scale).reshape(-1)
    if scale.size == 0:
        return 1.0
    return float(scale[0])


payload = json.loads(sys.stdin.read())
position_ids = np.load(payload["position_path"])
input_0 = np.load(payload["input_path"])
child_runtime_mode = payload.get("child_runtime_mode", "separate")
runtimes = []
load_events = []
if child_runtime_mode == "packed":
    model_files = [segment["model_file"] for segment in payload["resident_segments"]]
    t0 = time.perf_counter()
    runtime = HB_HBMRuntime(model_files)
    t1 = time.perf_counter()
    load_ms = round((t1 - t0) * 1000, 3)
    runtimes = [runtime for _ in payload["resident_segments"]]
    for index, segment in enumerate(payload["resident_segments"]):
        load_events.append({
            "segment": segment["segment"],
            "model_file": segment["model_file"],
            "load_ms": load_ms if index == 0 else 0.0,
            "packed_load_ms": load_ms,
            "child_runtime_mode": child_runtime_mode,
        })
else:
    for segment in payload["resident_segments"]:
        t0 = time.perf_counter()
        runtime = HB_HBMRuntime(segment["model_file"])
        t1 = time.perf_counter()
        runtimes.append(runtime)
        load_events.append({
            "segment": segment["segment"],
            "model_file": segment["model_file"],
            "load_ms": round((t1 - t0) * 1000, 3),
            "child_runtime_mode": child_runtime_mode,
        })

run_count = int(payload.get("run_count", 1))
results = []
dequantized = input_0
for run_index in range(run_count):
    current = payload["resident_segments"][run_index]
    runtime = runtimes[run_index]
    inputs = {"_input_0": dequantized, "_input_1": position_ids}
    t0 = time.perf_counter()
    output = runtime.run(inputs, model_name=current["model_name"])
    t1 = time.perf_counter()
    output_name = runtime.output_names[current["model_name"]][0]
    arr = output[current["model_name"]][output_name]
    scale = first_scale(runtime, current["model_name"], output_name)
    dequantized = arr.astype(np.float32) * scale
    results.append({
        "segment": current["segment"],
        "source": current["source"],
        "input_kind": current["input_kind"],
        "model_name": current["model_name"],
        "model_file": current["model_file"],
        "output_name": output_name,
        "output_shape": list(arr.shape),
        "output_dtype": str(arr.dtype),
        "output_scale": scale,
        "load_ms": load_events[run_index]["load_ms"],
        "packed_load_ms": load_events[run_index].get("packed_load_ms", 0.0),
        "preload_events": load_events,
        "run_ms": round((t1 - t0) * 1000, 3),
        "resident_segments": [item["segment"] for item in payload["resident_segments"]],
        "resident_count": len(payload["resident_segments"]),
        "child_runtime_mode": child_runtime_mode,
    })
np.save(payload["output_path"], dequantized)
print(json.dumps({
    "segments": results,
    "run_count": run_count,
    "resident_segments": [item["segment"] for item in payload["resident_segments"]],
    "resident_count": len(payload["resident_segments"]),
    "child_runtime_mode": child_runtime_mode,
}, ensure_ascii=False))
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Run Dream 7B seq16 segmented S100 HBM forward.")
    parser.add_argument("--hbm-dir", default="/mnt/nas/openclaw/models/dream7b-hbm/segments6")
    parser.add_argument("--fine-hbm-dir", default="/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16")
    parser.add_argument("--resplit-hbm-dir", default="/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16")
    parser.add_argument("--topwindow-hbm-dir", default="/mnt/nas/openclaw/models/dream7b-hbm/resplit-topwindow-seq16")
    parser.add_argument("--segment-plan", choices=("segments6", "fine-adjacent", "resplit-adjacent", "resplit-topwindow-adjacent"), default="segments6")
    parser.add_argument(
        "--residency-window-size",
        type=int,
        default=1,
        help="Keep this many adjacent HBM runtimes loaded. Use 2 with --segment-plan fine-adjacent.",
    )
    parser.add_argument(
        "--child-window-mode",
        choices=("sliding", "pair"),
        default="sliding",
        help="With residency-window-size > 1, run one segment per child (sliding) or run each resident pair in one child (pair).",
    )
    parser.add_argument(
        "--child-runtime-mode",
        choices=("separate", "packed"),
        default="separate",
        help="With residency-window-size > 1, load resident HBM files as separate runtimes or one packed runtime.",
    )
    parser.add_argument(
        "--window-execution-mode",
        choices=("child-process", "in-process", "window-batch"),
        default="child-process",
        help="With residency-window-size > 1, run resident windows in child processes, in the current Python process, or in window-major batch mode.",
    )
    parser.add_argument("--output-dir", default="/mnt/nas/openclaw/reports/models/dream7b_python_forward")
    parser.add_argument("--tokens-bin", default="", help="Optional int32 token-id binary with shape [1, seq_len].")
    parser.add_argument("--tokens", default="", help="Optional comma or whitespace separated token ids with length seq_len.")
    parser.add_argument("--tokens-batch-json", default="", help="Optional JSON file containing a list of seq_len token-id lists.")
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--save-logits", action="store_true", help="Write final float32 logits as logits.npy.")
    parser.add_argument("--top-k", type=int, default=0, help="Include top-k ids from the last position logits in summary.json.")
    return parser.parse_args()


def resolve_segments(segment_plan: str, hbm_dir: Path, fine_hbm_dir: Path, resplit_hbm_dir: Path, topwindow_hbm_dir: Path):
    if segment_plan == "segments6":
        specs = SEGMENTS6
    elif segment_plan == "fine-adjacent":
        specs = FINE_ADJACENT_SEGMENTS
    elif segment_plan == "resplit-adjacent":
        specs = RESPLIT_ADJACENT_SEGMENTS
    elif segment_plan == "resplit-topwindow-adjacent":
        specs = RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS
    else:
        raise ValueError(f"Unsupported segment plan: {segment_plan}")

    resolved = []
    for segment_id, source, file_name, model_name, input_kind in specs:
        if source == "fine":
            root = fine_hbm_dir
        elif source == "resplit":
            root = resplit_hbm_dir
        elif source == "topwindow":
            root = topwindow_hbm_dir
        else:
            root = hbm_dir
        resolved.append((segment_id, source, root / file_name, model_name, input_kind))
    return resolved


def parse_token_values(text: str) -> np.ndarray:
    parts = [part for part in text.replace(",", " ").split() if part]
    if not parts:
        raise ValueError("--tokens was set but no token ids were parsed")
    try:
        values = [int(part, 0) for part in parts]
    except ValueError as exc:
        raise ValueError(f"Invalid token id in --tokens: {text}") from exc
    return np.asarray(values, dtype=np.int32)


def load_tokens_batch_json(path: str, seq_len: int) -> np.ndarray:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("--tokens-batch-json must contain a JSON list")
    rows = []
    for index, row in enumerate(payload):
        if not isinstance(row, list):
            raise ValueError(f"--tokens-batch-json row {index} is not a JSON list")
        if len(row) != seq_len:
            raise ValueError(f"--tokens-batch-json row {index} expected {seq_len} token ids, got {len(row)}")
        rows.append([int(item) for item in row])
    if not rows:
        raise ValueError("--tokens-batch-json must contain at least one token row")
    return np.asarray(rows, dtype=np.int32)


def load_tokens(path: str, token_text: str, tokens_batch_json: str, seq_len: int) -> tuple[np.ndarray, str, int]:
    input_count = sum(1 for item in (path, token_text, tokens_batch_json) if item)
    if input_count > 1:
        raise ValueError("Use only one of --tokens-bin, --tokens, or --tokens-batch-json.")
    if tokens_batch_json:
        data = load_tokens_batch_json(tokens_batch_json, seq_len)
        return data, tokens_batch_json, int(data.shape[0])
    if token_text:
        data = parse_token_values(token_text)
        source = "tokens_arg"
    elif path:
        data = np.fromfile(path, dtype=np.int32)
        source = path
    else:
        data = np.zeros(seq_len, dtype=np.int32)
        source = "zero_tokens"

    expected = seq_len
    if data.size != expected:
        raise ValueError(f"Expected {expected} int32 token ids, got {data.size}: {source}")
    return data.reshape(1, seq_len), source, 1


def first_scale(runtime: HB_HBMRuntime, model_name: str, output_name: str) -> float:
    quant = runtime.output_quants[model_name][output_name]
    scale = np.asarray(quant.scale).reshape(-1)
    if scale.size == 0:
        return 1.0
    return float(scale[0])


def load_segment_runtime(model_file: Path):
    t0 = time.perf_counter()
    runtime = HB_HBMRuntime(str(model_file))
    t_load = time.perf_counter()
    return runtime, round((t_load - t0) * 1000, 3)


def run_loaded_segment(
    runtime: HB_HBMRuntime,
    model_file: Path,
    model_name: str,
    inputs: dict[str, np.ndarray],
    load_ms: float,
    resident_segments: list[str],
):
    t0 = time.perf_counter()
    output = runtime.run(inputs, model_name=model_name)
    t_run = time.perf_counter()
    output_name = runtime.output_names[model_name][0]
    arr = output[model_name][output_name]
    scale = first_scale(runtime, model_name, output_name)
    result = {
        "model_name": model_name,
        "model_file": str(model_file),
        "output_name": output_name,
        "output_shape": list(arr.shape),
        "output_dtype": str(arr.dtype),
        "output_scale": scale,
        "load_ms": load_ms,
        "run_ms": round((t_run - t0) * 1000, 3),
        "resident_segments": resident_segments,
        "resident_count": len(resident_segments),
    }
    dequantized = arr.astype(np.float32) * scale
    del output
    return dequantized, result


def topk_last_position(logits: np.ndarray, top_k: int) -> list[dict[str, float | int]]:
    if top_k <= 0:
        return []
    last = logits[0, -1].astype(np.float32, copy=False)
    k = min(int(top_k), int(last.shape[0]))
    if k <= 0:
        return []
    indices = np.argpartition(last, -k)[-k:]
    indices = indices[np.argsort(last[indices])[::-1]]
    return [{"token_id": int(idx), "score": float(last[idx])} for idx in indices]


def run_window_child_segments(
    segments,
    tokens: np.ndarray,
    position_ids: np.ndarray,
    output_dir: Path,
    residency_window_size: int,
    child_window_mode: str,
    child_runtime_mode: str,
):
    work_dir = output_dir / "window_child_io"
    work_dir.mkdir(parents=True, exist_ok=True)
    position_path = work_dir / "position_ids.npy"
    np.save(position_path, position_ids)
    current_input_path = work_dir / "input_tokens.npy"
    np.save(current_input_path, tokens)
    segment_results = []

    index = 0
    child_process_count = 0
    while index < len(segments):
        segment_id, source, model_file, model_name, input_kind = segments[index]
        if child_window_mode == "pair":
            run_count = min(residency_window_size, len(segments) - index)
            next_index = index + run_count
        else:
            run_count = 1
            next_index = index + 1
        resident_specs = []
        for resident_index in range(index, min(len(segments), index + residency_window_size)):
            resident_segment_id, resident_source, resident_model_file, resident_model_name, resident_input_kind = segments[resident_index]
            if not resident_model_file.exists():
                raise FileNotFoundError(resident_model_file)
            resident_specs.append(
                {
                    "segment": resident_segment_id,
                    "source": resident_source,
                    "model_file": str(resident_model_file),
                    "model_name": resident_model_name,
                    "input_kind": resident_input_kind,
                }
            )

        label = "__".join(item["segment"] for item in resident_specs[:run_count])
        output_path = work_dir / f"{label}_output.npy"
        payload = {
            "segment": segment_id,
            "source": source,
            "model_file": str(model_file),
            "model_name": model_name,
            "input_kind": input_kind,
            "input_path": str(current_input_path),
            "position_path": str(position_path),
            "output_path": str(output_path),
            "resident_segments": resident_specs,
            "run_count": run_count,
            "child_runtime_mode": child_runtime_mode,
        }
        proc = subprocess.run(
            [sys.executable, "-c", WINDOW_CHILD_CODE],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=180,
        )
        child_process_count += 1
        stdout_path = work_dir / f"{label}.stdout"
        stderr_path = work_dir / f"{label}.stderr"
        stdout_path.write_text(proc.stdout, encoding="utf-8")
        stderr_path.write_text(proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"Window child failed for {label}; stderr={stderr_path}")
        parsed = None
        for line in proc.stdout.splitlines()[::-1]:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                parsed = json.loads(line)
                break
        if parsed is None:
            raise RuntimeError(f"Window child did not emit JSON for {label}; stdout={stdout_path}")
        for result in parsed["segments"]:
            result["stdout"] = str(stdout_path)
            result["stderr"] = str(stderr_path)
            result["child_label"] = label
            result["child_run_count"] = run_count
            segment_results.append(result)
        current_input_path = output_path
        index = next_index

    final = np.load(current_input_path)
    return final, segment_results, child_process_count


def run_window_in_process_segments(
    segments,
    tokens: np.ndarray,
    position_ids: np.ndarray,
    residency_window_size: int,
    child_window_mode: str,
    child_runtime_mode: str,
):
    current_input = tokens
    segment_results = []

    index = 0
    while index < len(segments):
        if child_window_mode == "pair":
            run_count = min(residency_window_size, len(segments) - index)
            next_index = index + run_count
        else:
            run_count = 1
            next_index = index + 1

        resident_specs = []
        for resident_index in range(index, min(len(segments), index + residency_window_size)):
            resident_segment_id, resident_source, resident_model_file, resident_model_name, resident_input_kind = segments[resident_index]
            if not resident_model_file.exists():
                raise FileNotFoundError(resident_model_file)
            resident_specs.append(
                {
                    "segment": resident_segment_id,
                    "source": resident_source,
                    "model_file": resident_model_file,
                    "model_name": resident_model_name,
                    "input_kind": resident_input_kind,
                }
            )

        runtimes = []
        load_events = []
        if child_runtime_mode == "packed":
            model_files = [str(item["model_file"]) for item in resident_specs]
            t0 = time.perf_counter()
            runtime = HB_HBMRuntime(model_files)
            t1 = time.perf_counter()
            load_ms = round((t1 - t0) * 1000, 3)
            runtimes = [runtime for _ in resident_specs]
            for event_index, spec in enumerate(resident_specs):
                load_events.append(
                    {
                        "segment": spec["segment"],
                        "model_file": str(spec["model_file"]),
                        "load_ms": load_ms if event_index == 0 else 0.0,
                        "packed_load_ms": load_ms,
                        "child_runtime_mode": child_runtime_mode,
                    }
                )
        else:
            for spec in resident_specs:
                t0 = time.perf_counter()
                runtime = HB_HBMRuntime(str(spec["model_file"]))
                t1 = time.perf_counter()
                runtimes.append(runtime)
                load_events.append(
                    {
                        "segment": spec["segment"],
                        "model_file": str(spec["model_file"]),
                        "load_ms": round((t1 - t0) * 1000, 3),
                        "child_runtime_mode": child_runtime_mode,
                    }
                )

        try:
            for run_index in range(run_count):
                current = resident_specs[run_index]
                runtime = runtimes[run_index]
                inputs = {"_input_0": current_input, "_input_1": position_ids}
                t0 = time.perf_counter()
                output = runtime.run(inputs, model_name=current["model_name"])
                t1 = time.perf_counter()
                output_name = runtime.output_names[current["model_name"]][0]
                arr = output[current["model_name"]][output_name]
                scale = first_scale(runtime, current["model_name"], output_name)
                current_input = arr.astype(np.float32) * scale
                segment_results.append(
                    {
                        "segment": current["segment"],
                        "source": current["source"],
                        "input_kind": current["input_kind"],
                        "model_name": current["model_name"],
                        "model_file": str(current["model_file"]),
                        "output_name": output_name,
                        "output_shape": list(arr.shape),
                        "output_dtype": str(arr.dtype),
                        "output_scale": scale,
                        "load_ms": load_events[run_index]["load_ms"],
                        "packed_load_ms": load_events[run_index].get("packed_load_ms", 0.0),
                        "preload_events": load_events,
                        "run_ms": round((t1 - t0) * 1000, 3),
                        "resident_segments": [item["segment"] for item in resident_specs],
                        "resident_count": len(resident_specs),
                        "child_runtime_mode": child_runtime_mode,
                        "window_execution_mode": "in-process",
                    }
                )
                del output, arr
        finally:
            try:
                del runtime
            except NameError:
                pass
            del runtimes
            gc.collect()

        index = next_index

    return current_input, segment_results, 0


def run_window_batch_in_process_segments(
    segments,
    tokens_batch: np.ndarray,
    position_ids: np.ndarray,
    residency_window_size: int,
    child_window_mode: str,
    child_runtime_mode: str,
):
    if child_window_mode != "pair":
        raise ValueError("--window-execution-mode window-batch requires --child-window-mode pair")
    if child_runtime_mode != "packed":
        raise ValueError("--window-execution-mode window-batch requires --child-runtime-mode packed")
    current_inputs = [tokens_batch[index].reshape(1, position_ids.shape[0]).copy() for index in range(tokens_batch.shape[0])]
    segment_results = []

    index = 0
    while index < len(segments):
        run_count = min(residency_window_size, len(segments) - index)
        next_index = index + run_count
        resident_specs = []
        for resident_index in range(index, next_index):
            resident_segment_id, resident_source, resident_model_file, resident_model_name, resident_input_kind = segments[resident_index]
            if not resident_model_file.exists():
                raise FileNotFoundError(resident_model_file)
            resident_specs.append(
                {
                    "segment": resident_segment_id,
                    "source": resident_source,
                    "model_file": resident_model_file,
                    "model_name": resident_model_name,
                    "input_kind": resident_input_kind,
                }
            )

        model_files = [str(item["model_file"]) for item in resident_specs]
        t0 = time.perf_counter()
        runtime = HB_HBMRuntime(model_files)
        t1 = time.perf_counter()
        packed_load_ms = round((t1 - t0) * 1000, 3)
        try:
            for batch_index, current_input in enumerate(current_inputs):
                dequantized = current_input
                for run_index, current in enumerate(resident_specs):
                    inputs = {"_input_0": dequantized, "_input_1": position_ids}
                    t2 = time.perf_counter()
                    output = runtime.run(inputs, model_name=current["model_name"])
                    t3 = time.perf_counter()
                    output_name = runtime.output_names[current["model_name"]][0]
                    arr = output[current["model_name"]][output_name]
                    scale = first_scale(runtime, current["model_name"], output_name)
                    dequantized = arr.astype(np.float32) * scale
                    segment_results.append(
                        {
                            "batch_index": batch_index,
                            "segment": current["segment"],
                            "source": current["source"],
                            "input_kind": current["input_kind"],
                            "model_name": current["model_name"],
                            "model_file": str(current["model_file"]),
                            "output_name": output_name,
                            "output_shape": list(arr.shape),
                            "output_dtype": str(arr.dtype),
                            "output_scale": scale,
                            "load_ms": packed_load_ms if batch_index == 0 and run_index == 0 else 0.0,
                            "packed_load_ms": packed_load_ms,
                            "run_ms": round((t3 - t2) * 1000, 3),
                            "resident_segments": [item["segment"] for item in resident_specs],
                            "resident_count": len(resident_specs),
                            "child_runtime_mode": child_runtime_mode,
                            "window_execution_mode": "window-batch",
                        }
                    )
                    del output, arr
                current_inputs[batch_index] = dequantized
        finally:
            del runtime
            gc.collect()

        index = next_index

    return current_inputs, segment_results, 0


def main():
    args = parse_args()
    if args.residency_window_size < 1:
        raise ValueError("--residency-window-size must be >= 1")
    hbm_dir = Path(args.hbm_dir)
    fine_hbm_dir = Path(args.fine_hbm_dir)
    resplit_hbm_dir = Path(args.resplit_hbm_dir)
    topwindow_hbm_dir = Path(args.topwindow_hbm_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = resolve_segments(args.segment_plan, hbm_dir, fine_hbm_dir, resplit_hbm_dir, topwindow_hbm_dir)

    tokens, tokens_source, batch_count = load_tokens(args.tokens_bin, args.tokens, args.tokens_batch_json, args.seq_len)
    position_ids = np.arange(args.seq_len, dtype=np.int32)
    batch_outputs = None
    if args.window_execution_mode == "window-batch" and args.residency_window_size <= 1:
        raise ValueError("--window-execution-mode window-batch requires --residency-window-size greater than 1")
    if args.window_execution_mode != "window-batch" and batch_count != 1:
        raise ValueError("--tokens-batch-json requires --window-execution-mode window-batch")
    forward_start_ns = time.perf_counter_ns()
    if args.residency_window_size > 1 and args.window_execution_mode == "child-process":
        hidden, segment_results, child_process_count = run_window_child_segments(
            segments,
            tokens,
            position_ids,
            output_dir,
            args.residency_window_size,
            args.child_window_mode,
            args.child_runtime_mode,
        )
    elif args.residency_window_size > 1 and args.window_execution_mode == "in-process":
        hidden, segment_results, child_process_count = run_window_in_process_segments(
            segments,
            tokens,
            position_ids,
            args.residency_window_size,
            args.child_window_mode,
            args.child_runtime_mode,
        )
    elif args.residency_window_size > 1 and args.window_execution_mode == "window-batch":
        batch_outputs, segment_results, child_process_count = run_window_batch_in_process_segments(
            segments,
            tokens,
            position_ids,
            args.residency_window_size,
            args.child_window_mode,
            args.child_runtime_mode,
        )
        hidden = batch_outputs[0]
    else:
        hidden = None
        segment_results = []
    runtime_cache: dict[int, tuple[HB_HBMRuntime, float]] = {}

    def ensure_loaded(index: int):
        if index in runtime_cache:
            return
        segment_id, _, model_file, _, _ = segments[index]
        if not model_file.exists():
            raise FileNotFoundError(model_file)
        runtime_cache[index] = load_segment_runtime(model_file)

    def evict(index: int):
        item = runtime_cache.pop(index, None)
        if item is not None:
            del item
            gc.collect()

    if args.residency_window_size == 1:
        for index, (segment_id, source, model_file, model_name, input_kind) in enumerate(segments):
            ensure_loaded(index)
            resident_segments = [segments[item][0] for item in sorted(runtime_cache)]

            if input_kind == "tokens":
                inputs = {"_input_0": tokens, "_input_1": position_ids}
            else:
                if hidden is None:
                    raise RuntimeError(f"Missing hidden state before {segment_id}")
                expected = (args.seq_len, args.hidden_size)
                if hidden.shape != expected:
                    raise ValueError(f"Expected hidden shape {expected}, got {hidden.shape}")
                inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": position_ids}

            runtime, load_ms = runtime_cache[index]
            hidden, result = run_loaded_segment(runtime, model_file, model_name, inputs, load_ms, resident_segments)
            result["segment"] = segment_id
            result["source"] = source
            result["input_kind"] = input_kind
            segment_results.append(result)
            evict(index)
            del runtime
            gc.collect()

        for index in list(runtime_cache):
            evict(index)

    forward_end_ns = time.perf_counter_ns()
    expected_logits = (1, args.seq_len, args.vocab_size)
    if batch_outputs is not None:
        for batch_index, item in enumerate(batch_outputs):
            if item.shape != expected_logits:
                raise ValueError(f"Expected final logits shape {expected_logits} for batch {batch_index}, got {item.shape}")
    elif hidden.shape != expected_logits:
        raise ValueError(f"Expected final logits shape {expected_logits}, got {hidden.shape}")

    logits_path = ""
    if args.save_logits:
        if batch_outputs is None:
            logits_path = str(output_dir / "logits.npy")
            np.save(logits_path, hidden)
        else:
            logits_paths = []
            for batch_index, item in enumerate(batch_outputs):
                item_path = output_dir / f"logits_batch_{batch_index:03d}.npy"
                np.save(item_path, item)
                logits_paths.append(str(item_path))
            logits_path = json.dumps(logits_paths, ensure_ascii=False)
    topk_last = topk_last_position(hidden, args.top_k)
    topk_last_by_batch = []
    if batch_outputs is not None and args.top_k > 0:
        topk_last_by_batch = [
            {
                "batch_index": batch_index,
                "topk_last_position": topk_last_position(item, args.top_k),
            }
            for batch_index, item in enumerate(batch_outputs)
        ]
    final_shapes = [list(item.shape) for item in batch_outputs] if batch_outputs is not None else [list(hidden.shape)]
    if args.residency_window_size > 1 and args.window_execution_mode == "window-batch":
        execution_mode = "pair_window_batch"
    elif args.residency_window_size > 1:
        execution_mode = f"{args.child_window_mode}_{args.window_execution_mode.replace('-', '_')}"
    else:
        execution_mode = "in_process"
    wall_ms = round((forward_end_ns - forward_start_ns) / 1_000_000.0, 3)
    load_ms = round(sum(float(item.get("load_ms", 0.0)) for item in segment_results), 3)
    run_ms = round(sum(float(item.get("run_ms", 0.0)) for item in segment_results), 3)

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_segmented_hbm_python_forward",
        "segment_plan": args.segment_plan,
        "residency_window_size": args.residency_window_size,
        "child_window_mode": args.child_window_mode if args.residency_window_size > 1 else "",
        "child_runtime_mode": args.child_runtime_mode if args.residency_window_size > 1 else "",
        "window_execution_mode": args.window_execution_mode if args.residency_window_size > 1 else "in_process",
        "execution_mode": execution_mode,
        "child_process_count": child_process_count if args.residency_window_size > 1 else 0,
        "hbm_dir": str(hbm_dir),
        "fine_hbm_dir": str(fine_hbm_dir),
        "resplit_hbm_dir": str(resplit_hbm_dir),
        "topwindow_hbm_dir": str(topwindow_hbm_dir),
        "output_dir": str(output_dir),
        "runtime_version": HB_HBMRuntime.version,
        "tokens_source": tokens_source,
        "tokens_bin": args.tokens_bin or "",
        "tokens_batch_json": args.tokens_batch_json or "",
        "batch_count": batch_count,
        "wall_ms": wall_ms,
        "load_ms": load_ms,
        "run_ms": run_ms,
        "amortized_wall_ms_per_forward": round(wall_ms / batch_count, 3),
        "amortized_load_ms_per_forward": round(load_ms / batch_count, 3),
        "amortized_run_ms_per_forward": round(run_ms / batch_count, 3),
        "logits_npy": logits_path,
        "top_k": int(args.top_k),
        "topk_last_position": topk_last,
        "topk_last_position_by_batch": topk_last_by_batch,
        "final_shape": list(hidden.shape),
        "final_shapes": final_shapes,
        "final_dtype": str(hidden.dtype),
        "final_bytes": int(sum(item.nbytes for item in batch_outputs)) if batch_outputs is not None else int(hidden.nbytes),
        "segments": segment_results,
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
