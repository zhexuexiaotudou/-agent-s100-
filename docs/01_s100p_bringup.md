# 01. 从拿到 S100P 到接入 RDK Studio

## 1. 烧录系统

官方烧录教程：

https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/install_os/rdk_s100/instruction

本次跑通路线：

- 板卡：RDK S100P
- 主机：Windows 电脑，需要管理员权限修改网卡 IPv4
- 线缆：USB Type-C 线、以太网线
- 辅助工具：XBurn、MobaXterm、RDK Studio
- 连接：USB Type-C 连接电脑
- 下载模式：`DFU + Fastboot`
- 工具：XBurn
- 过程：严格按照官方页面执行

默认账号只用于本地首次上手：

```text
sunrise / sunrise
root / root
```

完成链路打通后应修改默认密码或改用 SSH key。

烧录阶段不要自行修改官方流程。agent 只需要确认工具、镜像、下载模式和板卡识别状态。

## 2. 连接电脑和 S100P

烧录完成后，用网线连接：

```text
电脑网口 <-> S100P 右侧网口
```

这个右侧网口对应板端：

```text
eth1
```

## 3. 查询板端 IP

使用烧录阶段用过的 MobaXterm 登录板子。

板端执行：

```bash
ifconfig -a
```

找到 `eth1`，记录 IP。

本次实测常见地址：

```text
192.168.127.10
```

如果你的板子不是这个 IP，以 `ifconfig -a` 显示为准。下文用 `<BOARD_IP>` 代表实际板端 IP。

默认账号通常是：

```text
sunrise / sunrise
root / root
```

## 4. 配置 Windows 以太网 IPv4

打开：

```text
控制面板
-> 网络和 Internet
-> 网络和共享中心
-> 更改适配器设置
```

找到“以太网连接了一个未知设备”的网卡。修改前建议截图或记录原设置；如果该网卡之后要恢复联网，改回自动获取 IP。

进入：

```text
属性
-> Internet 协议版本 4（TCP/IPv4）
-> 使用下面的 IP 地址
```

填写：

```text
IP 地址：192.168.127.2
子网掩码：255.255.255.0
默认网关：留空
DNS：留空
```

关键规则：

- 电脑 IP 和板端 IP 不能相同。
- 二者必须在同一网段。
- 直连开发链路不需要默认网关和 DNS。

## 5. 验证网络

Windows CMD 或 PowerShell：

```powershell
ping <BOARD_IP>
```

如果有回复，说明链路通。

进一步检查 SSH：

```powershell
Test-NetConnection <BOARD_IP> -Port 22
```

看到：

```text
TcpTestSucceeded : True
```

说明 SSH 端口可达。

## 6. 添加到 RDK Studio

打开 RDK Studio，添加新设备。

选择：

```text
SSH 网络连接
```

填写：

```text
IP：<BOARD_IP>
用户名：sunrise
密码：sunrise
```

连接成功后，RDK Studio 左侧会显示设备在线。

## 7. 这一步的成功判据

- Windows 能 `ping` 通板端 IP。
- Windows 能连通板端 22 端口。
- RDK Studio 能以 SSH 网络连接添加设备。
- RDK Studio 终端能进入板端 shell。

## 8. Agent 可验证项

烧录和接线需要人操作，agent 主要验证下面这些证据：

```bash
ifconfig -a
cat /etc/os-release | head
uname -a
```

Windows 侧：

```powershell
Test-NetConnection <BOARD_IP> -Port 22
```

期望：

```text
TcpTestSucceeded : True
```

## 9. 常见误区

- 网线接错口：本次跑通的是右侧网口，对应 `eth1`。
- Windows 网卡没有配静态 IP：只插线不配置同网段 IP，通常不能直接访问。
- 在 RDK Studio 里选错连接方式：这里应选 `SSH 网络连接`。
- 把电脑 IP 配成板端 IP：会冲突。
