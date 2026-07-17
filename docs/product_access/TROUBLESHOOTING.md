# 访问故障排查

按顺序运行：`digua-doctor`、`systemctl status digua-product-access`、以部署用户运行 `systemctl --user status openclaw-gateway qwen25-local-openai-gateway`、`curl http://127.0.0.1:8765/api/health`、`curl http://127.0.0.1:18080/v1/models`、`curl http://127.0.0.1/healthz`、`avahi-browse -art`、`ip -brief address`、`findmnt /mnt/nas/openclaw`。

- `digua.local` 不解析：先用 S100P LAN IP，随后检查 Avahi 与网络是否允许 mDNS。
- 系统级 Qwen 一直 `activating (auto-restart)` 且日志出现 `Address already in use`：先用 `sudo ss -ltnp | grep ':18080 '`、`systemctl status qwen25-local-openai-gateway` 和 `systemctl --user status qwen25-local-openai-gateway` 确认是否存在用户级/系统级双实例。产品机保留系统级单元。将现有用户单元文件改名为带日期的 `.pre-system-scope-*` 备份，再执行 `systemctl --user mask qwen25-local-openai-gateway.service`、`systemctl --user daemon-reload` 和 `sudo systemctl restart qwen25-local-openai-gateway.service`。回滚时先停止系统级单元，删除 `/home/<用户>/.config/systemd/user/qwen25-local-openai-gateway.service` 的 `/dev/null` 链接，将备份文件恢复为原名，执行 `systemctl --user daemon-reload` 后再启动选定的单一作用域；不得让两份单元同时监听 18080。
- 页面开但 NAS 不可用：不要重置数据库；检查 mount、凭据文件权限与 NAS 共享。
- 远程失败而 LAN 正常：保持 LAN，检查 remote ingress、Serve/Tunnel 和身份映射。
- Tailscale 重启后短暂不能解析：先等 `BackendState=Running` 和 `getent hosts <设备>.ts.net` 成功，再判断持久化失败；本次实机观察到控制面晚于 LAN/NAS 入口恢复。
- Tailscale 报 `CONNMARK --restore-mark`：这是当前 S100P iptables legacy 兼容告警；Serve 已可用，但不要未经回滚设计就切换全局 iptables backend，应作为主机网络加固项处理。
- 登录 403 CSRF：刷新页面以重新读取 session/CSRF；不要关闭 CSRF。
- 顶栏仍显示旧用户名但功能返回 `auth_required`：浏览器会话已失效。刷新后前端应清除旧身份并显示“登录”；从顶栏身份菜单或“文件”页重新登录。若刷新后仍显示旧身份，检查 `/api/v1/auth/session` 是否返回 `authenticated: false`，并确认部署的 `digua_ai_nas_v2.js` 已包含失效会话清理逻辑。
- 密码校验返回 200，但下一次文件请求立即返回 401：检查登录日志是否出现连续的 `POST /api/identity/login` 200 与 `GET /api/storage/list` 401。LAN HTTP 与远程 HTTPS 现在使用不同的 HttpOnly Cookie 名称，前端也显式携带同源凭据；旧版同名 Cookie 不再参与会话验证，部署后需要重新登录一次。
- 网络变更后失联：等待自动回滚，或在控制台运行 `digua-access network-rollback <snapshot> --confirm 'ROLLBACK NETWORK CHANGE'`。
- Cloudflare/Tailscale 未安装：状态为需要配置，不影响 LAN。
