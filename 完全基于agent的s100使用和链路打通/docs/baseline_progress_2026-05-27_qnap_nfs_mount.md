# Baseline Progress: QNAP NAS 直连与 NFS 挂载

本文记录上一次 GitHub 上传之后，S100P 直连 QNAP TS-264C NAS 并完成
`/mnt/nas/openclaw` 运行时挂载的实测过程。本文用于审阅后再推送到仓库。

## 结论摘要

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| S100P 直连 QNAP | verified | S100P `eth0` 能访问 QNAP NAS `169.254.110.209`，ping 0% 丢包。 |
| Windows 到 S100P 管理链路 | verified | S100P `eth1` 保持 `192.168.137.10/24`，默认路由仍走 `192.168.137.1`。 |
| QNAP 存储初始化 | operator verified | 已创建存储池 1，并创建 2 TB 厚卷 `Ctrl`。 |
| `OpenClawWorkspace` SMB 共享 | verified | `smbclient` 能看到 `OpenClawWorkspace`，并能写入/删除测试文件。 |
| SMB 内核挂载 | blocked | `mount -t cifs` 失败，原因是 S100P 当前内核没有 `cifs` 模块。 |
| QNAP NFS 导出 | verified | `showmount -e 169.254.110.209` 显示 `/OpenClawWorkspace` 导出给 `169.254.8.10`。 |
| NFS 运行时挂载 | verified | `/mnt/nas/openclaw` 已通过 NFS v4.1 挂载 `169.254.110.209:/OpenClawWorkspace`。 |
| NAS 写入测试 | verified | 已在 `/mnt/nas/openclaw/tmp` 写入并删除测试文件。 |
| 重启持久化 | not yet verified | 本轮没有写 `/etc/fstab`，也没有做重启后自动挂载验证。 |

仓库中不记录 NAS 密码。板端 SMB 凭据文件只存在于 S100P：

```text
/root/.smbcredentials-openclaw
mode: 600
```

## 网络拓扑

最终跑通的拓扑如下：

```text
Windows PC
  192.168.137.1
  |
  | 以太网 / Windows ICS 管理和上网链路
  |
S100P eth1
  192.168.137.10/24
  default route via 192.168.137.1

S100P eth0
  169.254.8.10/16
  no default route
  |
  | 直连网线
  |
QNAP TS-264C
  169.254.110.209
  OpenClawWorkspace share/export
```

S100P `eth0` 的 NetworkManager 配置：

```text
connection.id:      netplan-eth0
ipv4.method:        manual
ipv4.addresses:     169.254.8.10/16
ipv4.never-default: yes
ipv6.method:        ignore
```

这个配置保证 NAS 这条链路不会抢默认网关。S100P 出网仍然走 Windows ICS：

```text
8.8.8.8 via 192.168.137.1 dev eth1 src 192.168.137.10
```

Qfinder Pro 在电脑直接连接 NAS 时能发现 NAS；NAS 改接到 S100P `eth0` 后，
电脑上的 Qfinder 不再发现 NAS，这是预期行为。Qfinder 的发现依赖本地二层广播，
不会跨过 S100P 这层路由边界。

为了在不重新插线的情况下从电脑管理 QTS，临时通过 S100P 开了 SSH 隧道：

```text
127.0.0.1:18080 -> 169.254.110.209:8080
127.0.0.1:15001 -> 169.254.110.209:5001
```

Windows 侧验证结果：

```text
127.0.0.1:18080 tcp: ok, HTTP 200
127.0.0.1:15001 tcp: ok
```

## QNAP 配置

QTS 侧由操作者完成的配置：

1. 在单块 4 TB 硬盘上创建存储池。
2. 在存储池中创建 2 TB 厚卷，名称为 `Ctrl`。
3. 在 `Ctrl` 上创建普通共享文件夹 `OpenClawWorkspace`。
4. 共享路径选择 QNAP 自动指定。
5. 访客访问权限设为拒绝访问。
6. 给操作者提供的 NAS 账号授予读写权限。
7. 启用 NFS 服务。
8. 给 S100P `169.254.8.10` 添加 NFS 主机访问权限。
9. NFS 权限设为读写，安全类型为 `sys`，并避免把所有用户 squash 成
   `guest`。

