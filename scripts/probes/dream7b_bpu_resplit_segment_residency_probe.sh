#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_RESPLIT_BASE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_RESPLIT_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
resplit_hbm_dir="${DREAM7B_BPU_RESPLIT_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16}"
venv="${DREAM7B_BPU_RESPLIT_RESIDENCY_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
single_timeout_seconds="${DREAM7B_BPU_RESPLIT_SINGLE_TIMEOUT_SECONDS:-180}"
holder_ready_timeout_seconds="${DREAM7B_BPU_RESPLIT_HOLDER_READY_TIMEOUT_SECONDS:-180}"
candidate_timeout_seconds="${DREAM7B_BPU_RESPLIT_CANDIDATE_TIMEOUT_SECONDS:-180}"
prefix_start_delay_seconds="${DREAM7B_BPU_RESPLIT_PREFIX_START_DELAY_SECONDS:-1}"

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

case "$resplit_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16|/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16/|/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16|/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16/) ;;
  *)
    echo "Refusing resplit HBM path outside approved Dream 7B resplit directories: $resplit_hbm_dir" >&2
    exit 2
    ;;
esac

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi

for value_name in single_timeout_seconds holder_ready_timeout_seconds candidate_timeout_seconds prefix_start_delay_seconds; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[0-9]+$ ]] || [[ "$value" == "0" && "$value_name" != "prefix_start_delay_seconds" ]]; then
    echo "$value_name must be a non-zero positive integer, except prefix_start_delay_seconds may be 0." >&2
    exit 2
  fi
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_resplit_segment_residency_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - \
  "$run_dir" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$resplit_hbm_dir" \
  "$single_timeout_seconds" \
  "$holder_ready_timeout_seconds" \
  "$candidate_timeout_seconds" \
  "$prefix_start_delay_seconds" <<'PY'
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
base_hbm_dir = Path(sys.argv[2])
fine_hbm_dir = Path(sys.argv[3])
resplit_hbm_dir = Path(sys.argv[4])
single_timeout_seconds = int(sys.argv[5])
holder_ready_timeout_seconds = int(sys.argv[6])
candidate_timeout_seconds = int(sys.argv[7])
prefix_start_delay_seconds = int(sys.argv[8])

segments = [
    {"segment_index": 0, "segment": "seg00_01", "source": "resplit", "layer_start": 0, "layer_end": 1, "model_file": resplit_hbm_dir / "seg00_01/dream7b_segment_0_1_seq16_q8.hbm"},
    {"segment_index": 1, "segment": "seg01_02", "source": "resplit", "layer_start": 1, "layer_end": 2, "model_file": resplit_hbm_dir / "seg01_02/dream7b_segment_1_2_seq16_q8.hbm"},
    {"segment_index": 2, "segment": "seg02_04", "source": "fine", "layer_start": 2, "layer_end": 4, "model_file": fine_hbm_dir / "seg02_04/dream7b_segment_2_4_seq16_q8.hbm"},
    {"segment_index": 3, "segment": "seg04_07", "source": "base", "layer_start": 4, "layer_end": 7, "model_file": base_hbm_dir / "dream7b_segment_4_7_seq16_q8.hbm"},
    {"segment_index": 4, "segment": "seg07_10", "source": "fine", "layer_start": 7, "layer_end": 10, "model_file": fine_hbm_dir / "seg07_10/dream7b_segment_7_10_seq16_q8.hbm"},
    {"segment_index": 5, "segment": "seg10_12", "source": "resplit", "layer_start": 10, "layer_end": 12, "model_file": resplit_hbm_dir / "seg10_12/dream7b_segment_10_12_seq16_q8.hbm"},
    {"segment_index": 6, "segment": "seg12_14", "source": "resplit", "layer_start": 12, "layer_end": 14, "model_file": resplit_hbm_dir / "seg12_14/dream7b_segment_12_14_seq16_q8.hbm"},
    {"segment_index": 7, "segment": "seg14_17", "source": "fine", "layer_start": 14, "layer_end": 17, "model_file": fine_hbm_dir / "seg14_17/dream7b_segment_14_17_seq16_q8.hbm"},
    {"segment_index": 8, "segment": "seg17_19", "source": "resplit", "layer_start": 17, "layer_end": 19, "model_file": resplit_hbm_dir / "seg17_19/dream7b_segment_17_19_seq16_q8.hbm"},
    {"segment_index": 9, "segment": "seg19_21", "source": "resplit", "layer_start": 19, "layer_end": 21, "model_file": resplit_hbm_dir / "seg19_21/dream7b_segment_19_21_seq16_q8.hbm"},
    {"segment_index": 10, "segment": "seg21_24", "source": "base", "layer_start": 21, "layer_end": 24, "model_file": base_hbm_dir / "dream7b_segment_21_24_seq16_q8.hbm"},
    {"segment_index": 11, "segment": "seg24_26", "source": "fine", "layer_start": 24, "layer_end": 26, "model_file": fine_hbm_dir / "seg24_26/dream7b_segment_24_26_seq16_q8.hbm"},
    {"segment_index": 12, "segment": "seg26_27", "source": "resplit", "layer_start": 26, "layer_end": 27, "model_file": resplit_hbm_dir / "seg26_27/dream7b_segment_26_27_seq16_q8.hbm"},
    {"segment_index": 13, "segment": "seg27_28", "source": "resplit", "layer_start": 27, "layer_end": 28, "model_file": resplit_hbm_dir / "seg27_28/dream7b_segment_27_28_seq16_q8.hbm"},
]

