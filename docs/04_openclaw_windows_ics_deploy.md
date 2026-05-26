# S100P 通过 Windows 共享网络部署 OpenClaw 实战记录

日期：2026-05-27

目标：在 RDK S100P 上通过 RDK Studio 部署 OpenClaw。

背景：S100P 无法直接稳定接入校园网，因此采用“Windows 电脑联网，S100P 通过网线直连电脑，并使用 Windows Internet 连接共享上网”的方案。

## 1. 初始问题：RDK Studio 显示设备离线

重新给 S100P 上电并连接网线后，RDK Studio 里设备显示：

```text
root@192.168.127.10:22 离线
```

电脑侧检查发现，当时电脑以太网没有处在 S100P 所在网段，而是类似：

```text
169.254.x.x
```

因此无法访问：

```text
192.168.127.10
```

处理方法是把 Windows 连接 S100P 的有线网卡手动配置为：

```text
IP 地址：192.168.127.2
子网掩码：255.255.255.0
默认网关：留空
DNS：留空
```

然后测试：

```powershell
ping 192.168.127.10
Test-NetConnection 192.168.127.10 -Port 22
```

确认 S100P 的 SSH 能通。

## 2. OpenClaw 部署失败：缺少 Node/NPM

在 RDK Studio 的 OpenClaw 页面点击部署后，诊断日志显示：

```text
node: command not found
npm: command not found
openclaw-gateway.service could not be found
```

判断结果：

- `openclaw-gateway.service could not be found` 是结果，不是根因。
- 根因是 S100P 板端缺少 `node` 和 `npm`。
- RDK Studio 负责最终部署 OpenClaw，但前提是板端依赖要满足。

## 3. 选择网络方案：Windows 电脑做网关

因为 S100P 不方便直接接入校园网，也不能长期依赖手机热点，所以选择：

```text
电脑连接校园网/Wi-Fi
电脑以太网直连 S100P
Windows 开启 Internet 连接共享
S100P 通过电脑上网
```

一开始尝试过 PowerShell 的 `New-NetNat` 方案，但当前 Windows 环境报错：

```text
HRESULT 0x80041010
```

所以改用 Windows 图形界面的 Internet 连接共享。

## 4. 开启 Windows Internet 连接共享

在 Windows 中打开：

```text
控制面板
-> 网络和 Internet
-> 网络和共享中心
-> 更改适配器设置
```

选择正在上网的网卡，例如：

```text
WLAN
```

进入：

```text
属性 -> 共享
```

勾选：

```text
允许其他网络用户通过此计算机的 Internet 连接来连接
```

家庭网络连接选择连接 S100P 的有线网卡：

```text
以太网
```

开启后，Windows 把有线网卡改成：

```text
192.168.137.1
```

## 5. 通过 COM6 串口进入 S100P

由于开启 Windows 网络共享后，原来的：

```text
192.168.127.10
```

会失效，所以需要用 Type-C/USB 串口兜底进入 S100P。

本次 Windows 上识别到多个 CH340 串口，最终使用：

```text
COM6
Speed: 921600
Flow control: none
```

排查经验：

- 有的串口只能看到早期启动日志，不能登录。
- 如果提示 `Access denied`，通常是 RDK Studio 或 MobaXterm 占用了串口，需要关闭相关窗口后重试。
- 正确的 Linux 控制台会出现 Ubuntu 启动日志和登录提示。

最终通过 COM6 串口登录到 S100P 的 root shell。

## 6. 修改 S100P 网络到 Windows 共享网段

在 S100P 串口终端中执行：

```bash
ip addr flush dev eth1
ip addr add 192.168.137.10/24 dev eth1
ip link set eth1 up
ip route replace default via 192.168.137.1
echo "nameserver 223.5.5.5" > /etc/resolv.conf
```

然后测试：

```bash
ping -c 3 192.168.137.1
ping -c 3 8.8.8.8
ping -c 3 baidu.com
```

三项均成功：

```text
192.168.137.1 通：S100P 能到电脑
8.8.8.8 通：S100P 能出外网
baidu.com 通：DNS 正常
```

说明 S100P 已经通过 Windows 电脑成功上网。

