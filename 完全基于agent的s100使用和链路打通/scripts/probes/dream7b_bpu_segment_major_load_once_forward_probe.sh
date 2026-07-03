#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
job_count="${DREAM7B_BPU_SEGMENT_MAJOR_JOB_COUNT:-4}"
batch_count="${DREAM7B_BPU_SEGMENT_MAJOR_BATCH_COUNT:-192}"
job_count_limit="${DREAM7B_BPU_SEGMENT_MAJOR_JOB_COUNT_LIMIT:-12}"
batch_count_limit="${DREAM7B_BPU_SEGMENT_MAJOR_BATCH_COUNT_LIMIT:-256}"
top_k="${DREAM7B_BPU_SEGMENT_MAJOR_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_TIMEOUT_SEC:-1800}"
monitor_delay_ms="${DREAM7B_BPU_SEGMENT_MAJOR_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_SEGMENT_MAJOR_MONITOR_SAMPLE_COUNT:-18000}"
bpu_lock_path="${DREAM7B_BPU_SEGMENT_MAJOR_BPU_LOCK_PATH:-/run/lock/dream7b_bpu_batch_queue_runner.lock}"
bpu_lock_timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_BPU_LOCK_TIMEOUT_SEC:-600}"
baseline_load_to_run_ratio="${DREAM7B_BPU_SEGMENT_MAJOR_BASELINE_LOAD_TO_RUN_RATIO:-0.732649}"
stage3_target_load_to_run_ratio="${DREAM7B_BPU_SEGMENT_MAJOR_STAGE3_TARGET_LOAD_TO_RUN_RATIO:-0.35}"
stage5_target_load_to_run_ratio="${DREAM7B_BPU_SEGMENT_MAJOR_STAGE5_TARGET_LOAD_TO_RUN_RATIO:-0.15}"

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

