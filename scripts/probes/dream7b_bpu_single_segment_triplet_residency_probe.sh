#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
ready_timeout_seconds="${DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_READY_TIMEOUT_SECONDS:-180}"
start_delay_seconds="${DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_START_DELAY_SECONDS:-0}"
max_combinations="${DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_MAX_COMBINATIONS:-120}"

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
if ! [[ "$ready_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_READY_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$start_delay_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_START_DELAY_SECONDS must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$max_combinations" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_MAX_COMBINATIONS must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_single_segment_triplet_residency_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - \
  "$run_dir" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$ready_timeout_seconds" \
  "$start_delay_seconds" \
  "$max_combinations" <<'PY'
import itertools
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
base_hbm_dir = Path(sys.argv[2])
fine_hbm_dir = Path(sys.argv[3])
ready_timeout_seconds = int(sys.argv[4])
start_delay_seconds = float(sys.argv[5])
max_combinations = int(sys.argv[6])

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

def launch_worker(segment, label_prefix):
    label = f"{label_prefix}_segment_{segment['segment_index']:02d}_{segment['segment']}"
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

combination_records = []
combinations = list(itertools.combinations(segments, 3))[:max_combinations]
for combo_index, combo in enumerate(combinations):
    workers = []
    records = []
    label_prefix = "combo_{:03d}_{}".format(combo_index, "_".join(str(item["segment_index"]) for item in combo))
    try:
        for segment in combo:
            worker = launch_worker(segment, label_prefix)
            workers.append(worker)
            records.append(worker["ready_record"])
            if worker["ready_record"].get("status") != "ready":
                break
            if start_delay_seconds:
                time.sleep(start_delay_seconds)
    finally:
        for worker in reversed(workers):
            stop_worker(worker)
    ready_records = [item for item in records if item.get("status") == "ready"]
    failed_records = [item for item in records if item.get("status") != "ready"]
    combination_records.append(
        {
            "combination_index": combo_index,
            "segment_indexes": [item["segment_index"] for item in combo],
            "segments": [item["segment"] for item in combo],
            "attempted_worker_count": len(records),
            "ready_segment_count": len(ready_records),
            "failed_segment_count": len(failed_records),
            "ok": len(ready_records) == 3 and not failed_records,
            "records": records,
        }
    )

successful_records = [item for item in combination_records if item.get("ok") is True]
failed_records = [item for item in combination_records if item.get("ok") is not True]
max_resident_segment_count_observed = max([item.get("ready_segment_count", 0) for item in combination_records] or [0])
if successful_records:
    next_optimization_target = "inspect successful triplets and then test a persistent topology seeded by those segment groups"
else:
    next_optimization_target = "no tested single-segment triplet is resident; reduce HBM artifact size or change compiler/runtime residency before building a persistent worker pipeline"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_single_segment_triplet_residency_probe",
    "run_dir": str(run_dir),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "ready_timeout_seconds": ready_timeout_seconds,
    "start_delay_seconds": start_delay_seconds,
    "max_combinations": max_combinations,
    "segment_count": len(segments),
    "total_triplet_combination_count": 120,
    "tested_triplet_combination_count": len(combination_records),
    "successful_triplet_count": len(successful_records),
    "failed_triplet_count": len(failed_records),
    "successful_triplets": [item["segment_indexes"] for item in successful_records],
    "failed_triplets": [item["segment_indexes"] for item in failed_records],
    "max_resident_segment_count_observed": max_resident_segment_count_observed,
    "next_optimization_target": next_optimization_target,
    "combination_records": combination_records,
    "errors": [],
}
(run_dir / "single_segment_triplet_residency_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Single Segment Triplet Residency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- tested_triplet_combination_count: {payload['tested_triplet_combination_count']}",
    f"- successful_triplet_count: {payload['successful_triplet_count']}",
    f"- failed_triplet_count: {payload['failed_triplet_count']}",
    f"- max_resident_segment_count_observed: {payload['max_resident_segment_count_observed']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Combination Records",
    "",
    "| Combination | Segments | OK | Ready | Failed | First failure |",
    "| ---: | --- | --- | ---: | ---: | --- |",
]
for item in combination_records:
    first_failure = next((record for record in item["records"] if record.get("status") != "ready"), {})
    failure_text = ""
    if first_failure:
        failure_text = "{}: {}".format(first_failure.get("segment"), first_failure.get("exception", first_failure.get("status", ""))).replace("|", "/")
    lines.append(
        f"| {item['combination_index']} | {', '.join(item['segments'])} | {item['ok']} | "
        f"{item['ready_segment_count']} | {item['failed_segment_count']} | {failure_text} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This probe tests simultaneous three-single-segment HBM runtime residency only; it does not run inference or a production text service.",
    "- A successful triplet is a prerequisite for testing larger persistent segment worker topologies.",
])
(run_dir / "single_segment_triplet_residency_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "single_segment_triplet_residency_probe.md")
PY
