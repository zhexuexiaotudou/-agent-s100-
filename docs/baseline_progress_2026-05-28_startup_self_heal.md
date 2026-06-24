# Baseline Progress: Windows 开机自恢复链路

Date: 2026-05-28

本文记录 PC 登录后自动检查并修复 `PC -> S100P -> NAS -> OpenClaw/飞书`
整条链路的实测进展。它补强 Baseline A 的 PC parity、NAS workspace、飞书入口
和稳定性证据，也给 Baseline B 的日志诊断和安全审计提供一个本地运维入口。

## 结论摘要

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| Windows 开机自启动 | verified path | 已实现 `S100P-NAS-OpenClaw-LinkCheck` 计划任务入口，隐藏 PowerShell 控制台启动托盘程序。 |
| 托盘常驻状态查看 | verified path | 主程序支持 `-StartInTray`，开机后默认隐藏到系统托盘，双击可打开状态窗口。 |
| PC 到 S100P 链路 | verified | 最新日志显示 `192.168.127.10` ping 和 SSH 端口均 OK，SSH key 免密登录成功。 |
| S100P 双网段和外网 | verified | 最新日志显示 `eth1` 同时具备 `192.168.127.10/24` 与 `192.168.137.10/24`，默认路由走 `192.168.137.1`，`open.feishu.cn` 可解析。 |
| S100P 到 NAS/NFS | verified | 最新日志显示 NAS `169.254.110.209` 可达，`/mnt/nas/openclaw` 为 NFS v4.1 挂载且可写。 |
| OpenClaw/飞书入口 | verified | 最新日志显示 `openclaw-gateway.service` active，飞书日志有 `received message` 和 `dispatch complete`。 |
| 7x24 稳定性 | collecting | 本工具降低了电脑开机、NAS/S100P 断电后的人肉恢复成本，但还不能替代 7 天连续采样。 |

## Implementation

工具目录：

```text
scripts/startup_link_check/
```

文件：

```text
S100P-NAS-LinkCheck.ps1
install-startup-task.ps1
link-check.config.json
README.md
```

计划任务动作：

```powershell
powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -STA -File "...\S100P-NAS-LinkCheck.ps1" -StartInTray
```

日常入口：

```text
Windows 右下角托盘图标
  - 双击：打开状态窗口
  - 右键：重新检测、复制给 Codex、打开日志、退出
```

## Scope

启动检测覆盖：

1. Windows 侧 `以太网` 是否连接。
2. Windows 是否有 `192.168.127.2/24` 和 `192.168.137.1/24`。
3. PC 是否能 ping/SSH 到 `sunrise@192.168.127.10`。
4. S100P `eth1` 是否有双网段地址、默认路由和 DNS。
5. S100P 是否能 ping Windows ICS 网关和公网 DNS，并解析 `open.feishu.cn`。
6. S100P 是否能访问 NAS `169.254.110.209`。
7. `/mnt/nas/openclaw` 是否已挂载并可写。
8. `openclaw-gateway.service` 是否 active。
9. 飞书 gateway 日志是否有 ready、received message 或 dispatch complete。

自动修复覆盖：

```text
Windows missing IP -> New-NetIPAddress
S100P missing eth1 IP -> ip addr add
S100P missing route -> ip route replace
S100P DNS -> resolvectl dns/domain
S100P netplan -> /etc/netplan/99-hobot-net.yaml
NAS parent permission -> chmod 755 /mnt/nas
NAS missing mount -> mount -t nfs4 169.254.110.209:/OpenClawWorkspace /mnt/nas/openclaw
OpenClaw network recovered or EAI_AGAIN -> restart openclaw-gateway.service
```

## Local Evidence

日志文件：

```text
F:\Project\Digua\logs\link-check\2026-05-28.jsonl
```

开机/托盘路径记录：

```json
{"event":"run_start","data":{"noDelay":false,"useStartupDelay":true,"noGui":false,"startInTray":true}}
```

Windows 侧：

```text
Windows 网卡: OK, 以太网 已连接，链路速率 1 Gbps
Windows IP 192.168.127.2: OK
Windows IP 192.168.137.1: OK
```

PC -> S100P：

```text
PC -> S100P ping: OK, 192.168.127.10 可达
PC -> S100P SSH 端口: OK, 192.168.127.10:22 可达
S100P SSH key: OK, S100P_SSH_OK / ubuntu / sunrise
```

S100P 网络：

```text
S100P_NETWORK_RUNTIME_OK
eth1:
  192.168.127.10/24
  192.168.137.10/24
default via 192.168.137.1 dev eth1 metric 50
S100P_INTERNET_OK
```

NAS：

```text
TARGET            SOURCE                             FSTYPE
/mnt/nas/openclaw 169.254.110.209:/OpenClawWorkspace nfs4
NAS_LINK_OK
```

OpenClaw/飞书：

```text
SERVICE_STATE=active
openclaw-gateway.service: Active: active (running)
feishu[default]: received message
feishu[default]: dispatch complete
```

最终状态：

```json
{"status":"OK","windowsOk":true,"sshOk":true,"networkOk":true,"nasOk":true,"openclawOk":true}
```

## Baseline Impact

### Baseline A：S100P PC Parity

这一步把“像 PC 一样可恢复、可观察”的能力向前推了一步：

- A-003 NAS workspace：运行时 NFS 挂载、可达、可写再次确认；但 `/etc/fstab`
  和 S100P 重启后自动挂载仍未验收，因此 A-003 仍是 `doing`。
- A-004 飞书入口：飞书消息 received/dispatch complete 再次确认。
- A-010 稳定性：新增 PC 登录后自动巡检和自恢复入口；但 7 天连续稳定性仍在
  `collecting`，不能标记为完整 verified。

### Baseline B：AI NAS Homework

这一步不是新增 AI NAS 功能，而是补齐了产品化运维能力：

- B-005 日志分析助手：本工具产生结构化 JSONL 检测日志，并提供“复制给 Codex”
  的排障上下文；后续应让 `log_diagnose` 读取这类链路日志。
- B-010 安全审计：日志自动脱敏 token、secret、authorization、password、
  app_secret；飞书 `99991672` contact 权限错误被明确标为非阻断告警。

## Remaining Work

1. A-003：写入并审阅 NFS `/etc/fstab` 或 systemd mount/automount，再重启
   S100P 验证 `findmnt` 和写入测试。
2. A-010：把稳定性 sampler 的输出目录切到 NAS，积累 7 天样本并生成 summary。
3. B-005：扩展 `log_diagnose`，让它能读取 Windows link-check JSONL 日志和
   S100P Gateway 日志，输出一次端到端故障摘要。
4. B-010：决定是否处理 S100P 非必要开放服务；飞书 contact scope 继续作为
   follow-up，不阻塞消息入口。
