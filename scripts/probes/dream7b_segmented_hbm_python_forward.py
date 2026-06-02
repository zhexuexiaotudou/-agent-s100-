#!/usr/bin/env python3
import argparse
import gc
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from hbm_runtime import HB_HBMRuntime


SEGMENTS = [
    ("seg00_04", "dream7b_segment_0_4_seq16_q8.hbm", "dream_segment_00_04", "tokens"),
    ("seg04_07", "dream7b_segment_4_7_seq16_q8.hbm", "dream_segment_04_07", "hidden"),
    ("seg07_14", "dream7b_segment_7_14_seq16_q8.hbm", "dream_segment_07_14", "hidden"),
    ("seg14_21", "dream7b_segment_14_21_seq16_q8.hbm", "dream_segment_14_21", "hidden"),
    ("seg21_24", "dream7b_segment_21_24_seq16_q8.hbm", "dream_segment_21_24", "hidden"),
    ("seg24_28", "dream7b_segment_24_28_seq16_q8.hbm", "dream_segment_24_28", "hidden"),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Run Dream 7B seq16 segmented S100 HBM forward.")
    parser.add_argument("--hbm-dir", default="/mnt/nas/openclaw/models/dream7b-hbm/segments6")
    parser.add_argument("--output-dir", default="/mnt/nas/openclaw/reports/models/dream7b_python_forward")
    parser.add_argument("--tokens-bin", default="", help="Optional int32 token-id binary with shape [1, seq_len].")
    parser.add_argument("--tokens", default="", help="Optional comma or whitespace separated token ids with length seq_len.")
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--save-logits", action="store_true", help="Write final float32 logits as logits.npy.")
    parser.add_argument("--top-k", type=int, default=0, help="Include top-k ids from the last position logits in summary.json.")
    return parser.parse_args()


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


def run_segment(model_file: Path, model_name: str, inputs: dict[str, np.ndarray]):
    t0 = time.perf_counter()
    runtime = HB_HBMRuntime(str(model_file))
    t_load = time.perf_counter()
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
        "load_ms": round((t_load - t0) * 1000, 3),
        "run_ms": round((t_run - t_load) * 1000, 3),
    }
    dequantized = arr.astype(np.float32) * scale
    del output
    del runtime
    gc.collect()
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


def main():
    args = parse_args()
    hbm_dir = Path(args.hbm_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tokens, tokens_source = load_tokens(args.tokens_bin, args.tokens, args.seq_len)
    position_ids = np.arange(args.seq_len, dtype=np.int32)
    hidden = None
    segment_results = []

    for segment_id, file_name, model_name, input_kind in SEGMENTS:
        model_file = hbm_dir / file_name
        if not model_file.exists():
            raise FileNotFoundError(model_file)
        if input_kind == "tokens":
            inputs = {"_input_0": tokens, "_input_1": position_ids}
        else:
            if hidden is None:
                raise RuntimeError(f"Missing hidden state before {segment_id}")
            expected = (args.seq_len, args.hidden_size)
            if hidden.shape != expected:
                raise ValueError(f"Expected hidden shape {expected}, got {hidden.shape}")
            inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": position_ids}

        hidden, result = run_segment(model_file, model_name, inputs)
        result["segment"] = segment_id
        result["input_kind"] = input_kind
        segment_results.append(result)

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
        "hbm_dir": str(hbm_dir),
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
