# Security Model

OpenClaw + S100P + NAS 的第一版安全目标是：先能用，但不扩大暴露面。

## 边界

| 对象 | 默认策略 |
| --- | --- |
| OpenClaw Gateway | 只允许 LAN 或 Tailscale 访问 |
| NAS | 只开放 `/OpenClawWorkspace` 专用共享 |
| S100P | 只保留必要 SSH、OpenClaw、ROS2 服务 |
| PC | Codex 工作站，不保存生产 token |
| 机器人控制 | 默认只读，控制动作必须白名单和二次确认 |

## NAS 目录建议

```text
/OpenClawWorkspace/
  inbox/
  outbox/
  documents/
  photos/
  videos/
  robot_datasets/
  logs/
  reports/
  tmp/
```

OpenClaw 不应挂载整个 NAS 家目录、照片库或备份根目录。

## Token 和凭据

- 不把 token 写入 Git。
- `.env` 只保留在设备本地。
- repo 只提交 `env.example`。
- NAS 账号为 OpenClaw 单独创建，不复用管理员账号。

## 工具执行

第一版只允许执行仓库或 NAS workspace 下的白名单脚本：

```text
scripts/probes/
scripts/robot/
```

危险命令需要二次确认：

- 删除、格式化、递归移动。
- 停止关键服务。
- 修改网络配置。
- 控制机器人运动。

## 验收检查

每次 baseline 验收至少检查：

```bash
ss -tulpn
systemctl status openclaw-gateway.service
mount | grep openclaw
ls -ld /mnt/nas/openclaw
```

如果使用 Windows ICS 临时联网，还要记录：

```text
S100P IP: 192.168.137.10
Windows ethernet IP: 192.168.137.1
```
