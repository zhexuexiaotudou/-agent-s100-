#!/usr/bin/env bash
set -euo pipefail

PROVIDER=""
APPLY=0
CONFIRM=""
HOSTNAME=""
TUNNEL_ID=""
CREDENTIALS_FILE="/etc/cloudflared/digua-credentials.json"
CONFIG_FILE="/etc/cloudflared/digua.yml"
TEAM_DOMAIN=""
AUDIENCE=""
JSON_OUT=""
ENV_FILE="/etc/digua-ai-nas/digua.env"
ACTION="enable"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider) PROVIDER="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --disable) APPLY=1; ACTION="disable"; shift ;;
    --confirm) CONFIRM="${2:-}"; shift 2 ;;
    --hostname) HOSTNAME="${2:-}"; shift 2 ;;
    --tunnel-id) TUNNEL_ID="${2:-}"; shift 2 ;;
    --credentials-file) CREDENTIALS_FILE="${2:-}"; shift 2 ;;
    --config-file) CONFIG_FILE="${2:-}"; shift 2 ;;
    --team-domain) TEAM_DOMAIN="${2:-}"; shift 2 ;;
    --audience) AUDIENCE="${2:-}"; shift 2 ;;
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

blockers=()
[[ "$PROVIDER" == "tailscale" || "$PROVIDER" == "cloudflare" ]] || blockers+=("unsupported_provider")
if [[ "$APPLY" == "1" ]]; then command -v systemctl >/dev/null || blockers+=("systemctl_missing"); fi
if [[ "$PROVIDER" == "tailscale" ]]; then
  if [[ "$APPLY" == "1" ]]; then
    command -v tailscale >/dev/null || blockers+=("tailscale_cli_missing")
    expected="ENABLE PRIVATE TAILSCALE SERVE"; [[ "$ACTION" == "disable" ]] && expected="DISABLE TAILSCALE SERVE"
    [[ "$CONFIRM" == "$expected" ]] || blockers+=("confirmation_required")
    tailscale serve --help >/dev/null 2>&1 || blockers+=("tailscale_serve_help_failed")
  fi
elif [[ "$PROVIDER" == "cloudflare" ]]; then
  if [[ "$ACTION" == "enable" ]]; then
    [[ "$HOSTNAME" =~ ^[A-Za-z0-9.-]+$ && "$TUNNEL_ID" =~ ^[A-Za-z0-9._-]+$ && "$TEAM_DOMAIN" =~ ^[A-Za-z0-9.-]+$ && "$AUDIENCE" =~ ^[A-Za-z0-9._-]+$ ]] || blockers+=("cloudflare_access_configuration_invalid")
    [[ "$CREDENTIALS_FILE" == /* && "$CONFIG_FILE" == /* && "$ENV_FILE" == /* ]] || blockers+=("cloudflare_paths_must_be_absolute")
  fi
  if [[ "$APPLY" == "1" ]]; then
    command -v cloudflared >/dev/null || blockers+=("cloudflared_missing")
    expected="ENABLE CLOUDFLARE ACCESS TUNNEL"; [[ "$ACTION" == "disable" ]] && expected="DISABLE CLOUDFLARE TUNNEL"
    [[ "$CONFIRM" == "$expected" ]] || blockers+=("confirmation_required")
    if [[ "$ACTION" == "enable" ]]; then
      [[ -f "$CREDENTIALS_FILE" ]] || blockers+=("cloudflare_credentials_missing")
      [[ "$(stat -c '%a' "$CREDENTIALS_FILE" 2>/dev/null || true)" == "600" ]] || blockers+=("cloudflare_credentials_mode_must_be_600")
      [[ -f "$ENV_FILE" ]] || blockers+=("digua_env_file_missing")
    fi
  fi
fi

if [[ "$APPLY" == "1" && "${#blockers[@]}" -eq 0 ]]; then
  if [[ "$ACTION" == "disable" ]]; then
    if [[ "$PROVIDER" == "tailscale" ]]; then tailscale serve reset; else systemctl disable --now cloudflared.service; fi
    systemctl disable --now digua-product-remote-ingress.service
  else
    if [[ "$PROVIDER" == "tailscale" ]]; then
      systemctl enable --now digua-product-remote-ingress.service
      tailscale serve --bg http://127.0.0.1:8781
    else
      install -d -m 0700 "$(dirname "$CONFIG_FILE")"
      umask 077
      printf 'tunnel: %s\ncredentials-file: %s\ningress:\n  - hostname: %s\n    service: http://127.0.0.1:8781\n  - service: http_status:404\n' "$TUNNEL_ID" "$CREDENTIALS_FILE" "$HOSTNAME" > "$CONFIG_FILE"
      env_tmp="$(mktemp "$(dirname "$ENV_FILE")/.digua.env.XXXXXX")"
      grep -v -E '^(DIGUA_CF_TEAM_DOMAIN|DIGUA_CF_AUDIENCE)=' "$ENV_FILE" > "$env_tmp" || true
      printf 'DIGUA_CF_TEAM_DOMAIN=%s\nDIGUA_CF_AUDIENCE=%s\n' "$TEAM_DOMAIN" "$AUDIENCE" >> "$env_tmp"
      chmod --reference="$ENV_FILE" "$env_tmp"; chown --reference="$ENV_FILE" "$env_tmp"; mv "$env_tmp" "$ENV_FILE"
      systemctl enable --now digua-product-remote-ingress.service
      systemctl enable --now cloudflared.service
    fi
  fi
fi

blockers_json="$(printf '%s\n' "${blockers[@]-}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(BLOCKERS_JSON="$blockers_json" python3 - <<PY
import json, os
print(json.dumps({
  'ok': not json.loads(os.environ['BLOCKERS_JSON']), 'provider': '$PROVIDER',
  'action': '$ACTION', 'applied': bool($APPLY), 'private_origin': 'http://127.0.0.1:8781',
  'tailscale_funnel_enabled': False, 'router_port_forwarding_changed': False,
  'upnp_changed': False, 'cloudflare_access_required': '$PROVIDER' == 'cloudflare',
  'credentials_stored_in_database': False, 'production_verified': False,
  'blockers': json.loads(os.environ['BLOCKERS_JSON']),
}, ensure_ascii=False, indent=2))
PY
)"
[[ -z "$JSON_OUT" ]] || { mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; }
printf '%s\n' "$payload"
[[ "${#blockers[@]}" -eq 0 ]]
