# Skill: S100P 直连电脑网络链路

## 触发条件

用户已经烧录并启动 S100P，需要让 Windows 主机、RDK Studio 或 agent 通过 SSH 连接板卡。

## 不适用

板卡已经可通过 SSH 稳定访问时，不要重复修改 Windows 网卡。

## 前置条件

- S100P 已启动。
- 电脑和 S100P 用网线连接。
- 本次实测连接 S100P 右侧网口，对应板端 `eth1`。
- 用户允许修改 Windows 对应以太网适配器 IPv4。

## Agent 边界

agent 可以检查 Windows 网络、指导用户记录原配置、执行 PowerShell 检查。物理接线和 GUI 网络设置需用户确认后进行。

## 变量

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `<BOARD_IP>` | `192.168.127.10` | S100P `eth1` IP |
| `<HOST_IP>` | `192.168.127.2` | Windows 直连网卡静态 IP |
| `<BOARD_USER>` | `sunrise` | 板端用户 |

## 获取板端 IP

优先路径：

```bash
ifconfig -a
```

找到 `eth1` 的 IP。

如果 SSH 还不可用，可选路径：

- 用 MobaXterm 串口/烧录后控制台进入板卡。
- 尝试官方默认直连 IP：`192.168.127.10`。
- Windows 侧查看 ARP：

  ```powershell
  arp -a
  ```

## Windows 网卡配置

修改前记录当前网卡配置：

```powershell
Get-NetIPConfiguration
```

GUI 配置：

```text
IP 地址：<HOST_IP>
子网掩码：255.255.255.0
默认网关：留空
DNS：留空
```

## 验证

```powershell
ping <BOARD_IP>
Test-NetConnection <BOARD_IP> -Port 22
```

期望：

```text
TcpTestSucceeded : True
```

也可以运行仓库脚本：

```powershell
.\scripts\check_s100p_network.ps1 -BoardIp <BOARD_IP>
```

## 恢复 Windows 网卡

如果该以太网口之后要恢复普通联网，把 IPv4 改回自动获取。修改前保存的 `Get-NetIPConfiguration` 输出用于核对。

## 失败处理

| 现象 | 处理 |
| --- | --- |
| ping 不通 | 检查是否接右侧网口、Windows IP 是否同网段 |
| SSH 不通 | 检查 `<BOARD_IP>` 是否正确，确认板端 SSH 服务 |
| RDK Studio 不通 | 确认 Studio 选择 `SSH 网络连接` |

## 下一步

进入 `s100p_rdk_studio` 或 `s100p_yolo_detection`。
