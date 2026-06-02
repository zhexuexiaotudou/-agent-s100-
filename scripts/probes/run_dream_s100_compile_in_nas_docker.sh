#!/usr/bin/env bash
set -euo pipefail

# Run from S100P. It controls the QNAP NAS Docker daemon over TLS and attempts
# Dream -> S100 HBM compilation inside a NAS-hosted x86_64 Ubuntu container.

NAS_DOCKER_HOST="${NAS_DOCKER_HOST:-tcp://169.254.143.37:2376}"
NAS_DOCKER_CERT_PATH="${NAS_DOCKER_CERT_PATH:-/home/sunrise/.docker/nas-tudou}"
NAS_IMAGE="${NAS_IMAGE:-docker.1ms.run/library/ubuntu:22.04}"
NAS_WORKSPACE_HOST_PATH="${NAS_WORKSPACE_HOST_PATH:-/share/OpenClawWorkspace}"
WORKSPACE="${WORKSPACE:-/mnt/nas/openclaw}"

CONTAINER_SCRIPT="$WORKSPACE/tmp/dream_s100_compile_inside_container.sh"
LOG_DIR="$WORKSPACE/logs/dream-s100"
LOG_FILE="$LOG_DIR/compile_$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$WORKSPACE/tmp" "$LOG_DIR"

cat > "$CONTAINER_SCRIPT" <<'INNER'
#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-https://download.pytorch.org/whl/cpu}"

apt-get \
  -o Acquire::Check-Date=false \
  -o Acquire::Check-Valid-Until=false \
  update
apt-get install -y --no-install-recommends \
  ca-certificates \
  build-essential \
  python3.10 \
  python3.10-dev \
  python3.10-venv \
  python3-pip \
  git \
  curl \
  libglib2.0-0 \
  libgl1 \
  libsndfile1 \
  ffmpeg

SDK_OELLM_BUILD="${SDK_OELLM_BUILD:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build}"
DREAM_MODEL_DIR="${DREAM_MODEL_DIR:-/mnt/nas/openclaw/models/dream7b-hf}"
OUTPUT_DIR="${OUTPUT_DIR:-/mnt/nas/openclaw/models/dream7b-hbm}"
VENV_DIR="${VENV_DIR:-/mnt/nas/openclaw/tmp/dream-s100-oellm-venv}"
MARCH="${MARCH:-nash-e}"
CHUNK_SIZE="${CHUNK_SIZE:-256}"
CACHE_LEN="${CACHE_LEN:-512}"
W_BITS="${W_BITS:-8}"

SDK_OELLM_BUILD="$SDK_OELLM_BUILD" \
DREAM_MODEL_DIR="$DREAM_MODEL_DIR" \
OUTPUT_DIR="$OUTPUT_DIR" \
VENV_DIR="$VENV_DIR" \
MARCH="$MARCH" \
CHUNK_SIZE="$CHUNK_SIZE" \
CACHE_LEN="$CACHE_LEN" \
W_BITS="$W_BITS" \
bash "$DREAM_MODEL_DIR/compile_dream_with_deepseek_skeleton.sh"
INNER

chmod +x "$CONTAINER_SCRIPT"

export DOCKER_HOST="$NAS_DOCKER_HOST"
export DOCKER_TLS_VERIFY=1
export DOCKER_CERT_PATH="$NAS_DOCKER_CERT_PATH"

docker run --rm \
  --platform linux/amd64 \
  --name dream-s100-compile \
  -v "$NAS_WORKSPACE_HOST_PATH:$WORKSPACE" \
  -e PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
  -e PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-https://download.pytorch.org/whl/cpu}" \
  "$NAS_IMAGE" \
  bash "$CONTAINER_SCRIPT" 2>&1 | tee "$LOG_FILE"

echo "Compile log: $LOG_FILE"
