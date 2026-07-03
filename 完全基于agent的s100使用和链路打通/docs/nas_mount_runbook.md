# NAS 挂载 Runbook

本文用于推进 A-003：把 TS-264C 的 `/OpenClawWorkspace` 专用共享挂载到 S100P 的 `/mnt/nas/openclaw`。

## 需要先确认的信息

| 字段 | 示例 | 说明 |
| --- | --- | --- |
| 协议 | `smb` 或 `nfs` | TS-264C 开启的共享协议 |
| NAS 地址 | `192.168.137.x` 或固定 LAN IP | S100P 必须能访问 |
| 共享名或导出路径 | SMB: `OpenClawWorkspace`; NFS: `/share/OpenClawWorkspace` | 不要填 NAS 根目录 |
| 专用账号 | `openclaw` | 不使用 NAS 管理员账号 |
| 权限 | 读写 `/OpenClawWorkspace` | 第一版只给这个共享读写 |

不要把 NAS 密码写进 repo。S100P 上的凭据文件建议放在：

```text
/root/.smbcredentials-openclaw
```

权限必须是：

```bash
chmod 600 /root/.smbcredentials-openclaw
```

## 挂载前预检

如果还不知道 NAS 地址或共享名，先跑只读发现探针：

```bash
bash scripts/run_allowlisted_tool.sh nas_discovery_probe /root/.openclaw/workspace/logs/probes
```

这个探针只记录路由、邻居表、mDNS 提示、SMB/NFS 工具状态和当前挂载状态；
不扫网段、不登录 NAS、不执行挂载。

SMB：

```bash
bash scripts/probes/check_nas_mount_inputs.sh \
  --protocol smb \
  --host <NAS_IP> \
  --share OpenClawWorkspace
```

NFS：

```bash
bash scripts/probes/check_nas_mount_inputs.sh \
  --protocol nfs \
  --host <NAS_IP> \
  --share /share/OpenClawWorkspace
```

预检只做只读检查，不执行挂载。

## 2026-05-27 预检脚本验证记录

在 S100P 板端通过 RDK Studio 后端执行临时目录 smoke test：

```text
protocol=smb
host=192.168.137.1
share=OpenClawWorkspace
mountpoint=/mnt/nas/openclaw
ping=ok
mount.cifs=missing
tcp_445=ok
suggested_source=//192.168.137.1/OpenClawWorkspace
mountpoint_exists=no
already_mounted=no
PREFLIGHT_DONE
Refusing mountpoint outside /mnt/nas/openclaw: /root
Refusing mountpoint outside /mnt/nas/openclaw: /mnt/nas
NAS_PREFLIGHT_OK
```

结论：

- 预检脚本语法通过。
- 允许的挂载点 `/mnt/nas/openclaw` 可以进入预检流程。
- 危险挂载点 `/root` 和 `/mnt/nas` 被拒绝。
- 这次只用 Windows 主机地址做连通性 smoke test；真实挂载仍等待 TS-264C 共享信息。

## 2026-05-27 挂载脚本 dry-run 验证记录

`scripts/mount_openclaw_nas.sh` 已同步到板端：

```text
/root/.openclaw/workspace/scripts/mount_openclaw_nas.sh
/root/.openclaw/workspace/scripts/init_nas_workspace.sh
```

语法检查通过：

```text
bash -n /root/.openclaw/workspace/scripts/mount_openclaw_nas.sh
mount_syntax:0
bash -n /root/.openclaw/workspace/scripts/init_nas_workspace.sh
init_syntax:0
```

dry-run 输出：

```text
protocol=smb
host=192.168.137.1
share=OpenClawWorkspace
mountpoint=/mnt/nas/openclaw
source=//192.168.137.1/OpenClawWorkspace
mode=dry-run
mount.cifs=missing
ping=ok
already_mounted=no
DRY_RUN_DONE
```

