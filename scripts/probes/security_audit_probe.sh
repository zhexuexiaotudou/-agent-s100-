#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-${OPENCLAW_PROBE_DIR:-/root/.openclaw/workspace/logs/probes}}"
workspace="${OPENCLAW_WORKSPACE_DIR:-/root/.openclaw/workspace}"

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $out_dir" >&2
    exit 2
    ;;
esac

case "$workspace" in
  /root/.openclaw/workspace|/mnt/nas/openclaw) ;;
  *)
    echo "Refusing workspace outside approved roots: $workspace" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/security_audit_$stamp.md"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

openclaw_bin() {
  PATH=/root/.local/lib/node-v24.16.0-linux-arm64/bin:/root/.npm-global/bin:$PATH command openclaw "$@"
}

status_line() {
  local item="$1"
  local status="$2"
  local detail="$3"
  printf '| %s | %s | %s |\n' "$item" "$status" "$detail"
}

secret_scan() {
  local target="$1"
  local output="$2"
  if [[ ! -e "$target" ]]; then
    : > "$output"
    return 0
  fi

  find "$target" \
    \( -path '*/node_modules/*' -o -path '*/.git/*' -o -path '*/robot_datasets/*' \) -prune \
    -o -type f \
    \( -name '*.json' -o -name '*.md' -o -name '*.txt' -o -name '*.env' -o -name '*.sh' -o -name '*.js' \) \
    -print0 2>/dev/null \
    | while IFS= read -r -d '' file; do
        awk '
          BEGIN { IGNORECASE=1 }
          /tvly-[A-Za-z0-9_-]{20,}/ ||
          /sk-[A-Za-z0-9_-]{20,}/ ||
          /(api[_-]?key|secret|token|authorization|password)[[:space:]]*[:=][[:space:]]*["]?[A-Za-z0-9_./:+=@-]{12,}/ {
            printf "%s:%d: possible secret-like text\n", FILENAME, FNR
          }
        ' "$file" 2>/dev/null || true
      done > "$output"
}

listeners_file="$tmp_dir/listeners.txt"
ss -ltnp 2>/dev/null > "$listeners_file" || true

rpcinfo_file="$tmp_dir/rpcinfo.txt"
rpcinfo -p 2>/dev/null > "$rpcinfo_file" || true

public_listeners_file="$tmp_dir/public_listeners.txt"
awk '
  $1 == "LISTEN" &&
  $4 !~ /^127\./ &&
  $4 !~ /^\[::1\]:/ &&
  $4 !~ /^127\.0\.0\.53/ {
    print
  }
' "$listeners_file" > "$public_listeners_file" || true
public_listener_count="$(wc -l < "$public_listeners_file" | tr -d ' ')"

listener_review_file="$tmp_dir/listener_review.md"
{
  echo "| Listener | Category | Baseline action |"
  echo "| --- | --- | --- |"
  if [[ "$public_listener_count" == "0" ]]; then
    echo "| none | pass | no non-loopback listeners |"
  else
    while IFS= read -r line; do
      local_addr="$(printf '%s\n' "$line" | awk '{print $4}')"
      port="${local_addr##*:}"
      category="review"
      action="review against final S100P service policy"
      if [[ "$line" == *":18789"* || "$line" == *":18791"* ]]; then
        category="fail"
        action="OpenClaw Gateway must stay loopback-only"
      elif grep -Eq "[[:space:]](tcp|udp)[[:space:]]+$port[[:space:]]+" "$rpcinfo_file" 2>/dev/null; then
        category="nfs-rpc"
        action="disable if S100P is not serving NFS; otherwise firewall to trusted LAN only"
      elif [[ "$line" == *"LISTEN 0      64"* && "$line" != *"users:"* ]]; then
        category="nfs-rpc"
        action="kernel RPC/NFS-style listener; disable NFS stack if not needed"
      elif [[ "$line" == *":22 "* || "$line" == *":22"* ]]; then
        category="admin"
        action="keep only on trusted LAN/Tailscale; prefer key auth"
      elif [[ "$line" == *"x11vnc"* || "$line" == *":5900"* ]]; then
        category="remote-desktop"
        action="disable unless RDK Studio desktop access is required"
      elif [[ "$line" == *"rpc."* || "$line" == *"rpcbind"* || "$line" == *"mountd"* || "$line" == *":111"* || "$line" == *":2049"* ]]; then
        category="nfs-rpc"
        action="disable if S100P is not serving NFS; otherwise firewall to trusted LAN only"
      elif [[ "$line" == *"iiod"* ]]; then
        category="hardware-daemon"
        action="keep only if IIO tooling is needed; otherwise disable or firewall"
      fi
      escaped="${line//|/\\|}"
      echo "| \`$escaped\` | $category | $action |"
    done < "$public_listeners_file"
  fi
} > "$listener_review_file"

