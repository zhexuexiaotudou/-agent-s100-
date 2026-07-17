# 手机与 PWA

当前原生 HTML/CSS/JS 和中文业务文案保留。新增 `/setup` 与 `/settings/access` 手机页，现有 v2 页面通过 HttpOnly Cookie 使用统一入口，不再要求把长期 token 放入 localStorage；状态变更携带 CSRF。

manifest 提供 192 与 512 可缩放图标、standalone、主题色和 start URL。Service Worker 只缓存 `/ui` 与静态 shell；`/api/`、`/api/v1/`、下载、登录、搜索、聊天和审计不进入缓存。LAN HTTP 可正常浏览，但浏览器只有在 secure context 满足条件时才会提供安装能力。

2026-07-17 已直接对 S100P LAN 入口执行浏览器验收：360x800、390x844、430x932、768x1024 均无页面级横向溢出，console error 为 0；证据位于 `reports/access/raw/`。这些是对真实板端页面的浏览器 viewport 测试，不等同于物理手机扫码。物理手机与 HTTPS PWA 安装仍待用户终端验证，LAN HTTP 不伪装成 secure context。
