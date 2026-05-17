# Skill: S100P 直连电脑网络链路

## 触发条件

用户已经烧录系统，需要把 S100P 加入 RDK Studio 或让 agent 通过 SSH 连接板卡。

## 前置条件

- S100P 已启动。
- 电脑和 S100P 用网线连接。
- 网线连接 S100P 右侧网口，对应 `eth1`。

## 流程

1. 用 MobaXterm 登录板卡。
2. 执行：

   ```bash
   ifconfig -a
   ```

3. 找到 `eth1` 的 IP，例如：

   ```text
   192.168.127.10
   ```

4. Windows 打开以太网 IPv4 设置。
5. 设置电脑网卡：

   ```text
   IP 地址：192.168.127.2
   子网掩码：255.255.255.0
   默认网关：留空
   DNS：留空
   ```

6. 测试：

   ```powershell
   ping 192.168.127.10
   Test-NetConnection 192.168.127.10 -Port 22
   ```

## 成功判据

- ping 有回复。
- SSH 22 端口可达。

## 失败处理

- ping 不通：检查是否接到右侧网口、电脑 IP 是否同网段。
- SSH 不通：确认板端 SSH 服务和 IP。
- RDK Studio 不通：确认 Studio 使用的是 `SSH 网络连接`。
