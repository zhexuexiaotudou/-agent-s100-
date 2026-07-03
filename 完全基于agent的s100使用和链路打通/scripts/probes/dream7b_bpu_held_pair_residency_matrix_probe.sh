#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
holder_ready_timeout_seconds="${DREAM7B_BPU_HELD_PAIR_MATRIX_HOLDER_READY_TIMEOUT_SECONDS:-180}"
candidate_timeout_seconds="${DREAM7B_BPU_HELD_PAIR_MATRIX_CANDIDATE_TIMEOUT_SECONDS:-180}"

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
if ! [[ "$holder_ready_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_HELD_PAIR_MATRIX_HOLDER_READY_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$candidate_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_HELD_PAIR_MATRIX_CANDIDATE_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_held_pair_residency_matrix_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - \
  "$run_dir" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$holder_ready_timeout_seconds" \
  "$candidate_timeout_seconds" <<'PY'
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
base_hbm_dir = Path(sys.argv[2])
fine_hbm_dir = Path(sys.argv[3])
holder_ready_timeout_seconds = int(sys.argv[4])
candidate_timeout_seconds = int(sys.argv[5])

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

holder_code = r"""
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
    runtime = HB_HBMRuntime(payload["model_files"])
    load_end = time.perf_counter()
    ready_path.write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(),
        "pair_index": payload["pair_index"],
        "segments": payload["segments"],
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
        "pair_index": payload["pair_index"],
        "segments": payload["segments"],
        "status": "failed",
        "exception_type": type(exc).__name__,
        "exception": str(exc),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise
"""

candidate_code = r"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from hbm_runtime import HB_HBMRuntime

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
result_path = Path(payload["result_path"])
started = time.perf_counter()
try:
    load_start = time.perf_counter()
    runtime = HB_HBMRuntime(payload["model_files"])
    load_end = time.perf_counter()
    result_path.write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(),
        "holder_pair_index": payload["holder_pair_index"],
        "candidate_pair_index": payload["candidate_pair_index"],
        "candidate_segments": payload["candidate_segments"],
        "status": "loaded",
        "ok": True,
        "load_ms": round((load_end - load_start) * 1000, 3),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "runtime_version": HB_HBMRuntime.version,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    del runtime
except Exception as exc:
    result_path.write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(),
        "holder_pair_index": payload["holder_pair_index"],
        "candidate_pair_index": payload["candidate_pair_index"],
        "candidate_segments": payload["candidate_segments"],
        "status": "failed",
        "ok": False,
        "exception_type": type(exc).__name__,
        "exception": str(exc),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise
"""

def launch_holder(pair):
    label = f"holder_{pair['pair_index']:02d}_{'__'.join(pair['segments'])}"
    payload_path = run_dir / f"{label}.payload.json"
    ready_path = run_dir / f"{label}.ready.json"
    stop_path = run_dir / f"{label}.stop"
    stdout_path = run_dir / f"{label}.stdout"
    stderr_path = run_dir / f"{label}.stderr"
    payload = {
        **pair,
        "ready_path": str(ready_path),
        "stop_path": str(stop_path),
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stdout_fh = stdout_path.open("w", encoding="utf-8")
    stderr_fh = stderr_path.open("w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", holder_code, str(payload_path)], stdout=stdout_fh, stderr=stderr_fh)
    deadline = time.time() + holder_ready_timeout_seconds
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
            "pair_index": pair["pair_index"],
            "segments": pair["segments"],
            "status": "missing_ready_file",
        }
    return {
        "pair": pair,
        "label": label,
        "process": proc,
        "stdout_fh": stdout_fh,
        "stderr_fh": stderr_fh,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "stop_path": stop_path,
        "ready_record": ready_record,
    }

def stop_holder(holder):
    holder["stop_path"].write_text("stop\n", encoding="utf-8")
    try:
        holder["process"].wait(timeout=15)
    except subprocess.TimeoutExpired:
        holder["process"].kill()
        holder["process"].wait(timeout=15)
    holder["stdout_fh"].close()
    holder["stderr_fh"].close()

def run_candidate(holder_pair, candidate_pair):
    label = f"holder_{holder_pair['pair_index']:02d}__candidate_{candidate_pair['pair_index']:02d}"
    payload_path = run_dir / f"{label}.payload.json"
    result_path = run_dir / f"{label}.result.json"
    stdout_path = run_dir / f"{label}.stdout"
    stderr_path = run_dir / f"{label}.stderr"
    payload = {
        "holder_pair_index": holder_pair["pair_index"],
        "holder_segments": holder_pair["segments"],
        "candidate_pair_index": candidate_pair["pair_index"],
        "candidate_segments": candidate_pair["segments"],
        "model_files": candidate_pair["model_files"],
        "result_path": str(result_path),
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with stdout_path.open("w", encoding="utf-8") as stdout_fh, stderr_path.open("w", encoding="utf-8") as stderr_fh:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", candidate_code, str(payload_path)],
                stdout=stdout_fh,
                stderr=stderr_fh,
                timeout=candidate_timeout_seconds,
            )
            timeout = False
        except subprocess.TimeoutExpired:
            proc = None
            timeout = True
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        result = {
            "holder_pair_index": holder_pair["pair_index"],
            "candidate_pair_index": candidate_pair["pair_index"],
            "candidate_segments": candidate_pair["segments"],
            "status": "timeout" if timeout else "missing_result_file",
            "ok": False,
        }
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    result.update(
        {
            "holder_segments": holder_pair["segments"],
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "returncode": None if proc is None else proc.returncode,
            "timeout": timeout,
            "stderr_preview": stderr_text[-2000:],
        }
    )
    return result

matrix_entries = []
holder_records = []
for holder_pair in pair_windows:
    holder = launch_holder(holder_pair)
    holder_records.append(holder["ready_record"])
    try:
        if holder["ready_record"].get("status") != "ready":
            continue
        for candidate_pair in pair_windows:
            if candidate_pair["pair_index"] == holder_pair["pair_index"]:
                continue
            matrix_entries.append(run_candidate(holder_pair, candidate_pair))
    finally:
        stop_holder(holder)

successful_entries = [item for item in matrix_entries if item.get("ok") is True]
failed_entries = [item for item in matrix_entries if item.get("ok") is not True]
successful_pair_edges = [
    [item["holder_pair_index"], item["candidate_pair_index"]]
    for item in successful_entries
]
failed_pair_edges = [
    [item["holder_pair_index"], item["candidate_pair_index"]]
    for item in failed_entries
]
ready_holder_pair_indexes = [item["pair_index"] for item in holder_records if item.get("status") == "ready"]
max_resident_pair_count_observed = 2 if successful_entries else (1 if ready_holder_pair_indexes else 0)
if successful_entries:
    next_optimization_target = "inspect successful held-pair edges before choosing a narrower persistent worker topology"
else:
    next_optimization_target = "persistent multi-pair residency is not supported by this fine split; reduce individual pair HBM size or pursue a different split"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_held_pair_residency_matrix_probe",
    "run_dir": str(run_dir),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "holder_ready_timeout_seconds": holder_ready_timeout_seconds,
    "candidate_timeout_seconds": candidate_timeout_seconds,
    "pair_worker_count": len(pair_windows),
    "ready_holder_pair_count": len(ready_holder_pair_indexes),
    "ready_holder_pair_indexes": ready_holder_pair_indexes,
    "matrix_entry_count": len(matrix_entries),
    "successful_pair_edge_count": len(successful_entries),
    "failed_pair_edge_count": len(failed_entries),
    "successful_pair_edges": successful_pair_edges,
    "failed_pair_edges": failed_pair_edges,
    "max_resident_pair_count_observed": max_resident_pair_count_observed,
    "next_optimization_target": next_optimization_target,
    "holder_records": holder_records,
    "matrix_entries": matrix_entries,
    "errors": [],
}
(run_dir / "held_pair_residency_matrix_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Held Pair Residency Matrix Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- ready_holder_pair_count: {payload['ready_holder_pair_count']}",
    f"- matrix_entry_count: {payload['matrix_entry_count']}",
    f"- successful_pair_edge_count: {payload['successful_pair_edge_count']}",
    f"- failed_pair_edge_count: {payload['failed_pair_edge_count']}",
    f"- max_resident_pair_count_observed: {payload['max_resident_pair_count_observed']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Holder Records",
    "",
    "| Pair index | Segments | Status | Load ms |",
    "| ---: | --- | --- | ---: |",
]
for item in holder_records:
    lines.append(f"| {item.get('pair_index')} | {', '.join(item.get('segments') or [])} | {item.get('status')} | {item.get('load_ms', '')} |")
lines.extend([
    "",
    "## Matrix Entries",
    "",
    "| Holder | Candidate | OK | Status | Load ms | Exception |",
    "| ---: | ---: | --- | --- | ---: | --- |",
])
for item in matrix_entries:
    exception = (item.get("exception") or "").replace("|", "/")
    lines.append(
        f"| {item.get('holder_pair_index')} | {item.get('candidate_pair_index')} | {item.get('ok')} | "
        f"{item.get('status')} | {item.get('load_ms', '')} | {exception} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This probe tests pair coexistence only; it does not run inference or a production text service.",
    "- Use this matrix before choosing a persistent worker topology or a smaller split.",
])
(run_dir / "held_pair_residency_matrix_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "held_pair_residency_matrix_probe.md")
PY
