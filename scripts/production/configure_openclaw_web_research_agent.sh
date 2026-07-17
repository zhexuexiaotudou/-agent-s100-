#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_BIN="${OPENCLAW_BIN:-/opt/node-v22.19.0-linux-arm64/bin/openclaw}"
AGENT_ID="${AI_NAS_WEB_RESEARCH_AGENT:-web-research}"
MODEL_ID="${AI_NAS_WEB_RESEARCH_MODEL:-custom-gateway/MiniMax-M2.7}"
WORKSPACE_DIR="${AI_NAS_WEB_RESEARCH_WORKSPACE:-/root/.openclaw/workspace-web-research}"
AGENT_DIR="${AI_NAS_WEB_RESEARCH_AGENT_DIR:-/root/.openclaw/agents/web-research/agent}"
CONFIG_FILE="${OPENCLAW_CONFIG_PATH:-/root/.openclaw/openclaw.json}"
BACKUP_ROOT="${AI_NAS_OPENCLAW_CONFIG_BACKUP_ROOT:-/root/.openclaw/backups/ai-nas-web-research}"
ALLOWED_TOOLS='["web_search","web_fetch","tavily_search","tavily_extract"]'
DENIED_TOOLS='["read","edit","write","apply_patch","exec","process","nodes","cron","message","gateway","browser","s100p_run_probe","sessions_send","sessions_spawn","subagents","skill_workshop"]'

if [[ "${EUID}" -ne 0 ]]; then
  echo "configure_openclaw_web_research_agent.sh must run as root" >&2
  exit 1
fi
if [[ ! -x "${OPENCLAW_BIN}" ]]; then
  echo "OpenClaw CLI not executable: ${OPENCLAW_BIN}" >&2
  exit 1
fi
if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "OpenClaw config not found: ${CONFIG_FILE}" >&2
  exit 1
fi

export HOME=/root
export PATH="$(dirname "${OPENCLAW_BIN}"):/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

mkdir -p "${BACKUP_ROOT}"
chmod 700 "${BACKUP_ROOT}"
backup_path="${BACKUP_ROOT}/openclaw.json.$(date +%Y%m%d-%H%M%S)"
cp -p "${CONFIG_FILE}" "${backup_path}"
chmod 600 "${backup_path}"

if ! "${OPENCLAW_BIN}" agents list --json | python3 -c '
import json, sys
agent_id = sys.argv[1]
agents = json.load(sys.stdin)
raise SystemExit(0 if any(str(item.get("id")) == agent_id for item in agents if isinstance(item, dict)) else 1)
' "${AGENT_ID}"; then
  "${OPENCLAW_BIN}" agents add "${AGENT_ID}" \
    --workspace "${WORKSPACE_DIR}" \
    --agent-dir "${AGENT_DIR}" \
    --model "${MODEL_ID}" \
    --non-interactive \
    --json >/dev/null
fi

agent_index="$("${OPENCLAW_BIN}" config get agents.list --json | python3 -c '
import json, sys
agent_id = sys.argv[1]
agents = json.load(sys.stdin)
for index, item in enumerate(agents):
    if isinstance(item, dict) and str(item.get("id")) == agent_id:
        print(index)
        raise SystemExit(0)
raise SystemExit(1)
' "${AGENT_ID}")"

"${OPENCLAW_BIN}" config set "agents.list[${agent_index}].model" "${MODEL_ID}" >/dev/null
"${OPENCLAW_BIN}" config set "agents.list[${agent_index}].tools.allow" "${ALLOWED_TOOLS}" --strict-json >/dev/null
"${OPENCLAW_BIN}" config set "agents.list[${agent_index}].tools.deny" "${DENIED_TOOLS}" --strict-json >/dev/null
"${OPENCLAW_BIN}" config validate >/dev/null

if [[ "${RESTART_OPENCLAW_GATEWAY:-0}" == "1" ]]; then
  XDG_RUNTIME_DIR=/run/user/0 systemctl --user restart openclaw-gateway.service
  XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active --quiet openclaw-gateway.service
fi

python3 - "${CONFIG_FILE}" "${AGENT_ID}" "${backup_path}" <<'PY'
import json
import sys

config_path, agent_id, backup_path = sys.argv[1:]
config = json.load(open(config_path, encoding="utf-8"))
agent = next(item for item in (config.get("agents") or {}).get("list") or [] if item.get("id") == agent_id)
print(json.dumps({
    "ok": True,
    "agent": agent_id,
    "model": agent.get("model"),
    "workspace": agent.get("workspace"),
    "tools": agent.get("tools"),
    "config_backup": backup_path,
}, ensure_ascii=False))
PY
