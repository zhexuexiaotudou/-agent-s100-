#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_QWEN_BPU_CORE_SWEEP_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"
timeout_seconds="${S100_QWEN_BPU_CORE_SWEEP_TIMEOUT_SECONDS:-45}"
cores_text="${S100_QWEN_BPU_CORE_SWEEP_CORES:--1 0 1 2 3}"

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

if ! [[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "S100_QWEN_BPU_CORE_SWEEP_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi

for core in $cores_text; do
  case "$core" in
    -1|0|1|2|3) ;;
    *)
      echo "Refusing unsupported bpu_core value: $core" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_qwen_bpu_core_sweep_$stamp"
mkdir -p "$run_dir"

python3 - "$report_root" "$sdk_root" "$run_dir" "$timeout_seconds" "$cores_text" <<'PY'
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

report_root = Path(sys.argv[1])
sdk_root = Path(sys.argv[2])
run_dir = Path(sys.argv[3])
timeout_seconds = int(sys.argv[4])
cores = [int(item) for item in sys.argv[5].split()]

runtime_root = sdk_root / "oellm_runtime"
multichat_dir = runtime_root / "example" / "oellm_multichat"
runtime_bin = multichat_dir / "oellm_multichat"
source_config_path = multichat_dir / "qwen_multichat_config.json"
runtime_lib_dir = runtime_root / "lib"
demo_source_path = multichat_dir / "oellm_multichat_demo.cc"
hb_ucp_header_path = Path("/usr/include/hobot/hb_ucp.h")

def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""

def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)

def resolve_from_multichat(raw_value):
    if not raw_value:
        return None
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return (multichat_dir / path).resolve()

def latest_json(pattern):
    paths = [p for p in report_root.glob(pattern) if p.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda p: p.stat().st_mtime)
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}

def run_process(argv, cwd, timeout, stdin_text):
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(runtime_lib_dir)
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            input=stdin_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
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

def parse_runtime_output(stdout, stderr):
    combined = strip_ansi((stdout or "") + "\n" + (stderr or ""))
    return {
        "observed_backend_values": sorted({int(value) for value in re.findall(r"backend:\s*(\d+)", combined)}),
        "observed_ucp_alloc_failure_sizes": sorted({int(value) for value in re.findall(r"Allocate memory failed,\s*size:\s*(\d+)", combined)}),
        "stderr_alloc_error_lens": sorted({int(value) for value in re.findall(r"AllocError\s*\{\s*len:\s*(\d+)\s*\}", combined)}),
        "printed_bpu_core_values": sorted({int(value) for value in re.findall(r"bpu_core:\s*(-?\d+)", combined)}),
        "ion_failure_line_count": combined.count("ION_IOC_ALLOC"),
        "memory_alloc_failure_observed": (
            "Allocate memory failed" in combined
            or "Fail to allocate common buffer" in combined
            or "AllocError" in combined
        ),
        "ion_alloc_failure_observed": "ION_IOC_ALLOC" in combined,
        "bpu_mem_pool_alloc_error_observed": "bpu_mem_pool" in combined and "AllocError" in combined,
        "segmentation_fault_observed": "Segmentation fault" in combined,
        "hbrt_prepare_bpu_task_failure_observed": "PrepareBpuTask failed" in combined,
        "hbucp_submit_task_failure_observed": "hbUCPSubmitTask" in combined and "failed" in combined,
        "submit_infer_task_failure_observed": "SubmitInferTask" in combined and "failed" in combined,
        "prefill_failure_observed": (
            "DnnModelInfer prefill failed" in combined
            or "Failed to DoPrefill" in combined
            or "Failed to XlmInferPrefill" in combined
        ),
        "panic_alloc_error_observed": "panicked at hbrt4_cmd/src/bpu_mem_pool.rs" in combined,
        "hbm_load_success_observed": "Load hbm file" in combined and "success" in combined,
        "prefill_model_load_success_observed": "model_name is: prefill" in combined,
        "decode_model_load_success_observed": "model_name is: decode" in combined,
        "init_model_success_observed": "Init model success" in combined,
        "qwen_backend_failure_lines": [
            line for line in combined.splitlines()
            if any(text in line for text in ["bpu_core:", "backend:", "Allocate memory failed", "ION_IOC_ALLOC", "AllocError", "bpu_mem_pool.rs", "Segmentation fault"])
        ][:240],
    }

def backend_bit_matches(backend_values, constants):
    matches = {}
    for backend in backend_values:
        matches[str(backend)] = [
            name for name, value in sorted(constants.items(), key=lambda kv: kv[1])
            if value != 0 and (backend & value) == value
        ]
    return matches

