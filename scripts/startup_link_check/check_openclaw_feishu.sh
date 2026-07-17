#!/usr/bin/env bash
set +e

system_service="${LINKCHECK_SYSTEM_SERVICE:-openclaw-gateway.service}"
portal_service="${LINKCHECK_PORTAL_SERVICE:-openclaw-gateway.service}"
qwen_service="${LINKCHECK_QWEN_SERVICE:-qwen25-local-openai-gateway.service}"
user_runtime_dir="${LINKCHECK_USER_RUNTIME_DIR:-/run/user/1000}"
system_health="${LINKCHECK_SYSTEM_HEALTH:-http://127.0.0.1:18765/health}"
portal_health="${LINKCHECK_PORTAL_HEALTH:-http://127.0.0.1:8765/api/health}"
qwen_health="${LINKCHECK_QWEN_HEALTH:-http://127.0.0.1:18080/health}"
attempts="${LINKCHECK_HEALTH_ATTEMPTS:-1}"

export XDG_RUNTIME_DIR="$user_runtime_dir"

check_stack() {
  system_state="$(timeout 5 systemctl is-active "$system_service" 2>/dev/null || true)"
  portal_state="$(timeout 5 systemctl --user is-active "$portal_service" 2>/dev/null || true)"
  qwen_state="$(timeout 5 systemctl --user is-active "$qwen_service" 2>/dev/null || true)"
  system_http="$(curl -sS -o /dev/null --max-time 4 -w '%{http_code}' "$system_health" 2>/dev/null || true)"
  portal_http="$(curl -sS -o /dev/null --max-time 4 -w '%{http_code}' "$portal_health" 2>/dev/null || true)"
  qwen_http="$(curl -sS -o /dev/null --max-time 4 -w '%{http_code}' "$qwen_health" 2>/dev/null || true)"

  echo "SYSTEM_SERVICE_STATE=$system_state"
  echo "PORTAL_SERVICE_STATE=$portal_state"
  echo "QWEN_SERVICE_STATE=$qwen_state"
  echo "SYSTEM_HEALTH_HTTP=$system_http"
  echo "PORTAL_HEALTH_HTTP=$portal_http"
  echo "QWEN_HEALTH_HTTP=$qwen_http"

  if [ "$system_state" = "active" ] && [ "$portal_state" = "active" ] && [ "$qwen_state" = "active" ] &&
     [ "$system_http" = "200" ] && [ "$portal_http" = "200" ] && [ "$qwen_http" = "200" ]; then
    echo OPENCLAW_STACK_READY
    return 0
  fi
  return 1
}

i=1
while [ "$i" -le "$attempts" ]; do
  if check_stack; then
    exit 0
  fi
  [ "$i" -lt "$attempts" ] && sleep 3
  i=$((i + 1))
done

echo OPENCLAW_STACK_NOT_READY
exit 1