errors = []
warnings = []
for item in segments:
    item["model_file"] = str(item["model_file"])
    item["layer_count"] = item["layer_end"] - item["layer_start"]
    path = Path(item["model_file"])
    item["exists"] = path.is_file()
    item["size_bytes"] = path.stat().st_size if path.is_file() else 0
    if not item["exists"]:
        errors.append(f"missing HBM segment file: {path}")

single_code = r"""
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
    runtime = HB_HBMRuntime([payload["model_file"]])
    load_end = time.perf_counter()
    result = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "segment_index": payload["segment_index"],
        "segment": payload["segment"],
        "source": payload["source"],
        "status": "loaded",
        "ok": True,
        "load_ms": round((load_end - load_start) * 1000, 3),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "runtime_version": HB_HBMRuntime.version,
    }
    del runtime
except Exception as exc:
    result = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "segment_index": payload["segment_index"],
        "segment": payload["segment"],
        "source": payload["source"],
        "status": "failed",
        "ok": False,
        "exception_type": type(exc).__name__,
        "exception": str(exc),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
"""

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
    runtime = HB_HBMRuntime([payload["model_file"]])
    load_end = time.perf_counter()
    ready_path.write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(),
        "segment_index": payload["segment_index"],
        "segment": payload["segment"],
        "source": payload["source"],
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
        "source": payload["source"],
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
    runtime = HB_HBMRuntime([payload["model_file"]])
    load_end = time.perf_counter()
    result = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "holder_segment_index": payload["holder_segment_index"],
        "holder_segment": payload["holder_segment"],
        "candidate_segment_index": payload["candidate_segment_index"],
        "candidate_segment": payload["candidate_segment"],
        "status": "loaded",
        "ok": True,
        "load_ms": round((load_end - load_start) * 1000, 3),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "runtime_version": HB_HBMRuntime.version,
    }
    del runtime
except Exception as exc:
    result = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "holder_segment_index": payload["holder_segment_index"],
        "holder_segment": payload["holder_segment"],
        "candidate_segment_index": payload["candidate_segment_index"],
        "candidate_segment": payload["candidate_segment"],
        "status": "failed",
        "ok": False,
        "exception_type": type(exc).__name__,
        "exception": str(exc),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
