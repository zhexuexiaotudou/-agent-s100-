#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
repo_dir="${DREAM7B_BPU_PHASE1_PACKAGE_REPO_DIR:-/mnt/nas/openclaw/tmp/cross_job_queue_repo}"
model_dir="${DREAM7B_BPU_PHASE1_PACKAGE_MODEL_DIR:-/mnt/nas/openclaw/models/dream7b-hf}"
sdk_root="${DREAM7B_BPU_PHASE1_PACKAGE_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"
publish_hbm_dir="${DREAM7B_BPU_PHASE1_PACKAGE_PUBLISH_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/phase1-topload-seq16}"
local_cache_dir="${DREAM7B_BPU_PHASE1_PACKAGE_LOCAL_CACHE_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/phase1-topload-seq16}"
phase1_specs="${DREAM7B_BPU_PHASE1_PACKAGE_SPECS:-2:3 3:4 4:5 5:7}"
hash_model_weights="${DREAM7B_BPU_PHASE1_PACKAGE_HASH_MODEL_WEIGHTS:-0}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac
case "$repo_dir" in
  /mnt/nas/openclaw/tmp/*|/root/.openclaw/workspace/*|/tmp/*) ;;
  *)
    echo "Refusing repo dir outside approved workspace/tmp roots: $repo_dir" >&2
    exit 2
    ;;
esac
case "$model_dir" in
  /mnt/nas/openclaw/models/dream7b-hf|/mnt/nas/openclaw/models/dream7b-hf/*|/opt/digua/dream_hf|/opt/digua/dream_hf/*) ;;
  *)
    echo "Refusing Dream HF model dir outside approved roots: $model_dir" >&2
    exit 2
    ;;
esac
case "$sdk_root" in
  /mnt/nas/openclaw/toolchains/s100_llm_sdk/*|/opt/digua/s100_llm_sdk/*|/tmp/s100_llm_sdk/*) ;;
  *)
    echo "Refusing SDK root outside approved roots: $sdk_root" >&2
    exit 2
    ;;
esac
case "$publish_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/*) ;;
  *)
    echo "Refusing publish HBM dir outside approved NAS Dream HBM root: $publish_hbm_dir" >&2
    exit 2
    ;;
esac
case "$local_cache_dir" in
  /home/sunrise/.cache/openclaw/dream7b-hbm/*|/tmp/*) ;;
  *)
    echo "Refusing local cache dir outside approved S100P cache root: $local_cache_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_phase1_compile_recovery_package_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$repo_dir" \
  "$model_dir" \
  "$sdk_root" \
  "$publish_hbm_dir" \
  "$local_cache_dir" \
  "$phase1_specs" \
  "$hash_model_weights" <<'PY'
import hashlib
import json
import os
import platform
import stat
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
repo_dir = Path(sys.argv[2])
model_dir = Path(sys.argv[3])
sdk_root = Path(sys.argv[4])
publish_hbm_dir = Path(sys.argv[5])
local_cache_dir = Path(sys.argv[6])
phase1_specs = sys.argv[7].split()
hash_model_weights = sys.argv[8] == "1"

oellm_build_dir = sdk_root / "oellm_build"
compile_probe = repo_dir / "scripts/probes/compile_dream_segments_seq16_resplit_probe.sh"
compile_py = repo_dir / "scripts/probes/compile_dream_segmented_full_forward.py"
phase1_preflight_probe = repo_dir / "scripts/probes/dream7b_bpu_phase1_segment_plan_preflight_probe.sh"
batch_telemetry_probe = repo_dir / "scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh"
window_cost_probe = repo_dir / "scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh"
utilization_gap_probe = repo_dir / "scripts/probes/dream7b_bpu_utilization_gap_probe.sh"
deployment_acceptance_probe = repo_dir / "scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh"
default_acceptance_probe = repo_dir / "scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh"


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_record(path: Path, digest=False):
    return {
        "path": str(path),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "sha256": sha256(path) if digest and path.is_file() else "",
    }


def spec_to_segment(spec):
    start_s, end_s = spec.split(":", 1)
    start, end = int(start_s), int(end_s)
    return {
        "spec": spec,
        "segment_dir": f"seg{start:02d}_{end:02d}",
        "hbm_name": f"dream7b_segment_{start}_{end}_seq16_q8.hbm",
        "publish_hbm": str(publish_hbm_dir / f"seg{start:02d}_{end:02d}" / f"dream7b_segment_{start}_{end}_seq16_q8.hbm"),
        "publish_exists": (publish_hbm_dir / f"seg{start:02d}_{end:02d}" / f"dream7b_segment_{start}_{end}_seq16_q8.hbm").is_file(),
    }


errors = []
warnings = []

required_model_files = [
    "config.json",
    "model.safetensors.index.json",
    "model-00001-of-00004.safetensors",
    "model-00002-of-00004.safetensors",
    "model-00003-of-00004.safetensors",
    "model-00004-of-00004.safetensors",
    "configuration_dream.py",
    "modeling_dream.py",
    "tokenization_dream.py",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
]
model_records = [
    file_record(
        model_dir / name,
        digest=name == "config.json" or (hash_model_weights and name.endswith(".safetensors")),
    )
    for name in required_model_files
]
for record in model_records:
    if not record["exists"]:
        errors.append(f"missing Dream HF file: {record['path']}")

sdk_records = [
    file_record(oellm_build_dir / "requirements.txt"),
]
sdk_records.extend(file_record(path) for path in sorted(oellm_build_dir.glob("hbdk4_compiler-*.whl")))
sdk_records.extend(file_record(path) for path in sorted(oellm_build_dir.glob("leap_llm-*.whl")))
if not (oellm_build_dir / "requirements.txt").is_file():
    errors.append(f"missing SDK requirements.txt: {oellm_build_dir / 'requirements.txt'}")
if not list(oellm_build_dir.glob("hbdk4_compiler-*.whl")):
    errors.append(f"missing hbdk4 compiler wheel under {oellm_build_dir}")
if not list(oellm_build_dir.glob("leap_llm-*.whl")):
    errors.append(f"missing leap_llm wheel under {oellm_build_dir}")

repo_records = [
    file_record(compile_probe),
    file_record(compile_py),
    file_record(phase1_preflight_probe),
    file_record(batch_telemetry_probe),
    file_record(window_cost_probe),
    file_record(utilization_gap_probe),
    file_record(deployment_acceptance_probe),
    file_record(default_acceptance_probe),
]
for record in repo_records:
    if not record["exists"]:
        errors.append(f"missing repo script: {record['path']}")

target_segments = [spec_to_segment(spec) for spec in phase1_specs]
missing_targets = [item["spec"] for item in target_segments if not item["publish_exists"]]
if missing_targets:
    warnings.append(f"Phase 1 target HBM artifacts still missing: {missing_targets}")

machine = platform.machine()
cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace") if Path("/proc/cpuinfo").is_file() else ""
host_has_avx = " avx " in f" {cpuinfo} " or "\tavx " in cpuinfo
host_is_builder = machine == "x86_64" and host_has_avx
if not host_is_builder:
    warnings.append("current host is not an x86_64 AVX HBDK compile host; use this package on a builder machine")

recovery_sh = run_dir / "phase1_compile_recovery_runbook.sh"
recovery_sh.write_text(f"""#!/usr/bin/env bash
set -euo pipefail

# Run this on an x86_64 Linux host with AVX support. It may be WSL1/WSL2,
# native Ubuntu, or a Linux build server. Do not run it on S100P or the NAS CPU.
S100_HOST="${{S100_HOST:-sunrise@192.168.127.10}}"
WORK_ROOT="${{WORK_ROOT:-/opt/digua/phase1-dream7b-builder}}"
REPO_DIR="${{REPO_DIR:-$WORK_ROOT/repo}}"
SDK_ROOT="${{SDK_ROOT:-$WORK_ROOT/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}}"
MODEL_DIR="${{MODEL_DIR:-/opt/digua/dream_hf}}"
VENV_DIR="${{VENV_DIR:-/opt/digua/dream-s100-oellm-venv}}"
OUTPUT_ROOT="${{OUTPUT_ROOT:-/opt/digua/dream7b-segments-seq16-resplit/phase1-topload}}"
REPORT_ROOT="${{REPORT_ROOT:-/tmp/dream7b_phase1_topload_compile_reports}}"
PUBLISH_HBM_DIR="{publish_hbm_dir}"
LOCAL_CACHE_DIR="{local_cache_dir}"

if ! grep -m1 '^flags' /proc/cpuinfo | grep -qw avx; then
  echo "This host does not expose AVX; HBDK compiler import is expected to fail." >&2
  exit 4
fi

sudo mkdir -p "$WORK_ROOT" "$MODEL_DIR" "$VENV_DIR" "$(dirname "$OUTPUT_ROOT")"
sudo chown -R "$(id -u):$(id -g)" "$WORK_ROOT" "$MODEL_DIR" "$(dirname "$OUTPUT_ROOT")"

rsync -a --info=progress2 "$S100_HOST:/mnt/nas/openclaw/tmp/cross_job_queue_repo/" "$REPO_DIR/"
rsync -a --info=progress2 "$S100_HOST:/mnt/nas/openclaw/models/dream7b-hf/" "$MODEL_DIR/"
rsync -a --info=progress2 "$S100_HOST:/mnt/nas/openclaw/toolchains/s100_llm_sdk/" "$WORK_ROOT/s100_llm_sdk/"

python3.10 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$SDK_ROOT/oellm_build/requirements.txt"
python -m pip install "$SDK_ROOT"/oellm_build/hbdk4_compiler-*.whl "$SDK_ROOT"/oellm_build/leap_llm-*.whl

python -X faulthandler - <<'PHASE1_IMPORT_CHECK'
import hbdk4.compiler
import leap_llm
print("hbdk4.compiler import ok")
print("leap_llm import ok")
PHASE1_IMPORT_CHECK

cd "$REPO_DIR"
DREAM_RESPLIT_VENV="$VENV_DIR" \\
DREAM_RESPLIT_MODEL_DIR="$MODEL_DIR" \\
DREAM_RESPLIT_OUTPUT_ROOT="$OUTPUT_ROOT" \\
DREAM_RESPLIT_SPECS="{ ' '.join(phase1_specs) }" \\
DREAM_RESPLIT_EXPECTED_SPECS="{ ' '.join(phase1_specs) }" \\
DREAM_RESPLIT_SKIP_EXISTING=1 \\
bash scripts/probes/compile_dream_segments_seq16_resplit_probe.sh "$REPORT_ROOT"

rsync -a --info=progress2 "$OUTPUT_ROOT/" "$S100_HOST:$PUBLISH_HBM_DIR/"
ssh "$S100_HOST" "mkdir -p '$LOCAL_CACHE_DIR' && rsync -a '$PUBLISH_HBM_DIR/' '$LOCAL_CACHE_DIR/' && cd '$PUBLISH_HBM_DIR' && sha256sum -c manifest.sha256"

ssh "$S100_HOST" "cd /mnt/nas/openclaw/tmp/cross_job_queue_repo && bash scripts/probes/dream7b_bpu_phase1_segment_plan_preflight_probe.sh /mnt/nas/openclaw/reports/models"
ssh "$S100_HOST" "cd /mnt/nas/openclaw/tmp/cross_job_queue_repo && DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_PLAN=phase1-topload-adjacent DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_EVENT_COUNT=320 DREAM7B_BPU_RESPLIT_BATCH_FORWARD_ARGS='--segment-plan phase1-topload-adjacent' bash scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh /mnt/nas/openclaw/reports/models"
ssh "$S100_HOST" "cd /mnt/nas/openclaw/tmp/cross_job_queue_repo && DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_PLAN=phase1-topload-adjacent bash scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh /mnt/nas/openclaw/reports/models"
ssh "$S100_HOST" "cd /mnt/nas/openclaw/tmp/cross_job_queue_repo && bash scripts/probes/dream7b_bpu_utilization_gap_probe.sh /mnt/nas/openclaw/reports/models && bash scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh /mnt/nas/openclaw/reports/models && bash scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh /mnt/nas/openclaw/reports/models"
""", encoding="utf-8")
recovery_sh.chmod(recovery_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

readme = run_dir / "README.md"
readme.write_text(f"""# Dream 7B Phase 1 Compile Recovery Package

Purpose: build the four missing Phase 1 top-load HBM shards for the
`phase1-topload-adjacent` plan.

Target specs:

```text
{' '.join(phase1_specs)}
```

Current blocker: these HBM files are not present under:

```text
{publish_hbm_dir}
```

Run `phase1_compile_recovery_runbook.sh` on an x86_64 Linux host with AVX
support and network access to the S100P. The script copies the repo, SDK, and
Dream HF assets from S100P/NAS, creates the compiler venv, compiles the four
segments, publishes them back to NAS and S100P local cache, and launches the
Phase 1 preflight plus telemetry/acceptance probes.
""", encoding="utf-8")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_phase1_compile_recovery_package_probe" if not errors else "failed_dream7b_bpu_phase1_compile_recovery_package_probe",
    "run_dir": str(run_dir),
    "host": {
        "machine": machine,
        "host_has_avx": host_has_avx,
        "host_is_builder": host_is_builder,
    },
    "repo_dir": str(repo_dir),
    "model_dir": str(model_dir),
    "sdk_root": str(sdk_root),
    "publish_hbm_dir": str(publish_hbm_dir),
    "local_cache_dir": str(local_cache_dir),
    "phase1_specs": phase1_specs,
    "hash_model_weights": hash_model_weights,
    "target_segments": target_segments,
    "missing_target_specs": missing_targets,
    "model_records": model_records,
    "sdk_records": sdk_records,
    "repo_records": repo_records,
    "recovery_runbook": str(recovery_sh),
    "readme": str(readme),
    "next_step": "run recovery_runbook on an x86_64 AVX Linux HBDK builder, then run phase1 telemetry and acceptance",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "phase1_compile_recovery_package_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B Phase 1 Compile Recovery Package Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- host_is_builder: {payload['host']['host_is_builder']}",
    f"- model_dir: {payload['model_dir']}",
    f"- sdk_root: {payload['sdk_root']}",
    f"- phase1_specs: {' '.join(phase1_specs)}",
    f"- missing_target_specs: {payload['missing_target_specs']}",
    f"- recovery_runbook: {payload['recovery_runbook']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "phase1_compile_recovery_package_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "phase1_compile_recovery_package_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
