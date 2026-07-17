# Tailscale 私有远程访问

Tailscale 模式只使用 Serve，不使用 Funnel。先安装并登录 Tailscale，应用 `config/tailscale-policy.example.hujson` 的最小授权思想，再运行：

```bash
tailscale version
tailscale serve --help
bash release/install/configure_remote_access.sh --provider tailscale --dry-run
sudo bash release/install/configure_remote_access.sh --provider tailscale --apply --confirm 'ENABLE PRIVATE TAILSCALE SERVE'
```

脚本将 Serve 指向 `http://127.0.0.1:8781`。用 `digua-access identity-map tailscale user@example.com localuser` 明确映射；未映射身份拒绝。LAN 入口会剥离伪造的 Tailscale headers。禁用使用确认短语 `DISABLE TAILSCALE SERVE` 或 `tailscale serve reset`，随后禁用 remote ingress，并验证 LAN 仍可用。

必须在 S100P 上以实际 `tailscale serve --help` 为准；代码不假设旧版 CLI。auth key 只允许 root-only 临时 provisioning，不写数据库或 unit。

## 当前实机状态

2026-07-17 已验证 `https://digua.tail7c6cbb.ts.net/` 为 `tailnet only`，已批准的 owner 身份显式映射到本地 `admin`；外部登录名在公开证据中脱敏。未映射身份返回 401，LAN 伪造身份头不登录；Serve 与 remote ingress 在重启及禁用/重新启用后恢复。`tailscale funnel status` 必须持续显示 `tailnet only`，不得运行 `tailscale funnel`。

Tailscale 的首次 HTTPS/Serve 授权页同时给当前 Tailnet 添加了 `funnel` capability，但板端没有 Funnel 配置，非 Tailnet Windows 客户端也不能解析该 MagicDNS 名称。管理员完成控制台 welcome 后，应在 Access controls 的 `nodeAttrs` 中删除未使用的 `funnel` 属性，再复查 `tailscale status --json` 不含该 capability；删除前不能把“Funnel 能力已彻底禁用”写成事实。