关键选择：

```text
共享类型: 普通共享文件夹，不是 ISO 共享文件夹
共享/导出名: OpenClawWorkspace
NFS 允许主机: 169.254.8.10
S100P 挂载点: /mnt/nas/openclaw
```

## 验证证据

S100P 内核和网口：

```text
hostname: ubuntu
kernel: 6.1.158-rt58-DR-4.0.5-2603031328-g9f678e-g6caa4d
eth0: 169.254.8.10/16
eth1: 192.168.137.10/24
route to NAS: 169.254.110.209 dev eth0 src 169.254.8.10
route to internet: 8.8.8.8 via 192.168.137.1 dev eth1 src 192.168.137.10
```

NAS 连通性：

```text
PING 169.254.110.209: 2 transmitted, 2 received, 0% packet loss
SMB 445: succeeded
QTS 5001: succeeded
QTS 8080: succeeded
```

SMB 共享发现和写入测试：

```text
Sharename             Type
---------             ----
Public                Disk
OpenClawWorkspace     Disk
IPC$                  IPC

SMB write test under OpenClawWorkspace/tmp: passed
```

SMB 挂载失败的根因：

```text
mount -t cifs //169.254.110.209/OpenClawWorkspace /mnt/nas/openclaw ...
mount error: cifs filesystem not supported by the system
modprobe cifs: FATAL: Module cifs not found in directory /lib/modules/6.1.158-rt58-DR-4.0.5-2603031328-g9f678e-g6caa4d
```

结论：`cifs-utils` 和 SMB 登录可用，但当前 S100P 内核没有 CIFS 文件系统模块，
因此第一版 NAS workspace 挂载切换到 NFS。

NFS 验证：

```text
port 111: open
port 2049: open
showmount -e 169.254.110.209:
  /OpenClawWorkspace 169.254.8.10
```

运行时 NFS 挂载：

```text
TARGET            SOURCE                             FSTYPE
/mnt/nas/openclaw 169.254.110.209:/OpenClawWorkspace nfs4

OPTIONS include:
rw,vers=4.1,proto=tcp,sec=sys,clientaddr=169.254.8.10

Filesystem size:
169.254.110.209:/OpenClawWorkspace  2.0T  17G  2.0T  1% /mnt/nas/openclaw
```

workspace 初始化目录：

```text
/mnt/nas/openclaw/
  documents/
  logs/
  reports/
  robot_datasets/
  tmp/
```

写入测试：

```text
printf review > /mnt/nas/openclaw/tmp/.review_write_test
cat /mnt/nas/openclaw/tmp/.review_write_test
rm -f /mnt/nas/openclaw/tmp/.review_write_test
write_test_ok
```

## 当前风险和后续事项

- 当前只是运行时挂载，还没有写入 `/etc/fstab`。
- 还没有验证 S100P 重启后的自动挂载。
- NAS 只接在 S100P `eth0` 上时，电脑侧 Qfinder Pro 不会自动发现它。需要用
  SSH 隧道管理 QTS，或者临时把电脑网线直连 NAS。
- S100P 上保留了 SMB 凭据文件用于 `smbclient` 测试，但 SMB 内核挂载被缺失的
  CIFS 模块阻塞。除非后续补齐内核模块，否则第一版不要依赖 SMB 挂载。
- A-003 要标成完全 `verified` 前，需要写入经审阅的 NFS `/etc/fstab` 行，重启
  S100P 后再次验证 `findmnt` 和写入测试。

审阅后建议的持久化挂载行：

```text
169.254.110.209:/OpenClawWorkspace /mnt/nas/openclaw nfs defaults,nofail,x-systemd.automount 0 0
```

持久化后的建议验收命令：

```bash
systemctl daemon-reload
mount -a
findmnt /mnt/nas/openclaw
touch /mnt/nas/openclaw/tmp/.write_test && rm /mnt/nas/openclaw/tmp/.write_test
reboot
findmnt /mnt/nas/openclaw
touch /mnt/nas/openclaw/tmp/.write_test && rm /mnt/nas/openclaw/tmp/.write_test
```
