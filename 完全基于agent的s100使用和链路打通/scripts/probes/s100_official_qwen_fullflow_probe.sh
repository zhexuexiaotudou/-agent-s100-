#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_OFFICIAL_QWEN_FULLFLOW_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"
source_model_dir="${S100_OFFICIAL_QWEN_FULLFLOW_SOURCE_MODEL_DIR:-}"
output_model_path="${S100_OFFICIAL_QWEN_FULLFLOW_OUTPUT_MODEL_PATH:-/mnt/nas/openclaw/models/s100-official-qwen-fullflow}"
venv_dir="${S100_OFFICIAL_QWEN_FULLFLOW_VENV_DIR:-/tmp/s100-official-qwen-fullflow-venv}"
python_bin="${S100_OFFICIAL_QWEN_FULLFLOW_PYTHON:-python3.10}"
model_name="${S100_OFFICIAL_QWEN_FULLFLOW_MODEL_NAME:-qwen2_5-1_5b}"
march="${S100_OFFICIAL_QWEN_FULLFLOW_MARCH:-nash-m}"
cache_len="${S100_OFFICIAL_QWEN_FULLFLOW_CACHE_LEN:-512}"
chunk_size="${S100_OFFICIAL_QWEN_FULLFLOW_CHUNK_SIZE:-128}"
w_bits="${S100_OFFICIAL_QWEN_FULLFLOW_W_BITS:-8}"
runtime_timeout_seconds="${S100_OFFICIAL_QWEN_FULLFLOW_RUNTIME_TIMEOUT_SECONDS:-60}"
monitor_delay_ms="${S100_OFFICIAL_QWEN_FULLFLOW_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${S100_OFFICIAL_QWEN_FULLFLOW_MONITOR_SAMPLE_COUNT:-160}"
run_runtime="${S100_OFFICIAL_QWEN_FULLFLOW_RUN_RUNTIME:-1}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$sdk_root" in
  /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK|/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/|/opt/D-Robotics_LLM_S100_1.0.0_SDK|/opt/D-Robotics_LLM_S100_1.0.0_SDK/|/mnt/f/Project/Digua/tmp/s100_llm_sdk/inspect/D-Robotics_LLM_S100_1.0.0_SDK|/mnt/f/Project/Digua/tmp/s100_llm_sdk/inspect/D-Robotics_LLM_S100_1.0.0_SDK/) ;;
  *)
    echo "Refusing SDK path outside approved S100 official LLM SDK directories: $sdk_root" >&2
    exit 2
    ;;
esac