该命令未写凭据、未执行挂载、未写 `/etc/fstab`。`192.168.137.1` 只是 Windows ICS host 连通性 smoke test，不是真实 TS-264C NAS 地址。

危险挂载点拒绝验证：

```text
unsafe_exit:2
Refusing mountpoint outside /mnt/nas/openclaw: /mnt/nas
```

## 2026-05-27 SMB 依赖安装记录

板端确认能联网且 apt 源可用后，已安装 SMB 挂载依赖：

```bash
DEBIAN_FRONTEND=noninteractive apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y cifs-utils
```

安装结果：

```text
/usr/sbin/mount.cifs
mount.cifs version: 6.14
cifs-utils Installed: 2:6.14-1ubuntu0.3
```

安装后 dry-run 复测：

```text
mount.cifs=ok
ping=ok
already_mounted=no
DRY_RUN_DONE
```

额外直连检查：

```text
tcp_445=ok
already_mounted=no
```

因此 SMB 依赖不再是 A-003 的阻塞项。剩余阻塞是 TS-264C 的真实 host、共享名、账号和凭据。

## 手动挂载模板

仓库提供了一个默认 dry-run 的执行脚本，拿到 NAS 信息后优先用它生成计划并检查依赖：

```bash
bash scripts/mount_openclaw_nas.sh \
  --protocol smb \
  --host <NAS_IP> \
  --share OpenClawWorkspace
```

确认输出无误后再显式加 `--apply`。SMB 密码不要写进命令行，使用环境变量写入板端凭据文件：

```bash
OPENCLAW_NAS_PASSWORD='<NAS_PASSWORD>' \
bash scripts/mount_openclaw_nas.sh \
  --protocol smb \
  --host <NAS_IP> \
  --share OpenClawWorkspace \
  --username openclaw \
  --create-credentials \
  --init-workspace \
  --apply
```

如果手动挂载、写入测试和目录初始化都通过，再追加 `--write-fstab --apply` 持久化。脚本只允许挂载到 `/mnt/nas/openclaw` 及其子路径。

SMB：

```bash
mkdir -p /mnt/nas/openclaw
mount -t cifs //<NAS_IP>/OpenClawWorkspace /mnt/nas/openclaw \
  -o credentials=/root/.smbcredentials-openclaw,vers=3.0,iocharset=utf8,uid=0,gid=0,file_mode=0640,dir_mode=0750
```

NFS：

```bash
mkdir -p /mnt/nas/openclaw
mount -t nfs -o vers=4 <NAS_IP>:/share/OpenClawWorkspace /mnt/nas/openclaw
```

## 验收

```bash
findmnt /mnt/nas/openclaw
test -d /mnt/nas/openclaw/logs
touch /mnt/nas/openclaw/tmp/.write_test
rm /mnt/nas/openclaw/tmp/.write_test
bash scripts/init_nas_workspace.sh /mnt/nas/openclaw
bash scripts/run_allowlisted_tool.sh index_documents /mnt/nas/openclaw/documents /mnt/nas/openclaw/reports
bash scripts/run_allowlisted_tool.sh log_diagnose /mnt/nas/openclaw/logs /mnt/nas/openclaw/logs/probes
```

## 自动挂载

手动挂载和写入验证通过后，再写 `/etc/fstab`。不要在预检阶段写入。

SMB fstab 模板：

```text
//<NAS_IP>/OpenClawWorkspace /mnt/nas/openclaw cifs credentials=/root/.smbcredentials-openclaw,vers=3.0,iocharset=utf8,uid=0,gid=0,file_mode=0640,dir_mode=0750,nofail,x-systemd.automount 0 0
```

NFS fstab 模板：

```text
<NAS_IP>:/share/OpenClawWorkspace /mnt/nas/openclaw nfs defaults,nofail,x-systemd.automount 0 0
```

写入后执行：

```bash
systemctl daemon-reload
mount -a
findmnt /mnt/nas/openclaw
```

最后重启 S100P，再重复验收命令。
