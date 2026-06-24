#!/usr/bin/env bash
set -euo pipefail

target_dir="${1:-/mnt/nas/openclaw/models/dream7b-hf}"
base_url="${HF_ENDPOINT:-https://hf-mirror.com}/Dream-org/Dream-v0-Instruct-7B/resolve/main"

mkdir -p "$target_dir"
cd "$target_dir"

files=(
  vocab.json
  merges.txt
  model-00001-of-00004.safetensors
  model-00002-of-00004.safetensors
  model-00003-of-00004.safetensors
  model-00004-of-00004.safetensors
)

for file in "${files[@]}"; do
  echo "=== $(date -Is) downloading ${file} ==="
  curl \
    -fL \
    --retry 50 \
    --retry-delay 5 \
    --connect-timeout 30 \
    --speed-time 120 \
    --speed-limit 1024 \
    -C - \
    -o "$file" \
    "${base_url}/${file}"
  ls -lh "$file"
done

echo "=== $(date -Is) all downloads finished ==="
sha256sum "${files[@]}" > SHA256SUMS
cat SHA256SUMS
