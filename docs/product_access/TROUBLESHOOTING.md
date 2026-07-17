# 访问故障排查

按顺序运行：`digua-doctor`、`systemctl status digua-product-access`、以部署用户运行 `systemctl --user status openclaw-gateway qwen25-local-openai-gateway`、`curl http://127.0.0.1:8765/api/health`、`curl http://127.0.0.1:18080/v1/models`、`curl http://127.0.0.1/healthz`、`avahi-browse -art`、`ip -brief address`、`findmnt /mnt/nas/openclaw`。

- `digua.local` 不解析：先用 S100P LAN IP，随后检查 Avahi 与网络是否允许 mDNS。
- 页面开但 NAS 不可用：不要重置数据库；检查 mount、凭据文件权限与 NAS 共享。
- 远程失败而 LAN 正常：保持 LAN，检查 remote ingress、Serve/Tunnel 和身份映射。
- Tailscale 重启后短暂不能解析：先等 `BackendState=Running` 和 `getent hosts <设备>.ts.net` 成功，再判断持久化失败；本次实机观察到控制面晚于 LAN/NAS 入口恢复。
- Tailscale 报 `CONNMARK --restore-mark`：这是当前 S100P iptables legacy 兼容告警；Serve 已可用，但不要未经回滚设计就切换全局 iptables backend，应作为主机网络加固项处理。
- 登录 403 CSRF：刷新页面以重新读取 session/CSRF；不要关闭 CSRF。
- 网络变更后失联：等待自动回滚，或在控制台运行 `digua-access network-rollback <snapshot> --confirm 'ROLLBACK NETWORK CHANGE'`。
- Cloudflare/Tailscale 未安装：状态为需要配置，不影响 LAN。
