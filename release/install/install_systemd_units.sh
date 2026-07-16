#!/usr/bin/env bash
set -u

MODE="user"
DRY_RUN=1
UNIT_DIR="release/systemd"
JSON_OUT=""
INSTALL_ROOT="/opt/digua-ai-nas"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
REPORT_ROOT="/mnt/nas/openclaw/reports/qwen25_ai_nas"

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
    *) shift ;;
  esac
done

units=(openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-index-worker.service)
target_dir="$HOME/.config/systemd/user"
systemctl_cmd=(systemctl --user)
if [[ "$MODE" == "system" ]]; then
  target_dir="/etc/systemd/system"
  systemctl_cmd=(systemctl)
fi

blockers=()
[[ "$MODE" == "user" || "$MODE" == "system" ]] || blockers+=("unsupported_mode:$MODE")
for unit in "${units[@]}"; do
  [[ -f "$UNIT_DIR/$unit" ]] || blockers+=("unit_missing:$unit")
done

if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  mkdir -p "$target_dir" || blockers+=("target_dir_create_failed:$target_dir")
  for unit in "${units[@]}"; do
    if ! sed -e "s|@DIGUA_INSTALL_ROOT@|$INSTALL_ROOT|g" -e "s|@DIGUA_PERSONAL_ROOT@|$PERSONAL_ROOT|g" -e "s|@DIGUA_REPORT_ROOT@|$REPORT_ROOT|g" "$UNIT_DIR/$unit" > "$target_dir/$unit"; then
      blockers+=("unit_render_failed:$unit")
    fi
  done
  if [[ "${#blockers[@]}" -eq 0 ]] && ! "${systemctl_cmd[@]}" daemon-reload; then
    blockers+=("systemd_daemon_reload_failed")
  fi
  if [[ "${#blockers[@]}" -eq 0 ]] && ! "${systemctl_cmd[@]}" enable --now openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-index-worker.service; then
    blockers+=("systemd_enable_start_failed")
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
  "mode": "$MODE",
  "target_dir": "$target_dir",
  "install_root": "$INSTALL_ROOT",
  "personal_root": "$PERSONAL_ROOT",
  "report_root": "$REPORT_ROOT",
  "units": json.loads(os.environ["UNITS_JSON"]),
  "loopback_default": True,
  "enabled_on_apply": ["openclaw-gateway.service", "qwen25-local-openai-gateway.service", "digua-ai-index-worker.service"],
  "blockers": json.loads(os.environ["BLOCKERS_JSON"])
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
