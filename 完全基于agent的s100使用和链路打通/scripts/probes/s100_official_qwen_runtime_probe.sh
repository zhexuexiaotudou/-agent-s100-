#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_OFFICIAL_QWEN_RUNTIME_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"
dream_report_root="${S100_OFFICIAL_QWEN_RUNTIME_DREAM_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
runtime_timeout_seconds="${S100_OFFICIAL_QWEN_RUNTIME_TIMEOUT_SECONDS:-60}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$sdk_root" in
  /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK|/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/|/opt/D-Robotics_LLM_S100_1.0.0_SDK|/opt/D-Robotics_LLM_S100_1.0.0_SDK/) ;;
  *)
    echo "Refusing SDK path outside approved S100 official LLM SDK directories: $sdk_root" >&2
    exit 2
    ;;
esac

case "$dream_report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing Dream report path outside approved report directories: $dream_report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$runtime_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "S100_OFFICIAL_QWEN_RUNTIME_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_official_qwen_runtime_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$sdk_root" \
  "$dream_report_root" \
  "$runtime_timeout_seconds" <<'PY'
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
sdk_root = Path(sys.argv[2])
dream_report_root = Path(sys.argv[3])
runtime_timeout_seconds = int(sys.argv[4])

runtime_root = sdk_root / "oellm_runtime"
multichat_dir = runtime_root / "example" / "oellm_multichat"
runtime_bin = multichat_dir / "oellm_multichat"
runtime_config = multichat_dir / "qwen_multichat_config.json"
runtime_lib_dir = runtime_root / "lib"
performance_mode_script = runtime_root / "set_performance_mode.sh"

errors = []
warnings = []


def latest_json(root, pattern):
    paths = [path for path in root.glob(pattern) if path.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def read_json(path):
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_process(argv, cwd, timeout_seconds, stdin_text=None):
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(runtime_lib_dir)
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            input=stdin_text,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            env=env,
        )
        return {
            "timed_out": False,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "timed_out": True,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }


config = read_json(runtime_config)
hbm_path_raw = config.get("hbm_path") if isinstance(config, dict) else None
hbm_path = (multichat_dir / hbm_path_raw).resolve() if hbm_path_raw else None
tokenizer_dir_raw = config.get("tokenizer_dir") if isinstance(config, dict) else None
tokenizer_dir = (multichat_dir / tokenizer_dir_raw).resolve() if tokenizer_dir_raw else None
template_path_raw = config.get("template_path") if isinstance(config, dict) else None
template_path = (multichat_dir / template_path_raw).resolve() if template_path_raw else None

if not runtime_root.is_dir():
    errors.append("official oellm_runtime directory is missing")
if not runtime_bin.is_file():
    errors.append("official oellm_multichat binary is missing")
if not runtime_config.is_file():
    errors.append("official qwen_multichat_config.json is missing")
if not runtime_lib_dir.is_dir():
    errors.append("official oellm_runtime lib directory is missing")
if hbm_path is None or not hbm_path.is_file():
    errors.append("official Qwen HBM from qwen_multichat_config.json is missing")
if tokenizer_dir is None or not tokenizer_dir.is_dir():
    errors.append("official Qwen tokenizer_dir from qwen_multichat_config.json is missing")
if template_path is None or not template_path.is_file():
    errors.append("official Qwen template_path from qwen_multichat_config.json is missing")

ldd_result = None
runtime_result = None
if not errors:
    ldd_result = run_process(["ldd", str(runtime_bin)], multichat_dir, 20)
    runtime_result = run_process(
        [str(runtime_bin), "-c", str(runtime_config.name)],
        multichat_dir,
        runtime_timeout_seconds,
        "hello\nexit\n",
    )

runtime_stdout = (runtime_result or {}).get("stdout") or ""
runtime_stderr = (runtime_result or {}).get("stderr") or ""
combined_runtime_output = runtime_stdout + "\n" + runtime_stderr
ldd_stdout = (ldd_result or {}).get("stdout") or ""
ldd_stderr = (ldd_result or {}).get("stderr") or ""

memory_alloc_failure_observed = (
    "Allocate memory failed" in combined_runtime_output
    or "Fail to allocate common buffer" in combined_runtime_output
    or "AllocError" in combined_runtime_output
)
ion_alloc_failure_observed = "ION_IOC_ALLOC" in combined_runtime_output
bpu_mem_pool_alloc_error_observed = "bpu_mem_pool" in combined_runtime_output and "AllocError" in combined_runtime_output
segmentation_fault_observed = (
    (runtime_result or {}).get("returncode") in (-11, 139)
    or "Segmentation fault" in combined_runtime_output
)
hbm_load_success_observed = "Load hbm file" in combined_runtime_output and "success" in combined_runtime_output
prefill_model_load_success_observed = "model_name is: prefill" in combined_runtime_output
decode_model_load_success_observed = "model_name is: decode" in combined_runtime_output
init_model_success_observed = "Init model success" in combined_runtime_output
runtime_completed = (runtime_result or {}).get("returncode") == 0 and not (runtime_result or {}).get("timed_out")

