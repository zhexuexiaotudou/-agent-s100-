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

## 既有后台运行时漂移

access-only 安装器不会自动覆盖既有 OpenClaw/Qwen 单元。若登录与文件访问正常、AI 助手却返回 `local_qwen_chat_failed`，先确认 `127.0.0.1:18080/health` 为 200，再以服务用户执行：

```bash
release/install/sync_openclaw_portal_unit.sh --dry-run --source-root <merged-main>
release/install/sync_openclaw_portal_unit.sh --apply --source-root <merged-main>
```

该工具只同步用户级 `openclaw-gateway.service`，执行前备份旧 unit，失败时自动恢复；不会启停 Qwen 或产品访问服务。Qwen 可以由 system scope 或 user scope 承载，但 `ss -ltnp 'sport = :18080'` 必须只显示一个监听者。巡检时同时检查两个 scope，并以端口所有者、unit 状态和 `/health` 三项共同判定。

## 上游身份库锁竞争

相册并发加载期间若 NAS 身份库短时锁定，已有桥接会话应继续返回 200；尚未建立桥接的新会话最多经过受控重试后返回 `503 upstream_identity_bridge_unavailable`，而不是断开连接。巡检时运行：

```bash
sudo journalctl -u digua-product-access.service --since '<部署时间>' --no-pager
curl -fsS http://127.0.0.1/healthz
curl -fsS http://127.0.0.1:8765/api/health
findmnt /mnt/nas/openclaw
```

日志中若出现未捕获的 `sqlite3.OperationalError: database is locked`、`BrokenPipe` 或请求无状态码结束，视为访问层回归。若只有明确的 503，先等待写事务结束并重试登录后的首个业务请求；不要删除或重建任一 identity DB。持续锁竞争需要定位实际写入者和 NFS 状态，再按 access-only 回滚点恢复，不得用放宽认证绕过。

## 长耗时 AI 请求

产品访问层对普通上游请求保持 60 秒超时，对 `/api/copilot/chat` 和 `/api/assistant/chat` 使用 240 秒超时；该值必须长于 OpenClaw 云端桥接的 210 秒上限。若端口 80 在第 60 秒返回 502，而 8765 随后出现 200 与 `BrokenPipeError`，优先检查产品访问层是否仍运行旧版 `server.py`，不要误判为 MiniMax 或 S100P 断网。部署后必须从端口 80 走已认证会话验证真实联网检索、云端模型标识和非空来源。
