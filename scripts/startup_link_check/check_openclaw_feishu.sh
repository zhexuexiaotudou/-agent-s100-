#!/usr/bin/env bash
set +e

runtime_dir="${1:-/run/user/0}"
service="${2:-openclaw-gateway.service}"
log="/tmp/openclaw/openclaw-$(date +%F).log"

state="$(timeout 5 sudo -n env XDG_RUNTIME_DIR="$runtime_dir" systemctl --user is-active "$service" 2>/dev/null || true)"
echo "SERVICE_STATE=$state"

if [ -f "$log" ]; then
  timeout 5 sudo -n tail -200 "$log" 2>/dev/null |
    grep -Ei 'ws client ready|received message|dispatch complete|EAI_AGAIN|open.feishu.cn|99991672' |
    tail -80 || true
fi

if [ "$state" = "active" ] && timeout 5 sudo -n tail -200 "$log" 2>/dev/null | grep -q 'ws client ready'; then
  echo OPENCLAW_READY
  exit 0
fi

exit 1
