(function () {
  const state = {
    selected: null,
    lastResults: [],
  };

  const els = {
    status: document.getElementById("mm-status"),
    statusText: document.getElementById("mm-status-text"),
    metrics: document.getElementById("mm-metrics"),
    authForm: document.getElementById("mm-auth-form"),
    authState: document.getElementById("mm-auth-state"),
    username: document.getElementById("mm-username"),
    password: document.getElementById("mm-password"),
    form: document.getElementById("mm-search-form"),
    query: document.getElementById("mm-query"),
    modality: document.getElementById("mm-modality"),
    rebuild: document.getElementById("mm-rebuild"),
    results: document.getElementById("mm-results"),
    evidence: document.getElementById("mm-evidence"),
  };

  function setStatus(text, mode) {
    els.statusText.textContent = text;
    els.status.dataset.state = mode || "checking";
  }

  function setAuthState(text) {
    els.authState.textContent = text;
  }

  async function requestJson(url, options) {
    const headers = { "content-type": "application/json", ...authHeaders(), ...(options && options.headers ? options.headers : {}) };
    const response = await fetch(url, {
      ...options,
      headers,
    });
    const payload = await response.json();
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `request_failed_${response.status}`);
    }
    return payload;
  }

  function authHeaders() {
    try {
      const token = window.localStorage.getItem("diguaAiNasToken") || "";
      return token ? { Authorization: `Bearer ${token}` } : {};
    } catch (error) {
      return {};
    }
  }

  function getAuthToken() {
    try {
      return window.localStorage.getItem("diguaAiNasToken") || "";
    } catch (error) {
      return "";
    }
  }

  function saveAuth(token, user) {
    try {
      window.localStorage.setItem("diguaAiNasToken", token || "");
      if (user) window.localStorage.setItem("diguaAiNasUser", JSON.stringify(user));
    } catch (error) {
      return false;
    }
    return true;
  }

  function renderMetrics(payload) {
    const status = payload.status || payload;
    const counts = status.counts || {};
    const labels = [
      ["Indexed", status.indexed_count || 0],
      ["Embeddings", status.embedding_count || 0],
      ["Raw paths", status.raw_path_rows || 0],
      ["Cloud", status.cloud_used ? "used" : "off"],
      ["OCR", status.feature_flags && status.feature_flags.ocr_enabled ? "on" : "off"],
      ["Video content", status.feature_flags && status.feature_flags.video_keyframe_enabled ? "on" : "metadata"],
      ["Audio ASR", status.feature_flags && status.feature_flags.audio_transcript_enabled ? "on" : "metadata"],
    ];
    Object.keys(counts)
      .sort()
      .forEach((key) => labels.push([key, counts[key]]));
    els.metrics.innerHTML = labels.map(([name, value]) => `<span class="mm-pill">${escapeHtml(name)}: ${escapeHtml(String(value))}</span>`).join("");
  }

  function renderResults(results) {
    state.lastResults = results || [];
    state.selected = state.lastResults[0] || null;
    if (!state.lastResults.length) {
      els.results.innerHTML = '<div class="mm-empty">No matching local evidence</div>';
      renderEvidence(null);
      return;
    }
    els.results.innerHTML = state.lastResults.map(renderResultRow).join("");
    els.results.querySelectorAll("[data-result-index]").forEach((node) => {
      node.addEventListener("click", () => {
        const index = Number(node.dataset.resultIndex);
        state.selected = state.lastResults[index] || null;
        renderEvidence(state.selected);
      });
    });
    renderEvidence(state.selected);
  }

  function renderResultRow(item, index) {
    const methods = (item.matched_by || []).map((method) => `<span class="mm-tag">${escapeHtml(method)}</span>`).join("");
    return `
      <article class="mm-result" data-result-index="${index}">
        <div class="mm-rank">${item.rank || index + 1}</div>
        <div>
          <p class="mm-title">${escapeHtml(item.title_redacted || item.asset_id || "asset")}</p>
          <p class="mm-snippet">${escapeHtml(item.snippet_redacted || item.evidence_ref || "")}</p>
        </div>
        <div class="mm-tags">
          <span class="mm-tag">${escapeHtml(item.modality || "unknown")}</span>
          ${methods}
        </div>
      </article>
    `;
  }

  function renderEvidence(item) {
    if (!item) {
      els.evidence.innerHTML = "<dt>State</dt><dd>No selection</dd>";
      return;
    }
    const rows = [
      ["Asset", item.asset_id],
      ["Evidence", item.evidence_ref],
      ["Modality", item.modality],
      ["Score", item.score],
      ["Matched by", (item.matched_by || []).join(", ")],
      ["Path hash", item.path_hash],
      ["Privacy", item.privacy_level],
    ];
    els.evidence.innerHTML = rows.map(([name, value]) => `<dt>${escapeHtml(name)}</dt><dd>${escapeHtml(String(value || ""))}</dd>`).join("");
  }

  async function refreshStatus() {
    try {
      const payload = await requestJson("/api/multimodal-search/status");
      renderMetrics(payload);
      setStatus(payload.degraded ? "Ready with limits" : "Ready", payload.ok ? "ok" : "error");
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function runSearch(event) {
    event.preventDefault();
    const query = els.query.value.trim();
    if (!query) {
      renderResults([]);
      return;
    }
    setStatus("Searching", "checking");
    try {
      const payload = await requestJson("/api/multimodal-search/query", {
        method: "POST",
        body: JSON.stringify({ query, modality: els.modality.value, top_k: 10 }),
      });
      renderResults(payload.results || []);
      setStatus(payload.degraded ? "Results with limits" : "Results ready", payload.ok ? "ok" : "error");
    } catch (error) {
      setStatus(error.message, "error");
      if (error.message === "auth_required") setAuthState("Login required");
      renderResults([]);
    }
  }

  async function rebuildIndex() {
    els.rebuild.disabled = true;
    setStatus("Rebuilding", "checking");
    try {
      const payload = await requestJson("/api/multimodal-index/rebuild", {
        method: "POST",
        body: JSON.stringify({ max_files: 5000 }),
      });
      renderMetrics({ indexed_count: payload.indexed_assets, embedding_count: payload.image_embeddings, counts: payload.counts, cloud_used: false, raw_path_rows: 0 });
      setStatus("Index rebuilt", "ok");
    } catch (error) {
      setStatus(error.message, "error");
      if (error.message === "auth_required") setAuthState("Login required");
    } finally {
      els.rebuild.disabled = false;
    }
  }

  async function login(event) {
    event.preventDefault();
    const username = els.username.value.trim();
    const password = els.password.value;
    if (!username || !password) {
      setAuthState("Missing credentials");
      return;
    }
    setAuthState("Logging in");
    try {
      const payload = await requestJson("/api/identity/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
        headers: { "content-type": "application/json" },
      });
      const token = payload.token || (payload.data && payload.data.token) || "";
      const user = payload.user || (payload.data && payload.data.user) || { username };
      if (!token) throw new Error("token_missing");
      saveAuth(token, user);
      els.password.value = "";
      setAuthState(`Signed in: ${username}`);
      setStatus("Ready", "ok");
    } catch (error) {
      setAuthState(error.message);
      setStatus(error.message, "error");
    }
  }

  function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (char) => {
      const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
      return map[char] || char;
    });
  }

  els.form.addEventListener("submit", runSearch);
  els.authForm.addEventListener("submit", login);
  els.rebuild.addEventListener("click", rebuildIndex);
  setAuthState(getAuthToken() ? "Signed in" : "Local session");
  renderResults([]);
  refreshStatus();
})();
