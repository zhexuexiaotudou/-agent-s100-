#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
tokens="${2:-1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}"
batch_count="${3:-3}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"

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

if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "batch_count must be a positive integer: $batch_count" >&2
  exit 2
fi

if (( batch_count > 10 )); then
  echo "batch_count must be <= 10 for this bounded probe: $batch_count" >&2
  exit 2
fi

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_fine_forward_window_batch_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - "$run_dir" "$tokens" "$batch_count" "$base_hbm_dir" "$fine_hbm_dir" <<'PY'
import gc
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from hbm_runtime import HB_HBMRuntime

run_dir = Path(sys.argv[1])
token_text = sys.argv[2]
batch_count = int(sys.argv[3])
base_hbm_dir = Path(sys.argv[4])
fine_hbm_dir = Path(sys.argv[5])
seq_len = 16
vocab_size = 152064

fine_adjacent_segments = [
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


def parse_tokens(text):
    values = [int(part, 0) for part in text.replace(",", " ").split() if part]
    if len(values) != seq_len:
        raise ValueError(f"Expected {seq_len} token ids, got {len(values)}")
    return np.asarray(values, dtype=np.int32).reshape(1, seq_len)


def first_scale(runtime, model_name, output_name):
    quant = runtime.output_quants[model_name][output_name]
    scale = np.asarray(quant.scale).reshape(-1)
    if scale.size == 0:
        return 1.0
    return float(scale[0])


position_ids = np.arange(seq_len, dtype=np.int32)
base_tokens = parse_tokens(token_text)
current_inputs = [base_tokens.copy() for _ in range(batch_count)]
windows = []
start_ns = time.perf_counter_ns()

for index in range(0, len(fine_adjacent_segments), 2):
    pair = fine_adjacent_segments[index:index + 2]
    model_files = [str(item[2]) for item in pair]
    for _, _, model_file, _, _ in pair:
        if not model_file.exists():
            raise FileNotFoundError(model_file)
    t0 = time.perf_counter()
    runtime = HB_HBMRuntime(model_files)
    t1 = time.perf_counter()
    load_ms = round((t1 - t0) * 1000, 3)
    segment_events = []
    try:
        for batch_index in range(batch_count):
            dequantized = current_inputs[batch_index]
            for segment_id, source, model_file, model_name, input_kind in pair:
                inputs = {"_input_0": dequantized, "_input_1": position_ids}
                t2 = time.perf_counter()
                output = runtime.run(inputs, model_name=model_name)
                t3 = time.perf_counter()
                output_name = runtime.output_names[model_name][0]
                arr = output[model_name][output_name]
                scale = first_scale(runtime, model_name, output_name)
                dequantized = arr.astype(np.float32) * scale
                segment_events.append(
                    {
                        "batch_index": batch_index,
                        "segment": segment_id,
                        "source": source,
                        "input_kind": input_kind,
                        "model_name": model_name,
                        "model_file": str(model_file),
                        "output_name": output_name,
                        "output_shape": list(arr.shape),
                        "output_dtype": str(arr.dtype),
                        "output_scale": scale,
                        "run_ms": round((t3 - t2) * 1000, 3),
                    }
                )
                del output, arr
            current_inputs[batch_index] = dequantized
    finally:
        del runtime
        gc.collect()

    windows.append(
        {
            "window_index": index // 2,
            "resident_segments": [item[0] for item in pair],
            "packed_load_ms": load_ms,
            "batch_count": batch_count,
            "segment_events": segment_events,
        }
    )

end_ns = time.perf_counter_ns()
final_shapes = [list(item.shape) for item in current_inputs]
errors = []
for batch_index, shape in enumerate(final_shapes):
    if shape != [1, seq_len, vocab_size]:
        errors.append(f"batch {batch_index} final_shape={shape}")
expected_segment_events = batch_count * len(fine_adjacent_segments)
actual_segment_events = sum(len(item["segment_events"]) for item in windows)
if actual_segment_events != expected_segment_events:
    errors.append(f"expected {expected_segment_events} segment events, got {actual_segment_events}")

load_ms = round(sum(float(item["packed_load_ms"]) for item in windows), 3)
run_ms = round(sum(float(event["run_ms"]) for item in windows for event in item["segment_events"]), 3)
wall_ms = round((end_ns - start_ns) / 1_000_000.0, 3)
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_fine_forward_window_batch_probe" if not errors else "failed_dream7b_bpu_fine_forward_window_batch_probe",
    "run_dir": str(run_dir),
    "batch_count": batch_count,
    "segment_plan": "fine-adjacent",
    "residency_window_size": 2,
    "child_window_mode": "pair",
    "child_runtime_mode": "packed",
    "window_execution_mode": "window-batch",
    "execution_mode": "pair_window_batch",
    "child_process_count": 0,
    "window_count": len(windows),
    "segment_count": len(fine_adjacent_segments),
    "total_segment_events": actual_segment_events,
    "final_shapes": final_shapes,
    "wall_ms": wall_ms,
    "load_ms": load_ms,
    "run_ms": run_ms,
    "amortized_load_ms_per_forward": round(load_ms / batch_count, 3),
    "amortized_wall_ms_per_forward": round(wall_ms / batch_count, 3),
    "errors": errors,
    "windows": windows,
    "notes": [
        "This probe runs multiple independent seq16 token inputs in window-major order.",
        "It loads each resident pair once, runs that pair for every batch item, then releases the runtime.",
        "It proves a batching/throughput direction for concurrent requests, not a single-request diffusion-step speedup.",
    ],
}
(run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Fine Forward Window Batch Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- batch_count: {payload['batch_count']}",
    f"- execution_mode: {payload['execution_mode']}",
    f"- window_execution_mode: {payload['window_execution_mode']}",
    f"- child_process_count: {payload['child_process_count']}",
    f"- window_count: {payload['window_count']}",
    f"- total_segment_events: {payload['total_segment_events']}",
    f"- wall_ms: {payload['wall_ms']}",
    f"- load_ms: {payload['load_ms']}",
    f"- run_ms: {payload['run_ms']}",
    f"- amortized_load_ms_per_forward: {payload['amortized_load_ms_per_forward']}",
    f"- amortized_wall_ms_per_forward: {payload['amortized_wall_ms_per_forward']}",
    f"- final_shapes: {payload['final_shapes']}",
    "",
    "## Windows",
    "",
    "| Window | Resident segments | Packed load ms | Segment events |",
    "| ---: | --- | ---: | ---: |",
]
for item in windows:
    lines.append(
        f"| {item['window_index']} | {item['resident_segments']} | {item['packed_load_ms']:.3f} | {len(item['segment_events'])} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This is a bounded throughput probe for independent seq16 inputs.",
    "- It does not reduce reload cost for a single dependent Dream diffusion request.",
])
(run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "summary.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
