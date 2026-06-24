#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_QWEN_BACKEND9_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"

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

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_qwen_backend9_baseline_$stamp"
mkdir -p "$run_dir"

python3 - "$report_root" "$sdk_root" "$run_dir" <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

report_root = Path(sys.argv[1])
sdk_root = Path(sys.argv[2])
run_dir = Path(sys.argv[3])

config_path = sdk_root / "oellm_runtime/example/oellm_multichat/qwen_multichat_config.json"
demo_source_path = sdk_root / "oellm_runtime/example/oellm_multichat/oellm_multichat_demo.cc"
runtime_lib_path = sdk_root / "oellm_runtime/lib/libhbucp.so"
hb_ucp_header_path = Path("/usr/include/hobot/hb_ucp.h")

def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""

def latest_json(pattern):
    paths = [p for p in report_root.glob(pattern) if p.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda p: p.stat().st_mtime)
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}

def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)

def write_capture(name, text):
    path = run_dir / name
    path.write_text(text, encoding="utf-8")
    return str(path)

def run_capture(cmd):
    try:
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return {
            "command": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as exc:
        return {
            "command": cmd,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }

qwen_runtime_path, qwen_runtime = latest_json("s100_official_qwen_runtime_*/official_qwen_runtime_probe.json")
hbmem_matrix_path, hbmem_matrix = latest_json("s100_hbmem_common_buffer_matrix_*/hbmem_common_buffer_matrix_probe.json")
dream_util_path, dream_util = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
dream_window3_path, dream_window3 = latest_json("dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json")

config_text = read_text(config_path)
try:
    config = json.loads(config_text) if config_text else {}
except Exception:
    config = {}

demo_text = read_text(demo_source_path)
demo_lines = demo_text.splitlines()

def matching_lines(needles):
    lines = []
    for index, line in enumerate(demo_lines, 1):
        if any(needle in line for needle in needles):
            lines.append({"line": index, "text": line})
    return lines

demo_bpu_core_lines = matching_lines(["bpu_core", "infer_backend", "kModelTypeMap", "batch_num"])
demo_default_bpu_core_value = None
for item in demo_bpu_core_lines:
    if "int32_t bpu_core = -1" in item["text"]:
        demo_default_bpu_core_value = -1

demo_default_infer_backend = ""
for item in demo_bpu_core_lines:
    if "request.infer_backend = XLM_INFER_BACKEND_BPU_ANY" in item["text"]:
        demo_default_infer_backend = "XLM_INFER_BACKEND_BPU_ANY"

header_text = read_text(hb_ucp_header_path)
hb_ucp_backend_constants = {}
for line in header_text.splitlines():
    match = re.match(r"\s*#define\s+(HB_UCP_(?:CORE_ANY|BPU_CORE_[A-Z0-9_]+))\s+\((\d+)ULL\s*<<\s*(\d+)\)", line)
    if match:
        name, left, shift = match.groups()
        hb_ucp_backend_constants[name] = int(left) << int(shift)

runtime_dir = qwen_runtime_path.parent if qwen_runtime_path else None
qwen_stdout = read_text(runtime_dir / "oellm_multichat.stdout.txt") if runtime_dir else ""
qwen_stderr = read_text(runtime_dir / "oellm_multichat.stderr.txt") if runtime_dir else ""
combined_qwen_output = strip_ansi(qwen_stdout + "\n" + qwen_stderr)

observed_backend_values = sorted({int(value) for value in re.findall(r"backend:\s*(\d+)", combined_qwen_output)})
observed_ucp_alloc_failure_sizes = sorted({int(value) for value in re.findall(r"Allocate memory failed,\s*size:\s*(\d+)", combined_qwen_output)})
stderr_alloc_error_lens = sorted({int(value) for value in re.findall(r"AllocError\s*\{\s*len:\s*(\d+)\s*\}", combined_qwen_output)})
ion_failure_line_count = combined_qwen_output.count("ION_IOC_ALLOC")

backend_bit_matches = {}
for backend in observed_backend_values:
    backend_bit_matches[str(backend)] = [
        name for name, value in sorted(hb_ucp_backend_constants.items(), key=lambda kv: kv[1])
        if value != 0 and (backend & value) == value
    ]

backend_9_equals_hb_ucp_bpu_core_any = None
if "HB_UCP_BPU_CORE_ANY" in hb_ucp_backend_constants:
    backend_9_equals_hb_ucp_bpu_core_any = hb_ucp_backend_constants["HB_UCP_BPU_CORE_ANY"] == 9

nm_capture = run_capture(["nm", "-D", "--defined-only", str(runtime_lib_path)])
strings_capture = run_capture(["strings", str(runtime_lib_path)])
nm_relevant_lines = [
    line for line in nm_capture["stdout"].splitlines()
    if any(text in line for text in ["hbUCP", "Backend", "Malloc", "Mem", "Schedule"])
][:160]
strings_relevant_lines = [
    line for line in strings_capture["stdout"].splitlines()
    if any(text in line for text in ["backend", "Backend", "HB_UCP", "hbUCP", "UCP", "Malloc", "Allocate memory", "BPU_CORE", "core"])
][:220]

captures = {
    "qwen_multichat_config": write_capture("qwen_multichat_config.json", config_text),
    "oellm_multichat_demo_bpu_core_lines": write_capture(
        "oellm_multichat_demo_bpu_core_lines.txt",
        "\n".join(f"{item['line']}: {item['text']}" for item in demo_bpu_core_lines) + "\n",
    ),
    "hb_ucp_backend_constants": write_capture(
        "hb_ucp_backend_constants.txt",
        "\n".join(f"{name}={value}" for name, value in sorted(hb_ucp_backend_constants.items(), key=lambda kv: kv[1])) + "\n",
    ),
    "qwen_backend_failure_lines": write_capture(
        "qwen_backend_failure_lines.txt",
        "\n".join(
            line for line in combined_qwen_output.splitlines()
            if any(text in line for text in ["backend:", "Allocate memory failed", "ION_IOC_ALLOC", "AllocError", "bpu_mem_pool.rs"])
        )[:20000] + "\n",
    ),
    "libhbucp_nm_relevant": write_capture("libhbucp_nm_relevant.txt", "\n".join(nm_relevant_lines) + "\n"),
    "libhbucp_strings_relevant": write_capture("libhbucp_strings_relevant.txt", "\n".join(strings_relevant_lines) + "\n"),
}

official_qwen_has_similar_bpu_memory_issue = bool(
    qwen_runtime.get("memory_alloc_failure_observed")
    or observed_ucp_alloc_failure_sizes
    or stderr_alloc_error_lens
    or ion_failure_line_count
)

direct_hbmem_matrix_qwen_sizes_pass = (
    hbmem_matrix.get("qwen_log_size_success_count", 0) > 0
    and hbmem_matrix.get("qwen_log_size_failure_count") == 0
)

official_qwen_issue_not_raw_size_only = bool(
    official_qwen_has_similar_bpu_memory_issue
    and direct_hbmem_matrix_qwen_sizes_pass
)

errors = []
warnings = []
if not config_path.is_file():
    errors.append(f"official qwen_multichat_config.json is missing: {config_path}")
if not demo_source_path.is_file():
    errors.append(f"official oellm_multichat_demo.cc is missing: {demo_source_path}")
if not hb_ucp_header_path.is_file():
    errors.append(f"hb_ucp.h is missing: {hb_ucp_header_path}")
if not qwen_runtime_path:
    warnings.append("latest official Qwen runtime report was not found")
if not hbmem_matrix_path:
    warnings.append("latest S100 HBMEM/UCP allocation matrix report was not found")
if observed_backend_values and 9 in observed_backend_values and backend_9_equals_hb_ucp_bpu_core_any is False:
    warnings.append("observed Qwen backend: 9 does not equal HB_UCP_BPU_CORE_ANY from /usr/include/hobot/hb_ucp.h")
if official_qwen_issue_not_raw_size_only:
    warnings.append("official Qwen has a BPU/common-buffer allocation failure even though direct HBMEM/UCP allocation of logged Qwen sizes passed")

payload = {
    "generated_at": now_iso(),
    "verdict": "ok_s100_qwen_backend9_baseline_probe" if not errors else "failed_s100_qwen_backend9_baseline_probe",
    "run_dir": str(run_dir),
    "sdk_root": str(sdk_root),
    "qwen_multichat_config_path": str(config_path),
    "qwen_multichat_config": config,
    "config_has_bpu_core": "bpu_core" in config,
    "config_bpu_core_value": config.get("bpu_core"),
    "demo_source_path": str(demo_source_path),
    "demo_default_bpu_core_value": demo_default_bpu_core_value,
    "demo_default_infer_backend": demo_default_infer_backend,
    "demo_bpu_core_lines": demo_bpu_core_lines,
    "hb_ucp_header_path": str(hb_ucp_header_path),
    "hb_ucp_backend_constants": hb_ucp_backend_constants,
    "observed_backend_values": observed_backend_values,
    "observed_backend_bit_matches_from_hb_ucp_header": backend_bit_matches,
    "backend_9_equals_hb_ucp_bpu_core_any": backend_9_equals_hb_ucp_bpu_core_any,
    "observed_ucp_alloc_failure_sizes": observed_ucp_alloc_failure_sizes,
    "stderr_alloc_error_lens": stderr_alloc_error_lens,
    "ion_failure_line_count": ion_failure_line_count,
    "qwen_runtime_report_path": str(qwen_runtime_path) if qwen_runtime_path else "",
    "qwen_runtime_returncode": qwen_runtime.get("runtime_returncode"),
    "qwen_runtime_completed": qwen_runtime.get("runtime_completed"),
    "qwen_hbm_load_success_observed": qwen_runtime.get("hbm_load_success_observed"),
    "qwen_init_model_success_observed": qwen_runtime.get("init_model_success_observed"),
    "qwen_memory_alloc_failure_observed": qwen_runtime.get("memory_alloc_failure_observed"),
    "qwen_ion_alloc_failure_observed": qwen_runtime.get("ion_alloc_failure_observed"),
    "qwen_bpu_mem_pool_alloc_error_observed": qwen_runtime.get("bpu_mem_pool_alloc_error_observed"),
    "qwen_segmentation_fault_observed": qwen_runtime.get("segmentation_fault_observed"),
    "qwen_same_failure_class_as_dream": qwen_runtime.get("same_failure_class_as_dream"),
    "hbmem_matrix_report_path": str(hbmem_matrix_path) if hbmem_matrix_path else "",
    "hbmem_matrix_qwen_log_size_success_count": hbmem_matrix.get("qwen_log_size_success_count"),
    "hbmem_matrix_qwen_log_size_failure_count": hbmem_matrix.get("qwen_log_size_failure_count"),
    "hbmem_matrix_ucp_success_count": hbmem_matrix.get("ucp_success_count"),
    "direct_hbmem_matrix_qwen_sizes_pass": direct_hbmem_matrix_qwen_sizes_pass,
    "official_qwen_has_similar_bpu_memory_issue": official_qwen_has_similar_bpu_memory_issue,
    "official_qwen_issue_not_raw_size_only": official_qwen_issue_not_raw_size_only,
    "dream_utilization_report_path": str(dream_util_path) if dream_util_path else "",
    "dream_diagnosis": dream_util.get("diagnosis"),
    "dream_max_observed_bpu_loading": dream_util.get("max_observed_bpu_loading"),
    "dream_avg_observed_bpu_loading_across_reports": dream_util.get("avg_observed_bpu_loading_across_reports"),
    "dream_window3_report_path": str(dream_window3_path) if dream_window3_path else "",
    "dream_window3_stderr_contains_memory_alloc_failure": dream_window3.get("stderr_contains_memory_alloc_failure"),
    "comparison": {
        "official_qwen_route": "official Qwen uses vendor qwen_multichat_config.json, vendor Qwen2.5_1.5B_Instruct_1024.hbm, and oellm_multichat",
        "dream_route": "Dream 7B uses project-created segmented S100 .hbm artifacts and the dream7b-bpu-fine-batch-forward path",
        "similarity": "both official Qwen and Dream evidence include BPU/common-buffer memory allocation failures on this S100P state",
        "difference": "official Qwen fails after vendor HBM/model load during UCP/ION/BPU memory allocation, while Dream already executes bounded seq16 batch BPU runs and its sustained average utilization is diagnosed as hbm_reload_dominated",
    },
    "next_probe_target": "run a controlled official Qwen bpu_core sweep by copying qwen_multichat_config.json and adding exact bpu_core values -1, 0, 1, 2, and 3; compare backend values and memory failures before transferring any backend/core-pinning idea to Dream 7B",
    "captures": captures,
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "qwen_backend9_baseline_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# S100 Qwen Backend 9 Baseline Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- qwen_runtime_report_path: {payload['qwen_runtime_report_path']}",
    f"- qwen_runtime_completed: {payload['qwen_runtime_completed']}",
    f"- qwen_runtime_returncode: {payload['qwen_runtime_returncode']}",
    f"- qwen_hbm_load_success_observed: {payload['qwen_hbm_load_success_observed']}",
    f"- qwen_init_model_success_observed: {payload['qwen_init_model_success_observed']}",
    f"- qwen_memory_alloc_failure_observed: {payload['qwen_memory_alloc_failure_observed']}",
    f"- qwen_ion_alloc_failure_observed: {payload['qwen_ion_alloc_failure_observed']}",
    f"- qwen_bpu_mem_pool_alloc_error_observed: {payload['qwen_bpu_mem_pool_alloc_error_observed']}",
    f"- qwen_segmentation_fault_observed: {payload['qwen_segmentation_fault_observed']}",
    f"- config_has_bpu_core: {payload['config_has_bpu_core']}",
    f"- config_bpu_core_value: {payload['config_bpu_core_value']}",
    f"- demo_default_bpu_core_value: {payload['demo_default_bpu_core_value']}",
    f"- demo_default_infer_backend: {payload['demo_default_infer_backend']}",
    f"- observed_backend_values: {payload['observed_backend_values']}",
    f"- observed_backend_bit_matches_from_hb_ucp_header: {payload['observed_backend_bit_matches_from_hb_ucp_header']}",
    f"- backend_9_equals_hb_ucp_bpu_core_any: {payload['backend_9_equals_hb_ucp_bpu_core_any']}",
    f"- observed_ucp_alloc_failure_sizes: {payload['observed_ucp_alloc_failure_sizes']}",
    f"- stderr_alloc_error_lens: {payload['stderr_alloc_error_lens']}",
    f"- hbmem_matrix_qwen_log_size_success_count: {payload['hbmem_matrix_qwen_log_size_success_count']}",
    f"- hbmem_matrix_qwen_log_size_failure_count: {payload['hbmem_matrix_qwen_log_size_failure_count']}",
    f"- direct_hbmem_matrix_qwen_sizes_pass: {payload['direct_hbmem_matrix_qwen_sizes_pass']}",
    f"- official_qwen_has_similar_bpu_memory_issue: {payload['official_qwen_has_similar_bpu_memory_issue']}",
    f"- official_qwen_issue_not_raw_size_only: {payload['official_qwen_issue_not_raw_size_only']}",
    f"- dream_diagnosis: {payload['dream_diagnosis']}",
    f"- dream_window3_stderr_contains_memory_alloc_failure: {payload['dream_window3_stderr_contains_memory_alloc_failure']}",
    "",
    "## Comparison",
    "",
    f"- official_qwen_route: {payload['comparison']['official_qwen_route']}",
    f"- dream_route: {payload['comparison']['dream_route']}",
    f"- similarity: {payload['comparison']['similarity']}",
    f"- difference: {payload['comparison']['difference']}",
    "",
    f"- next_probe_target: {payload['next_probe_target']}",
]
if warnings:
    lines += ["", "## Warnings", ""]
    lines += [f"- {warning}" for warning in warnings]
if errors:
    lines += ["", "## Errors", ""]
    lines += [f"- {error}" for error in errors]

(run_dir / "qwen_backend9_baseline_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "qwen_backend9_baseline_probe.md")
PY