errors = []
warnings = []

if not runtime_bin.is_file():
    errors.append(f"official oellm_multichat binary is missing: {runtime_bin}")
if not source_config_path.is_file():
    errors.append(f"official qwen_multichat_config.json is missing: {source_config_path}")
if not runtime_lib_dir.is_dir():
    errors.append(f"official oellm_runtime lib directory is missing: {runtime_lib_dir}")
if not demo_source_path.is_file():
    errors.append(f"official oellm_multichat_demo.cc is missing: {demo_source_path}")

source_config_text = read_text(source_config_path)
try:
    source_config = json.loads(source_config_text) if source_config_text else {}
except Exception as exc:
    source_config = {}
    errors.append(f"official qwen_multichat_config.json is not valid JSON: {exc}")

hbm_path = resolve_from_multichat(source_config.get("hbm_path"))
tokenizer_dir = resolve_from_multichat(source_config.get("tokenizer_dir"))
template_path = resolve_from_multichat(source_config.get("template_path"))

if hbm_path is None or not hbm_path.is_file():
    errors.append("official Qwen HBM from qwen_multichat_config.json is missing")
if tokenizer_dir is None or not tokenizer_dir.is_dir():
    errors.append("official Qwen tokenizer_dir from qwen_multichat_config.json is missing")
if template_path is None or not template_path.is_file():
    errors.append("official Qwen template_path from qwen_multichat_config.json is missing")

demo_text = read_text(demo_source_path)
demo_bpu_core_lines = [
    {"line": index, "text": line}
    for index, line in enumerate(demo_text.splitlines(), 1)
    if any(text in line for text in ["bpu_core", "infer_backend", "kModelTypeMap"])
]
demo_supports_config_bpu_core = 'config.contains("bpu_core")' in demo_text
demo_default_bpu_core_value = -1 if "int32_t bpu_core = -1" in demo_text else None
demo_default_infer_backend = "XLM_INFER_BACKEND_BPU_ANY" if "request.infer_backend = XLM_INFER_BACKEND_BPU_ANY" in demo_text else ""

hb_ucp_backend_constants = {}
header_text = read_text(hb_ucp_header_path)
for line in header_text.splitlines():
    match = re.match(r"\s*#define\s+(HB_UCP_(?:CORE_ANY|BPU_CORE_[A-Z0-9_]+))\s+\((\d+)ULL\s*<<\s*(\d+)\)", line)
    if match:
        name, left, shift = match.groups()
        hb_ucp_backend_constants[name] = int(left) << int(shift)

case_results = []
case_report_paths = []

