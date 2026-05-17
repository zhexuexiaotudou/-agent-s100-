# Skill: S100P 烧录系统

## 触发条件

用户要从零开始使用 S100P，或板卡系统不可用，需要重新烧录。

## 前置条件

- Windows 电脑
- S100P
- USB Type-C 线
- 官方 XBurn 工具
- 官方 S100 系列镜像

## 流程

1. 打开官方烧录教程。
2. 下载并安装 XBurn。
3. 将 S100P 通过 USB Type-C 连接电脑。
4. 进入官方要求的下载模式。
5. 在 XBurn 中选择 `DFU + Fastboot`。
6. 选择正确的 S100 系列镜像。
7. 开始烧录。
8. 等待完成并重启板卡。

## 成功判据

- XBurn 显示烧录完成。
- 板卡能启动。
- 后续能通过 MobaXterm 或串口/SSH 登录。

## 失败处理

- 电脑识别不到设备：检查 USB 线、驱动、下载模式。
- 烧录失败：重新进入下载模式，确认镜像和板卡型号。
- 烧录后无法启动：回到官方教程核对镜像版本。

## 官方参考

https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/install_os/rdk_s100/instruction
