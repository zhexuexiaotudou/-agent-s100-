#!/usr/bin/env bash
set -u

MODE="user"
DRY_RUN=1
UNIT_DIR="release/systemd"
JSON_OUT=""
INSTALL_ROOT="/opt/digua-ai-nas"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
REPORT_ROOT="/mnt/nas/openclaw/reports/qwen25_ai_nas"
ENV_FILE=""
SIMULATION=0
TARGET_DIR_OVERRIDE=""
SERVICE_USER="${SUDO_USER:-$(id -un)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="${2:-}"; shift 2 ;;
    --unit-dir) UNIT_DIR="${2:-}"; shift 2 ;;
    --apply) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --personal-root) PERSONAL_ROOT="${2:-}"; shift 2 ;;
    --report-root) REPORT_ROOT="${2:-}"; shift 2 ;;
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --simulate) SIMULATION=1; DRY_RUN=0; shift ;;
    --target-dir) TARGET_DIR_OVERRIDE="${2:-}"; shift 2 ;;
    --service-user) SERVICE_USER="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

units=(openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-index-worker.service digua-product-access.service digua-product-remote-ingress.service)
enabled_units=(openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-index-worker.service digua-product-access.service)
target_dir="$HOME/.config/systemd/user"
systemctl_cmd=(systemctl --user)
if [[ "$MODE" == "system" ]]; then
  target_dir="/etc/systemd/system"
  systemctl_cmd=(systemctl)
fi
[[ -n "$TARGET_DIR_OVERRIDE" ]] && target_dir="$TARGET_DIR_OVERRIDE"
if [[ -z "$ENV_FILE" ]]; then
  if [[ "$MODE" == "system" ]]; then ENV_FILE="/etc/digua-ai-nas/digua.env"; else ENV_FILE="$HOME/.config/digua-ai-nas/digua.env"; fi
fi

blockers=()
services_started_verified=0
[[ "$MODE" == "user" || "$MODE" == "system" ]] || blockers+=("unsupported_mode:$MODE")
[[ "$SERVICE_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || blockers+=("service_user_contains_unsafe_characters")
for unit in "${units[@]}"; do
  [[ -f "$UNIT_DIR/$unit" ]] || blockers+=("unit_missing:$unit")
done

if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  mkdir -p "$target_dir" || blockers+=("target_dir_create_failed:$target_dir")
  user_directive=""; [[ "$MODE" == "system" ]] && user_directive="User=$SERVICE_USER"
  for unit in "${units[@]}"; do
    if ! sed -e "s|@DIGUA_INSTALL_ROOT@|$INSTALL_ROOT|g" -e "s|@DIGUA_PERSONAL_ROOT@|$PERSONAL_ROOT|g" -e "s|@DIGUA_REPORT_ROOT@|$REPORT_ROOT|g" -e "s|@DIGUA_ENV_FILE@|$ENV_FILE|g" -e "s|@DIGUA_USER_DIRECTIVE@|$user_directive|g" "$UNIT_DIR/$unit" > "$target_dir/$unit"; then
      blockers+=("unit_render_failed:$unit")
    fi
  done
  if [[ "$SIMULATION" == "0" && "${#blockers[@]}" -eq 0 ]] && ! "${systemctl_cmd[@]}" daemon-reload; then
    blockers+=("systemd_daemon_reload_failed")
  fi
  if [[ "$SIMULATION" == "0" && "${#blockers[@]}" -eq 0 ]] && ! "${systemctl_cmd[@]}" enable --now "${enabled_units[@]}"; then
    blockers+=("systemd_enable_start_failed")
  fi
  if [[ "$SIMULATION" == "0" && "${#blockers[@]}" -eq 0 ]]; then
    services_started_verified=1
    for unit in "${enabled_units[@]}"; do
      if ! "${systemctl_cmd[@]}" is-active --quiet "$unit"; then services_started_verified=0; blockers+=("service_not_active:$unit"); fi
    done
  fi
fi

ok=1
[[ "${#blockers[@]}" -eq 0 ]] || ok=0
blockers_json="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
units_json="$(printf '%s\n' "${units[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(BLOCKERS_JSON="$blockers_json" UNITS_JSON="$units_json" python3 - <<PY
import json, os
payload = {
  "ok": bool($ok),
  "dry_run": bool($DRY_RUN),
  "simulation": bool($SIMULATION),
  "production_verified": False,
  "mode": "$MODE",
  "target_dir": "$target_dir",
  "install_root": "$INSTALL_ROOT",
  "personal_root": "$PERSONAL_ROOT",
  "report_root": "$REPORT_ROOT",
  "env_file": "$ENV_FILE",
  "service_user": "$SERVICE_USER",
  "units": json.loads(os.environ["UNITS_JSON"]),
  "loopback_default": True,
  "enabled_on_apply": [] if bool($DRY_RUN) or bool($SIMULATION) else ["openclaw-gateway.service", "qwen25-local-openai-gateway.service", "digua-ai-index-worker.service", "digua-product-access.service"],
  "remote_ingress_default_enabled": False,
  "services_started_verified": bool($services_started_verified),
  "blockers": json.loads(os.environ["BLOCKERS_JSON"])
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
