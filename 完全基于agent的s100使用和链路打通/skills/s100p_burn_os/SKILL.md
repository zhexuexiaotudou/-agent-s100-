# Skill: S100P 烧录系统

## 触发条件

用户拿到新的 S100P、系统不可用、或需要重新刷官方镜像。

## 不适用

板卡已经能 SSH 登录且 ROS/TROS 环境正常时，不要重复烧录。

## 前置条件

- RDK S100P 和电源。
- Windows 主机，有管理员权限。
- USB Type-C 线。
- 官方 XBurn 工具和 S100 系列镜像。
- 用户可执行物理接线和 GUI 点击。

## Agent 边界

agent 可以解释流程、核对官方页面、整理检查清单。XBurn GUI 操作、按键/接线/上电由用户完成。

## 变量

| 变量 | 说明 |
| --- | --- |
| `<IMAGE_FILE>` | 官方 S100 系列镜像 |
| `<XBURN_VERSION>` | XBurn 版本 |
| `<DOWNLOAD_MODE>` | 本次跑通为 `DFU + Fastboot` |

## 操作流程

1. 打开官方烧录教程。
2. 确认板卡型号和镜像匹配。
3. 用 USB Type-C 连接 S100P 和 Windows 主机。
4. 按官方说明进入下载模式。
5. 在 XBurn 中选择 `DFU + Fastboot`。
6. 选择 `<IMAGE_FILE>`。
7. 开始烧录并等待完成。
8. 重启板卡。

## 成功判据

烧录完成后，应能获得至少一项证据：

```bash
cat /etc/os-release | head
uname -a
ifconfig -a
```

期望：

- 系统能启动到登录提示。
- 默认用户可登录。
- 能看到网络接口，例如 `eth1`。

## 失败处理

| 现象 | 处理 |
| --- | --- |
| XBurn 识别不到设备 | 检查 USB 线、驱动、下载模式 |
| 烧录失败 | 重新进入下载模式，核对镜像和板卡型号 |
| 烧录后无法启动 | 回到官方教程核对镜像版本和烧录日志 |

## 下一步

进入 `s100p_network_link`，建立电脑到板卡的 SSH 网络链路。

## 官方参考

https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/install_os/rdk_s100/instruction
