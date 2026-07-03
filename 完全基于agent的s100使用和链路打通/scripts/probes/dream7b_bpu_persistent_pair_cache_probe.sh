#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
worker_hold_seconds="${DREAM7B_BPU_PERSISTENT_PAIR_CACHE_WORKER_HOLD_SECONDS:-20}"
worker_ready_timeout_seconds="${DREAM7B_BPU_PERSISTENT_PAIR_CACHE_READY_TIMEOUT_SECONDS:-180}"
worker_start_delay_seconds="${DREAM7B_BPU_PERSISTENT_PAIR_CACHE_START_DELAY_SECONDS:-2}"

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
if ! [[ "$worker_hold_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_WORKER_HOLD_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$worker_ready_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_READY_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$worker_start_delay_seconds" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_PAIR_CACHE_START_DELAY_SECONDS must be a non-negative integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_persistent_pair_cache_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - \
  "$run_dir" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$worker_hold_seconds" \
  "$worker_ready_timeout_seconds" \
  "$worker_start_delay_seconds" <<'PY'
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
base_hbm_dir = Path(sys.argv[2])
fine_hbm_dir = Path(sys.argv[3])
worker_hold_seconds = int(sys.argv[4])
worker_ready_timeout_seconds = int(sys.argv[5])
worker_start_delay_seconds = int(sys.argv[6])

pair_windows = [
    {
        "pair_index": 0,
        "segments": ["seg00_02", "seg02_04"],
        "model_files": [
            str(fine_hbm_dir / "seg00_02/dream7b_segment_0_2_seq16_q8.hbm"),
            str(fine_hbm_dir / "seg02_04/dream7b_segment_2_4_seq16_q8.hbm"),
        ],
    },
    {
        "pair_index": 1,
        "segments": ["seg04_07", "seg07_10"],
        "model_files": [
            str(base_hbm_dir / "dream7b_segment_4_7_seq16_q8.hbm"),
            str(fine_hbm_dir / "seg07_10/dream7b_segment_7_10_seq16_q8.hbm"),
        ],
    },
    {
        "pair_index": 2,
        "segments": ["seg10_14", "seg14_17"],
        "model_files": [
            str(fine_hbm_dir / "seg10_14/dream7b_segment_10_14_seq16_q8.hbm"),
            str(fine_hbm_dir / "seg14_17/dream7b_segment_14_17_seq16_q8.hbm"),
        ],
    },
    {
        "pair_index": 3,
        "segments": ["seg17_21", "seg21_24"],
        "model_files": [
            str(fine_hbm_dir / "seg17_21/dream7b_segment_17_21_seq16_q8.hbm"),
            str(base_hbm_dir / "dream7b_segment_21_24_seq16_q8.hbm"),
        ],
    },
    {
        "pair_index": 4,
        "segments": ["seg24_26", "seg26_28"],
        "model_files": [
            str(fine_hbm_dir / "seg24_26/dream7b_segment_24_26_seq16_q8.hbm"),
            str(fine_hbm_dir / "seg26_28/dream7b_segment_26_28_seq16_q8.hbm"),
        ],
    },
]

missing = []
for pair in pair_windows:
    for model_file in pair["model_files"]:
        if not Path(model_file).exists():
            missing.append(model_file)
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
hold_seconds = int(payload["hold_seconds"])
started = time.perf_counter()
try:
    load_start = time.perf_counter()
    runtime = HB_HBMRuntime(payload["model_files"])
    load_end = time.perf_counter()
    ready = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "pair_index": payload["pair_index"],
        "segments": payload["segments"],
        "model_files": payload["model_files"],
        "status": "ready",
        "load_ms": round((load_end - load_start) * 1000, 3),
        "runtime_version": HB_HBMRuntime.version,
    }
    ready_path.write_text(json.dumps(ready, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    deadline = time.time() + hold_seconds
    while time.time() < deadline and not stop_path.exists():
        time.sleep(0.2)
    del runtime
except Exception as exc:
    failed = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "pair_index": payload["pair_index"],
        "segments": payload["segments"],
        "model_files": payload["model_files"],
        "status": "failed",
        "exception_type": type(exc).__name__,
        "exception": str(exc),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    ready_path.write_text(json.dumps(failed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise
"""

workers = []
stop_path = run_dir / "stop_workers"
launch_stopped_reason = ""
for pair in pair_windows:
    label = f"pair_{pair['pair_index']:02d}_{'__'.join(pair['segments'])}"
    payload_path = run_dir / f"{label}.payload.json"
    ready_path = run_dir / f"{label}.ready.json"
    stdout_path = run_dir / f"{label}.stdout"
    stderr_path = run_dir / f"{label}.stderr"
    payload = {
        **pair,
        "ready_path": str(ready_path),
        "stop_path": str(stop_path),
        "hold_seconds": worker_hold_seconds,
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stdout_fh = stdout_path.open("w", encoding="utf-8")
    stderr_fh = stderr_path.open("w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", worker_code, str(payload_path)], stdout=stdout_fh, stderr=stderr_fh)
    worker = {
        **pair,
        "label": label,
        "payload_path": str(payload_path),
        "ready_path": str(ready_path),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "process": proc,
        "stdout_fh": stdout_fh,
        "stderr_fh": stderr_fh,
    }
    workers.append(worker)
    deadline = time.time() + worker_ready_timeout_seconds
    worker_ready = False
    while time.time() < deadline:
        if ready_path.exists():
            try:
                ready_payload = json.loads(ready_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                ready_payload = {}
            worker_ready = ready_payload.get("status") == "ready"
            break
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    if not worker_ready:
        launch_stopped_reason = f"{label} did not reach ready status"
        break
    if worker_start_delay_seconds:
        time.sleep(worker_start_delay_seconds)

ready_records = []
for item in workers:
    path = Path(item["ready_path"])
    if path.exists():
        ready_records.append(json.loads(path.read_text(encoding="utf-8")))
    else:
        ready_records.append(
            {
                "pair_index": item["pair_index"],
                "segments": item["segments"],
                "model_files": item["model_files"],
                "status": "missing_ready_file",
            }
        )

ready_pair_indexes = sorted(item["pair_index"] for item in ready_records if item.get("status") == "ready")
failed_pair_indexes = sorted(item["pair_index"] for item in ready_records if item.get("status") != "ready")
returncodes_before_stop = {item["label"]: item["process"].poll() for item in workers}
stop_path.write_text("stop\n", encoding="utf-8")

for item in workers:
    try:
        item["process"].wait(timeout=15)
    except subprocess.TimeoutExpired:
        item["process"].kill()
        item["process"].wait(timeout=15)
    item["stdout_fh"].close()
    item["stderr_fh"].close()

returncodes_after_stop = {item["label"]: item["process"].returncode for item in workers}
worker_outputs = []
for item in workers:
    stderr_text = Path(item["stderr"]).read_text(encoding="utf-8", errors="replace")
    worker_outputs.append(
        {
            "label": item["label"],
            "pair_index": item["pair_index"],
            "segments": item["segments"],
            "model_files": item["model_files"],
            "ready_path": item["ready_path"],
            "stdout": item["stdout"],
            "stderr": item["stderr"],
            "returncode_before_stop": returncodes_before_stop[item["label"]],
            "returncode_after_stop": returncodes_after_stop[item["label"]],
            "stderr_preview": stderr_text[-2000:],
        }
    )

all_pair_workers_ready = len(ready_pair_indexes) == len(pair_windows)
if all_pair_workers_ready:
    next_optimization_target = "implement a persistent pair-worker forward pipeline and compare multi-step generation load amortization"
else:
    next_optimization_target = "do not implement all-pair persistent cache yet; use this failure boundary to guide a different split or runtime-residency strategy"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_persistent_pair_cache_probe",
    "run_dir": str(run_dir),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "worker_hold_seconds": worker_hold_seconds,
    "worker_ready_timeout_seconds": worker_ready_timeout_seconds,
    "worker_start_delay_seconds": worker_start_delay_seconds,
    "pair_worker_count": len(pair_windows),
    "launched_pair_worker_count": len(workers),
    "ready_pair_worker_count": len(ready_pair_indexes),
    "failed_pair_worker_count": len(failed_pair_indexes),
    "ready_pair_indexes": ready_pair_indexes,
    "failed_pair_indexes": failed_pair_indexes,
    "launch_stopped_reason": launch_stopped_reason,
    "all_pair_workers_ready": all_pair_workers_ready,
    "next_optimization_target": next_optimization_target,
    "ready_records": ready_records,
    "worker_outputs": worker_outputs,
    "errors": [],
}
(run_dir / "persistent_pair_cache_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Persistent Pair Cache Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- launched_pair_worker_count: {payload['launched_pair_worker_count']}",
    f"- ready_pair_worker_count: {payload['ready_pair_worker_count']}",
    f"- failed_pair_worker_count: {payload['failed_pair_worker_count']}",
    f"- launch_stopped_reason: {payload['launch_stopped_reason']}",
    f"- all_pair_workers_ready: {payload['all_pair_workers_ready']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Pair Workers",
    "",
    "| Pair index | Segments | Status | Load ms |",
    "| ---: | --- | --- | ---: |",
]
for item in ready_records:
    lines.append(
        f"| {item.get('pair_index')} | {', '.join(item.get('segments') or [])} | {item.get('status')} | {item.get('load_ms', '')} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This probe only tests whether all five packed fine pair runtimes can be held resident as long-lived workers.",
    "- It does not run a production text-generation service.",
    "- If `all_pair_workers_ready` is false, a persistent all-pair cache is not a valid short-term route for removing per-step HBM reload.",
])
(run_dir / "persistent_pair_cache_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "persistent_pair_cache_probe.md")
PY
