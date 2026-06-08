#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
python_bin="${DREAM7B_BPU_SCHEDULING_PARAMS_PYTHON:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python}"
hbm_path="${DREAM7B_BPU_SCHEDULING_PARAMS_HBM:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16/seg00_02/dream7b_segment_0_2_seq16_q8.hbm}"
cores_text="${DREAM7B_BPU_SCHEDULING_PARAMS_CORES:-default 0 1 2 3}"
timeout_seconds="${DREAM7B_BPU_SCHEDULING_PARAMS_TIMEOUT_SECONDS:-30}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$python_bin" in
  /mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python|/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python3|/home/sunrise/.openclaw/*/bin/python|/home/sunrise/.openclaw/*/bin/python3) ;;
  *)
    echo "Refusing Python path outside approved S100P runtime directories: $python_bin" >&2
    exit 2
    ;;
esac

case "$hbm_path" in
  /home/sunrise/.cache/openclaw/dream7b-hbm/*|/mnt/nas/openclaw/models/dream7b-hbm/*) ;;
  *)
    echo "Refusing HBM path outside approved Dream 7B HBM directories: $hbm_path" >&2
    exit 2
    ;;
esac

if ! [[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SCHEDULING_PARAMS_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi

for core in $cores_text; do
  case "$core" in
    default|0|1|2|3) ;;
    *)
      echo "Refusing unsupported scheduling core value: $core" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_scheduling_params_$stamp"
mkdir -p "$run_dir"

python3 - "$run_dir" "$python_bin" "$hbm_path" "$cores_text" "$timeout_seconds" <<'PY'
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

run_dir = Path(sys.argv[1])
python_bin = Path(sys.argv[2])
hbm_path = Path(sys.argv[3])
cores = sys.argv[4].split()
timeout_seconds = int(sys.argv[5])

def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)

child_code = r'''
import json
import os
import time
import numpy as np
from hbm_runtime import HB_HBMRuntime

hbm_path = os.environ["DREAM7B_BPU_SCHED_CHILD_HBM"]
core_text = os.environ["DREAM7B_BPU_SCHED_CHILD_CORE"]
runtime = HB_HBMRuntime(hbm_path)
model_name = runtime.model_names[0]
payload = {
    "core": core_text,
    "model_name": model_name,
    "runtime_version": getattr(HB_HBMRuntime, "version", None),
    "set_scheduling_params_doc": getattr(runtime.set_scheduling_params, "__doc__", ""),
    "initial_sched_params_repr": repr(runtime.sched_params),
    "set_scheduling_params_called": False,
    "set_scheduling_params_ok": None,
    "after_set_sched_params_repr": "",
    "run_ok": False,
    "run_ms": None,
    "output_name": "",
    "output_shape": [],
    "output_dtype": "",
}
if core_text != "default":
    runtime.set_scheduling_params(bpu_cores={model_name: [int(core_text)]})
    payload["set_scheduling_params_called"] = True
    payload["set_scheduling_params_ok"] = True
    payload["after_set_sched_params_repr"] = repr(runtime.sched_params)
inputs = {
    "_input_0": np.zeros((1, 16), dtype=np.int32),
    "_input_1": np.arange(16, dtype=np.int32),
}
t0 = time.perf_counter()
output = runtime.run(inputs, model_name=model_name)
t1 = time.perf_counter()
output_name = runtime.output_names[model_name][0]
arr = output[model_name][output_name]
payload["run_ok"] = True
payload["run_ms"] = round((t1 - t0) * 1000, 3)
payload["output_name"] = output_name
payload["output_shape"] = list(arr.shape)
payload["output_dtype"] = str(arr.dtype)
print(json.dumps(payload, ensure_ascii=False))
'''

errors = []
warnings = []
if not python_bin.is_file():
    errors.append(f"runtime Python is missing: {python_bin}")
if not hbm_path.is_file():
    errors.append(f"Dream 7B HBM is missing: {hbm_path}")

case_results = []
if not errors:
    for core in cores:
        case_name = f"core_{core}"
        case_dir = run_dir / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["DREAM7B_BPU_SCHED_CHILD_HBM"] = str(hbm_path)
        env["DREAM7B_BPU_SCHED_CHILD_CORE"] = core
        completed = subprocess.run(
            [str(python_bin), "-u", "-c", child_code],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            env=env,
        )
        stdout_path = case_dir / "stdout.txt"
        stderr_path = case_dir / "stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8", errors="replace")
        stderr_path.write_text(completed.stderr, encoding="utf-8", errors="replace")
        clean = strip_ansi(completed.stdout + "\n" + completed.stderr)
        parsed_payload = {}
        for line in completed.stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    parsed_payload = json.loads(line)
                except Exception:
                    parsed_payload = {}
        unsupported_line = ""
        for line in clean.splitlines():
            if "schedule backend unsupported" in line:
                unsupported_line = line
                break
        result = {
            "core": core,
            "case_dir": str(case_dir),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "returncode": completed.returncode,
            "run_ok": bool(parsed_payload.get("run_ok")),
            "set_scheduling_params_called": parsed_payload.get("set_scheduling_params_called"),
            "set_scheduling_params_ok": parsed_payload.get("set_scheduling_params_ok"),
            "model_name": parsed_payload.get("model_name", ""),
            "runtime_version": parsed_payload.get("runtime_version"),
            "run_ms": parsed_payload.get("run_ms"),
            "output_shape": parsed_payload.get("output_shape", []),
            "output_dtype": parsed_payload.get("output_dtype", ""),
            "set_scheduling_params_doc": parsed_payload.get("set_scheduling_params_doc", ""),
            "initial_sched_params_repr": parsed_payload.get("initial_sched_params_repr", ""),
            "after_set_sched_params_repr": parsed_payload.get("after_set_sched_params_repr", ""),
            "schedule_backend_unsupported_observed": "schedule backend unsupported" in clean,
            "schedule_backend_unsupported_line": unsupported_line,
            "abort_observed": "Aborted" in clean or completed.returncode in (-6, 134),
            "ucp_invalid_argument_observed": "UCP Error (code: -100001" in clean,
        }
        (case_dir / "case_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        case_results.append(result)

run_ok_by_core = {item["core"]: item["run_ok"] for item in case_results}
returncode_by_core = {item["core"]: item["returncode"] for item in case_results}
unsupported_by_core = {item["core"]: item["schedule_backend_unsupported_observed"] for item in case_results}
abort_by_core = {item["core"]: item["abort_observed"] for item in case_results}

if any(unsupported_by_core.values()):
    warnings.append("at least one tested Dream scheduling core produced schedule backend unsupported")
if run_ok_by_core.get("0") is True:
    warnings.append("Dream single-segment HBM supports explicit bpu_cores={model_name: [0]} in this runtime")

payload = {
    "generated_at": now_iso(),
    "verdict": "ok_dream7b_bpu_scheduling_params_probe" if not errors else "failed_dream7b_bpu_scheduling_params_probe",
    "run_dir": str(run_dir),
    "python_bin": str(python_bin),
    "hbm_path": str(hbm_path),
    "tested_cores": cores,
    "case_count": len(case_results),
    "case_results": case_results,
    "run_ok_by_core": run_ok_by_core,
    "returncode_by_core": returncode_by_core,
    "schedule_backend_unsupported_by_core": unsupported_by_core,
    "abort_by_core": abort_by_core,
    "core0_explicit_supported": run_ok_by_core.get("0") is True,
    "nonzero_cores_supported": any(run_ok_by_core.get(core) is True for core in ("1", "2", "3")),
    "interpretation": "Dream HB_HBMRuntime exposes set_scheduling_params with bpu_cores mapping; the tested single segment supports default and core 0, while cores 1/2/3 are unsupported for this HBM and abort in isolated child processes.",
    "next_probe_target": "treat Dream bpu_cores as a model-specific scheduling constraint; do not port Qwen bpu_core values directly, and continue HBM reload/residency optimization with optional core0-only scheduling checks.",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "scheduling_params_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B BPU Scheduling Params Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- hbm_path: {payload['hbm_path']}",
    f"- tested_cores: {payload['tested_cores']}",
    f"- run_ok_by_core: {payload['run_ok_by_core']}",
    f"- returncode_by_core: {payload['returncode_by_core']}",
    f"- schedule_backend_unsupported_by_core: {payload['schedule_backend_unsupported_by_core']}",
    f"- abort_by_core: {payload['abort_by_core']}",
    f"- core0_explicit_supported: {payload['core0_explicit_supported']}",
    f"- nonzero_cores_supported: {payload['nonzero_cores_supported']}",
    f"- interpretation: {payload['interpretation']}",
    f"- next_probe_target: {payload['next_probe_target']}",
]
(run_dir / "scheduling_params_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "scheduling_params_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
