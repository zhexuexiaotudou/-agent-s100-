# 40500 Hardening and Recovery Gate

结论：本轮访问层恢复与加固实机门禁通过。

- 两次重启定位并修复 NAS automount 早于网络就绪的竞态；启用 `NetworkManager-wait-online.service` 后，NFS、80、8765、18080 首次检查自动恢复，无人工补救。
- 实际卸载 NFS 后，端口 80 保持健康，NAS 状态返回 `nas_not_mounted`，存储 API 返回 503 degraded；重新挂载后服务恢复。测试没有关闭 NAS 电源，证据只表述为真实 NFS 断挂演练。
- 删除默认路由后，LAN、登录、NAS、门户、Qwen 均可用；恢复默认路由后互联网恢复。
- 对 eth0 应用错误静态地址并设 30 秒 timer，地址从 `10.254.254.10/24` 自动回到 `169.254.8.10/16`，NFS 与服务随后恢复。
- access-only 回滚、再升级、二维码 CLI、Cloudflare dry-run 均通过；原有 backend unit 哈希未改变。
- LAN 伪造 Tailscale/Cloudflare identity headers 实测保持 unauthenticated。PR #29 移除访问设置页端点的 `innerHTML`，并隐藏 Python runtime Server 版本。

边界：S100P 还有既存的 SSH、NFS/RPC、VNC、iiod 等局域网监听；它们不是本访问层创建的。产品后端 8765 与 18080 仍只监听 `127.0.0.1`。未从公网侧验证路由器端口转发状态，不能把“没有主机级公网暴露”扩大为整个网络已审计。
