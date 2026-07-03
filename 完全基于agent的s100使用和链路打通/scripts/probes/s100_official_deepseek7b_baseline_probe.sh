#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_OFFICIAL_DEEPSEEK7B_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"
model_dir="${S100_OFFICIAL_DEEPSEEK7B_MODEL_DIR:-/mnt/nas/openclaw/models/s100-official-deepseek-r1-distill-qwen-7b}"
hbm_url="${S100_OFFICIAL_DEEPSEEK7B_HBM_URL:-https://d-robotics-aitoolchain.oss-cn-beijing.aliyuncs.com/llm_s100/1.0.0/models/DeepSeek_R1_Distill_Qwen_7B_1024.hbm}"
hbm_filename="${S100_OFFICIAL_DEEPSEEK7B_HBM_FILENAME:-DeepSeek_R1_Distill_Qwen_7B_1024.hbm}"
run_download="${S100_OFFICIAL_DEEPSEEK7B_RUN_DOWNLOAD:-1}"
run_runtime="${S100_OFFICIAL_DEEPSEEK7B_RUN_RUNTIME:-1}"
runtime_timeout_seconds="${S100_OFFICIAL_DEEPSEEK7B_RUNTIME_TIMEOUT_SECONDS:-180}"
monitor_delay_ms="${S100_OFFICIAL_DEEPSEEK7B_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${S100_OFFICIAL_DEEPSEEK7B_MONITOR_SAMPLE_COUNT:-240}"
prompt_text="${S100_OFFICIAL_DEEPSEEK7B_PROMPT:-hello}"

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

