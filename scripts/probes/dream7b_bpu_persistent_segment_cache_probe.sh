#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
hold_seconds="${DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_WORKER_HOLD_SECONDS:-5}"
ready_timeout_seconds="${DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_READY_TIMEOUT_SECONDS:-180}"
start_delay_seconds="${DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_START_DELAY_SECONDS:-1}"

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

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi
if ! [[ "$hold_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_WORKER_HOLD_SECONDS must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$ready_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_READY_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$start_delay_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_START_DELAY_SECONDS must be a non-negative number." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_persistent_segment_cache_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - \
  "$run_dir" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$hold_seconds" \
  "$ready_timeout_seconds" \
  "$start_delay_seconds" <<'PY'
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
base_hbm_dir = Path(sys.argv[2])
fine_hbm_dir = Path(sys.argv[3])
hold_seconds = float(sys.argv[4])
ready_timeout_seconds = int(sys.argv[5])
start_delay_seconds = float(sys.argv[6])

segments = [
    {
        "segment_index": 0,
        "segment": "seg00_02",
        "model_file": str(fine_hbm_dir / "seg00_02/dream7b_segment_0_2_seq16_q8.hbm"),
    },
    {
        "segment_index": 1,
        "segment": "seg02_04",
        "model_file": str(fine_hbm_dir / "seg02_04/dream7b_segment_2_4_seq16_q8.hbm"),
    },
    {
        "segment_index": 2,
        "segment": "seg04_07",
        "model_file": str(base_hbm_dir / "dream7b_segment_4_7_seq16_q8.hbm"),
    },
    {
        "segment_index": 3,
        "segment": "seg07_10",
        "model_file": str(fine_hbm_dir / "seg07_10/dream7b_segment_7_10_seq16_q8.hbm"),
    },
    {
        "segment_index": 4,
        "segment": "seg10_14",
        "model_file": str(fine_hbm_dir / "seg10_14/dream7b_segment_10_14_seq16_q8.hbm"),
    },
    {
        "segment_index": 5,
        "segment": "seg14_17",
        "model_file": str(fine_hbm_dir / "seg14_17/dream7b_segment_14_17_seq16_q8.hbm"),
    },
    {
        "segment_index": 6,
        "segment": "seg17_21",
        "model_file": str(fine_hbm_dir / "seg17_21/dream7b_segment_17_21_seq16_q8.hbm"),
    },
    {
        "segment_index": 7,
        "segment": "seg21_24",
        "model_file": str(base_hbm_dir / "dream7b_segment_21_24_seq16_q8.hbm"),
    },
    {
        "segment_index": 8,
        "segment": "seg24_26",
        "model_file": str(fine_hbm_dir / "seg24_26/dream7b_segment_24_26_seq16_q8.hbm"),
    },
    {
        "segment_index": 9,
        "segment": "seg26_28",
        "model_file": str(fine_hbm_dir / "seg26_28/dream7b_segment_26_28_seq16_q8.hbm"),
    },
]

missing = [item["model_file"] for item in segments if not Path(item["model_file"]).exists()]
if missing:
    raise SystemExit("missing HBM files: " + ", ".join(missing))

worker_code = r"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from hbm_runtime import HB_HBMRuntime

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ready_path = Path(payload["ready_path"])
stop_path = Path(payload["stop_path"])
try:
    load_start = time.perf_counter()
    runtime = HB_HBMRuntime([payload["model_file"]])
    load_end = time.perf_counter()
    ready_path.write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(),
        "segment_index": payload["segment_index"],
        "segment": payload["segment"],
        "status": "ready",
        "load_ms": round((load_end - load_start) * 1000, 3),
        "runtime_version": HB_HBMRuntime.version,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    while not stop_path.exists():
        time.sleep(0.2)
    del runtime
except Exception as exc:
    ready_path.write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(),
        "segment_index": payload["segment_index"],
        "segment": payload["segment"],
        "status": "failed",
        "exception_type": type(exc).__name__,
        "exception": str(exc),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise
"""

def launch_worker(segment):
    label = f"segment_{segment['segment_index']:02d}_{segment['segment']}"
    payload_path = run_dir / f"{label}.payload.json"
    ready_path = run_dir / f"{label}.ready.json"
    stop_path = run_dir / f"{label}.stop"
    stdout_path = run_dir / f"{label}.stdout"
    stderr_path = run_dir / f"{label}.stderr"
    payload = {
        **segment,
        "ready_path": str(ready_path),
        "stop_path": str(stop_path),
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stdout_fh = stdout_path.open("w", encoding="utf-8")
    stderr_fh = stderr_path.open("w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", worker_code, str(payload_path)], stdout=stdout_fh, stderr=stderr_fh)
    deadline = time.time() + ready_timeout_seconds
    ready_record = None
    while time.time() < deadline:
        if ready_path.exists():
            ready_record = json.loads(ready_path.read_text(encoding="utf-8"))
            break
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    if ready_record is None:
        ready_record = {
            "segment_index": segment["segment_index"],
            "segment": segment["segment"],
            "status": "missing_ready_file",
        }
    return {
        "segment": segment,
        "label": label,
        "process": proc,
        "stdout_fh": stdout_fh,
        "stderr_fh": stderr_fh,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "stop_path": stop_path,
        "ready_record": ready_record,
    }

def stop_worker(worker):
    worker["stop_path"].write_text("stop\n", encoding="utf-8")
    try:
        worker["process"].wait(timeout=15)
    except subprocess.TimeoutExpired:
        worker["process"].kill()
        worker["process"].wait(timeout=15)
    worker["stdout_fh"].close()
    worker["stderr_fh"].close()

workers = []
records = []
launch_stopped_reason = ""
try:
    for segment in segments:
        worker = launch_worker(segment)
        workers.append(worker)
        record = worker["ready_record"]
        records.append(record)
        if record.get("status") != "ready":
            launch_stopped_reason = f"segment_{segment['segment_index']:02d}_{segment['segment']} did not reach ready status"
            break
        if start_delay_seconds:
            time.sleep(start_delay_seconds)
    if hold_seconds:
        time.sleep(hold_seconds)
finally:
    for worker in reversed(workers):
        stop_worker(worker)

ready_records = [item for item in records if item.get("status") == "ready"]
failed_records = [item for item in records if item.get("status") != "ready"]
ready_segment_indexes = [item["segment_index"] for item in ready_records]
failed_segment_indexes = [item["segment_index"] for item in failed_records if "segment_index" in item]
all_segment_workers_ready = len(ready_records) == len(segments) and not failed_records
if all_segment_workers_ready:
    next_optimization_target = "implement a single-segment persistent worker pipeline and measure whether HBM reload share drops under real forward/generation traffic"
else:
    next_optimization_target = "use the ready prefix and failure record to choose a smaller segment split or different runtime-residency strategy"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_persistent_segment_cache_probe",
    "run_dir": str(run_dir),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "hold_seconds": hold_seconds,
    "ready_timeout_seconds": ready_timeout_seconds,
    "start_delay_seconds": start_delay_seconds,
    "segment_worker_count": len(segments),
    "launched_segment_worker_count": len(records),
    "ready_segment_worker_count": len(ready_records),
    "failed_segment_worker_count": len(failed_records),
    "ready_segment_indexes": ready_segment_indexes,
    "failed_segment_indexes": failed_segment_indexes,
    "all_segment_workers_ready": all_segment_workers_ready,
    "launch_stopped_reason": launch_stopped_reason,
    "max_resident_segment_count_observed": len(ready_records),
    "next_optimization_target": next_optimization_target,
    "ready_records": ready_records,
    "failed_records": failed_records,
    "records": records,
    "errors": [],
}
(run_dir / "persistent_segment_cache_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Persistent Segment Cache Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- segment_worker_count: {payload['segment_worker_count']}",
    f"- launched_segment_worker_count: {payload['launched_segment_worker_count']}",
    f"- ready_segment_worker_count: {payload['ready_segment_worker_count']}",
    f"- failed_segment_worker_count: {payload['failed_segment_worker_count']}",
    f"- all_segment_workers_ready: {payload['all_segment_workers_ready']}",
    f"- launch_stopped_reason: {payload['launch_stopped_reason']}",
    f"- max_resident_segment_count_observed: {payload['max_resident_segment_count_observed']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Records",
    "",
    "| Segment index | Segment | Status | Load ms | Exception |",
    "| ---: | --- | --- | ---: | --- |",
]
for item in records:
    exception = (item.get("exception") or "").replace("|", "/")
    lines.append(f"| {item.get('segment_index')} | {item.get('segment')} | {item.get('status')} | {item.get('load_ms', '')} | {exception} |")
lines.extend([
    "",
    "## Boundary",
    "",
    "- This probe tests simultaneous single-segment HBM runtime residency only; it does not run inference or a production text service.",
    "- A fully ready result is a prerequisite for attempting a persistent single-segment worker pipeline.",
])
(run_dir / "persistent_segment_cache_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "persistent_segment_cache_probe.md")
PY
