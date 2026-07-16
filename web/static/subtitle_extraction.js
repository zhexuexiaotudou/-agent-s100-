async function api(path, options = {}) {
  const token = window.sessionStorage.getItem('diguaAiNasToken') || '';
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const response = await fetch(path, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  return response.json();
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);
}
async function refresh() {
  const status = await api('/api/subtitle/status');
  document.querySelector('#status').textContent =
    `backend=${status.backend?.backend || 'unknown'} real_asr=${Boolean(status.backend?.real_asr)} transcripts=${status.transcript_count || 0} degraded=${Boolean(status.degraded)} reason=${status.degraded_reason || 'none'}`;
}
document.querySelector('#search').onclick = async () => {
  const query = document.querySelector('#query').value;
  const data = await api('/api/subtitle/search', { method: 'POST', body: JSON.stringify({ query }) });
  document.querySelector('#results').innerHTML = (data.results || []).map(row => `
    <article class="result"><div>${escapeHtml(row.text_redacted)}</div><div class="meta">${escapeHtml(row.asset_id)} ${escapeHtml(row.start_sec)}-${escapeHtml(row.end_sec)} ${escapeHtml(row.evidence_ref)}</div></article>
  `).join('');
};
refresh();
