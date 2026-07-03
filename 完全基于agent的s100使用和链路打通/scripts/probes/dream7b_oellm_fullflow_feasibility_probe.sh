#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_oellm_build="${DREAM7B_OELLM_FULLFLOW_SDK_OELLM_BUILD:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build}"
dream_model_dir="${DREAM7B_OELLM_FULLFLOW_MODEL_DIR:-/mnt/nas/openclaw/models/dream7b-hf}"
output_dir="${DREAM7B_OELLM_FULLFLOW_OUTPUT_DIR:-/mnt/nas/openclaw/models/dream7b-oellm-fullflow}"
venv_dir="${DREAM7B_OELLM_FULLFLOW_VENV_DIR:-/tmp/dream7b-oellm-fullflow-venv}"
compile_script="${DREAM7B_OELLM_FULLFLOW_COMPILE_SCRIPT:-scripts/probes/compile_dream_with_deepseek_skeleton.sh}"
march="${DREAM7B_OELLM_FULLFLOW_MARCH:-nash-m}"
chunk_size="${DREAM7B_OELLM_FULLFLOW_CHUNK_SIZE:-128}"
cache_len="${DREAM7B_OELLM_FULLFLOW_CACHE_LEN:-512}"
w_bits="${DREAM7B_OELLM_FULLFLOW_W_BITS:-8}"
run_compile="${DREAM7B_OELLM_FULLFLOW_RUN_COMPILE:-1}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$sdk_oellm_build" in
  /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build|/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build/|/opt/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build|/opt/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build/|/mnt/f/Project/Digua/tmp/s100_llm_sdk/inspect/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build|/mnt/f/Project/Digua/tmp/s100_llm_sdk/inspect/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build/) ;;
  *)
    echo "Refusing SDK oellm_build path outside approved S100 official LLM SDK directories: $sdk_oellm_build" >&2
    exit 2
    ;;
esac

case "$dream_model_dir" in
  /mnt/nas/openclaw/models/dream7b-hf|/mnt/nas/openclaw/models/dream7b-hf/*|/opt/digua/dream_hf|/opt/digua/dream_hf/*|/tmp/dream_hf|/tmp/dream_hf/*|/mnt/f/Project/Digua/tmp/dream_hf|/mnt/f/Project/Digua/tmp/dream_hf/*|/root/.openclaw/workspace/models/dream7b-hf|/root/.openclaw/workspace/models/dream7b-hf/*) ;;
  *)
    echo "Refusing Dream model path outside approved Dream HF directories: $dream_model_dir" >&2
    exit 2
    ;;
esac

case "$output_dir" in
  /tmp/*|/mnt/f/Project/Digua/tmp/models/dream7b-oellm-fullflow|/mnt/f/Project/Digua/tmp/models/dream7b-oellm-fullflow/*|/mnt/nas/openclaw/models/dream7b-oellm-fullflow|/mnt/nas/openclaw/models/dream7b-oellm-fullflow/*|/root/.openclaw/workspace/models/dream7b-oellm-fullflow|/root/.openclaw/workspace/models/dream7b-oellm-fullflow/*) ;;
  *)
    echo "Refusing output dir outside approved Dream OELLM fullflow directories: $output_dir" >&2
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

case "$compile_script" in
  scripts/probes/compile_dream_with_deepseek_skeleton.sh|*/scripts/probes/compile_dream_with_deepseek_skeleton.sh) ;;
  *)
    echo "Refusing compile script outside approved Dream skeleton compiler: $compile_script" >&2
    exit 2
    ;;
esac

for value in "$chunk_size" "$cache_len" "$w_bits"; do
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "Dream OELLM fullflow numeric parameters must be positive integers." >&2
    exit 2
  fi
done

case "$run_compile" in
  0|1) ;;
  *)
    echo "DREAM7B_OELLM_FULLFLOW_RUN_COMPILE must be 0 or 1." >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_oellm_fullflow_feasibility_$stamp"