gateway_public="no"
if awk '$0 ~ /18789/ && $4 !~ /127\.0\.0\.1:/ && $4 !~ /\[::1\]:/ { found=1 } END { exit found ? 0 : 1 }' "$listeners_file"; then
  gateway_public="yes"
fi

config_json="$tmp_dir/config.json"
node <<'NODE' > "$config_json" 2>/dev/null || true
const fs = require("fs");
const path = "/root/.openclaw/openclaw.json";
const result = {
  exists: fs.existsSync(path),
  parse_ok: false
};
if (result.exists) {
  try {
    const cfg = JSON.parse(fs.readFileSync(path, "utf8"));
    result.parse_ok = true;
    result.search_provider = cfg.tools?.web?.search?.provider ?? null;
    result.search_enabled = cfg.tools?.web?.search?.enabled ?? null;
    result.tavily_enabled = cfg.plugins?.entries?.tavily?.enabled ?? null;
    result.feishu_group_policy = cfg.channels?.feishu?.groupPolicy ?? null;
    result.feishu_require_mention = cfg.channels?.feishu?.requireMention ?? null;
    result.exec_security = cfg.tools?.exec?.security ?? null;
    result.exec_ask = cfg.tools?.exec?.ask ?? null;
    result.exec_safe_bins_count = Array.isArray(cfg.tools?.exec?.safeBins) ? cfg.tools.exec.safeBins.length : null;
    result.plugins_allow_count = Array.isArray(cfg.plugins?.allow) ? cfg.plugins.allow.length : null;
    result.has_tavily_key = Boolean(
      cfg.plugins?.entries?.tavily?.config?.apiKey ||
      cfg.tools?.web?.search?.tavily?.apiKey
    );
    result.has_feishu_secret = Boolean(
      cfg.channels?.feishu?.secret ||
      cfg.channels?.feishu?.appSecret ||
      cfg.channels?.feishu?.app_secret
    );
  } catch (error) {
    result.error = error.message;
  }
}
console.log(JSON.stringify(result, null, 2));
NODE

config_validate="$tmp_dir/config_validate.txt"
openclaw_bin config validate > "$config_validate" 2>&1 || true

plugins_list="$tmp_dir/plugins.txt"
openclaw_bin plugins list > "$plugins_list" 2>&1 || true

secret_hits="$tmp_dir/secret_hits.txt"
secret_scan "$workspace" "$secret_hits"
secret_hit_count="$(wc -l < "$secret_hits" | tr -d ' ')"

nas_status="not_mounted"
if mountpoint -q /mnt/nas/openclaw 2>/dev/null; then
  nas_status="mounted"
elif [[ -d /mnt/nas/openclaw ]]; then
  nas_status="directory_exists_not_mounted"
fi

config_valid="warn"
if grep -q 'Config valid' "$config_validate" 2>/dev/null; then
  config_valid="pass"
fi

tavily_loaded="warn"
if grep -qi 'tavily.*loaded' "$plugins_list" 2>/dev/null; then
  tavily_loaded="pass"
fi

s100p_plugin_loaded="warn"
if grep -qi 's100p-.*loaded' "$plugins_list" 2>/dev/null; then
  s100p_plugin_loaded="pass"
fi

gateway_status="pass"
gateway_detail="loopback only"
if [[ "$gateway_public" == "yes" ]]; then
  gateway_status="fail"
  gateway_detail="18789 is listening on a non-loopback address"