case "$model_dir" in
  /tmp/*|/mnt/nas/openclaw/models/s100-official-deepseek-r1-distill-qwen-7b|/mnt/nas/openclaw/models/s100-official-deepseek-r1-distill-qwen-7b/*|/root/.openclaw/workspace/models/s100-official-deepseek-r1-distill-qwen-7b|/root/.openclaw/workspace/models/s100-official-deepseek-r1-distill-qwen-7b/*) ;;
  *)
    echo "Refusing model path outside approved DeepSeek 7B directories: $model_dir" >&2
    exit 2
    ;;
esac

case "$run_download" in
  0|1) ;;
  *)
    echo "S100_OFFICIAL_DEEPSEEK7B_RUN_DOWNLOAD must be 0 or 1." >&2
    exit 2
    ;;
esac

case "$run_runtime" in
  0|1) ;;
  *)
    echo "S100_OFFICIAL_DEEPSEEK7B_RUN_RUNTIME must be 0 or 1." >&2
    exit 2
    ;;
esac

for value in "$runtime_timeout_seconds" "$monitor_delay_ms" "$monitor_sample_count"; do
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "Numeric DeepSeek 7B probe parameters must be positive integers." >&2
    exit 2
  fi
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_official_deepseek7b_baseline_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$sdk_root" \
  "$model_dir" \
  "$hbm_url" \
  "$hbm_filename" \
  "$run_download" \
  "$run_runtime" \
  "$runtime_timeout_seconds" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$prompt_text" <<'PY'
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
sdk_root = Path(sys.argv[2])
model_dir = Path(sys.argv[3])
hbm_url = sys.argv[4]
hbm_filename = sys.argv[5]
run_download = sys.argv[6] == "1"
run_runtime = sys.argv[7] == "1"
runtime_timeout_seconds = int(sys.argv[8])
monitor_delay_ms = int(sys.argv[9])
monitor_sample_count = int(sys.argv[10])
prompt_text = sys.argv[11]

runtime_root = sdk_root / "oellm_runtime"
runtime_example_dir = runtime_root / "example" / "oellm_multichat"
runtime_bin = runtime_example_dir / "oellm_multichat"
runtime_lib_dir = runtime_root / "lib"
official_deepseek_config = runtime_example_dir / "deepseek_multichat_config.json"
resolve_model_path = runtime_root / "model" / "resolve_model_nash-m.txt"
deepseek_tokenizer_dir = runtime_root / "config" / "DeepSeek_R1_Distill_Qwen_7B_config"
deepseek_template_path = deepseek_tokenizer_dir / "DeepSeek_R1_Distill_Qwen_7B.jinja"
hbm_path = model_dir / hbm_filename
isolated_runtime_dir = run_dir / "isolated_runtime"
isolated_runtime_config = isolated_runtime_dir / "deepseek7b_multichat_config.json"
runtime_stdout_path = run_dir / "oellm_multichat.stdout.txt"
runtime_stderr_path = run_dir / "oellm_multichat.stderr.txt"
runtime_ldd_path = run_dir / "oellm_multichat.ldd.txt"
download_stdout_path = run_dir / "download.stdout.txt"
download_stderr_path = run_dir / "download.stderr.txt"
monitor_stdout_path = run_dir / "hrt_ucp_monitor.stdout"
monitor_stderr_path = run_dir / "hrt_ucp_monitor.stderr"

errors: list[str] = []
warnings: list[str] = []


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_capture(cmd, cwd=None, timeout=None, env=None, stdin_text=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            input=stdin_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
        return {
            "command": cmd,
            "returncode": result.returncode,
            "timed_out": False,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "returncode": None,
            "timed_out": True,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }


def latest_json(root: Path, pattern: str):
    paths = [path for path in root.glob(pattern) if path.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, None


def parse_bpu_samples(text: str):
    return [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", text)]


def parse_performance(text: str):
    match = re.search(r"Performance\s+prefill:\s*([0-9.]+)tokens/s\s+decode:\s*([0-9.]+)tokens/s", text)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def parse_bpu_alloc_request_bytes(text: str):
    matches = re.findall(r"Cannot malloc bpu memory with length\s+([0-9]+)\s+bytes", text)
    if not matches:
        return None
    return max(int(item) for item in matches)


def file_size(path: Path):
    return path.stat().st_size if path.is_file() else 0


model_dir.mkdir(parents=True, exist_ok=True)

meminfo_text = read_text(Path("/proc/meminfo"))
cmdline_text = read_text(Path("/proc/cmdline"))
df_result = run_capture(["df", "-h", str(model_dir.parent), str(run_dir.parent)], timeout=20)
url_spider_result = run_capture(["wget", "--spider", "-S", hbm_url], timeout=60)

(run_dir / "meminfo.txt").write_text(meminfo_text, encoding="utf-8", errors="replace")
(run_dir / "cmdline.txt").write_text(cmdline_text, encoding="utf-8", errors="replace")
(run_dir / "df.txt").write_text((df_result["stdout"] or "") + (df_result["stderr"] or ""), encoding="utf-8", errors="replace")
(run_dir / "url_spider.stdout.txt").write_text(url_spider_result["stdout"], encoding="utf-8", errors="replace")
(run_dir / "url_spider.stderr.txt").write_text(url_spider_result["stderr"], encoding="utf-8", errors="replace")

download_result = None
download_status = "skipped_existing_hbm" if hbm_path.is_file() and file_size(hbm_path) > 0 else "not_started"
if run_download and not (hbm_path.is_file() and file_size(hbm_path) > 0):
    download_status = "running"
    download_result = run_capture(["wget", "-c", hbm_url, "-O", str(hbm_path)], timeout=21600)
    download_stdout_path.write_text(download_result["stdout"], encoding="utf-8", errors="replace")
    download_stderr_path.write_text(download_result["stderr"], encoding="utf-8", errors="replace")
    download_status = "completed" if download_result["returncode"] == 0 and hbm_path.is_file() else "failed"
elif not run_download and not hbm_path.is_file():
    download_status = "blocked_missing_hbm_download_disabled"

runtime_config_template = read_json(official_deepseek_config)

if not sdk_root.is_dir():
    errors.append(f"missing SDK root: {sdk_root}")
if not runtime_root.is_dir():
    errors.append(f"missing oellm_runtime directory: {runtime_root}")
if not runtime_bin.is_file():
    errors.append(f"missing oellm_multichat binary: {runtime_bin}")
if not runtime_lib_dir.is_dir():
    errors.append(f"missing oellm_runtime lib directory: {runtime_lib_dir}")
if not official_deepseek_config.is_file():
    errors.append(f"missing official deepseek_multichat_config.json: {official_deepseek_config}")
if not deepseek_tokenizer_dir.is_dir():
    errors.append(f"missing DeepSeek 7B tokenizer/config directory: {deepseek_tokenizer_dir}")
if not deepseek_template_path.is_file():
    errors.append(f"missing DeepSeek 7B template: {deepseek_template_path}")
if not hbm_path.is_file() or file_size(hbm_path) <= 0:
    errors.append(f"missing DeepSeek 7B HBM: {hbm_path}")

isolated_runtime_config_written = False
ldd_result = None
runtime_result = None
monitor_result = None
runtime_status = "not_started"

if not errors and run_runtime:
    isolated_runtime_dir.mkdir(parents=True, exist_ok=True)
    isolated_config = dict(runtime_config_template)
    isolated_config["hbm_path"] = str(hbm_path)
    isolated_config["tokenizer_dir"] = str(deepseek_tokenizer_dir)
    isolated_config["template_path"] = str(deepseek_template_path)
    isolated_config.setdefault("model_type", 1)
    isolated_runtime_config.write_text(json.dumps(isolated_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    isolated_runtime_config_written = True

    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(runtime_lib_dir)
    ldd_result = run_capture(["ldd", str(runtime_bin)], cwd=runtime_example_dir, timeout=20, env=env)
    runtime_ldd_path.write_text((ldd_result["stdout"] or "") + (ldd_result["stderr"] or ""), encoding="utf-8", errors="replace")

    monitor_proc = None
    monitor_bin = shutil.which("hrt_ucp_monitor") or "/usr/hobot/bin/hrt_ucp_monitor"
    if Path(monitor_bin).is_file():
        monitor_proc = subprocess.Popen(
            [monitor_bin, "-b", "-e", "bpu", "-d", str(monitor_delay_ms), "-n", str(monitor_sample_count)],
            stdout=monitor_stdout_path.open("w", encoding="utf-8"),
            stderr=monitor_stderr_path.open("w", encoding="utf-8"),
        )
    else:
        warnings.append("hrt_ucp_monitor is not available; runtime will run without BPU telemetry sampling")

    runtime_result = run_capture(
        [str(runtime_bin), "-c", str(isolated_runtime_config)],
        cwd=runtime_example_dir,
        timeout=runtime_timeout_seconds,
        env=env,
        stdin_text=f"{prompt_text}\nexit\n",
    )
    runtime_stdout_path.write_text(runtime_result["stdout"], encoding="utf-8", errors="replace")
    runtime_stderr_path.write_text(runtime_result["stderr"], encoding="utf-8", errors="replace")

    if monitor_proc is not None:
        monitor_timeout = int((monitor_delay_ms * monitor_sample_count) / 1000) + 5
        try:
            monitor_proc.wait(timeout=max(2, monitor_timeout))
        except subprocess.TimeoutExpired:
            monitor_proc.terminate()
            monitor_proc.wait(timeout=5)
        monitor_result = {"returncode": monitor_proc.returncode, "timeout_seconds": monitor_timeout}

    runtime_status = "completed" if runtime_result["returncode"] == 0 and not runtime_result["timed_out"] else "failed"
elif not errors:
    runtime_status = "skipped_by_env"
else:
    runtime_status = "blocked_preflight"

runtime_text = read_text(runtime_stdout_path) + "\n" + read_text(runtime_stderr_path)
monitor_text = read_text(monitor_stdout_path)
bpu_loading_samples = parse_bpu_samples(monitor_text)
prefill_tokens_per_s, decode_tokens_per_s = parse_performance(runtime_text)

memory_alloc_failure_observed = (
    "Allocate memory failed" in runtime_text
    or "Fail to allocate common buffer" in runtime_text
    or "AllocError" in runtime_text
    or "Cannot malloc bpu memory" in runtime_text
)
bpu_alloc_request_bytes = parse_bpu_alloc_request_bytes(runtime_text)
hbm_load_success_observed = "Load hbm file" in runtime_text and "success" in runtime_text
init_model_success_observed = "Init model success" in runtime_text
prefill_model_load_success_observed = "model_name is: prefill" in runtime_text
decode_model_load_success_observed = "model_name is: decode" in runtime_text
runtime_completed = bool(runtime_result and runtime_result["returncode"] == 0 and not runtime_result["timed_out"])

qwen_path, qwen_report = latest_json(run_dir.parent, "s100_official_qwen_fullflow_*/official_qwen_fullflow_probe.json")
dream_gap_path, dream_gap = latest_json(run_dir.parent, "dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
dream_batch_path, dream_batch = latest_json(run_dir.parent, "dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json")
dream_oellm_path, dream_oellm = latest_json(run_dir.parent, "dream7b_oellm_fullflow_feasibility_*/dream7b_oellm_fullflow_feasibility_probe.json")

qwen_summary = {
    "report_path": str(qwen_path) if qwen_path else "",
    "runtime_completed": (qwen_report or {}).get("runtime_completed") if qwen_report else None,
    "runtime_returncode": (qwen_report or {}).get("runtime_returncode") if qwen_report else None,
    "cache_len": (qwen_report or {}).get("cache_len") if qwen_report else None,
    "chunk_size": (qwen_report or {}).get("chunk_size") if qwen_report else None,
    "decode_tokens_per_s": (qwen_report or {}).get("decode_tokens_per_s") if qwen_report else None,
    "memory_alloc_failure_observed": (qwen_report or {}).get("memory_alloc_failure_observed") if qwen_report else None,
}
dream_summary = {
    "oellm_report_path": str(dream_oellm_path) if dream_oellm_path else "",
    "oellm_failure_stage": (dream_oellm or {}).get("failure_stage") if dream_oellm else None,
    "oellm_compile_status": (dream_oellm or {}).get("compile_status") if dream_oellm else None,
    "utilization_gap_path": str(dream_gap_path) if dream_gap_path else "",
    "diagnosis": (dream_gap or {}).get("diagnosis") if dream_gap else None,
    "batch_telemetry_path": str(dream_batch_path) if dream_batch_path else "",
    "batch_avg_bpu_loading": (dream_batch or {}).get("avg_bpu_loading") if dream_batch else None,
    "batch_load_to_run_ratio": ((dream_batch or {}).get("forward_metrics") or {}).get("load_to_run_ratio") if dream_batch else None,
}

if runtime_result and runtime_result.get("timed_out"):
    warnings.append("DeepSeek 7B runtime timed out before completion")
if runtime_result and not runtime_completed and memory_alloc_failure_observed:
    warnings.append("DeepSeek 7B runtime reached memory allocation failure; inspect stdout/stderr")
if not bpu_loading_samples:
    warnings.append("No nonzero BPU telemetry samples parsed from hrt_ucp_monitor output")

decision = "unknown"
if runtime_completed:
    decision = "official_7b_fallback_runnable"
elif memory_alloc_failure_observed:
    decision = "official_7b_runtime_blocked_common_buffer"
elif hbm_load_success_observed or init_model_success_observed:
    decision = "official_7b_hbm_loads_but_runtime_blocked"
elif hbm_path.is_file():
    decision = "official_7b_hbm_present_but_runtime_not_proven"
else:
    decision = "official_7b_hbm_missing"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_s100_official_deepseek7b_baseline_probe" if not errors else "failed_s100_official_deepseek7b_baseline_probe",
    "run_dir": str(run_dir),
    "sdk_root": str(sdk_root),
    "model_dir": str(model_dir),
    "hbm_url": hbm_url,
    "hbm_filename": hbm_filename,
    "hbm_path": str(hbm_path),
    "hbm_exists": hbm_path.is_file(),
    "hbm_size_bytes": file_size(hbm_path),
    "download_status": download_status,
    "download_returncode": (download_result or {}).get("returncode"),
    "download_timed_out": (download_result or {}).get("timed_out") if download_result else None,
    "url_spider_returncode": url_spider_result.get("returncode"),
    "url_spider_timed_out": url_spider_result.get("timed_out"),
    "official_deepseek_config": str(official_deepseek_config),
    "official_deepseek_config_json": runtime_config_template,
    "deepseek_tokenizer_dir": str(deepseek_tokenizer_dir),
    "deepseek_template_path": str(deepseek_template_path),
    "isolated_runtime_config": str(isolated_runtime_config),
    "isolated_runtime_config_written": isolated_runtime_config_written,
    "runtime_status": runtime_status,
    "runtime_returncode": (runtime_result or {}).get("returncode"),
    "runtime_timed_out": (runtime_result or {}).get("timed_out") if runtime_result else None,
    "runtime_completed": runtime_completed,
    "runtime_timeout_seconds": runtime_timeout_seconds,
    "hbm_load_success_observed": hbm_load_success_observed,
    "prefill_model_load_success_observed": prefill_model_load_success_observed,
    "decode_model_load_success_observed": decode_model_load_success_observed,
    "init_model_success_observed": init_model_success_observed,
    "memory_alloc_failure_observed": memory_alloc_failure_observed,
    "bpu_alloc_request_bytes": bpu_alloc_request_bytes,
    "prefill_tokens_per_s": prefill_tokens_per_s,
    "decode_tokens_per_s": decode_tokens_per_s,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": len([sample for sample in bpu_loading_samples if sample > 0]),
    "max_bpu_loading": max(bpu_loading_samples) if bpu_loading_samples else 0.0,
    "avg_bpu_loading": round(sum(bpu_loading_samples) / len(bpu_loading_samples), 3) if bpu_loading_samples else 0.0,
    "monitor_result": monitor_result,
    "df_output_path": str(run_dir / "df.txt"),
    "meminfo_path": str(run_dir / "meminfo.txt"),
    "cmdline_path": str(run_dir / "cmdline.txt"),
    "captured_stdout_path": str(runtime_stdout_path),
    "captured_stderr_path": str(runtime_stderr_path),
    "captured_ldd_path": str(runtime_ldd_path),
    "captured_monitor_stdout_path": str(monitor_stdout_path),
    "captured_monitor_stderr_path": str(monitor_stderr_path),
    "comparison": {
        "qwen_1_5b_512_128": qwen_summary,
        "dream7b_segmented": dream_summary,
    },
    "decision": decision,
    "next_probe_target": "if DeepSeek 7B runtime is blocked, inspect common-buffer/BPU allocation and consider vendor-recommended ion/performance-mode changes only after preserving current Dream/Qwen state",
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "deepseek7b_baseline_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# S100 Official DeepSeek 7B Baseline Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- hbm_path: {payload['hbm_path']}",
    f"- hbm_exists: {payload['hbm_exists']}",
    f"- hbm_size_bytes: {payload['hbm_size_bytes']}",
    f"- download_status: {payload['download_status']}",
    f"- runtime_status: {payload['runtime_status']}",
    f"- runtime_returncode: {payload['runtime_returncode']}",
    f"- runtime_completed: {payload['runtime_completed']}",
    f"- hbm_load_success_observed: {payload['hbm_load_success_observed']}",
    f"- init_model_success_observed: {payload['init_model_success_observed']}",
    f"- memory_alloc_failure_observed: {payload['memory_alloc_failure_observed']}",
    f"- bpu_alloc_request_bytes: {payload['bpu_alloc_request_bytes']}",
    f"- prefill_tokens_per_s: {payload['prefill_tokens_per_s']}",
    f"- decode_tokens_per_s: {payload['decode_tokens_per_s']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- decision: {payload['decision']}",
    "",
    "## Comparison",
    "",
    f"- qwen_1_5b_512_128.runtime_completed: {qwen_summary.get('runtime_completed')}",
    f"- qwen_1_5b_512_128.runtime_returncode: {qwen_summary.get('runtime_returncode')}",
    f"- qwen_1_5b_512_128.memory_alloc_failure_observed: {qwen_summary.get('memory_alloc_failure_observed')}",
    f"- dream7b_segmented.oellm_failure_stage: {dream_summary.get('oellm_failure_stage')}",
    f"- dream7b_segmented.diagnosis: {dream_summary.get('diagnosis')}",
    f"- dream7b_segmented.batch_load_to_run_ratio: {dream_summary.get('batch_load_to_run_ratio')}",
    "",
    "## Captured Files",
    "",
    f"- stdout: {payload['captured_stdout_path']}",
    f"- stderr: {payload['captured_stderr_path']}",
    f"- monitor_stdout: {payload['captured_monitor_stdout_path']}",
    f"- isolated_runtime_config: {payload['isolated_runtime_config']}",
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
(run_dir / "deepseek7b_baseline_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "deepseek7b_baseline_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
