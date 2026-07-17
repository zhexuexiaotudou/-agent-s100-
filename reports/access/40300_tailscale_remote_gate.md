# 40300 Tailscale Remote Gate

状态：`needs_user_tailnet_approval`，尚未通过外部门禁。S100P 已按 Tailscale 官方 Ubuntu 22.04 ARM64 安装路径部署 1.98.9，`tailscaled` active，安装后的 remote helper 与 clean access-only 模拟均通过。

当前 `BackendState=NeedsLogin`，Serve 与 Funnel 状态均为空，`digua-product-remote-ingress.service` 保持 inactive；因此没有新增远程或公网暴露。代码限定私有 `127.0.0.1:8781` origin、显式身份映射、未映射拒绝，LAN 伪造 `Tailscale-User-Login` 实测不会登录。

剩余硬边界是用户用自己的 tailnet 批准 S100P。批准后还必须依次验证 Serve HTTPS、授权与未授权身份、禁用回滚、重启恢复、Funnel 始终为空，再将本门禁提升为通过。