mkdir -p "$run_dir"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - \
  "$run_dir" \
  "$repo_dir" \
  "$sdk_oellm_build" \
  "$dream_model_dir" \
  "$output_dir" \
  "$venv_dir" \
  "$compile_script" \
  "$march" \
  "$chunk_size" \
  "$cache_len" \
  "$w_bits" \
  "$run_compile" <<'PY'
import json
import os
import platform
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
repo_dir = Path(sys.argv[2])
sdk_oellm_build = Path(sys.argv[3])
dream_model_dir = Path(sys.argv[4])
output_dir = Path(sys.argv[5])
venv_dir = Path(sys.argv[6])
compile_script_arg = Path(sys.argv[7])
march = sys.argv[8]
chunk_size = int(sys.argv[9])
cache_len = int(sys.argv[10])
w_bits = int(sys.argv[11])
run_compile = sys.argv[12] == "1"

compile_script = compile_script_arg if compile_script_arg.is_absolute() else repo_dir / compile_script_arg
stdout_path = run_dir / "compile_dream_with_deepseek_skeleton.stdout.txt"
stderr_path = run_dir / "compile_dream_with_deepseek_skeleton.stderr.txt"

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


def run_capture(cmd, cwd=None, timeout=None, env=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
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
    wheels = sorted(sdk_oellm_build.glob(f"{prefix}*.whl"))
    return wheels[0] if wheels else None


def model_registry_from_wheel():
    wheel = find_wheel("leap_llm-")
    if not wheel:
        return {"wheel": "", "supported_models": [], "dream_registered": False, "factory_excerpt_path": ""}
    try:
        with zipfile.ZipFile(wheel) as archive:
            text = archive.read("leap_llm/apis/model/model_factory.py").decode("utf-8", errors="replace")
    except Exception as exc:
        warnings.append(f"failed to read leap_llm model_factory from wheel: {type(exc).__name__}: {exc}")
        return {"wheel": str(wheel), "supported_models": [], "dream_registered": False, "factory_excerpt_path": ""}
    supported = re.findall(r'@register_model\("([^"]+)"', text)
    excerpt = run_dir / "leap_llm_model_factory_registry.txt"
    excerpt.write_text("\n".join(supported) + "\n", encoding="utf-8")
    return {
        "wheel": str(wheel),
        "supported_models": supported,
        "dream_registered": any(item.lower() in {"dream", "dream7b", "dream-v0-instruct-7b"} for item in supported),
        "factory_excerpt_path": str(excerpt),
    }


machine = platform.machine()
cpuinfo = read_text(Path("/proc/cpuinfo"))
host_has_avx = " avx " in f" {cpuinfo.lower()} "
build_host_compatible = machine == "x86_64" and host_has_avx
registry = model_registry_from_wheel()
dream_config = read_json(dream_model_dir / "config.json")
dream_config_summary = {
    "model_type": dream_config.get("model_type"),
    "architectures": dream_config.get("architectures"),
    "hidden_size": dream_config.get("hidden_size"),
    "intermediate_size": dream_config.get("intermediate_size"),
    "num_hidden_layers": dream_config.get("num_hidden_layers"),
    "num_attention_heads": dream_config.get("num_attention_heads"),
    "num_key_value_heads": dream_config.get("num_key_value_heads"),
    "vocab_size": dream_config.get("vocab_size"),
    "mask_token_id": dream_config.get("mask_token_id"),
    "use_cache": dream_config.get("use_cache"),
    "torch_dtype": dream_config.get("torch_dtype"),
}

if not sdk_oellm_build.is_dir():
    errors.append(f"missing SDK oellm_build directory: {sdk_oellm_build}")
if not compile_script.is_file():
    errors.append(f"missing Dream skeleton compile script: {compile_script}")
if not (dream_model_dir / "config.json").is_file():
    errors.append(f"missing Dream config: {dream_model_dir / 'config.json'}")
if not any(dream_model_dir.glob("model-*.safetensors")):
    errors.append(f"missing Dream safetensors shards in {dream_model_dir}")
if registry["dream_registered"]:
    warnings.append("Dream appears in the official SDK model registry; direct model_name Dream should be tested before skeleton fallback")
else:
    warnings.append("Dream is not registered in official leap_llm model_factory; direct official oellm_build migration is blocked before compilation")
if not build_host_compatible:
    errors.append("build host is not compatible: x86_64 with AVX is required for HBDK compiler import")

compile_result = None
compile_status = "not_started"
compiled_hbms: list[Path] = []
failure_stage = ""

if not registry["dream_registered"]:
    compile_status = "blocked_registry_missing"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text(
        "Dream is not registered in official leap_llm model_factory; no direct official oellm_build model adapter is available.\n",
        encoding="utf-8",
    )
elif run_compile and not errors:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "SDK_OELLM_BUILD": str(sdk_oellm_build),
            "DREAM_MODEL_DIR": str(dream_model_dir),
            "OUTPUT_DIR": str(output_dir),
            "VENV_DIR": str(venv_dir),
            "MARCH": march,
            "CHUNK_SIZE": str(chunk_size),
            "CACHE_LEN": str(cache_len),
            "W_BITS": str(w_bits),
        }
    )
    compile_result = run_capture(["bash", str(compile_script)], cwd=repo_dir, timeout=21600, env=env)
    stdout_path.write_text(compile_result["stdout"], encoding="utf-8", errors="replace")
    stderr_path.write_text(compile_result["stderr"], encoding="utf-8", errors="replace")
    compile_status = "completed" if compile_result["returncode"] == 0 else "failed"
    if compile_result["returncode"] != 0:
        errors.append(f"Dream OELLM skeleton compile failed with returncode {compile_result['returncode']}")
