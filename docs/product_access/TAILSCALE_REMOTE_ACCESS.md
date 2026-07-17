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
