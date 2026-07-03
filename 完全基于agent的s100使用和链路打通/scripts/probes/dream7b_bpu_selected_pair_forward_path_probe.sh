#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
triplet_json="${DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON:-}"
selected_pair_text="${DREAM7B_BPU_SELECTED_PAIR_INDEXES:-}"
forward_cmd="${DREAM7B_BPU_SELECTED_PAIR_BASELINE_FORWARD_CMD:-dream7b-bpu-fine-batch-forward}"
batch_count="${DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT:-4}"
batch_count_limit="${DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT_LIMIT:-16}"
job_count="${DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT:-1}"
job_count_limit="${DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT_LIMIT:-12}"
top_k="${DREAM7B_BPU_SELECTED_PAIR_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC:-900}"
selected_only="${DREAM7B_BPU_SELECTED_PAIR_ONLY:-0}"
tokens_batch_json_override="${DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON:-}"
tokens_batches_by_job_json_override="${DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON:-}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$base_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/segments6|/mnt/nas/openclaw/models/dream7b-hbm/segments6/|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6/) ;;
  *)
    echo "Refusing base HBM path outside approved Dream 7B HBM directories: $base_hbm_dir" >&2
    exit 2
    ;;
esac

case "$fine_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16|/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/|/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16|/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16/) ;;
  *)
    echo "Refusing fine HBM path outside approved Dream 7B HBM directories: $fine_hbm_dir" >&2
    exit 2
    ;;
esac

if [[ -n "$triplet_json" ]]; then
  case "$triplet_json" in
    /tmp/*|/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_*/*|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing triplet JSON path outside approved report directories: $triplet_json" >&2
      exit 2
      ;;
  esac
fi

if [[ -n "$tokens_batch_json_override" ]]; then
  case "$tokens_batch_json_override" in
    /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing tokens batch JSON outside approved report directories: $tokens_batch_json_override" >&2
      exit 2
      ;;
  esac
  if [[ ! -f "$tokens_batch_json_override" ]]; then
    echo "Missing DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON: $tokens_batch_json_override" >&2
    exit 2
  fi
fi
if [[ -n "$tokens_batches_by_job_json_override" ]]; then
  case "$tokens_batches_by_job_json_override" in
    /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing tokens batches-by-job JSON outside approved report directories: $tokens_batches_by_job_json_override" >&2
      exit 2
      ;;
  esac
  if [[ ! -f "$tokens_batches_by_job_json_override" ]]; then
    echo "Missing DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON: $tokens_batches_by_job_json_override" >&2
    exit 2
  fi
fi
if [[ -n "$tokens_batch_json_override" && -n "$tokens_batches_by_job_json_override" ]]; then
  echo "Use only one of DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON or DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON." >&2
  exit 2
fi