elif not run_compile:
    compile_status = "skipped_by_env"
else:
    compile_status = "blocked_preflight"

if output_dir.is_dir():
    compiled_hbms = sorted(path for path in output_dir.glob("*.hbm") if path.is_file() and path.stat().st_size > 0)

stderr_text = read_text(stderr_path)
stdout_text = read_text(stdout_path)
combined = stdout_text + "\n" + stderr_text
if not registry["dream_registered"]:
    failure_stage = "registry_missing"
elif "Illegal instruction" in combined or "SIGILL" in combined:
    failure_stage = "hbdk_import_or_compiler_cpu_instruction"
elif "Model 'Dream'" in combined or "not supported" in combined:
    failure_stage = "official_sdk_model_registry"
elif "size mismatch" in combined or "Missing key" in combined or "Unexpected key" in combined:
    failure_stage = "weight_mapping_or_model_shape"
elif "hbdk4" in combined and "Traceback" in combined:
    failure_stage = "hbdk_compile"
elif compile_status == "blocked_preflight":
    failure_stage = "preflight"
elif compile_status == "completed" and compiled_hbms:
    failure_stage = "none"
elif compile_status == "failed":
    failure_stage = "unknown_compile_failure"
else:
    failure_stage = compile_status

minimal_failure_package = {
    "command": compile_result.get("command") if compile_result else [],
    "unable_to_attempt_direct_official_compile_reason": "" if registry["dream_registered"] else "Dream is absent from official leap_llm model_factory registry; direct oellm_build requires a registered model adapter.",
    "environment": {
        "SDK_OELLM_BUILD": str(sdk_oellm_build),
        "DREAM_MODEL_DIR": str(dream_model_dir),
        "OUTPUT_DIR": str(output_dir),
        "VENV_DIR": str(venv_dir),
        "MARCH": march,
        "CHUNK_SIZE": str(chunk_size),
        "CACHE_LEN": str(cache_len),
        "W_BITS": str(w_bits),
    },
    "stdout_path": str(stdout_path),
    "stderr_path": str(stderr_path),
    "dream_config_summary": dream_config_summary,
    "sdk_registry_summary": registry,
    "failure_stage": failure_stage,
}

