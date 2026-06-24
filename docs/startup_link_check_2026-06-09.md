# Startup Link Check Repair - 2026-06-09

## Symptom

Local startup link check log:

```text
F:\Project\Digua\logs\link-check\2026-06-09.jsonl
```

Initial failed items:

```text
Windows ICS 共享: 重启 SharedAccess 后重新获取共享网卡失败
S100P 外网/DNS: S100P 外网或飞书域名解析失败
OpenClaw/飞书: gateway active 但近期未看到飞书消息，可在飞书发测试消息复核
```

Passing items at the same time:

```text
PC -> S100P ping: 192.168.127.10 可达
PC -> S100P SSH 端口: 192.168.127.10:22 可达
S100P SSH key: 免密 SSH 登录成功
S100P 运行时网络: S100P 双网段、默认路由和 DNS 已就绪
S100P netplan 持久化: netplan 已包含双网段、默认路由和 DNS
S100P -> NAS/NFS: NAS 可达、NFS 已挂载且可写
```

## Diagnosis

S100P could reach the Windows gateway:

```text
192.168.137.1
```

S100P could not reach the external DNS probe:

```text
223.5.5.5
```

The Windows host itself could reach:

```text
223.5.5.5
open.feishu.cn
```

Therefore the failure was in Windows ICS/NAT forwarding from:

```text
WLAN -> 以太网
```

The local Codex process was not running as Administrator, so direct `HNetCfg.HNetShare` COM inspection returned:

```text
E_ACCESSDENIED
```

The existing scheduled task was available:

```text
S100P-NAS-OpenClaw-LinkCheck
```

It is installed with:

```text
RunLevel Highest
```

## Script Fix

Updated script:

```text
F:\Project\Digua\scripts\startup_link_check\S100P-NAS-LinkCheck.ps1
```

Fixes:

- `Ensure-WindowsIcsSharing` now skips null connection objects returned by `HNetCfg.HNetShare.EnumEveryConnection()`.
- `Ensure-WindowsIcsSharing` records per-connection COM errors instead of aborting the whole repair.
- `Restart-Service -Name SharedAccess -Force` failure no longer immediately fails the ICS repair path.
- After a `SharedAccess` restart attempt, the script still reacquires COM connections and tries to enable:

```text
WLAN: SharingConnectionType 0
以太网: SharingConnectionType 1
```

Syntax check:

```text
PS_PARSE_OK
```

## Repair Run

The stale scheduled task instance was stopped, then restarted:

```powershell
Stop-ScheduledTask -TaskName 'S100P-NAS-OpenClaw-LinkCheck'
Start-ScheduledTask -TaskName 'S100P-NAS-OpenClaw-LinkCheck'
```

Successful repair log:

```text
2026-06-09T12:56:18 Windows ICS 共享 FIXED
2026-06-09T12:56:19 Windows IP 192.168.127.2 FIXED
2026-06-09T12:56:25 S100P 外网/DNS OK
2026-06-09T12:56:26 S100P -> NAS/NFS OK
2026-06-09T12:56:45 OpenClaw/飞书 FIXED
2026-06-09T12:56:45 run_end status FIXED failures []
```

ICS state after repair:

```text
WLAN enabled=True type=0
以太网 enabled=True type=1
```

Independent S100P verification after repair:

```text
ping 192.168.137.1: 0% packet loss
ping 223.5.5.5: 0% packet loss
getent hosts open.feishu.cn: returned 222.192.187.* records
```

## Current Status

Current link status after the repair:

```text
Windows ICS/NAT: fixed
S100P internet/DNS: ok
NAS/NFS: ok
OpenClaw/Feishu: fixed
```

The scheduled task may remain in `Running` state because it was launched with `-StartInTray`. That state does not mean the network check is still failing; the authoritative result is the latest `run_end` event in:

```text
F:\Project\Digua\logs\link-check\2026-06-09.jsonl
```