if not errors:
    for core in cores:
        case_name = f"bpu_core_{core}".replace("-", "minus_")
        case_dir = run_dir / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        case_config = dict(source_config)
        case_config["hbm_path"] = str(hbm_path)
        case_config["tokenizer_dir"] = str(tokenizer_dir)
        case_config["template_path"] = str(template_path)
        case_config["bpu_core"] = core
        case_config_path = case_dir / "qwen_multichat_config.json"
        case_config_path.write_text(json.dumps(case_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = run_process(
            [str(runtime_bin), "-c", str(case_config_path)],
            multichat_dir,
            timeout_seconds,
            "hello\nexit\n",
        )
        stdout_path = case_dir / "oellm_multichat.stdout.txt"
        stderr_path = case_dir / "oellm_multichat.stderr.txt"
        stdout_path.write_text(result["stdout"], encoding="utf-8", errors="replace")
        stderr_path.write_text(result["stderr"], encoding="utf-8", errors="replace")

        parsed = parse_runtime_output(result["stdout"], result["stderr"])
        runtime_completed = result["returncode"] == 0 and not result["timed_out"]
        segfault = parsed["segmentation_fault_observed"] or result["returncode"] in (-11, 139)
        functional_failure_observed = (
            parsed["memory_alloc_failure_observed"]
            or parsed["ion_alloc_failure_observed"]
            or parsed["bpu_mem_pool_alloc_error_observed"]
            or parsed["hbrt_prepare_bpu_task_failure_observed"]
            or parsed["hbucp_submit_task_failure_observed"]
            or parsed["submit_infer_task_failure_observed"]
            or parsed["prefill_failure_observed"]
            or parsed["panic_alloc_error_observed"]
            or segfault
        )
        case_payload = {
            "bpu_core": core,
            "case_dir": str(case_dir),
            "config_path": str(case_config_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "returncode": result["returncode"],
            "timed_out": result["timed_out"],
            "runtime_completed": runtime_completed,
            "segmentation_fault_observed": segfault,
            "functional_failure_observed": functional_failure_observed,
            "functional_success_observed": runtime_completed and not functional_failure_observed,
            "hbm_load_success_observed": parsed["hbm_load_success_observed"],
            "prefill_model_load_success_observed": parsed["prefill_model_load_success_observed"],
            "decode_model_load_success_observed": parsed["decode_model_load_success_observed"],
            "init_model_success_observed": parsed["init_model_success_observed"],
            "printed_bpu_core_values": parsed["printed_bpu_core_values"],
            "observed_backend_values": parsed["observed_backend_values"],
            "observed_backend_bit_matches_from_hb_ucp_header": backend_bit_matches(parsed["observed_backend_values"], hb_ucp_backend_constants),
            "observed_ucp_alloc_failure_sizes": parsed["observed_ucp_alloc_failure_sizes"],
            "stderr_alloc_error_lens": parsed["stderr_alloc_error_lens"],
            "ion_failure_line_count": parsed["ion_failure_line_count"],
            "memory_alloc_failure_observed": parsed["memory_alloc_failure_observed"],
            "ion_alloc_failure_observed": parsed["ion_alloc_failure_observed"],
            "bpu_mem_pool_alloc_error_observed": parsed["bpu_mem_pool_alloc_error_observed"],
            "hbrt_prepare_bpu_task_failure_observed": parsed["hbrt_prepare_bpu_task_failure_observed"],
            "hbucp_submit_task_failure_observed": parsed["hbucp_submit_task_failure_observed"],
            "submit_infer_task_failure_observed": parsed["submit_infer_task_failure_observed"],
            "prefill_failure_observed": parsed["prefill_failure_observed"],
            "panic_alloc_error_observed": parsed["panic_alloc_error_observed"],
            "qwen_backend_failure_lines": parsed["qwen_backend_failure_lines"],
        }
        case_json_path = case_dir / "case_result.json"
        case_md_path = case_dir / "case_result.md"
        case_json_path.write_text(json.dumps(case_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        case_md_lines = [
            f"# S100 Qwen bpu_core {core} Sweep Case",
            "",
            f"- bpu_core: {core}",
            f"- returncode: {case_payload['returncode']}",
            f"- timed_out: {case_payload['timed_out']}",
            f"- runtime_completed: {case_payload['runtime_completed']}",
            f"- segmentation_fault_observed: {case_payload['segmentation_fault_observed']}",
            f"- functional_failure_observed: {case_payload['functional_failure_observed']}",
            f"- functional_success_observed: {case_payload['functional_success_observed']}",
            f"- hbm_load_success_observed: {case_payload['hbm_load_success_observed']}",
            f"- init_model_success_observed: {case_payload['init_model_success_observed']}",
            f"- printed_bpu_core_values: {case_payload['printed_bpu_core_values']}",
            f"- observed_backend_values: {case_payload['observed_backend_values']}",
            f"- observed_backend_bit_matches_from_hb_ucp_header: {case_payload['observed_backend_bit_matches_from_hb_ucp_header']}",
            f"- observed_ucp_alloc_failure_sizes: {case_payload['observed_ucp_alloc_failure_sizes']}",
            f"- stderr_alloc_error_lens: {case_payload['stderr_alloc_error_lens']}",
            f"- memory_alloc_failure_observed: {case_payload['memory_alloc_failure_observed']}",
            f"- ion_alloc_failure_observed: {case_payload['ion_alloc_failure_observed']}",
            f"- bpu_mem_pool_alloc_error_observed: {case_payload['bpu_mem_pool_alloc_error_observed']}",
            f"- hbrt_prepare_bpu_task_failure_observed: {case_payload['hbrt_prepare_bpu_task_failure_observed']}",
            f"- hbucp_submit_task_failure_observed: {case_payload['hbucp_submit_task_failure_observed']}",
            f"- submit_infer_task_failure_observed: {case_payload['submit_infer_task_failure_observed']}",
            f"- prefill_failure_observed: {case_payload['prefill_failure_observed']}",
            f"- panic_alloc_error_observed: {case_payload['panic_alloc_error_observed']}",
        ]
        case_md_path.write_text("\n".join(case_md_lines) + "\n", encoding="utf-8")
        case_payload["case_json_path"] = str(case_json_path)
        case_payload["case_md_path"] = str(case_md_path)
        case_results.append(case_payload)
        case_report_paths.append(str(case_json_path))

backend_values_by_core = {str(item["bpu_core"]): item["observed_backend_values"] for item in case_results}
memory_alloc_failure_by_core = {str(item["bpu_core"]): item["memory_alloc_failure_observed"] for item in case_results}
runtime_completed_by_core = {str(item["bpu_core"]): item["runtime_completed"] for item in case_results}
returncode_by_core = {str(item["bpu_core"]): item["returncode"] for item in case_results}
segmentation_fault_by_core = {str(item["bpu_core"]): item["segmentation_fault_observed"] for item in case_results}
functional_failure_by_core = {str(item["bpu_core"]): item["functional_failure_observed"] for item in case_results}
functional_success_by_core = {str(item["bpu_core"]): item["functional_success_observed"] for item in case_results}
prefill_failure_by_core = {str(item["bpu_core"]): item["prefill_failure_observed"] for item in case_results}

all_cases_failed_memory = bool(case_results) and all(item["memory_alloc_failure_observed"] for item in case_results)
all_cases_failed_functionally = bool(case_results) and all(item["functional_failure_observed"] for item in case_results)
any_case_completed = any(item["runtime_completed"] for item in case_results)
any_case_functional_success = any(item["functional_success_observed"] for item in case_results)
backend_changed_by_core = len({tuple(item["observed_backend_values"]) for item in case_results}) > 1 if case_results else False
explicit_core_changed_backend_or_failure = any(
    item["bpu_core"] != -1
    and (
        item["observed_backend_values"] != backend_values_by_core.get("-1", [])
        or item["memory_alloc_failure_observed"] != memory_alloc_failure_by_core.get("-1")
        or item["runtime_completed"] != runtime_completed_by_core.get("-1")
        or item["segmentation_fault_observed"] != segmentation_fault_by_core.get("-1")
        or item["prefill_failure_observed"] != prefill_failure_by_core.get("-1")
    )
    for item in case_results
)

if case_results and all_cases_failed_memory:
    warnings.append("all tested official Qwen bpu_core values still reported memory allocation failure")
if case_results and not backend_changed_by_core:
    warnings.append("all tested official Qwen bpu_core values produced the same observed backend value set")
if case_results and not any_case_completed:
    warnings.append("no tested official Qwen bpu_core value completed the runtime")
if case_results and all_cases_failed_functionally:
    warnings.append("all tested official Qwen bpu_core values still failed functionally")

baseline_path, baseline = latest_json("s100_qwen_backend9_baseline_*/qwen_backend9_baseline_probe.json")
dream_util_path, dream_util = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")

payload = {
    "generated_at": now_iso(),
    "verdict": "ok_s100_qwen_bpu_core_sweep_probe" if not errors else "failed_s100_qwen_bpu_core_sweep_probe",
    "run_dir": str(run_dir),
    "sdk_root": str(sdk_root),
    "runtime_bin": str(runtime_bin),
    "source_config_path": str(source_config_path),
    "runtime_lib_dir": str(runtime_lib_dir),
    "timeout_seconds": timeout_seconds,
    "tested_bpu_core_values": cores,
    "source_config_had_bpu_core": "bpu_core" in source_config,
    "demo_source_path": str(demo_source_path),
    "demo_supports_config_bpu_core": demo_supports_config_bpu_core,
    "demo_default_bpu_core_value": demo_default_bpu_core_value,
    "demo_default_infer_backend": demo_default_infer_backend,
    "demo_bpu_core_lines": demo_bpu_core_lines,
    "hb_ucp_header_path": str(hb_ucp_header_path),
    "hb_ucp_backend_constants": hb_ucp_backend_constants,
    "qwen_hbm_path": str(hbm_path) if hbm_path else "",
    "tokenizer_dir": str(tokenizer_dir) if tokenizer_dir else "",
    "template_path": str(template_path) if template_path else "",
    "case_count": len(case_results),
    "case_report_paths": case_report_paths,
    "case_results": case_results,
    "backend_values_by_core": backend_values_by_core,
    "memory_alloc_failure_by_core": memory_alloc_failure_by_core,
    "runtime_completed_by_core": runtime_completed_by_core,
    "returncode_by_core": returncode_by_core,
    "segmentation_fault_by_core": segmentation_fault_by_core,
    "functional_failure_by_core": functional_failure_by_core,
    "functional_success_by_core": functional_success_by_core,
    "prefill_failure_by_core": prefill_failure_by_core,
    "all_cases_failed_memory": all_cases_failed_memory,
    "all_cases_failed_functionally": all_cases_failed_functionally,
    "any_case_completed": any_case_completed,
    "any_case_functional_success": any_case_functional_success,
    "backend_changed_by_core": backend_changed_by_core,
    "explicit_core_changed_backend_or_failure": explicit_core_changed_backend_or_failure,
    "latest_backend9_baseline_report_path": str(baseline_path) if baseline_path else "",
    "latest_backend9_baseline_observed_backend_values": baseline.get("observed_backend_values"),
    "latest_backend9_baseline_direct_hbmem_matrix_qwen_sizes_pass": baseline.get("direct_hbmem_matrix_qwen_sizes_pass"),
    "dream_utilization_report_path": str(dream_util_path) if dream_util_path else "",
    "dream_diagnosis": dream_util.get("diagnosis"),
    "interpretation": (
        "explicit bpu_core values changed the official Qwen crash behavior, but no tested core produced functional inference; core pinning alone is not sufficient"
        if all_cases_failed_functionally and explicit_core_changed_backend_or_failure
        else "explicit bpu_core values changed the official Qwen backend/failure behavior; inspect the successful or less-failing core before adapting backend/core pinning to Dream 7B"
        if explicit_core_changed_backend_or_failure
        else "explicit bpu_core values did not change the observed official Qwen backend/failure class; Dream 7B should continue focusing on HBM reload/residency reduction rather than simple Qwen-style core pinning"
    ),
    "next_probe_target": (
        "treat explicit bpu_core as an optional crash-mitigation variable, but continue Dream 7B HBM reload/residency work before expecting sustained 128TOPS utilization"
        if all_cases_failed_functionally and explicit_core_changed_backend_or_failure
        else "transfer the least-failing explicit backend/core setting into a minimal Dream 7B HBM runtime experiment"
        if explicit_core_changed_backend_or_failure
        else "continue Dream 7B HBM reload/residency work; do not expect simple bpu_core pinning alone to unlock sustained 128TOPS utilization"
    ),
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "qwen_bpu_core_sweep_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# S100 Qwen bpu_core Sweep Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- tested_bpu_core_values: {payload['tested_bpu_core_values']}",
    f"- source_config_had_bpu_core: {payload['source_config_had_bpu_core']}",
    f"- demo_supports_config_bpu_core: {payload['demo_supports_config_bpu_core']}",
    f"- demo_default_bpu_core_value: {payload['demo_default_bpu_core_value']}",
    f"- demo_default_infer_backend: {payload['demo_default_infer_backend']}",
    f"- backend_values_by_core: {payload['backend_values_by_core']}",
    f"- memory_alloc_failure_by_core: {payload['memory_alloc_failure_by_core']}",
    f"- runtime_completed_by_core: {payload['runtime_completed_by_core']}",
    f"- returncode_by_core: {payload['returncode_by_core']}",
    f"- segmentation_fault_by_core: {payload['segmentation_fault_by_core']}",
    f"- functional_failure_by_core: {payload['functional_failure_by_core']}",
    f"- functional_success_by_core: {payload['functional_success_by_core']}",
    f"- prefill_failure_by_core: {payload['prefill_failure_by_core']}",
    f"- all_cases_failed_memory: {payload['all_cases_failed_memory']}",
    f"- all_cases_failed_functionally: {payload['all_cases_failed_functionally']}",
    f"- any_case_completed: {payload['any_case_completed']}",
    f"- any_case_functional_success: {payload['any_case_functional_success']}",
    f"- backend_changed_by_core: {payload['backend_changed_by_core']}",
    f"- explicit_core_changed_backend_or_failure: {payload['explicit_core_changed_backend_or_failure']}",
    f"- dream_diagnosis: {payload['dream_diagnosis']}",
    f"- interpretation: {payload['interpretation']}",
    f"- next_probe_target: {payload['next_probe_target']}",
    "",
    "## Cases",
    "",
]
for item in case_results:
    lines.append(
        f"- bpu_core={item['bpu_core']}: returncode={item['returncode']}, "
        f"runtime_completed={item['runtime_completed']}, backend={item['observed_backend_values']}, "
        f"memory_alloc_failure={item['memory_alloc_failure_observed']}, functional_success={item['functional_success_observed']}, "
        f"alloc_sizes={item['observed_ucp_alloc_failure_sizes']}, alloc_lens={item['stderr_alloc_error_lens']}"
    )
if warnings:
    lines += ["", "## Warnings", ""]
    lines += [f"- {warning}" for warning in warnings]
if errors:
    lines += ["", "## Errors", ""]
    lines += [f"- {error}" for error in errors]

(run_dir / "qwen_bpu_core_sweep_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "qwen_bpu_core_sweep_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
