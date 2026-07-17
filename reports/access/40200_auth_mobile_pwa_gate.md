# 40200 Auth, Mobile and PWA Gate

结论：S100P 鉴权与响应式门禁通过。无密钥实机矩阵创建临时 admin/operator/viewer，验证 HttpOnly、SameSite=Lax、CSRF 缺失拒绝、角色写入边界、上游身份桥、会话撤销、logout 失效、公开创建用户拒绝与已认领设备不可再次 claim；临时用户随后从本地和 NAS 身份库删除，输出不含密码或 token。

Playwright 直接访问真实 S100P，在 360x800、390x844、430x932、768x1024 四个 viewport 均无页面级横向溢出，console error 为 0；390px setup 页由 401px 修正为 390px。匿名首页现在只公开设备已就绪，不泄露 NAS 容量，登录后才读取个人数据。

Service Worker 明确排除 API、下载、登录、搜索、聊天和审计。LAN HTTP 可浏览但不是 secure context，因此实际 PWA 安装按钮须留到 Tailscale/Cloudflare HTTPS 或物理手机验收；这两项不伪造通过。