case "$output_model_path" in
  /tmp/*|/mnt/f/Project/Digua/tmp/models/s100-official-qwen-fullflow|/mnt/f/Project/Digua/tmp/models/s100-official-qwen-fullflow/*|/mnt/nas/openclaw/models/s100-official-qwen-fullflow|/mnt/nas/openclaw/models/s100-official-qwen-fullflow/*|/root/.openclaw/workspace/models/s100-official-qwen-fullflow|/root/.openclaw/workspace/models/s100-official-qwen-fullflow/*) ;;
  *)
    echo "Refusing output model path outside approved Qwen fullflow directories: $output_model_path" >&2
    exit 2
    ;;
esac

case "$venv_dir" in
  /tmp/*|/mnt/nas/openclaw/tmp/*|/root/.openclaw/workspace/tmp/*) ;;
  *)
    echo "Refusing venv path outside approved temporary directories: $venv_dir" >&2
    exit 2
    ;;
esac

for value in "$cache_len" "$chunk_size" "$w_bits" "$runtime_timeout_seconds" "$monitor_delay_ms" "$monitor_sample_count"; do
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "Numeric fullflow parameters must be positive integers." >&2
    exit 2
  fi
done

case "$run_runtime" in
  0|1) ;;
  *)
    echo "S100_OFFICIAL_QWEN_FULLFLOW_RUN_RUNTIME must be 0 or 1." >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_official_qwen_fullflow_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$sdk_root" \
  "$source_model_dir" \
  "$output_model_path" \
  "$venv_dir" \
  "$python_bin" \
  "$model_name" \
  "$march" \
  "$cache_len" \
  "$chunk_size" \
  "$w_bits" \
  "$runtime_timeout_seconds" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$run_runtime" <<'PY'
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
sdk_root = Path(sys.argv[2])
source_model_dir_arg = sys.argv[3]
output_model_path = Path(sys.argv[4])
venv_dir = Path(sys.argv[5])
python_bin = sys.argv[6]
model_name = sys.argv[7]
march = sys.argv[8]
cache_len = int(sys.argv[9])
chunk_size = int(sys.argv[10])
w_bits = int(sys.argv[11])
runtime_timeout_seconds = int(sys.argv[12])
monitor_delay_ms = int(sys.argv[13])
monitor_sample_count = int(sys.argv[14])
run_runtime = sys.argv[15] == "1"

build_root = sdk_root / "oellm_build"
runtime_root = sdk_root / "oellm_runtime"
runtime_example_dir = runtime_root / "example" / "oellm_multichat"
runtime_bin = runtime_example_dir / "oellm_multichat"
runtime_lib_dir = runtime_root / "lib"
official_runtime_config = runtime_example_dir / "qwen_multichat_config.json"
calib_text_path = run_dir / "calib_prompts.json"
isolated_runtime_dir = run_dir / "isolated_runtime"
isolated_runtime_config = isolated_runtime_dir / "qwen_fullflow_config.json"
build_stdout = run_dir / "oellm_build.stdout.txt"
build_stderr = run_dir / "oellm_build.stderr.txt"
runtime_stdout = run_dir / "oellm_multichat.stdout.txt"
runtime_stderr = run_dir / "oellm_multichat.stderr.txt"
monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"

errors: list[str] = []
warnings: list[str] = []


def now_iso():
    return datetime.now().astimezone().isoformat()


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
    except Exception as exc:
        return {
            "command": cmd,
            "returncode": None,
            "timed_out": False,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def find_wheel(prefix: str):
    wheels = sorted(build_root.glob(f"{prefix}*.whl"))
    return wheels[0] if wheels else None


def supported_models_from_wheel():
    wheel = find_wheel("leap_llm-")
    if not wheel:
        return []
    try:
        with zipfile.ZipFile(wheel) as archive:
            text = archive.read("leap_llm/apis/model/model_factory.py").decode("utf-8", errors="replace")
    except Exception:
        return []
    return re.findall(r'@register_model\("([^"]+)"', text)


def source_candidates():
    if source_model_dir_arg:
        return [Path(source_model_dir_arg)]
    return [
        Path("/mnt/nas/openclaw/models/qwen2_5-1_5b-hf"),
        Path("/mnt/nas/openclaw/models/Qwen2.5-1.5B-Instruct"),
        Path("/mnt/nas/openclaw/models/Qwen2.5_1.5B_Instruct"),
        Path("/root/.openclaw/workspace/models/qwen2_5-1_5b-hf"),
    ]


def select_source_model_dir():
    for candidate in source_candidates():
        if (candidate / "config.json").is_file():
            return candidate
    return source_candidates()[0]


def resolve_runtime_path(raw: str | None):
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return (runtime_example_dir / path).resolve()


def parse_bpu_samples(text: str):
    return [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", text)]


source_model_dir = select_source_model_dir()
calib_text_path.write_text(
    json.dumps(
        [
            {"text": "Explain the purpose of an embedded AI accelerator in one sentence."},
            {"text": "List two checks needed before deploying a language model to S100P."},
        ],
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

machine = platform.machine()
cpuinfo = read_text(Path("/proc/cpuinfo"))
host_has_avx = " avx " in f" {cpuinfo.lower()} "
sdk_exists = sdk_root.is_dir()
build_root_exists = build_root.is_dir()
runtime_root_exists = runtime_root.is_dir()
source_model_exists = (source_model_dir / "config.json").is_file()
supported_models = supported_models_from_wheel()
model_registered = model_name in supported_models
build_host_compatible = machine == "x86_64" and host_has_avx

hbdk_wheel = find_wheel("hbdk4_compiler-")
leap_wheel = find_wheel("leap_llm-")
requirements = build_root / "requirements.txt"
build_status = "not_started"
build_result = None
import_result = None
compiled_hbms: list[Path] = []

if not sdk_exists:
    errors.append(f"missing SDK root: {sdk_root}")
if not build_root_exists:
    errors.append(f"missing SDK oellm_build directory: {build_root}")
if not runtime_root_exists:
    warnings.append(f"missing SDK oellm_runtime directory: {runtime_root}")
if not source_model_exists:
    errors.append(f"missing Qwen source model config: {source_model_dir / 'config.json'}")
if supported_models and not model_registered:
    errors.append(f"{model_name} is not registered in official leap_llm model_factory")
if not build_host_compatible:
    errors.append("build host is not compatible: x86_64 with AVX is required for HBDK compiler import")
if not hbdk_wheel:
    errors.append("missing hbdk4 compiler wheel in SDK oellm_build")
if not leap_wheel:
    errors.append("missing leap_llm wheel in SDK oellm_build")
if not requirements.is_file():
    errors.append("missing SDK oellm_build requirements.txt")

can_attempt_build = (
    sdk_exists
    and build_root_exists
    and source_model_exists
    and build_host_compatible
    and hbdk_wheel is not None
    and leap_wheel is not None
    and requirements.is_file()
    and (not supported_models or model_registered)
)

if can_attempt_build:
    output_model_path.mkdir(parents=True, exist_ok=True)
    build_status = "running"
    setup_commands = [
        [python_bin, "-m", "venv", str(venv_dir)],
    ]
    setup_results = []
    for cmd in setup_commands:
        setup_results.append(run_capture(cmd, timeout=600))
    venv_python = venv_dir / "bin" / "python"
    oellm_build_bin = venv_dir / "bin" / "oellm_build"
    if not venv_python.is_file():
        errors.append(f"venv python was not created: {venv_python}")
        build_status = "venv_failed"
    else:
        install_cmds = [
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
            [str(venv_python), "-m", "pip", "install", "-r", str(requirements)],
            [str(venv_python), "-m", "pip", "install", str(hbdk_wheel), str(leap_wheel)],
        ]
        for cmd in install_cmds:
            setup_results.append(run_capture(cmd, timeout=1800))
        (run_dir / "venv_setup.json").write_text(json.dumps(setup_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        import_result = run_capture(
            [str(venv_python), "-X", "faulthandler", "-c", "import hbdk4.compiler, leap_llm, torch; print('hbdk4.compiler imported'); print(torch.__version__)"],
            timeout=120,
        )
        (run_dir / "hbdk_import.stdout.txt").write_text(import_result["stdout"], encoding="utf-8", errors="replace")
        (run_dir / "hbdk_import.stderr.txt").write_text(import_result["stderr"], encoding="utf-8", errors="replace")
        if import_result["returncode"] != 0:
            errors.append("hbdk4.compiler import failed after SDK install")
            build_status = "hbdk_import_failed"
        else:
            build_cmd = [
                str(oellm_build_bin if oellm_build_bin.is_file() else venv_python),
            ]
            if not oellm_build_bin.is_file():
                build_cmd.extend(["-m", "leap_llm.apis.oellm_build"])
            build_cmd.extend(
                [
                    "--model_name",
                    model_name,
                    "--march",
                    march,
                    "--input_model_path",
                    str(source_model_dir),
                    "--output_model_path",
                    str(output_model_path),
                    "--cache_len",
                    str(cache_len),
                    "--chunk_size",
                    str(chunk_size),
                    "--calib_text_path",
                    str(calib_text_path),
                    "--w_bits",
                    str(w_bits),
                ]
            )
            build_result = run_capture(build_cmd, cwd=build_root, timeout=21600)
            build_stdout.write_text(build_result["stdout"], encoding="utf-8", errors="replace")
            build_stderr.write_text(build_result["stderr"], encoding="utf-8", errors="replace")
            build_status = "completed" if build_result["returncode"] == 0 else "failed"
            if build_result["returncode"] != 0:
                errors.append(f"oellm_build failed with returncode {build_result['returncode']}")
else:
    build_status = "blocked_preflight"

if output_model_path.is_dir():
    compiled_hbms = sorted(path for path in output_model_path.glob("*.hbm") if path.is_file() and path.stat().st_size > 0)

official_config = read_json(official_runtime_config)
tokenizer_dir = resolve_runtime_path(official_config.get("tokenizer_dir") if isinstance(official_config, dict) else None)
template_path = resolve_runtime_path(official_config.get("template_path") if isinstance(official_config, dict) else None)
compiled_hbm_path = compiled_hbms[-1] if compiled_hbms else None
isolated_runtime_config_written = False
runtime_result = None
monitor_result = None
runtime_status = "not_started"

if compiled_hbm_path and run_runtime:
    if not runtime_bin.is_file():
        warnings.append(f"official oellm_multichat binary is missing: {runtime_bin}")
        runtime_status = "blocked_missing_runtime_binary"
    elif not runtime_lib_dir.is_dir():
        warnings.append(f"official oellm_runtime lib directory is missing: {runtime_lib_dir}")
        runtime_status = "blocked_missing_runtime_lib"
    elif tokenizer_dir is None or not tokenizer_dir.is_dir():
        warnings.append(f"official Qwen tokenizer_dir is missing: {tokenizer_dir}")
        runtime_status = "blocked_missing_tokenizer"
    elif template_path is None or not template_path.is_file():
        warnings.append(f"official Qwen template_path is missing: {template_path}")
        runtime_status = "blocked_missing_template"
    else:
        isolated_runtime_dir.mkdir(parents=True, exist_ok=True)
        isolated_config = dict(official_config)
        isolated_config["hbm_path"] = str(compiled_hbm_path)
        isolated_config["tokenizer_dir"] = str(tokenizer_dir)
        isolated_config["template_path"] = str(template_path)
        isolated_runtime_config.write_text(json.dumps(isolated_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        isolated_runtime_config_written = True
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(runtime_lib_dir)
        monitor_proc = None
        if shutil.which("hrt_ucp_monitor"):
            monitor_proc = subprocess.Popen(
                ["hrt_ucp_monitor", "-b", "-e", "bpu", "-d", str(monitor_delay_ms), "-n", str(monitor_sample_count)],
                stdout=monitor_stdout.open("w", encoding="utf-8"),
                stderr=monitor_stderr.open("w", encoding="utf-8"),
            )
        else:
            warnings.append("hrt_ucp_monitor is not available; runtime will run without BPU telemetry sampling")
        runtime_result = run_capture(
            [str(runtime_bin), "-c", str(isolated_runtime_config)],
            cwd=runtime_example_dir,
            timeout=runtime_timeout_seconds,
            env=env,
            stdin_text="hello\nexit\n",
        )
        runtime_stdout.write_text(runtime_result["stdout"], encoding="utf-8", errors="replace")
        runtime_stderr.write_text(runtime_result["stderr"], encoding="utf-8", errors="replace")
        if monitor_proc is not None:
            try:
                monitor_proc.wait(timeout=max(2, monitor_timeout := int((monitor_delay_ms * monitor_sample_count) / 1000) + 5))
            except subprocess.TimeoutExpired:
                monitor_proc.terminate()
                monitor_proc.wait(timeout=5)
            monitor_result = {"returncode": monitor_proc.returncode, "timeout_seconds": monitor_timeout}
        runtime_status = "completed" if runtime_result["returncode"] == 0 and not runtime_result["timed_out"] else "failed"
elif compiled_hbm_path:
    runtime_status = "skipped_by_env"
else:
    runtime_status = "blocked_missing_compiled_hbm"

runtime_text = read_text(runtime_stdout) + "\n" + read_text(runtime_stderr)
monitor_text = read_text(monitor_stdout)
bpu_loading_samples = parse_bpu_samples(monitor_text)
memory_alloc_failure_observed = (
    "Allocate memory failed" in runtime_text
    or "Fail to allocate common buffer" in runtime_text
    or "AllocError" in runtime_text
)
hbm_load_success_observed = "Load hbm file" in runtime_text and "success" in runtime_text
init_model_success_observed = "Init model success" in runtime_text
runtime_completed = bool(runtime_result and runtime_result["returncode"] == 0 and not runtime_result["timed_out"])
build_pass = build_status == "completed" and bool(compiled_hbm_path)
runtime_attempted = runtime_result is not None
fullflow_completed = build_pass and runtime_attempted and (runtime_completed or memory_alloc_failure_observed or hbm_load_success_observed)

if build_status == "blocked_preflight":
    warnings.append("official Qwen fullflow did not build because preflight requirements were not satisfied")
if build_pass and not runtime_attempted:
    warnings.append("official Qwen build produced HBM, but runtime was not attempted on this host")
if runtime_attempted and not runtime_completed and memory_alloc_failure_observed:
    warnings.append("official Qwen fullflow built HBM but runtime hit BPU/common-buffer allocation failure")

payload = {
    "generated_at": now_iso(),
    "verdict": "ok_s100_official_qwen_fullflow_probe" if fullflow_completed and not errors else "failed_s100_official_qwen_fullflow_probe",
    "run_dir": str(run_dir),
    "sdk_root": str(sdk_root),
    "build_root": str(build_root),
    "runtime_root": str(runtime_root),
    "source_model_dir": str(source_model_dir),
    "source_model_exists": source_model_exists,
    "output_model_path": str(output_model_path),
    "venv_dir": str(venv_dir),
    "model_name": model_name,
    "march": march,
    "cache_len": cache_len,
    "chunk_size": chunk_size,
    "w_bits": w_bits,
    "supported_models_from_sdk_wheel": supported_models,
    "model_registered": model_registered,
    "host_machine": machine,
    "host_has_avx": host_has_avx,
    "build_host_compatible": build_host_compatible,
    "calib_text_path": str(calib_text_path),
    "build_status": build_status,
    "build_returncode": build_result.get("returncode") if build_result else None,
    "build_command": build_result.get("command") if build_result else [],
    "build_stdout": str(build_stdout),
    "build_stderr": str(build_stderr),
    "compiled_hbm_count": len(compiled_hbms),
    "compiled_hbm_path": str(compiled_hbm_path) if compiled_hbm_path else "",
    "compiled_hbm_size_bytes": compiled_hbm_path.stat().st_size if compiled_hbm_path else 0,
    "tokenizer_dir": str(tokenizer_dir) if tokenizer_dir else "",
    "template_path": str(template_path) if template_path else "",
    "isolated_runtime_dir": str(isolated_runtime_dir),
    "isolated_runtime_config": str(isolated_runtime_config),
    "isolated_runtime_config_written": isolated_runtime_config_written,
    "run_runtime": run_runtime,
    "runtime_status": runtime_status,
    "runtime_returncode": runtime_result.get("returncode") if runtime_result else None,
    "runtime_timed_out": runtime_result.get("timed_out") if runtime_result else None,
    "runtime_completed": runtime_completed,
    "runtime_timeout_seconds": runtime_timeout_seconds,
    "hbm_load_success_observed": hbm_load_success_observed,
    "init_model_success_observed": init_model_success_observed,
    "memory_alloc_failure_observed": memory_alloc_failure_observed,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "monitor_result": monitor_result,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": sum(1 for item in bpu_loading_samples if item > 0.0),
    "max_bpu_loading": round(max(bpu_loading_samples), 3) if bpu_loading_samples else 0.0,
    "avg_bpu_loading": round(sum(bpu_loading_samples) / len(bpu_loading_samples), 3) if bpu_loading_samples else 0.0,
    "build_pass": build_pass,
    "runtime_attempted": runtime_attempted,
    "fullflow_completed": fullflow_completed,
    "next_probe_target": "if build passed but runtime failed, compare this isolated HBM/runtime result with s100_official_qwen_runtime_probe, backend9, and bpu_core sweep; if build is blocked, move compilation to an x86_64 AVX Linux host with the same SDK and source model",
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "official_qwen_fullflow_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# S100 Official Qwen Fullflow Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- model_name: {model_name}",
    f"- march: {march}",
    f"- cache_len: {cache_len}",
    f"- chunk_size: {chunk_size}",
    f"- source_model_dir: {source_model_dir}",
    f"- output_model_path: {output_model_path}",
    f"- build_host_compatible: {build_host_compatible}",
    f"- model_registered: {model_registered}",
    f"- build_status: {build_status}",
    f"- build_pass: {build_pass}",
    f"- compiled_hbm_path: {payload['compiled_hbm_path']}",
    f"- compiled_hbm_size_bytes: {payload['compiled_hbm_size_bytes']}",
    f"- isolated_runtime_config_written: {isolated_runtime_config_written}",
    f"- runtime_status: {runtime_status}",
    f"- runtime_attempted: {runtime_attempted}",
    f"- runtime_completed: {runtime_completed}",
    f"- hbm_load_success_observed: {hbm_load_success_observed}",
    f"- memory_alloc_failure_observed: {memory_alloc_failure_observed}",
    f"- bpu_loading_sample_count: {payload['bpu_loading_sample_count']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- fullflow_completed: {fullflow_completed}",
    "",
    "## Captured Files",
    "",
    f"- calib_text_path: {calib_text_path}",
    f"- build_stdout: {build_stdout}",
    f"- build_stderr: {build_stderr}",
    f"- isolated_runtime_config: {isolated_runtime_config}",
    f"- runtime_stdout: {runtime_stdout}",
    f"- runtime_stderr: {runtime_stderr}",
    f"- monitor_stdout: {monitor_stdout}",
    f"- monitor_stderr: {monitor_stderr}",
    "",
    "## Next Probe Target",
    "",
    f"- {payload['next_probe_target']}",
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
(run_dir / "official_qwen_fullflow_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "official_qwen_fullflow_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
