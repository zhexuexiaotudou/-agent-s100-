# Skill: RDK Studio 接入 S100P

## 触发条件

用户希望用 RDK Studio 管理 S100P，包括终端、文件、远程桌面和后续开发。

## 前置条件

- 电脑能 ping 通 S100P。
- SSH 端口 22 可达。
- 已知板端 IP。

## 添加设备

RDK Studio 添加新设备时选择：

```text
SSH 网络连接
```

填写：

```text
IP：192.168.127.10
用户名：sunrise
密码：sunrise
```

## 成功判据

- Studio 设备列表显示在线。
- Studio 终端能进入板端 shell。
- Studio 文件功能能看到 `/home/sunrise`。

## 远程桌面

RDK Studio 远程桌面依赖 VNC/x11vnc。

常见端口：

```text
5900
```

常见口令：

```text
88888888
```

如果黑屏或端口未就绪，优先不要阻塞 YOLO 任务，可以先用 HTTP 查看结果图。

检查：

```bash
ss -lntp | grep 5900
systemctl --user status x11vnc-s100p.service
```

重启：

```bash
systemctl --user restart x11vnc-s100p.service
```
