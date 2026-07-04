async function fetchHarnessStatus(url = "/api/harness/status") {
  const response = await fetch(url, {headers: {"Accept": "application/json"}});
  const data = await response.json();
  return {ok: response.ok, status: response.status, data};
}

function sanitizeHarnessStatus(data) {
  return {
    ok: Boolean(data && data.ok),
    service: data && data.service,
    policy_id: data && data.policy_id,
    readonly_workspaces_enabled: Boolean(data && data.readonly_workspaces_enabled),
    token_budget_gate_enabled: Boolean(data && data.token_budget_gate_enabled),
    privacy_redaction_gate_enabled: Boolean(data && data.privacy_redaction_gate_enabled),
    copy_execute_enabled: Boolean(data && data.copy_execute_enabled),
    copy_execute_requires: data && data.copy_execute_requires,
    forbidden_actions: data && data.forbidden_actions,
    qwen_execution_authority: Boolean(data && data.qwen_execution_authority),
    cloud_private_raw_egress: Boolean(data && data.cloud_private_raw_egress),
    dispatcher_exists: Boolean(data && data.dispatcher_exists),
    dispatcher_sha256_prefix: data && data.dispatcher_sha256 ? String(data.dispatcher_sha256).slice(0, 12) : null,
    raw_private_content_in_status: Boolean(data && data.raw_private_content_in_status)
  };
}

function renderHarnessStatus(target, data) {
  target.textContent = JSON.stringify(sanitizeHarnessStatus(data), null, 2);
}

async function attachHarnessStatus(targetId = "harness-status-output") {
  const target = document.getElementById(targetId);
  if (!target) {
    return null;
  }
  const result = await fetchHarnessStatus();
  renderHarnessStatus(target, result.data);
  return result;
}

window.HarnessStatus = {
  fetchHarnessStatus,
  sanitizeHarnessStatus,
  renderHarnessStatus,
  attachHarnessStatus
};

document.addEventListener("DOMContentLoaded", () => {
  attachHarnessStatus().catch((error) => {
    const target = document.getElementById("harness-status-output");
    if (target) {
      target.textContent = JSON.stringify({ok: false, error: String(error)}, null, 2);
    }
  });
});
