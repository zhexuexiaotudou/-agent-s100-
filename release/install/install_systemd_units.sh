#!/usr/bin/env bash
set -u

MODE="user"
DRY_RUN=1
UNIT_DIR="release/systemd"
JSON_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="${2:-}"; shift 2 ;;
    --unit-dir) UNIT_DIR="${2:-}"; shift 2 ;;
    --apply) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

units=(openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-index-worker.service digua-ai-nightly-index.timer)
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
  mkdir -p "$target_dir"
  for unit in "${units[@]}"; do cp "$UNIT_DIR/$unit" "$target_dir/$unit"; done
  "${systemctl_cmd[@]}" daemon-reload
  "${systemctl_cmd[@]}" enable openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-nightly-index.timer
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
  "units": json.loads(os.environ["UNITS_JSON"]),
  "loopback_default": True,
  "enabled_on_apply": ["openclaw-gateway.service", "qwen25-local-openai-gateway.service", "digua-ai-nightly-index.timer"],
  "blockers": json.loads(os.environ["BLOCKERS_JSON"])
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
