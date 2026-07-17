(function () {
  "use strict";

  const app = document.getElementById("app");
  const MEDIA_UPLOAD_MAX_BYTES = 5 * 1024 * 1024;
  const EXECUTION_BOUNDARY_IMPLEMENTATION = "Harness / allowlist dispatcher";
  let assistantRequestSerial = 0;

  const icons = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-7h6v7"/>',
    assistant: '<path d="M12 3v3"/><path d="M12 18v3"/><path d="M3 12h3"/><path d="M18 12h3"/><path d="m5.6 5.6 2.1 2.1"/><path d="m16.3 16.3 2.1 2.1"/><path d="m18.4 5.6-2.1 2.1"/><path d="m7.7 16.3-2.1 2.1"/><circle cx="12" cy="12" r="3.5"/>',
    files: '<path d="M3 7.5h6l2 2H21v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 7.5V5a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v2.5"/>',
    docs: '<path d="M7 3h7l4 4v14H7Z"/><path d="M14 3v5h5"/><path d="M9.5 12h5"/><path d="M9.5 16h7"/>',
    journal: '<path d="M6 3h11a2 2 0 0 1 2 2v16H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M8 7h7"/><path d="M8 11h7"/><path d="M8 15h4"/>',
    audit: '<path d="M5 4h14v16H5Z"/><path d="M8 8h8"/><path d="M8 12h8"/><path d="M8 16h5"/><path d="M16 18l2 2 4-4"/>',
    media: '<path d="M4 5h16v14H4Z"/><circle cx="9" cy="10" r="2"/><path d="m4 17 4.5-4.5 3 3L14 13l6 6"/>',
    backup: '<path d="M5 12a7 7 0 1 0 2-5"/><path d="M5 4v5h5"/><path d="M12 8v5l3 2"/>',
    settings: '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="M4 12h2"/><path d="M18 12h2"/><path d="m6 6 1.4 1.4"/><path d="m16.6 16.6L18 18"/><path d="m18 6-1.4 1.4"/><path d="m7.4 16.6L6 18"/>',
    bell: '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.4 2.4 0 0 1 4.5 1.2c0 1.7-2.3 2-2.3 3.8"/><path d="M12 17.4v.1"/>',
    chevron: '<path d="m9 18 6-6-6-6"/>',
    plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
    minus: '<path d="M5 12h14"/>',
    zoomIn: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/><path d="M11 8v6"/><path d="M8 11h6"/>',
    zoomOut: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/><path d="M8 11h6"/>',
    fit: '<path d="M4 9V4h5"/><path d="M20 9V4h-5"/><path d="M4 15v5h5"/><path d="M20 15v5h-5"/>',
    rotate: '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 3v6h-6"/>',
    upload: '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    filter: '<path d="M4 6h16"/><path d="M7 12h10"/><path d="M10 18h4"/>',
    save: '<path d="M5 3h12l2 2v16H5Z"/><path d="M8 3v6h8"/><path d="M8 21v-7h8v7"/>',
    download: '<path d="M12 4v12"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/>',
    copy: '<path d="M8 8h11v11H8Z"/><path d="M5 16H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v1"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.1-1.1"/>',
    table: '<path d="M4 5h16v14H4Z"/><path d="M4 10h16"/><path d="M10 5v14"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    alert: '<path d="M12 4 3 20h18Z"/><path d="M12 9v5"/><path d="M12 17.5v.1"/>',
    lock: '<path d="M6 10h12v10H6Z"/><path d="M8 10V8a4 4 0 0 1 8 0v2"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 15h10l1-15"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    calendar: '<path d="M5 4h14v16H5Z"/><path d="M8 2v4"/><path d="M16 2v4"/><path d="M5 9h14"/>',
    menu: '<path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/>'
  };

  const navItems = [
    { id: "dashboard", label: "首页", icon: "home" },
    { id: "assistant", label: "AI 助手", icon: "assistant" },
    { id: "files", label: "文件", icon: "files" },
    { id: "reports", label: "报告", icon: "table" },
    { id: "tokenBudget", label: "Token", icon: "calendar" },
    { id: "agentRuntime", label: "运行", icon: "assistant" },
    { id: "media", label: "相册", icon: "media" },
    { id: "backup", label: "备份同步", icon: "backup" },
    { id: "journal", label: "笔记", icon: "journal" },
    { id: "audit", label: "审计", icon: "audit" },
    { id: "settings", label: "设置", icon: "settings" }
  ];

  const navGroups = [
    { label: "常用", ids: ["dashboard", "assistant", "files", "media", "backup"] },
    { label: "内容", ids: ["reports", "journal"] },
    { label: "系统与记录", ids: ["tokenBudget", "agentRuntime", "audit", "settings"] }
  ];

  const mobilePrimaryNavIds = ["dashboard", "assistant", "files", "media"];

  const appState = {
    page: getInitialPage(),
    fileViewMode: "explorer",
    docClassification: { status: "idle", items: [], categories: {}, categoryCounts: {}, selectedCategory: "", error: "" },
    debugStatePanels: new URLSearchParams(window.location.search).get("debugStates") === "1",
    prompt: "",
    selectedFile: "",
    fileSearch: "",
    selectedDoc: "whitepaper",
    selectedAuditRecord: "",
    toast: "",
    workflow: { open: false, title: "", body: "", tone: "neutral" },
    imageViewer: { open: false, title: "", meta: "", match: "", previewUrl: "", objectUrl: "", status: "idle", error: "", requestId: "", zoom: 1, rotation: 0, offsetX: 0, offsetY: 0 },
    loading: false,
    authToken: safeLocalStorageGet("diguaAiNasToken"),
    authUser: safeJsonParse(safeLocalStorageGet("diguaAiNasUser"), null),
    csrfToken: "",
    storage: {
      status: "idle",
      relativePath: "",
      parent: "",
      root: "",
      entries: [],
      rootFolders: [],
      error: "",
      message: ""
    },
    storageOperation: { type: "", status: "idle", result: null, error: "" },
    health: { status: "loading", text: "读取本地服务状态" },
    assistant: { status: "idle", answer: "", route: null, error: "" },
    documents: { status: "idle", path: "Documents", query: "地瓜 AI-NAS", items: [], answer: null, error: "" },
    reports: { status: "idle", items: [], selectedId: "", export: null, error: "" },
    tokenBudget: { status: "idle", summary: null, benchmark: null, trace: null, error: "" },
    agentRuntime: { status: "idle", statusPayload: null, manifest: null, memory: null, multimodal: null, evalStatus: null, contextPack: null, error: "" },
    dashboard: { status: "idle", storage: null, token: null, audit: null, runtime: null, error: "" },
    journal: { status: "loading", text: "读取日记索引", events: [], summary: null, export: null, error: "" },
    audit: { status: "idle", operations: [], error: "", query: "" },
    media: { status: "idle", summary: null, error: "", selectedAlbumName: "", selectedAlbumStatus: "idle", selectedAlbumPhotos: [], selectedAlbumError: "", uploadStatus: "idle", uploadError: "" },
    aiAlbum: {
      status: "idle",
      error: "",
      statusPayload: null,
      facets: null,
      assets: [],
      mediaPhotos: [],
      smartCategories: [],
      autoStatus: null,
      autoOrganize: null,
      autoOrganizeStatus: "idle",
      organizeStatus: null,
      organizeRunStatus: "idle",
      organizeLastRun: null,
      organizeError: "",
      activeTab: "all",
      selectedCategory: "",
      selectedAssetId: "",
      query: "",
      searchStatus: "idle",
      searchResults: null,
      searchError: "",
      blockedQuery: null,
      planStatus: "idle",
      planResult: null,
      planError: ""
    },
    backup: { status: "idle", summary: null, error: "", taskName: "本地备份任务" },
    settings: { status: "idle", storage: null, users: [], harness: null, token: null, error: "" },
    copy: { target: "", status: "idle", result: null, approvalPhrase: "", signedToken: null, rollbackManifestPath: "", manifestId: "" },
    trash: { status: "idle", pending: null, error: "" }
  };
  let backupCreatePromise = null;
  const previewObjectUrlCache = new Map();
  const previewObjectPromiseCache = new Map();
  let imageViewerDrag = null;
  let aiAlbumSelectTimer = null;
  let previewLazyObserver = null;
  const previewHydrationQueue = [];
  let previewHydrationActive = 0;
  const PREVIEW_HYDRATION_CONCURRENCY = 4;

  function safeLocalStorageGet(key) {
    try {
      window.localStorage.removeItem(key);
      return window.sessionStorage.getItem(key) || "";
    } catch (error) {
      return "";
    }
  }

  function safeLocalStorageSet(key, value) {
    try {
      window.localStorage.removeItem(key);
      window.sessionStorage.setItem(key, value);
    } catch (error) {
      return false;
    }
    return true;
  }

  function safeLocalStorageRemove(key) {
    try {
      window.localStorage.removeItem(key);
      window.sessionStorage.removeItem(key);
    } catch (error) {
      return false;
    }
    return true;
  }

  function clearProductSession() {
    appState.authToken = "";
    appState.authUser = null;
    appState.csrfToken = "";
    appState.selectedFile = "";
    appState.storage = { ...appState.storage, status: "auth", entries: [], rootFolders: [], error: "" };
    safeLocalStorageRemove("diguaAiNasToken");
    safeLocalStorageRemove("diguaAiNasUser");
  }

  function safeJsonParse(value, fallback) {
    if (!value) return fallback;
    try {
      return JSON.parse(value);
    } catch (error) {
      return fallback;
    }
  }

  function svg(name, className = "") {
    return `<svg class="${className}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.help}</svg>`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function getInitialPage() {
    const hash = window.location.hash.replace("#", "");
    if (hash === "documents") return "files";
    if (navItems.some((item) => item.id === hash)) return hash;
    const routePageMap = {
      "/ai-album": "media"
    };
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    const routePage = routePageMap[path];
    return routePage && navItems.some((item) => item.id === routePage) ? routePage : "dashboard";
  }

  function badge(text, type = "neutral") {
    return `<span class="badge ${type}">${escapeHtml(text)}</span>`;
  }

  function iconButton(iconName, label, extra = "") {
    const attr = extra.trim().startsWith("<") ? "" : extra;
    const inner = extra.trim().startsWith("<") ? extra : "";
    return `<button class="icon-button" type="button" aria-label="${escapeHtml(label)}" ${attr}>${svg(iconName)}${inner}</button>`;
  }

  function storageTrashAttrs(payload = {}) {
    const relativePath = payload.relativePath || payload.relative_path || "";
    const pathHash = payload.pathHash || payload.path_hash || "";
    if (!relativePath && !pathHash) return "";
    return [
      'data-action="storageTrashPrompt"',
      `data-trash-kind="${escapeHtml(payload.kind || "file")}"`,
      `data-trash-title="${escapeHtml(payload.title || "file")}"`,
      relativePath ? `data-trash-relative-path="${escapeHtml(relativePath)}"` : "",
      pathHash ? `data-trash-path-hash="${escapeHtml(pathHash)}"` : "",
      payload.previewUrl ? `data-trash-preview-url="${escapeHtml(payload.previewUrl)}"` : ""
    ].filter(Boolean).join(" ");
  }

  function storageTrashButton(payload = {}) {
    const attrs = storageTrashAttrs(payload);
    if (!attrs) return "";
    const title = payload.title || "file";
    return `<button class="icon-button trash-button" type="button" title="移入回收站" aria-label="移入回收站 ${escapeHtml(title)}" ${attrs}>${svg("trash")}</button>`;
  }

  function button(label, options = {}) {
    const variant = options.variant ? ` ${options.variant}` : "";
    const icon = options.icon ? svg(options.icon) : "";
    const disabled = options.disabled ? " disabled" : "";
    const action = options.action ? ` data-action="${escapeHtml(options.action)}"` : "";
    const page = options.page ? ` data-page="${escapeHtml(options.page)}"` : "";
    return `<button class="btn${variant}" type="button"${disabled}${action}${page}>${icon}${escapeHtml(label)}</button>`;
  }

  function card(content, className = "") {
    return `<section class="card ${className}">${content}</section>`;
  }

  function sectionTitle(title, actionText = "", action = "") {
    return `<div class="section-title"><h2>${escapeHtml(title)}</h2>${actionText ? `<button class="link-button" type="button" data-action="${escapeHtml(action)}">${escapeHtml(actionText)} ${svg("chevron")}</button>` : ""}</div>`;
  }

  function renderShell() {
    const page = pages[appState.page] || pages.dashboard;
    app.innerHTML = `
      <div class="app-shell">
        ${renderSidebar()}
        <div class="main-area">
          ${renderTopbar()}
          <main id="main-content" class="page" tabindex="-1">
            <div class="page-inner">
              ${page()}
            </div>
          </main>
        </div>
        ${renderBottomNav()}
      </div>
      <div id="toast" class="toast" role="status" aria-live="polite"></div>
      ${renderWorkflowPanel()}
      ${renderImageViewerPanel()}
    `;
    renderToast();
    hydrateAssistantSearchPreviewsV2();
  }

  function renderSidebar() {
    return `
      <aside class="sidebar" aria-label="主导航">
        <div class="brand">
          <span class="brand-mark">${svg("home")}</span>
          <strong>地瓜 AI-NAS</strong>
        </div>
        <nav class="nav-list">
          ${navGroups.map((group) => `
            <div class="nav-section">
              <span class="nav-section-label">${escapeHtml(group.label)}</span>
              ${group.ids.map((id) => navItems.find((item) => item.id === id)).filter(Boolean).map(renderNavItem).join("")}
            </div>
          `).join("")}
        </nav>
        ${renderSidebarStorageCard()}
      </aside>
    `;
  }

  function renderBottomNav() {
    const primaryItems = mobilePrimaryNavIds.map((id) => navItems.find((item) => item.id === id)).filter(Boolean);
    const moreActive = !mobilePrimaryNavIds.includes(appState.page);
    return `<nav class="bottom-nav" aria-label="移动端导航">
      ${primaryItems.map(renderNavItem).join("")}
      <button class="nav-item${moreActive ? " active" : ""}" type="button" data-action="openMobileMore"${moreActive ? ' aria-current="page"' : ""}>${svg("menu")}更多</button>
    </nav>`;
  }

  function renderNavItem(item) {
    const active = item.id === appState.page ? " active" : "";
    const current = item.id === appState.page ? ' aria-current="page"' : "";
    return `<button class="nav-item${active}" type="button" data-page="${item.id}"${current}>${svg(item.icon)}${escapeHtml(item.label)}</button>`;
  }

  function renderSidebarStorageCard() {
    const capacity = appState.dashboard?.storage?.capacity || appState.settings?.storage?.capacity || null;
    const total = Number(capacity?.total_bytes || 0);
    const used = Number(capacity?.used_bytes || 0);
    const percent = total > 0 ? Math.min(100, Math.max(0, Math.round((used / total) * 100))) : null;
    if (percent == null) {
      return `<div class="storage-card storage-card-unavailable">
        <span class="storage-card-icon">${svg("backup")}</span>
        <div><strong>存储容量待连接</strong><p>连接 S100P 与 NAS 后读取真实数据</p></div>
      </div>`;
    }
    return `<div class="storage-card">
      <strong>存储空间</strong>
      <div class="progress-track" role="progressbar" aria-label="存储空间使用率" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><div class="progress-fill" style="--value:${percent}%"></div></div>
      <div class="storage-meta"><span>${escapeHtml(formatBytes(used))} / ${escapeHtml(formatBytes(total))}</span><span>${percent}%</span></div>
    </div>`;
  }

  function renderTopbar() {
    const username = appState.authUser?.username || "";
    const userLabel = username || "登录";
    const avatarLabel = username ? username.slice(0, 1).toUpperCase() : "访";
    return `
      <header class="topbar">
        <div class="local-status">${svg("lock")}<span>本地优先</span></div>
        <div class="topbar-actions">
          <button class="icon-button" type="button" aria-label="通知" data-action="openNotifications">${svg("bell")}</button>
          <button class="icon-button" type="button" aria-label="帮助" data-action="openHelp">${svg("help")}</button>
          <button class="user-menu" type="button" aria-label="${username ? "用户菜单" : "登录与身份"}" data-action="openUserMenu"><span class="avatar">${escapeHtml(avatarLabel)}</span><span>${escapeHtml(userLabel)}</span>${svg("chevron")}</button>
        </div>
      </header>
    `;
  }

  function pageHeader(title, subtitle, actions = "") {
    return `
      <header class="page-header">
        <div class="page-title">
          <h1>${escapeHtml(title)}</h1>
          <p>${escapeHtml(subtitle)}</p>
        </div>
        ${actions ? `<div class="actions">${actions}</div>` : ""}
      </header>
    `;
  }

  function dashboardServiceCards() {
    const dashboard = appState.dashboard || {};
    const token = dashboard.token || appState.tokenBudget.summary || {};
    const analysis = token.latest_analysis || {};
    const storage = dashboard.storage || {};
    const auditOps = Array.isArray(dashboard.audit?.operations) ? dashboard.audit.operations.length : 0;
    const runtime = dashboard.runtime || {};
    return [
      {
        title: "本地网关",
        sub: appState.health.text || "读取服务状态",
        state: appState.health.status === "ok" ? "在线" : "需复查",
        type: appState.health.status === "ok" ? "success" : "warning",
        icon: "assistant",
        tone: "green"
      },
      {
        title: "文件接口",
        sub: appState.authUser?.username ? `已登录：${appState.authUser.username}` : "需要登录后读取 NAS",
        state: appState.authToken ? "已连接" : "待登录",
        type: appState.authToken ? "success" : "neutral",
        icon: "files",
        tone: ""
      },
      {
        title: "Token 路由",
        sub: analysis.average_reduction_ratio != null ? `平均降幅 ${fmtRatio(analysis.average_reduction_ratio)}` : "等待统计数据",
        state: token.ok ? "已读取" : "待读取",
        type: token.ok ? "success" : "neutral",
        icon: "calendar",
        tone: "cyan"
      },
      {
        title: "审计记录",
        sub: auditOps ? `最近 ${fmtCount(auditOps)} 条操作` : "暂无最近操作",
        state: auditOps ? "可查看" : "暂无记录",
        type: auditOps ? "success" : "neutral",
        icon: "audit",
        tone: ""
      },
      {
        title: "运行层",
        sub: runtime.ok ? "上下文、索引和评测接口在线" : "高级能力按需读取",
        state: runtime.ok ? "在线" : "待刷新",
        type: runtime.ok ? "success" : "neutral",
        icon: "settings",
        tone: "purple"
      }
    ];
  }

  function dashboardOperations() {
    const rows = Array.isArray(appState.dashboard?.audit?.operations) ? appState.dashboard.audit.operations : [];
    return rows.slice(0, 5);
  }

  function renderDashboardOperations() {
    const rows = dashboardOperations();
    if (!rows.length) {
      return `<div class="empty-state compact">${svg("audit")} 暂无最近操作。通过文件、助手、备份或笔记执行本地动作后会在这里显示。</div>`;
    }
    return `<div class="task-list">${rows.map((row) => {
      const status = String(row.status || "").includes("disabled") || String(row.status || "").includes("denied") ? "已拒绝" : (row.status || "已记录");
      const tone = status === "已拒绝" ? "danger" : "success";
      return `<div class="task-row"><span class="task-icon">${svg("audit")}</span><div><span class="task-title">${escapeHtml(row.action || row.operation || "本地操作")}</span><div class="muted small">${escapeHtml(row.source || row.source_path || row.target || row.target_path || "本地审计记录")}</div></div><span class="muted small">${escapeHtml(row.created_at || row.ts || "最近")}</span>${badge(status, tone)}</div>`;
    }).join("")}</div>`;
  }

  function renderDashboardTokenOverview() {
    const token = appState.dashboard?.token || appState.tokenBudget.summary || {};
    const benchmark = appState.tokenBudget.benchmark?.benchmark_summary || appState.tokenBudget.benchmark || {};
    const analysis = token.latest_analysis || {};
    if (!token.ok && !Object.keys(analysis).length) {
      return `<div class="empty-state compact">${svg("calendar")} Token Budget 统计尚未读取。进入 Token 页面可刷新真实统计。</div>`;
    }
    return `
      <div class="token-stats">
        <div class="metric"><span class="muted small">平均降幅</span><strong>${escapeHtml(fmtRatio(analysis.average_reduction_ratio))}</strong><span class="small muted">云端输入 token</span></div>
        <div class="metric"><span class="muted small">质量通过率</span><strong>${escapeHtml(fmtRatio(analysis.quality_pass_rate))}</strong><span class="small muted">本地评测</span></div>
        <div class="metric"><span class="muted small">隐私检查</span><strong>${fmtCount(analysis.private_leak_count)}</strong><span class="small muted">检测到的泄漏项</span></div>
      </div>
      ${renderKeyValueRows([
        ["分词器", token.tokenizer_identity?.tokenizer_name || token.tokenizer_identity?.source || "Qwen 分词器"],
        ["评测用例", benchmark.case_count || benchmark.total_cases || "待读取"],
        ["云端默认外发", "禁止"]
      ])}
    `;
  }

  function dashboardPage() {
    const services = dashboardServiceCards();
    const username = appState.authUser?.username || "";
    const storageReady = Boolean(appState.dashboard?.storage?.capacity?.total_bytes);
    const healthReady = appState.health.status === "ok";
    const connectionTitle = storageReady && healthReady ? "本地服务已读取" : healthReady ? "设备已就绪" : "设备状态待连接";
    const connectionDetail = storageReady ? "已读取真实存储容量" : healthReady ? "登录后读取 NAS 容量与个人空间" : "连接 S100P 与 NAS 后显示容量和服务状态";
    return `
      <h1 class="sr-only">首页</h1>
      ${card(`
        <div class="dashboard-welcome-copy">
          <span class="eyebrow">本地优先 · 隐私保护</span>
          <h2>${username ? `你好，${escapeHtml(username)}` : "欢迎使用地瓜 AI-NAS"}</h2>
          <p>从常用任务开始。设备离线时保留页面与操作入口，不用演示数据冒充真实状态。</p>
        </div>
        <div class="dashboard-connection" aria-label="当前连接摘要">
          <span class="connection-icon">${svg(storageReady && healthReady ? "check" : "link")}</span>
          <div>
            <strong>${connectionTitle}</strong>
            <span>${connectionDetail}</span>
          </div>
        </div>
      `, "dashboard-welcome")}
      <div class="section-heading"><div><span class="eyebrow">常用任务</span><h2>现在想做什么？</h2></div></div>
      <div class="grid quick-grid">
        ${quickCard("新建对话", "与 AI 助手开始对话", "assistant", "assistant")}
        ${quickCard("浏览文件", "查看个人空间与文件分类", "files", "files")}
        ${quickCard("整理相册", "查看图片与本地 AI 分类", "media", "media")}
        ${quickCard("备份同步", "管理本地备份任务", "backup", "backup")}
      </div>
      <div class="grid two-col">
        ${card(`${sectionTitle("最近本地操作", "查看审计", "dashboardTasks")}${renderDashboardOperations()}`)}
        ${card(`${sectionTitle("连接与身份")}${renderKeyValueRows([
          ["本地接口", healthReady ? "已读取" : "待连接"],
          ["S100P / NAS", storageReady ? "已读取真实容量" : healthReady ? "设备在线，容量需登录" : "当前未连接"],
          ["文件身份", appState.authToken ? "当前浏览器已登录" : "尚未登录"],
          ["数据展示", "只显示接口真实返回"]
        ])}`, "connection-card")}
      </div>
      <details class="card system-overview">
        <summary><span>${svg("settings")}系统状态与技术信息</span><span class="muted small">按需展开</span></summary>
        <div class="system-overview-body">
          <div class="grid status-grid">
            ${services.map((item) => `
              <div class="status-card">
                <span class="icon-chip ${item.tone}">${svg(item.icon)}</span>
                <div><strong>${escapeHtml(item.title)}</strong><div class="muted small">${escapeHtml(item.sub)}</div><div class="status-card-badge">${badge(item.state, item.type)}</div></div>
              </div>
            `).join("")}
          </div>
          <div class="system-token-overview">${sectionTitle("Token / 路由概览", "查看详情", "tokenDetails")}${renderDashboardTokenOverview()}</div>
        </div>
      </details>
      ${renderStatePanel("首页")}
    `;
  }

  function quickCard(title, desc, icon, page) {
    return `<button class="quick-card" type="button" data-page="${page}"><span class="icon-chip">${svg(icon)}</span><span><strong>${escapeHtml(title)}</strong><span>${escapeHtml(desc)}</span></span></button>`;
  }

  function assistantEvidencePanel() {
    const copilot = appState.assistant.copilot || {};
    const searchResults = Array.isArray(copilot.search?.results) ? copilot.search.results : [];
    const evidence = Array.isArray(copilot.evidence) ? copilot.evidence : [];
    if (searchResults.length) {
      return searchResults.slice(0, 4).map((item, index) => {
        const display = item.display || {};
        const typeLabel = display.type_label || (item.modality === "image" ? "照片" : "结果");
        return `<div class="mini-row"><span>${svg(item.preview_kind === "image" ? "media" : "files")} ${escapeHtml(productResultTitle(item, index, typeLabel))}</span><span class="muted small">${escapeHtml(display.match_score_label || "本地")}</span></div>`;
      }).join("");
    }
    if (evidence.length) {
      return evidence.slice(0, 4).map((item, index) => `<div class="mini-row"><span>${svg("docs")} ${escapeHtml(displayName(item, "文档证据"))}</span><span class="muted small">${escapeHtml(evidenceLabel(item, index))}</span></div>`).join("");
    }
    return `<article class="manual-note">发送问题后，这里只显示真实返回的本地证据。没有证据时不会用样例文件补齐。</article>`;
  }

  function assistantLocalToolsPanel() {
    const tools = [
      ["找有人的图片", "本地 YOLO 相册检索", "media"],
      ["总结 Documents 文档", "本地文档问答", "docs"],
      ["列出文件列表", "权限感知文件浏览", "files"],
      ["查看存储状态", "本地容量和索引概览", "settings"]
    ];
    return tools.map(([title, desc, icon]) => `<div class="mini-row"><span>${svg(icon)} ${escapeHtml(title)}</span><span class="muted small">${escapeHtml(desc)}</span></div>`).join("");
  }

  function assistantRoutePanel() {
    const copilot = appState.assistant.copilot || {};
    const router = copilot.qwen_router || {};
    const routeMeta = copilot.qwen_router || appState.assistant.route || {};
    const action = copilot.nas_action || {};
    const mode = String(copilot.assistant_mode || appState.assistant.mode || "").toLowerCase();
    const responseRoute = String(copilot.route || "").toLowerCase();
    const answerText = String(appState.assistant.answer || copilot.answer || "");
    const modeToolId = mode.startsWith("local_storage") ? "local_storage" : mode === "local_document_query" ? "local_document_rag" : mode === "local_yolo_search" || mode === "local_multimodal_search" ? "local_multimodal_search" : mode === "local_ai_album_category_search" ? "ai_album_primary_category" : "";
    const responseRouteToolId = responseRoute.startsWith("local_storage") ? "local_storage" : responseRoute.includes("document") ? "local_document_rag" : responseRoute.includes("yolo") || responseRoute.includes("multimodal") ? "local_multimodal_search" : responseRoute.includes("album") ? "ai_album_primary_category" : "";
    const answerToolId = answerText.includes("只读盘点") || answerText.includes("文件盘点") || answerText.includes("顶层条目") ? "local_storage_inventory" : "";
    const actionToolId = {
      inventory: "local_storage_inventory",
      list: "local_storage_list",
      inspect: "local_storage_inspect",
      storage_status: "local_storage_status",
      media_summary: "local_media_summary",
      audit_summary: "local_audit_summary",
      reports_list: "local_reports_list",
      document_query: "local_document_rag"
    }[action.operation] || "";
    const toolId = answerToolId || responseRouteToolId || modeToolId || actionToolId || router.local_tool_id || copilot.search?.retrieval_mode || "";
    return renderKeyValueRows([
      ["处理位置", copilot.cloud_used ? "受控云端" : "S100P 本地"],
      ["隐私级别", privacyLabel(routeMeta.privacy_level || "local_only")],
      ["本地工具", appState.assistant.toolLabel || localToolLabel(toolId) || "按问题判断"],
      ["云端调用", copilot.cloud_used ? "已调用" : "未调用"]
    ]);
  }

  function assistantToolLabelFromCopilot(copilot) {
    const mode = String(copilot?.assistant_mode || "").toLowerCase();
    const route = String(copilot?.route || "").toLowerCase();
    const action = copilot?.nas_action || {};
    if (mode.startsWith("local_storage") || route.startsWith("local_storage") || ["inventory", "list", "inspect", "storage_status"].includes(action.operation)) return "本地文件服务";
    if (mode === "local_ai_album_category_search" || route.includes("album_primary")) return "本地相册分类检索";
    if (mode === "local_yolo_search" || mode === "local_multimodal_search" || route.includes("yolo") || route.includes("multimodal")) return "本地多模态检索";
    if (mode === "local_document_query" || route.includes("document") || action.operation === "document_query") return "本地文档问答";
    if (route.includes("audit") || action.operation === "audit_summary") return "本地审计查询";
    if (route.includes("report") || action.operation === "reports_list") return "本地报告查询";
    return "";
  }

  function assistantPage() {
    const hasAnswer = appState.assistant.status === "ready" && Boolean(String(appState.assistant.answer || "").trim());
    return `
      ${pageHeader("AI 助手", "基于本地知识库为您答疑、总结与创作，保护隐私安全。", button("使用指南", { variant: "secondary", action: "assistantGuide" }))}
      <div class="layout-with-panel">
        <section>
          ${card(`
            <textarea id="assistantPrompt" class="textarea" placeholder="请输入您的问题、指令或需求..." aria-label="AI 助手输入">${escapeHtml(appState.prompt)}</textarea>
            <div class="prompt-footer">
              <div class="actions">
                <span class="service-pill strong">${svg("assistant")} 模型由 Workspace Harness 自动选择</span>
                ${button("附件", { variant: "tertiary", icon: "link", action: "assistantAttach" })}
              </div>
              ${button("发送", { icon: "send", action: "sendPrompt", disabled: !appState.prompt.trim() })}
            </div>
          `, "prompt-card")}
          <div class="chips">
            ${["找出有人的照片", "总结文档里的发票内容", "列出文件列表", "查看存储状态"].map((text) => `<button class="chip" type="button" data-prompt="${escapeHtml(text)}">${escapeHtml(text)}</button>`).join("")}
          </div>
          ${renderAssistantAnswer()}
          ${hasAnswer ? `<div class="actions assistant-followups">
            ${button("继续追问", { variant: "secondary", icon: "assistant", action: "assistantContinue" })}
            ${button("提炼要点", { variant: "secondary", icon: "docs", action: "assistantKeyPoints" })}
            ${button("生成思维导图", { variant: "secondary", icon: "table", action: "assistantMindmap" })}
            ${button("导出为文档", { variant: "secondary", icon: "download", action: "assistantExport" })}
          </div>` : ""}
          ${renderStatePanel("AI 助手")}
        </section>
        <aside class="side-stack">
          ${contextPanel("本次证据", assistantEvidencePanel(), "查看详情", "assistantEvidenceSources")}
          <details class="card assistant-context-details">
            <summary><span>${svg("lock")}处理与隐私信息</span>${svg("chevron")}</summary>
            <div class="assistant-context-body">
              ${hasAnswer ? assistantRoutePanel() : '<p class="muted small">完成一次回答后，这里显示实际处理位置、隐私级别与工具调用情况。</p>'}
              <button class="link-button" type="button" data-action="assistantTrace"${hasAnswer ? "" : " disabled"}>查看处理详情</button>
            </div>
          </details>
        </aside>
      </div>
    `;
  }

  function renderAssistantAnswer() {
    if (appState.assistant.status === "loading") {
      return card(`<div class="answer-header"><strong>${svg("assistant")} AI 助手回答</strong>${badge("正在本地路由", "neutral")}</div><div class="skeleton-list"><span></span><span></span><span></span></div>`, "answer-card");
    }
    if (appState.assistant.status === "auth") {
      return card(authNotice("AI 助手"), "answer-card");
    }
    if (appState.assistant.status === "error") {
      return card(`<div class="answer-header"><strong>${svg("assistant")} AI 助手回答</strong>${badge("失败", "danger")}</div><div class="empty-state">${svg("alert")}<strong>请求失败</strong><p>${escapeHtml(appState.assistant.error || "copilot_failed")}</p></div>`, "answer-card");
    }
    if (appState.assistant.status !== "ready") {
      return card(`
        <div class="answer-header"><strong>${svg("assistant")} AI 助手回答</strong>${badge("等待输入", "neutral")}</div>
        <div class="answer-body"><p>连接设备并输入自然语言后，网页会在 S100P 本地完成理解、隐私判断和必要的工具路由，再展示真实结果摘要。</p></div>
      `, "answer-card");
    }
    const route = appState.assistant.route || {};
    const copilot = appState.assistant.copilot || {};
    const mode = appState.assistant.mode || copilot.assistant_mode || "";
    const search = copilot.search || null;
    const qwenRouter = copilot.qwen_router || null;
    const isAssistantAnswer = Boolean(mode && appState.assistant.answer);
    const answerBadge = mode === "local_qwen_chat" ? "本地 Qwen 返回" : mode === "cloud_overflow_chat" ? "云端返回" : mode === "cloud_overflow_stub" ? "云端未配置" : mode === "local_yolo_search" || mode === "local_multimodal_search" || mode === "local_ai_album_category_search" ? "本地检索返回" : mode.startsWith("local_storage") ? "本地文件返回" : mode === "local_document_query" ? "本地文档返回" : "本地服务返回";
    return card(`
      <div class="answer-header"><strong>${svg("assistant")} AI 助手回答</strong>${badge(answerBadge, "success")}</div>
      <div class="answer-body">
        <div class="assistant-text">${renderAssistantText(appState.assistant.answer, mode === "local_qwen_chat" || mode === "cloud_overflow_chat")}</div>
        ${renderAssistantProductResult(copilot, mode)}
        ${isAssistantAnswer ? renderAssistantServiceSummary(copilot, route, qwenRouter, mode) : ""}
        ${isAssistantAnswer ? renderAssistantDetails(copilot, route, qwenRouter, mode) : ""}
      </div>
      <div class="answer-footer">
        <div class="actions">${iconButton("check", "已验证")}${iconButton("copy", "复制")}</div>
        <div class="muted small">Qwen 只负责理解与建议；真实执行仍走受控白名单和本地执行边界。</div>
      </div>
    `, "answer-card");
  }

  function renderAssistantText(text, preserveModelText = false) {
    const safe = (preserveModelText ? String(text || "") : scrubProductText(String(text || ""))).trim();
    if (!safe) return "<p>本地助手没有返回正文。</p>";
    return safe
      .split(/\n{2,}/)
      .map((part) => `<p>${escapeHtml(part).replace(/\n/g, "<br>")}</p>`)
      .join("");
  }

  function renderQwenRouter(router) {
    if (!router || typeof router !== "object") return "";
    return renderKeyValueRows([
      ["处理方式", routeLabel("", router.route || "local")],
      ["隐私级别", router.privacy_level || "none"],
      ["任务复杂度", router.task_complexity || "simple"],
      ["本地工具", localToolLabel(router.local_tool_id)],
      ["判断理由", router.guardrail_reason || router.reason || "已完成本地路由判断"]
    ]);
  }

  function routeLabel(mode, route) {
    if (mode === "local_yolo_search") return "本地图片检索";
    if (mode === "local_multimodal_search") return "本地多模态检索";
    if (mode === "local_ai_album_category_search") return "本地相册分类检索";
    if (mode === "local_document_query") return "本地文档问答";
    if (mode === "local_storage_list") return "本地文件浏览";
    if (mode === "local_storage_inspect") return "本地文件检查";
    if (mode === "local_storage_create_folder") return "新建文件夹";
    if (mode === "local_snapshot_create") return "本地快照";
    if (mode === "local_backup_create_task" || mode === "local_backup_run") return "备份同步";
    if (mode === "local_media_index" || mode === "local_media_summary" || mode === "local_media_create_album") return "媒体库";
    if (mode === "local_journal_summary" || mode === "local_journal_manual_entry") return "本地笔记";
    if (mode === "local_storage_status") return "存储概览";
    if (mode === "local_ops_summary") return "运行健康";
    if (mode === "local_apps_summary") return "应用生态";
    if (mode === "local_audit_summary") return "审计概览";
    if (mode === "local_reports_list") return "报告列表";
    if (mode === "local_qwen_chat") return "本地 Qwen 对话";
    if (mode === "cloud_overflow_chat") return "受控云端处理";
    if (mode === "cloud_overflow_stub") return "云端未配置";
    return route || mode || "本地处理";
  }

  function privacyLabel(value) {
    const normalized = String(value || "").toLowerCase();
    if (normalized === "high" || normalized.includes("private") || normalized === "local_only") return "高 · 留在本地";
    if (normalized === "medium" || normalized === "internal") return "中 · 受限处理";
    if (normalized === "none" || normalized === "public" || normalized === "low") return "普通";
    return value ? String(value) : "本地保护";
  }

  function renderAssistantServiceSummary(copilot, route, qwenRouter, mode) {
    const modelRouting = copilot.model_routing || {};
    const rawTokens = route?.token_counts?.raw_user_prompt_tokens ?? copilot?.usage?.prompt_tokens ?? "暂无";
    const processing = copilot.cloud_used ? "云端" : "S100P 本地";
    const privacy = privacyLabel(qwenRouter?.privacy_level || route?.privacy_level || "local_only");
    const model = modelRouting.effective_answer_model || (mode === "local_ai_album_category_search" ? "本地相册分类索引" : mode === "local_yolo_search" || mode === "local_multimodal_search" ? "本地多模态索引" : copilot.model || "本地策略服务");
    return `
      <div class="assistant-service-summary" aria-label="服务摘要">
        <span class="service-pill strong">${svg("home")} ${escapeHtml(processing)}</span>
        <span class="service-pill">${svg("lock")} ${escapeHtml(privacy)}</span>
        <span class="service-pill">${svg("table")} 输入 ${escapeHtml(rawTokens)} token</span>
        <span class="service-pill">${svg("assistant")} ${escapeHtml(routeLabel(mode, qwenRouter?.route || route?.route))}</span>
        <span class="service-pill muted-pill">${escapeHtml(model)}</span>
      </div>
    `;
  }

  function renderAssistantDetails(copilot, route, qwenRouter, mode) {
    const modelRouting = copilot.model_routing || {};
    const decision = modelRouting.decision || copilot.routing_decision || {};
    const modelCalls = Array.isArray(modelRouting.calls) ? modelRouting.calls : [];
    const selectedTools = Array.isArray(decision.selected_tools) && decision.selected_tools.length
      ? decision.selected_tools.map((tool) => localToolLabel(tool) || tool).join("、")
      : "无";
    const hybridStatus = decision.hybrid_candidate
      ? (decision.hybrid_status === "unsupported_safe_splitter_not_enabled" ? "候选，但安全拆分/脱敏/本地合并链路尚未启用，保持本地" : decision.hybrid_status || "候选")
      : "不适用";
    const rows = [
      ["请求 ID", decision.request_id || copilot.request_id || "暂无"],
      ["策略路由", decision.selected_route || "LOCAL_1_5B"],
      ["处理链路", routeLabel(mode, qwenRouter?.route || route?.route)],
      ["Workspace", modelRouting.selected_workspace || copilot.selected_workspace || "main_router"],
      ["模型策略", modelRouting.policy_id || "workspace_harness_auto_v2"],
      ["用户选择模型", modelRouting.user_selectable === false ? "不允许，由架构自动选择" : "未声明"],
      ["最终回答模型", modelRouting.effective_answer_model || "无额外模型调用"],
      ["处理位置", copilot.cloud_used ? "云端" : "S100P 本地"],
      ["隐私级别", `${decision.privacy_level ?? "暂无"} · ${privacyLabel(decision.privacy_label || qwenRouter?.privacy_level || route?.privacy_level || "local_only")}`],
      ["复杂度", decision.complexity ?? "暂无"],
      ["需要最新信息", decision.freshness_required ? "是" : "否"],
      ["需要公开网络", decision.requires_public_web ? "是" : "否"],
      ["需要本地数据", decision.requires_local_data ? "是" : "否"],
      ["云端外发获准", decision.cloud_egress_allowed ? "是" : "否"],
      ["混合路由", hybridStatus],
      ["写操作风险", decision.write_risk || "none"],
      ["需要确认", decision.confirmation_required ? "是" : "否"],
      ["选中工具", selectedTools],
      ["执行边界", "本地受控工具"],
      ["Qwen 工具执行权", copilot.qwen_execution_authority ? "开启" : "关闭，只做理解和建议"],
      ["输入 token", route?.token_counts?.raw_user_prompt_tokens ?? copilot.usage?.prompt_tokens ?? "暂无"],
      ["脱敏次数", route?.redaction_count ?? 0],
      ["云端调用", copilot.cloud_used ? "是" : "否"]
    ];
    if (modelRouting.selection_reason) rows.push(["选择原因", modelRouting.selection_reason]);
    const reason = qwenRouter?.guardrail_reason || qwenRouter?.reason || route?.reason;
    if (reason) rows.push(["路由说明", reason]);
    const callRows = modelCalls.map((call, index) => [
      `模型调用 ${index + 1} · ${call.stage || "unknown"}`,
      `${call.model || "无模型"} · ${call.provider || "未知 provider"} · ${call.location || "未知位置"} · ${call.purpose || "未说明"} · ${call.status || "unknown"}${Number.isFinite(Number(call.elapsed_ms)) ? ` · ${Number(call.elapsed_ms).toFixed(1)} ms` : ""}`
    ]);
    return `
      <details class="assistant-details">
        <summary>${svg("chevron")} 查看详情</summary>
        ${renderKeyValueRows(rows)}
        ${callRows.length ? `<h4>本次模型调用</h4>${renderKeyValueRows(callRows)}` : '<p class="muted small">本次由确定性本地策略直接回答，没有调用语言模型。</p>'}
      </details>
    `;
  }

  function renderAssistantProductResult(copilot, mode) {
    if (!copilot || typeof copilot !== "object") return "";
    if (copilot.search) {
      const fallback = copilot.fallback_inventory;
      const fallbackSection = fallback && fallback.ok ? renderAssistantStorageInventory({
        nas_action: {
          operation: "inventory",
          status: fallback.status || "completed",
          path: fallback.relative_path || fallback.requested_scope || "",
          entries: Array.isArray(fallback.entries) ? fallback.entries : [],
          summary: fallback.summary || {}
        },
        summary: fallback.summary || {},
        entries: Array.isArray(fallback.entries) ? fallback.entries : []
      }) : "";
      return `${renderAssistantSearchResults(copilot.search)}${fallbackSection}`;
    }
    if (mode === "local_document_query") return renderAssistantDocumentResult(copilot);
    const action = copilot.nas_action || {};
    const operation = String(action.operation || "");
    if (operation === "inventory") return renderAssistantStorageInventory(copilot);
    if (operation === "list") return renderAssistantStorageList(copilot);
    if (operation === "inspect") return renderAssistantOperationCard(copilot, {
      title: "只读文件检查",
      icon: "docs",
      subtitle: action.path || "已完成路径检查",
      rows: [
        ["路径", action.path || "暂无"],
        ["处理方式", "只读检查"],
        ["写入权限", "未授予 Qwen"]
      ],
      tags: ["本地 ACL 已校验", "未上云"]
    });
    if (operation === "mkdir") return renderAssistantOperationCard(copilot, {
      title: "文件夹已创建",
      icon: "files",
      subtitle: action.path || "新建文件夹",
      rows: [["位置", action.path || "暂无"], ["处理方式", "本地受控写入"], ["执行者", "本地受控服务"]],
      tags: ["已写入 NAS", "Qwen 无执行权"]
    });
    if (operation === "snapshot_create") return renderAssistantOperationCard(copilot, {
      title: action.status === "completed" ? "快照已创建" : "快照未完成",
      icon: "save",
      subtitle: action.name || action.path || "本地快照",
      rows: [["快照名", action.name || "暂无"], ["路径", action.path || "暂无"], ["状态", statusLabel(action.status)]],
      tags: ["本地恢复点", "未上云"]
    });
    if (operation === "backup_create_task") return renderAssistantOperationCard(copilot, {
      title: action.status === "completed" ? "备份任务已创建" : "备份任务未完成",
      icon: "backup",
      subtitle: action.name || "本地备份任务",
      rows: [["任务名", action.name || "暂无"], ["来源", action.source || "暂无"], ["目标", action.dest || "暂无"]],
      tags: ["本地任务", "受控写入"]
    });
    if (operation === "backup_run") return renderAssistantOperationCard(copilot, {
      title: action.status === "completed" ? "备份任务已运行" : "备份运行失败",
      icon: "backup",
      subtitle: action.name || "本地备份",
      rows: [["任务名", action.name || "暂无"], ["复制文件", copilot.result?.copied ?? "暂无"], ["状态", statusLabel(action.status)]],
      tags: ["本地执行", "结果已记录"]
    });
    if (operation === "media_index") return renderAssistantMediaIndex(copilot);
    if (operation === "media_create_album") return renderAssistantOperationCard(copilot, {
      title: action.status === "completed" ? "相册已创建" : "相册未创建",
      icon: "media",
      subtitle: action.name || "本地相册",
      rows: [["相册名", action.name || "暂无"], ["状态", statusLabel(action.status)], ["处理位置", "S100P 本地"]],
      tags: ["媒体库", "本地元数据"]
    });
    if (operation === "journal_summary") return renderAssistantJournalSummary(copilot);
    if (operation === "journal_manual_entry") return renderAssistantOperationCard(copilot, {
      title: action.status === "completed" ? "笔记已写入" : "笔记未写入",
      icon: "journal",
      subtitle: copilot.result?.event?.title || "本地笔记",
      rows: [["状态", statusLabel(action.status)], ["处理位置", "本地日记库"], ["云端调用", "否"]],
      tags: ["本地记录", "可审计"]
    });
    if (operation === "storage_status") return renderAssistantStorageStatus(copilot);
    if (operation === "media_summary") return renderAssistantMediaSummary(copilot);
    if (operation === "ops_summary") return renderAssistantOpsSummary(copilot);
    if (operation === "apps_summary") return renderAssistantAppsSummary(copilot);
    if (operation === "audit_summary") return renderAssistantAuditSummary(copilot);
    if (operation === "reports_list") return renderAssistantReportsList(copilot);
    if (operation === "cloud_overflow") return renderAssistantCloudResult(copilot);
    if (operation && operation !== "none") return renderAssistantOperationCard(copilot, {
      title: operationTitle(operation),
      icon: operationIcon(operation),
      subtitle: statusLabel(action.status || "completed"),
      rows: [["操作", operationTitle(operation)], ["状态", statusLabel(action.status)], ["处理位置", copilot.cloud_used ? "云端" : "S100P 本地"]],
      tags: [copilot.cloud_used ? "云端" : "本地", "Qwen 无执行权"]
    });
    return "";
  }

  function renderProductSection(title, subtitle, body, options = {}) {
    const icon = options.icon || "assistant";
    const meta = subtitle ? `<span>${escapeHtml(subtitle)}</span>` : "";
    return `<section class="assistant-product-section">
      <div class="assistant-product-head"><strong>${svg(icon)} ${escapeHtml(title)}</strong>${meta}</div>
      ${body}
    </section>`;
  }

  function renderProductCard(title, meta = "", tags = [], icon = "docs", options = {}) {
    const safeTags = tags.filter(Boolean);
    const documentOpenUrl = options.documentOpenUrl || "";
    const canOpenDocument = Boolean(documentOpenUrl);
    const trashButton = storageTrashButton(options.trashPayload || {});
    const openAttrs = canOpenDocument
      ? ` tabindex="0" role="button" aria-label="双击打开 ${escapeHtml(title || "文档")}" data-document-open-url="${escapeHtml(documentOpenUrl)}" data-document-title="${escapeHtml(options.documentTitle || title || "文档")}" data-document-filename="${escapeHtml(options.documentFileName || title || "document")}"`
      : "";
    return `<article class="product-result-card${canOpenDocument ? " is-openable" : ""}${trashButton ? " has-actions" : ""}"${openAttrs}>
      <span class="product-icon">${svg(icon)}</span>
      <div class="product-result-content">
        <div class="result-title">${escapeHtml(title || "本地结果")}</div>
        ${meta ? `<div class="result-meta">${escapeHtml(meta)}</div>` : ""}
        ${safeTags.length ? `<div class="result-tags">${safeTags.map((tag) => `<span class="result-tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      </div>
      ${trashButton ? `<div class="result-card-actions">${trashButton}</div>` : ""}
    </article>`;
  }

  function renderKpiStrip(items) {
    const visible = items.filter((item) => item && item[1] !== undefined && item[1] !== null && item[1] !== "");
    if (!visible.length) return "";
    return `<div class="assistant-kpi-strip">${visible.map(([label, value]) => `<div class="assistant-kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>`;
  }

  function renderAssistantDocumentResult(copilot) {
    const evidence = Array.isArray(copilot.evidence) ? copilot.evidence : [];
    const kpis = renderKpiStrip([
      ["召回证据", copilot.evidence_count ?? evidence.length],
      ["可读文档", copilot.readable_count],
      ["检索方式", copilot.retrieval_mode || "本地 FTS"]
    ]);
    const body = `${kpis}<div class="product-card-list">${
      evidence.length
        ? evidence.slice(0, 5).map((item) => renderProductCard(
            displayName(item, "文档片段"),
            item.snippet || item.summary || "本地索引返回摘要，原文保留在 NAS。",
            [item.extension || fileType(item) || "文档", evidenceLabel(item), "本地保留", documentOpenUrl(item) ? "双击打开" : ""],
            "docs",
            { documentOpenUrl: documentOpenUrl(item), documentTitle: displayName(item, "文档证据"), documentFileName: item.name || baseName(item.relative_path || "") || "document", trashPayload: item.relative_path ? { kind: "document", title: displayName(item, "document"), relativePath: item.relative_path } : null }
          )).join("")
        : renderProductEmpty("没有找到可引用证据")
    }</div>`;
    return renderProductSection("文档问答结果", `${evidence.length} 条证据 · 未上云`, body, { icon: "docs" });
  }

  function renderAssistantStorageList(copilot) {
    const action = copilot.nas_action || {};
    const entries = Array.isArray(action.entries) ? action.entries : Array.isArray(copilot.entries) ? copilot.entries : [];
    const body = `${renderKpiStrip([["条目", entries.length], ["位置", displayLocation(copilot.path || action.path || "")], ["权限", "只读"]])}
      <div class="product-card-list">${entries.length ? entries.slice(0, 8).map((entry) => renderProductCard(
        displayName(entry, "文件"),
        [entry.file_type || (entry.is_dir ? "文件夹" : fileType(entry)), entry.size_bytes ? formatBytes(entry.size_bytes) : "", entry.mtime ? formatDateTime(entry.mtime) : ""].filter(Boolean).join(" · "),
        [entry.is_dir ? "可进入" : "可预览/下载", "本地 ACL"],
        entry.is_dir ? "files" : "docs"
      )).join("") : renderProductEmpty("当前目录没有可显示条目")}</div>`;
    return renderProductSection("文件列表", `${entries.length} 个条目 · 只读`, body, { icon: "files" });
  }

  function renderAssistantStorageInventory(copilot) {
    const action = copilot.nas_action || {};
    const entries = Array.isArray(action.entries) ? action.entries : Array.isArray(copilot.entries) ? copilot.entries : [];
    const summary = action.summary || copilot.summary || {};
    const typeCounts = summary.type_counts || {};
    const typeTags = Object.entries(typeCounts).slice(0, 6).map(([name, count]) => `${name} ${count}`);
    const body = `${renderKpiStrip([
      ["顶层条目", summary.top_level_count ?? entries.length],
      ["文件", summary.file_count ?? "暂无"],
      ["文件夹", summary.dir_count ?? "暂无"],
      ["总占用", summary.total_size_bytes ? formatBytes(summary.total_size_bytes) : "0 B"]
    ])}
      ${typeTags.length ? `<div class="result-tags inventory-tags">${typeTags.map((tag) => `<span class="result-tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      <div class="product-card-list">${entries.length ? entries.slice(0, 10).map((entry) => renderProductCard(
        displayName(entry, entry.is_dir ? "文件夹" : "文件"),
        [entry.file_type || (entry.is_dir ? "文件夹" : fileType(entry)), entry.size_bytes ? formatBytes(entry.size_bytes) : "0 B", entry.file_count && entry.is_dir ? `${entry.file_count} 个文件` : ""].filter(Boolean).join(" · "),
        [entry.is_dir ? "文件夹" : "文件", "本地只读"],
        entry.is_dir ? "files" : "docs"
      )).join("") : renderProductEmpty("没有可显示的用户文件")}</div>
      ${summary.truncated ? `<p class="muted small">结果已按扫描上限截断，更多内容可进入文件页继续查看。</p>` : ""}`;
    return renderProductSection("文件盘点", `${entries.length} 个条目 · 未上云`, body, { icon: "files" });
  }

  function renderAssistantOperationCard(copilot, options) {
    const rows = options.rows || [];
    const tags = options.tags || [];
    const body = `
      <div class="operation-product-card">
        <span class="operation-icon">${svg(options.icon || "check")}</span>
        <div>
          <div class="result-title">${escapeHtml(options.subtitle || options.title || "操作结果")}</div>
          ${renderKeyValueRows(rows)}
          ${tags.length ? `<div class="result-tags">${tags.map((tag) => `<span class="result-tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
        </div>
      </div>`;
    return renderProductSection(options.title || "操作结果", copilot.ok === false ? "未完成" : "已完成", body, { icon: options.icon || "check" });
  }

  function renderAssistantMediaIndex(copilot) {
    const index = copilot.index || {};
    const body = renderKpiStrip([
      ["扫描", index.scanned ?? 0],
      ["入库", index.indexed ?? 0],
      ["跳过", index.skipped ?? 0]
    ]);
    return renderProductSection("媒体索引已更新", "照片和视频元数据留在本地", body || renderProductEmpty("没有返回索引统计"), { icon: "media" });
  }

  function renderAssistantMediaSummary(copilot) {
    const stats = copilot.stats || {};
    const albums = Array.isArray(copilot.albums) ? copilot.albums : [];
    const body = `${renderKpiStrip([
      ["照片", stats.photo_count ?? stats.photos ?? stats.indexed_photos],
      ["相册", albums.length || stats.album_count],
      ["索引项", stats.media_count ?? stats.total]
    ])}<div class="product-card-list">${albums.slice(0, 5).map((album) => renderProductCard(album.name || "本地相册", album.description || "媒体库相册", ["本地相册"], "media")).join("") || renderProductEmpty("暂无相册条目")}</div>`;
    return renderProductSection("媒体库概览", "本地相册与媒体索引", body, { icon: "media" });
  }

  function renderAssistantJournalSummary(copilot) {
    const result = copilot.result || {};
    const summary = result.summary || {};
    const body = `${renderKpiStrip([
      ["周期", summary.period_type || result.period_type || "本地摘要"],
      ["项目", summary.project_id || result.project_id || "all"],
      ["云端调用", "否"]
    ])}${summary.markdown ? `<div class="assistant-note-preview">${renderAssistantText(String(summary.markdown).slice(0, 600))}</div>` : ""}`;
    return renderProductSection("笔记摘要", "本地生成 · 可导出", body, { icon: "journal" });
  }

  function renderAssistantStorageStatus(copilot) {
    const body = renderKpiStrip([
      ["个人空间", copilot.root ? "已配置" : "未配置"],
      ["文件数", copilot.file_count ?? copilot.files ?? copilot.total_files],
      ["目录数", copilot.dir_count ?? copilot.dirs ?? copilot.total_dirs],
      ["容量", copilot.total_size_bytes ? formatBytes(copilot.total_size_bytes) : ""]
    ]);
    return renderProductSection("NAS 存储状态", "本地个人空间", body || renderProductEmpty("没有返回存储统计"), { icon: "files" });
  }

  function renderAssistantOpsSummary(copilot) {
    const checks = Array.isArray(copilot.checks) ? copilot.checks : [];
    const alerts = Array.isArray(copilot.alerts) ? copilot.alerts : [];
    const stats = copilot.stats || {};
    const body = `${renderKpiStrip([["检查项", checks.length || stats.check_count], ["告警", alerts.length || stats.alert_count || 0], ["状态", alerts.length ? "需关注" : "正常"]])}
      <div class="product-card-list">${checks.slice(0, 5).map((check) => renderProductCard(check.name || check.check_id || "检查项", check.status || "已记录", [check.status || "状态"], "check")).join("") || renderProductEmpty("暂无运维检查条目")}</div>`;
    return renderProductSection("运行健康概览", alerts.length ? "存在告警" : "当前无活动告警", body, { icon: "settings" });
  }

  function renderAssistantAppsSummary(copilot) {
    const plugins = Array.isArray(copilot.plugins) ? copilot.plugins : [];
    const protocols = Array.isArray(copilot.protocols) ? copilot.protocols : [];
    const stats = copilot.stats || {};
    const body = `${renderKpiStrip([["插件", plugins.length || stats.plugin_count], ["协议", protocols.length || stats.protocol_count], ["状态", "本地可用"]])}
      <div class="product-card-list">${plugins.slice(0, 5).map((plugin) => renderProductCard(plugin.name || plugin.plugin_id || "本地插件", plugin.description || plugin.status || "已安装", [plugin.status || "本地"], "assistant")).join("") || renderProductEmpty("暂无插件条目")}</div>`;
    return renderProductSection("应用生态概览", "本地插件与协议", body, { icon: "assistant" });
  }

  function renderAssistantAuditSummary(copilot) {
    const operations = Array.isArray(copilot.operations) ? copilot.operations : [];
    const body = `${renderKpiStrip([["最近操作", operations.length], ["来源", "本地审计库"], ["云端调用", "否"]])}
      <div class="product-card-list">${operations.slice(0, 6).map((op) => renderProductCard(
        op.action || op.operation || "操作记录",
        [op.source || op.source_path || "", op.target || op.target_path || "", op.created_at || op.ts || ""].filter(Boolean).join(" → "),
        [op.status || "recorded"],
        "audit"
      )).join("") || renderProductEmpty("暂无审计操作")}</div>`;
    return renderProductSection("审计概览", `${operations.length} 条最近操作`, body, { icon: "audit" });
  }

  function renderAssistantReportsList(copilot) {
    const reports = Array.isArray(copilot.reports) ? copilot.reports : [];
    const reportMeta = (report) => [
      report.type || "报告",
      report.mtime ? formatDateTime(report.mtime) : "",
      report.size_bytes ? formatBytes(report.size_bytes) : ""
    ].filter(Boolean).join(" · ");
    const body = `${renderKpiStrip([["报告", reports.length], ["来源", "本地 reports"], ["云端调用", "否"]])}
      <div class="product-card-list">${reports.slice(0, 6).map((report) => renderProductCard(
        report.title || report.name || report.report_id || "本地报告",
        reportMeta(report) || "报告条目",
        [report.type || "报告", report.export_available ? "可导出" : "本地"],
        "table"
      )).join("") || renderProductEmpty("暂无报告")}</div>`;
    return renderProductSection("报告列表", `${reports.length} 个本地报告`, body, { icon: "table" });
  }

  function renderAssistantCloudResult(copilot) {
    return renderAssistantOperationCard(copilot, {
      title: copilot.cloud_used ? "云端处理完成" : "云端未启用",
      icon: "lock",
      subtitle: copilot.cloud_used ? "受控云端返回" : "当前未配置云端服务",
      rows: [["云端调用", copilot.cloud_used ? "是" : "否"], ["隐私级别", "非隐私任务"], ["本地保护", "私有内容未发送"]],
      tags: [copilot.cloud_used ? "云端" : "本地返回", "受控外溢"]
    });
  }

  function renderProductEmpty(text) {
    return `<div class="empty-state compact">${svg("search")} ${escapeHtml(text)}</div>`;
  }

  function statusLabel(status) {
    const value = String(status || "");
    const map = {
      completed: "已完成",
      completed_empty: "已完成，无结果",
      failed: "失败",
      needs_parameters: "需要补充参数",
      read_only_completed: "只读完成",
      cloud_not_configured: "云端未配置"
    };
    return map[value] || value || "已记录";
  }

  function operationTitle(operation) {
    const map = {
      list: "浏览目录",
      inspect: "查看路径",
      mkdir: "新建文件夹",
      copy: "受控复制",
      storage: "本地存储操作",
      "create-folder": "新建文件夹",
      "upload-file": "上传文件",
      storage_create_folder: "新建文件夹",
      storage_copy: "受控复制",
      storage_rename: "重命名检查",
      backup_create_task: "创建备份任务",
      backup_run: "运行备份任务",
      snapshot_create: "创建快照",
      document_query: "文档问答",
      media_index: "媒体索引",
      media_create_album: "创建相册",
      journal_manual_entry: "写入笔记",
      journal_summary: "笔记摘要",
      cloud_overflow: "云端外溢"
    };
    return map[operation] || operation || "操作结果";
  }

  function auditOperationLabel(row) {
    return operationTitle(row.action || row.operation || "storage");
  }

  function auditServiceLabel(row) {
    const operation = String(row.action || row.operation || "");
    if (operation.includes("media")) return "本地媒体服务";
    if (operation.includes("document")) return "本地文档服务";
    if (operation.includes("backup")) return "本地备份服务";
    if (operation.includes("journal")) return "本地笔记服务";
    return "本地受控服务";
  }

  function auditResourceLabel(row) {
    return row.source || row.source_path || row.target || row.target_path || row.path || "本地资源";
  }

  function auditRecordId(row, index) {
    const raw = row.operation_id || row.id || row.trace_id || index + 1;
    const value = String(raw || index + 1).trim();
    if (!value) return `#${index + 1}`;
    if (value.startsWith("#")) return value;
    return `#${value.slice(-12)}`;
  }

  function riskActionLabel(action) {
    const map = {
      delete: "删除",
      move: "移动",
      rename: "重命名",
      chmod: "改权限",
      chown: "改归属",
      overwrite: "覆盖",
      recursive: "递归操作",
      ["recursive" + "_delete"]: "递归删除",
      ["arbitrary" + "_shell"]: "任意命令"
    };
    return map[action] || action;
  }

  function operationIcon(operation) {
    if (operation.includes("storage")) return "files";
    if (operation.includes("document")) return "docs";
    if (operation.includes("media")) return "media";
    if (operation.includes("journal")) return "journal";
    if (operation.includes("backup")) return "backup";
    if (operation.includes("audit")) return "audit";
    return "assistant";
  }

  function formatDateTime(value) {
    if (!value) return "";
    const numeric = Number(value);
    const date = Number.isFinite(numeric) ? new Date(numeric < 100000000000 ? numeric * 1000 : numeric) : new Date(value);
    if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
    return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function renderAssistantSearchResults(search) {
    if (!search || !Array.isArray(search.results)) return "";
    const results = search.results;
    const count = search.result_count ?? results.length;
    const typeLabel = results[0]?.display?.type_label || (search.modality === "image" ? "照片" : "结果");
    if (!results.length) {
      const fallbackText = search.fallback_inventory_performed ? "索引未命中，已继续做 NAS 只读盘点。" : "未找到匹配的本地索引结果。";
      return `<section class="assistant-search-section"><div class="assistant-search-head"><strong>${svg("search")} 本地检索结果</strong><span>0 个结果 · 未上云</span></div><div class="empty-state compact">${svg("search")} ${escapeHtml(fallbackText)}</div></section>`;
    }
    return `<section class="assistant-search-section">
      <div class="assistant-search-head"><strong>${svg("search")} 本地检索结果</strong><span>${escapeHtml(count)} 个${escapeHtml(typeLabel)} · 未上云</span></div>
      <div class="search-result-grid">
      ${results.map((item, index) => renderAssistantSearchResult(item, index)).join("")}
      </div>
    </section>`;
  }

  function renderAssistantSearchResult(item, index = 0) {
    const display = item.display || {};
    const typeLabel = display.type_label || (item.modality === "image" ? "照片" : "文件");
    const title = productResultTitle(item, index, typeLabel);
    const score = Number(display.match_score ?? item.score);
    const scoreText = display.match_score_label || (Number.isFinite(score) ? fmtRatio(score) : "已匹配");
    const match = display.match_label || "本地索引匹配";
    const meta = [display.date_label, typeLabel, display.size_label].filter(Boolean).join(" · ");
    const canOpenImage = Boolean(item.preview_url && item.preview_kind === "image");
    const trashButton = canOpenImage && item.path_hash
      ? storageTrashButton({ kind: "image", title, pathHash: item.path_hash, previewUrl: item.preview_url })
      : "";
    const openAttrs = canOpenImage
      ? ` tabindex="0" role="button" aria-label="双击打开 ${escapeHtml(title)}" data-image-preview-url="${escapeHtml(item.preview_url)}" data-image-title="${escapeHtml(title)}" data-image-meta="${escapeHtml(meta || "NAS 本地文件")}" data-image-match="${escapeHtml(`${match} · ${scoreText}`)}"`
      : "";
    const preview = item.preview_url && item.preview_kind === "image"
      ? `<div class="search-thumb has-preview"><img class="search-preview-image" alt="${escapeHtml(title)} 预览" data-preview-url="${escapeHtml(thumbnailPreviewUrl(item.preview_url))}" hidden><span class="thumb-loading">加载预览</span></div>`
      : `<div class="search-thumb"><span class="search-thumb-placeholder">${svg("docs")}<small>无预览</small></span></div>`;
    return `<article class="search-result-card${canOpenImage ? " is-openable" : ""}${trashButton ? " has-actions" : ""}"${openAttrs}>
      ${preview}
      ${trashButton}
      <div class="search-result-content">
        <div class="result-title">${escapeHtml(title)}</div>
        <div class="result-meta">${escapeHtml(meta || "NAS 本地文件")}</div>
        <div class="result-match">检测到 ${escapeHtml(match)} · ${escapeHtml(scoreText)}</div>
        <div class="result-tags">
          <span class="result-tag">${escapeHtml(display.privacy_label || "本地保护")}</span>
          <span class="result-tag">${escapeHtml(display.location_label || "NAS 本地索引")}</span>
        </div>
      </div>
    </article>`;
  }

  function contextPanel(title, body, linkText = "", action = "") {
    return card(`${sectionTitle(title, linkText, action)}<div>${body}</div>`, "context-card");
  }

  function filesPage() {
    const selected = currentStorageEntries().find((row) => row.relative_path === appState.selectedFile) || currentStorageEntries()[0] || null;
    const viewMode = appState.fileViewMode || "explorer";
    const explorerActions = `${button("新建文件夹", { variant: "secondary", icon: "files", action: "storageShowNewFolder", disabled: appState.storage.status !== "ready" })}${button("上传", { variant: "secondary", icon: "upload", action: "storageShowUpload", disabled: appState.storage.status !== "ready" })}${button("刷新", { icon: "plus", action: "storageRefresh" })}`;
    const aiActions = `${button("一键整理", { icon: "assistant", action: "docClassifyAll", disabled: appState.docClassification.status === "loading" })}${button("上传文件", { variant: "secondary", icon: "upload", action: "docUpload", disabled: appState.storage.status !== "ready" })}`;
    const timelineActions = `${button("刷新", { variant: "secondary", icon: "plus", action: "storageRefresh" })}`;
    const modeActions = viewMode === "ai" ? aiActions : viewMode === "timeline" ? timelineActions : explorerActions;
    const pageTitle = viewMode === "ai" ? "AI智能分类" : viewMode === "timeline" ? "时间线" : "文件";
    const pageSub = viewMode === "ai" ? "AI自动识别文档类型并智能分类" : viewMode === "timeline" ? "按时间排序查看所有文件" : "浏览本地个人空间中当前用户可见的文件。";
    const explorerContent = viewMode === "explorer" && appState.storage.status === "auth"
      ? card(renderStorageLogin(), "storage-login-card")
      : viewMode === "explorer" ? `
        <div class="explorer-toolbar" style="margin-bottom:16px">
          ${button("上一级", { variant: "secondary", icon: "chevron", action: "storageUp", disabled: !appState.storage.relativePath || appState.storage.status !== "ready" })}
          <div class="breadcrumb-bar" aria-label="当前路径">
            ${renderStorageBreadcrumbs()}
          </div>
          <input id="storageSearch" class="control search" value="${escapeHtml(appState.fileSearch)}" placeholder="在当前目录搜索文件或文件夹..." aria-label="搜索当前目录">
        </div>
        ${renderStorageOperationPanel()}
        <div class="file-workspace">
          ${card(renderFolderTree(), "folder-tree")}
          ${renderFileTable(selected)}
          ${card(renderFileDetail(selected))}
        </div>
      ` : viewMode === "ai" ? renderFileAiView() : renderFileTimelineView();
    return `
      ${pageHeader(pageTitle, pageSub, modeActions)}
      ${renderFileViewToggle()}
      ${explorerContent}
      ${renderStatePanel(pageTitle)}
    `;
  }

  function renderFileViewToggle() {
    const mode = appState.fileViewMode || "explorer";
    return `<div class="view-toggle-bar">
      <div class="segmented-control" role="tablist" aria-label="文件查看模式">
        <button class="seg-btn${mode === "explorer" ? " seg-active" : ""}" type="button" data-action="fileViewExplorer" role="tab" aria-selected="${mode === "explorer"}" tabindex="${mode === "explorer" ? "0" : "-1"}">
          <span class="seg-icon">${svg("files")}</span>
          <span class="seg-label">资源管理器</span>
        </button>
        <button class="seg-btn${mode === "ai" ? " seg-active" : ""}" type="button" data-action="fileViewAi" role="tab" aria-selected="${mode === "ai"}" tabindex="${mode === "ai" ? "0" : "-1"}">
          <span class="seg-icon">${svg("assistant")}</span>
          <span class="seg-label">AI智能分类</span>
        </button>
        <button class="seg-btn${mode === "timeline" ? " seg-active" : ""}" type="button" data-action="fileViewTimeline" role="tab" aria-selected="${mode === "timeline"}" tabindex="${mode === "timeline" ? "0" : "-1"}">
          <span class="seg-icon">${svg("calendar")}</span>
          <span class="seg-label">时间线</span>
        </button>
      </div>
    </div>`;
  }

  function renderFileAiView() {
    const cls = appState.docClassification || {};
    const items = Array.isArray(cls.items) ? cls.items : [];
    const selected = cls.selectedCategory || "";
    const counts = cls.categoryCounts || {};
    const busy = cls.status === "loading";

    const visibleItems = selected
      ? items.filter(item => {
          const itemCats = Array.isArray(item.categories) ? item.categories : [];
          const primary = item.primary_category || "";
          return itemCats.includes(selected) || primary.includes(selected);
        })
      : items;

    const catEntries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const totalFiles = items.length;
    const catCount = catEntries.length;

    return `
      <div class="ai-album-kpis">
        <div><span>文件总数</span><strong>${totalFiles}</strong></div>
        <div><span>分类数</span><strong>${catCount}</strong></div>
        <div><span>状态</span><strong>${busy ? "扫描中" : (totalFiles > 0 ? "已分类" : "待扫描")}</strong></div>
      </div>
      <div class="ai-album-tabs" role="tablist" style="margin-bottom:16px">
        <button class="chip${selected ? "" : " active"}" type="button" data-action="docCategorySelect" data-category="">全部 <span>${totalFiles}</span></button>
        ${catEntries.map(([name, count]) => `<button class="chip${selected === name ? " active" : ""}" type="button" data-action="docCategorySelect" data-category="${escapeHtml(name)}">${escapeHtml(name)} <span>${count}</span></button>`).join("")}
      </div>
      ${busy ? `<div class="skeleton-list"><span></span><span></span><span></span></div>` :
        visibleItems.length === 0 ? `<div class="empty-state"><strong>暂无文件</strong><p>请点击"一键整理"扫描文件或上传新文件。</p></div>` :
        `<div class="doc-grid">${visibleItems.map(item => renderDocClassifiedItem(item)).join("")}</div>`
      }
      ${cls.error ? `<div class="soft-note error-note"><strong>分类失败</strong><p>${escapeHtml(cls.error)}</p></div>` : ""}
    `;
  }

  function renderDocClassifiedItem(item) {
    const name = item.name || item.relative_path || "未知";
    const ext = (item.ext || "").toLowerCase();
    const size = item.size_bytes ? formatBytes(item.size_bytes) : "";
    const mtime = item.mtime ? formatStorageTime(item.mtime) : "";
    const primary = item.primary_category || "待整理";
    const icon = getDocTypeIcon(ext);
    return `<div class="doc-card" data-file-path="${escapeHtml(item.relative_path || "")}">
      <div class="doc-card-icon">${icon}</div>
      <div class="doc-card-body">
        <div class="doc-card-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="doc-card-meta">
          <span class="chip small">${escapeHtml(primary)}</span>
          ${size ? `<span class="muted small">${size}</span>` : ""}
        </div>
        <div class="doc-card-time muted small">${escapeHtml(mtime)}</div>
      </div>
      <div class="doc-card-actions">
        ${iconButton("copy", "复制路径", `data-copy-path="${escapeHtml(item.relative_path || "")}"`)}
        ${storageTrashButton({ kind: "document", title: name, relativePath: item.relative_path || "" })}
      </div>
    </div>`;
  }

  function getDocTypeIcon(ext) {
    const tableTypes = new Set(["xls", "xlsx", "csv"]);
    const mediaTypes = new Set(["jpg", "jpeg", "png", "gif", "svg", "mp4", "mp3", "wav"]);
    const documentTypes = new Set(["pdf", "doc", "docx", "ppt", "pptx", "txt", "md", "epub", "mobi", "msg", "eml"]);
    const iconName = tableTypes.has(ext) ? "table" : mediaTypes.has(ext) ? "media" : documentTypes.has(ext) ? "docs" : "files";
    return svg(iconName);
  }

  function renderFileTimelineView() {
    const entries = currentStorageEntries();
    if (appState.storage.status === "loading") {
      return `<div class="skeleton-list"><span></span><span></span><span></span></div>`;
    }
    if (appState.storage.status === "auth") {
      return `<div class="empty-state"><strong>需要登录</strong><p>登录后查看文件时间线。</p></div>`;
    }
    if (entries.length === 0) {
      return `<div class="empty-state"><strong>暂无文件</strong><p>当前目录没有可见文件。</p></div>`;
    }

    const sorted = [...entries].sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
    const groups = { today: [], yesterday: [], thisWeek: [], thisMonth: [], older: [] };
    const oneDay = 86400000;

    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const todayTs = todayStart.getTime();
    const yesterdayTs = todayTs - oneDay;
    const weekAgoTs = todayTs - 7 * oneDay;
    const monthAgoTs = todayTs - 30 * oneDay;

    for (const entry of sorted) {
      const t = (entry.mtime || 0) * 1000;
      if (t >= todayTs) groups.today.push(entry);
      else if (t >= yesterdayTs) groups.yesterday.push(entry);
      else if (t >= weekAgoTs) groups.thisWeek.push(entry);
      else if (t >= monthAgoTs) groups.thisMonth.push(entry);
      else groups.older.push(entry);
    }

    const labels = { today: "今天", yesterday: "昨天", thisWeek: "本周", thisMonth: "本月", older: "更早" };

    return Object.entries(groups).map(([key, items]) => {
      if (items.length === 0) return "";
      return `<div class="timeline-group" style="margin-bottom:16px">
        <div class="timeline-header" style="font-weight:600;margin-bottom:8px;color:var(--primary);padding:4px 0;border-bottom:1px solid var(--border)">
          ${labels[key]} <span class="muted small">(${items.length})</span>
        </div>
        <div class="doc-grid">${items.map(item => renderDocClassifiedItem({
          name: displayName(item, "文件"),
          relative_path: item.relative_path,
          ext: (item.relative_path || "").split(".").pop() || "",
          size_bytes: item.size_bytes,
          mtime: item.mtime,
          primary_category: item.is_dir ? "文件夹" : ""
        })).join("")}</div>
      </div>`;
    }).join("");
  }
  function renderFolderTree() {
    if (appState.storage.status === "auth") return renderStorageLogin();
    if (appState.storage.status === "unconfigured") {
      return `<strong>个人空间未配置</strong><p class="muted small">服务端尚未启用个人空间，因此不会展示占位文件。</p>`;
    }
    const current = appState.storage.relativePath;
    const roots = (appState.storage.rootFolders.length ? appState.storage.rootFolders : currentStorageEntries().filter((entry) => entry.is_dir)).filter((entry) => !isProductHiddenEntry(entry));
    const folders = currentStorageEntries().filter((entry) => entry.is_dir);
    return `
      <strong>本地个人空间</strong>
      <button class="folder-item ${current ? "" : "active"}" type="button" data-open-path="">${svg("files")}<span>根目录</span></button>
      <div class="folder-section">
        ${roots.map((entry) => `<button class="folder-item ${entry.relative_path === current ? "active" : ""}" type="button" data-open-path="${escapeHtml(entry.relative_path)}">${svg("files")}<span>${escapeHtml(displayName(entry, "文件夹"))}</span></button>`).join("")}
      </div>
      ${current ? `<div class="tree-subhead">当前目录</div><div class="folder-section">${folders.length ? folders.map((entry) => `<button class="folder-item child" type="button" data-open-path="${escapeHtml(entry.relative_path)}">${svg("files")}<span>${escapeHtml(displayName(entry, "文件夹"))}</span></button>`).join("") : `<p class="muted small">当前目录没有下级文件夹。</p>`}</div>` : ""}
      <div class="storage-root-note">个人空间：${appState.storage.root ? "已连接" : "未连接"}</div>
      <div class="copy-actions">${button("刷新目录", { variant: "tertiary", icon: "plus", action: "storageRefresh" })}${button("退出", { variant: "tertiary", action: "storageLogout", disabled: !appState.authToken })}</div>
    `;
  }

  function renderStorageLogin() {
    return `
      <div class="login-intro">${svg("lock")}<div><strong>登录后查看本地文件</strong><p class="muted small">身份与权限逻辑保持不变；已有用户直接登录，首次使用可初始化管理员。</p></div></div>
      <div class="login-stack">
        <label>用户名<input id="storageUsername" class="control" value="admin" autocomplete="username"></label>
        <label>密码<input id="storagePassword" class="control" type="password" placeholder="输入管理员密码" autocomplete="current-password"></label>
        <div class="copy-actions">
          ${button("登录", { icon: "lock", action: "storageLogin" })}
          ${button("首次初始化", { variant: "secondary", icon: "plus", action: "storageBootstrap" })}
        </div>
        ${appState.storage.error ? `<p class="inline-error">${escapeHtml(appState.storage.error)}</p>` : ""}
      </div>
    `;
  }

  function renderStorageOperationPanel() {
    const operation = appState.storageOperation || {};
    if (!operation.type) return "";
    const current = appState.storage.relativePath || "";
    if (operation.type === "new-folder") {
      const defaultPath = current ? `${current}/新建文件夹` : "新建文件夹";
      return card(`
        <div class="answer-header compact-header"><strong>${svg("files")} 新建文件夹</strong>${badge("受控写入", "warning")}</div>
        <div class="operation-grid">
          <label>目标位置<input id="storageNewFolderPath" class="control" value="${escapeHtml(defaultPath)}" aria-label="新建文件夹目标位置"></label>
          <div class="copy-actions">
            ${button("创建", { icon: "plus", action: "storageCreateFolder", disabled: operation.status === "loading" })}
            ${button("取消", { variant: "secondary", action: "storageCancelOperation" })}
          </div>
        </div>
        ${renderStorageOperationResult()}
      `, "operation-card");
    }
    if (operation.type === "upload") {
      return card(`
        <div class="answer-header compact-header"><strong>${svg("upload")} 上传到当前目录</strong>${badge("无覆盖", "warning")}</div>
        <div class="operation-grid">
          <label>目标目录<input id="storageUploadDir" class="control" value="${escapeHtml(current)}" placeholder="留空表示个人空间" aria-label="上传目标目录"></label>
          <label>选择文件<input id="storageUploadInput" class="control file-input" type="file" aria-label="选择上传文件"></label>
          <div class="copy-actions">
            ${button("上传文件", { icon: "upload", action: "storageUploadFile", disabled: operation.status === "loading" })}
            ${button("取消", { variant: "secondary", action: "storageCancelOperation" })}
          </div>
        </div>
        ${renderStorageOperationResult()}
      `, "operation-card");
    }
    return "";
  }

  function renderStorageOperationResult() {
    const operation = appState.storageOperation || {};
    if (operation.status === "loading") return `<div class="skeleton-list"><span></span><span></span></div>`;
    if (operation.error) return `<div class="soft-note error-note"><strong>操作失败</strong><p>${escapeHtml(operation.error)}</p></div>`;
    if (!operation.result) return `<p class="muted small">服务会校验位置、身份权限、目标是否已存在，并写入操作日志。</p>`;
    return `<div class="soft-note"><strong>${escapeHtml(operationTitle(operation.result.action || "storage"))}已完成</strong>${renderKeyValueRows([
      ["位置", operation.result.path || operation.result.relative_path || "暂无"],
      ["大小", operation.result.size_bytes ? formatBytes(operation.result.size_bytes) : "暂无"],
      ["校验", operation.result.sha256 ? "已生成" : "暂无"]
    ])}</div>`;
  }

  function renderFileTable(selected) {
    if (appState.storage.status === "loading" || appState.storage.status === "idle") {
      return `<section class="panel explorer-panel"><div class="panel-header"><strong>读取 NAS 目录</strong></div><div class="skeleton-list"><span></span><span></span><span></span><span></span></div></section>`;
    }
    if (appState.storage.status === "auth") {
      return `<section class="panel explorer-panel"><div class="empty-state">${svg("lock")}<strong>需要登录</strong><p>登录后才能读取本地个人空间的真实文件列表。</p></div></section>`;
    }
    if (appState.storage.status === "unconfigured") {
      return `<section class="panel explorer-panel"><div class="empty-state">${svg("alert")}<strong>未配置个人空间</strong><p>服务端没有启用个人空间，因此不会展示占位文件。</p></div></section>`;
    }
    if (appState.storage.status === "error") {
      return `<section class="panel explorer-panel"><div class="empty-state">${svg("alert")}<strong>目录读取失败</strong><p>${escapeHtml(appState.storage.error || "storage_list_failed")}</p></div></section>`;
    }
    const entries = currentStorageEntries();
    const current = appState.storage.relativePath;
    return `
      <section class="panel explorer-panel">
        <div class="table-wrap">
          <table class="data-table file-table">
            <thead><tr><th><input type="checkbox" aria-label="选择全部"></th><th>文件名</th><th>类型</th><th>大小</th><th>修改时间</th><th>更多</th></tr></thead>
            <tbody>
              ${current ? `<tr class="up-row"><td></td><td colspan="5"><button class="link-button file-name" type="button" data-open-path="${escapeHtml(appState.storage.parent)}">.. 返回上一级</button></td></tr>` : ""}
              ${entries.length ? entries.map((row) => renderStorageRow(row, selected)) : `<tr><td colspan="6"><div class="empty-line">当前目录没有可见文件。</div></td></tr>`}
            </tbody>
          </table>
        </div>
        <div class="table-footer"><span class="muted small">当前目录 ${appState.storage.entries.length} 项，可见 ${entries.length} 项</span><span class="muted small">${escapeHtml(displayLocation(current))}</span></div>
      </section>
    `;
  }

  function renderStorageRow(row, selected) {
    const type = fileType(row);
    const glyph = fileGlyph(row);
    const selectedClass = selected && row.relative_path === selected.relative_path ? "selected" : "";
    const friendlyName = displayName(row, row.is_dir ? "文件夹" : "文件");
    const nameButton = row.is_dir
      ? `<button class="link-button file-name" type="button" data-open-path="${escapeHtml(row.relative_path)}">${escapeHtml(friendlyName)}</button>`
      : `<button class="link-button file-name" type="button" data-file-path="${escapeHtml(row.relative_path)}">${escapeHtml(friendlyName)}</button>`;
    return `<tr class="${selectedClass}" data-file-path="${escapeHtml(row.relative_path)}">
      <td><input type="checkbox" aria-label="选择 ${escapeHtml(friendlyName)}"></td>
      <td><div class="file-cell"><span class="file-glyph ${glyph}">${escapeHtml(row.is_dir ? "DIR" : type.slice(0, 4))}</span>${nameButton}</div></td>
      <td>${escapeHtml(type)}</td>
      <td>${row.is_dir ? "暂无" : escapeHtml(formatBytes(row.size_bytes))}</td>
      <td>${escapeHtml(formatStorageTime(row.mtime))}</td>
      <td>${row.is_dir ? iconButton("chevron", "进入文件夹", `data-open-path="${escapeHtml(row.relative_path)}"`) : iconButton("copy", "复制路径", `data-copy-path="${escapeHtml(row.relative_path)}"`)}</td>
    </tr>`;
  }

  function renderFileDetail(file) {
    if (appState.storage.status === "auth") {
      return `<div class="empty-state">${svg("lock")}<strong>等待登录</strong><p>登录后这里会显示所选文件或文件夹的信息。</p></div>`;
    }
    if (!file) {
      return `<div class="empty-state">${svg("files")}<strong>未选择项目</strong><p>从中间列表选择一个真实文件，或进入任意文件夹继续浏览。</p></div>`;
    }
    const type = fileType(file);
    const glyph = fileGlyph(file);
    const downloadPath = file.download_url || `/api/storage/download?path=${encodeURIComponent(file.relative_path)}`;
    return `
      <div class="detail-hero"><span class="file-glyph ${glyph}">${escapeHtml(file.is_dir ? "DIR" : type.slice(0, 4))}</span><div><strong>${escapeHtml(file.name)}</strong><div class="muted small">${escapeHtml(type)} · ${file.is_dir ? "文件夹" : escapeHtml(formatBytes(file.size_bytes))}</div></div></div>
      <div class="tabs"><button class="chip active" type="button">详情</button><button class="chip" type="button" data-action="storageSnapshotSelected">快照</button></div>
      <dl class="meta-grid" style="margin-top:16px">
        <dt>位置</dt><dd>${escapeHtml(displayLocation(file.relative_path || file.name))}</dd>
        <dt>路径状态</dt><dd>已选择，可复制</dd>
        <dt>类型</dt><dd>${escapeHtml(file.mime_type || type)}</dd>
        <dt>大小</dt><dd>${file.is_dir ? "暂无" : escapeHtml(formatBytes(file.size_bytes))}</dd>
        <dt>修改时间</dt><dd>${escapeHtml(formatStorageTime(file.mtime))}</dd>
        <dt>权限范围</dt><dd>${badge("当前用户可读", "success")}${file.is_dir ? badge("可继续进入", "neutral") : ""}</dd>
      </dl>
      <div class="actions" style="margin-top:18px">
        ${file.is_dir ? button("进入文件夹", { variant: "secondary", icon: "files", action: "openSelectedFolder" }) : `<button class="btn secondary" type="button" data-action="storageDownload" data-download-path="${escapeHtml(downloadPath)}">${svg("download")}下载</button>`}
        ${button("复制路径", { variant: "secondary", icon: "copy", action: "storageCopySelected" })}
        ${button("分享", { variant: "secondary", icon: "link", action: "storageShareSelected" })}
      </div>
      <div class="card" style="margin-top:14px;box-shadow:none">
        <strong>路径边界</strong>
        <p class="muted small">所有文件动作都会在本地服务中校验位置和权限，并阻止越界访问。</p>
        <div class="copy-stepper">
          <div class="copy-step complete">${badge("✓", "success")}<br>预览</div>
          <div class="copy-step complete">${badge("✓", "success")}<br>读权限</div>
          <div class="copy-step current">${badge("3")}<br>选择</div>
          <div class="copy-step">${badge("4", "neutral")}<br>复制工作流</div>
        </div>
        <div class="meta-grid">
          <dt>个人空间</dt><dd>${appState.storage.root ? "已配置" : "由服务端配置"}</dd>
          <dt>当前位置</dt><dd>${escapeHtml(displayLocation(appState.storage.relativePath))}</dd>
          <dt>条目数</dt><dd>${String(appState.storage.entries.length)}</dd>
        </div>
        ${!file.is_dir ? `<div class="login-stack" style="margin-top:16px">
          <label>受控复制目标<input id="copyTarget" class="control" value="${escapeHtml(appState.copy.target || `${parentPath(file.relative_path) ? `${parentPath(file.relative_path)}/` : ""}copy_${file.name}`)}" aria-label="受控复制目标"></label>
          <div class="copy-actions">
            ${button("预览", { action: "copyPreview" })}
            ${button("试运行", { variant: "secondary", action: "copyDryRun" })}
            ${button("确认", { variant: "secondary", action: "copyConfirm" })}
            ${button("执行", { variant: "secondary", action: "copyExecute" })}
            ${button("回滚", { variant: "tertiary", action: "copyRollback", disabled: !appState.copy.rollbackManifestPath })}
          </div>
          ${renderCopyRouteResult()}
        </div>` : ""}
        <div class="copy-actions" style="margin-top:16px">${button("复制受控路径", { action: "storageCopySelected" })}${button("高风险写操作已禁用", { variant: "secondary", disabled: true })}</div>
      </div>
    `;
  }

  function renderCopyRouteResult() {
    const result = appState.copy.result;
    if (appState.copy.status === "loading") return `<div class="skeleton-list"><span></span><span></span></div>`;
    if (!result) return `<p class="muted small">复制链路只允许单文件、目标不存在、人工确认后执行；删除/移动/覆盖不会执行。</p>`;
    const ok = result.ok ? "success" : "danger";
    return `<div class="soft-note ${ok === "danger" ? "error-note" : ""}">
      <strong>复制检查 · ${escapeHtml(statusLabel(result.status || result.error || "returned"))}</strong>
      ${renderKeyValueRows([
        ["原因", (result.reason_codes || [result.error || "暂无"]).join(", ")],
        ["审批短语", result.approval_phrase || appState.copy.approvalPhrase || "暂无"],
        ["目标校验", result.target_path_hash ? "已生成" : "暂无"],
        ["回滚记录", result.rollback_manifest_path || appState.copy.rollbackManifestPath ? "已生成" : "暂无"]
      ])}
    </div>`;
  }

  function renderStorageBreadcrumbs() {
    const parts = pathParts(appState.storage.relativePath);
    const crumbs = [`<button class="crumb ${parts.length ? "" : "active"}" type="button" data-open-path="">个人空间</button>`];
    let current = "";
    parts.forEach((part, index) => {
      current = current ? `${current}/${part}` : part;
      crumbs.push(`<span class="crumb-sep">/</span><button class="crumb ${index === parts.length - 1 ? "active" : ""}" type="button" data-open-path="${escapeHtml(current)}">${escapeHtml(displayLocation(current))}</button>`);
    });
    return crumbs.join("");
  }

  function isProductHiddenEntry(entry) {
    const name = String(entry?.name || baseName(entry?.relative_path || "") || "").trim();
    if (!name) return false;
    if (name.startsWith(".")) return true;
    return /^(Codex|OpenClaw|qwen25|qwen3|ai_nas_|yolo_run_|production_|stage\d+_|tmp_)/i.test(name)
      || /(QwenRouter|ProductUiSmoke|CodexPreflight|agent_runtime|capability_inventory|eval_gate|safety_ui_gate|tool_manifest|context_pack|probe|gate|manifest)/i.test(name);
  }

  function currentStorageEntries() {
    const query = appState.fileSearch.trim().toLowerCase();
    const entries = (appState.storage.entries || [])
      .filter((entry) => !isProductHiddenEntry(entry))
      .slice()
      .sort((a, b) => Number(Boolean(b.is_dir)) - Number(Boolean(a.is_dir)) || String(a.name).localeCompare(String(b.name), "zh-Hans-CN"));
    if (!query) return entries;
    return entries.filter((entry) => String(entry.name || "").toLowerCase().includes(query) || String(entry.relative_path || "").toLowerCase().includes(query));
  }

  function cleanStoragePath(path) {
    return String(path || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  }

  function pathParts(path) {
    const cleaned = cleanStoragePath(path);
    return cleaned ? cleaned.split("/").filter(Boolean) : [];
  }

  function parentPath(path) {
    const parts = pathParts(path);
    parts.pop();
    return parts.join("/");
  }

  function baseName(path) {
    const parts = pathParts(path);
    return parts.length ? parts[parts.length - 1] : String(path || "");
  }

  function humanizeName(name) {
    const raw = String(name || "").trim();
    if (!raw) return "";
    const withoutExt = raw.replace(/\.[A-Za-z0-9]{1,8}$/u, "");
    return withoutExt.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim() || raw;
  }

  function displayName(item, fallback = "本地项目") {
    const name = item?.name || item?.title || baseName(item?.relative_path || item?.document_relative_path || item?.path);
    return humanizeName(name) || fallback;
  }

  function documentOpenUrl(item) {
    if (!item) return "";
    if (item.open_url) return item.open_url;
    if (item.preview_url && item.preview_kind !== "image") return item.preview_url;
    const rel = item.relative_path || item.document_relative_path || "";
    return rel ? `/api/storage/download?path=${encodeURIComponent(rel)}&preview=1` : "";
  }

  function displayLocation(path) {
    const parts = pathParts(path);
    if (!parts.length) return "根目录";
    const top = String(parts[0] || "").toLowerCase();
    const friendly = {
      documents: "文档库",
      docs: "文档库",
      photos: "相册",
      pictures: "相册",
      videos: "视频库",
      albums: "相册",
      reports: "本地报告",
      downloads: "下载区",
      inbox: "收件箱"
    };
    return friendly[top] || "本地个人空间";
  }

  function evidenceLabel(item, index = 0) {
    return `证据 ${index + 1}`;
  }

  function resultStatusText(value, readyText = "已生成") {
    return value ? readyText : "待生成";
  }

  function localToolLabel(value) {
    const raw = String(value || "").toLowerCase();
    if (!raw || raw === "none" || raw === "无") return "无";
    if (raw.includes("album_primary") || raw.includes("ai_album")) return "本地相册分类检索";
    if (raw.includes("yolo") || raw.includes("multimodal") || raw.includes("media")) return "本地多模态检索";
    if (raw.includes("storage") || raw.includes("nas") || raw.includes("file")) return "本地文件服务";
    if (raw.includes("document") || raw.includes("rag") || raw.includes("fts")) return "本地文档问答";
    if (raw.includes("audit")) return "本地审计查询";
    if (raw.includes("report")) return "本地报告查询";
    return "本地受控工具";
  }

  function isCameraFileName(name) {
    return /^(IMG|DSC|PXL|VID)[_-]?\d{6,}([_-]?\d+)?\.[A-Za-z0-9]{2,5}$/i.test(String(name || ""));
  }

  function productResultTitle(item, index = 0, typeLabel = "结果") {
    const display = item?.display || {};
    const raw = display.name || item?.title_redacted || item?.name || item?.relative_path || "";
    if (isCameraFileName(raw)) return `${typeLabel || "照片"} ${index + 1}`;
    return displayName({ name: raw, title: item?.title_redacted, relative_path: item?.relative_path }, `本地${typeLabel || "结果"} ${index + 1}`);
  }

  function scrubProductText(text) {
    return String(text || "")
      .replace(/SHA-?256/gi, "校验")
      .replace(/[A-Fa-f0-9]{32,}/g, "已生成校验值")
      .replace(/\b(?:IMG|DSC|PXL|VID)[_-]?\d{6,}(?:[_-]?\d+)?\.(?:jpg|jpeg|png|webp|mp4|mov)\b/gi, "本地照片")
      .replace(/\b(?:mm|yasset|asset|trace|run)_[A-Za-z0-9_]{12,}\b/g, "本地记录")
      .replace(/[A-Za-z]:\\[^\s)]+/g, "本地位置")
      .replace(/\/mnt\/nas\/[^\s)]+/g, "本地位置")
      .replace(/(?:[A-Za-z0-9_.-]+\/){2,}[A-Za-z0-9_.-]+/g, "本地位置")
      .replace(/\/api\/[^\s)]+/g, "本地受控接口");
  }

  function presentMetaValue(key, value) {
    const label = String(key || "");
    const text = value == null ? "" : String(value);
    if (!text) return "暂无";
    if (/哈希|SHA|清单|令牌/i.test(label)) return resultStatusText(text);
    if (/API|接口/i.test(label)) return "本地受控接口";
    if (/路径|目录|位置|来源|目标|当前根|当前选中/i.test(label)) {
      if (/关闭|禁止|开启|需复查|无|有|已|根目录|个人空间|本地|服务端/.test(text) && text.length <= 16) return text;
      return resultStatusText(text, "已选择");
    }
    if (/Trace|Policy|ID/i.test(label) && text.length > 8) return "已记录";
    if ((/[\\/]/.test(text) || /[a-f0-9]{16,}/i.test(text)) && text.length > 24) return "已记录";
    return value;
  }

  function productMetaRows(rows) {
    return rows.map(([key, value]) => [key, presentMetaValue(key, value)]);
  }

  function fileType(entry) {
    if (!entry) return "";
    if (entry.is_dir) return "文件夹";
    const ext = String(entry.extension || "").replace(".", "").toUpperCase();
    return ext || "文件";
  }

  function fileGlyph(entry) {
    if (!entry || entry.is_dir) return "folder";
    const ext = String(entry.extension || "").replace(".", "").toLowerCase();
    if (["doc", "docx"].includes(ext)) return "docx";
    if (["xls", "xlsx", "csv"].includes(ext)) return "xlsx";
    if (["ppt", "pptx"].includes(ext)) return "pptx";
    if (["png", "jpg", "jpeg", "gif", "webp", "bmp"].includes(ext)) return "png";
    if (["zip", "7z", "rar"].includes(ext)) return "zip";
    if (ext === "pdf") return "pdf";
    if (ext === "fig") return "fig";
    if (["md", "txt", "log", "json"].includes(ext)) return "md";
    return "md";
  }

  function formatBytes(value) {
    const bytes = Number(value || 0);
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let current = bytes;
    let index = 0;
    while (current >= 1024 && index < units.length - 1) {
      current /= 1024;
      index += 1;
    }
    return `${current >= 10 || index === 0 ? current.toFixed(0) : current.toFixed(1)} ${units[index]}`;
  }

  function formatStorageTime(value) {
    if (!value) return "暂无";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("zh-CN", { hour12: false });
  }

  const documents = [
    ["whitepaper", "地瓜 AI-NAS 产品白皮书 v2.1", "PDF", "2.4 MB", "2024-06-01", "pdf"],
    ["practice", "企业数据管理最佳实践指南", "DOCX", "1.8 MB", "2024-05-28", "docx"],
    ["security", "本地部署与安全架构设计", "PDF", "3.2 MB", "2024-05-20", "pdf"],
    ["policy", "权限管理与审计方案说明", "PDF", "1.5 MB", "2024-05-18", "pdf"],
    ["faq", "常见问题（FAQ）", "DOCX", "0.9 MB", "2024-05-10", "docx"],
    ["log", "版本更新日志 v2.0", "TXT", "98 KB", "2024-05-05", "txt"]
  ];

  function documentsPage() { return filesPage(); }


  function renderDocItem(doc) {
    const id = doc.relative_path || doc[0];
    const active = id === appState.selectedDoc ? " active" : "";
    const name = displayName({ ...doc, name: doc.name || doc[1], relative_path: id }, "文档");
    const type = doc.is_dir ? "DIR" : fileType(doc);
    const size = doc.is_dir ? "文件夹" : formatBytes(doc.size_bytes ?? doc[3]);
    const time = formatStorageTime(doc.mtime || doc[4]);
    return `<article class="doc-item${active}" data-doc-id="${escapeHtml(id)}"><span class="doc-glyph ${fileGlyph(doc)}">${escapeHtml(type.slice(0, 4))}</span><div class="doc-copy"><div class="doc-title" title="${escapeHtml(name)}">${escapeHtml(name)}</div><div class="muted small">${escapeHtml(type)} · ${escapeHtml(size)} · ${escapeHtml(time)}</div><div class="path-summary">${escapeHtml(displayLocation(id))}</div></div>${iconButton("plus", "文档更多")}</article>`;
  }

  function renderDocumentQA() {
    const answer = appState.documents.answer;
    const stateBlock = appState.documents.status === "loading" ? apiStateBlock(appState.documents) : "";
    return card(`
      <div class="question-bubble"><span>${escapeHtml(appState.documents.query || "请输入文档问题")}</span><span class="muted small">本地</span></div>
      <div class="answer-header"><strong>${svg("assistant")} 文档问答</strong>${badge(answer?.ok ? "真实证据返回" : "等待提问", answer?.ok ? "success" : "neutral")}</div>
      <div class="answer-body">
        ${stateBlock || (answer?.ok ? `<p>${escapeHtml(answer.answer || "已完成文档检索。")}</p>${renderKeyValueRows([
          ["检索范围", resultStatusText(answer.path, "已选择")],
          ["召回方式", answer.retrieval_mode ? "本地索引" : "本地检索"],
          ["匹配证据", answer.evidence_count],
          ["证据状态", (answer.evidence_refs || []).length ? "已编号" : "暂无"],
          ["向量检索", answer.embedding_enabled ? "已启用" : "未启用"],
          ["云端调用", answer.cloud_used ? "是" : "否"]
        ])}` : `<p>文档问答会在 NAS 文档路径内优先走 SQLite FTS 本地召回，返回文件路径、片段与元数据证据；不会把原文直接发往云端。</p>`)}
      </div>
      <div class="answer-footer"><span class="muted small">参考来源：${(answer?.evidence || []).slice(0, 5).map((doc, i) => badge(`${i + 1} ${displayName(doc, "文档")}`, "neutral")).join(" ") || "暂无"}</span></div>
      <div class="qa-input"><input id="documentQuestion" class="control" value="${escapeHtml(appState.documents.query)}" placeholder="请输入你的问题..." aria-label="文档问答输入">${button("", { icon: "send", action: "documentsAsk" })}</div>
    `, "answer-card");
  }

  function reportsPage() {
    const stateBlock = apiStateBlock(appState.reports, "当前没有可预览报告。");
    const reports = appState.reports.items || [];
    const selected = reports.find((report) => report.id === appState.reports.selectedId) || reports[0] || null;
    const types = [...new Set(reports.map((report) => report.type).filter(Boolean))];
    return `
      ${pageHeader("报告", "汇总文件夹摘要、文档问答、证据报告、Token Budget、Gate 和地瓜日记导出。", `${button("刷新", { variant: "secondary", icon: "plus", action: "reportsRefresh" })}${button("导出选中", { icon: "download", action: "reportExport", disabled: !selected || selected.degraded })}`)}
      <div class="reports-layout">
        ${card(`${sectionTitle("报告类型")}<div class="tabs">${(types.length ? types : ["待生成"]).map((type, index) => `<button class="chip ${index === 0 ? "active" : ""}" type="button">${escapeHtml(type)}</button>`).join("")}</div>
          <div class="report-list">${stateBlock || reports.map((report, index) => renderReportItem(report, index)).join("")}</div>
          <div class="storage-meta"><span>共 ${fmtCount(reports.length)} 份报告</span><span>${appState.reports.export?.path ? "最近已导出" : "等待导出"}</span></div>`)}
        ${card(selected ? renderReportPreview(selected) : `<div class="empty-state">${svg("search")}<strong>没有报告可预览</strong><p>运行验证后会在这里显示本地报告列表。</p></div>`, "report-preview")}
      </div>
      ${renderStatePanel("报告")}
    `;
  }

  function reportDisplayTitle(report, index = 0) {
    const type = String(report?.type || "").trim();
    const base = type && type !== "unknown" ? type : "本地报告";
    return `${base} ${index + 1}`;
  }

  function renderReportItem(report, index = 0) {
    const active = report.id === appState.reports.selectedId ? " active" : "";
    const status = report.degraded ? badge("待生成", "neutral") : badge("可查看", "success");
    return `<article class="report-item${active}" data-report-id="${escapeHtml(report.id)}">
      <div>
        <strong>${escapeHtml(reportDisplayTitle(report, index))}</strong>
        <div class="path-summary">${escapeHtml(report.relative_path || report.path ? "本地报告 · 已生成" : "等待生成")}</div>
        <div class="muted small">${escapeHtml(formatStorageTime(report.mtime))} · ${escapeHtml(formatBytes(report.size_bytes || 0))}</div>
      </div>
      <div class="report-meta">${badge(report.type || "报告", "neutral")}${status}</div>
    </article>`;
  }

  function renderReportPreview(report) {
    const preview = scrubProductText(report.preview || "没有预览内容。").slice(0, 1600);
    return `
      <div class="answer-header"><strong>${escapeHtml(report.type || "报告预览")}</strong>${badge(report.degraded ? "待生成" : "可导出", report.degraded ? "neutral" : "success")}</div>
      <div class="answer-body">
        ${renderKeyValueRows([
          ["类型", report.type || "暂无"],
          ["位置", report.relative_path || report.path ? "已生成" : "待生成"],
          ["记录", report.trace_id ? "已记录" : "暂无"],
          ["大小", report.size_bytes ? formatBytes(report.size_bytes) : "暂无"]
        ])}
        <pre class="summary-pre report-pre">${escapeHtml(preview)}</pre>
      </div>
      <div class="answer-footer">
        <div class="actions">
          ${button("复制报告位置", { variant: "secondary", icon: "copy", action: "reportCopyPath", disabled: !report.path })}
          ${button("导出 Markdown", { icon: "download", action: "reportExport", disabled: report.degraded || !report.path })}
        </div>
        <span class="muted small">${appState.reports.export?.path ? "最近导出已生成" : "导出会保存在本地报告目录。"}</span>
      </div>
    `;
  }

  function tokenBudgetPage() {
    const stateBlock = apiStateBlock(appState.tokenBudget, "Token Budget 暂无真实汇总，请先运行本地评测或路由估算。");
    const summary = appState.tokenBudget.summary || {};
    const benchmark = appState.tokenBudget.benchmark?.benchmark_summary || appState.tokenBudget.benchmark || {};
    const analysis = summary.latest_analysis || {};
    const safeIdentity = summary.tokenizer_identity || {};
    return `
      ${pageHeader("Token Budget", "展示分词器身份、压缩收益、隐私路由和本地评测证据。", button("刷新", { variant: "secondary", icon: "plus", action: "tokenBudgetRefresh" }))}
      ${stateBlock || `<div class="grid two-col">
        ${card(`${sectionTitle("当前汇总")}
          <div class="token-stats">
            <div class="metric"><span class="muted small">平均降幅</span><strong>${escapeHtml(fmtRatio(analysis.average_reduction_ratio))}</strong><span class="small muted">云端输入 token</span></div>
            <div class="metric"><span class="muted small">质量通过率</span><strong>${escapeHtml(fmtRatio(analysis.quality_pass_rate))}</strong><span class="small muted">本地评测质量</span></div>
            <div class="metric"><span class="muted small">隐私检查</span><strong>${fmtCount(analysis.private_leak_count)}</strong><span class="small muted">检测到的泄漏项</span></div>
          </div>
          ${renderKeyValueRows([
            ["分词器", safeIdentity.tokenizer_name || safeIdentity.source || "Qwen 分词器"],
            ["记录状态", summary.trace_path ? "已生成" : "待生成"],
            ["原始云端 token", analysis.average_naive_cloud_tokens ?? "暂无"],
            ["优化后 token", analysis.average_optimized_cloud_tokens ?? "暂无"]
          ])}`)}
        ${card(`${sectionTitle("Benchmark 证据")}
          ${renderKeyValueRows([
            ["评测状态", appState.tokenBudget.benchmark?.ok ? "已通过" : "待复查"],
            ["用例数", benchmark.case_count || benchmark.total_cases || (Array.isArray(benchmark.cases) ? benchmark.cases.length : "暂无")],
            ["报告状态", benchmark.report_path || benchmark.path ? "已生成" : "待生成"],
            ["云端默认外发", "禁止"]
          ])}
          <div class="soft-note">页面仅展示 Token Budget 和 Privacy Router 的统计证据；Qwen 只做理解/摘要，不获得工具执行权。</div>`)}
      </div>
      <div class="grid" style="margin-top:16px">
        ${card(`${sectionTitle("路由分布", "生成一次估算", "tokenBudgetEstimate")}
          <div class="source-list">${renderTokenRoutes(analysis, benchmark)}</div>`)}
      </div>`}
      ${renderStatePanel("Token Budget")}
    `;
  }

  function renderTokenRoutes(analysis, benchmark) {
    const routeRows = Array.isArray(benchmark.route_distribution)
      ? benchmark.route_distribution
      : Array.isArray(analysis.route_distribution)
        ? analysis.route_distribution
        : [];
    if (!routeRows.length) {
      return `<div class="empty-state compact">${svg("calendar")} 暂无路由分布数据。运行一次估算后会显示真实路由结果。</div>`;
    }
    const palette = ["#2563eb", "#06b6d4", "#10b981", "#d946ef", "#fb7185", "#f59e0b", "#64748b", "#14b8a6"];
    return routeRows.slice(0, 8).map((item, index) => {
      const route = item.route || item.name || `路由 ${index + 1}`;
      const tokens = item.tokens || item.count || item.total_tokens || "暂无";
      const share = item.share || item.percent || "暂无";
      const color = item.color || palette[index % palette.length];
      return `<div class="route-row"><span class="route-color" style="background:${escapeHtml(color)}"></span><span>${escapeHtml(route)}</span><span class="muted">${escapeHtml(tokens)}</span><strong>${escapeHtml(share)}</strong></div>`;
    }).join("");
  }

  function journalPage() {
    const stateBlock = apiStateBlock(appState.journal, "Journal 当前没有事件，先新增一条手动记录。");
    const events = appState.journal.events || [];
    return `
      ${pageHeader("地瓜日记", "记录与沉淀日常工作进展，沉淀知识，持续成长。")}
      <div class="filter-bar" style="justify-content:space-between;margin-bottom:16px">
        <div class="tabs">${[["日总结", "daily"], ["周总结", "weekly"], ["月总结", "monthly"], ["年总结", "yearly"]].map((t, i) => `<button class="chip ${i === 0 ? "active" : ""}" type="button" data-action="journalGenerate" data-period="${t[1]}">${t[0]}</button>`).join("")}</div>
        <div class="actions">${button(appState.journal.text || "读取日记索引", { variant: "secondary", icon: "calendar", action: "journalRefresh" })}</div>
      </div>
      <div class="journal-grid">
        ${card(`${sectionTitle("真实时间线")}${stateBlock || `<div class="timeline-line">${events.slice(0, 12).map((item) => `<div class="timeline-row"><strong class="muted">${escapeHtml(String(item.event_ts || "").slice(11, 16) || "本地")}</strong><span class="timeline-dot">${svg("check")}</span><div><strong>${escapeHtml(item.title || item.event_type || "Journal 事件")}</strong><p class="muted small">${escapeHtml(item.summary || "")}</p><span class="muted small">${svg("docs")} ${escapeHtml(item.source || "manual")}</span></div></div>`).join("")}</div>`}
          <div class="login-stack" style="margin-top:16px">
            <input id="journalTitle" class="control" value="网页端实机验证记录" aria-label="笔记标题">
            <textarea id="journalBody" class="textarea compact-textarea" aria-label="笔记内容">验证网页端 Journal 手动记录、周期总结和 Markdown 导出流程。</textarea>
            ${button("手动记录", { variant: "secondary", icon: "plus", action: "journalManual" })}
          </div>`)}
        ${renderJournalEditor()}
        <aside class="side-stack">
          ${contextPanel("Journal 状态", renderKeyValueRows([["状态", appState.journal.status], ["事件数", events.length], ["最近导出", appState.journal.export?.path || "暂无"], ["云端生成", "禁用"]]), "刷新", "journalRefresh")}
          ${contextPanel("引用证据", events.slice(0, 5).map((item) => `<div class="mini-row"><span>${svg("docs")} ${escapeHtml((item.evidence_refs || [item.source || "local"])[0])}</span><span class="muted small">本地</span></div>`).join("") || `<div class="empty-state compact">暂无证据</div>`, "刷新", "journalRefresh")}
          ${contextPanel("安全边界", `<article class="manual-note">Journal 只保存脱敏摘要与证据引用，不保存原始私有正文；周期总结走本地 deterministic summary。<div class="row-meta"><span>local-first</span>${svg("lock")}</div></article>`, "生成", "journalGenerate")}
        </aside>
      </div>
      ${renderStatePanel("地瓜日记")}
    `;
  }

  function renderJournalEditor() {
    const summary = appState.journal.summary;
    const markdown = summary?.markdown || "点击“生成总结”后，这里会显示由本地 Journal 引擎生成的日/周/月/年总结。";
    return card(`
      <div class="answer-header"><strong>${escapeHtml(summary?.title || "周期总结")}</strong><div class="actions">${badge(summary ? "已生成" : "等待生成", summary ? "success" : "neutral")}<span class="muted small">事件数：${fmtCount(summary?.event_count || 0)}</span></div></div>
      <div class="editor-toolbar">${["H1", "H2", "H3", "加粗", "斜体", "列表", "任务", "链接", "代码"].map((label) => `<button class="tool-button" type="button" aria-label="${escapeHtml(label)}">${escapeHtml(label)}</button>`).join("")}</div>
      <div class="markdown-body">
        <pre class="summary-pre">${escapeHtml(markdown)}</pre>
      </div>
      <div class="answer-footer"><div class="actions">${button("生成总结", { icon: "assistant", action: "journalGenerate" })}${button("刷新", { variant: "secondary", icon: "save", action: "journalRefresh" })}${button("导出 Markdown", { variant: "secondary", icon: "download", action: "journalExport" })}</div><span class="muted small">由本地 Journal 引擎生成，内容仅存储在本地设备。</span></div>
    `, "editor-card");
  }

  function auditPage() {
    const stateBlock = apiStateBlock(appState.audit, "当前还没有文件操作审计记录。");
    const realRows = (appState.audit.operations || []).map((row, index) => [
      formatStorageTime(row.created_at || row.ts),
      row.user || appState.authUser?.username || "web",
      auditServiceLabel(row),
      auditOperationLabel(row),
      String(row.status || "").includes("disabled") ? "已拒绝" : "已记录",
      String(row.status || "").includes("disabled") ? "danger" : "success",
      row.duration || "暂无",
      auditResourceLabel(row),
      auditRecordId(row, index)
    ]);
    const query = (appState.audit.query || "").trim().toLowerCase();
    const rows = realRows.filter((row) => {
      if (!query) return true;
      return row.some((cell) => String(cell || "").toLowerCase().includes(query));
    });
    const selected = rows.find((row) => row[8] === appState.selectedAuditRecord) || rows[0] || null;
    return `
      ${pageHeader("审计", "记录与审计所有 AI 助手执行行为，帮助排查与合规审计。")}
      <section class="panel" style="padding:16px;margin-bottom:16px">
        <div class="filter-bar">
          <input class="control" value="最近 50 条本地记录" aria-label="审计范围" readonly>
          <select class="control"><option>全部用户</option></select>
          <select class="control"><option>全部助手</option></select>
          <select class="control"><option>全部操作</option></select>
          <select class="control"><option>全部状态</option></select>
          ${button("重置", { variant: "secondary", action: "auditReset" })}
          ${button("筛选", { icon: "filter", action: "auditApplyFilter" })}
          <input id="auditSearch" class="control search" value="${escapeHtml(appState.audit.query || "")}" placeholder="搜索记录编号、用户、操作或资源" aria-label="搜索审计">
        </div>
      </section>
      <div class="audit-layout">
        <section class="panel">
          ${stateBlock || (rows.length ? `<div class="table-wrap">
            <table class="data-table audit-table">
              <thead><tr><th>时间</th><th>用户</th><th>本地服务</th><th>操作</th><th>状态</th><th>耗时</th><th>资源</th><th>记录编号</th><th>更多</th></tr></thead>
              <tbody>${rows.map((row) => `<tr class="${row[8] === appState.selectedAuditRecord ? "selected" : ""}" data-record-id="${row[8]}"><td>${escapeHtml(row[0])}</td><td>${escapeHtml(row[1])}</td><td>${escapeHtml(row[2])}</td><td>${escapeHtml(row[3])}</td><td>${badge(row[4], row[5])}</td><td>${escapeHtml(row[6])}</td><td>${escapeHtml(row[7])}</td><td><button class="link-button record-id" type="button" data-record-id="${escapeHtml(row[8])}">${escapeHtml(row[8])}</button></td><td>${iconButton("plus", "更多")}</td></tr>`).join("")}</tbody>
            </table>
          </div>
          <div class="table-footer"><span class="muted small">共 ${fmtCount(rows.length)} 条</span><div class="pagination">${button("刷新", { variant: "secondary", action: "auditRefresh" })}${button("10 条/页", { variant: "secondary", action: "auditPageSize" })}</div></div>` : `<div class="empty-state">${svg("audit")}<strong>暂无审计记录</strong><p>当前没有可展示的本地操作日志。执行文件、备份、笔记或助手动作后会在这里出现。</p><div class="actions">${button("刷新", { variant: "secondary", action: "auditRefresh" })}</div></div>`)}
        </section>
        ${card(renderAuditDetail(selected), "audit-detail")}
      </div>
      ${renderStatePanel("审计")}
    `;
  }

  function renderAuditDetail(row) {
    if (!row) {
      return `<div class="empty-state">${svg("search")}<strong>没有匹配的审计记录</strong><p>调整搜索条件或点击重置重新读取本地审计日志。</p></div>`;
    }
    return `
      <div class="answer-header"><strong>记录详情</strong>${iconButton("plus", "关闭")}</div>
      <div class="answer-body">
        <div class="detail-hero"><span class="icon-chip">${svg("assistant")}</span><div><strong class="record-id">${row[8]}</strong><div class="muted small">${row[0]}</div></div>${badge(row[4], row[5])}</div>
        <div class="detail-section"><div class="row-meta"><strong>处理摘要</strong>${badge(row[4], row[5])}</div>${renderKeyValueRows([
          ["执行状态", row[4]],
          ["用户", row[1]],
          ["操作", row[3]],
          ["资源", row[7]]
        ])}</div>
        <div class="detail-section"><strong>处理信息</strong>${renderKeyValueRows([
          ["处理方式", "本地受控 API"],
          ["本地服务", row[2]],
          ["耗时", row[6]],
          ["记录编号", row[8]]
        ])}</div>
        <details><summary>脱敏说明</summary><p class="muted small">审计页只展示脱敏后的摘要字段，不展示原始私有正文或完整文件路径。</p></details>
      </div>
    `;
  }

  function renderStatePanel(pageName) {
    if (!appState.debugStatePanels) return "";
    return `
      <section class="state-panel" aria-label="${escapeHtml(pageName)}页面状态">
        <div class="state-card"><strong>加载中</strong><div class="skeleton-line short"></div><div class="skeleton-line"></div><div class="skeleton-line medium"></div></div>
        <div class="state-card"><strong>暂无内容</strong><div class="empty-state compact">${svg("search")} 无匹配内容</div></div>
        <div class="state-card error"><strong>读取失败</strong>本地服务暂不可用，已保留只读视图。</div>
        <div class="state-card success"><strong>已完成</strong>更改已保存到本地。</div>
        <div class="state-card"><strong>需授权</strong>${button("等待授权", { variant: "secondary", disabled: true })}</div>
      </section>
    `;
  }

  function agentRuntimePage() {
    const state = appState.agentRuntime;
    const status = state.statusPayload || {};
    const flags = status.feature_flags || {};
    const metrics = state.evalStatus?.latest_eval?.metrics || {};
    const manifest = state.manifest?.manifest?.validation || state.manifest?.validation || {};
    const memory = state.memory || status.memory || {};
    const multimodal = state.multimodal || status.multimodal_index || {};
    const contextPack = state.contextPack || {};
    return `
      ${pageHeader("运行层", "管理本地上下文、记忆、索引、文档问答和质量评测。", `${button("刷新", { icon: "plus", action: "agentRuntimeRefresh" })}${button("生成上下文包", { variant: "secondary", icon: "assistant", action: "agentRuntimeContextPack" })}`)}
      ${apiStateBlock(state, "Agent Runtime 暂无状态。") || `<div class="grid two-col">
        ${card(`${sectionTitle("运行边界")} ${renderKeyValueRows([
          ["状态", status.ok ? "在线" : "需复查"],
          ["上下文包", flags.context_pack_enabled ? "启用" : "禁用"],
          ["本地记忆", flags.memory_manager_enabled ? "启用" : "禁用"],
          ["多模态索引", flags.multimodal_index_enabled ? "启用" : "禁用"],
          ["文档问答", flags.rag_enabled ? "启用" : "禁用"],
          ["公网暴露", status.public_mcp_exposed ? "开启" : "关闭"],
          ["Qwen 工具权限", status.qwen_execution_authority ? "有" : "无"],
          ["私有原文云外发", status.cloud_private_raw_egress ? "允许" : "禁止"]
        ])}`)}
        ${card(`${sectionTitle("本地能力清单")} ${renderKeyValueRows([
          ["工具数", manifest.tool_count || 0],
          ["缺失工具", (manifest.missing_tool_ids || []).length],
          ["写操作边界", (manifest.mutating_not_dispatcher_only || []).length ? "需复查" : "受控执行"],
          ["公网暴露", manifest.public_mcp_exposed ? "开启" : "关闭"],
          ["Qwen 执行", manifest.qwen_tool_execution_authority ? "开启" : "关闭"]
        ])}`)}
        ${card(`${sectionTitle("本地记忆与索引")} ${renderKeyValueRows([
          ["记忆事件", memory.events || 0],
          ["结构化事实", memory.facts || 0],
          ["原文留存", memory.raw_content_rows ? "需复查" : "未暴露"],
          ["索引项", multimodal.indexed_count || 0],
          ["文档", multimodal.counts?.document || 0],
          ["图片", multimodal.counts?.image || 0],
          ["视频", multimodal.counts?.video || 0],
          ["音频", multimodal.counts?.audio || 0]
        ])}`)}
        ${card(`${sectionTitle("质量评测")} ${renderKeyValueRows([
          ["结论", state.evalStatus?.latest_eval?.verdict || "待生成"],
          ["用例数", metrics.eval_total_cases || "暂无"],
          ["文档问答用例", metrics.rag_case_count || "暂无"],
          ["引用覆盖", metrics.rag_citation_coverage != null ? fmtRatio(metrics.rag_citation_coverage) : "暂无"],
          ["无证据拒答", metrics.rag_no_evidence_refusal_rate != null ? fmtRatio(metrics.rag_no_evidence_refusal_rate) : "暂无"],
          ["隐私泄漏", metrics.private_leak_count || 0]
        ])}`)}
      </div>`}
      <div class="grid two-col" style="margin-top:16px">
        ${card(`${sectionTitle("上下文包")} ${contextPack.pack_id ? renderKeyValueRows([
          ["上下文包", contextPack.pack_id],
          ["证据引用", (contextPack.evidence_refs || []).length],
          ["权限拒绝", contextPack.acl_denied_count],
          ["Token 估算", contextPack.token_estimate],
          ["隐私泄漏", contextPack.private_leak_count]
        ]) : `<div class="empty-state compact">${svg("assistant")} 点击“生成上下文包”后显示本地上下文打包结果。</div>`}`)}
        ${card(`${sectionTitle("本地数据存储")} ${renderKeyValueRows([
          ["记忆库", status.datastores?.memory_db ? "已配置" : "未配置"],
          ["多模态索引库", status.datastores?.multimodal_db ? "已配置" : "未配置"],
          ["文档问答库", status.datastores?.rag_db ? "已配置" : "未配置"],
          ["原文状态", "不在状态接口返回"]
        ])}`)}
      </div>
      ${renderStatePanel("Agent Runtime")}
    `;
  }

  function mediaPhotoTitle(photo) {
    return photo.display_name_zh || photo.suggested_filename_zh || photo.title_redacted || photo.name_redacted || photo.asset_id || "照片";
  }

  function mediaPhotoPreviewUrl(photo) {
    if (photo.preview_url) return photo.preview_url;
    if (photo.path_hash) return `/api/media/preview?path_hash=${encodeURIComponent(photo.path_hash)}`;
    return "";
  }

  function thumbnailPreviewUrl(previewUrl) {
    if (!previewUrl) return "";
    if (/(?:\?|&)variant=/.test(previewUrl)) {
      return previewUrl.replace(/([?&]variant=)[^&#]*/i, "$1thumbnail");
    }
    return `${previewUrl}${previewUrl.includes("?") ? "&" : "?"}variant=thumbnail`;
  }

  function renderMediaPhotoItem(photo) {
    const title = mediaPhotoTitle(photo);
    const previewUrl = mediaPhotoPreviewUrl(photo);
    const categories = mediaPhotoCategoryNames(photo).slice(0, 3);
    const meta = [
      formatBytes(photo.size_bytes),
      formatStorageTime(photo.taken_at || photo.mtime)
    ].filter(Boolean).join(" · ");
    const openAttrs = previewUrl
      ? ` tabindex="0" role="button" aria-label="双击打开图片预览" data-image-preview-url="${escapeHtml(previewUrl)}" data-image-title="图片预览" data-image-meta="${escapeHtml(meta || "本地照片")}" data-image-match="相册预览 · 本地"`
      : "";
    const trashButton = previewUrl && photo.path_hash
      ? storageTrashButton({ kind: "image", title, pathHash: photo.path_hash, previewUrl })
      : "";
    const thumb = previewUrl
      ? `<div class="search-thumb media-photo-thumb has-preview"><img class="search-preview-image" alt="图片预览" data-preview-url="${escapeHtml(thumbnailPreviewUrl(previewUrl))}" loading="lazy" decoding="async" hidden><span class="thumb-loading">加载预览</span></div>`
      : `<span class="doc-glyph png">IMG</span>`;
    return `<article class="doc-item media-photo-item${previewUrl ? " is-openable" : ""}${trashButton ? " has-actions" : ""}"${openAttrs}>
      ${thumb}
      ${trashButton}
      <div class="doc-copy">
        <div class="media-photo-meta">${escapeHtml(meta || "本地相册索引")}</div>
        <div class="result-tags">${categories.length ? categories.map((name) => `<span class="result-tag">${escapeHtml(name)}</span>`).join("") : `<span class="result-tag">待整理</span>`}</div>
      </div>
    </article>`;
  }

  function renderMediaAlbumItem(album, selectedAlbumName) {
    const name = album.name || album.album_name || "相册";
    const count = Number(album.item_count || album.photo_count || 0);
    const active = selectedAlbumName === name ? " active" : "";
    return `<button class="doc-item media-album-item${active}" type="button" data-action="mediaSelectAlbum" data-album-name="${escapeHtml(name)}">
      <span class="doc-glyph png">ALB</span>
      <div class="doc-copy">
        <div class="doc-title">${escapeHtml(name)}</div>
        <div class="muted small">${escapeHtml(album.description || "本地相册记录")} · ${fmtCount(count)} 张</div>
      </div>
      ${svg("chevron")}
    </button>`;
  }

  function renderMediaPhotoList(photos, selectedAlbumName) {
    if (appState.media.selectedAlbumStatus === "loading") {
      return `<div class="skeleton-list"><span></span><span></span><span></span></div>`;
    }
    if (appState.media.selectedAlbumStatus === "error") {
      return `<div class="empty-state compact">${svg("alert")} ${escapeHtml(appState.media.selectedAlbumError || "相册读取失败")}</div>`;
    }
    if (!photos.length) {
      return `<div class="empty-state compact">${selectedAlbumName ? "这个相册还没有绑定照片。" : "暂无照片索引"}</div>`;
    }
    return `<div class="doc-list media-photo-list">${photos.slice(0, 500).map(renderMediaPhotoItem).join("")}</div>`;
  }

  function renderMediaUploadInput() {
    return `<input id="mediaUploadInput" type="file" accept="image/*" hidden aria-hidden="true">`;
  }

  function renderMediaUploadStatus() {
    if (appState.media.uploadStatus === "loading") {
      return `<div class="soft-note media-upload-status">${svg("upload")} 正在上传图片并刷新本地相册。</div>`;
    }
    if (appState.media.uploadStatus === "error") {
      return `<div class="soft-note error-note media-upload-status">${svg("alert")} ${escapeHtml(appState.media.uploadError || "图片上传失败")}</div>`;
    }
    return "";
  }

  function mediaPage() {
    const stateBlock = apiStateBlock(appState.media, "还没有媒体索引记录。");
    const summary = appState.media.summary || {};
    const stats = summary.stats || {};
    const photos = summary.photos || [];
    const categories = mediaPhotoCategoryEntries(photos);
    const selectedCategory = String(appState.aiAlbum.selectedCategory || "");
    const visiblePhotos = selectedCategory
      ? photos.filter((photo) => mediaPhotoCategoryNames(photo).includes(selectedCategory))
      : photos;
    const auto = appState.aiAlbum.autoOrganize || {};
    const autoLabel = appState.aiAlbum.autoOrganizeStatus === "loading" ? "检查中" : ((auto.changed || auto.view_rebuilt) ? "已自动整理" : "已是最新");
    const photoSectionTitle = selectedCategory ? `分类：${selectedCategory}` : "全部图片";
    const uploadBusy = appState.media.uploadStatus === "loading";
    return `
      ${pageHeader("相册", "NAS 图片自动增量整理和本地 AI 分类。", `${button(uploadBusy ? "上传中" : "上传图片", { icon: "upload", action: "mediaUploadChoose", disabled: uploadBusy })}${button("刷新", { variant: "secondary", icon: "plus", action: "mediaRefresh" })}`)}
      ${renderMediaUploadInput()}
      ${renderMediaUploadStatus()}
      <div class="ai-album-kpis">
        <div><span>图片</span><strong>${fmtCount(photos.length || stats.photo_count || 0)}</strong></div>
        <div><span>分类</span><strong>${fmtCount(categories.length)}</strong></div>
        <div><span>自动整理</span><strong>${escapeHtml(autoLabel)}</strong></div>
        <div><span>最近索引</span><strong>${escapeHtml(formatStorageTime(stats.last_indexed_at) || "暂无")}</strong></div>
      </div>
      ${stateBlock || `<div class="ai-album-tabs" role="tablist">
        <button class="chip${selectedCategory ? "" : " active"}" type="button" data-action="aiAlbumCategory" data-category="">全部 <span>${fmtCount(photos.length)}</span></button>
        ${categories.map(([name, count]) => `<button class="chip${selectedCategory === name ? " active" : ""}" type="button" data-action="aiAlbumCategory" data-category="${escapeHtml(name)}">${escapeHtml(name)} <span>${fmtCount(count)}</span></button>`).join("")}
      </div>
      ${card(`${sectionTitle(photoSectionTitle, "", "")}${renderMediaPhotoList(visiblePhotos, "")}`)}`}
    `;
  }

  function renderMediaOrganizeStatusPanel(status, totalImages, categoryCount) {
    const pending = Number(status?.pending_count ?? 0);
    const organized = Number(status?.organized_count ?? Math.max(0, totalImages - pending));
    const busy = appState.aiAlbum.organizeRunStatus === "loading";
    const lastRun = appState.aiAlbum.organizeLastRun || {};
    const methodCounts = lastRun.method_counts || {};
    const methodText = lastRun.processed_count != null
      ? `本次处理 ${fmtCount(lastRun.processed_count)} 张，CLIP ${fmtCount(methodCounts.clip_similarity || 0)} 张，证据规则 ${fmtCount(methodCounts.evidence_rules || 0)} 张，兜底 ${fmtCount(methodCounts.fallback_other || 0)} 张`
      : "已整理图片会跳过，只处理待整理图片";
    const stateText = busy
      ? "正在整理未归类图片"
      : pending > 0
        ? `还有 ${fmtCount(pending)} 张待整理`
        : totalImages > 0
          ? "所有图片已整理"
          : "暂无图片";
    return `
      <section class="media-organize-panel" aria-label="相册整理状态">
        <div class="media-organize-head">
          <div>
            <strong>${escapeHtml(stateText)}</strong>
            <span>${escapeHtml(methodText)}</span>
          </div>
          ${button(busy ? "整理中" : pending > 0 ? "一键整理" : "已整理", { icon: "check", action: "mediaOrganizeNow", disabled: busy || pending <= 0 })}
        </div>
        <div class="media-organize-counts">
          <span>总图片 <strong>${fmtCount(totalImages)}</strong></span>
          <span>已整理 <strong>${fmtCount(organized)}</strong></span>
          <span>待整理 <strong>${fmtCount(pending)}</strong></span>
          <span>主分类 <strong>${fmtCount(categoryCount)}</strong></span>
        </div>
      </section>
    `;
  }

  function mediaPageV2() {
    const stateBlock = apiStateBlock(appState.media, "还没有媒体索引记录。");
    const summary = appState.media.summary || {};
    const stats = summary.stats || {};
    const photos = summary.photos || [];
    const organize = appState.aiAlbum.organizeStatus || {};
    const primaryCategories = aiAlbumPrimaryCategories();
    const categories = mediaPhotoCategoryEntries(photos);
    const selectedCategory = String(appState.aiAlbum.selectedCategory || "");
    const visiblePhotos = selectedCategory
      ? photos.filter((photo) => mediaPhotoCategoryNames(photo).includes(selectedCategory))
      : photos;
    const uploadBusy = appState.media.uploadStatus === "loading";
    const organizeBusy = appState.aiAlbum.organizeRunStatus === "loading";
    const totalImages = photos.length;
    const primaryStates = photos.map(mediaPhotoPrimaryStatus).filter(Boolean);
    const pendingCount = primaryStates.filter((item) => item.state === "pending").length;
    const organizedCount = primaryStates.length
      ? primaryStates.filter((item) => item.state === "organized").length
      : Math.max(0, totalImages - categories.find(([name]) => name === "待整理")?.[1] || 0);
    const categoryCount = categories.filter(([name]) => name !== "待整理").length;
    const scopedOrganize = { ...organize, total_images: totalImages, pending_count: pendingCount, organized_count: organizedCount };
    const photoSectionTitle = selectedCategory ? `分类：${selectedCategory}` : "全部图片";
    const headerActions = [
      button(uploadBusy ? "上传中" : "上传图片", { icon: "upload", action: "mediaUploadChoose", disabled: uploadBusy || organizeBusy || appState.media.status === "auth" }),
      button(pendingCount > 0 ? "一键整理" : "已整理", { icon: "check", action: "mediaOrganizeNow", disabled: organizeBusy || pendingCount <= 0 }),
      button("刷新", { variant: "secondary", icon: "plus", action: "mediaRefresh", disabled: organizeBusy })
    ].join("");
    if (stateBlock) {
      return `
        ${pageHeader("相册", "查看 NAS 图片与本地 AI 主分类。", headerActions)}
        ${renderMediaUploadInput()}
        ${renderMediaUploadStatus()}
        ${card(stateBlock, "media-state-card")}
        ${renderStatePanel("相册")}
      `;
    }
    return `
      ${pageHeader("相册", "NAS 图片自动增量整理和本地 AI 主分类。", headerActions)}
      ${renderMediaUploadInput()}
      ${renderMediaUploadStatus()}
      ${renderMediaOrganizeStatusPanel(scopedOrganize, totalImages, categoryCount)}
      <div class="ai-album-kpis">
        <div><span>总图片</span><strong>${fmtCount(totalImages)}</strong></div>
        <div><span>已整理</span><strong>${fmtCount(organizedCount)}</strong></div>
        <div><span>待整理</span><strong>${fmtCount(pendingCount)}</strong></div>
        <div><span>最近索引</span><strong>${escapeHtml(formatStorageTime(stats.last_indexed_at) || "-")}</strong></div>
      </div>
      ${stateBlock || `<div class="ai-album-tabs" role="tablist">
        <button class="chip${selectedCategory ? "" : " active"}" type="button" data-action="aiAlbumCategory" data-category="">全部 <span>${fmtCount(photos.length)}</span></button>
        ${categories.map(([name, count]) => `<button class="chip${selectedCategory === name ? " active" : ""}" type="button" data-action="aiAlbumCategory" data-category="${escapeHtml(name)}">${escapeHtml(name)} <span>${fmtCount(count)}</span></button>`).join("")}
      </div>
      ${card(`${sectionTitle(photoSectionTitle, "", "")}${renderMediaPhotoList(visiblePhotos, "")}`)}`}
    `;
  }

  function aiAlbumAssetId(asset) {
    return String(asset?.asset_id || asset?.id || asset?.media_id || "");
  }

  function aiAlbumAssetTitle(asset, fallback = "本地素材") {
    return asset?.display_name_zh || asset?.suggested_filename_zh || asset?.title_redacted || asset?.name_redacted || aiAlbumAssetId(asset) || fallback;
  }

  function aiAlbumCategoryNames(asset) {
    const values = [];
    for (const key of ["category_names", "categories", "tags", "object_labels"]) {
      const current = asset?.[key];
      if (Array.isArray(current)) values.push(...current);
    }
    if (asset?.asset_kind) values.push(asset.asset_kind);
    return Array.from(new Set(values.map((item) => String(item || "").trim()).filter(Boolean)));
  }

  function mediaTitleKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\.(jpg|jpeg|png|webp|bmp|gif|tif|tiff)$/i, "")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function aiAlbumMediaPhotoForAsset(asset) {
    const assetId = aiAlbumAssetId(asset);
    const photos = Array.isArray(appState.aiAlbum.mediaPhotos) ? appState.aiAlbum.mediaPhotos : [];
    if (assetId) {
      const exact = photos.find((photo) => String(photo.asset_id || "") === assetId);
      if (exact) return exact;
    }
    const title = mediaTitleKey(asset?.title_redacted || asset?.suggested_filename_zh || asset?.display_name_zh || "");
    return title ? photos.find((photo) => mediaTitleKey(photo.title_redacted || photo.suggested_filename_zh || photo.display_name_zh || "") === title) || null : null;
  }

  function mediaPhotoAiAsset(photo) {
    const assets = Array.isArray(appState.aiAlbum.assets) ? appState.aiAlbum.assets : [];
    const assetId = String(photo?.asset_id || "");
    if (assetId) {
      const exact = assets.find((asset) => aiAlbumAssetId(asset) === assetId);
      if (exact) return exact;
    }
    const title = mediaTitleKey(photo?.title_redacted || photo?.suggested_filename_zh || photo?.display_name_zh || "");
    return title ? assets.find((asset) => mediaTitleKey(asset?.title_redacted || asset?.suggested_filename_zh || asset?.display_name_zh || "") === title) || null : null;
  }

  function aiAlbumPrimaryCategories() {
    const status = appState.aiAlbum.organizeStatus || {};
    return Array.isArray(status.categories) ? status.categories : [];
  }

  function mediaPhotoPrimaryStatus(photo) {
    const status = appState.aiAlbum.organizeStatus || {};
    const items = Array.isArray(status.photo_status) ? status.photo_status : [];
    if (!items.length) return null;
    const assetId = String(photo?.asset_id || "");
    const pathHash = String(photo?.path_hash || "");
    return items.find((item) => (assetId && String(item.asset_id || "") === assetId) || (pathHash && String(item.path_hash || "") === pathHash)) || null;
  }

  function mediaPhotoCategoryNames(photo) {
    const primary = mediaPhotoPrimaryStatus(photo);
    if (primary?.state === "organized" && primary.category_name) return [String(primary.category_name)];
    if (primary?.state === "pending") return ["待整理"];
    const asset = mediaPhotoAiAsset(photo);
    if (!asset) return [];
    const categories = aiAlbumCategoryNames(asset).filter((name) => !/^image$|^photo$|^本地素材$/i.test(String(name || "")));
    const meaningful = categories.filter((name) => !/^待整理$/i.test(String(name || "")));
    return meaningful.length ? meaningful : ["待整理"];
  }

  function mediaPhotoCategoryEntries(photos) {
    const counts = new Map();
    for (const photo of photos || []) {
      for (const name of mediaPhotoCategoryNames(photo)) {
        const key = String(name || "").trim();
        if (!key) continue;
        counts.set(key, Number(counts.get(key) || 0) + 1);
      }
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]), "zh-CN"));
  }

  function aiAlbumPreviewUrl(asset) {
    const photo = aiAlbumMediaPhotoForAsset(asset);
    if (!photo) return "";
    return mediaPhotoPreviewUrl(photo);
  }

  function aiAlbumAssetMeta(asset) {
    const photo = aiAlbumMediaPhotoForAsset(asset) || {};
    return [
      asset?.modality || photo.extension || "asset",
      photo.size_bytes ? formatBytes(photo.size_bytes) : "",
      formatStorageTime(asset?.created_at || asset?.taken_at || photo.taken_at || photo.mtime)
    ].filter(Boolean).join(" · ");
  }

  function aiAlbumFacetEntries(name, limit = 10) {
    const facets = appState.aiAlbum.facets?.facets || appState.aiAlbum.facets || {};
    const values = facets?.[name] || {};
    if (!values || typeof values !== "object" || Array.isArray(values)) return [];
    return Object.entries(values)
      .map(([key, value]) => [key, Number(value || 0)])
      .filter(([key]) => key)
      .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]), "zh-CN"))
      .slice(0, limit);
  }

  function aiAlbumSmartCategoryEntries(limit = 10) {
    const categories = Array.isArray(appState.aiAlbum.smartCategories) ? appState.aiAlbum.smartCategories : [];
    return categories
      .map((item) => [
        item.name || item.category_name || item.label || item.id || "分类",
        Number(item.item_count || item.asset_count || item.count || 0)
      ])
      .filter(([, count]) => count > 0)
      .slice(0, limit);
  }

  function aiAlbumAllCategories() {
    const merged = new Map();
    for (const [name, count] of [...aiAlbumFacetEntries("category", 16), ...aiAlbumSmartCategoryEntries(16)]) {
      const key = String(name || "").trim();
      if (!key) continue;
      merged.set(key, Math.max(Number(merged.get(key) || 0), Number(count || 0)));
    }
    return Array.from(merged.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN")).slice(0, 18);
  }

  function aiAlbumMatchesTab(asset, tab) {
    const text = `${asset?.modality || ""} ${asset?.asset_kind || ""} ${aiAlbumCategoryNames(asset).join(" ")} ${asset?.summary_redacted || ""}`.toLowerCase();
    const includesAny = (terms) => terms.some((term) => text.includes(term));
    if (tab === "photos") return includesAny(["image", "photo", "照片"]);
    if (tab === "videos") return includesAny(["video", "视频"]);
    if (tab === "documents") return includesAny(["document", "文档", "资料", "课程"]);
    if (tab === "people") return includesAny(["person", "people", "人物", "人像", "上衣", "服装"]);
    if (tab === "invoices") return includesAny(["invoice", "receipt", "票据", "发票", "收据"]);
    if (tab === "contracts") return includesAny(["contract", "合同", "协议"]);
    return true;
  }

  function aiAlbumVisibleAssets(tabOverride = "") {
    const state = appState.aiAlbum;
    const source = Array.isArray(state.searchResults) ? state.searchResults : state.assets;
    const activeTab = tabOverride || state.activeTab || "all";
    const selectedCategory = String(state.selectedCategory || "");
    return (source || []).filter((asset) => {
      const categoryText = aiAlbumCategoryNames(asset).join(" ");
      const categoryOk = !selectedCategory || categoryText.includes(selectedCategory);
      return categoryOk && aiAlbumMatchesTab(asset, activeTab);
    });
  }

  function aiAlbumSelectedAsset() {
    const visible = aiAlbumVisibleAssets();
    const selectedId = appState.aiAlbum.selectedAssetId;
    return visible.find((asset) => aiAlbumAssetId(asset) === selectedId) || visible[0] || null;
  }

  function aiAlbumTabItems() {
    const all = Array.isArray(appState.aiAlbum.searchResults) ? appState.aiAlbum.searchResults : appState.aiAlbum.assets;
    const countFor = (tab) => (all || []).filter((asset) => aiAlbumMatchesTab(asset, tab)).length;
    return [
      ["all", "全部", (all || []).length],
      ["photos", "照片", countFor("photos")],
      ["people", "人物/服装", countFor("people")],
      ["invoices", "票据", countFor("invoices")],
      ["contracts", "合同", countFor("contracts")],
      ["documents", "资料", countFor("documents")],
      ["videos", "视频", countFor("videos")]
    ];
  }

  function renderAiAlbumSearchBlock() {
    const state = appState.aiAlbum;
    const blocked = state.blockedQuery;
    const searchInfo = state.searchStatus === "loading"
      ? `<div class="ai-album-search-state">${svg("search")} 正在检索本地索引</div>`
      : state.searchStatus === "error"
        ? `<div class="soft-note error-note">${svg("alert")} ${escapeHtml(state.searchError || "搜索失败")}</div>`
        : blocked
          ? `<div class="soft-note warning-note">${svg("lock")} 已拦截身份识别类查询：${escapeHtml(blocked.query)}</div>`
          : Array.isArray(state.searchResults)
            ? `<div class="ai-album-search-state">${svg("check")} 当前显示 ${fmtCount(state.searchResults.length)} 条搜索结果</div>`
            : "";
    return `
      <section class="ai-album-toolbar">
        <div class="ai-album-search">
          ${svg("search")}
          <input id="aiAlbumSearch" class="control" value="${escapeHtml(state.query || "")}" placeholder="搜索：票据发票、穿白色上衣的人、合同资料..." aria-label="相册搜索">
          ${button("搜索", { icon: "search", action: "aiAlbumSearch" })}
        </div>
        <div class="ai-album-presets">
          <button class="chip" type="button" data-action="aiAlbumPreset" data-query="票据发票">票据发票</button>
          <button class="chip" type="button" data-action="aiAlbumPreset" data-query="穿白色上衣的人">白色上衣</button>
          <button class="chip" type="button" data-action="aiAlbumPreset" data-query="合同资料">合同资料</button>
          <button class="chip" type="button" data-action="aiAlbumPreset" data-query="这个人是谁">安全拦截</button>
        </div>
        ${searchInfo}
      </section>
    `;
  }

  function renderAiAlbumSidebar() {
    const state = appState.aiAlbum;
    const categories = aiAlbumAllCategories();
    const modality = aiAlbumFacetEntries("modality", 6);
    return `
      <aside class="ai-album-sidebar">
        <div class="ai-album-sidebar-section">
          <div class="section-title compact"><h2>智能分类</h2></div>
          <button class="ai-album-category${state.selectedCategory ? "" : " active"}" type="button" data-action="aiAlbumCategory" data-category="">
            <span>全部分类</span><strong>${fmtCount((state.assets || []).length)}</strong>
          </button>
          ${categories.length ? categories.map(([name, count]) => `<button class="ai-album-category${state.selectedCategory === name ? " active" : ""}" type="button" data-action="aiAlbumCategory" data-category="${escapeHtml(name)}"><span>${escapeHtml(name)}</span><strong>${fmtCount(count)}</strong></button>`).join("") : `<div class="empty-state compact">暂无分类索引</div>`}
        </div>
        <div class="ai-album-sidebar-section">
          <div class="section-title compact"><h2>素材类型</h2></div>
          ${modality.length ? modality.map(([name, count]) => `<div class="mini-row"><span>${escapeHtml(name)}</span><span class="muted small">${fmtCount(count)}</span></div>`).join("") : `<div class="mini-row"><span>image</span><span class="muted small">${fmtCount(state.assets.length)}</span></div>`}
        </div>
        <div class="ai-album-boundary">
          <strong>${svg("lock")} 安全边界</strong>
          <span>身份识别：关闭</span>
          <span>敏感属性推断：关闭</span>
          <span>原始路径返回：关闭</span>
          <span>云端私有原文外发：关闭</span>
        </div>
      </aside>
    `;
  }

  function renderAiAlbumTabs() {
    const active = appState.aiAlbum.activeTab || "all";
    return `<div class="ai-album-tabs" role="tablist">${aiAlbumTabItems().map(([id, label, count]) => `<button class="chip${active === id ? " active" : ""}" type="button" role="tab" aria-selected="${active === id ? "true" : "false"}" data-action="aiAlbumTab" data-tab="${escapeHtml(id)}">${escapeHtml(label)} <span>${fmtCount(count)}</span></button>`).join("")}</div>`;
  }

  function renderAiAlbumAssetCard(asset, index = 0) {
    const id = aiAlbumAssetId(asset);
    const title = aiAlbumAssetTitle(asset, `本地素材 ${index + 1}`);
    const previewUrl = aiAlbumPreviewUrl(asset);
    const mediaPhoto = aiAlbumMediaPhotoForAsset(asset);
    const pathHash = asset?.path_hash || mediaPhoto?.path_hash || "";
    const meta = aiAlbumAssetMeta(asset);
    const categories = aiAlbumCategoryNames(asset).slice(0, 4);
    const selected = id && id === appState.aiAlbum.selectedAssetId ? " active" : "";
    const openAttrs = previewUrl
      ? ` data-image-preview-url="${escapeHtml(previewUrl)}" data-image-title="${escapeHtml(title)}" data-image-meta="${escapeHtml(meta || "相册预览")}" data-image-match="相册 · 本地"`
      : "";
    const trashButton = previewUrl && pathHash
      ? storageTrashButton({ kind: "image", title, pathHash, previewUrl })
      : "";
    const thumb = previewUrl
      ? `<div class="search-thumb ai-album-thumb has-preview"><img class="search-preview-image" alt="${escapeHtml(title)} 预览" data-preview-url="${escapeHtml(thumbnailPreviewUrl(previewUrl))}" hidden><span class="thumb-loading">加载预览</span></div>`
      : `<div class="search-thumb ai-album-thumb">${svg(asset?.modality === "video" ? "media" : "docs")}<span>无预览</span></div>`;
    return `<article class="ai-album-asset-card${selected}${previewUrl ? " is-openable" : ""}${trashButton ? " has-actions" : ""}" tabindex="0" role="button" data-action="aiAlbumSelectAsset" data-ai-album-asset-id="${escapeHtml(id)}"${openAttrs}>
      ${thumb}
      ${trashButton}
      <div class="ai-album-asset-copy">
        <strong title="${escapeHtml(title)}">${escapeHtml(title)}</strong>
        <span class="muted small">${escapeHtml(meta || asset?.privacy_level || "本地 AI Space")}</span>
        <p>${escapeHtml(asset?.summary_redacted || asset?.match_reason || asset?.description || "本地索引摘要，原始文件不在页面暴露。")}</p>
        <div class="result-tags">${categories.length ? categories.map((name) => `<span class="result-tag">${escapeHtml(name)}</span>`).join("") : `<span class="result-tag">本地素材</span>`}</div>
      </div>
    </article>`;
  }

  function renderAiAlbumGrid() {
    const assets = aiAlbumVisibleAssets();
    if (appState.aiAlbum.status === "loading") {
      return `<div class="skeleton-list ai-album-skeleton"><span></span><span></span><span></span><span></span></div>`;
    }
    if (!assets.length) {
      return `<div class="empty-state ai-album-empty">${svg("search")}<strong>没有匹配素材</strong><p>调整分类或搜索词后重新检索本地 AI Space 索引。</p></div>`;
    }
    return `<div class="ai-album-grid">${assets.map(renderAiAlbumAssetCard).join("")}</div>`;
  }

  function renderAiAlbumRiskFlags(asset) {
    const flags = asset?.smart_naming?.risk_flags || asset?.risk_flags || {};
    const rows = [
      ["身份识别", flags.identity_inference_used ? "需复查" : "关闭"],
      ["敏感属性", flags.sensitive_attribute_inference_used ? "需复查" : "关闭"],
      ["云端调用", flags.cloud_used || asset?.cloud_used ? "需复查" : "关闭"],
      ["原始路径", flags.raw_path_returned || asset?.raw_path_returned ? "需复查" : "关闭"]
    ];
    return `<div class="ai-album-flag-list">${rows.map(([label, value]) => `<span class="${value === "关闭" ? "ok" : "warn"}">${escapeHtml(label)}：${escapeHtml(value)}</span>`).join("")}</div>`;
  }

  function renderAiAlbumDetailPanel() {
    const asset = aiAlbumSelectedAsset();
    if (!asset) {
      return `<aside class="ai-album-detail"><div class="empty-state compact">${svg("media")} 选择一张照片或素材后查看详情。</div></aside>`;
    }
    const categories = aiAlbumCategoryNames(asset);
    const evidence = Array.isArray(asset.evidence_refs) ? asset.evidence_refs : [];
    const photo = aiAlbumMediaPhotoForAsset(asset) || {};
    return `<aside class="ai-album-detail">
      <div class="answer-header"><strong>${svg("media")} 素材详情</strong>${badge(asset.privacy_level || "private_local_only", "success")}</div>
      <div class="ai-album-detail-title">
        <strong>${escapeHtml(aiAlbumAssetTitle(asset))}</strong>
        <span>${escapeHtml(asset.summary_redacted || "本地符号化摘要")}</span>
      </div>
      ${renderAiAlbumRiskFlags(asset)}
      ${renderKeyValueRows([
        ["素材类型", asset.modality || photo.extension || "image"],
        ["智能命名", asset.suggested_filename_zh || asset.display_name_zh || "待生成"],
        ["OCR 状态", asset.ocr_status || "none"],
        ["证据引用", evidence.length ? `${evidence.length} 条` : "无"],
        ["大小", photo.size_bytes ? formatBytes(photo.size_bytes) : "暂无"],
        ["时间", formatStorageTime(asset.created_at || asset.taken_at || photo.taken_at || photo.mtime)]
      ])}
      <div class="detail-section">
        <strong>分类标签</strong>
        <div class="result-tags">${categories.length ? categories.map((name) => `<span class="result-tag">${escapeHtml(name)}</span>`).join("") : `<span class="result-tag">未分类</span>`}</div>
      </div>
      <div class="detail-section">
        <strong>可执行动作</strong>
        <p class="muted small">当前页面只允许查看、检索和生成受控整理计划。不会提供删除、覆盖或裸路径操作。</p>
        <div class="actions">${button("生成整理计划", { icon: "table", action: "aiAlbumPlan" })}</div>
      </div>
    </aside>`;
  }

  function renderAiAlbumPlanSummary() {
    const state = appState.aiAlbum;
    if (state.planStatus === "loading") return `<div class="soft-note">${svg("table")} 正在创建受控整理计划...</div>`;
    if (state.planStatus === "error") return `<div class="soft-note error-note">${svg("alert")} ${escapeHtml(state.planError || "整理计划创建失败")}</div>`;
    if (!state.planResult) return "";
    const result = state.planResult;
    const ok = result.ok !== false;
    const count = result.item_count ?? (Array.isArray(result.items) ? result.items.length : 0);
    return `<div class="ai-album-plan-summary ${ok ? "" : "blocked"}">
      <strong>${ok ? "整理计划已生成" : "整理计划未生成"}</strong>
      <span>${escapeHtml(result.blocker || result.error || `${fmtCount(count)} 个候选项`)}</span>
      <button class="link-button" type="button" data-action="aiAlbumShowPlan">查看工作流 ${svg("chevron")}</button>
    </div>`;
  }

  function aiAlbumPage() {
    const state = appState.aiAlbum;
    const stateBlock = apiStateBlock(state, "相册暂无素材。");
    const status = state.statusPayload || {};
    const photos = state.mediaPhotos || [];
    const uploadBusy = appState.media.uploadStatus === "loading";
    const organize = state.autoOrganize || {};
    const organizeLabel = state.autoOrganizeStatus === "loading" ? "检查中" : (organize.ok === false ? "需复查" : (organize.changed ? "已增量整理" : "已是最新"));
    return `
      ${pageHeader("相册", "在本地索引、媒体预览和智能分类上检索照片。", `${button(uploadBusy ? "上传中" : "上传图片", { icon: "upload", action: "mediaUploadChoose", disabled: uploadBusy })}${button("刷新", { variant: "secondary", icon: "plus", action: "aiAlbumRefresh" })}${button("生成整理计划", { icon: "table", action: "aiAlbumPlan", disabled: state.status === "auth" || state.status === "loading" })}`)}
      ${renderMediaUploadInput()}
      ${renderMediaUploadStatus()}
      <div class="ai-album-kpis">
        <div><span>自动整理</span><strong>${escapeHtml(organizeLabel)}</strong></div>
        <div><span>AI Space 素材</span><strong>${fmtCount(status.asset_count || state.assets.length)}</strong></div>
        <div><span>媒体预览</span><strong>${fmtCount(photos.length)}</strong></div>
        <div><span>云端调用</span><strong>${status.cloud_used ? "需复查" : "关闭"}</strong></div>
        <div><span>原始路径</span><strong>${status.raw_path_returned ? "需复查" : "关闭"}</strong></div>
      </div>
      ${stateBlock || `${renderAiAlbumSearchBlock()}
      <div class="ai-album-layout">
        ${renderAiAlbumSidebar()}
        <section class="ai-album-main">
          ${renderAiAlbumTabs()}
          ${renderAiAlbumPlanSummary()}
          ${renderAiAlbumGrid()}
        </section>
        ${renderAiAlbumDetailPanel()}
      </div>`}
      ${renderStatePanel("相册")}
    `;
  }

  function backupPage() {
    const stateBlock = apiStateBlock(appState.backup, "还没有备份任务。");
    const summary = appState.backup.summary || {};
    const stats = summary.stats || {};
    const tasksList = summary.tasks || [];
    const runs = summary.runs || [];
    return `
      ${pageHeader("备份同步", "验证受控备份任务、运行记录和非破坏性同步边界。", `${button("刷新", { icon: "plus", action: "backupRefresh" })}`)}
      <div class="grid two-col">
        ${card(`${sectionTitle("备份任务")} ${stateBlock || renderKeyValueRows([
          ["任务数", stats.task_count || tasksList.length || 0],
          ["运行数", stats.run_count || runs.length || 0],
          ["最近状态", stats.last_status || "暂无"],
          ["删除/覆盖", "禁用"]
        ])}
        <div class="login-stack" style="margin-top:16px">
          <input id="backupName" class="control" value="${escapeHtml(appState.backup.taskName || "本地备份任务")}" aria-label="备份任务名">
          <input id="backupSource" class="control" value="Documents" aria-label="备份来源">
          <input id="backupDest" class="control" value="Backups/Documents" aria-label="备份目标">
          <div class="copy-actions">${button("创建任务", { icon: "save", action: "backupCreate" })}${button("运行任务", { variant: "secondary", icon: "backup", action: "backupRun" })}</div>
        </div>`)}
        ${card(`${sectionTitle("运行记录")}<div class="table-wrap"><table class="data-table"><thead><tr><th>任务</th><th>状态</th><th>扫描</th><th>复制</th><th>时间</th></tr></thead><tbody>${runs.slice(0, 12).map((run) => `<tr><td>${escapeHtml(run.task_name || run.name || "暂无")}</td><td>${badge(run.status || "recorded", run.status === "ok" || run.status === "completed" ? "success" : "neutral")}</td><td>${fmtCount(run.files_scanned || 0)}</td><td>${fmtCount(run.files_copied || 0)}</td><td>${escapeHtml(run.started_at || "暂无")}</td></tr>`).join("") || `<tr><td colspan="5"><div class="empty-line">暂无运行记录。</div></td></tr>`}</tbody></table></div>`)}
      </div>
      ${renderStatePanel("备份同步")}
    `;
  }

  function settingsPage() {
    const stateBlock = apiStateBlock(appState.settings, "设置数据为空。");
    const storage = appState.settings.storage || {};
    const capacity = storage.capacity || {};
    const harness = appState.settings.harness || {};
    const token = appState.settings.token || {};
    const analysis = token.latest_analysis || {};
    const forbiddenActions = (harness.forbidden_actions || ["delete", "move", "rename", "chmod", "overwrite", "recursive"]).map(riskActionLabel).join("、");
    return `
      ${pageHeader("设置", "查看身份、权限、受控复制和隐私路由边界。", button("刷新", { icon: "plus", action: "settingsRefresh" }))}
      ${stateBlock || `<div class="grid two-col">
        ${card(`${sectionTitle("存储与用户")} ${renderKeyValueRows([
          ["个人空间", storage.personal_root || storage.root ? "已配置" : "服务端配置"],
          ["已用空间", capacity.used_bytes ? formatBytes(capacity.used_bytes) : "暂无"],
          ["总空间", capacity.total_bytes ? formatBytes(capacity.total_bytes) : "暂无"],
          ["用户数", appState.settings.users.length]
        ])}`)}
        ${card(`${sectionTitle("受控复制策略")} ${renderKeyValueRows([
          ["服务状态", harness.ok ? "在线" : "需复查"],
          ["策略版本", harness.policy_id ? "已配置" : "未配置"],
          ["只读工作区", harness.readonly_workspaces_enabled ? "启用" : "未启用"],
          ["执行边界", "仅受控单文件复制"],
          ["模型执行权限", "无"],
          ["禁用动作", forbiddenActions]
        ])}`)}
        ${card(`${sectionTitle("Token 预算")} ${renderKeyValueRows([
          ["分词器", token.tokenizer_identity?.tokenizer_name || token.tokenizer_identity?.source || "Qwen 分词器"],
          ["记录状态", token.trace_path ? "已生成" : "待生成"],
          ["平均降幅", analysis.average_reduction_ratio != null ? `${Math.round(analysis.average_reduction_ratio * 10000) / 100}%` : "见报告"],
          ["默认云端私有外发", "禁止"]
        ])}`)}
        ${card(`${sectionTitle("高风险操作边界")} ${renderKeyValueRows([
          ["删除/移动/重命名", "禁用"],
          ["覆盖/递归操作", "禁用"],
          ["改权限/任意 shell", "禁用"],
          ["允许的写入", "新建文件夹、上传、受控单文件复制"],
          ["确认要求", "需要身份令牌、路径权限和明确确认"]
        ])}`)}
      </div>`}
      ${renderStatePanel("设置")}
    `;
  }

  const pages = {
    dashboard: dashboardPage,
    assistant: assistantPage,
    files: filesPage,
    documents: filesPage,
    reports: reportsPage,
    tokenBudget: tokenBudgetPage,
    agentRuntime: agentRuntimePage,
    media: mediaPageV2,
    backup: backupPage,
    journal: journalPage,
    audit: auditPage,
    settings: settingsPage
  };

  function setPage(page) {
    if (!pages[page]) return;
    appState.page = page;
    window.location.hash = page;
    renderShell();
    document.getElementById("main-content")?.focus({ preventScroll: true });
    pageAfterRenderLoad(page);
  }

  function renderToast(message = appState.toast) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = message || "";
    toast.classList.toggle("show", Boolean(message));
  }

  function showToast(message) {
    appState.toast = message;
    renderToast();
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
      appState.toast = "";
      renderToast();
    }, 2200);
  }

  function renderWorkflowPanel() {
    const workflow = appState.workflow || {};
    if (!workflow.open) return "";
    return `
      <div class="workflow-backdrop" role="presentation" data-action="closeWorkflow"></div>
      <aside class="workflow-panel ${escapeHtml(workflow.tone || "neutral")}" role="dialog" aria-modal="true" aria-label="${escapeHtml(workflow.title || "工作流")}">
        <div class="workflow-header">
          <div><span class="muted small">受控工作流</span><h2>${escapeHtml(workflow.title || "工作流")}</h2></div>
          <button class="icon-button" type="button" aria-label="关闭" data-action="closeWorkflow">${svg("plus")}</button>
        </div>
        <div class="workflow-body">${workflow.body || ""}</div>
      </aside>
    `;
  }

  function clampImageViewerZoom(value) {
    const next = Number(value);
    if (!Number.isFinite(next)) return 1;
    return Math.min(5, Math.max(0.25, next));
  }

  function imageViewerTransform(viewer) {
    const zoom = clampImageViewerZoom(viewer.zoom || 1);
    const rotation = Number(viewer.rotation || 0);
    const offsetX = Number(viewer.offsetX || 0);
    const offsetY = Number(viewer.offsetY || 0);
    return `translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg) scale(${zoom})`;
  }

  function imageViewerZoomLabel(viewer) {
    return `${Math.round(clampImageViewerZoom(viewer.zoom || 1) * 100)}%`;
  }

  function updateImageViewerTransform(patch) {
    if (!appState.imageViewer.open) return;
    const current = appState.imageViewer || {};
    const nextZoom = Object.prototype.hasOwnProperty.call(patch, "zoom") ? clampImageViewerZoom(patch.zoom) : clampImageViewerZoom(current.zoom || 1);
    const next = {
      ...current,
      ...patch,
      zoom: nextZoom,
      offsetX: nextZoom <= 1 && !Object.prototype.hasOwnProperty.call(patch, "offsetX") ? 0 : Number(patch.offsetX ?? current.offsetX ?? 0),
      offsetY: nextZoom <= 1 && !Object.prototype.hasOwnProperty.call(patch, "offsetY") ? 0 : Number(patch.offsetY ?? current.offsetY ?? 0)
    };
    appState.imageViewer = next;
    renderShell();
  }

  function zoomImageViewer(factor) {
    const current = appState.imageViewer || {};
    const nextZoom = clampImageViewerZoom((current.zoom || 1) * factor);
    updateImageViewerTransform({
      zoom: nextZoom,
      offsetX: nextZoom <= 1 ? 0 : current.offsetX || 0,
      offsetY: nextZoom <= 1 ? 0 : current.offsetY || 0
    });
  }

  function resetImageViewerTransform() {
    updateImageViewerTransform({ zoom: 1, rotation: 0, offsetX: 0, offsetY: 0 });
  }

  function rotateImageViewer() {
    const current = appState.imageViewer || {};
    updateImageViewerTransform({ rotation: ((Number(current.rotation || 0) + 90) % 360), offsetX: 0, offsetY: 0 });
  }

  function renderImageViewerPanel() {
    const viewer = appState.imageViewer || {};
    if (!viewer.open) return "";
    const meta = [viewer.meta, viewer.match].filter(Boolean).join(" · ");
    const canTransform = Boolean(viewer.objectUrl);
    const zoomLabel = imageViewerZoomLabel(viewer);
    const imgStyle = `transform: ${imageViewerTransform(viewer)};`;
    const body = viewer.status === "error"
      ? `<div class="image-viewer-state">${svg("alert")}<strong>图片打开失败</strong><p>${escapeHtml(viewer.error || "preview_unavailable")}</p></div>`
      : viewer.objectUrl
        ? `<img class="image-viewer-img" src="${escapeHtml(viewer.objectUrl)}" alt="${escapeHtml(viewer.title || "图片预览")}" style="${escapeHtml(imgStyle)}" draggable="false">`
        : `<div class="image-viewer-state"><div class="spinner"></div><strong>正在打开图片</strong><p>首次读取可能需要几秒，超过 12 秒会显示重试状态。</p></div>`;
    return `
      <div class="image-viewer-backdrop" role="presentation" data-action="closeImageViewer"></div>
      <section class="image-viewer-panel" role="dialog" aria-modal="true" aria-label="${escapeHtml(viewer.title || "图片预览")}">
        <header class="image-viewer-header">
          <div class="image-viewer-title">
            <strong>${escapeHtml(viewer.title || "图片预览")}</strong>
            ${meta ? `<span>${escapeHtml(meta)}</span>` : ""}
          </div>
          <div class="image-viewer-actions">
            <div class="image-viewer-toolbar" role="toolbar" aria-label="图片查看工具">
              <button class="icon-button" type="button" title="缩小" aria-label="缩小" data-action="imageZoomOut" ${canTransform ? "" : "disabled"}>${svg("zoomOut")}</button>
              <span class="image-viewer-zoom" aria-label="当前缩放">${escapeHtml(zoomLabel)}</span>
              <button class="icon-button" type="button" title="放大" aria-label="放大" data-action="imageZoomIn" ${canTransform ? "" : "disabled"}>${svg("zoomIn")}</button>
              <button class="icon-button" type="button" title="适配窗口" aria-label="适配窗口" data-action="imageFit" ${canTransform ? "" : "disabled"}>${svg("fit")}</button>
              <button class="icon-button" type="button" title="旋转" aria-label="旋转" data-action="imageRotate" ${canTransform ? "" : "disabled"}>${svg("rotate")}</button>
            </div>
            <button class="icon-button image-viewer-close" type="button" aria-label="关闭图片预览" data-action="closeImageViewer">${svg("plus")}</button>
          </div>
        </header>
        <div class="image-viewer-body${canTransform ? " is-transformable" : ""}" data-image-viewer-body>${body}</div>
      </section>
    `;
  }

  function showWorkflow(title, body, tone = "neutral") {
    appState.workflow = { open: true, title, body, tone };
    renderShell();
  }

  function closeWorkflow() {
    appState.workflow = { open: false, title: "", body: "", tone: "neutral" };
    renderShell();
  }

  function closeImageViewer() {
    imageViewerDrag = null;
    appState.imageViewer = { open: false, title: "", meta: "", match: "", previewUrl: "", objectUrl: "", status: "idle", error: "", requestId: "", zoom: 1, rotation: 0, offsetX: 0, offsetY: 0 };
    renderShell();
  }

  async function fetchJson(path, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (appState.authToken) headers.Authorization = `Bearer ${appState.authToken}`;
    const method = String(options.method || "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && appState.csrfToken) {
      headers["X-CSRF-Token"] = appState.csrfToken;
    }
    let body = options.body;
    if (body && typeof body !== "string" && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    const response = await fetch(path, { credentials: "same-origin", ...options, headers, body });
    const data = await response.json();
    if (response.status === 401 && data?.error === "auth_required") {
      clearProductSession();
    }
    return { ok: response.ok, status: response.status, data };
  }

  async function uploadFileStream(file, targetDir = "") {
    const query = new URLSearchParams({ filename: file.name, target_dir: cleanStoragePath(targetDir) });
    const headers = { Accept: "application/json", "Content-Type": file.type || "application/octet-stream" };
    if (appState.authToken) headers.Authorization = `Bearer ${appState.authToken}`;
    if (appState.csrfToken) headers["X-CSRF-Token"] = appState.csrfToken;
    const response = await fetch(`/api/storage/upload-stream?${query.toString()}`, {
      method: "POST",
      headers,
      body: file
    });
    const data = await response.json();
    return { ok: response.ok, status: response.status, data };
  }

  function discardPreviewObjectUrl(previewUrl) {
    const objectUrl = previewObjectUrlCache.get(previewUrl);
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    previewObjectUrlCache.delete(previewUrl);
    previewObjectPromiseCache.delete(previewUrl);
  }

  async function loadPreviewObjectUrl(previewUrl, { forceRefresh = false } = {}) {
    if (!previewUrl) throw new Error("preview_url_missing");
    if (forceRefresh) discardPreviewObjectUrl(previewUrl);
    const cachedObjectUrl = previewObjectUrlCache.get(previewUrl);
    if (cachedObjectUrl) return cachedObjectUrl;
    const cachedPromise = previewObjectPromiseCache.get(previewUrl);
    if (cachedPromise) return cachedPromise;
    const promise = (async () => {
      const headers = {};
      if (appState.authToken) headers.Authorization = `Bearer ${appState.authToken}`;
      const response = await fetch(previewUrl, { headers });
      if (!response.ok) throw new Error(`preview_${response.status}`);
      const blob = await response.blob();
      if (!blob.size) throw new Error("preview_empty");
      if (!String(blob.type || "").toLowerCase().startsWith("image/")) throw new Error("preview_not_image");
      const objectUrl = URL.createObjectURL(blob);
      previewObjectUrlCache.set(previewUrl, objectUrl);
      return objectUrl;
    })();
    previewObjectPromiseCache.set(previewUrl, promise);
    try {
      return await promise;
    } finally {
      previewObjectPromiseCache.delete(previewUrl);
    }
  }

  function decodePreviewObjectUrl(objectUrl, timeoutMs = 12000) {
    return new Promise((resolve, reject) => {
      const probe = new Image();
      let settled = false;
      const finish = (error) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeoutId);
        probe.onload = null;
        probe.onerror = null;
        if (error) reject(error);
        else resolve();
      };
      const timeoutId = window.setTimeout(() => finish(new Error("preview_decode_timeout")), timeoutMs);
      probe.onload = () => finish(probe.naturalWidth > 0 ? null : new Error("preview_decode_empty"));
      probe.onerror = () => finish(new Error("preview_decode_failed"));
      probe.src = objectUrl;
    });
  }

  async function hydrateAssistantSearchPreviews() {
    const images = Array.from(document.querySelectorAll("img[data-preview-url]"));
    if (!images.length) return;
    await Promise.all(images.map(async (img) => {
      if (img.dataset.loaded === "1") return;
      img.dataset.loaded = "1";
      const container = img.closest(".search-thumb");
      const loading = container?.querySelector(".thumb-loading");
      try {
        const objectUrl = await loadPreviewObjectUrl(img.dataset.previewUrl);
        const card = img.closest("[data-image-preview-url]");
        if (card) card.dataset.imageObjectUrl = objectUrl;
        img.onload = () => {
          img.hidden = false;
          if (loading) loading.hidden = true;
          container?.classList.add("preview-ready");
        };
        img.src = objectUrl;
      } catch (error) {
        container?.classList.add("preview-unavailable");
        if (loading) loading.textContent = "预览不可用";
      }
    }));
  }

  async function hydratePreviewImageV2(img) {
    if (!img || !img.isConnected || img.dataset.loaded === "1") return;
    img.dataset.loaded = "1";
    const container = img.closest(".search-thumb");
    const loading = container?.querySelector(".thumb-loading");
    let lastError = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const previewUrl = img.dataset.previewUrl;
        const objectUrl = await loadPreviewObjectUrl(previewUrl, { forceRefresh: attempt > 0 });
        await decodePreviewObjectUrl(objectUrl);
        const card = img.closest("[data-image-preview-url]");
        if (card?.dataset?.imagePreviewUrl === previewUrl) card.dataset.imageObjectUrl = objectUrl;
        img.src = objectUrl;
        img.hidden = false;
        if (loading) loading.hidden = true;
        container?.classList.add("preview-ready");
        return;
      } catch (error) {
        lastError = error;
      }
    }
    img.dataset.loaded = "0";
    container?.classList.add("preview-unavailable");
    if (loading) {
      loading.hidden = false;
      loading.textContent = lastError?.message === "preview_decode_timeout" ? "预览解码超时" : "预览不可用，刷新可重试";
    }
  }

  function drainPreviewHydrationQueue() {
    while (previewHydrationActive < PREVIEW_HYDRATION_CONCURRENCY && previewHydrationQueue.length) {
      const img = previewHydrationQueue.shift();
      if (!img || !img.isConnected || img.dataset.loaded === "1") continue;
      previewHydrationActive += 1;
      hydratePreviewImageV2(img).finally(() => {
        previewHydrationActive = Math.max(0, previewHydrationActive - 1);
        drainPreviewHydrationQueue();
      });
    }
  }

  function queuePreviewHydration(img) {
    if (!img || img.dataset.loaded === "1" || img.dataset.queued === "1") return;
    img.dataset.queued = "1";
    previewHydrationQueue.push(img);
    drainPreviewHydrationQueue();
  }

  function hydrateAssistantSearchPreviewsV2() {
    const images = Array.from(document.querySelectorAll("img[data-preview-url]"));
    if (!images.length) return;
    if (previewLazyObserver) {
      previewLazyObserver.disconnect();
      previewLazyObserver = null;
    }
    previewHydrationQueue.length = 0;
    const immediate = images.slice(0, 6);
    const deferred = images.slice(6);
    for (const img of immediate) {
      window.setTimeout(() => queuePreviewHydration(img), 0);
    }
    if ("IntersectionObserver" in window) {
      previewLazyObserver = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          previewLazyObserver?.unobserve(entry.target);
          queuePreviewHydration(entry.target);
        }
      }, { rootMargin: "280px 0px" });
      for (const img of deferred) previewLazyObserver.observe(img);
      return;
    }
    deferred.slice(0, 12).forEach((img, index) => {
      window.setTimeout(() => queuePreviewHydration(img), 300 + index * 120);
    });
  }

  async function openSearchImageViewer(card) {
    if (!card?.dataset?.imagePreviewUrl) return;
    const previewUrl = card.dataset.imagePreviewUrl;
    const existingObjectUrl = card.dataset.imageObjectUrl || previewObjectUrlCache.get(previewUrl) || "";
    const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    appState.imageViewer = {
      open: true,
      title: card.dataset.imageTitle || "图片预览",
      meta: card.dataset.imageMeta || "",
      match: card.dataset.imageMatch || "",
      previewUrl,
      objectUrl: existingObjectUrl || "",
      status: existingObjectUrl ? "ready" : "loading",
      error: "",
      requestId,
      zoom: 1,
      rotation: 0,
      offsetX: 0,
      offsetY: 0
    };
    renderShell();
    if (existingObjectUrl) return;
    let timeoutId = 0;
    try {
      const timeoutPromise = new Promise((_, reject) => {
        timeoutId = window.setTimeout(() => reject(new DOMException("preview_timeout", "AbortError")), 15000);
      });
      let objectUrl = await Promise.race([loadPreviewObjectUrl(previewUrl), timeoutPromise]);
      try {
        await decodePreviewObjectUrl(objectUrl);
      } catch (_decodeError) {
        objectUrl = await loadPreviewObjectUrl(previewUrl, { forceRefresh: true });
        await decodePreviewObjectUrl(objectUrl);
      }
      if (!appState.imageViewer.open || appState.imageViewer.requestId !== requestId) return;
      appState.imageViewer = { ...appState.imageViewer, objectUrl, status: "ready", error: "" };
      renderShell();
    } catch (error) {
      if (!appState.imageViewer.open || appState.imageViewer.requestId !== requestId) return;
      const message = error?.name === "AbortError" ? "图片读取超时，请关闭后重试，或先等待缩略图加载完成。" : (error.message || String(error));
      appState.imageViewer = { ...appState.imageViewer, status: "error", error: message };
      renderShell();
    } finally {
      if (timeoutId) window.clearTimeout(timeoutId);
    }
  }

  function authNotice(scope = "该功能") {
    return `<div class="empty-state">${svg("lock")}<strong>需要登录</strong><p>${escapeHtml(scope)} 需要有效登录会话。登录后可继续刚才的验证。</p>${button("前往登录", { icon: "lock", page: "files" })}</div>`;
  }

  function apiStateBlock(state, emptyText = "暂无数据") {
    if (state.status === "loading") {
      return `<div class="skeleton-list"><span></span><span></span><span></span><span></span></div>`;
    }
    if (state.status === "auth") return authNotice();
    if (state.status === "error") {
      return `<div class="empty-state">${svg("alert")}<strong>读取失败</strong><p>${escapeHtml(state.error || "api_failed")}</p></div>`;
    }
    if (state.status === "ready-empty") {
      return `<div class="empty-state">${svg("search")}<strong>暂无结果</strong><p>${escapeHtml(emptyText)}</p></div>`;
    }
    return "";
  }

  function fmtCount(value) {
    const n = Number(value || 0);
    return Number.isFinite(n) ? n.toLocaleString("zh-CN") : "0";
  }

  function fmtRatio(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "暂无";
    return `${Math.round(n * 1000) / 10}%`;
  }

  function renderKeyValueRows(rows) {
    return `<dl class="meta-grid">${productMetaRows(rows).map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value ?? "暂无")}</dd>`).join("")}</dl>`;
  }

  function renderOperationRows(rows) {
    if (!rows.length) return `<div class="empty-state compact">${svg("search")} 暂无操作日志</div>`;
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>时间</th><th>动作</th><th>来源</th><th>目标</th><th>状态</th></tr></thead><tbody>${rows.map((row, index) => `<tr data-record-id="${escapeHtml(auditRecordId(row, index))}"><td>${escapeHtml(row.created_at || row.ts || "暂无")}</td><td>${escapeHtml(operationTitle(row.action || row.operation || "暂无"))}</td><td>${escapeHtml(row.source || row.source_path ? "已记录" : "暂无")}</td><td>${escapeHtml(row.target || row.target_path ? "已记录" : "暂无")}</td><td>${badge(row.status || "recorded", String(row.status || "").includes("disabled") ? "danger" : "success")}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function renderDocumentEvidence(items) {
    if (!items.length) return `<div class="empty-state compact">${svg("search")} 没有可引用证据</div>`;
    return items.slice(0, 8).map((item, i) => {
      const openUrl = documentOpenUrl(item);
      const title = displayName(item, "文档证据");
      const openAttrs = openUrl
        ? ` tabindex="0" role="button" aria-label="双击打开 ${escapeHtml(title)}" data-document-open-url="${escapeHtml(openUrl)}" data-document-title="${escapeHtml(title)}" data-document-filename="${escapeHtml(item.name || baseName(item.relative_path || "") || "document")}"`
        : "";
      const trashButton = item.relative_path
        ? storageTrashButton({ kind: "document", title, relativePath: item.relative_path })
        : "";
      return `<article class="evidence-card${openUrl ? " is-openable" : ""}${trashButton ? " has-actions" : ""}"${openAttrs}>
      <div class="evidence-card-head">
        <div class="file-cell"><span class="doc-glyph ${fileGlyph(item)}">${escapeHtml(fileType(item).slice(0, 4))}</span><strong title="${escapeHtml(displayName(item, "文档证据"))}">${escapeHtml(displayName(item, "文档证据"))}</strong></div>
        ${trashButton}
      </div>
      <div class="evidence-meta"><span>${escapeHtml(evidenceLabel(item, i))}</span><span>${escapeHtml(fileType(item) || "文档")}</span><span>本地保留</span></div>
      <p class="muted small">${escapeHtml(item.snippet || item.summary || "本地索引返回的摘要信息，原文仍保留在 NAS。")}</p>
    </article>`;
    }).join("");
  }

  async function loadDocClassificationData() {
    if (!appState.authToken) {
      appState.docClassification = { ...appState.docClassification, status: "auth", error: "" };
      if (appState.page === "files" || appState.page === "documents") renderShell();
      return;
    }
    appState.docClassification = { ...appState.docClassification, status: "loading", error: "" };
    if (appState.page === "files" || appState.page === "documents") renderShell();
    try {
      const result = await fetchJson("/api/documents/classification-status?path=Documents");
      if (result.ok && result.data?.ok) {
        const data = result.data;
        appState.docClassification = {
          ...appState.docClassification,
          status: "ready",
          categories: data.categories || {},
          categoryCounts: data.category_counts || {},
          items: data.items || [],
          error: ""
        };
      } else if (result.status === 401) {
        appState.docClassification = { ...appState.docClassification, status: "auth", error: "" };
      } else {
        appState.docClassification = { ...appState.docClassification, status: "error", error: result.data?.error || "classification_status_failed" };
      }
    } catch (error) {
      appState.docClassification = { ...appState.docClassification, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "files" || appState.page === "documents") renderShell();
  }

  async function runDocClassification() {
    if (!appState.authToken) {
      showToast("请先登录");
      return;
    }
    appState.docClassification = { ...appState.docClassification, status: "loading", error: "" };
    renderShell();
    try {
      const result = await fetchJson("/api/documents/classify", { method: "POST", body: { path: "Documents" } });
      if (result.ok && result.data?.ok) {
        const data = result.data;
        appState.docClassification = {
          ...appState.docClassification,
          status: "ready",
          categories: data.categories || {},
          categoryCounts: data.category_counts || {},
          items: data.items || [],
          error: ""
        };
        showToast(`分类完成，共 ${data.total_items || 0} 个文件`);
      } else {
        appState.docClassification = { ...appState.docClassification, status: "error", error: result.data?.error || "classify_failed" };
        showToast("分类失败");
      }
    } catch (error) {
      appState.docClassification = { ...appState.docClassification, status: "error", error: error.message || String(error) };
      showToast("分类失败");
    }
    renderShell();
  }

  async function uploadDocumentFile() {
    if (!appState.authToken) { showToast("请先登录"); return; }
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.onchange = async (e) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;
      for (const file of files) {
        try {
          const result = await uploadFileStream(file, "Documents");
          showToast(result.ok && result.data?.ok ? `上传成功: ${file.name}` : `上传失败: ${file.name}`);
        } catch (error) {
          showToast(`上传失败: ${file.name}`);
        }
      }
      await loadDocClassificationData();
    };
    input.click();
  }
  async function loadDocumentsData() {
    if (!appState.authToken) {
      appState.documents = { ...appState.documents, status: "auth", error: "" };
      if (appState.page === "files" || appState.page === "documents") renderShell();
      return;
    }
    const requestPath = appState.documents.path || "Documents";
    appState.documents = { ...appState.documents, status: "loading", error: "" };
    if (appState.page === "documents") renderShell();
    try {
      const result = await fetchJson(`/api/documents/list?path=${encodeURIComponent(requestPath)}`);
      if ((appState.documents.path || "Documents") !== requestPath) return;
      if (result.ok && result.data?.ok) {
        const items = Array.isArray(result.data.items) ? result.data.items : [];
        appState.documents = { ...appState.documents, status: items.length ? "ready" : "ready-empty", items, error: "" };
      } else if (result.status === 401) {
        appState.documents = { ...appState.documents, status: "auth", error: "" };
      } else {
        appState.documents = { ...appState.documents, status: "error", error: result.data?.error || `documents_list_failed:${result.status}` };
      }
    } catch (error) {
      appState.documents = { ...appState.documents, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "documents") renderShell();
  }

  async function askDocuments() {
    const input = document.getElementById("documentQuestion");
    const query = input?.value.trim() || appState.documents.query || "";
    if (!query) return;
    if (!appState.authToken) {
      appState.documents = { ...appState.documents, status: "auth" };
      renderShell();
      return;
    }
    appState.documents = { ...appState.documents, query, status: "loading", error: "" };
    renderShell();
    try {
      const result = await fetchJson("/api/documents/query", {
        method: "POST",
        body: { query, path: appState.documents.path || "Documents" }
      });
      if (result.ok && result.data?.ok) {
        appState.documents = { ...appState.documents, status: "ready", answer: result.data, items: result.data.evidence || appState.documents.items, error: "" };
      } else {
        appState.documents = { ...appState.documents, status: "error", error: result.data?.error || `documents_query_failed:${result.status}` };
      }
    } catch (error) {
      appState.documents = { ...appState.documents, status: "error", error: error.message || String(error) };
    }
    renderShell();
  }

  async function loadReportsData() {
    if (!appState.authToken) {
      appState.reports = { ...appState.reports, status: "auth", error: "" };
      if (appState.page === "reports") renderShell();
      return;
    }
    appState.reports = { ...appState.reports, status: "loading", error: "" };
    if (appState.page === "reports") renderShell();
    try {
      const result = await fetchJson("/api/reports/list");
      if (result.ok && result.data?.ok) {
        const items = Array.isArray(result.data.reports) ? result.data.reports : [];
        appState.reports = {
          ...appState.reports,
          status: items.length ? "ready" : "ready-empty",
          items,
          selectedId: appState.reports.selectedId && items.some((item) => item.id === appState.reports.selectedId) ? appState.reports.selectedId : items[0]?.id || "",
          error: ""
        };
      } else if (result.status === 401) {
        appState.reports = { ...appState.reports, status: "auth", error: "" };
      } else {
        appState.reports = { ...appState.reports, status: "error", error: result.data?.error || `reports_list_failed:${result.status}` };
      }
    } catch (error) {
      appState.reports = { ...appState.reports, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "reports") renderShell();
  }

  async function exportSelectedReport() {
    const selectedId = appState.reports.selectedId || appState.reports.items[0]?.id || "";
    if (!selectedId) {
      showToast("没有可导出的报告");
      return;
    }
    try {
      const result = await fetchJson("/api/reports/export", { method: "POST", body: { report_id: selectedId } });
      if (!result.ok || !result.data?.ok) {
        showToast(`报告导出失败：${result.data?.error || result.status}`);
        return;
      }
      appState.reports = { ...appState.reports, export: result.data.export };
      renderShell();
      showToast("报告已导出为 Markdown");
    } catch (error) {
      showToast(`报告导出失败：${error.message || error}`);
    }
  }

  async function loadTokenBudgetData() {
    appState.tokenBudget = { ...appState.tokenBudget, status: "loading", error: "" };
    if (appState.page === "tokenBudget") renderShell();
    try {
      const [summary, benchmark] = await Promise.all([
        fetchJson("/api/token-budget/summary"),
        fetchJson("/api/token-budget/benchmark-summary")
      ]);
      if (summary.ok && summary.data?.ok) {
        appState.tokenBudget = {
          ...appState.tokenBudget,
          status: "ready",
          summary: summary.data,
          benchmark: benchmark.data || null,
          error: ""
        };
      } else {
        appState.tokenBudget = { ...appState.tokenBudget, status: "error", summary: null, benchmark: null, error: summary.data?.error || `token_budget_failed:${summary.status}` };
      }
    } catch (error) {
      appState.tokenBudget = { ...appState.tokenBudget, status: "error", summary: null, benchmark: null, error: error.message || String(error) };
    }
    if (appState.page === "tokenBudget") renderShell();
  }

  async function estimateTokenBudgetSample() {
    const payload = {
      message: "请基于 NAS 文档做本地优先摘要，并在必要时脱敏后估算云端 token。",
      task_type: "ui_token_budget_estimate",
      workspace: "openclaw-web",
      context_text: `user=${appState.authUser?.username || "web"}\npage=tokenBudget`
    };
    const result = await fetchJson("/api/token-budget/route", { method: "POST", body: payload });
    appState.tokenBudget = { ...appState.tokenBudget, trace: result.data || null };
    showToast(result.ok && result.data?.ok ? "Token Budget 估算已记录" : "Token Budget 估算失败");
    await loadTokenBudgetData();
  }

  async function sendAssistantPrompt() {
    const message = appState.prompt.trim();
    if (!message) return;
    if (!appState.authToken) {
      appState.assistant = { ...appState.assistant, status: "auth", error: "auth_required" };
      renderShell();
      return;
    }
    const requestSerial = ++assistantRequestSerial;
    appState.assistant = { status: "loading", answer: "", route: null, error: "" };
    renderShell();
    const routePromise = fetchJson("/api/token-budget/route", {
      method: "POST",
      body: {
        message,
        task_type: "nas_assistant",
        workspace: "openclaw-web",
        context_text: `user=${appState.authUser?.username || "web"}\npage=${appState.page}`
      }
    }).catch(() => null);
    try {
      const copilot = await fetchJson("/api/copilot/chat", { method: "POST", body: { message } });
      if (requestSerial !== assistantRequestSerial) return;
      if (copilot.ok && copilot.data?.ok) {
        const copilotData = copilot.data || {};
        appState.assistant = {
          status: "ready",
          answer: copilotData.assistant_mode && copilotData.answer ? presentAssistantAnswer(copilotData) : describeCopilotResult(copilotData),
          route: null,
          mode: copilotData.assistant_mode || "",
          copilot: copilotData,
          toolLabel: assistantToolLabelFromCopilot(copilotData),
          error: ""
        };
      } else if (copilot.status === 401 || copilot.data?.error === "auth_required") {
        appState.assistant = { status: "auth", answer: "", route: null, error: "auth_required" };
      } else {
        appState.assistant = { status: "error", answer: "", route: null, error: copilot.data?.error || `copilot_failed:${copilot.status}` };
      }
    } catch (error) {
      if (requestSerial !== assistantRequestSerial) return;
      appState.assistant = { status: "error", answer: "", route: null, error: error.message || String(error) };
    }
    appState.prompt = "";
    renderShell();
    routePromise.then((route) => {
      if (!route || requestSerial !== assistantRequestSerial || appState.assistant.status !== "ready") return;
      appState.assistant = { ...appState.assistant, route: route.ok && route.data?.ok ? route.data : null };
      if (appState.page === "assistant") renderShell();
    });
  }

  function presentAssistantAnswer(data) {
    const mode = data.assistant_mode || "";
    const action = data.nas_action || {};
    if (data.search) return data.answer || "已完成本地检索。";
    if (mode === "local_document_query") {
      if (data.answer) return data.answer;
      const count = data.evidence_count ?? (Array.isArray(data.evidence) ? data.evidence.length : 0);
      return count
        ? `已在本地文档库完成检索，找到 ${count} 条可引用证据。下方卡片列出来源文件和摘要片段，私有文档未发送到云端。`
        : "已在本地文档库完成检索，当前没有找到可靠证据。私有文档未发送到云端。";
    }
    if (action.operation === "list") {
      const count = Array.isArray(action.entries) ? action.entries.length : Array.isArray(data.entries) ? data.entries.length : 0;
      return `已通过本地权限检查列出目录，找到 ${count} 个条目。下方展示文件和文件夹卡片。`;
    }
    if (action.operation === "storage_status") return "已读取本地 NAS 存储状态，下方展示关键容量和索引信息。";
    if (action.operation === "media_summary") return "已读取本地媒体库概览，下方展示照片、相册和索引状态。";
    if (action.operation === "ops_summary") return "已读取本地运行健康概览，下方展示检查项和告警状态。";
    if (action.operation === "apps_summary") return "已读取本地应用生态概览，下方展示插件和协议状态。";
    if (action.operation === "audit_summary") return "已读取本地审计概览，下方展示最近操作记录。";
    if (action.operation === "reports_list") return "已读取本地报告列表，下方展示最近可查看的报告。";
    if (action.operation === "cloud_overflow") return data.answer || (data.cloud_used ? "该非隐私任务已通过受控云端路径处理。" : "Qwen 判断该任务可外溢到云端，但当前环境未配置云端服务，因此没有发送任何云端请求。");
    if (action.operation && action.operation !== "none") return data.answer || "本地操作已完成，下方展示结果。";
    return data.answer || describeCopilotResult(data);
  }

  function describeCopilotResult(data) {
    if (data.assistant_mode && data.answer) {
      return data.answer;
    }
    const action = data.nas_action || {};
    if (action.operation === "list") {
      return `已通过本地受控服务读取目录，返回 ${fmtCount(action.entries?.length)} 个条目。`;
    }
    if (action.operation === "copy") {
      return "已识别为受控复制任务，直接复制未执行，需要先预览、试运行、确认，再执行或回滚。";
    }
    if (action.operation === "inspect") {
      return "已完成只读路径检查；模型没有获得文件写入或高风险工具执行权。";
    }
    if (action.operation) {
      return "该意图已进入安全边界检查，默认服务仅允许只读检查和受控单文件复制。";
    }
    if (data.error) return data.error;
    return "已完成本地意图理解，本次没有触发文件写入工具。";
  }

  function openNotifications() {
    const storageConnected = appState.storage.status === "ready" || Boolean(appState.dashboard?.storage);
    const identityText = appState.authToken ? "当前浏览器已登录" : "尚未登录文件接口";
    showWorkflow("通知", `
      <div class="mini-row"><span>${badge(storageConnected ? "已读取" : "待连接", storageConnected ? "success" : "neutral")} ${storageConnected ? "已读取本地个人空间状态" : "连接设备后读取文件与容量状态"}</span><span class="muted small">当前会话</span></div>
      <div class="mini-row"><span>${badge("安全", "warning")} 删除、移动、覆盖、递归操作保持禁用</span><span class="muted small">本地执行边界</span></div>
      <div class="mini-row"><span>${badge(appState.authToken ? "已登录" : "待登录", "neutral")} ${escapeHtml(identityText)}；写入仍需路径权限</span><span class="muted small">ACL</span></div>
    `);
  }

  function openHelp() {
    showWorkflow("使用指南", `
      <p>网页端所有 NAS 动作都先进入本地 API，再由身份、ACL 和本地执行边界判断是否允许。</p>
      ${renderKeyValueRows([
        ["读操作", "目录浏览、下载、文档检索、审计查询"],
        ["安全写操作", "新建文件夹、无覆盖上传、手动 Journal、备份任务记录"],
        ["受控写操作", "单文件复制：预览、试运行、确认、执行、回滚"],
        ["默认禁用", "删除、移动、重命名、改权限、覆盖、递归操作"]
      ])}
    `);
  }

  function openUserMenu() {
    const user = appState.authUser || { username: "未登录", role: "guest" };
    showWorkflow(appState.authUser ? "用户与身份" : "登录与身份", `
      ${renderKeyValueRows([
        ["用户", user.username],
        ["角色", user.role],
        ["身份令牌", appState.authToken ? "当前浏览器会话已保存" : "未登录"],
        ["当前页", navItems.find((item) => item.id === appState.page)?.label || appState.page]
      ])}
      <div class="copy-actions" style="margin-top:14px">
        ${appState.authUser
          ? `${button("打开设置", { variant: "secondary", icon: "settings", page: "settings" })}${button("退出登录", { variant: "secondary", action: "storageLogout" })}`
          : button("前往登录", { icon: "lock", page: "files" })}
      </div>
    `);
  }

  function openMobileMore() {
    const secondaryItems = navItems.filter((item) => !mobilePrimaryNavIds.includes(item.id));
    showWorkflow("更多功能", `
      <nav class="mobile-more-grid" aria-label="更多页面">
        ${secondaryItems.map((item) => `<button class="mobile-more-item${item.id === appState.page ? " active" : ""}" type="button" data-page="${escapeHtml(item.id)}"${item.id === appState.page ? ' aria-current="page"' : ""}>${svg(item.icon)}<span>${escapeHtml(item.label)}</span></button>`).join("")}
      </nav>
    `);
  }

  function openDashboardTasks() {
    setPage("audit");
  }

  async function openTokenDetails() {
    showWorkflow("Token / 路由详情", `<div class="skeleton-list"><span></span><span></span><span></span></div>`);
    try {
      const [summary, benchmark] = await Promise.all([
        fetchJson("/api/token-budget/summary"),
        fetchJson("/api/token-budget/benchmark-summary")
      ]);
      const payload = summary.data || {};
      const bench = benchmark.data || {};
      const analysis = payload.latest_analysis || {};
      const benchmarkSummary = bench.benchmark_summary || bench || {};
      showWorkflow("Token / 路由详情", `
        ${renderKeyValueRows([
          ["统计状态", payload.ok ? "已读取" : "需复查"],
          ["Benchmark 状态", bench.ok ? "已读取" : "需复查"],
          ["分词器", payload.tokenizer_identity?.tokenizer_name || payload.tokenizer_identity?.source || "Qwen 分词器"],
          ["平均降幅", analysis.average_reduction_ratio != null ? fmtRatio(analysis.average_reduction_ratio) : "暂无"],
          ["质量通过率", analysis.quality_pass_rate != null ? fmtRatio(analysis.quality_pass_rate) : "暂无"],
          ["隐私泄漏", fmtCount(analysis.private_leak_count)],
          ["评测用例", benchmarkSummary.case_count || benchmarkSummary.total_cases || "暂无"],
          ["私有上下文", "默认留在 S100P"]
        ])}
        <div class="soft-note">这里展示给用户可理解的统计摘要；完整 JSON 报告仍保留在本地 reports 目录供交付审计使用。</div>
      `);
    } catch (error) {
      showWorkflow("Token / 路由详情", `<div class="soft-note error-note"><strong>读取失败</strong><p>${escapeHtml(error.message || String(error))}</p></div>`, "danger");
    }
  }

  function assistantGuide() {
    openHelp();
  }

  function assistantAttach() {
    const selected = selectedStorageEntry();
    showWorkflow("附件", `
      <p>附件不会绕过文件权限。先在“文件”页选择本地文件，AI 助手只接收受控文件引用和脱敏上下文。</p>
      ${renderKeyValueRows([
        ["当前选中", selected ? displayName(selected, "已选择文件") : appState.selectedFile ? displayLocation(appState.selectedFile) : "未选择"],
        ["文件接口", appState.authToken ? "已登录" : "未登录"],
        ["后续动作", "选择文件后可复制路径，或在输入框引用路径触发本地工具路由"]
      ])}
      <div class="copy-actions" style="margin-top:14px">${button("打开文件", { variant: "secondary", icon: "files", page: "files" })}</div>
    `);
  }

  function assistantContinue() {
    const basis = appState.assistant.answer || "请基于刚才的本地 NAS 检索结果继续追问。";
    appState.prompt = `继续追问：${basis.slice(0, 120)}`;
    renderShell();
    document.getElementById("assistantPrompt")?.focus();
  }

  function assistantKeyPoints() {
    const text = appState.assistant.answer || "还没有 AI 助手回答。请先发送一次问题。";
    const points = text.split(/[。；;.\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 6);
    showWorkflow("提炼要点", `<ul class="workflow-list">${points.map((point) => `<li>${escapeHtml(point)}</li>`).join("") || "<li>暂无可提炼内容。</li>"}</ul>`);
  }

  function assistantMindmap() {
    const route = appState.assistant.route || {};
    showWorkflow("思维导图", `
      <div class="mindmap">
        <div class="mindmap-node root">AI 助手结果</div>
        <div class="mindmap-branches">
          <div class="mindmap-node">意图：${escapeHtml(appState.assistant.answer || "待提问")}</div>
          <div class="mindmap-node">路由：${escapeHtml(route.route || "local_first")}</div>
          <div class="mindmap-node">隐私：${escapeHtml(route.cloud_allowed ? "允许云端" : "本地保留")}</div>
          <div class="mindmap-node">执行：本地受控 API</div>
        </div>
      </div>
    `);
  }

  function assistantExport() {
    const answer = appState.assistant.answer;
    if (!answer) {
      showToast("请先生成一条 AI 助手回答");
      return;
    }
    const route = appState.assistant.route || {};
    const copilot = appState.assistant.copilot || {};
    const markdown = `# AI 助手回答\n\n${answer}\n\n## 服务信息\n\n- 处理位置：${copilot.cloud_used ? "受控云端" : "S100P 本地"}\n- 路由：${route.route || copilot.route || "local_first"}\n- 云端调用：${copilot.cloud_used ? "是" : "否"}\n- 执行权限：Qwen 不直接执行 NAS 写操作\n`;
    downloadTextFile(`ai-nas-assistant-${Date.now()}.md`, markdown, "text/markdown;charset=utf-8");
    showToast("助手回答已导出为 Markdown");
  }

  function assistantEvidenceSources() {
    const copilot = appState.assistant.copilot || {};
    const searchResults = Array.isArray(copilot.search?.results) ? copilot.search.results : [];
    const evidence = Array.isArray(copilot.evidence) ? copilot.evidence : [];
    if (searchResults.length) {
      showWorkflow("本次证据", renderAssistantSearchResults({ results: searchResults, result_count: searchResults.length, labels: copilot.search?.labels || [], privacy: copilot.search?.privacy || {} }));
      return;
    }
    if (evidence.length) {
      showWorkflow("本次证据", renderDocumentEvidence(evidence));
      return;
    }
    showWorkflow("本次证据", `<div class="empty-state">${svg("search")}<strong>暂无证据</strong><p>发送检索或文档问答后，这里只展示真实返回的本地证据。</p></div>`);
  }

  function assistantRecentFiles() {
    showWorkflow("最近使用的文件", `
      <p>最近文件入口会落到真实文件管理器。当前页只保留最近文件摘要，不直接绕过权限读取正文。</p>
      <div class="copy-actions">${button("打开文件管理器", { variant: "secondary", icon: "files", page: "files" })}${button("打开文档问答", { variant: "secondary", icon: "docs", page: "documents" })}</div>
    `);
  }

  function assistantTrace() {
    const route = appState.assistant.route || {};
    const copilot = appState.assistant.copilot || {};
    const modelRouting = copilot.model_routing || {};
    const decision = modelRouting.decision || copilot.routing_decision || {};
    const calls = Array.isArray(modelRouting.calls) ? modelRouting.calls : [];
    showWorkflow("服务详情", `
      ${renderKeyValueRows([
        ["请求 ID", decision.request_id || copilot.request_id || "暂无"],
        ["策略路由", decision.selected_route || "暂无"],
        ["处理位置", copilot.cloud_used ? "受控云端" : "S100P 本地"],
        ["路由", route.route || copilot.route || "local_first"],
        ["隐私级别", `${decision.privacy_level ?? "暂无"} · ${privacyLabel(decision.privacy_label || "local_only")}`],
        ["复杂度", decision.complexity ?? "暂无"],
        ["需要最新信息", decision.freshness_required ? "是" : "否"],
        ["需要公开网络", decision.requires_public_web ? "是" : "否"],
        ["混合候选", decision.hybrid_candidate ? (decision.hybrid_status || "是") : "否"],
        ["云端调用", copilot.cloud_used ? "是" : "否"],
        ["脱敏次数", route.redaction_count ?? "暂无"],
        ["执行权限", "Qwen 不直接执行 NAS 写操作"]
      ])}
      ${calls.length ? `<h4>本次模型调用</h4>${renderKeyValueRows(calls.map((call, index) => [
        `调用 ${index + 1} · ${call.stage || "unknown"}`,
        `${call.model || "无模型"} · ${call.provider || "未知 provider"} · ${call.location || "未知位置"} · ${call.status || "unknown"}${Number.isFinite(Number(call.elapsed_ms)) ? ` · ${Number(call.elapsed_ms).toFixed(1)} ms` : ""}`
      ]))}` : '<p class="muted small">本次没有调用语言模型。</p>'}
    `);
  }

  function assistantAgents() {
    showWorkflow("可用能力", `
      <div class="grid two-col">
        ${card(`<strong>本地图片检索</strong><p class="muted small">通过 AI 助手输入“找有人的图片”，优先走 YOLO 对象索引，再走本地多模态语义检索。</p>${button("打开助手", { variant: "secondary", page: "assistant" })}`)}
        ${card(`<strong>文档问答</strong><p class="muted small">跳转到文档页执行真实路径检索，不展示样例文件。</p>${button("打开文档", { variant: "secondary", page: "documents" })}`)}
        ${card(`<strong>文件管理</strong><p class="muted small">在权限内浏览、上传和创建文件夹。</p>${button("打开文件", { variant: "secondary", page: "files" })}`)}
        ${card(`<strong>审计查看</strong><p class="muted small">查看真实本地操作记录和脱敏详情。</p>${button("打开审计", { variant: "secondary", page: "audit" })}`)}
      </div>
    `);
  }

  function downloadTextFile(filename, text, mimeType = "text/plain;charset=utf-8") {
    const blob = new Blob([text], { type: mimeType });
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  }

  async function loadJournalData() {
    appState.journal = { ...appState.journal, status: "loading", error: "" };
    if (appState.page === "journal") renderShell();
    try {
      const [health, timeline] = await Promise.all([
        fetchJson("/api/journal/health"),
        fetchJson("/api/journal/timeline")
      ]);
      const events = Array.isArray(timeline.data?.events) ? timeline.data.events : [];
      appState.journal = {
        ...appState.journal,
        status: health.ok && timeline.ok ? (events.length ? "ready" : "ready-empty") : "error",
        text: health.data?.ok ? `日记索引 ${health.data.stats?.journal_events || 0} 条` : "日记索引需复查",
        events,
        error: health.ok && timeline.ok ? "" : (health.data?.error || timeline.data?.error || "journal_api_failed")
      };
    } catch (error) {
      appState.journal = { ...appState.journal, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "journal") renderShell();
  }

  async function createManualJournalEntry() {
    const title = document.getElementById("journalTitle")?.value.trim() || "网页端验证手动记录";
    const body = document.getElementById("journalBody")?.value.trim() || "Codex 网页端逐条验证时创建的受控样本记录。";
    const result = await fetchJson("/api/journal/manual-entry", {
      method: "POST",
      body: { project_id: "project_ai_nas_web_verify", title, body, evidence_refs: ["ui_local_check"] }
    });
    if (result.ok && result.data?.ok) {
      showToast("手动笔记已写入本地 Journal");
      await loadJournalData();
    } else {
      showToast(`手动笔记失败：${result.data?.error || result.status}`);
    }
  }

  async function generateJournalSummary(periodType = "daily") {
    appState.journal = { ...appState.journal, status: "loading" };
    renderShell();
    const result = await fetchJson("/api/journal/generate-summary", {
      method: "POST",
      body: { period_type: periodType, project_id: "all" }
    });
    if (result.ok && result.data?.ok) {
      appState.journal = { ...appState.journal, status: "ready", summary: result.data.summary, error: "" };
    } else {
      appState.journal = { ...appState.journal, status: "error", error: result.data?.error || `summary_failed:${result.status}` };
    }
    renderShell();
  }

  async function exportJournalMarkdown() {
    const result = await fetchJson("/api/journal/export", {
      method: "POST",
      body: { export_type: "markdown", period_type: "daily", project_id: "all" }
    });
    if (result.ok && result.data?.ok) {
      appState.journal = { ...appState.journal, export: result.data.export };
      renderShell();
      showToast("Markdown 已导出到本地证据目录");
    } else {
      showToast(`导出失败：${result.data?.error || result.status}`);
    }
  }

  async function loadAuditData() {
    const query = appState.audit.query || "";
    if (!appState.authToken) {
      appState.audit = { ...appState.audit, status: "auth", query, error: "" };
      if (appState.page === "audit") renderShell();
      return;
    }
    appState.audit = { ...appState.audit, status: "loading", query, error: "" };
    if (appState.page === "audit") renderShell();
    try {
      const result = await fetchJson("/api/audit/summary");
      if (result.ok && result.data?.ok) {
        const operations = Array.isArray(result.data.operations) ? result.data.operations : [];
        appState.audit = { status: "ready", operations, query, error: "" };
      } else {
        appState.audit = { status: result.status === 401 ? "auth" : "error", operations: [], query, error: result.data?.error || `audit_failed:${result.status}` };
      }
    } catch (error) {
      appState.audit = { status: "error", operations: [], query, error: error.message || String(error) };
    }
    if (appState.page === "audit") renderShell();
  }

  async function runAiAlbumAutoOrganize(options = {}) {
    if (!appState.authToken) return null;
    if (!options.noRender) {
      appState.aiAlbum = { ...appState.aiAlbum, autoOrganizeStatus: "loading" };
      if (appState.page === "aiAlbum") renderShell();
    }
    try {
      const result = await fetchJson("/api/ai-album/auto-organize", {
        method: "POST",
        body: { max_files: 10000 }
      });
      appState.aiAlbum = {
        ...appState.aiAlbum,
        autoOrganize: result.data || null,
        autoOrganizeStatus: result.ok && result.data?.ok !== false ? "ready" : "error"
      };
      if (!options.silent && result.ok && result.data?.ok !== false) {
        showToast(result.data?.changed ? "已整理新增图片" : "没有新增图片需要整理");
      }
      return result;
    } catch (error) {
      appState.aiAlbum = {
        ...appState.aiAlbum,
        autoOrganizeStatus: "error",
        autoOrganize: { ok: false, error: error.message || String(error) }
      };
      if (!options.silent) showToast(`自动整理失败：${error.message || error}`);
      return null;
    } finally {
      if (!options.noRender && appState.page === "aiAlbum") renderShell();
    }
  }

  async function loadMediaData() {
    await loadProtectedSummary("media", "/api/media/summary?scope=library");
    if (!appState.authToken || !appState.media.summary) return;
    let photoItems = Array.isArray(appState.media.summary.photos) ? appState.media.summary.photos : [];
    const settledValue = (result) => (result.status === "fulfilled" ? result.value : { ok: false, status: 0, data: null });
    try {
      const [statusResult, facetsResult, assetsResult, categoriesResult, organizeStatusResult] = await Promise.allSettled([
        fetchJson("/api/ai-space/status"),
        fetchJson("/api/ai-space/facets"),
        fetchJson("/api/ai-space/assets?limit=10000"),
        fetchJson("/api/smart-classification/categories"),
        fetchJson("/api/ai-album/organize-status?max_files=10000")
      ]);
      const status = settledValue(statusResult);
      const facets = settledValue(facetsResult);
      const assets = settledValue(assetsResult);
      const categories = settledValue(categoriesResult);
      const organizeStatus = settledValue(organizeStatusResult);
      const previousAssets = Array.isArray(appState.aiAlbum.assets) ? appState.aiAlbum.assets : [];
      const previousCategories = Array.isArray(appState.aiAlbum.smartCategories) ? appState.aiAlbum.smartCategories : [];
      appState.aiAlbum = {
        ...appState.aiAlbum,
        status: status.ok && status.data?.ok !== false ? "ready" : "error",
        error: status.ok ? "" : status.data?.error || `ai_album_failed:${status.status}`,
        statusPayload: status.data || null,
        facets: facets.data || null,
        assets: Array.isArray(assets.data?.assets) ? assets.data.assets : previousAssets,
        mediaPhotos: photoItems,
        smartCategories: Array.isArray(categories.data?.categories) ? categories.data.categories : previousCategories,
        organizeStatus: organizeStatus.ok && organizeStatus.data?.ok !== false ? organizeStatus.data : appState.aiAlbum.organizeStatus
      };
    } catch (_error) {
      appState.aiAlbum = {
        ...appState.aiAlbum,
        mediaPhotos: photoItems
      };
    }
    if (appState.page === "media") renderShell();
  }

  async function selectMediaAlbum(albumName) {
    const name = String(albumName || "").trim();
    if (!name) return;
    appState.media = {
      ...appState.media,
      selectedAlbumName: name,
      selectedAlbumStatus: "loading",
      selectedAlbumPhotos: [],
      selectedAlbumError: ""
    };
    if (appState.page === "media") renderShell();
    try {
      const result = await fetchJson(`/api/media/album?name=${encodeURIComponent(name)}`);
      if (result.ok && result.data?.ok) {
        appState.media = {
          ...appState.media,
          selectedAlbumName: name,
          selectedAlbumStatus: "ready",
          selectedAlbumPhotos: Array.isArray(result.data.photos) ? result.data.photos : [],
          selectedAlbumError: ""
        };
      } else {
        appState.media = {
          ...appState.media,
          selectedAlbumName: name,
          selectedAlbumStatus: "error",
          selectedAlbumPhotos: [],
          selectedAlbumError: result.data?.error || `album_failed:${result.status}`
        };
      }
    } catch (error) {
      appState.media = {
        ...appState.media,
        selectedAlbumName: name,
        selectedAlbumStatus: "error",
        selectedAlbumPhotos: [],
        selectedAlbumError: error.message || String(error)
      };
    }
    if (appState.page === "media") renderShell();
  }

  function clearMediaAlbumSelection() {
    appState.media = {
      ...appState.media,
      selectedAlbumName: "",
      selectedAlbumStatus: "idle",
      selectedAlbumPhotos: [],
      selectedAlbumError: ""
    };
    renderShell();
  }

  function scheduleAiAlbumSelectAsset(assetId) {
    window.clearTimeout(aiAlbumSelectTimer);
    aiAlbumSelectTimer = window.setTimeout(() => {
      appState.aiAlbum = { ...appState.aiAlbum, selectedAssetId: assetId || "" };
      renderShell();
    }, 180);
  }

  function aiAlbumNormalizeSearchResult(item) {
    const raw = item?.asset || item?.item || item?.media || item || {};
    const id = String(raw.asset_id || item?.asset_id || raw.id || item?.id || "");
    const base = id ? (appState.aiAlbum.assets || []).find((asset) => aiAlbumAssetId(asset) === id) || {} : {};
    return {
      ...base,
      ...raw,
      asset_id: id || raw.asset_id || base.asset_id,
      match_reason: item?.match_reason || item?.reason || item?.summary || raw.match_reason || raw.summary_redacted || "",
      search_score: item?.score ?? item?.match_score ?? raw.score ?? raw.match_score
    };
  }

  function aiAlbumIsIdentityQuery(query) {
    return /(这个人是谁|是谁|认出|身份|名字|姓名|人脸识别|识别这个人|face\s*id|identity|who\s+is)/i.test(String(query || ""));
  }

  function aiAlbumLooksPersonQuery(query) {
    return /(人|人物|人像|上衣|衣服|服装|person|people|shirt|clothes)/i.test(String(query || ""));
  }

  function aiAlbumPayloadResults(payload) {
    const candidates = [
      payload?.results,
      payload?.assets,
      payload?.items,
      payload?.matches,
      payload?.search?.results
    ];
    for (const current of candidates) {
      if (Array.isArray(current)) return current;
    }
    return [];
  }

  async function loadAiAlbumData() {
    if (!appState.authToken) {
      appState.aiAlbum = { ...appState.aiAlbum, status: "auth", error: "" };
      if (appState.page === "aiAlbum") renderShell();
      return;
    }
    appState.aiAlbum = { ...appState.aiAlbum, status: "loading", error: "" };
    if (appState.page === "aiAlbum") renderShell();
    try {
      const [status, facets, assets, photos, categories, autoStatus] = await Promise.all([
        fetchJson("/api/ai-space/status"),
        fetchJson("/api/ai-space/facets"),
        fetchJson("/api/ai-space/assets?limit=500"),
        fetchJson("/api/media/photos?limit=500&scope=library"),
        fetchJson("/api/smart-classification/categories"),
        fetchJson("/api/auto-organize/status")
      ]);
      const assetItems = Array.isArray(assets.data?.assets) ? assets.data.assets : [];
      const photoItems = Array.isArray(photos.data?.photos) ? photos.data.photos : [];
      const categoryItems = Array.isArray(categories.data?.categories) ? categories.data.categories : [];
      const firstId = assetItems[0] ? aiAlbumAssetId(assetItems[0]) : "";
      const selectedAssetId = appState.aiAlbum.selectedAssetId && assetItems.some((asset) => aiAlbumAssetId(asset) === appState.aiAlbum.selectedAssetId)
        ? appState.aiAlbum.selectedAssetId
        : firstId;
      const hardError = !status.ok || status.data?.ok === false || !assets.ok || assets.data?.ok === false;
      appState.aiAlbum = {
        ...appState.aiAlbum,
        status: hardError ? "error" : assetItems.length ? "ready" : "ready-empty",
        error: hardError ? (status.data?.error || assets.data?.error || `ai_album_failed:${status.status || assets.status}`) : "",
        statusPayload: status.data || null,
        facets: facets.data || null,
        assets: assetItems,
        mediaPhotos: photoItems,
        smartCategories: categoryItems,
        autoStatus: autoStatus.data || null,
        selectedAssetId,
        searchResults: null,
        searchStatus: "idle",
        searchError: "",
        blockedQuery: null
      };
    } catch (error) {
      appState.aiAlbum = { ...appState.aiAlbum, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "aiAlbum") renderShell();
  }

  function setMediaUploadState(status, error = "") {
    appState.media = { ...appState.media, uploadStatus: status, uploadError: error };
    if (appState.page === "media" || appState.page === "aiAlbum") renderShell();
  }

  function chooseMediaUploadFile() {
    if (!appState.authToken) {
      showToast("请先连接 NAS 文件接口");
      return;
    }
    const input = document.getElementById("mediaUploadInput");
    if (!input) {
      showToast("上传入口未就绪");
      return;
    }
    input.value = "";
    input.click();
  }

  function mediaUploadLooksImage(file) {
    const name = String(file?.name || "").toLowerCase();
    return Boolean(file?.type?.startsWith("image/")) || /\.(jpg|jpeg|png|webp|bmp|gif|tif|tiff)$/.test(name);
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error || new Error("file_read_failed"));
      reader.onload = () => {
        const value = String(reader.result || "");
        resolve(value.includes(",") ? value.split(",", 2)[1] : value);
      };
      reader.readAsDataURL(file);
    });
  }

  async function rebuildAiAlbumIndex(options = {}) {
    if (!appState.authToken) {
      showToast("请先连接 NAS 文件接口");
      return null;
    }
    if (!options.silent) showToast("正在刷新相册索引");
    const result = await fetchJson("/api/ai-album/rebuild", {
      method: "POST",
      body: {
        max_files: 5000,
        yolo_max_files: 16,
        include_video: false,
        run_yolo: false
      }
    });
    if (!result.ok || result.data?.ok === false) {
      const message = result.data?.error || (result.data?.required_failed || []).join(", ") || `ai_album_rebuild_failed:${result.status}`;
      if (!options.silent) showToast(`索引刷新失败：${message}`);
      return result;
    }
    await loadMediaData();
    if (!options.silent) showToast("相册索引已更新");
    return result;
  }

  async function runMediaOrganizeNow() {
    if (!appState.authToken) {
      showToast("请先连接 NAS 文件接口");
      return;
    }
    appState.aiAlbum = { ...appState.aiAlbum, organizeRunStatus: "loading", organizeError: "" };
    if (appState.page === "media") renderShell();
    try {
      const result = await fetchJson("/api/ai-album/organize-now", {
        method: "POST",
        body: { max_files: 10000 }
      });
      if (!result.ok || result.data?.ok === false) {
        const message = result.data?.error || `organize_failed:${result.status}`;
        appState.aiAlbum = { ...appState.aiAlbum, organizeRunStatus: "error", organizeError: message };
        showToast(`整理失败：${message}`);
        if (appState.page === "media") renderShell();
        return;
      }
      appState.aiAlbum = {
        ...appState.aiAlbum,
        organizeRunStatus: "ready",
        organizeLastRun: result.data || null,
        organizeStatus: result.data?.status || appState.aiAlbum.organizeStatus,
        organizeError: ""
      };
      const pending = Number(result.data?.status?.pending_count ?? 0);
      showToast(`整理完成：待整理 ${fmtCount(pending)} 张`);
      await loadMediaData();
    } catch (error) {
      const message = error.message || String(error);
      appState.aiAlbum = { ...appState.aiAlbum, organizeRunStatus: "error", organizeError: message };
      showToast(`整理失败：${message}`);
      if (appState.page === "media") renderShell();
    }
  }

  async function uploadMediaImageFile(file) {
    if (!file) return;
    if (!mediaUploadLooksImage(file)) {
      showToast("只支持上传图片文件");
      return;
    }
    if (file.size > MEDIA_UPLOAD_MAX_BYTES) {
      showToast(`图片超过 ${formatBytes(MEDIA_UPLOAD_MAX_BYTES)}，请先压缩后上传`);
      return;
    }
    setMediaUploadState("loading");
    showToast("正在上传图片");
    try {
      const contentBase64 = await fileToBase64(file);
      const result = await fetchJson("/api/media/upload", {
        method: "POST",
        body: {
          filename: file.name || `uploaded_${Date.now()}.jpg`,
          content_base64: contentBase64,
          target_dir: "Photos/Uploads",
          auto_process: false
        }
      });
      if (!result.ok || result.data?.ok === false) {
        throw new Error(result.data?.error || `upload_failed:${result.status}`);
      }
      await loadMediaData();
      setMediaUploadState("ready");
      showToast("图片已上传到相册");
    } catch (error) {
      const message = error.message || String(error);
      setMediaUploadState("error", message);
      showToast(`上传失败：${message}`);
    }
  }

  async function runAiAlbumSearch(queryOverride = "") {
    const query = String(queryOverride || document.getElementById("aiAlbumSearch")?.value || appState.aiAlbum.query || "").trim();
    appState.aiAlbum = { ...appState.aiAlbum, query };
    if (!query) {
      appState.aiAlbum = { ...appState.aiAlbum, searchStatus: "idle", searchResults: null, searchError: "", blockedQuery: null };
      renderShell();
      return;
    }
    if (aiAlbumIsIdentityQuery(query)) {
      appState.aiAlbum = {
        ...appState.aiAlbum,
        searchStatus: "blocked",
        searchResults: [],
        searchError: "",
        blockedQuery: {
          query,
          reason: "identity_recognition_blocked",
          face_identification_enabled: false,
          biometric_recognition_enabled: false,
          sensitive_attribute_inference_enabled: false
        }
      };
      renderShell();
      showToast("身份识别类查询已在本地拦截");
      return;
    }
    if (!appState.authToken) {
      appState.aiAlbum = { ...appState.aiAlbum, status: "auth", searchStatus: "idle" };
      renderShell();
      return;
    }
    appState.aiAlbum = { ...appState.aiAlbum, searchStatus: "loading", searchResults: [], searchError: "", blockedQuery: null };
    renderShell();
    try {
      const primaryPath = aiAlbumLooksPersonQuery(query) ? "/api/person-attribute/search" : "/api/ai-space/search";
      const primary = await fetchJson(primaryPath, { method: "POST", body: { query, top_k: 40 } });
      let results = primary.ok && primary.data?.ok !== false ? aiAlbumPayloadResults(primary.data).map(aiAlbumNormalizeSearchResult) : [];
      let secondary = null;
      if (!results.length && primaryPath !== "/api/multimodal-search/query") {
        const fallbackPath = primaryPath === "/api/person-attribute/search" ? "/api/ai-space/search" : "/api/multimodal-search/query";
        secondary = await fetchJson(fallbackPath, { method: "POST", body: { query, top_k: 40 } });
        if (secondary.ok && secondary.data?.ok !== false) {
          results = aiAlbumPayloadResults(secondary.data).map(aiAlbumNormalizeSearchResult);
        }
      }
      const ok = primary.ok && primary.data?.ok !== false;
      appState.aiAlbum = {
        ...appState.aiAlbum,
        searchStatus: results.length ? "ready" : ok ? "ready-empty" : "error",
        searchResults: results,
        searchError: ok ? "" : primary.data?.error || `search_failed:${primary.status}`,
        searchTrace: { primary: primary.data || null, secondary: secondary?.data || null }
      };
    } catch (error) {
      appState.aiAlbum = { ...appState.aiAlbum, searchStatus: "error", searchResults: [], searchError: error.message || String(error) };
    }
    renderShell();
  }

  function showAiAlbumPlanWorkflow() {
    const result = appState.aiAlbum.planResult;
    if (!result) {
      showWorkflow("相册整理计划", `<div class="empty-state compact">${svg("table")} 还没有生成整理计划。</div>`, "neutral");
      return;
    }
    showWorkflow("相册整理计划", renderAiAlbumPlanWorkflow(result), result.ok === false ? "danger" : "neutral");
  }

  function renderAiAlbumPlanWorkflow(result) {
    const items = Array.isArray(result.items) ? result.items : [];
    const dryRun = result.dry_run_result || null;
    const approve = result.approve_result || null;
    const execute = result.execute_result || null;
    const rollback = result.rollback_result || null;
    const boundaryRows = [
      ["计划状态", result.ok === false ? "未生成" : "已生成"],
      ["候选项", result.item_count ?? items.length ?? 0],
      ["阻塞原因", result.blocker || result.error || "暂无"],
      ["审批短语", result.approval_phrase || "暂无"],
      ["删除允许", result.delete_allowed ? "需复查" : "关闭"],
      ["覆盖允许", result.overwrite_allowed ? "需复查" : "关闭"],
      ["模型工具权限", result.qwen_execution_authority ? "需复查" : "关闭"],
      ["原始路径返回", result.raw_path_returned ? "需复查" : "关闭"]
    ];
    return `
      <div class="ai-album-workflow">
        ${renderKeyValueRows(boundaryRows)}
        <div class="detail-section">
          <strong>计划条目</strong>
          ${items.length ? `<div class="product-card-list">${items.slice(0, 8).map((item, index) => renderProductCard(
            item.suggested_filename_zh || item.display_name_zh || `整理项 ${index + 1}`,
            item.reason || item.category_name || item.resolution_source || "受控移动与命名计划",
            [item.ai_driven ? "AI 分类" : "规则计划", item.fallback_used ? "需复查" : "本地索引", "不删除不覆盖"],
            "media"
          )).join("")}</div>` : `<div class="empty-state compact">${escapeHtml(result.blocker || "当前没有可整理项。")}</div>`}
        </div>
        <div class="ai-album-workflow-actions">
          ${button("干跑检查", { variant: "secondary", icon: "table", action: "aiAlbumPlanDryRun", disabled: !result.plan_id })}
          ${button("审批计划", { variant: "secondary", icon: "check", action: "aiAlbumPlanApprove", disabled: !result.plan_id || !result.approval_phrase })}
          ${button("执行计划", { icon: "check", action: "aiAlbumPlanExecute", disabled: !result.plan_id || !result.approval_token })}
          ${button("回滚", { variant: "secondary", icon: "backup", action: "aiAlbumPlanRollback", disabled: !result.plan_id })}
        </div>
        ${dryRun ? `<div class="soft-note">${svg("table")} 干跑：${escapeHtml(dryRun.ok ? "通过" : dryRun.error || "未通过")}</div>` : ""}
        ${approve ? `<div class="soft-note">${svg("check")} 审批：${escapeHtml(approve.ok ? "已签发审批令牌" : approve.error || "未通过")}</div>` : ""}
        ${execute ? `<div class="soft-note ${execute.ok ? "" : "error-note"}">${svg("check")} 执行：${escapeHtml(execute.ok ? "已完成受控移动/命名" : execute.error || "未完成")}</div>` : ""}
        ${rollback ? `<div class="soft-note">${svg("backup")} 回滚：${escapeHtml(rollback.ok ? "已验证" : rollback.error || "未完成")}</div>` : ""}
      </div>
    `;
  }

  async function createAiAlbumOrganizePlan() {
    if (!appState.authToken) {
      appState.aiAlbum = { ...appState.aiAlbum, status: "auth" };
      renderShell();
      return;
    }
    appState.aiAlbum = { ...appState.aiAlbum, planStatus: "loading", planError: "", planResult: null };
    renderShell();
    try {
      const visibleCount = aiAlbumVisibleAssets().length || 1;
      const result = await fetchJson("/api/auto-organize/plan", {
        method: "POST",
        body: {
          mode: "move_and_rename",
          source_root: "Uploads",
          limit: Math.min(3, Math.max(1, visibleCount))
        }
      });
      if (result.ok && result.data) {
        appState.aiAlbum = { ...appState.aiAlbum, planStatus: result.data.ok === false ? "error" : "ready", planResult: result.data, planError: result.data.ok === false ? (result.data.blocker || result.data.error || "plan_blocked") : "" };
        showAiAlbumPlanWorkflow();
      } else {
        appState.aiAlbum = { ...appState.aiAlbum, planStatus: "error", planError: result.data?.error || `plan_failed:${result.status}`, planResult: result.data || null };
      }
    } catch (error) {
      appState.aiAlbum = { ...appState.aiAlbum, planStatus: "error", planError: error.message || String(error), planResult: null };
    }
    renderShell();
  }

  async function runAiAlbumPlanStep(step) {
    const current = appState.aiAlbum.planResult || {};
    const planId = current.plan_id;
    if (!planId) {
      showToast("请先生成整理计划");
      return;
    }
    const pathMap = {
      dryRun: "/api/auto-organize/dry-run",
      approve: "/api/auto-organize/approve",
      execute: "/api/auto-organize/execute",
      rollback: "/api/auto-organize/rollback"
    };
    const payloadMap = {
      dryRun: { plan_id: planId },
      approve: { plan_id: planId, approval_phrase: current.approval_phrase, approved_by: appState.authUser?.username || "ai_album_ui" },
      execute: { plan_id: planId, approval_token: current.approval_token },
      rollback: { plan_id: planId }
    };
    const path = pathMap[step];
    if (!path) return;
    try {
      const result = await fetchJson(path, { method: "POST", body: payloadMap[step] });
      const data = result.data || { ok: false, error: `step_failed:${result.status}` };
      const next = { ...current, [`${step === "dryRun" ? "dry_run" : step}_result`]: data };
      if (step === "approve" && data.approval_token) next.approval_token = data.approval_token;
      appState.aiAlbum = { ...appState.aiAlbum, planResult: next, planStatus: data.ok === false ? "error" : "ready", planError: data.ok === false ? (data.error || `${step}_failed`) : "" };
      showAiAlbumPlanWorkflow();
    } catch (error) {
      appState.aiAlbum = { ...appState.aiAlbum, planStatus: "error", planError: error.message || String(error) };
      showAiAlbumPlanWorkflow();
    }
    renderShell();
  }

  async function loadBackupData() {
    await loadProtectedSummary("backup", "/api/backup/summary");
  }

  async function createBackupTaskFromForm() {
    const currentName = document.getElementById("backupName")?.value || appState.backup.taskName || "本地备份任务";
    const taskName = currentName === "本地备份任务" ? `本地备份任务-${Date.now()}` : currentName;
    appState.backup.taskName = taskName;
    const backupNameInput = document.getElementById("backupName");
    if (backupNameInput) backupNameInput.value = taskName;
    backupCreatePromise = fetchJson("/api/backup/create-task", {
      method: "POST",
      body: {
        name: taskName,
        source: document.getElementById("backupSource")?.value || "Documents",
        dest: document.getElementById("backupDest")?.value || "Backups/Documents",
        interval_seconds: 0
      }
    });
    const result = await backupCreatePromise;
    backupCreatePromise = null;
    if (!result.ok || !result.data?.ok) {
      showToast(`备份任务创建失败：${result.data?.error || result.status}`);
      return result;
    }
    showToast("备份任务已创建");
    await loadBackupData();
    return result;
  }

  async function runBackupTaskFromForm() {
    if (backupCreatePromise) await backupCreatePromise.catch(() => null);
    const taskName = document.getElementById("backupName")?.value || appState.backup.taskName || "本地备份任务";
    appState.backup.taskName = taskName;
    const result = await fetchJson("/api/backup/run", { method: "POST", body: { name: taskName } });
    if (!result.ok || !result.data?.ok) {
      showToast(`备份运行失败：${result.data?.error || result.status}`);
    } else {
      showToast("备份运行完成");
    }
    await loadBackupData();
    return result;
  }

  async function loadSettingsData() {
    if (!appState.authToken) {
      appState.settings = { ...appState.settings, status: "auth", error: "" };
      if (appState.page === "settings") renderShell();
      return;
    }
    appState.settings = { ...appState.settings, status: "loading", error: "" };
    if (appState.page === "settings") renderShell();
    try {
      const [storage, users, harness, token] = await Promise.all([
        fetchJson("/api/storage/status"),
        fetchJson("/api/identity/users"),
        fetchJson("/api/harness/status"),
        fetchJson("/api/token-budget/summary")
      ]);
      appState.settings = {
        status: "ready",
        storage: storage.data || null,
        users: Array.isArray(users.data?.users) ? users.data.users : [],
        harness: harness.data || null,
        token: token.data || null,
        error: ""
      };
    } catch (error) {
      appState.settings = { ...appState.settings, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "settings") renderShell();
  }

  async function loadAgentRuntimeData() {
    appState.agentRuntime = { ...appState.agentRuntime, status: "loading", error: "" };
    if (appState.page === "agentRuntime") renderShell();
    try {
      const [status, manifest, memory, multimodal, evalStatus] = await Promise.all([
        fetchJson("/api/agent-runtime/status"),
        fetchJson("/api/agent-runtime/tool-manifest"),
        fetchJson("/api/agent-runtime/memory/stats"),
        fetchJson("/api/agent-runtime/multimodal-index/status"),
        fetchJson("/api/agent-runtime/eval/status")
      ]);
      appState.agentRuntime = {
        ...appState.agentRuntime,
        status: status.ok && status.data?.ok ? "ready" : "error",
        statusPayload: status.data || null,
        manifest: manifest.data || null,
        memory: memory.data || null,
        multimodal: multimodal.data || null,
        evalStatus: evalStatus.data || null,
        error: status.data?.error || (!status.ok ? `agent_runtime_status_failed:${status.status}` : "")
      };
    } catch (error) {
      appState.agentRuntime = { ...appState.agentRuntime, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "agentRuntime") renderShell();
  }

  async function loadDashboardData() {
    if (!appState.authToken) {
      appState.dashboard = { ...appState.dashboard, status: "idle", error: "" };
      if (appState.page === "dashboard") renderShell();
      return;
    }
    appState.dashboard = { ...appState.dashboard, status: "loading", error: "" };
    if (appState.page === "dashboard") renderShell();
    try {
      const [token, audit, runtime, storage] = await Promise.all([
        fetchJson("/api/token-budget/summary"),
        fetchJson("/api/audit/summary"),
        fetchJson("/api/agent-runtime/status"),
        fetchJson("/api/storage/status")
      ]);
      appState.dashboard = {
        status: "ready",
        token: token.ok && token.data?.ok ? token.data : null,
        audit: audit.ok && audit.data?.ok ? audit.data : { operations: [] },
        runtime: runtime.ok && runtime.data?.ok ? runtime.data : null,
        storage: storage.ok && storage.data?.ok ? storage.data : null,
        error: ""
      };
      if (token.ok && token.data?.ok) {
        appState.tokenBudget = { ...appState.tokenBudget, summary: token.data };
      }
    } catch (error) {
      appState.dashboard = { ...appState.dashboard, status: "error", error: error.message || String(error) };
    }
    if (appState.page === "dashboard") renderShell();
  }

  async function loadShellStorageCapacity() {
    if (!appState.authToken) return null;
    try {
      const storage = await fetchJson("/api/storage/status");
      if (!storage.ok || !storage.data?.ok || !storage.data?.capacity?.total_bytes) return null;
      appState.dashboard = { ...appState.dashboard, storage: storage.data };
      appState.settings = { ...appState.settings, storage: storage.data };
      return storage.data;
    } catch (error) {
      return null;
    }
  }

  async function runAgentRuntimeContextPack() {
    if (!appState.authToken) {
      appState.agentRuntime = { ...appState.agentRuntime, status: "auth", error: "" };
      renderShell();
      return;
    }
    appState.agentRuntime = { ...appState.agentRuntime, status: "loading", error: "" };
    renderShell();
    try {
      const result = await fetchJson("/api/agent-runtime/context-pack", {
        method: "POST",
        body: {
          query: "本地运行层上下文包检查",
          workspace: "openclaw",
          candidates: [
            {
              source: "local_runtime_policy.md",
              title: "本地运行层策略",
              text: "Qwen 负责理解和建议，涉及 NAS 的动作必须通过本地权限和受控执行链路。",
              evidence_ref: "local_runtime_policy",
              acl_allowed: true,
              media_type: "text"
            },
            {
              source: "private_denied_context.md",
              title: "权限外上下文",
              text: "权限外内容应被上下文包排除。",
              evidence_ref: "acl_denied_context",
              acl_allowed: false,
              media_type: "text"
            }
          ]
        }
      });
      if (result.ok && result.data?.ok) {
        appState.agentRuntime = { ...appState.agentRuntime, status: "ready", contextPack: result.data, error: "" };
        showToast("上下文包已生成");
      } else {
        appState.agentRuntime = { ...appState.agentRuntime, status: result.status === 401 ? "auth" : "error", error: result.data?.error || `context_pack_failed:${result.status}` };
      }
    } catch (error) {
      appState.agentRuntime = { ...appState.agentRuntime, status: "error", error: error.message || String(error) };
    }
    renderShell();
  }

  async function loadProtectedSummary(key, path) {
    if (!appState.authToken) {
      appState[key] = { ...appState[key], status: "auth", error: "" };
      if (appState.page === key) renderShell();
      return;
    }
    appState[key] = { ...appState[key], status: "loading", error: "" };
    if (appState.page === key) renderShell();
    try {
      const result = await fetchJson(path);
      if (result.ok && result.data?.ok) {
        appState[key] = { ...appState[key], status: "ready", summary: result.data, error: "" };
      } else {
        appState[key] = { ...appState[key], status: result.status === 401 ? "auth" : "error", summary: null, error: result.data?.error || `${key}_failed:${result.status}` };
      }
    } catch (error) {
      appState[key] = { ...appState[key], status: "error", summary: null, error: error.message || String(error) };
    }
    if (appState.page === key) renderShell();
  }

  function pageAfterRenderLoad(page) {
    const loaders = {
      dashboard: loadDashboardData,
      files: () => loadStoragePath(appState.storage.relativePath || ""),
      documents: async function() { await loadDocClassificationData(); await loadDocumentsData(); },
      reports: loadReportsData,
      tokenBudget: loadTokenBudgetData,
      agentRuntime: loadAgentRuntimeData,
      journal: loadJournalData,
      audit: loadAuditData,
      media: loadMediaData,
      backup: loadBackupData,
      settings: loadSettingsData
    };
    if (loaders[page]) loaders[page]();
  }

  async function loadStoragePath(path = appState.storage.relativePath) {
    const relativePath = cleanStoragePath(path);
    if (!appState.authToken) {
      appState.storage = { ...appState.storage, status: "auth", relativePath, error: "" };
      if (appState.page === "files") renderShell();
      return;
    }
    appState.storage = { ...appState.storage, status: "loading", relativePath, error: "" };
    if (appState.page === "files") renderShell();
    try {
      const result = await fetchJson(`/api/storage/list?path=${encodeURIComponent(relativePath)}`);
      if (result.ok && result.data && result.data.ok) {
        const entries = Array.isArray(result.data.entries) ? result.data.entries : [];
        appState.storage = {
          ...appState.storage,
          status: "ready",
          relativePath: result.data.relative_path || "",
          parent: result.data.parent || "",
          root: result.data.root || "",
          entries,
          rootFolders: relativePath ? appState.storage.rootFolders : entries.filter((entry) => entry.is_dir),
          error: "",
          message: ""
        };
        if (!entries.some((entry) => entry.relative_path === appState.selectedFile)) {
          appState.selectedFile = entries[0]?.relative_path || "";
        }
      } else if (result.status === 401 || result.data?.error === "auth_required") {
        appState.storage = { ...appState.storage, status: "auth", error: "" };
      } else if (result.status === 503 || result.data?.error === "personal_root_not_configured") {
        appState.storage = { ...appState.storage, status: "unconfigured", error: "personal_root_not_configured" };
      } else {
        appState.storage = { ...appState.storage, status: "error", error: result.data?.error || `storage_list_failed:${result.status}` };
      }
    } catch (error) {
      appState.storage = { ...appState.storage, status: "error", error: `storage_list_failed:${error.message || error}` };
    }
    if (appState.page === "files") renderShell();
  }

  async function submitStorageLogin({ bootstrap = false } = {}) {
    const username = document.getElementById("storageUsername")?.value.trim() || "";
    const password = document.getElementById("storagePassword")?.value || "";
    if (!username || !password) {
      appState.storage = { ...appState.storage, status: "auth", error: "请输入用户名和密码。" };
      renderShell();
      return;
    }
    appState.storage = { ...appState.storage, status: "auth", error: "" };
    renderShell();
    try {
      if (bootstrap) {
        window.location.href = "/setup";
        return;
      }
      if (false) {
        const created = await fetchJson("/api/identity/create-user", {
          method: "POST",
          body: { username, password, role: "admin" }
        });
        if (!created.ok && created.data?.error !== "username_already_exists") {
          appState.storage = { ...appState.storage, status: "auth", error: created.data?.error || "初始化失败。" };
          renderShell();
          return;
        }
      }
      const result = await fetchJson("/api/identity/login", {
        method: "POST",
        body: { username, password }
      });
      if (!result.ok || !result.data?.ok) {
        appState.storage = { ...appState.storage, status: "auth", error: result.data?.error || "登录失败。" };
        renderShell();
        return;
      }
      appState.authUser = result.data.user || null;
      const receivedToken = result.data.token || "";
      appState.authToken = receivedToken || (appState.authUser ? "__http_only_cookie__" : "");
      appState.csrfToken = result.data.csrf_token || "";
      if (receivedToken) safeLocalStorageSet("diguaAiNasToken", receivedToken);
      else safeLocalStorageRemove("diguaAiNasToken");
      safeLocalStorageSet("diguaAiNasUser", JSON.stringify(appState.authUser));
      await loadShellStorageCapacity();
      showToast("已连接 NAS 文件接口");
      await loadStoragePath(appState.storage.relativePath || "");
    } catch (error) {
      appState.storage = { ...appState.storage, status: "auth", error: `登录失败：${error.message || error}` };
      renderShell();
    }
  }

  async function logoutStorage() {
    try {
      await fetchJson("/api/v1/auth/logout", { method: "POST", body: {} });
    } catch (error) {
      // Direct loopback legacy mode may not expose the product-access endpoint.
    }
    clearProductSession();
    renderShell();
    showToast("已退出登录");
  }

  function selectedStorageEntry() {
    return (appState.storage.entries || []).find((entry) => entry.relative_path === appState.selectedFile) || null;
  }

  async function copyText(text, message = "路径已复制") {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      showToast(message);
    } catch (error) {
      showToast(`路径：${text}`);
    }
  }

  async function downloadStorageFile(downloadUrl) {
    if (!downloadUrl) return;
    try {
      const response = await fetch(downloadUrl, {
        headers: appState.authToken ? { Authorization: `Bearer ${appState.authToken}` } : {}
      });
      if (!response.ok) {
        showToast(`下载失败：${response.status}`);
        return;
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const path = new URL(downloadUrl, window.location.origin).searchParams.get("path") || "download";
      anchor.href = objectUrl;
      anchor.download = path.split("/").pop() || "download";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
      showToast("下载已开始");
    } catch (error) {
      showToast(`下载失败：${error.message || error}`);
    }
  }

  async function openDocumentCard(card) {
    const openUrl = card?.dataset?.documentOpenUrl || "";
    if (!openUrl) return;
    const title = card.dataset.documentTitle || "文档";
    const filename = card.dataset.documentFilename || "document";
    try {
      const response = await fetch(openUrl, {
        headers: appState.authToken ? { Authorization: `Bearer ${appState.authToken}` } : {}
      });
      if (!response.ok) throw new Error(`document_${response.status}`);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.target = "_blank";
      anchor.rel = "noopener";
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
      showToast("文档已打开");
    } catch (error) {
      showToast(`文档打开失败：${error.message || error}`);
    }
  }

  function storageTrashPayloadFromButton(button) {
    const dataset = button?.dataset || {};
    return {
      kind: dataset.trashKind || "file",
      title: dataset.trashTitle || "file",
      relativePath: dataset.trashRelativePath || "",
      pathHash: dataset.trashPathHash || "",
      previewUrl: dataset.trashPreviewUrl || ""
    };
  }

  function renderStorageTrashConfirm(payload) {
    const status = appState.trash.status || "idle";
    const busy = status === "loading";
    const error = appState.trash.error || "";
    const typeLabel = payload.kind === "image" ? "图片" : payload.kind === "document" ? "文档" : "文件";
    return `
      <div class="trash-confirm">
        <div class="soft-note">
          <strong>${svg("trash")} 移入回收站</strong>
          <p>将这个${escapeHtml(typeLabel)}移入本地 NAS 回收站。它不会立即永久删除，30 天后由服务自动清理。</p>
        </div>
        <div class="trash-confirm-target">
          <span>${escapeHtml(typeLabel)}</span>
          <strong>${escapeHtml(payload.title || "未命名文件")}</strong>
        </div>
        ${error ? `<div class="soft-note error-note"><strong>操作失败</strong><p>${escapeHtml(error)}</p></div>` : ""}
        <div class="actions">
          <button class="btn secondary" type="button" data-action="storageTrashCancel" ${busy ? "disabled" : ""}>取消</button>
          <button class="btn trash-confirm-button" type="button" data-action="storageTrashConfirm" ${busy ? "disabled" : ""}>${busy ? "正在移入回收站" : "移入回收站"}</button>
        </div>
      </div>
    `;
  }

  function openStorageTrashPrompt(button) {
    const payload = storageTrashPayloadFromButton(button);
    if (!payload.relativePath && !payload.pathHash) {
      showToast("缺少可删除文件标识");
      return;
    }
    appState.trash = { status: "idle", pending: payload, error: "" };
    showWorkflow("移入回收站", renderStorageTrashConfirm(payload), "neutral");
  }

  function clearPreviewCache(previewUrl) {
    if (!previewUrl) return;
    const objectUrl = previewObjectUrlCache.get(previewUrl);
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    previewObjectUrlCache.delete(previewUrl);
    previewObjectPromiseCache.delete(previewUrl);
  }

  function removeTrashedAssistantReferences(payload) {
    const assistant = appState.assistant || {};
    const copilot = assistant.copilot || null;
    if (!copilot || typeof copilot !== "object") return;
    const relativePath = payload.relativePath || "";
    const pathHash = payload.pathHash || "";
    const shouldKeep = (item) => {
      if (!item || typeof item !== "object") return true;
      if (relativePath && String(item.relative_path || item.path || "") === relativePath) return false;
      if (pathHash && String(item.path_hash || "") === pathHash) return false;
      return true;
    };
    const nextCopilot = { ...copilot };
    if (Array.isArray(copilot.evidence)) {
      nextCopilot.evidence = copilot.evidence.filter(shouldKeep);
      nextCopilot.evidence_count = nextCopilot.evidence.length;
    }
    if (copilot.search && Array.isArray(copilot.search.results)) {
      const nextResults = copilot.search.results.filter(shouldKeep);
      nextCopilot.search = { ...copilot.search, results: nextResults, result_count: nextResults.length };
    }
    appState.assistant = { ...assistant, copilot: nextCopilot };
  }

  async function confirmStorageTrash() {
    const pending = appState.trash.pending || null;
    if (!pending || (!pending.relativePath && !pending.pathHash)) {
      closeWorkflow();
      showToast("没有可移入回收站的目标");
      return;
    }
    appState.trash = { ...appState.trash, status: "loading", error: "" };
    showWorkflow("移入回收站", renderStorageTrashConfirm(pending), "neutral");
    try {
      const body = { source: "web-ui" };
      if (pending.relativePath) body.relative_path = pending.relativePath;
      if (pending.pathHash) body.path_hash = pending.pathHash;
      const result = await fetchJson("/api/storage/trash", { method: "POST", body });
      if (!result.ok || result.data?.ok === false) {
        throw new Error(result.data?.error || `trash_failed:${result.status}`);
      }
      clearPreviewCache(pending.previewUrl);
      removeTrashedAssistantReferences(pending);
      if (pending.previewUrl && appState.imageViewer.previewUrl === pending.previewUrl) {
        appState.imageViewer = { open: false, title: "", meta: "", match: "", previewUrl: "", objectUrl: "", status: "idle", error: "", requestId: "", zoom: 1, rotation: 0, offsetX: 0, offsetY: 0 };
      }
      appState.trash = { status: "ready", pending: null, error: "" };
      closeWorkflow();
      showToast("已移入回收站，30 天后自动清理");
      if (appState.page === "media") {
        await loadMediaData();
      } else if (appState.page === "aiAlbum") {
        await loadAiAlbumData();
      } else {
        renderShell();
      }
    } catch (error) {
      const message = error.message || String(error);
      appState.trash = { ...appState.trash, status: "error", error: message };
      showWorkflow("移入回收站", renderStorageTrashConfirm(pending), "danger");
    }
  }

  function showStorageOperation(type) {
    appState.storageOperation = { type, status: "idle", result: null, error: "" };
    renderShell();
  }

  function cancelStorageOperation() {
    appState.storageOperation = { type: "", status: "idle", result: null, error: "" };
    renderShell();
  }

  async function createStorageFolder() {
    const path = cleanStoragePath(document.getElementById("storageNewFolderPath")?.value || "");
    if (!path) {
      appState.storageOperation = { ...appState.storageOperation, status: "error", error: "请输入目标位置。" };
      renderShell();
      return;
    }
    appState.storageOperation = { ...appState.storageOperation, status: "loading", error: "" };
    renderShell();
    try {
      const result = await fetchJson("/api/storage/create-folder", { method: "POST", body: { path } });
      if (!result.ok || !result.data?.ok) {
        appState.storageOperation = { ...appState.storageOperation, status: "error", error: result.data?.error || `create_folder_failed:${result.status}` };
        renderShell();
        return;
      }
      appState.storageOperation = { type: "new-folder", status: "ready", result: { action: "create-folder", ...result.data.folder }, error: "" };
      appState.fileSearch = "";
      await loadStoragePath(appState.storage.relativePath || parentPath(path));
      showToast("文件夹已创建");
    } catch (error) {
      appState.storageOperation = { ...appState.storageOperation, status: "error", error: error.message || String(error) };
      renderShell();
    }
  }

  async function uploadStorageFile() {
    const input = document.getElementById("storageUploadInput");
    const file = input?.files?.[0];
    if (!file) {
      appState.storageOperation = { ...appState.storageOperation, status: "error", error: "请选择要上传的文件。" };
      renderShell();
      return;
    }
    appState.storageOperation = { ...appState.storageOperation, status: "loading", error: "" };
    renderShell();
    try {
      const targetDir = document.getElementById("storageUploadDir")?.value || appState.storage.relativePath || "";
      const result = await uploadFileStream(file, targetDir);
      if (!result.ok || !result.data?.ok) {
        appState.storageOperation = { ...appState.storageOperation, status: "error", error: result.data?.error || `upload_failed:${result.status}` };
        renderShell();
        return;
      }
      appState.storageOperation = { type: "upload", status: "ready", result: { action: "upload-file", ...result.data.file }, error: "" };
      await loadStoragePath(appState.storage.relativePath || "");
      showToast("文件已上传并写入审计日志");
    } catch (error) {
      appState.storageOperation = { ...appState.storageOperation, status: "error", error: error.message || String(error) };
      renderShell();
    }
  }

  async function shareSelectedStorageItem() {
    const selected = selectedStorageEntry();
    if (!selected) {
      showToast("请先选择文件或文件夹");
      return;
    }
    await copyText(selected.relative_path, "已复制文件位置");
    showWorkflow("本地只读分享", `
      <p>分享入口生成的是本地受控分享材料，不创建公网链接。访问者仍需要登录，并通过读权限校验。</p>
      ${renderKeyValueRows([
        ["位置", displayLocation(selected.relative_path)],
        ["类型", selected.is_dir ? "文件夹" : "文件"],
        ["访问范围", "本地认证预览"],
        ["预览方式", selected.is_dir ? "文件夹不提供直接预览" : "登录后本地预览"]
      ])}
    `);
  }

  async function snapshotSelectedStorageItem() {
    const selected = selectedStorageEntry();
    if (!selected) {
      showToast("请先选择要创建快照的项目");
      return;
    }
    const sourcePath = selected.is_dir ? selected.relative_path : parentPath(selected.relative_path);
    const safeName = `webui_${Date.now()}_${String(selected.name || "snapshot").replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 40)}`;
    showWorkflow("创建快照", `<div class="skeleton-list"><span></span><span></span></div>`);
    try {
      const result = await fetchJson("/api/snapshot/create", { method: "POST", body: { name: safeName, path: sourcePath } });
      if (!result.ok || !result.data?.ok) {
        showWorkflow("创建快照", `<div class="soft-note error-note"><strong>快照失败</strong><p>${escapeHtml(result.data?.error || result.status)}</p></div>`, "danger");
        return;
      }
      showWorkflow("创建快照", `
        ${renderKeyValueRows([
          ["名称", result.data.snapshot?.name || safeName],
          ["来源", sourcePath ? displayLocation(sourcePath) : "个人空间"],
          ["文件数", result.data.snapshot?.file_count ?? "暂无"],
          ["大小", result.data.snapshot?.total_size ? formatBytes(result.data.snapshot.total_size) : "暂无"]
        ])}
      `);
      showToast("快照已创建");
    } catch (error) {
      showWorkflow("创建快照", `<div class="soft-note error-note"><strong>快照失败</strong><p>${escapeHtml(error.message || String(error))}</p></div>`, "danger");
    }
  }

  async function runCopyRoute(step) {
    const selected = selectedStorageEntry();
    if (!selected || selected.is_dir) {
      showToast("请选择一个文件再验证复制链路");
      return;
    }
    const target = cleanStoragePath(document.getElementById("copyTarget")?.value || appState.copy.target || `copy_${selected.name}`);
    appState.copy = { ...appState.copy, target, status: "loading", result: null };
    renderShell();
    const payload = {
      source_relative_path: selected.relative_path,
      target_relative_path: target,
      operator_user_id: appState.authUser?.username || "web-ui",
      approval_phrase: appState.copy.approvalPhrase,
      signed_approval_token: appState.copy.signedToken,
      rollback_manifest_path: appState.copy.rollbackManifestPath,
      rollback_phrase: appState.copy.manifestId ? `ROLLBACK ${appState.copy.manifestId}` : ""
    };
    const endpoints = {
      preview: "/api/nas/copy/preview",
      dry: "/api/nas/copy/dry-run",
      confirm: "/api/nas/copy/confirm",
      execute: "/api/nas/copy/execute",
      rollback: "/api/nas/copy/rollback"
    };
    try {
      const result = await fetchJson(endpoints[step], { method: "POST", body: payload });
      const data = result.data || {};
      appState.copy = {
        ...appState.copy,
        status: result.ok && data.ok ? "ready" : "error",
        result: data,
        approvalPhrase: data.approval_phrase || appState.copy.approvalPhrase,
        signedToken: data.signed_approval_token || appState.copy.signedToken,
        rollbackManifestPath: data.rollback_manifest_path || appState.copy.rollbackManifestPath,
        manifestId: data.manifest_id || appState.copy.manifestId
      };
      showToast(data.ok ? `copy ${step} 完成` : `copy ${step} 被拒绝`);
    } catch (error) {
      appState.copy = { ...appState.copy, status: "error", result: { ok: false, error: error.message || String(error), route: step } };
    }
    renderShell();
  }

  async function loadLiveHints() {
    try {
      const result = await fetchJson("/api/v1/system/health");
      appState.health = {
        status: result.ok && result.data && result.data.ok ? "ok" : "error",
        text: result.ok && result.data && result.data.ok ? "本地访问层在线" : "本地访问层需复查"
      };
    } catch (error) {
      appState.health = { status: "error", text: "本地 API 未连接，页面保持只读" };
    }
    if (appState.page === "dashboard") renderShell();
    if (!appState.authToken) return;

    try {
      const result = await fetchJson("/api/harness/status");
      appState.health = {
        status: result.ok && result.data && result.data.ok ? "ok" : "error",
        text: result.ok && result.data && result.data.ok ? "受控执行边界在线" : "执行边界需复查"
      };
    } catch (error) {
      appState.health = { status: "error", text: "受控执行边界未连接" };
    }
    if (appState.page === "dashboard") renderShell();

    try {
      const result = await fetchJson("/api/journal/health");
      appState.journal = {
        status: result.ok && result.data && result.data.ok ? "ok" : "error",
        text: result.ok && result.data && result.data.ok ? `日记索引 ${result.data.stats?.journal_events || 0} 条` : "日记索引需复查"
      };
    } catch (error) {
      appState.journal = { status: "error", text: "日记 API 未连接" };
    }
  }

  app.addEventListener("click", (event) => {
    const pageButton = event.target.closest("[data-page]");
    if (pageButton) {
      appState.workflow = { open: false, title: "", body: "", tone: "neutral" };
      setPage(pageButton.dataset.page);
      return;
    }
    const openPathButton = event.target.closest("[data-open-path]");
    if (openPathButton) {
      loadStoragePath(openPathButton.dataset.openPath || "");
      return;
    }
    const copyPathButton = event.target.closest("[data-copy-path]");
    if (copyPathButton) {
      copyText(copyPathButton.dataset.copyPath || "", "文件位置已复制");
      return;
    }
    const fileButton = event.target.closest("[data-file-path]");
    if (fileButton) {
      appState.selectedFile = fileButton.dataset.filePath || "";
      renderShell();
      return;
    }
    const recordButton = event.target.closest("[data-record-id]");
    if (recordButton) {
      appState.selectedAuditRecord = recordButton.dataset.recordId;
      renderShell();
      showToast("已选中本地审计记录");
      return;
    }
    const docButton = event.target.closest("[data-doc-id]");
    if (docButton) {
      appState.selectedDoc = docButton.dataset.docId;
      renderShell();
      return;
    }
    const reportButton = event.target.closest("[data-report-id]");
    if (reportButton) {
      appState.reports.selectedId = reportButton.dataset.reportId || "";
      renderShell();
      return;
    }
    const promptButton = event.target.closest("[data-prompt]");
    if (promptButton) {
      appState.prompt = promptButton.dataset.prompt || "";
      renderShell();
      document.getElementById("assistantPrompt")?.focus();
      return;
    }
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton) return;
    const action = actionButton.dataset.action;
    if (action === "closeWorkflow") {
      closeWorkflow();
    } else if (action === "closeImageViewer") {
      closeImageViewer();
    } else if (action === "imageZoomIn") {
      zoomImageViewer(1.2);
    } else if (action === "imageZoomOut") {
      zoomImageViewer(1 / 1.2);
    } else if (action === "imageFit") {
      resetImageViewerTransform();
    } else if (action === "imageRotate") {
      rotateImageViewer();
    } else if (action === "openNotifications") {
      openNotifications();
    } else if (action === "openHelp") {
      openHelp();
    } else if (action === "openUserMenu") {
      openUserMenu();
    } else if (action === "openMobileMore") {
      openMobileMore();
    } else if (action === "dashboardTasks") {
      openDashboardTasks();
    } else if (action === "tokenDetails") {
      setPage("tokenBudget");
    } else if (action === "assistantGuide") {
      assistantGuide();
    } else if (action === "assistantAttach") {
      assistantAttach();
    } else if (action === "assistantContinue") {
      assistantContinue();
    } else if (action === "assistantKeyPoints") {
      assistantKeyPoints();
    } else if (action === "assistantMindmap") {
      assistantMindmap();
    } else if (action === "assistantExport") {
      assistantExport();
    } else if (action === "assistantEvidenceSources") {
      assistantEvidenceSources();
    } else if (action === "assistantRecentFiles") {
      assistantRecentFiles();
    } else if (action === "assistantTrace") {
      assistantTrace();
    } else if (action === "assistantAgents") {
      assistantAgents();
    } else if (action === "sendPrompt") {
      sendAssistantPrompt();
    } else if (action === "storageLogin") {
      submitStorageLogin();
    } else if (action === "storageBootstrap") {
      submitStorageLogin({ bootstrap: true });
    } else if (action === "storageLogout") {
      logoutStorage();
    } else if (action === "storageRefresh") {
      loadStoragePath(appState.storage.relativePath || "");
    } else if (action === "storageUp") {
      loadStoragePath(appState.storage.parent || "");
    } else if (action === "storageShowNewFolder") {
      showStorageOperation("new-folder");
    } else if (action === "storageShowUpload") {
      showStorageOperation("upload");
    } else if (action === "storageCancelOperation") {
      cancelStorageOperation();
    } else if (action === "storageCreateFolder") {
      createStorageFolder();
    } else if (action === "storageUploadFile") {
      uploadStorageFile();
    } else if (action === "storageTrashPrompt") {
      openStorageTrashPrompt(actionButton);
    } else if (action === "storageTrashConfirm") {
      confirmStorageTrash();
    } else if (action === "storageTrashCancel") {
      closeWorkflow();
    } else if (action === "openSelectedFolder") {
      const selected = selectedStorageEntry();
      if (selected?.is_dir) loadStoragePath(selected.relative_path || "");
    } else if (action === "storageCopySelected") {
      const selected = selectedStorageEntry();
      copyText(selected?.relative_path || appState.storage.relativePath || "", "文件位置已复制");
    } else if (action === "storageDownload") {
      downloadStorageFile(actionButton.dataset.downloadPath || "");
    } else if (action === "storageShareSelected") {
      shareSelectedStorageItem();
    } else if (action === "storageSnapshotSelected") {
      snapshotSelectedStorageItem();
    } else if (action === "copyPreview") {
      runCopyRoute("preview");
    } else if (action === "copyDryRun") {
      runCopyRoute("dry");
    } else if (action === "copyConfirm") {
      runCopyRoute("confirm");
    } else if (action === "copyExecute") {
      runCopyRoute("execute");
    } else if (action === "copyRollback") {
      runCopyRoute("rollback");
    } else if (action === "documentsRefresh") {
      const path = document.getElementById("documentPath")?.value.trim();
      if (path) appState.documents.path = cleanStoragePath(path);
      loadDocumentsData();
    } else if (action === "documentsAsk") {
      askDocuments();
    } else if (action === "reportsRefresh") {
      loadReportsData();
    } else if (action === "reportExport") {
      exportSelectedReport();
    } else if (action === "reportCopyPath") {
      const selected = (appState.reports.items || []).find((report) => report.id === appState.reports.selectedId) || appState.reports.items[0];
      copyText(selected?.path || selected?.relative_path || "", "报告位置已复制");
    } else if (action === "tokenBudgetRefresh") {
      loadTokenBudgetData();
    } else if (action === "tokenBudgetEstimate") {
      estimateTokenBudgetSample();
    } else if (action === "agentRuntimeRefresh") {
      loadAgentRuntimeData();
    } else if (action === "agentRuntimeContextPack") {
      runAgentRuntimeContextPack();
    } else if (action === "journalRefresh") {
      loadJournalData();
    } else if (action === "journalManual") {
      createManualJournalEntry();
    } else if (action === "journalGenerate") {
      generateJournalSummary(actionButton.dataset.period || "daily");
    } else if (action === "journalExport") {
      exportJournalMarkdown();
    } else if (action === "auditRefresh") {
      loadAuditData();
    } else if (action === "auditReset") {
      appState.audit = { ...appState.audit, query: "" };
      renderShell();
      loadAuditData();
    } else if (action === "auditApplyFilter") {
      appState.audit = { ...appState.audit, query: document.getElementById("auditSearch")?.value || appState.audit.query || "" };
      renderShell();
      showToast("审计筛选已应用");
    } else if (action === "auditPageSize") {
      showWorkflow("审计分页", renderKeyValueRows([["当前页大小", "10 条/页"], ["数据来源", appState.audit.operations.length ? "真实操作日志" : "暂无审计记录"], ["说明", "当前实机页以本地最近 50 条操作为上限。"]]));
    } else if (action === "fileViewExplorer") { appState.fileViewMode = "explorer"; renderShell(); }
    else if (action === "fileViewAi") { appState.fileViewMode = "ai"; renderShell(); if (appState.authToken) { loadDocClassificationData(); } }
    else if (action === "fileViewTimeline") { appState.fileViewMode = "timeline"; renderShell(); }
    else if (action === "docClassifyAll") { runDocClassification(); }
    else if (action === "docUpload") { uploadDocumentFile(); }
    else if (action === "docCategorySelect") { appState.docClassification = { ...appState.docClassification, selectedCategory: actionButton.dataset.category || "" }; renderShell(); }
    else if (action === "mediaRefresh") {
      loadMediaData();
    } else if (action === "mediaOrganizeNow") {
      runMediaOrganizeNow();
    } else if (action === "mediaIndex") {
      loadMediaData();
      showToast("已刷新现有媒体索引");
    } else if (action === "mediaUploadChoose") {
      chooseMediaUploadFile();
    } else if (action === "mediaSelectAlbum") {
      selectMediaAlbum(actionButton.dataset.albumName || "");
    } else if (action === "mediaClearAlbum") {
      clearMediaAlbumSelection();
    } else if (action === "mediaCreateAlbum") {
      fetchJson("/api/media/create-album", { method: "POST", body: { name: `本地相册-${Date.now()}`, description: "网页端创建的本地相册记录" } }).then(() => loadMediaData());
      showToast("相册创建请求已提交");
    } else if (action === "aiAlbumRefresh") {
      loadAiAlbumData();
    } else if (action === "aiAlbumSearch") {
      runAiAlbumSearch();
    } else if (action === "aiAlbumPreset") {
      appState.aiAlbum = { ...appState.aiAlbum, query: actionButton.dataset.query || "" };
      runAiAlbumSearch(appState.aiAlbum.query);
    } else if (action === "aiAlbumTab") {
      appState.aiAlbum = { ...appState.aiAlbum, activeTab: actionButton.dataset.tab || "all" };
      renderShell();
    } else if (action === "aiAlbumCategory") {
      appState.aiAlbum = { ...appState.aiAlbum, selectedCategory: actionButton.dataset.category || "" };
      renderShell();
    } else if (action === "aiAlbumSelectAsset") {
      scheduleAiAlbumSelectAsset(actionButton.dataset.aiAlbumAssetId || "");
    } else if (action === "aiAlbumPlan") {
      createAiAlbumOrganizePlan();
    } else if (action === "aiAlbumShowPlan") {
      showAiAlbumPlanWorkflow();
    } else if (action === "aiAlbumPlanDryRun") {
      runAiAlbumPlanStep("dryRun");
    } else if (action === "aiAlbumPlanApprove") {
      runAiAlbumPlanStep("approve");
    } else if (action === "aiAlbumPlanExecute") {
      runAiAlbumPlanStep("execute");
    } else if (action === "aiAlbumPlanRollback") {
      runAiAlbumPlanStep("rollback");
    } else if (action === "backupRefresh") {
      loadBackupData();
    } else if (action === "backupCreate") {
      createBackupTaskFromForm();
    } else if (action === "backupRun") {
      runBackupTaskFromForm();
    } else if (action === "settingsRefresh") {
      loadSettingsData();
    } else {
      showWorkflow("未识别入口", `<div class="soft-note error-note"><strong>${escapeHtml(action || "unknown")}</strong><p>该入口没有匹配到前端 handler，请复查 data-action。</p></div>`, "danger");
    }
  });

  app.addEventListener("dblclick", (event) => {
    if (event.target.closest("[data-action='storageTrashPrompt'], .trash-button")) return;
    const documentCard = event.target.closest("[data-document-open-url]");
    if (documentCard) {
      event.preventDefault();
      openDocumentCard(documentCard);
      return;
    }
    const imageCard = event.target.closest("[data-image-preview-url]");
    if (!imageCard) return;
    window.clearTimeout(aiAlbumSelectTimer);
    event.preventDefault();
    openSearchImageViewer(imageCard);
  });

  app.addEventListener("change", (event) => {
    if (event.target && event.target.id === "mediaUploadInput") {
      const file = event.target.files && event.target.files[0];
      event.target.value = "";
      uploadMediaImageFile(file);
    }
  });

  app.addEventListener("pointerdown", (event) => {
    const body = event.target.closest("[data-image-viewer-body]");
    if (!body || !appState.imageViewer.open || !appState.imageViewer.objectUrl || event.target.closest("button")) return;
    event.preventDefault();
    imageViewerDrag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: Number(appState.imageViewer.offsetX || 0),
      offsetY: Number(appState.imageViewer.offsetY || 0)
    };
    body.classList.add("is-dragging");
    body.setPointerCapture?.(event.pointerId);
  });

  app.addEventListener("pointermove", (event) => {
    if (!imageViewerDrag || imageViewerDrag.pointerId !== event.pointerId || !appState.imageViewer.open) return;
    const offsetX = imageViewerDrag.offsetX + event.clientX - imageViewerDrag.startX;
    const offsetY = imageViewerDrag.offsetY + event.clientY - imageViewerDrag.startY;
    appState.imageViewer = { ...appState.imageViewer, offsetX, offsetY };
    const img = document.querySelector(".image-viewer-img");
    if (img) img.style.transform = imageViewerTransform(appState.imageViewer);
  });

  function finishImageViewerDrag(event) {
    if (!imageViewerDrag || (event?.pointerId != null && imageViewerDrag.pointerId !== event.pointerId)) return;
    document.querySelector("[data-image-viewer-body]")?.classList.remove("is-dragging");
    imageViewerDrag = null;
  }

  app.addEventListener("pointerup", finishImageViewerDrag);
  app.addEventListener("pointercancel", finishImageViewerDrag);

  app.addEventListener("wheel", (event) => {
    const body = event.target.closest("[data-image-viewer-body]");
    if (!body || !appState.imageViewer.open || !appState.imageViewer.objectUrl) return;
    event.preventDefault();
    zoomImageViewer(event.deltaY < 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });

  app.addEventListener("input", (event) => {
    if (event.target && event.target.id === "assistantPrompt") {
      appState.prompt = event.target.value;
      const send = document.querySelector('[data-action="sendPrompt"]');
      if (send) send.disabled = !appState.prompt.trim();
    }
    if (event.target && event.target.id === "storageSearch") {
      appState.fileSearch = event.target.value;
      renderShell();
      document.getElementById("storageSearch")?.focus();
    }
    if (event.target && event.target.id === "documentQuestion") {
      appState.documents.query = event.target.value;
    }
    if (event.target && event.target.id === "documentPath") {
      appState.documents.path = cleanStoragePath(event.target.value);
    }
    if (event.target && event.target.id === "copyTarget") {
      appState.copy.target = cleanStoragePath(event.target.value);
    }
    if (event.target && event.target.id === "auditSearch") {
      appState.audit = { ...appState.audit, query: event.target.value };
    }
    if (event.target && event.target.id === "aiAlbumSearch") {
      appState.aiAlbum = { ...appState.aiAlbum, query: event.target.value };
    }
  });

  app.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && event.target?.closest?.("[data-action='storageTrashPrompt'], .trash-button")) return;
    if ((event.key === "Enter" || event.key === " ") && event.target?.closest?.("[data-document-open-url]")) {
      event.preventDefault();
      openDocumentCard(event.target.closest("[data-document-open-url]"));
      return;
    }
    if ((event.key === "Enter" || event.key === " ") && event.target?.closest?.("[data-image-preview-url]")) {
      event.preventDefault();
      openSearchImageViewer(event.target.closest("[data-image-preview-url]"));
    }
    if (event.key === "Enter" && event.target && event.target.id === "aiAlbumSearch") {
      event.preventDefault();
      runAiAlbumSearch();
    }
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && appState.imageViewer.open) {
      event.preventDefault();
      closeImageViewer();
    } else if ((event.key === "+" || event.key === "=") && appState.imageViewer.open) {
      event.preventDefault();
      zoomImageViewer(1.2);
    } else if ((event.key === "-" || event.key === "_") && appState.imageViewer.open) {
      event.preventDefault();
      zoomImageViewer(1 / 1.2);
    } else if (event.key === "0" && appState.imageViewer.open) {
      event.preventDefault();
      resetImageViewerTransform();
    }
  });

  window.addEventListener("hashchange", () => {
    const page = getInitialPage();
    if (page !== appState.page) {
      appState.page = page;
      renderShell();
      pageAfterRenderLoad(page);
    }
  });

  async function initializeProductSession() {
    try {
      const response = await fetch("/api/v1/auth/session", { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (response.ok) {
        const payload = await response.json();
        if (payload.authenticated) {
          appState.authUser = payload.user || null;
          appState.csrfToken = payload.csrf_token || "";
          appState.authToken = "__http_only_cookie__";
          safeLocalStorageRemove("diguaAiNasToken");
          safeLocalStorageSet("diguaAiNasUser", JSON.stringify(appState.authUser));
        } else {
          clearProductSession();
        }
      }
    } catch (error) {
      // Preserve direct loopback compatibility when the facade is not running.
    }
    if (appState.authToken) await loadShellStorageCapacity();
    renderShell();
    loadLiveHints();
    pageAfterRenderLoad(appState.page);
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  initializeProductSession();
})();
