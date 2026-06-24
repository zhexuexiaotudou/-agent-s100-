#!/usr/bin/env bash
set -euo pipefail

# First Dream-on-S100 BPU experiment:
# compile Dream HF safetensors through the official DeepSeek/Qwen text skeleton.
#
# Why this is the first attempt:
# - Dream uses a Qwen/Llama-like decoder block and its HF weight names match
#   leap_llm.models.deepseek after the SDK removes the "model." prefix.
# - The official xlm runtime does not support Dream, so this script only builds
#   an HBM forward graph. Host-side Dream diffusion sampling must call that graph
#   directly instead of xlm_infer.
#
# Must run on x86_64 Linux with Python 3.10. The hbdk4 compiler wheel in the
# S100 LLM SDK is manylinux_x86_64, not aarch64 and not Windows.

SDK_OELLM_BUILD="${SDK_OELLM_BUILD:-/opt/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build}"
DREAM_MODEL_DIR="${DREAM_MODEL_DIR:-/mnt/nas/openclaw/models/dream7b-hf}"
OUTPUT_DIR="${OUTPUT_DIR:-/mnt/nas/openclaw/models/dream7b-hbm}"
MARCH="${MARCH:-nash-e}"
CHUNK_SIZE="${CHUNK_SIZE:-256}"
CACHE_LEN="${CACHE_LEN:-512}"
W_BITS="${W_BITS:-8}"
VENV_DIR="${VENV_DIR:-/tmp/dream-s100-oellm-venv}"
USE_QEMU_X86_64="${USE_QEMU_X86_64:-0}"
QEMU_X86_64_BIN="${QEMU_X86_64_BIN:-/usr/bin/qemu-x86_64-static}"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: hbdk4 compiler wheel requires x86_64 Linux, current arch is $(uname -m)." >&2
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

python - <<'PY'
import platform
import hbdk4
import leap_llm
print("python", platform.python_version(), platform.machine())
print("hbdk4", getattr(hbdk4, "__version__", "unknown"))
print("leap_llm imported")
PY

if [[ "$USE_QEMU_X86_64" == "1" ]]; then
  if [[ ! -x "$QEMU_X86_64_BIN" ]]; then
    echo "ERROR: USE_QEMU_X86_64=1 but qemu binary not found: $QEMU_X86_64_BIN" >&2
    exit 2
  fi
  OELLM_BUILD=(env QEMU_CPU=max "$QEMU_X86_64_BIN" "$VENV_DIR/bin/python" "$VENV_DIR/bin/oellm_build")
else
  OELLM_BUILD=(oellm_build)
fi

"${OELLM_BUILD[@]}" \
  --model_name deepseek-qwen-7b \
  --march "$MARCH" \
  --input_model_path "$DREAM_MODEL_DIR" \
  --output_model_path "$OUTPUT_DIR" \
  --chunk_size "$CHUNK_SIZE" \
  --cache_len "$CACHE_LEN" \
  --w_bits "$W_BITS"

echo "HBM output directory: $OUTPUT_DIR"
find "$OUTPUT_DIR" -maxdepth 1 -type f -printf '%f %s bytes\n' | sort
