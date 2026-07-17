# S100P + NAS + OpenClaw startup link checker

这个目录保存 Windows 侧的开机自恢复工具，用来在电脑登录后自动检查并修复：

- PC 到 S100P 的以太网直连链路
- S100P 的双网段地址、默认路由和 DNS
- S100P 到 NAS 的 NFS 挂载与写入权限
- S100P 时钟、根分区容量和启动后的网络竞态
- OpenClaw 系统网关、AI-NAS 门户和本地 Qwen 健康链路

工具面向当前实测拓扑：

```text
Windows PC
  ├─ 以太网: 192.168.127.2/24
  ├─ ICS:    192.168.137.1/24
  │
S100P eth1
  ├─ 192.168.127.10/24
  └─ 192.168.137.10/24, default via 192.168.137.1

S100P eth0: 169.254.8.10/16
NAS:        169.254.143.37:/OpenClawWorkspace
mount:      /mnt/nas/openclaw
services:   system openclaw-gateway.service -> 127.0.0.1:18765
            user openclaw-gateway.service   -> 127.0.0.1:8765
            user qwen25-local-openai-gateway.service -> 127.0.0.1:18080
```

## Files

- `S100P-NAS-LinkCheck.ps1`: 主程序。包含托盘 GUI、链路检测、自动修复、日志和“复制给 Codex”的诊断文本。
- `link-check.config.json`: 固定参数配置。包括 Windows 网卡名、PC/S100P/NAS 地址、SSH key、NFS 路径、OpenClaw 服务名。
- `install-startup-task.ps1`: 注册 Windows 登录后自启动计划任务。

## Install

在 Windows PowerShell 中以管理员权限运行：

```powershell
cd "F:\Project\Digua\完全基于agent的s100使用和链路打通\scripts\startup_link_check"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-startup-task.ps1
```

安装后会创建计划任务：

```text
S100P-NAS-OpenClaw-LinkCheck
```

计划任务使用最高权限运行，并用隐藏 PowerShell 控制台启动：

```powershell
powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -STA -File "...\S100P-NAS-LinkCheck.ps1" -StartInTray
```

## Daily Use

开机登录后，程序默认隐藏在 Windows 右下角系统托盘，不弹 PowerShell 控制台，也不占任务栏。

- 双击托盘图标：打开状态窗口。
- 右键托盘图标：打开状态窗口、重新检测、复制给 Codex、打开日志目录、退出托盘程序。
- 链路正常：状态窗口约 5 秒后自动隐藏回托盘。
- 程序做过自动修复：状态窗口约 10 秒后自动隐藏。
- 链路失败：状态窗口会自动弹出，并按配置每 30 秒重试；默认最多重试 20 次。网线晚插、NAS 晚启动等情况不再要求重新登录 Windows。

如果手动关闭状态窗口，它只会隐藏到托盘；真正退出需要右键托盘图标选择“退出托盘程序”。

## Manual Check

无界面快速检测：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\S100P-NAS-LinkCheck.ps1 -NoGui -NoDelay
```

打开 GUI 检测：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File .\S100P-NAS-LinkCheck.ps1
```

隐藏到托盘启动：

```powershell
powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -STA -File .\S100P-NAS-LinkCheck.ps1 -StartInTray
```

