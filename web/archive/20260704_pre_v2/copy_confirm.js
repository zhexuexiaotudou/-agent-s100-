async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  return {ok: response.ok, status: response.status, data};
}

function renderCopyDecision(target, data) {
  target.textContent = JSON.stringify({
    ok: data.ok,
    route: data.route,
    status: data.status,
    reason_codes: data.reason_codes || [],
    source_path_hash: data.source_path_hash,
    target_path_hash: data.target_path_hash,
    source_sha256_prefix: data.source_sha256_prefix,
    target_hash_verified: data.target_hash_verified,
    qwen_execution_authority: data.qwen_execution_authority,
    cloud_private_egress: data.cloud_private_egress
  }, null, 2);
}

window.HarnessCopyConfirm = {
  postJson,
  renderCopyDecision
};
