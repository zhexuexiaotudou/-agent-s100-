#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$repo_root/tmp/harness_shadow.env"

mkdir -p "$(dirname "$env_file")"
cat > "$env_file" <<'EOF'
AI_NAS_HARNESS_SHADOW=0
EOF

export AI_NAS_HARNESS_SHADOW=0

failures=()
require_text() {
  local file="$1"
  local needle="$2"
  local label="$3"
  if [[ ! -r "$file" ]]; then
    failures+=("$label:missing_file:$file")
    return
  fi
  if ! grep -Fq -- "$needle" "$file"; then
    failures+=("$label:missing_text:$needle")
  fi
}

require_text "$repo_root/configs/systemd/openclaw-gateway.service" "--port 8765" "openclaw_port"
require_text "$repo_root/configs/systemd/openclaw-gateway.service" "--qwen-gateway-url http://127.0.0.1:18080" "openclaw_qwen_route"
require_text "$repo_root/configs/systemd/qwen25-local-openai-gateway.service" "QWEN25_OPENAI_PORT=18080" "qwen_port"
require_text "$repo_root/configs/systemd/qwen25-local-openai-gateway.service" "qwen25_openai_gateway.py" "qwen_gateway_script"
require_text "$repo_root/scripts/qwen25_openai_gateway.py" "policy[\"ai_nas\"][\"tool_dispatcher\"]" "qwen_reads_dispatcher_from_policy"
require_text "$repo_root/configs/qwen25_official_route_policy.json" "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh" "qwen_policy_dispatcher_boundary"
require_text "$repo_root/configs/systemd/dream7b-local-openai-gateway.service" "DREAM7B_OPENAI_PORT=18888" "dream7b_18888_unchanged"
require_text "$repo_root/configs/systemd/dream7b-bpu-experimental-gateway-18889.service" "DREAM7B_EXPERIMENTAL_PORT=18889" "dream7b_18889_unchanged"

if (( ${#failures[@]} > 0 )); then
  printf 'AI_NAS_HARNESS_SHADOW=0\n'
  printf 'harness_shadow_disabled=false\n'
  printf 'failure_count=%s\n' "${#failures[@]}"
  printf '%s\n' "${failures[@]}"
  exit 1
fi

printf 'AI_NAS_HARNESS_SHADOW=0\n'
printf 'harness_shadow_disabled=true\n'
printf 'env_file=%s\n' "$env_file"
printf 'production_route=openclaw-gateway:8765 -> qwen25-local-openai-gateway:18080 -> ai_nas_allowlisted_tool.sh\n'
printf 'protected_ports_unchanged=18888,18889\n'
