# Baseline Progress: NAS-backed Service Policy And Hardening Plan

Date: 2026-05-28

本文记录 B-010 的服务策略和 hardening dry-run 计划已经写入 NAS。两项都是只读输出，
没有停止服务、没有改防火墙、没有 mask systemd unit。

## Outputs

```text
/mnt/nas/openclaw/logs/probes/service_policy_20260528-183619.md
/mnt/nas/openclaw/logs/probes/service_hardening_plan_20260528-183619.md
```

更新后的 roll-up：

```text
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-183640.md
Probe reports: 16
Workspace reports: 16
Service policy: /mnt/nas/openclaw/logs/probes/service_policy_20260528-183619.md
```

## Service Policy Matrix

| Component | Observed | Suggested decision | Current action |
| --- | --- | --- | --- |
| OpenClaw Gateway | loopback | keep-loopback | 保持现状 |
| SSH | present | keep-trusted-management | 保持现状 |
| NFS/RPC server stack | present | disable-if-client-only | 等用户确认 |
| x11vnc | present | disable-if-unused | 等用户确认 |
| iiod | present | keep-or-firewall | 等用户确认 |

## Hardening Plan Status

Dry-run plan 中生成了候选命令，但没有执行：

```bash
sudo systemctl disable --now nfs-server nfs-mountd rpcbind rpc-statd || true
sudo systemctl mask nfs-server nfs-mountd rpcbind rpc-statd || true
sudo systemctl disable --now x11vnc || true
sudo systemctl mask x11vnc || true
sudo systemctl disable --now iiod || true
sudo systemctl mask iiod || true
```

Firewall-only alternative 也只是写入报告：

```bash
sudo ufw allow from 192.168.137.0/24 to any port 22 proto tcp
sudo ufw deny 5900/tcp
sudo ufw deny 111 && sudo ufw deny 2049
sudo ufw deny 30431/tcp
```

## Baseline Impact

- B-010 remains `doing`: security audit、service policy、hardening plan 都已 NAS-backed。
- 真正关闭 NFS/RPC、x11vnc、iiod 或上防火墙需要用户确认，当前未做。
- A-003 不受影响：S100P 当前是 NAS client；是否关闭本机 NFS server 仍需确认 S100P 不承担 export。