if ! [[ "$batch_count_limit" =~ ^[1-9][0-9]*$ ]] || (( batch_count_limit < 1 || batch_count_limit > 256 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT_LIMIT must be an integer from 1 to 256." >&2
  exit 2
fi
if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count > batch_count_limit )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT must be an integer from 1 to $batch_count_limit." >&2
  exit 2
fi
if ! [[ "$job_count_limit" =~ ^[1-9][0-9]*$ ]] || (( job_count_limit < 1 || job_count_limit > 32 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT_LIMIT must be an integer from 1 to 32." >&2
  exit 2
fi
if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count > job_count_limit )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT must be an integer from 1 to $job_count_limit." >&2
  exit 2
fi
if (( job_count > 1 )) && [[ "$selected_only" != "1" ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT greater than 1 requires DREAM7B_BPU_SELECTED_PAIR_ONLY=1." >&2
  exit 2
fi
if (( job_count > 1 )) && [[ -n "$tokens_batch_json_override" ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT greater than 1 does not support DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON override." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
case "$selected_only" in
  0|1) ;;
  *)
    echo "DREAM7B_BPU_SELECTED_PAIR_ONLY must be 0 or 1." >&2
    exit 2
    ;;
esac
if ! command -v "$forward_cmd" >/dev/null 2>&1; then
  echo "Missing deployed S100P command: $forward_cmd" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_forward_path_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$triplet_json" \
  "$selected_pair_text" \
  "$forward_cmd" \
  "$batch_count" \
  "$job_count" \
  "$top_k" \
  "$timeout_sec" \
  "$selected_only" \
  "$tokens_batch_json_override" \
  "$tokens_batches_by_job_json_override" <<'PY'
import gc
import itertools
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from multiprocessing import Pipe, Process
from pathlib import Path

import numpy as np
from hbm_runtime import HB_HBMRuntime

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
base_hbm_dir = Path(sys.argv[3])
fine_hbm_dir = Path(sys.argv[4])
triplet_json_arg = sys.argv[5]
selected_pair_text = sys.argv[6].strip()
forward_cmd = sys.argv[7]
batch_count = int(sys.argv[8])
job_count = int(sys.argv[9])
top_k = int(sys.argv[10])
timeout_sec = int(sys.argv[11])
selected_only = sys.argv[12] == "1"
tokens_batch_json_override = sys.argv[13]
tokens_batches_by_job_json_override = sys.argv[14]

seq_len = 16
hidden_size = 3584
vocab_size = 152064
position_ids = np.arange(seq_len, dtype=np.int32)

segments = [
    ("seg00_02", "fine", fine_hbm_dir / "seg00_02/dream7b_segment_0_2_seq16_q8.hbm", "dream_segment_00_02", "tokens"),
    ("seg02_04", "fine", fine_hbm_dir / "seg02_04/dream7b_segment_2_4_seq16_q8.hbm", "dream_segment_02_04", "hidden"),
    ("seg04_07", "base", base_hbm_dir / "dream7b_segment_4_7_seq16_q8.hbm", "dream_segment_04_07", "hidden"),
    ("seg07_10", "fine", fine_hbm_dir / "seg07_10/dream7b_segment_7_10_seq16_q8.hbm", "dream_segment_07_10", "hidden"),
    ("seg10_14", "fine", fine_hbm_dir / "seg10_14/dream7b_segment_10_14_seq16_q8.hbm", "dream_segment_10_14", "hidden"),
    ("seg14_17", "fine", fine_hbm_dir / "seg14_17/dream7b_segment_14_17_seq16_q8.hbm", "dream_segment_14_17", "hidden"),
    ("seg17_21", "fine", fine_hbm_dir / "seg17_21/dream7b_segment_17_21_seq16_q8.hbm", "dream_segment_17_21", "hidden"),
    ("seg21_24", "base", base_hbm_dir / "dream7b_segment_21_24_seq16_q8.hbm", "dream_segment_21_24", "hidden"),
    ("seg24_26", "fine", fine_hbm_dir / "seg24_26/dream7b_segment_24_26_seq16_q8.hbm", "dream_segment_24_26", "hidden"),
    ("seg26_28", "fine", fine_hbm_dir / "seg26_28/dream7b_segment_26_28_seq16_q8.hbm", "dream_segment_26_28", "hidden"),
]

missing = [str(item[2]) for item in segments if not item[2].exists()]
if missing:
    raise SystemExit("missing HBM files: " + ", ".join(missing))

def latest_triplet_json():
    if triplet_json_arg:
        path = Path(triplet_json_arg)
        if not path.is_file():
            raise SystemExit(f"missing DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON: {path}")
        return path
    paths = [
        path
        for path in report_root.glob("dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json")
        if path.is_file()
    ]
    if not paths:
        raise SystemExit("missing single-segment triplet residency report")
    return max(paths, key=lambda path: path.stat().st_mtime)

triplet_json_path = latest_triplet_json()
triplet_report = json.loads(triplet_json_path.read_text(encoding="utf-8"))
successful_triplets = triplet_report.get("successful_triplets") or []
if not isinstance(successful_triplets, list):
    raise SystemExit("single_segment_triplet_residency_probe.json field successful_triplets is not a list")

pair_thirds = defaultdict(set)
for triplet in successful_triplets:
    values = [int(item) for item in triplet]
    if len(values) != 3:
        continue
    for pair in itertools.combinations(sorted(values), 2):
        pair_thirds[pair].update(set(values) - set(pair))

segment_indexes = set(range(len(segments)))
if selected_pair_text:
    parts = [int(item) for item in selected_pair_text.replace(",", " ").split()]
    if len(parts) != 2:
        raise SystemExit(f"DREAM7B_BPU_SELECTED_PAIR_INDEXES must contain exactly 2 indexes: {selected_pair_text}")
    selected_pair = tuple(sorted(parts))
else:
    candidates = []
    for pair, thirds in pair_thirds.items():
        covered = set(pair).union(thirds)
        candidates.append(
            {
                "pair": pair,
                "thirds": sorted(thirds),
                "coverage_count": len(covered),
                "covers_all_segments": covered == segment_indexes,
            }
        )
    if not candidates:
        raise SystemExit("no successful pair candidates found in successful_triplets")
    best = sorted(candidates, key=lambda item: (-int(item["covers_all_segments"]), -item["coverage_count"], item["pair"]))[0]
    selected_pair = best["pair"]

if any(index < 0 or index >= len(segments) for index in selected_pair):
    raise SystemExit(f"invalid selected pair indexes: {selected_pair}")
selected_thirds = pair_thirds.get(selected_pair, set())
selected_pair_covers_all_segments = set(selected_pair).union(selected_thirds) == segment_indexes
if not selected_pair_covers_all_segments:
    raise SystemExit(
        f"selected pair {selected_pair} does not cover all segments through successful_triplets; thirds={sorted(selected_thirds)}"
    )

if tokens_batches_by_job_json_override:
    source_tokens_batches_by_job_json = Path(tokens_batches_by_job_json_override)
    raw_job_tokens_batches = json.loads(source_tokens_batches_by_job_json.read_text(encoding="utf-8"))
    if not isinstance(raw_job_tokens_batches, list) or not raw_job_tokens_batches:
        raise SystemExit("DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON must contain a non-empty JSON list")
    job_tokens_batches = []
    expected_batch_count = None
    for job_index, raw_tokens_batch in enumerate(raw_job_tokens_batches):
        if not isinstance(raw_tokens_batch, list) or not raw_tokens_batch:
            raise SystemExit(f"tokens job {job_index} must contain a non-empty JSON list")
        normalized_tokens_batch = []
        for batch_index, row in enumerate(raw_tokens_batch):
            if not isinstance(row, list) or len(row) != seq_len:
                raise SystemExit(f"tokens job {job_index} row {batch_index} must contain exactly {seq_len} token ids")
            normalized_tokens_batch.append([int(item) for item in row])
        if expected_batch_count is None:
            expected_batch_count = len(normalized_tokens_batch)
        elif len(normalized_tokens_batch) != expected_batch_count:
            raise SystemExit(
                "DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON must use the same batch count for every job"
            )
        job_tokens_batches.append(normalized_tokens_batch)
    job_count = len(job_tokens_batches)
    batch_count = int(expected_batch_count or 0)
elif tokens_batch_json_override:
    source_tokens_batch_json = Path(tokens_batch_json_override)
    tokens_batch = json.loads(source_tokens_batch_json.read_text(encoding="utf-8"))
    if not isinstance(tokens_batch, list) or not tokens_batch:
        raise SystemExit("DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON must contain a non-empty JSON list")
    normalized_tokens_batch = []
    for batch_index, row in enumerate(tokens_batch):
        if not isinstance(row, list) or len(row) != seq_len:
            raise SystemExit(f"tokens batch row {batch_index} must contain exactly {seq_len} token ids")
        normalized_tokens_batch.append([int(item) for item in row])
    tokens_batch = normalized_tokens_batch
    batch_count = len(tokens_batch)
    job_tokens_batches = [tokens_batch]
else:
    job_tokens_batches = []
    for job_index in range(job_count):
        tokens_batch = []
        for batch_index in range(batch_count):
            base = ((job_index + 1) * 10000) + ((batch_index + 1) * 100)
            tokens_batch.append([base + offset for offset in range(1, seq_len + 1)])
        job_tokens_batches.append(tokens_batch)
tokens_batch = job_tokens_batches[0]
tokens_batch_json = run_dir / "tokens_batch.json"
tokens_batch_json.write_text(json.dumps(tokens_batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tokens_batches_by_job_json = run_dir / "tokens_batches_by_job.json"
tokens_batches_by_job_json.write_text(json.dumps(job_tokens_batches, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def first_scale(runtime, model_name, output_name):
    quant = runtime.output_quants[model_name][output_name]
    scale = np.asarray(quant.scale).reshape(-1)
    if scale.size == 0:
        return 1.0
    return float(scale[0])

def run_loaded_segment(runtime, model_file, model_name, input_array):
    inputs = {"_input_0": input_array, "_input_1": position_ids}
    t0 = time.perf_counter()
    output = runtime.run(inputs, model_name=model_name)
    t1 = time.perf_counter()
    output_name = runtime.output_names[model_name][0]
    arr = output[model_name][output_name]
    scale = first_scale(runtime, model_name, output_name)
    dequantized = arr.astype(np.float32) * scale
    result = {
        "model_name": model_name,
        "model_file": str(model_file),
        "output_name": output_name,
        "output_shape": list(arr.shape),
        "output_dtype": str(arr.dtype),
        "output_scale": scale,
        "run_ms": round((t1 - t0) * 1000, 3),
    }
    del output, arr
    return dequantized, result

def selected_worker_main(conn, worker_payload):
    segment_index = worker_payload["segment_index"]
    segment_id = worker_payload["segment"]
    model_file = Path(worker_payload["model_file"])
    model_name = worker_payload["model_name"]
    try:
        load_start = time.perf_counter()
        runtime = HB_HBMRuntime(str(model_file))
        load_end = time.perf_counter()
        conn.send(
            {
                "segment_index": segment_index,
                "segment": segment_id,
                "status": "ready",
                "resident_load_ms": round((load_end - load_start) * 1000, 3),
                "runtime_version": HB_HBMRuntime.version,
            }
        )
        while True:
            message = conn.recv()
            if message.get("cmd") == "stop":
                break
            if message.get("cmd") != "run":
                raise ValueError(f"unsupported worker command: {message}")
            output, result = run_loaded_segment(runtime, model_file, model_name, message["input"])
            result.update(
                {
                    "segment_index": segment_index,
                    "segment": segment_id,
                    "batch_index": message["batch_index"],
                    "load_ms": 0.0,
                    "resident_worker": True,
                }
            )
            conn.send({"ok": True, "output": output, "result": result})
        del runtime
        gc.collect()
    except Exception as exc:
        conn.send(
            {
                "segment_index": segment_index,
                "segment": segment_id,
                "status": "failed",
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            }
        )

def start_selected_workers():
    workers = {}
    ready_records = []
    for segment_index in selected_pair:
        segment_id, source, model_file, model_name, input_kind = segments[segment_index]
        parent_conn, child_conn = Pipe()
        payload = {
            "segment_index": segment_index,
            "segment": segment_id,
            "source": source,
            "model_file": str(model_file),
            "model_name": model_name,
            "input_kind": input_kind,
        }
        proc = Process(target=selected_worker_main, args=(child_conn, payload))
        proc.start()
        ready = parent_conn.recv()
        ready_records.append(ready)
        if ready.get("status") != "ready":
            raise RuntimeError(f"selected worker failed: {ready}")
        workers[segment_index] = {
            "process": proc,
            "conn": parent_conn,
            "ready": ready,
            "payload": payload,
        }
    return workers, ready_records

def stop_selected_workers(workers):
    for worker in workers.values():
        try:
            worker["conn"].send({"cmd": "stop"})
        except Exception:
            pass
    for worker in workers.values():
        proc = worker["process"]
        proc.join(timeout=15)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=15)

def run_selected_pair_forward():
    workers, ready_records = start_selected_workers()
    segment_results = []
    selected_resident_load_ms = round(sum(float(item.get("resident_load_ms", 0.0)) for item in ready_records), 3)
    forward_load_ms = 0.0
    forward_run_ms = 0.0
    started = time.perf_counter()
    final_shapes_by_job = []
    topk_last_position_by_job = []
    processed_forward_count = 0
    try:
        for job_index, job_tokens_batch in enumerate(job_tokens_batches):
            tokens_batch_np = np.asarray(job_tokens_batch, dtype=np.int32)
            batch_outputs = [tokens_batch_np[index].reshape(1, seq_len).copy() for index in range(batch_count)]
            for segment_index, (segment_id, source, model_file, model_name, input_kind) in enumerate(segments):
                if segment_index in workers:
                    worker = workers[segment_index]
                    for batch_index, current_input in enumerate(batch_outputs):
                        worker["conn"].send({"cmd": "run", "job_index": job_index, "batch_index": batch_index, "input": current_input})
                        response = worker["conn"].recv()
                        if not response.get("ok"):
                            raise RuntimeError(f"selected worker run failed: {response}")
                        batch_outputs[batch_index] = response["output"]
                        result = response["result"]
                        result["job_index"] = job_index
                        forward_run_ms += float(result.get("run_ms", 0.0))
                        segment_results.append(result)
                    continue

                load_start = time.perf_counter()
                runtime = HB_HBMRuntime(str(model_file))
                load_end = time.perf_counter()
                load_ms = round((load_end - load_start) * 1000, 3)
                forward_load_ms += load_ms
                try:
                    for batch_index, current_input in enumerate(batch_outputs):
                        output, result = run_loaded_segment(runtime, model_file, model_name, current_input)
                        result.update(
                            {
                                "segment_index": segment_index,
                                "segment": segment_id,
                                "job_index": job_index,
                                "batch_index": batch_index,
                                "load_ms": load_ms if batch_index == 0 else 0.0,
                                "resident_worker": False,
                            }
                        )
                        forward_run_ms += float(result.get("run_ms", 0.0))
                        batch_outputs[batch_index] = output
                        segment_results.append(result)
                finally:
                    del runtime
                    gc.collect()
            final_shapes = [list(item.shape) for item in batch_outputs]
            for batch_index, shape in enumerate(final_shapes):
                if shape != [1, seq_len, vocab_size]:
                    raise ValueError(f"Expected final logits shape {[1, seq_len, vocab_size]} for job {job_index} batch {batch_index}, got {shape}")
            final_shapes_by_job.append(final_shapes)
            processed_forward_count += len(batch_outputs)
            job_topk = []
            if top_k > 0:
                for batch_index, logits in enumerate(batch_outputs):
                    last = logits[0, -1].astype(np.float32, copy=False)
                    k = min(top_k, int(last.shape[0]))
                    indices = np.argpartition(last, -k)[-k:]
                    indices = indices[np.argsort(last[indices])[::-1]]
                    job_topk.append(
                        {
                            "job_index": job_index,
                            "batch_index": batch_index,
                            "topk_last_position": [{"token_id": int(idx), "score": float(last[idx])} for idx in indices],
                        }
                    )
            topk_last_position_by_job.append(job_topk)
    finally:
        stop_selected_workers(workers)
    wall_ms = round((time.perf_counter() - started) * 1000, 3)
    final_shapes = final_shapes_by_job[0] if final_shapes_by_job else []
    topk_last_position_by_batch = topk_last_position_by_job[0] if topk_last_position_by_job else []
    selected_total_load_ms = round(selected_resident_load_ms + forward_load_ms, 3)
    return {
        "verdict": "ok_selected_pair_forward",
        "job_count": job_count,
        "batch_count": batch_count,
        "processed_forward_count": processed_forward_count,
        "segment_plan": "fine-adjacent",
        "selected_pair": list(selected_pair),
        "selected_segments": [segments[index][0] for index in selected_pair],
        "selected_third_segments": [segments[index][0] for index in sorted(selected_thirds)],
        "selected_pair_covers_all_segments": selected_pair_covers_all_segments,
        "selected_worker_count": len(workers),
        "selected_worker_ready_records": ready_records,
        "selected_resident_load_ms": selected_resident_load_ms,
        "forward_load_ms": round(forward_load_ms, 3),
        "selected_total_load_ms": selected_total_load_ms,
        "run_ms": round(forward_run_ms, 3),
        "wall_ms": wall_ms,
        "load_share_including_resident_load": round(selected_total_load_ms / max(wall_ms, 0.001), 6),
        "warm_load_share_excluding_resident_load": round(forward_load_ms / max(wall_ms, 0.001), 6),
        "amortized_total_load_ms_per_forward": round(selected_total_load_ms / processed_forward_count, 3),
        "amortized_warm_load_ms_per_forward": round(forward_load_ms / processed_forward_count, 3),
        "amortized_run_ms_per_forward": round(forward_run_ms / processed_forward_count, 3),
        "amortized_wall_ms_per_forward": round(wall_ms / processed_forward_count, 3),
        "final_shapes": final_shapes,
        "final_shapes_by_job": final_shapes_by_job,
        "final_shape": final_shapes[0],
        "top_k": top_k,
        "topk_last_position_by_batch": topk_last_position_by_batch,
        "topk_last_position_by_job": topk_last_position_by_job,
        "segments": segment_results,
    }

def run_baseline_forward():
    baseline_dir = run_dir / "baseline_pair_window_forward"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "baseline.forward.stdout"
    stderr_path = run_dir / "baseline.forward.stderr"
    cmd = [
        forward_cmd,
        "--tokens-batch-json",
        str(tokens_batch_json),
        "--top-k",
        str(top_k),
        "--output-dir",
        str(baseline_dir),
    ]
    started = time.monotonic()
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_sec)
    wall_ms = round((time.monotonic() - started) * 1000, 3)
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    summary_path = baseline_dir / "summary.json"
    summary = {}
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "wall_ms_from_subprocess": wall_ms,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "summary_json": str(summary_path) if summary_path.is_file() else "",
        "summary": summary,
    }

selected_started = time.monotonic()
selected_summary = run_selected_pair_forward()
selected_elapsed_ms = round((time.monotonic() - selected_started) * 1000, 3)
selected_summary["subprocess_wall_ms"] = selected_elapsed_ms
selected_summary_path = run_dir / "selected_pair_forward_summary.json"
selected_summary_path.write_text(json.dumps(selected_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

baseline = {
    "command": [],
    "returncode": None,
    "wall_ms_from_subprocess": None,
    "stdout": "",
    "stderr": "",
    "summary_json": "",
    "summary": {},
}
if not selected_only:
    baseline = run_baseline_forward()
baseline_summary = baseline.get("summary") or {}
baseline_load_ms = float(baseline_summary.get("load_ms") or 0.0)
baseline_run_ms = float(baseline_summary.get("run_ms") or 0.0)
baseline_wall_ms = float(baseline_summary.get("wall_ms") or baseline.get("wall_ms_from_subprocess") or 0.0)
selected_warm_load_ms = float(selected_summary.get("forward_load_ms") or 0.0)
selected_total_load_ms = float(selected_summary.get("selected_total_load_ms") or 0.0)

errors = []
warnings = []
if selected_summary.get("verdict") != "ok_selected_pair_forward":
    errors.append(f"unexpected selected verdict: {selected_summary.get('verdict')}")
if not selected_only and baseline.get("returncode") != 0:
    errors.append(f"baseline forward returned {baseline.get('returncode')}")
if not selected_only and baseline_summary.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
    errors.append(f"unexpected baseline verdict: {baseline_summary.get('verdict')}")
if not selected_only and baseline_summary.get("batch_count") != batch_count:
    errors.append(f"unexpected baseline batch_count: {baseline_summary.get('batch_count')}")
expected_final_shapes = [[1, seq_len, vocab_size] for _ in range(batch_count)]
if selected_summary.get("final_shapes") != expected_final_shapes:
    errors.append(f"unexpected selected final_shapes: {selected_summary.get('final_shapes')}")
if selected_summary.get("final_shapes_by_job") != [expected_final_shapes for _ in range(job_count)]:
    errors.append(f"unexpected selected final_shapes_by_job: {selected_summary.get('final_shapes_by_job')}")

warm_load_ms_delta = None
total_load_ms_delta = None
warm_load_ms_delta_ratio = None
total_load_ms_delta_ratio = None
warm_path_load_improved = False
total_path_load_improved = False
if selected_only:
    warnings.append("baseline comparison skipped because DREAM7B_BPU_SELECTED_PAIR_ONLY=1")
else:
    warm_load_ms_delta = round(baseline_load_ms - selected_warm_load_ms, 3)
    total_load_ms_delta = round(baseline_load_ms - selected_total_load_ms, 3)
    warm_load_ms_delta_ratio = round(warm_load_ms_delta / baseline_load_ms, 6) if baseline_load_ms else 0.0
    total_load_ms_delta_ratio = round(total_load_ms_delta / baseline_load_ms, 6) if baseline_load_ms else 0.0
    warm_path_load_improved = warm_load_ms_delta > 0
    total_path_load_improved = total_load_ms_delta > 0
if not selected_only and warm_load_ms_delta <= 0:
    warnings.append(
        f"selected warm forward_load_ms did not improve baseline load_ms: baseline={baseline_load_ms}, selected_warm={selected_warm_load_ms}"
    )
if not selected_only and total_load_ms_delta <= 0:
    warnings.append(
        f"selected total load including resident startup did not improve baseline load_ms: baseline={baseline_load_ms}, selected_total={selected_total_load_ms}"
    )

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_forward_path_probe" if not errors else "failed_dream7b_bpu_selected_pair_forward_path_probe",
    "run_dir": str(run_dir),
    "triplet_json": str(triplet_json_path),
    "forward_cmd": forward_cmd,
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "job_count": job_count,
    "batch_count": batch_count,
    "processed_forward_count": selected_summary.get("processed_forward_count"),
    "top_k": top_k,
    "timeout_sec": timeout_sec,
    "selected_only": selected_only,
    "tokens_batch_json": str(tokens_batch_json),
    "tokens_batches_by_job_json": str(tokens_batches_by_job_json),
    "source_tokens_batch_json": tokens_batch_json_override,
    "source_tokens_batches_by_job_json": tokens_batches_by_job_json_override,
    "selected_summary_json": str(selected_summary_path),
    "selected": {
        "selected_pair": selected_summary.get("selected_pair"),
        "selected_segments": selected_summary.get("selected_segments"),
        "selected_third_segments": selected_summary.get("selected_third_segments"),
        "selected_pair_covers_all_segments": selected_summary.get("selected_pair_covers_all_segments"),
        "selected_worker_count": selected_summary.get("selected_worker_count"),
        "job_count": selected_summary.get("job_count"),
        "processed_forward_count": selected_summary.get("processed_forward_count"),
        "selected_resident_load_ms": selected_summary.get("selected_resident_load_ms"),
        "forward_load_ms": selected_summary.get("forward_load_ms"),
        "selected_total_load_ms": selected_summary.get("selected_total_load_ms"),
        "run_ms": selected_summary.get("run_ms"),
        "wall_ms": selected_summary.get("wall_ms"),
        "load_share_including_resident_load": selected_summary.get("load_share_including_resident_load"),
        "warm_load_share_excluding_resident_load": selected_summary.get("warm_load_share_excluding_resident_load"),
        "amortized_total_load_ms_per_forward": selected_summary.get("amortized_total_load_ms_per_forward"),
        "amortized_warm_load_ms_per_forward": selected_summary.get("amortized_warm_load_ms_per_forward"),
        "amortized_run_ms_per_forward": selected_summary.get("amortized_run_ms_per_forward"),
        "amortized_wall_ms_per_forward": selected_summary.get("amortized_wall_ms_per_forward"),
        "final_shapes": selected_summary.get("final_shapes"),
        "final_shapes_by_job": selected_summary.get("final_shapes_by_job"),
    },
    "baseline": {
        "summary_json": baseline.get("summary_json"),
        "returncode": baseline.get("returncode"),
        "verdict": baseline_summary.get("verdict"),
        "batch_count": baseline_summary.get("batch_count"),
        "execution_mode": baseline_summary.get("execution_mode"),
        "residency_window_size": baseline_summary.get("residency_window_size"),
        "window_execution_mode": baseline_summary.get("window_execution_mode"),
        "load_ms": round(baseline_load_ms, 3),
        "run_ms": round(baseline_run_ms, 3),
        "wall_ms": round(baseline_wall_ms, 3),
        "load_share": round(baseline_load_ms / max(baseline_wall_ms, 0.001), 6),
        "amortized_load_ms_per_forward": baseline_summary.get("amortized_load_ms_per_forward"),
        "amortized_run_ms_per_forward": baseline_summary.get("amortized_run_ms_per_forward"),
        "amortized_wall_ms_per_forward": baseline_summary.get("amortized_wall_ms_per_forward"),
    },
    "comparison": {
        "warm_load_ms_delta_vs_baseline": warm_load_ms_delta,
        "warm_load_ms_delta_ratio_vs_baseline": warm_load_ms_delta_ratio,
        "total_load_ms_delta_vs_baseline": total_load_ms_delta,
        "total_load_ms_delta_ratio_vs_baseline": total_load_ms_delta_ratio,
        "warm_path_load_improved": warm_path_load_improved,
        "total_path_load_improved": total_path_load_improved,
        "baseline_skipped": selected_only,
    },
    "next_optimization_target": "promote selected-pair worker path only after batch16 and telemetry probes confirm the warm-load reduction improves sustained BPU utilization",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "selected_pair_forward_path_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Selected Pair Forward Path Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- selected_pair: {payload['selected']['selected_pair']}",
    f"- selected_segments: {payload['selected']['selected_segments']}",
    f"- selected_pair_covers_all_segments: {payload['selected']['selected_pair_covers_all_segments']}",
    f"- job_count: {payload['job_count']}",
    f"- batch_count: {payload['batch_count']}",
    f"- processed_forward_count: {payload['processed_forward_count']}",
    f"- selected.forward_load_ms: {payload['selected']['forward_load_ms']}",
    f"- selected.selected_total_load_ms: {payload['selected']['selected_total_load_ms']}",
    f"- baseline.load_ms: {payload['baseline']['load_ms']}",
    f"- comparison.warm_load_ms_delta_vs_baseline: {payload['comparison']['warm_load_ms_delta_vs_baseline']}",
    f"- comparison.warm_load_ms_delta_ratio_vs_baseline: {payload['comparison']['warm_load_ms_delta_ratio_vs_baseline']}",
    f"- comparison.total_load_ms_delta_vs_baseline: {payload['comparison']['total_load_ms_delta_vs_baseline']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Warnings",
    "",
]
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(
    [
        "",
        "## Boundary",
        "",
        "- This probe runs a complete fine-adjacent forward path with the selected pair held as resident workers.",
        "- It is an experiment path and does not change the production `dream7b-bpu-fine-batch-forward` default.",
    ]
)
(run_dir / "selected_pair_forward_path_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "selected_pair_forward_path_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
