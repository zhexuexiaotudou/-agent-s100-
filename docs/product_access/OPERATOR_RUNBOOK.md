# 运维手册

## 日常

检查 `digua-doctor`、`/healthz`、`/readyz`、NAS mount、Qwen 与门户服务。使用 `digua-access status/endpoints` 查看非秘密配置。任何实际变更写入 `reports/access/raw/command_execution_log.jsonl`，但不得记录密码、Cookie、Authorization、claim 或 tunnel credential。

## 远程启停

先 dry-run，再应用明确确认短语。远程启用后测试授权与拒绝路径；禁用后确认 URL 不可用且 LAN 正常。Tailscale 使用 `serve status --json/reset`，Cloudflare 使用 root-only config 与 systemd。

## 网络变更

只用检测到的 NetworkManager connection 名，不硬编码接口。`network-plan` 后用 `network-apply`；工具保存不含 Wi-Fi secret 的 IPv4/DNS 快照并安排 120 秒回滚。新连接可达后 `network-confirm`，失败则自动或手动 rollback。

## 升级与卸载

`deploy/product_access/upgrade.sh` 先保留现有安装副本再原子替换。`rollback.sh <backup>` 恢复。`uninstall.sh` 默认保留 NAS 数据、identity 和 product access 状态；只有用户另行明确批准才删除数据。
