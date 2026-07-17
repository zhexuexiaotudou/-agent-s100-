# 安全边界

- 对外 Web：LAN 80；远程只经 Tailscale/Cloudflare HTTPS。8765、18080、18888、18889 保持回环或原有边界。
- 产品访问安装器不新增 NAS 管理、SMB、NFS、SSH、Docker socket、systemd D-Bus、SQLite 文件、NAS 根目录或 shell 暴露。当前 S100P 镜像已有 SSH、NFS/RPC、VNC、iiod 等 LAN listener，必须作为独立主机加固项审计，不能算作本访问层已经关闭。
- 不使用 UPnP、路由器裸转发或 Tailscale Funnel。当前板端只配置 tailnet-only Serve；首次授权页留下的未使用 `funnel` policy capability 仍待管理员从 Access controls 删除，删除前不得声称策略层已彻底禁用 Funnel。
- LAN claim 仅在无用户、有效期内、错误次数未耗尽时有效；只存 hash。
- Cookie 为 HttpOnly/SameSite=Lax；LAN HTTP 使用独立的 `digua_lan_session`，远程 HTTPS 使用带 Secure 的 `__Host-digua_session`，避免同一浏览器中的 HTTP/HTTPS 会话名冲突。CSRF 从原始 session 派生，不持久化第二个 secret。
- `admin` 管理用户、网络和远程；`operator` 使用受控业务动作；`viewer` 只能执行允许的读取/搜索类动作。
- remote identity header 只在 loopback remote ingress 信任；LAN 同名 header 被删除。Cloudflare JWT 必须完成应用侧验证。
- access-only 会话桥接只接受已通过本地 Cookie/CSRF 校验且上游已存在的用户名；桥接 token 仅保存在进程内存，并在注销、撤销或服务重启时失效，不进入 Cookie、数据库、审计或验收包。
- 写操作仍由现有 ACL、allowlist、preview/dry-run/确认/签名/source hash 门禁决定；访问层不扩大权限。
