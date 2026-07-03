#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
triplet_json="${DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_TRIPLET_JSON:-}"
hold_seconds="${DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_HOLD_SECONDS:-10}"
ready_timeout_seconds="${DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_READY_TIMEOUT_SECONDS:-180}"
poll_interval_seconds="${DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_POLL_INTERVAL_SECONDS:-2}"
start_delay_seconds="${DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_START_DELAY_SECONDS:-0}"
max_triplets="${DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_MAX_TRIPLETS:-20}"

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
  echo "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_HOLD_SECONDS must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$ready_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_READY_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$poll_interval_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_POLL_INTERVAL_SECONDS must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$start_delay_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_START_DELAY_SECONDS must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$max_triplets" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_MAX_TRIPLETS must be a positive integer." >&2
  exit 2
fi
if [[ -n "$triplet_json" ]]; then
  case "$triplet_json" in
    /tmp/*|/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_*/*|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing triplet JSON path outside approved report directories: $triplet_json" >&2
      exit 2
      ;;
  esac
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_persistent_triplet_topology_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - \
  "$run_dir" \
  "$report_root" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$triplet_json" \
  "$hold_seconds" \
  "$ready_timeout_seconds" \
  "$poll_interval_seconds" \
  "$start_delay_seconds" \
  "$max_triplets" <<'PY'
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
base_hbm_dir = Path(sys.argv[3])
fine_hbm_dir = Path(sys.argv[4])
triplet_json_arg = sys.argv[5]
hold_seconds = float(sys.argv[6])
ready_timeout_seconds = int(sys.argv[7])
poll_interval_seconds = float(sys.argv[8])
start_delay_seconds = float(sys.argv[9])
max_triplets = int(sys.argv[10])


def latest_triplet_json():
    if triplet_json_arg:
        path = Path(triplet_json_arg)
        if not path.is_file():
            raise SystemExit(f"missing DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_TRIPLET_JSON: {path}")
        return path
    paths = list(report_root.glob("dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json"))
    paths = [path for path in paths if path.is_file()]
    if not paths:
        raise SystemExit("missing triplet residency report for persistent triplet topology probe")
    return max(paths, key=lambda path: path.stat().st_mtime)


triplet_json_path = latest_triplet_json()
triplet_report = json.loads(triplet_json_path.read_text(encoding="utf-8"))
source_successful_triplets = triplet_report.get("successful_triplets") or []
if not source_successful_triplets:
    raise SystemExit("triplet report has no successful_triplets")

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
segment_by_index = {item["segment_index"]: item for item in segments}

missing = [item["model_file"] for item in segments if not Path(item["model_file"]).exists()]
if missing:
    raise SystemExit("missing HBM files: " + ", ".join(missing))

candidate_triplets = []
seen = set()
for triplet in source_successful_triplets:
    candidate = tuple(sorted(int(item) for item in triplet))
    if len(candidate) != 3 or any(index not in segment_by_index for index in candidate):
        raise SystemExit(f"invalid successful triplet in source report: {triplet}")
    if candidate in seen:
        continue
    seen.add(candidate)
    candidate_triplets.append(candidate)
candidate_triplets = candidate_triplets[:max_triplets]

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


def hold_and_poll(workers):
    samples = []
    deadline = time.time() + hold_seconds
    while True:
        elapsed = max(0.0, hold_seconds - max(0.0, deadline - time.time()))
        worker_samples = []
        for worker in workers:
            record = worker["ready_record"]
            worker_samples.append(
                {
                    "segment_index": record.get("segment_index"),
                    "segment": record.get("segment"),
                    "alive": worker["process"].poll() is None,
                }
            )
        samples.append(
            {
                "elapsed_seconds": round(elapsed, 3),
                "alive_worker_count": sum(1 for item in worker_samples if item["alive"]),
                "workers": worker_samples,
            }
        )
        if time.time() >= deadline:
            break
        sleep_seconds = poll_interval_seconds if poll_interval_seconds > 0 else 0.5
        time.sleep(min(sleep_seconds, max(0.0, deadline - time.time())))
    return samples


