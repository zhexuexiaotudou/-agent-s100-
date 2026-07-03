#!/usr/bin/env bash
set -euo pipefail

# First Dream-on-S100 BPU experiment:
# compile Dream HF safetensors through the official DeepSeek/Qwen text skeleton.
#
# This does not make Dream work through xlm_infer. It only tries to produce a
# fixed-length HBM forward/logits graph that a host-side Dream diffusion loop can
# call once per denoise step.

SDK_OELLM_BUILD="${SDK_OELLM_BUILD:-/opt/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build}"
DREAM_MODEL_DIR="${DREAM_MODEL_DIR:-/mnt/nas/openclaw/models/dream7b-hf}"
OUTPUT_DIR="${OUTPUT_DIR:-/mnt/nas/openclaw/models/dream7b-hbm}"
MARCH="${MARCH:-nash-e}"
CHUNK_SIZE="${CHUNK_SIZE:-256}"
CACHE_LEN="${CACHE_LEN:-512}"
W_BITS="${W_BITS:-8}"
VENV_DIR="${VENV_DIR:-/tmp/dream-s100-oellm-venv}"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: hbdk4 compiler wheel requires x86_64 Linux, current arch is $(uname -m)." >&2
  exit 2
fi

if ! grep -qw avx /proc/cpuinfo; then
  echo "ERROR: HBDK compiler import can SIGILL on this CPU because AVX is absent." >&2
  exit 2
fi

if [[ ! -d "$SDK_OELLM_BUILD" ]]; then
  echo "ERROR: SDK_OELLM_BUILD not found: $SDK_OELLM_BUILD" >&2
  exit 2
fi

if [[ ! -f "$DREAM_MODEL_DIR/model-00001-of-00004.safetensors" ]]; then
  echo "ERROR: Dream HF safetensors not found in $DREAM_MODEL_DIR" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
python3.10 -m venv "$VENV_DIR"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$SDK_OELLM_BUILD/requirements.txt"
python -m pip install \
  "$SDK_OELLM_BUILD/hbdk4_compiler-"*.whl \
  "$SDK_OELLM_BUILD/leap_llm-"*.whl

python -X faulthandler - <<'PY'
import platform
import hbdk4.compiler
import leap_llm
import torch
print("python", platform.python_version(), platform.machine())
print("torch", torch.__version__)
print("hbdk4.compiler imported")
print("leap_llm imported")
PY

oellm_build \
  --model_name deepseek-qwen-7b \
  --march "$MARCH" \
  --input_model_path "$DREAM_MODEL_DIR" \
  --output_model_path "$OUTPUT_DIR" \
  --chunk_size "$CHUNK_SIZE" \
  --cache_len "$CACHE_LEN" \
  --w_bits "$W_BITS"

echo "HBM output directory: $OUTPUT_DIR"
find "$OUTPUT_DIR" -maxdepth 1 -type f -printf '%f %s bytes\n' | sort
