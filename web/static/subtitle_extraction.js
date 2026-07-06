async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  return response.json();
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
    <article class="result"><div>${row.text_redacted}</div><div class="meta">${row.asset_id} ${row.start_sec}-${row.end_sec} ${row.evidence_ref}</div></article>
  `).join('');
};
refresh();