case "$bpu_lock_path" in
  /tmp/*|/run/lock/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing BPU lock path outside approved directories: $bpu_lock_path" >&2
    exit 2
    ;;
esac

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi
if ! [[ "$job_count_limit" =~ ^[1-9][0-9]*$ ]] || (( job_count_limit < 1 || job_count_limit > 24 )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_JOB_COUNT_LIMIT must be 1..24." >&2
  exit 2
fi
if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 1 || job_count > job_count_limit )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_JOB_COUNT must be 1..$job_count_limit." >&2
  exit 2
fi
if ! [[ "$batch_count_limit" =~ ^[1-9][0-9]*$ ]] || (( batch_count_limit < 1 || batch_count_limit > 256 )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_BATCH_COUNT_LIMIT must be 1..256." >&2
  exit 2
fi
if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count < 1 || batch_count > batch_count_limit )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_BATCH_COUNT must be 1..$batch_count_limit." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$bpu_lock_timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_BPU_LOCK_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi
if ! command -v flock >/dev/null 2>&1; then
  echo "Missing deployed command: flock" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_segment_major_load_once_forward_$stamp"
mkdir -p "$run_dir"

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
python_stdout="$run_dir/segment_major.stdout"
python_stderr="$run_dir/segment_major.stderr"
summary_json="$run_dir/segment_major_load_once_forward_probe.json"

hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"

cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup_monitor EXIT

exec 9>"$bpu_lock_path"
if ! flock -w "$bpu_lock_timeout_sec" 9; then
  echo "Timed out waiting for BPU lock: $bpu_lock_path" >&2
  exit 5
fi

set +e
"$venv/bin/python" - \
  "$run_dir" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$job_count" \
  "$batch_count" \
  "$top_k" \
  "$timeout_sec" \
  "$baseline_load_to_run_ratio" \
  "$stage3_target_load_to_run_ratio" \
  "$stage5_target_load_to_run_ratio" > "$python_stdout" 2> "$python_stderr" <<'PY'
import gc
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from hbm_runtime import HB_HBMRuntime

run_dir = Path(sys.argv[1])
base_hbm_dir = Path(sys.argv[2])
fine_hbm_dir = Path(sys.argv[3])
job_count = int(sys.argv[4])
batch_count = int(sys.argv[5])
top_k = int(sys.argv[6])
timeout_sec = int(sys.argv[7])
baseline_load_to_run_ratio = float(sys.argv[8])
stage3_target_load_to_run_ratio = float(sys.argv[9])
stage5_target_load_to_run_ratio = float(sys.argv[10])

deadline = time.monotonic() + timeout_sec
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

def check_deadline():
    if time.monotonic() >= deadline:
        raise TimeoutError(f"segment-major forward timed out after {timeout_sec} seconds")

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

records = []
for job_index in range(job_count):
    for batch_index in range(batch_count):
        ordinal = job_index * batch_count + batch_index
        base = 1000 + ((ordinal * 17) % 120000)
        tokens = np.asarray([base + offset for offset in range(1, seq_len + 1)], dtype=np.int32).reshape(1, seq_len)
        records.append({"job_index": job_index, "batch_index": batch_index, "state": tokens})

errors = []
warnings = []
segment_results = []
topk_results = []
final_shape_counts = {}
total_load_ms = 0.0
total_run_ms = 0.0
started = time.perf_counter()
peak_live_bytes = 0

try:
    for segment_index, (segment_id, source, model_file, model_name, input_kind) in enumerate(segments):
        check_deadline()
        load_start = time.perf_counter()
        runtime = HB_HBMRuntime(str(model_file))
        load_end = time.perf_counter()
        load_ms = round((load_end - load_start) * 1000, 3)
        total_load_ms += load_ms
        segment_run_ms = 0.0
        segment_started = time.perf_counter()
        try:
            for record in records:
                check_deadline()
                output, result = run_loaded_segment(runtime, model_file, model_name, record["state"])
                segment_run_ms += float(result["run_ms"])
                total_run_ms += float(result["run_ms"])
                if segment_index == len(segments) - 1:
                    shape = list(output.shape)
                    final_shape_counts[str(shape)] = final_shape_counts.get(str(shape), 0) + 1
                    if shape != [1, seq_len, vocab_size]:
                        errors.append(f"unexpected final shape for job={record['job_index']} batch={record['batch_index']}: {shape}")
                    if top_k > 0:
                        last = output[0, -1].astype(np.float32, copy=False)
                        k = min(top_k, int(last.shape[0]))
                        indices = np.argpartition(last, -k)[-k:]
                        indices = indices[np.argsort(last[indices])[::-1]]
                        if len(topk_results) < 8:
                            topk_results.append(
                                {
                                    "job_index": record["job_index"],
                                    "batch_index": record["batch_index"],
                                    "topk_last_position": [
                                        {"token_id": int(idx), "score": float(last[idx])} for idx in indices
                                    ],
                                }
                            )
                    record["state"] = None
                    del output
                else:
                    record["state"] = output
                result.update(
                    {
                        "segment_index": segment_index,
                        "segment": segment_id,
                        "source": source,
                        "load_ms": load_ms if record["job_index"] == 0 and record["batch_index"] == 0 else 0.0,
                    }
                )
                segment_results.append(result)
            live_bytes = sum(
                int(record["state"].nbytes)
                for record in records
                if isinstance(record.get("state"), np.ndarray)
            )
            peak_live_bytes = max(peak_live_bytes, live_bytes)
        finally:
            del runtime
            gc.collect()
        segment_wall_ms = round((time.perf_counter() - segment_started) * 1000, 3)
        progress = {
            "segment_index": segment_index,
            "segment": segment_id,
            "load_ms": load_ms,
            "segment_run_ms": round(segment_run_ms, 3),
            "segment_wall_ms": segment_wall_ms,
            "processed_forward_count": len(records),
            "peak_live_bytes": peak_live_bytes,
        }
        (run_dir / f"segment_{segment_index:02d}_progress.json").write_text(
            json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
except Exception as exc:
    errors.append(f"{type(exc).__name__}: {exc}")

wall_ms = round((time.perf_counter() - started) * 1000, 3)
processed_forward_count = job_count * batch_count if not errors else sum(final_shape_counts.values())
load_to_run_ratio = round(total_load_ms / total_run_ms, 6) if total_run_ms else None
baseline_delta = round(load_to_run_ratio - baseline_load_to_run_ratio, 6) if load_to_run_ratio is not None else None
load_event_count = len(segments)
job_major_equivalent_load_event_count = 2 + (len(segments) - 2) * job_count
load_event_reduction_ratio = round(1.0 - (load_event_count / job_major_equivalent_load_event_count), 6)

decision = "segment_major_load_once_incomplete"
if not errors:
    decision = "segment_major_load_once_progress_candidate"
    if load_to_run_ratio is not None and load_to_run_ratio <= stage3_target_load_to_run_ratio:
        decision = "segment_major_load_once_meets_stage3_ratio_gate"
    if load_to_run_ratio is not None and load_to_run_ratio <= stage5_target_load_to_run_ratio:
        decision = "segment_major_load_once_meets_90pct_ratio_gate"
if load_to_run_ratio is not None and load_to_run_ratio > stage3_target_load_to_run_ratio:
    warnings.append(f"load_to_run_ratio {load_to_run_ratio} remains above Stage 3 target {stage3_target_load_to_run_ratio}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_segment_major_load_once_forward_probe" if not errors else "failed_dream7b_bpu_segment_major_load_once_forward_probe",
    "decision": decision,
    "run_dir": str(run_dir),
    "segment_major_load_once": True,
    "job_major_baseline_replaced": False,
    "job_count": job_count,
    "batch_count": batch_count,
    "processed_forward_count": processed_forward_count,
    "seq_len": seq_len,
    "segment_count": len(segments),
    "load_event_count": load_event_count,
    "job_major_equivalent_load_event_count": job_major_equivalent_load_event_count,
    "load_event_reduction_ratio": load_event_reduction_ratio,
    "total_load_ms": round(total_load_ms, 3),
    "total_run_ms": round(total_run_ms, 3),
    "wall_ms": wall_ms,
    "load_to_run_ratio": load_to_run_ratio,
    "baseline_load_to_run_ratio": baseline_load_to_run_ratio,
    "load_to_run_ratio_delta_vs_baseline": baseline_delta,
    "stage3_target_load_to_run_ratio": stage3_target_load_to_run_ratio,
    "stage5_target_load_to_run_ratio": stage5_target_load_to_run_ratio,
    "amortized_load_ms_per_forward": round(total_load_ms / processed_forward_count, 3) if processed_forward_count else None,
    "amortized_run_ms_per_forward": round(total_run_ms / processed_forward_count, 3) if processed_forward_count else None,
    "amortized_wall_ms_per_forward": round(wall_ms / processed_forward_count, 3) if processed_forward_count else None,
    "peak_live_bytes": peak_live_bytes,
    "peak_live_mib": round(peak_live_bytes / (1024 * 1024), 3),
    "final_shape_counts": final_shape_counts,
    "topk_sample": topk_results,
    "segment_results_count": len(segment_results),
    "segment_loads": [
        {
            "segment_index": index,
            "segment": segment[0],
            "source": segment[1],
            "model_file": str(segment[2]),
        }
        for index, segment in enumerate(segments)
    ],
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "segment_major_load_once_forward_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

lines = [
    "# Dream 7B Segment-Major Load-Once Forward Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- decision: {payload['decision']}",
    f"- job_count: {payload['job_count']}",
    f"- batch_count: {payload['batch_count']}",
    f"- processed_forward_count: {payload['processed_forward_count']}",
    f"- load_event_count: {payload['load_event_count']}",
    f"- job_major_equivalent_load_event_count: {payload['job_major_equivalent_load_event_count']}",
    f"- load_event_reduction_ratio: {payload['load_event_reduction_ratio']}",
    f"- total_load_ms: {payload['total_load_ms']}",
    f"- total_run_ms: {payload['total_run_ms']}",
    f"- wall_ms: {payload['wall_ms']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- load_to_run_ratio_delta_vs_baseline: {payload['load_to_run_ratio_delta_vs_baseline']}",
    f"- amortized_wall_ms_per_forward: {payload['amortized_wall_ms_per_forward']}",
    f"- peak_live_mib: {payload['peak_live_mib']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "segment_major_load_once_forward_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "segment_major_load_once_forward_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
python_rc="$?"
set -e

cleanup_monitor
trap - EXIT

"$venv/bin/python" - \
  "$run_dir" \
  "$summary_json" \
  "$monitor_stdout" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" <<'PY'
import json
import re
import statistics
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
summary_json = Path(sys.argv[2])
monitor_stdout = Path(sys.argv[3])
monitor_delay_ms = int(sys.argv[4])
monitor_sample_count = int(sys.argv[5])

payload = json.loads(summary_json.read_text(encoding="utf-8")) if summary_json.is_file() else {
    "verdict": "failed_dream7b_bpu_segment_major_load_once_forward_probe",
    "errors": ["missing segment major summary json"],
}
monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.is_file() else ""
samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
avg_bpu = statistics.fmean(samples) if samples else 0.0
max_bpu = max(samples) if samples else 0.0
nonzero = sum(1 for item in samples if item > 0.0)
payload.update(
    {
        "monitor_delay_ms": monitor_delay_ms,
        "monitor_sample_count": monitor_sample_count,
        "bpu_loading_sample_count": len(samples),
        "nonzero_bpu_loading_sample_count": nonzero,
        "avg_bpu_loading": round(avg_bpu, 3),
        "max_bpu_loading": round(max_bpu, 3),
    }
)
if not samples:
    payload.setdefault("errors", []).append("hrt_ucp_monitor produced no BPU0 loading samples")
elif nonzero <= 0:
    payload.setdefault("errors", []).append("hrt_ucp_monitor produced no nonzero BPU0 loading samples")
if payload.get("errors"):
    payload["verdict"] = "failed_dream7b_bpu_segment_major_load_once_forward_probe"
summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

md = run_dir / "segment_major_load_once_forward_probe.md"
lines = md.read_text(encoding="utf-8").splitlines() if md.is_file() else ["# Dream 7B Segment-Major Load-Once Forward Probe", ""]
insert = [
    "",
    "## BPU Telemetry",
    "",
    f"- avg_bpu_loading: {payload.get('avg_bpu_loading')}",
    f"- max_bpu_loading: {payload.get('max_bpu_loading')}",
    f"- bpu_loading_sample_count: {payload.get('bpu_loading_sample_count')}",
    f"- nonzero_bpu_loading_sample_count: {payload.get('nonzero_bpu_loading_sample_count')}",
]
lines.extend(insert)
md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md)
if payload.get("errors"):
    raise SystemExit("; ".join(payload["errors"]))
PY

exit "$python_rc"
