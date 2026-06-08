#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
triplet_json="${DREAM7B_BPU_SEEDED_QUAD_TRIPLET_JSON:-}"
ready_timeout_seconds="${DREAM7B_BPU_SEEDED_QUAD_READY_TIMEOUT_SECONDS:-180}"
start_delay_seconds="${DREAM7B_BPU_SEEDED_QUAD_START_DELAY_SECONDS:-0}"
max_combinations="${DREAM7B_BPU_SEEDED_QUAD_MAX_COMBINATIONS:-140}"

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
  echo "DREAM7B_BPU_SEEDED_QUAD_READY_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$start_delay_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_SEEDED_QUAD_START_DELAY_SECONDS must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$max_combinations" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SEEDED_QUAD_MAX_COMBINATIONS must be a positive integer." >&2
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
run_dir="$report_root/dream7b_bpu_seeded_quad_residency_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - \
  "$run_dir" \
  "$report_root" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$triplet_json" \
  "$ready_timeout_seconds" \
  "$start_delay_seconds" \
  "$max_combinations" <<'PY'
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
ready_timeout_seconds = int(sys.argv[6])
start_delay_seconds = float(sys.argv[7])
max_combinations = int(sys.argv[8])

def latest_triplet_json():
    if triplet_json_arg:
        path = Path(triplet_json_arg)
        if not path.is_file():
            raise SystemExit(f"missing DREAM7B_BPU_SEEDED_QUAD_TRIPLET_JSON: {path}")
        return path
    paths = list(report_root.glob("dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json"))
    paths = [path for path in paths if path.is_file()]
    if not paths:
        raise SystemExit("missing triplet residency report for seeded quad probe")
    return max(paths, key=lambda path: path.stat().st_mtime)

triplet_json_path = latest_triplet_json()
triplet_report = json.loads(triplet_json_path.read_text(encoding="utf-8"))
successful_triplets = triplet_report.get("successful_triplets") or []
if not successful_triplets:
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

quad_seed_map = {}
for triplet in successful_triplets:
    seed = tuple(sorted(int(item) for item in triplet))
    if len(seed) != 3 or any(index not in segment_by_index for index in seed):
        raise SystemExit(f"invalid successful triplet in source report: {triplet}")
    for candidate in segment_by_index:
        if candidate in seed:
            continue
        quad = tuple(sorted((*seed, candidate)))
        quad_seed_map.setdefault(quad, []).append(list(seed))
quad_combinations = sorted(quad_seed_map)[:max_combinations]

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
for combo_index, quad in enumerate(quad_combinations):
    workers = []
    records = []
    label_prefix = "quad_{:03d}_{}".format(combo_index, "_".join(str(item) for item in quad))
    try:
        for segment_index in quad:
            worker = launch_worker(segment_by_index[segment_index], label_prefix)
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
            "segment_indexes": list(quad),
            "segments": [segment_by_index[item]["segment"] for item in quad],
            "source_successful_triplets": quad_seed_map[quad],
            "attempted_worker_count": len(records),
            "ready_segment_count": len(ready_records),
            "failed_segment_count": len(failed_records),
            "ok": len(ready_records) == 4 and not failed_records,
            "records": records,
        }
    )

successful_records = [item for item in combination_records if item.get("ok") is True]
failed_records = [item for item in combination_records if item.get("ok") is not True]
max_resident_segment_count_observed = max([item.get("ready_segment_count", 0) for item in combination_records] or [0])
if successful_records:
    next_optimization_target = "inspect successful seeded quads and then test larger resident groups or a seeded persistent worker topology"
else:
    next_optimization_target = "no tested seeded quad is resident; use successful triplets as the current persistent topology seed"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_seeded_quad_residency_probe",
    "run_dir": str(run_dir),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "triplet_json": str(triplet_json_path),
    "source_successful_triplet_count": len(successful_triplets),
    "ready_timeout_seconds": ready_timeout_seconds,
    "start_delay_seconds": start_delay_seconds,
    "max_combinations": max_combinations,
    "segment_count": len(segments),
    "seeded_quad_candidate_count": len(quad_seed_map),
    "tested_seeded_quad_count": len(combination_records),
    "successful_seeded_quad_count": len(successful_records),
    "failed_seeded_quad_count": len(failed_records),
    "successful_seeded_quads": [item["segment_indexes"] for item in successful_records],
    "failed_seeded_quads": [item["segment_indexes"] for item in failed_records],
    "max_resident_segment_count_observed": max_resident_segment_count_observed,
    "next_optimization_target": next_optimization_target,
    "combination_records": combination_records,
    "errors": [],
}
(run_dir / "seeded_quad_residency_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Seeded Quad Residency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- triplet_json: {payload['triplet_json']}",
    f"- source_successful_triplet_count: {payload['source_successful_triplet_count']}",
    f"- seeded_quad_candidate_count: {payload['seeded_quad_candidate_count']}",
    f"- tested_seeded_quad_count: {payload['tested_seeded_quad_count']}",
    f"- successful_seeded_quad_count: {payload['successful_seeded_quad_count']}",
    f"- failed_seeded_quad_count: {payload['failed_seeded_quad_count']}",
    f"- max_resident_segment_count_observed: {payload['max_resident_segment_count_observed']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Combination Records",
    "",
    "| Combination | Segments | OK | Ready | Failed | Source triplets | First failure |",
    "| ---: | --- | --- | ---: | ---: | --- | --- |",
]
for item in combination_records:
    first_failure = next((record for record in item["records"] if record.get("status") != "ready"), {})
    failure_text = ""
    if first_failure:
        failure_text = "{}: {}".format(first_failure.get("segment"), first_failure.get("exception", first_failure.get("status", ""))).replace("|", "/")
    source = "; ".join(str(source) for source in item["source_successful_triplets"])
    lines.append(
        f"| {item['combination_index']} | {', '.join(item['segments'])} | {item['ok']} | "
        f"{item['ready_segment_count']} | {item['failed_segment_count']} | {source} | {failure_text} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This probe tests four-single-segment HBM runtime residency seeded by successful triplets only; it does not run inference or a production text service.",
    "- A successful quad is a prerequisite for testing larger resident groups or a seeded persistent worker topology.",
])
(run_dir / "seeded_quad_residency_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "seeded_quad_residency_probe.md")
PY