direct_oellm_migration_supported = compile_status == "completed" and bool(compiled_hbms)
missing_adapter_evidence = {
    "registry_missing": not registry["dream_registered"],
    "required_adapter": "official leap_llm model_factory registration and Dream/DreamModel adapter",
    "registry_path": registry.get("factory_excerpt_path"),
    "supported_models_from_sdk": registry["supported_models"],
}
payload = {
    "generated_at": now_iso(),
    "verdict": "ok_dream7b_oellm_fullflow_feasibility_probe" if direct_oellm_migration_supported and not errors else "failed_dream7b_oellm_fullflow_feasibility_probe",
    "run_dir": str(run_dir),
    "sdk_oellm_build": str(sdk_oellm_build),
    "dream_model_dir": str(dream_model_dir),
    "output_dir": str(output_dir),
    "venv_dir": str(venv_dir),
    "compile_script": str(compile_script),
    "march": march,
    "chunk_size": chunk_size,
    "cache_len": cache_len,
    "w_bits": w_bits,
    "host_machine": machine,
    "host_has_avx": host_has_avx,
    "build_host_compatible": build_host_compatible,
    "dream_registered_in_official_sdk": registry["dream_registered"],
    "supported_models_from_sdk": registry["supported_models"],
    "missing_adapter_evidence": missing_adapter_evidence,
    "dream_config_summary": dream_config_summary,
    "run_compile": run_compile,
    "compile_status": compile_status,
    "compile_returncode": compile_result.get("returncode") if compile_result else None,
    "compiled_hbm_count": len(compiled_hbms),
    "compiled_hbm_paths": [str(path) for path in compiled_hbms],
    "direct_oellm_migration_supported": direct_oellm_migration_supported,
    "failure_stage": failure_stage,
    "minimal_failure_package": minimal_failure_package,
    "next_probe_target": "if failure_stage is registry_missing, keep the segmented Dream HBM route and ask for an official Dream/DreamModel adapter or supported custom-model path; if it is preflight, rerun on x86_64 AVX Linux",
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "dream7b_oellm_fullflow_feasibility_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# Dream 7B OELLM Fullflow Feasibility Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- dream_registered_in_official_sdk: {payload['dream_registered_in_official_sdk']}",
    f"- build_host_compatible: {payload['build_host_compatible']}",
    f"- compile_status: {payload['compile_status']}",
    f"- compile_returncode: {payload['compile_returncode']}",
    f"- compiled_hbm_count: {payload['compiled_hbm_count']}",
    f"- direct_oellm_migration_supported: {payload['direct_oellm_migration_supported']}",
    f"- failure_stage: {payload['failure_stage']}",
    f"- next_probe_target: {payload['next_probe_target']}",
    "",
    "## Dream Config Summary",
    "",
    *[f"- {key}: {value}" for key, value in dream_config_summary.items()],
    "",
    "## Minimal Failure Package",
    "",
    f"- stdout_path: {stdout_path}",
    f"- stderr_path: {stderr_path}",
    f"- registry_path: {registry.get('factory_excerpt_path')}",
    f"- missing_adapter_evidence: {missing_adapter_evidence}",
    f"- SDK_OELLM_BUILD: {sdk_oellm_build}",
    f"- DREAM_MODEL_DIR: {dream_model_dir}",
    f"- OUTPUT_DIR: {output_dir}",
    f"- MARCH: {march}",
    f"- CHUNK_SIZE: {chunk_size}",
    f"- CACHE_LEN: {cache_len}",
    f"- W_BITS: {w_bits}",
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
(run_dir / "dream7b_oellm_fullflow_feasibility_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "dream7b_oellm_fullflow_feasibility_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