fi

secret_status="pass"
secret_detail="no secret-like text found in scanned workspace files"
if [[ "$secret_hit_count" != "0" ]]; then
  secret_status="warn"
  secret_detail="$secret_hit_count secret-like metadata hits; values are redacted"
fi

nas_audit_status="warn"
nas_detail="$nas_status"
if [[ "$nas_status" == "mounted" ]]; then
  nas_audit_status="pass"
fi

public_listener_status="pass"
public_listener_detail="$public_listener_count non-loopback listeners"
if [[ "$public_listener_count" != "0" ]]; then
  public_listener_status="warn"
  public_listener_detail="$public_listener_count non-loopback listeners; review exposed services"
fi

{
  echo "# OpenClaw S100P Security Audit"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- hostname: $(hostname 2>/dev/null || true)"
  echo "- workspace: $workspace"
  echo "- report: $report"
  echo
  echo "## Verdict Matrix"
  echo
  echo "| Check | Status | Detail |"
  echo "| --- | --- | --- |"
  status_line "OpenClaw config validation" "$config_valid" "$(tr '\n' ' ' < "$config_validate" | sed 's/|/\\|/g' | cut -c1-180)"
  status_line "Gateway exposure" "$gateway_status" "$gateway_detail"
  status_line "Tavily plugin" "$tavily_loaded" "plugin list contains Tavily loaded"
  status_line "S100P allowlisted plugin" "$s100p_plugin_loaded" "plugin list contains s100p allowlisted tools loaded"
  status_line "Non-loopback listeners" "$public_listener_status" "$public_listener_detail"
  status_line "NAS workspace mount" "$nas_audit_status" "$nas_detail"
  status_line "Workspace secret scan" "$secret_status" "$secret_detail"
  echo
  echo "## Redacted Config Summary"
  echo
  echo '```json'
  cat "$config_json"
  echo '```'
  echo
  echo "## Gateway Listeners"
  echo
  echo '```text'
  grep -E '18789|State|LISTEN' "$listeners_file" 2>/dev/null || true
  echo '```'
  echo
  echo "## Non-Loopback Listeners"
  echo
  echo '```text'
  if [[ "$public_listener_count" == "0" ]]; then
    echo "none"
  else
    cat "$public_listeners_file"
  fi
  echo '```'
  echo
  echo "## Non-Loopback Listener Review"
  echo
  cat "$listener_review_file"
  echo
  echo "## RPC Services"
  echo
  echo '```text'
  if [[ -s "$rpcinfo_file" ]]; then
    cat "$rpcinfo_file"
  else
    echo "rpcinfo unavailable or no RPC services reported"
  fi
  echo '```'
  echo
  echo "## Plugin Status"
  echo
  echo '```text'
  grep -Ei 'tavily|s100p|loaded' "$plugins_list" 2>/dev/null || sed -n '1,40p' "$plugins_list"
  echo '```'
  echo
  echo "## Secret-Like Metadata Hits"
  echo
  echo "Values are intentionally not printed."
  echo
  if [[ "$secret_hit_count" == "0" ]]; then
    echo "No secret-like metadata hits in scanned workspace files."
  else
    echo '```text'
    sed -n '1,80p' "$secret_hits"
    echo '```'
  fi
  echo
  echo "## Current Blockers"
  echo
  if [[ "$nas_status" != "mounted" ]]; then
    echo "- NAS-backed validation is pending until /mnt/nas/openclaw is mounted."
  fi
  if [[ "$gateway_public" == "yes" ]]; then
    echo "- Gateway listener must be restricted to loopback/LAN policy before treating A-010 as verified."
  fi
  if [[ "$public_listener_count" != "0" ]]; then
    echo "- Review non-loopback listeners and close services not required for the S100P baseline."
  fi
  if [[ "$secret_hit_count" != "0" ]]; then
    echo "- Review secret-like metadata hits and move real secrets out of versioned/shared workspace files."
  fi
  echo "- Sandbox isolation remains blocked until Docker/Podman/runc is installed or A-006 is dropped."
} > "$report"

echo "$report"