topology_records = []
for topology_index, triplet in enumerate(candidate_triplets):
    workers = []
    records = []
    label_prefix = "topology_{:03d}_{}".format(topology_index, "_".join(str(item) for item in triplet))
    try:
        for segment_index in triplet:
            worker = launch_worker(segment_by_index[segment_index], label_prefix)
            workers.append(worker)
            records.append(worker["ready_record"])
            if worker["ready_record"].get("status") != "ready":
                break
            if start_delay_seconds:
                time.sleep(start_delay_seconds)
        ready_records = [item for item in records if item.get("status") == "ready"]
        if len(ready_records) == 3:
            hold_samples = hold_and_poll(workers)
        else:
            hold_samples = []
    finally:
        for worker in reversed(workers):
            stop_worker(worker)
    ready_records = [item for item in records if item.get("status") == "ready"]
    failed_records = [item for item in records if item.get("status") != "ready"]
    dead_sample_count = sum(1 for sample in hold_samples for item in sample["workers"] if not item["alive"])
    topology_records.append(
        {
            "topology_index": topology_index,
            "segment_indexes": list(triplet),
            "segments": [segment_by_index[index]["segment"] for index in triplet],
            "attempted_worker_count": len(records),
            "ready_segment_count": len(ready_records),
            "failed_segment_count": len(failed_records),
            "hold_sample_count": len(hold_samples),
            "dead_worker_sample_count": dead_sample_count,
            "ok": len(ready_records) == 3 and not failed_records and dead_sample_count == 0,
            "records": records,
            "hold_samples": hold_samples,
        }
    )

stable_records = [item for item in topology_records if item.get("ok") is True]
failed_records = [item for item in topology_records if item.get("ok") is not True]
selected_topology = stable_records[0]["segment_indexes"] if stable_records else []
selection_rule = "first stable topology in source successful_triplets order"
if stable_records:
    next_optimization_target = "wire the selected stable triplet into a forward-path experiment and compare HBM load share against the current pair-window production path"
else:
    next_optimization_target = "no successful triplet stayed stable; keep current pair-window path and change split/runtime before a persistent worker experiment"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_persistent_triplet_topology_probe",
    "run_dir": str(run_dir),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "triplet_json": str(triplet_json_path),
    "source_successful_triplet_count": len(source_successful_triplets),
    "tested_triplet_topology_count": len(topology_records),
    "stable_triplet_topology_count": len(stable_records),
    "failed_triplet_topology_count": len(failed_records),
    "hold_seconds": hold_seconds,
    "ready_timeout_seconds": ready_timeout_seconds,
    "poll_interval_seconds": poll_interval_seconds,
    "start_delay_seconds": start_delay_seconds,
    "max_triplets": max_triplets,
    "segment_count": len(segments),
    "stable_triplets": [item["segment_indexes"] for item in stable_records],
    "failed_triplets": [item["segment_indexes"] for item in failed_records],
    "selected_topology": selected_topology,
    "selection_rule": selection_rule,
    "max_resident_segment_count_observed": max([item.get("ready_segment_count", 0) for item in topology_records] or [0]),
    "next_optimization_target": next_optimization_target,
    "topology_records": topology_records,
    "errors": [],
}
(run_dir / "persistent_triplet_topology_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Persistent Triplet Topology Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- triplet_json: {payload['triplet_json']}",
    f"- source_successful_triplet_count: {payload['source_successful_triplet_count']}",
    f"- tested_triplet_topology_count: {payload['tested_triplet_topology_count']}",
    f"- stable_triplet_topology_count: {payload['stable_triplet_topology_count']}",
    f"- failed_triplet_topology_count: {payload['failed_triplet_topology_count']}",
    f"- hold_seconds: {payload['hold_seconds']}",
    f"- selected_topology: {payload['selected_topology']}",
    f"- max_resident_segment_count_observed: {payload['max_resident_segment_count_observed']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Topology Records",
    "",
    "| Topology | Segments | OK | Ready | Failed | Hold samples | Dead samples | First failure |",
    "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |",
]
for item in topology_records:
    first_failure = next((record for record in item["records"] if record.get("status") != "ready"), {})
    failure_text = ""
    if first_failure:
        failure_text = "{}: {}".format(first_failure.get("segment"), first_failure.get("exception", first_failure.get("status", ""))).replace("|", "/")
    lines.append(
        f"| {item['topology_index']} | {', '.join(item['segments'])} | {item['ok']} | "
        f"{item['ready_segment_count']} | {item['failed_segment_count']} | {item['hold_sample_count']} | "
        f"{item['dead_worker_sample_count']} | {failure_text} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This probe tests long-lived three-single-segment HBM runtime residency seeded by the successful triplet report.",
    "- It does not run inference or replace the current pair-window production forward path.",
])
(run_dir / "persistent_triplet_topology_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "persistent_triplet_topology_probe.md")
PY
