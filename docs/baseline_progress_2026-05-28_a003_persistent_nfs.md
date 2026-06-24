# Baseline Progress: A-003 Persistent NFS Mount

Date: 2026-05-28

本文记录 A-003 `NAS workspace 挂载到 S100P` 从运行时挂载推进到重启后自动恢复的实测闭环。

## Verdict

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| S100P eth0 NAS 专用地址 | verified | 重启后 `eth0` 自动恢复 `169.254.8.10/16`。 |
| NAS 路由 | verified | 重启后 `ip route get 169.254.110.209` 走 `dev eth0 src 169.254.8.10`。 |
| NFS fstab 持久化 | verified | `/etc/fstab` 包含 `169.254.110.209:/OpenClawWorkspace /mnt/nas/openclaw nfs4 ...`。 |
| systemd automount | verified | 重启后访问 `/mnt/nas/openclaw` 自动触发 NFS v4.1 挂载。 |
| NAS 写入 | verified | 重启后在 `/mnt/nas/openclaw/tmp` 写入并删除测试文件成功。 |
| OpenClaw Gateway | verified after repair | 重启后启用 root linger 并启动 `user@0.service` 后，`openclaw-gateway.service` active，飞书 WebSocket ready。 |

A-003 现在可以标记为 `verified`：NAS workspace 在 S100P 重启后能自动恢复为可写 NFS 挂载。

## What Changed On S100P

### `/etc/fstab`

新增持久化 automount 行：

```text
169.254.110.209:/OpenClawWorkspace /mnt/nas/openclaw nfs4 defaults,nofail,x-systemd.automount,_netdev 0 0
```

写入前已备份：

```text
/etc/fstab.bak-openclaw-20260528-175141
```

### `/etc/netplan/99-hobot-net.yaml`

修复重启后 NAS 路由丢失的根因：原配置把 `eth0` 设为 DHCP，重启后没有恢复
`169.254.8.10/16`，导致 `169.254.110.209` 错误走到 `eth1`。

当前配置：

```yaml
network:
  version: 2
  renderer: NetworkManager
  ethernets:
    eth0:
      addresses:
        - "169.254.8.10/16"
      dhcp4: false
      dhcp6: false
      link-local: []
      macaddress: "6e:75:df:40:9c:bc"
    eth1:
      addresses:
        - "192.168.127.10/24"
        - "192.168.137.10/24"
      routes:
        - to: default
          via: 192.168.137.1
          metric: 50
      nameservers:
        addresses:
          - 223.5.5.5
          - 8.8.8.8
          - 8.8.4.4
      dhcp4: false
      dhcp6: false
      macaddress: "3e:a5:ed:ba:5b:b2"
```

写入前已备份：

```text
/etc/netplan/99-hobot-net.yaml.bak-a003-20260528-180031
```

### Startup Link Checker

同步修复 Windows 侧托盘工具，避免它后续把 `eth0` 再写回 DHCP。

变更点：

```text
scripts/startup_link_check/link-check.config.json
  s100p.nasInterface = eth0
  s100p.nasInterfaceIPv4 = 169.254.8.10/16

scripts/startup_link_check/S100P-NAS-LinkCheck.ps1
  Ensure-S100PNetwork now restores eth0 runtime address and NAS route.
  Get-NetplanYaml now writes eth0 as static 169.254.8.10/16.
```

## Reboot Evidence

第二次重启后的验收命令输出摘要：

```text
remote_host=ubuntu
uptime=up 0 minutes
```

地址：

```text
eth0: inet 169.254.8.10/16
eth1: inet 192.168.127.10/24
eth1: inet 192.168.137.10/24
```

NAS 路由：

```text
169.254.110.209 dev eth0 src 169.254.8.10
```

NAS ping：

```text
1 packets transmitted, 1 received, 0% packet loss
```

fstab：

```text
169.254.110.209:/OpenClawWorkspace /mnt/nas/openclaw nfs4 defaults,nofail,x-systemd.automount,_netdev 0 0
```

automount 触发后：

```text
TARGET            SOURCE                             FSTYPE
/mnt/nas/openclaw systemd-1                          autofs
/mnt/nas/openclaw 169.254.110.209:/OpenClawWorkspace nfs4
```

写入测试：

```text
printf a003_reboot2 > /mnt/nas/openclaw/tmp/.a003_reboot2_test
cat /mnt/nas/openclaw/tmp/.a003_reboot2_test
rm -f /mnt/nas/openclaw/tmp/.a003_reboot2_test
```

结果：

```text
REBOOT2_AUTOMOUNT_OK
```

## OpenClaw Post-Reboot Note

重启后首次检查 root user systemd 时出现：

```text
Failed to connect to bus: No such file or directory
```

已执行：

```bash
sudo loginctl enable-linger root
sudo systemctl start user@0.service
sudo env XDG_RUNTIME_DIR=/run/user/0 systemctl --user restart openclaw-gateway.service
```

随后验证：

```text
openclaw-gateway.service: active
gateway listening on 127.0.0.1:18789
ws client ready
open.feishu.cn DNS OK
NAS write OK
```

这说明 A-003 已闭环；A-002/A-004 也具备重启后恢复路径，但后续仍应单独记录
Gateway root user manager 的持久化策略。

## Baseline Impact

- A-003: `verified`
- A-004: remains `verified`
- A-010: still `doing`; 7 天稳定性采样仍需继续
- B-002/B-005/B-007/A-009: 可以切到 `/mnt/nas/openclaw` 做 NAS-backed 复测
