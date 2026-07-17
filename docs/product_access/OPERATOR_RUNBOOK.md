# 运维手册

## 日常

检查 `digua-doctor`、`/healthz`、`/readyz`、NAS mount、Qwen 与门户服务。使用 `digua-access status/endpoints` 查看非秘密配置。任何实际变更写入 `reports/access/command_execution_log.jsonl`，原始脱敏摘要与截图放在 `reports/access/raw/`；不得记录密码、Cookie、Authorization、claim 或 tunnel credential。

产品机使用系统级 OpenClaw/Qwen 服务时，必须确认同名用户级 Qwen 单元未同时占用 18080。升级与重启验收至少记录 `systemctl is-active qwen25-local-openai-gateway`、`systemctl --user is-enabled qwen25-local-openai-gateway`、18080 监听 PID 和 Qwen `/health`；用户级旧单元应保留备份后 masked，而不是直接删除。

## 远程启停

先 dry-run，再应用明确确认短语。远程启用后测试授权与拒绝路径；禁用后确认 URL 不可用且 LAN 正常。Tailscale 使用 `serve status --json/reset`，并用 `tailscale funnel status` 确认输出为 `tailnet only`；Cloudflare 使用 root-only config 与 systemd。若 `tailscale status --json` 仍列出 `funnel` capability，应在管理控制台 Access controls 删除未使用的 `funnel` node attribute，不能用板端 `serve reset` 冒充策略层清理。

## 网络变更

只用检测到的 NetworkManager connection 名，不硬编码接口。`network-plan` 后用 `network-apply`；工具保存不含 Wi-Fi secret 的 IPv4/DNS 快照并安排 120 秒回滚。新连接可达后 `network-confirm`，失败则自动或手动 rollback。

## 升级与卸载

`deploy/product_access/upgrade.sh` 先保留现有安装副本再原子替换。`rollback.sh <backup>` 恢复。`uninstall.sh` 默认保留 NAS 数据、identity 和 product access 状态；只有用户另行明确批准才删除数据。

`/etc/digua-ai-nas/install-mode` 为 `access-only` 时，上述三个入口自动限定为产品访问层，不得改动既有 OpenClaw/Qwen systemd 单元。升级前后应记录这两个既有单元的哈希与活动状态。
