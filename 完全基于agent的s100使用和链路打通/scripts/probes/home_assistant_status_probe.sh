#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-}"
if [[ -z "$out_dir" ]]; then
  if [[ -d /mnt/nas/openclaw/logs/probes && -w /mnt/nas/openclaw/logs/probes ]]; then
    out_dir="/mnt/nas/openclaw/logs/probes"
  else
    out_dir="/root/.openclaw/workspace/logs/probes"
  fi
fi

case "$out_dir" in
  ""|"/"|"/mnt"|"/mnt/nas"|"/home"|"/root")
    echo "Refusing unsafe output directory: $out_dir" >&2
    exit 2
    ;;
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/home_assistant_status_$stamp.md"

read_env_value() {
  local key="$1"
  local file="$2"
  [[ -f "$file" ]] || return 1
  awk -v key="$key" '
    $0 ~ "^[[:space:]]*" key "=" {
      sub("^[[:space:]]*" key "=", "")
      gsub(/^[[:space:]]+|[[:space:]]+$/, "")
      gsub(/^["'\'']|["'\'']$/, "")
      print
      exit
    }
  ' "$file"
}

first_value() {
  local key value
  for key in "$@"; do
    value="${!key:-}"
    if [[ -n "$value" ]]; then
      printf '%s\n' "$value"
      return 0
    fi
  done
  return 1
}

config_files=(
  "/root/.openclaw/workspace/config/home_assistant.env"
  "/root/.openclaw/workspace/.env"
  "/root/.openclaw/credentials/home-assistant.env"
)

ha_url="$(first_value HOME_ASSISTANT_URL HA_URL 2>/dev/null || true)"
ha_token="$(first_value HOME_ASSISTANT_TOKEN HA_TOKEN 2>/dev/null || true)"
config_source="environment"

if [[ -z "$ha_url" || -z "$ha_token" ]]; then
  for file in "${config_files[@]}"; do
    if [[ -z "$ha_url" ]]; then
      ha_url="$(read_env_value HOME_ASSISTANT_URL "$file" || read_env_value HA_URL "$file" || true)"
      [[ -n "$ha_url" ]] && config_source="$file"
    fi
    if [[ -z "$ha_token" ]]; then
      ha_token="$(read_env_value HOME_ASSISTANT_TOKEN "$file" || read_env_value HA_TOKEN "$file" || true)"
      [[ -n "$ha_token" ]] && config_source="$file"
    fi
  done
fi

ha_url="${ha_url%/}"
api_status="not_attempted"
states_status="not_attempted"
entity_count="unknown"
domain_summary="not_available"
verdict="blocked_no_config"
api_tmp="$(mktemp)"
states_tmp="$(mktemp)"
trap 'rm -f "$api_tmp" "$states_tmp"' EXIT

if [[ -n "$ha_url" && -n "$ha_token" ]]; then
  verdict="checking"
  api_code="$(curl -sS -m 8 -o "$api_tmp" -w '%{http_code}' \
    -H "Authorization: Bearer $ha_token" \
    -H "Content-Type: application/json" \
    "$ha_url/api/" 2>/dev/null || true)"
  api_status="$api_code"

  states_code="$(curl -sS -m 12 -o "$states_tmp" -w '%{http_code}' \
    -H "Authorization: Bearer $ha_token" \
    -H "Content-Type: application/json" \
    "$ha_url/api/states" 2>/dev/null || true)"
  states_status="$states_code"

  if [[ "$api_code" == "200" && "$states_code" == "200" ]]; then
    verdict="ok_readonly"
    entity_count="$(python3 - "$states_tmp" <<'PY' 2>/dev/null || echo unknown
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
print(len(data) if isinstance(data, list) else "unknown")
PY
)"
    domain_summary="$(python3 - "$states_tmp" <<'PY' 2>/dev/null || echo not_available
import collections, json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
counts = collections.Counter()
if isinstance(data, list):
    for item in data:
        entity = str(item.get("entity_id", ""))
        if "." in entity:
            counts[entity.split(".", 1)[0]] += 1
for domain, count in counts.most_common(12):
    print(f"{domain}: {count}")
PY
)"
  elif [[ "$api_code" == "401" || "$states_code" == "401" || "$api_code" == "403" || "$states_code" == "403" ]]; then
    verdict="blocked_auth"
  else
    verdict="blocked_connectivity"
  fi
fi

{
  echo "# Home Assistant Read-Only Status Probe"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- output: $report"
  echo "- mode: read-only"
  echo "- control_api_called: no"
  echo "- services_api_called: no"
  echo
  echo "## Configuration"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Config source | ${config_source:-not_found} |"
  echo "| URL configured | $([[ -n "$ha_url" ]] && echo yes || echo no) |"
  echo "| Token configured | $([[ -n "$ha_token" ]] && echo yes || echo no) |"
  echo
  echo "## Read-Only API Checks"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| GET /api/ status | $api_status |"
  echo "| GET /api/states status | $states_status |"
  echo "| Entity count | $entity_count |"
  echo "| Verdict | $verdict |"
  echo
  echo "## Entity Domains"
  echo
  echo '```text'
  printf '%s\n' "$domain_summary"
  echo '```'
  echo
  echo "## Next Actions"
  if [[ "$verdict" == "blocked_no_config" ]]; then
    echo "1. Create /root/.openclaw/workspace/config/home_assistant.env with HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN."
    echo "2. Use a long-lived access token with read-only intent and do not put it in reports."
    echo "3. Re-run this probe; it will only call GET /api/ and GET /api/states."
  elif [[ "$verdict" == "ok_readonly" ]]; then
    echo "1. Keep B-008 read-only unless a separate B-009 control whitelist is approved."
    echo "2. Archive this report under NAS after A-003 is mounted."
  else
    echo "1. Check Home Assistant URL reachability from S100P."
    echo "2. Check token validity and Home Assistant API permissions."
  fi
} > "$report"

echo "$report"
