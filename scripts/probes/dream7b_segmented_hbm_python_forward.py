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
runtimes = []
load_events = []
for segment in payload["resident_segments"]:
    t0 = time.perf_counter()
    runtime = HB_HBMRuntime(segment["model_file"])
    t1 = time.perf_counter()
    runtimes.append(runtime)
    load_events.append({
        "segment": segment["segment"],
        "model_file": segment["model_file"],
        "load_ms": round((t1 - t0) * 1000, 3),
    })

current = payload["resident_segments"][0]
runtime = runtimes[0]
inputs = {"_input_0": input_0, "_input_1": position_ids}
t0 = time.perf_counter()
output = runtime.run(inputs, model_name=current["model_name"])
t1 = time.perf_counter()
output_name = runtime.output_names[current["model_name"]][0]
arr = output[current["model_name"]][output_name]
scale = first_scale(runtime, current["model_name"], output_name)
dequantized = arr.astype(np.float32) * scale
np.save(payload["output_path"], dequantized)
print(json.dumps({
    "model_name": current["model_name"],
    "model_file": current["model_file"],
    "output_name": output_name,
    "output_shape": list(arr.shape),
    "output_dtype": str(arr.dtype),
    "output_scale": scale,
    "load_ms": load_events[0]["load_ms"],
    "preload_events": load_events,
    "run_ms": round((t1 - t0) * 1000, 3),
    "resident_segments": [item["segment"] for item in payload["resident_segments"]],
    "resident_count": len(payload["resident_segments"]),
}, ensure_ascii=False))
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Run Dream 7B seq16 segmented S100 HBM forward.")
    parser.add_argument("--hbm-dir", default="/mnt/nas/openclaw/models/dream7b-hbm/segments6")
    parser.add_argument("--fine-hbm-dir", default="/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16")
    parser.add_argument("--segment-plan", choices=("segments6", "fine-adjacent"), default="segments6")
    parser.add_argument(
        "--residency-window-size",
        type=int,
        default=1,
        help="Keep this many adjacent HBM runtimes loaded. Use 2 with --segment-plan fine-adjacent.",
    )
    parser.add_argument("--output-dir", default="/mnt/nas/openclaw/reports/models/dream7b_python_forward")
    parser.add_argument("--tokens-bin", default="", help="Optional int32 token-id binary with shape [1, seq_len].")
    parser.add_argument("--tokens", default="", help="Optional comma or whitespace separated token ids with length seq_len.")
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--save-logits", action="store_true", help="Write final float32 logits as logits.npy.")
    parser.add_argument("--top-k", type=int, default=0, help="Include top-k ids from the last position logits in summary.json.")
    return parser.parse_args()


def resolve_segments(segment_plan: str, hbm_dir: Path, fine_hbm_dir: Path):
    if segment_plan == "segments6":
        specs = SEGMENTS6
    elif segment_plan == "fine-adjacent":
        specs = FINE_ADJACENT_SEGMENTS
    else:
        raise ValueError(f"Unsupported segment plan: {segment_plan}")

    resolved = []
    for segment_id, source, file_name, model_name, input_kind in specs:
        root = fine_hbm_dir if source == "fine" else hbm_dir
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


def load_tokens(path: str, token_text: str, seq_len: int) -> tuple[np.ndarray, str]:
    if path and token_text:
        raise ValueError("Use either --tokens-bin or --tokens, not both.")
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
    return data.reshape(1, seq_len), source


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
):
    work_dir = output_dir / "window_child_io"
    work_dir.mkdir(parents=True, exist_ok=True)
    position_path = work_dir / "position_ids.npy"
    np.save(position_path, position_ids)
    current_input_path = work_dir / "input_tokens.npy"
    np.save(current_input_path, tokens)
    segment_results = []

    for index, (segment_id, source, model_file, model_name, input_kind) in enumerate(segments):
        resident_specs = []
        for resident_index in range(index, min(len(segments), index + residency_window_size)):
            resident_segment_id, _, resident_model_file, resident_model_name, _ = segments[resident_index]
            if not resident_model_file.exists():
                raise FileNotFoundError(resident_model_file)
            resident_specs.append(
                {
                    "segment": resident_segment_id,
                    "model_file": str(resident_model_file),
                    "model_name": resident_model_name,
                }
            )

        output_path = work_dir / f"{segment_id}_output.npy"
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
        }
        proc = subprocess.run(
            [sys.executable, "-c", WINDOW_CHILD_CODE],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=180,
        )
        stdout_path = work_dir / f"{segment_id}.stdout"
        stderr_path = work_dir / f"{segment_id}.stderr"
        stdout_path.write_text(proc.stdout, encoding="utf-8")
        stderr_path.write_text(proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"Window child failed for {segment_id}; stderr={stderr_path}")
        parsed = None
        for line in proc.stdout.splitlines()[::-1]:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                parsed = json.loads(line)
                break
        if parsed is None:
            raise RuntimeError(f"Window child did not emit JSON for {segment_id}; stdout={stdout_path}")
        parsed["segment"] = segment_id
        parsed["source"] = source
        parsed["input_kind"] = input_kind
        parsed["stdout"] = str(stdout_path)
        parsed["stderr"] = str(stderr_path)
        segment_results.append(parsed)
        current_input_path = output_path

    final = np.load(current_input_path)
    return final, segment_results


def main():
    args = parse_args()
    if args.residency_window_size < 1:
        raise ValueError("--residency-window-size must be >= 1")
    hbm_dir = Path(args.hbm_dir)
    fine_hbm_dir = Path(args.fine_hbm_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = resolve_segments(args.segment_plan, hbm_dir, fine_hbm_dir)

    tokens, tokens_source = load_tokens(args.tokens_bin, args.tokens, args.seq_len)
    position_ids = np.arange(args.seq_len, dtype=np.int32)
    if args.residency_window_size > 1:
        hidden, segment_results = run_window_child_segments(
            segments,
            tokens,
            position_ids,
            output_dir,
            args.residency_window_size,
        )
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

    expected_logits = (1, args.seq_len, args.vocab_size)
    if hidden.shape != expected_logits:
        raise ValueError(f"Expected final logits shape {expected_logits}, got {hidden.shape}")

    logits_path = ""
    if args.save_logits:
        logits_path = str(output_dir / "logits.npy")
        np.save(logits_path, hidden)
    topk_last = topk_last_position(hidden, args.top_k)

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_segmented_hbm_python_forward",
        "segment_plan": args.segment_plan,
        "residency_window_size": args.residency_window_size,
        "execution_mode": "window_child_process" if args.residency_window_size > 1 else "in_process",
        "hbm_dir": str(hbm_dir),
        "fine_hbm_dir": str(fine_hbm_dir),
        "output_dir": str(output_dir),
        "runtime_version": HB_HBMRuntime.version,
        "tokens_source": tokens_source,
        "tokens_bin": args.tokens_bin or "",
        "logits_npy": logits_path,
        "top_k": int(args.top_k),
        "topk_last_position": topk_last,
        "final_shape": list(hidden.shape),
        "final_dtype": str(hidden.dtype),
        "final_bytes": int(hidden.nbytes),
        "segments": segment_results,
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
