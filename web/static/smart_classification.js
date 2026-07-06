async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  return response.json();
}
async function refresh() {
  const status = await api('/api/smart-classification/status');
  document.querySelector('#status').textContent =
    `categories=${status.category_count || 0} memberships=${status.membership_count || 0} names=${status.smart_name_count || 0} moved=${Boolean(status.physical_file_moved)}`;
  const data = await api('/api/smart-classification/categories');
  document.querySelector('#categories').innerHTML = (data.categories || []).map(category => `
    <article class="card">
      <strong>${category.name_zh || category.name}</strong>
      <div class="meta">${category.item_count || 0} matched assets</div>
      <div class="meta">${category.name_en || ''}</div>
      <pre>${JSON.stringify(category.rule || {}, null, 2)}</pre>
    </article>
  `).join('');
}
document.querySelector('#rebuild').onclick = async () => { await api('/api/smart-classification/rebuild', { method: 'POST', body: '{}' }); refresh(); };
refresh();
