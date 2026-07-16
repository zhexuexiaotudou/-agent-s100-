let currentPlan = null;
let approvalToken = null;

async function api(path, options = {}) {
  const token = window.sessionStorage.getItem("diguaAiNasToken") || "";
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) },
  });
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[character]);
}

function showJson(id, data) {
  document.getElementById(id).textContent = JSON.stringify(data, null, 2);
}

function renderPlan(data) {
  currentPlan = data.plan_id || data.plan?.plan_id || currentPlan;
  const items = data.items || [];
  document.getElementById("planBox").innerHTML = items.length
    ? items.map((item) => `<div class="item"><strong>${escapeHtml(item.final_filename || item.suggested_filename_zh || item.item_id)}</strong><div>${escapeHtml(item.operation)} · ${escapeHtml(item.status)}</div><div class="muted">${escapeHtml(item.source_rel || "")} -&gt; ${escapeHtml(item.target_rel || "")}</div></div>`).join("")
    : `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
}

async function refresh() {
  showJson("statusBox", await api("/api/auto-organize/status"));
}

document.getElementById("refresh").onclick = refresh;
document.getElementById("planForm").onsubmit = async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = Object.fromEntries(form.entries());
  const data = await api("/api/auto-organize/plan", { method: "POST", body: JSON.stringify(payload) });
  renderPlan(data);
};
document.getElementById("dryRun").onclick = async () => {
  if (!currentPlan) return;
  renderPlan(await api("/api/auto-organize/dry-run", { method: "POST", body: JSON.stringify({ plan_id: currentPlan }) }));
};
document.getElementById("approve").onclick = async () => {
  if (!currentPlan) return;
  const data = await api("/api/auto-organize/approve", { method: "POST", body: JSON.stringify({ plan_id: currentPlan, approval_phrase: `APPROVE AUTO ORGANIZE ${currentPlan}` }) });
  approvalToken = data.approval_token;
  renderPlan(data);
};
document.getElementById("execute").onclick = async () => {
  if (!currentPlan) return;
  renderPlan(await api("/api/auto-organize/execute", { method: "POST", body: JSON.stringify({ plan_id: currentPlan, approval_token: approvalToken }) }));
};
document.getElementById("rollback").onclick = async () => {
  if (!currentPlan) return;
  renderPlan(await api("/api/auto-organize/rollback", { method: "POST", body: JSON.stringify({ plan_id: currentPlan }) }));
};

refresh();
