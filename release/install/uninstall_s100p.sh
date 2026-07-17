#!/usr/bin/env bash
set -u

DRY_RUN=1
INSTALL_ROOT="/opt/digua-ai-nas"
SYSTEMD_MODE="system"
JSON_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --systemd-mode) SYSTEMD_MODE="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

units=(openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-index-worker.service)
systemctl_cmd=(systemctl --user)
[[ "$SYSTEMD_MODE" == "system" ]] && systemctl_cmd=(systemctl)

actions=()
for unit in "${units[@]}"; do actions+=("disable:$unit" "stop:$unit"); done
actions+=("remove_install_root:$INSTALL_ROOT")

safe_root=1
[[ "$INSTALL_ROOT" == /* && "$INSTALL_ROOT" != "/" && "$INSTALL_ROOT" != "/opt" && "$INSTALL_ROOT" != "/usr" ]] || safe_root=0

if [[ "$DRY_RUN" == "0" && "$safe_root" == "1" ]]; then
  for unit in "${units[@]}"; do
    "${systemctl_cmd[@]}" disable --now "$unit" >/dev/null 2>&1 || true
  done
  rm -rf "$INSTALL_ROOT"
fi

actions_json="$(printf '%s\n' "${actions[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(ACTIONS_JSON="$actions_json" python3 - <<PY
import json, os
print(json.dumps({
  "ok": bool($safe_root),
  "dry_run": bool($DRY_RUN),
  "install_root": "$INSTALL_ROOT",
  "systemd_mode": "$SYSTEMD_MODE",
  "nas_data_removed": False,
  "personal_data_removed": False,
  "actions": json.loads(os.environ["ACTIONS_JSON"]),
  "blockers": [] if bool($safe_root) else ["unsafe_install_root"],
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( safe_root ? 0 : 1 ))
