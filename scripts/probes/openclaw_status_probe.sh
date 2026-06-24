#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-}"
if [[ -z "$out_dir" ]]; then
  if [[ -d /mnt/nas/openclaw/logs/probes && -w /mnt/nas/openclaw/logs/probes ]]; then
    out_dir="/mnt/nas/openclaw/logs/probes"
  else
    out_dir="/tmp/openclaw-probes"
  fi
fi

case "$out_dir" in
  ""|"/"|"/mnt"|"/mnt/nas"|"/home"|"/root")
    echo "Refusing unsafe output directory: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/openclaw_status_$stamp.txt"

{
  echo "timestamp=$(date -Is)"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "kernel=$(uname -a)"
  echo
  echo "## node"
  command -v node || true
  node -v 2>&1 || true
  command -v npm || true
  npm -v 2>&1 || true
  echo
  echo "## network"
  ip -br addr 2>/dev/null || true
  ip route 2>/dev/null || true
  echo
  echo "## openclaw-gateway"
  systemctl --user --no-pager --full status openclaw-gateway 2>&1 | sed -n '1,24p' || true
  ss -ltnp 2>/dev/null | grep 18789 || true
  echo
  echo "## openclaw config summary"
  node <<'NODE' 2>/dev/null || true
const fs = require('fs');
const path = '/root/.openclaw/openclaw.json';
const cfg = JSON.parse(fs.readFileSync(path, 'utf8'));
console.log(JSON.stringify({
  searchProvider: cfg.tools?.web?.search?.provider,
  searchEnabled: cfg.tools?.web?.search?.enabled,
  tavilyEnabled: cfg.plugins?.entries?.tavily?.enabled,
  feishuGroupPolicy: cfg.channels?.feishu?.groupPolicy,
  feishuRequireMention: cfg.channels?.feishu?.requireMention
}, null, 2));
NODE
  echo
  echo "## nas mount"
  mount | grep -i openclaw || true
  ls -ld /mnt/nas /mnt/nas/openclaw 2>&1 || true
} > "$report"

echo "$report"