if ldd_result and "not found" in (ldd_stdout + ldd_stderr):
    warnings.append("official Qwen runtime ldd still reports missing dependencies even with LD_LIBRARY_PATH")
if runtime_result and runtime_result.get("timed_out"):
    warnings.append("official Qwen runtime timed out before completion")
if runtime_result and not runtime_completed and memory_alloc_failure_observed:
    warnings.append("official Qwen runtime loaded the official HBM but failed during BPU/common-buffer memory allocation")
if runtime_result and not runtime_completed and not memory_alloc_failure_observed:
    warnings.append("official Qwen runtime did not complete; inspect captured stdout/stderr")

utilization_path, utilization = latest_json(dream_report_root, "dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
window3_path, window3 = latest_json(dream_report_root, "dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json")
selected_path, selected = latest_json(dream_report_root, "dream7b_bpu_selected_triplet_forward_path_*/selected_triplet_forward_path_probe.json")

dream_summary = {
    "utilization_gap_path": str(utilization_path) if utilization_path else "",
    "diagnosis": utilization.get("diagnosis") if utilization else None,
    "avg_observed_bpu_loading_across_reports": utilization.get("avg_observed_bpu_loading_across_reports") if utilization else None,
    "runtime_load_to_run_ratio": ((utilization.get("runtime_telemetry") or {}).get("load_to_run_ratio") if utilization else None),
    "systemd_load_to_run_ratio": ((utilization.get("systemd_telemetry") or {}).get("load_to_run_ratio") if utilization else None),
    "window3_forward_path": str(window3_path) if window3_path else "",
    "window3_stderr_contains_memory_alloc_failure": window3.get("stderr_contains_memory_alloc_failure") if window3 else None,
    "selected_triplet_forward_path": str(selected_path) if selected_path else "",
    "selected_triplet_forward_supported": selected.get("selected_triplet_forward_supported") if selected else None,
    "selected_triplet_reboot_or_disconnect_observed": selected.get("reboot_or_disconnect_observed") if selected else None,
}

same_failure_class_as_dream = False
comparison_reason = (
    "official Qwen uses a single vendor .hbm and official oellm runtime, while Dream uses a project-created segmented .hbm chain; "
    "current official Qwen evidence shows BPU/common-buffer allocation failure after HBM/model load, not the Dream sustained-utilization hbm_reload_dominated pattern"
)
if memory_alloc_failure_observed and bool(dream_summary.get("window3_stderr_contains_memory_alloc_failure")):
    same_failure_class_as_dream = True
    comparison_reason = (
        "both official Qwen runtime and at least one Dream residency/forward feasibility probe expose BPU memory allocation failure on this S100P state; "
        "Dream's sustained service bottleneck remains separately diagnosed as hbm_reload_dominated"
    )

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_s100_official_qwen_runtime_probe" if not errors else "failed_s100_official_qwen_runtime_probe",
    "run_dir": str(run_dir),
    "sdk_root": str(sdk_root),
    "runtime_root": str(runtime_root),
    "multichat_dir": str(multichat_dir),
    "runtime_bin": str(runtime_bin),
    "runtime_config": str(runtime_config),
    "runtime_lib_dir": str(runtime_lib_dir),
    "performance_mode_script": str(performance_mode_script),
    "performance_mode_script_exists": performance_mode_script.is_file(),
    "performance_mode_script_action": "inspected_not_applied",
    "runtime_timeout_seconds": runtime_timeout_seconds,
    "qwen_multichat_config": config,
    "qwen_hbm_path": str(hbm_path) if hbm_path else "",
    "qwen_hbm_exists": hbm_path.is_file() if hbm_path else False,
    "qwen_hbm_size_bytes": hbm_path.stat().st_size if hbm_path and hbm_path.is_file() else 0,
    "tokenizer_dir": str(tokenizer_dir) if tokenizer_dir else "",
    "tokenizer_dir_exists": tokenizer_dir.is_dir() if tokenizer_dir else False,
    "template_path": str(template_path) if template_path else "",
    "template_path_exists": template_path.is_file() if template_path else False,
    "ldd_returncode": (ldd_result or {}).get("returncode"),
    "ldd_missing_dependency_observed": "not found" in (ldd_stdout + ldd_stderr),
    "runtime_returncode": (runtime_result or {}).get("returncode"),
    "runtime_timed_out": (runtime_result or {}).get("timed_out") if runtime_result else None,
    "runtime_completed": runtime_completed,
    "hbm_load_success_observed": hbm_load_success_observed,
    "prefill_model_load_success_observed": prefill_model_load_success_observed,
    "decode_model_load_success_observed": decode_model_load_success_observed,
    "init_model_success_observed": init_model_success_observed,
    "memory_alloc_failure_observed": memory_alloc_failure_observed,
    "ion_alloc_failure_observed": ion_alloc_failure_observed,
    "bpu_mem_pool_alloc_error_observed": bpu_mem_pool_alloc_error_observed,
    "segmentation_fault_observed": segmentation_fault_observed,
    "official_qwen_runtime_supported_on_current_s100p_state": runtime_completed,
    "same_failure_class_as_dream": same_failure_class_as_dream,
    "comparison_to_dream": {
        "reason": comparison_reason,
        "dream_failure_summary": dream_summary,
    },
    "next_probe_target": "inspect S100P BPU/common-buffer memory pool and official runtime performance-mode prerequisites before using Qwen as a clean 128TOPS utilization baseline",
    "captured_stdout_path": str(run_dir / "oellm_multichat.stdout.txt"),
    "captured_stderr_path": str(run_dir / "oellm_multichat.stderr.txt"),
    "captured_ldd_path": str(run_dir / "oellm_multichat.ldd.txt"),
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "oellm_multichat.stdout.txt").write_text(runtime_stdout, encoding="utf-8", errors="replace")
(run_dir / "oellm_multichat.stderr.txt").write_text(runtime_stderr, encoding="utf-8", errors="replace")
(run_dir / "oellm_multichat.ldd.txt").write_text(ldd_stdout + ldd_stderr, encoding="utf-8", errors="replace")
(run_dir / "official_qwen_runtime_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# S100 Official Qwen Runtime Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- qwen_hbm_exists: {payload['qwen_hbm_exists']}",
    f"- qwen_hbm_size_bytes: {payload['qwen_hbm_size_bytes']}",
    f"- ldd_missing_dependency_observed: {payload['ldd_missing_dependency_observed']}",
    f"- runtime_returncode: {payload['runtime_returncode']}",
    f"- runtime_timed_out: {payload['runtime_timed_out']}",
    f"- runtime_completed: {payload['runtime_completed']}",
    f"- hbm_load_success_observed: {payload['hbm_load_success_observed']}",
    f"- prefill_model_load_success_observed: {payload['prefill_model_load_success_observed']}",
    f"- decode_model_load_success_observed: {payload['decode_model_load_success_observed']}",
    f"- init_model_success_observed: {payload['init_model_success_observed']}",
    f"- memory_alloc_failure_observed: {payload['memory_alloc_failure_observed']}",
    f"- ion_alloc_failure_observed: {payload['ion_alloc_failure_observed']}",
    f"- bpu_mem_pool_alloc_error_observed: {payload['bpu_mem_pool_alloc_error_observed']}",
    f"- segmentation_fault_observed: {payload['segmentation_fault_observed']}",
    f"- official_qwen_runtime_supported_on_current_s100p_state: {payload['official_qwen_runtime_supported_on_current_s100p_state']}",
    f"- same_failure_class_as_dream: {payload['same_failure_class_as_dream']}",
    f"- next_probe_target: {payload['next_probe_target']}",
    "",
    "## Comparison To Dream",
    "",
    f"- reason: {comparison_reason}",
    f"- dream.diagnosis: {dream_summary.get('diagnosis')}",
    f"- dream.runtime_load_to_run_ratio: {dream_summary.get('runtime_load_to_run_ratio')}",
    f"- dream.systemd_load_to_run_ratio: {dream_summary.get('systemd_load_to_run_ratio')}",
    f"- dream.window3_stderr_contains_memory_alloc_failure: {dream_summary.get('window3_stderr_contains_memory_alloc_failure')}",
    f"- dream.selected_triplet_forward_supported: {dream_summary.get('selected_triplet_forward_supported')}",
    "",
    "## Captured Files",
    "",
    f"- stdout: {payload['captured_stdout_path']}",
    f"- stderr: {payload['captured_stderr_path']}",
    f"- ldd: {payload['captured_ldd_path']}",
    "",
    "## Warnings",
    "",
    *warning_lines,
    "",
    "## Errors",
    "",
    *error_lines,
    "",
]
(run_dir / "official_qwen_runtime_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "official_qwen_runtime_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