"""


def run_subprocess(label, code, payload, timeout_seconds):
    payload_path = run_dir / f"{label}.payload.json"
    stdout_path = run_dir / f"{label}.stdout"
    stderr_path = run_dir / f"{label}.stderr"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with stdout_path.open("w", encoding="utf-8") as stdout_fh, stderr_path.open("w", encoding="utf-8") as stderr_fh:
        proc = subprocess.run(
            [sys.executable, "-c", code, str(payload_path)],
            stdout=stdout_fh,
            stderr=stderr_fh,
            timeout=timeout_seconds,
            check=False,
        )
    return proc.returncode, str(stdout_path), str(stderr_path)


def launch_holder(label, segment):
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
            "segment_index": segment["segment_index"],
            "segment": segment["segment"],
            "source": segment["source"],
            "status": "missing_ready_file",
        }
    return {
        "label": label,
        "segment": segment,
        "process": proc,
        "stdout_fh": stdout_fh,
        "stderr_fh": stderr_fh,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "stop_path": stop_path,
        "ready_record": ready_record,
    }


def stop_holder(holder):
    try:
        holder["stop_path"].write_text("stop\n", encoding="utf-8")
        holder["process"].wait(timeout=15)
    except subprocess.TimeoutExpired:
        holder["process"].kill()
        holder["process"].wait(timeout=15)
    finally:
        holder["stdout_fh"].close()
        holder["stderr_fh"].close()


single_records = []
if not errors:
    for segment in segments:
        label = f"single_{segment['segment_index']:02d}_{segment['segment']}"
        result_path = run_dir / f"{label}.result.json"
        rc, stdout_path, stderr_path = run_subprocess(
            label,
            single_code,
            {**segment, "result_path": str(result_path)},
            single_timeout_seconds,
        )
        record = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {
            "segment_index": segment["segment_index"],
            "segment": segment["segment"],
            "source": segment["source"],
            "status": "missing_result",
            "ok": False,
        }
        record.update({"returncode": rc, "stdout": stdout_path, "stderr": stderr_path})
        single_records.append(record)

adjacent_pair_records = []
if not errors:
    for holder_segment, candidate_segment in zip(segments, segments[1:]):
        holder = launch_holder(f"adjacent_holder_{holder_segment['segment_index']:02d}_{holder_segment['segment']}", holder_segment)
        try:
            result_path = run_dir / f"adjacent_{holder_segment['segment_index']:02d}_{candidate_segment['segment_index']:02d}.result.json"
            ready = holder["ready_record"]
            if ready.get("status") == "ready":
                rc, stdout_path, stderr_path = run_subprocess(
                    f"adjacent_candidate_{holder_segment['segment_index']:02d}_{candidate_segment['segment_index']:02d}",
                    candidate_code,
                    {
                        **candidate_segment,
                        "holder_segment_index": holder_segment["segment_index"],
                        "holder_segment": holder_segment["segment"],
                        "candidate_segment_index": candidate_segment["segment_index"],
                        "candidate_segment": candidate_segment["segment"],
                        "result_path": str(result_path),
                    },
                    candidate_timeout_seconds,
                )
                candidate = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {
                    "status": "missing_result",
                    "ok": False,
                }
            else:
                rc = None
                stdout_path = ""
                stderr_path = ""
                candidate = {"status": "skipped_holder_not_ready", "ok": False}
            adjacent_pair_records.append(
                {
                    "holder": ready,
                    "candidate": candidate,
                    "candidate_returncode": rc,
                    "candidate_stdout": stdout_path,
                    "candidate_stderr": stderr_path,
                    "ok": ready.get("status") == "ready" and candidate.get("ok") is True,
                }
            )
        finally:
            stop_holder(holder)

prefix_holders = []
prefix_records = []
if not errors:
    for segment in segments:
        holder = launch_holder(f"prefix_{segment['segment_index']:02d}_{segment['segment']}", segment)
        prefix_holders.append(holder)
        record = holder["ready_record"]
        prefix_records.append(record)
        if record.get("status") != "ready":
            break
        if prefix_start_delay_seconds:
            time.sleep(prefix_start_delay_seconds)
    for holder in reversed(prefix_holders):
        stop_holder(holder)

single_success_count = sum(1 for item in single_records if item.get("ok") is True)
adjacent_pair_success_count = sum(1 for item in adjacent_pair_records if item.get("ok") is True)
ready_prefix_count = sum(1 for item in prefix_records if item.get("status") == "ready")
first_prefix_failure = next((item for item in prefix_records if item.get("status") != "ready"), None)
resplit_adjacent_pair_supported = adjacent_pair_success_count == max(0, len(segments) - 1)

if single_records and single_success_count != len(segments):
    warnings.append("one or more resplit-layout segments failed isolated runtime load")
if adjacent_pair_records and not resplit_adjacent_pair_supported:
    warnings.append("one or more resplit-layout adjacent segment pairs failed simultaneous residency")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_resplit_segment_residency_probe" if not errors else "failed_dream7b_bpu_resplit_segment_residency_probe",
    "run_dir": str(run_dir),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "resplit_hbm_dir": str(resplit_hbm_dir),
    "segment_count": len(segments),
    "segments": segments,
    "single_success_count": single_success_count,
    "adjacent_pair_count": len(adjacent_pair_records),
    "adjacent_pair_success_count": adjacent_pair_success_count,
    "resplit_adjacent_pair_supported": resplit_adjacent_pair_supported,
    "ready_prefix_count": ready_prefix_count,
    "first_prefix_failure": first_prefix_failure,
    "single_records": single_records,
    "adjacent_pair_records": adjacent_pair_records,
    "prefix_records": prefix_records,
    "next_optimization_target": (
        "adapt the Dream forward runtime to a resplit-layout segment plan and benchmark load/run telemetry"
        if resplit_adjacent_pair_supported
        else "inspect failed resplit-layout adjacent pairs before using the resplit layout for forward execution"
    ),
    "warnings": warnings,
    "errors": errors,
}
json_path = run_dir / "resplit_segment_residency_probe.json"
md_path = run_dir / "resplit_segment_residency_probe.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Resplit Segment Residency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- segment_count: {payload['segment_count']}",
    f"- single_success_count: {payload['single_success_count']}",
    f"- adjacent_pair_success_count: {payload['adjacent_pair_success_count']}",
    f"- adjacent_pair_count: {payload['adjacent_pair_count']}",
    f"- resplit_adjacent_pair_supported: {payload['resplit_adjacent_pair_supported']}",
    f"- ready_prefix_count: {payload['ready_prefix_count']}",
    f"- first_prefix_failure: {payload['first_prefix_failure']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Segments",
    "",
]
for item in segments:
    lines.append(
        f"- {item['segment_index']} {item['segment']} {item['source']} "
        f"layers={item['layer_start']}:{item['layer_end']} size_bytes={item['size_bytes']}"
    )
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md_path)
if errors:
    raise SystemExit("; ".join(errors))
PY