只运行配置、语法和恢复契约自测，不访问实机：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\S100P-NAS-LinkCheck.ps1 -SelfTest
```

## Logs

日志默认写入：

```text
F:\Project\Digua\logs\link-check\YYYY-MM-DD.jsonl
```

每次检测会记录：

- 检测项名称和状态
- 关键命令输出
- 自动修复动作
- 最终状态 `OK`、`FIXED` 或 `FAIL`

日志会自动脱敏 `token`、`secret`、`authorization`、`password`、`app_secret` 等字段。

最终状态示例：

```json
{"status":"OK","windowsOk":true,"sshOk":true,"clockOk":true,"networkOk":true,"nasOk":true,"storageOk":true,"openclawOk":true}
```

## What It Repairs

Windows 侧：

- 检查 `以太网` 是否连接。
- 检查并补齐 `192.168.127.2/24` 和 `192.168.137.1/24`。
- 先检查 ICS 是否已经正确配置；只有 S100P 外网复测失败时才强制重建 WLAN → 以太网共享，避免每次运行都扰动网络。

S100P 侧：

- 检查 SSH key 免密登录。
- 检查板端与 Windows 的时钟偏差；超过 120 秒时先按 Windows UTC 校时，再重新启用 NTP。
- 补齐 `eth1` 上的 `192.168.127.10/24` 和 `192.168.137.10/24`。
- 设置默认路由 `default via 192.168.137.1 dev eth1 metric 50`。
- 设置 DNS。
- 校验 `/etc/netplan/99-hobot-net.yaml` 的持久配置。

NAS 侧：

- 检查 `169.254.143.37` 是否可达；地址变化时在 `eth0` 上发现实际 NFS export 并更新配置。
- 同时验证 NAS 的 NFS export 和 TCP/NFS 服务，而不是只依赖 Ping。
- 检查 `/mnt/nas/openclaw` 是否已挂载。
- 修复 `/mnt/nas` 父目录权限。
- 同时清除 `mnt-nas-openclaw.mount` 与 `.automount` 的 start-limit，并在网卡晚于 fstab 启动时重新挂载。
- 强制核对挂载源必须等于当前 NAS 的 `/OpenClawWorkspace`，防止把板载目录误判成 NAS。
- 执行“写入 → 读取 → 删除”临时探针，不残留测试文件。

OpenClaw/本地 AI 侧：

- 检查 system `openclaw-gateway.service` 和 `18765/health`。
- 检查 sunrise user 的 AI-NAS portal、Qwen 服务，以及 `8765/api/health`、`18080/health`。
- 网络被修复时只重连系统 OpenClaw；服务或健康接口异常时才同时恢复门户和 Qwen。
- 读取 S100P 根分区与 NAS 容量；根分区达到 90% 时告警，达到 98% 时阻断验收。

## Covered Failure Modes

| 场景 | 检测/恢复 |
| --- | --- |
| Windows 网线未插或晚插 | 明确报告 `Disconnected/0 bps`，托盘自动定时重试 |
| Windows 双 IP 丢失 | 最高权限任务自动补齐 |
| ICS 配置存在但 NAT/DNS 失效 | HTTPS/DNS 初检失败后按需重建 ICS，再做最终复测 |
| S100P 地址、路由或 DNS 漂移 | 修复运行时配置并校验 netplan |
| S100P 时钟错误 | 与 Windows UTC 比较并校时 |
| NAS IP 变化 | `eth0` ARP 发现 + NFS export 筛选 |
| NAS 比 S100P 晚启动 | 等待链路、清除 mount/automount start-limit 并重新挂载 |
| 假挂载或落到板载目录 | 校验精确 NFS source + 真实读写删除探针 |
| system/user systemd 混淆 | 分别检查系统 OpenClaw、sunrise 门户和 Qwen |
| 服务 active 但端口不可用 | 三个 loopback 健康接口均必须返回 HTTP 200 |
| 根分区接近写满 | 90% 告警，98% 失败 |

## Troubleshooting

如果窗口显示失败：

1. 点击“复制给 Codex”。
2. 把复制出来的诊断文本发给 Codex。
3. 同时说明 S100P、NAS、交换机/网线和电脑是否刚断电重启过。

优先检查：

- Windows 是否仍有 `192.168.127.2/24` 和 `192.168.137.1/24`。
- S100P 是否仍在 `192.168.127.10`。
- SSH key `C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519` 是否存在。
- S100P 是否能解析并通过 HTTPS 访问 `open.weixin.qq.com`。
- NAS 是否仍在 `169.254.143.37`；如果变化，日志中是否出现 `NAS_DISCOVERED_IP`。
- NFS export 是否仍是 `/OpenClawWorkspace`。
- systemd 是否出现 `mount-start-limit-hit`；新版脚本会同时 reset mount 和 automount。
