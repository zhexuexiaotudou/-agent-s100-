# S100P + NAS + OpenClaw startup link checker

这个目录保存 Windows 侧的开机自恢复工具，用来在电脑登录后自动检查并修复：

- PC 到 S100P 的以太网直连链路
- S100P 的双网段地址、默认路由和 DNS
- S100P 到 NAS 的 NFS 挂载与写入权限
- OpenClaw gateway 和飞书机器人链路

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
NAS:        169.254.110.209:/OpenClawWorkspace
mount:      /mnt/nas/openclaw
service:    openclaw-gateway.service
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
- 链路失败：状态窗口会自动弹出并停留。

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
{"status":"OK","windowsOk":true,"sshOk":true,"networkOk":true,"nasOk":true,"openclawOk":true}
```

## What It Repairs

Windows 侧：

- 检查 `以太网` 是否连接。
- 检查并补齐 `192.168.127.2/24` 和 `192.168.137.1/24`。

S100P 侧：

- 检查 SSH key 免密登录。
- 补齐 `eth1` 上的 `192.168.127.10/24` 和 `192.168.137.10/24`。
- 设置默认路由 `default via 192.168.137.1 dev eth1 metric 50`。
- 设置 DNS。
- 校验 `/etc/netplan/99-hobot-net.yaml` 的持久配置。

NAS 侧：

- 检查 `169.254.110.209` 是否可达。
- 检查 `/mnt/nas/openclaw` 是否已挂载。
- 修复 `/mnt/nas` 父目录权限。
- 尝试挂载 `169.254.110.209:/OpenClawWorkspace`。
- 写入小文件验证可写性。

OpenClaw/飞书侧：

- 检查 root user systemd 中的 `openclaw-gateway.service` 是否 active。
- 检查日志里是否有 `received message` 或 `dispatch complete`。
- 若网络刚修复、服务 inactive、或出现 `EAI_AGAIN open.feishu.cn`，自动重启 gateway。
- 飞书 `99991672` contact 权限错误只作为非阻断告警。

## Troubleshooting

如果窗口显示失败：

1. 点击“复制给 Codex”。
2. 把复制出来的诊断文本发给 Codex。
3. 同时说明 S100P、NAS、交换机/网线和电脑是否刚断电重启过。

优先检查：

- Windows 是否仍有 `192.168.127.2/24` 和 `192.168.137.1/24`。
- S100P 是否仍在 `192.168.127.10`。
- SSH key `C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519` 是否存在。
- S100P 是否能解析 `open.feishu.cn`。
- NAS 是否仍在 `169.254.110.209`。
- NFS export 是否仍是 `/OpenClawWorkspace`。

