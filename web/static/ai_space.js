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

function renderStatus(data) {
  document.querySelector('#status').textContent =
    `assets=${data.asset_count || 0} evidence=${data.evidence_count || 0} degraded=${Boolean(data.degraded)} reason=${data.degraded_reason || 'none'}`;
}

function renderCards(items) {
  document.querySelector('#cards').innerHTML = items.map(item => `
    <article class="card">
      <strong>${escapeHtml(item.display_name_zh || item.title_redacted || item.asset_id)}</strong>
      <div class="meta">${escapeHtml(item.modality)} / ${escapeHtml(item.asset_kind)} / ${escapeHtml(item.privacy_level)}</div>
      ${item.suggested_filename_zh ? `<div class="meta">${escapeHtml(item.suggested_filename_zh)}</div>` : ''}
      <div class="tags">${[...(item.object_labels || []), ...(item.person_attrs || []), ...(item.category_names || [])].slice(0, 8).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>
      <p>${escapeHtml(item.summary_redacted || '')}</p>
      <div class="meta">${escapeHtml((item.evidence_refs || []).join(', '))}</div>
    </article>
  `).join('');
}

async function refresh() {
  renderStatus(await api('/api/ai-space/status'));
  const facets = await api('/api/ai-space/facets');
  document.querySelector('#facets').textContent = JSON.stringify(facets.facets || {}, null, 2);
  const assets = await api('/api/ai-space/assets');
  renderCards(assets.assets || []);
}

document.querySelector('#rebuild').onclick = async () => { await api('/api/ai-space/rebuild', { method: 'POST', body: '{}' }); refresh(); };
document.querySelector('#search').onclick = async () => {
  const query = document.querySelector('#query').value;
  const result = await api('/api/ai-space/search', { method: 'POST', body: JSON.stringify({ query }) });
  renderCards(result.results || []);
};
refresh();