## 7. 安装 Node/NPM 时遇到的问题

先尝试使用 apt 安装：

```bash
apt update
apt install -y nodejs npm
```

安装后 `npm` 能显示版本，但 `node` 出现异常：

```text
Fatal process OOM in insufficient memory to create an Isolate
Trace/breakpoint trap (core dumped)
```

检查内存后发现 S100P 内存充足：

```text
Mem: 21G
available: 19G
```

因此判断不是实际内存不足，而是系统源里的 Node 12 与当前 S100P 环境存在兼容问题。

## 8. 放弃板端 curl，改用电脑下载 Node arm64 包

尝试在板端执行：

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x -o /tmp/setup_node18.sh
```

出现卡住不动的问题。

因此改用更稳定的方案：

```text
电脑下载 Node.js Linux arm64 tarball
再传到 S100P
```

下载包：

```text
node-v20.19.2-linux-arm64.tar.xz
```

上传到 S100P：

```text
/root/node-v20.19.2-linux-arm64.tar.xz
```

## 9. 在 S100P 手动安装 Node 20

在 S100P 上执行：

```bash
cd /root
tar -xf node-v20.19.2-linux-arm64.tar.xz -C /opt
ln -sf /opt/node-v20.19.2-linux-arm64/bin/node /usr/local/bin/node
ln -sf /opt/node-v20.19.2-linux-arm64/bin/npm /usr/local/bin/npm
ln -sf /opt/node-v20.19.2-linux-arm64/bin/npx /usr/local/bin/npx
```

第一次执行 `node -v` 时仍然报：

```text
/usr/bin/node: No such file or directory
```

原因是 `$PATH` 中 `/usr/bin` 优先于 `/usr/local/bin`，系统仍然先找旧的 `/usr/bin/node`。

修复方法：

```bash
rm -f /usr/bin/node /usr/bin/npm /usr/bin/npx
ln -sf /opt/node-v20.19.2-linux-arm64/bin/node /usr/bin/node
ln -sf /opt/node-v20.19.2-linux-arm64/bin/npm /usr/bin/npm
ln -sf /opt/node-v20.19.2-linux-arm64/bin/npx /usr/bin/npx
hash -r
```

验证：

```bash
which node
node -v
which npm
npm -v
```

最终 `node -v` 成功，Node/NPM 依赖修复完成。

## 10. 重新连接 RDK Studio

由于当前 S100P 的 IP 已变成：

```text
192.168.137.10
```

所以 RDK Studio 里原来的设备：

```text
root@192.168.127.10:22
```

不能再用。

需要重新添加设备：

```text
连接方式：SSH 网络连接
IP：192.168.137.10
端口：22
用户名：root
密码：root 密码
```

电脑侧验证：

```powershell
ping 192.168.137.10
Test-NetConnection 192.168.137.10 -Port 22
```

确认 SSH 端口可达后，在 RDK Studio 中重新连接设备。

## 11. 最终部署 OpenClaw

回到 RDK Studio 的 OpenClaw 页面，重新点击部署。

部署前提已满足：

```text
S100P 能上网
node -v 正常
npm -v 正常
RDK Studio 能通过 192.168.137.10:22 连接板子
```

最终 RDK Studio 页面显示 OpenClaw 部署成功。

## 12. 本次经验总结

关键结论：

1. S100P 不一定能直接接入校园网。
2. Windows 电脑可以作为临时网关，让 S100P 通过电脑上网。
3. 开启 Windows 网络共享后，S100P 的连接网段会从 `192.168.127.x` 变成 `192.168.137.x`。
4. RDK Studio 设备 IP 也要同步改成 `192.168.137.10`。
5. USB 串口是网络改坏时的兜底入口，本次使用 `COM6`。
6. S100P 上 apt 源里的 Node 12 可能不稳定。
7. 对 OpenClaw 来说，更稳的做法是安装 Node.js 官方 Linux arm64 tarball。
8. RDK Studio 仍然是部署 OpenClaw 的主入口，不建议绕开它手工部署 OpenClaw。
9. Codex 的作用是诊断链路、记录过程、修正依赖、沉淀文档；RDK Studio 负责最终 OpenClaw 安装部署。
