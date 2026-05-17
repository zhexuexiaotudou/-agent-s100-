# Skill: RDK Studio 接入 S100P

## 触发条件

用户希望用 RDK Studio 管理 S100P，包括终端、文件、代码编辑和远程桌面。

## 不适用

只需要命令行 SSH 跑 YOLO 时，可以直接进入 `s100p_yolo_detection`。

## 前置条件

- `<BOARD_IP>` 已知。
- Windows 能 ping 通 S100P。
- SSH 端口 22 可达。

## 变量

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `<BOARD_IP>` | `192.168.127.10` | 板端 IP |
| `<BOARD_USER>` | `sunrise` | 板端用户 |
| `<BOARD_PASSWORD>` | 默认口令仅用于首次本地实验 | 建议跑通后修改 |
| `<VNC_PORT>` | `5900` | RDK Studio 远程桌面常用端口 |
| `<VNC_PASSWORD>` | `88888888` | 实验口令，需按实际配置确认 |

## 添加设备

RDK Studio 添加新设备时选择：

```text
SSH 网络连接
```

填写 `<BOARD_IP>`、`<BOARD_USER>` 和实际密码。

## 成功判据

- Studio 设备列表显示在线。
- Studio 终端能进入板端 shell。
- Studio 文件功能能看到 `/home/<BOARD_USER>`。

## 可选：远程桌面

远程桌面是 RDK Studio 接入后的可选功能，不应阻塞 YOLO 命令行流程。

检查 VNC：

```bash
ss -lntp | grep <VNC_PORT>
```

期望看到监听。

如果使用 `x11vnc-s100p.service`：

```bash
systemctl --user status x11vnc-s100p.service
systemctl --user restart x11vnc-s100p.service
```

## 失败处理

| 现象 | 处理 |
| --- | --- |
| Studio 添加失败 | 回到 `s100p_network_link` 检查 ping 和 22 端口 |
| 远程桌面黑屏 | 不阻塞 YOLO，先用 HTTP 或 scp 查看结果图 |
| 5900 未就绪 | 检查 VNC/x11vnc 是否启动 |

## 下一步

进入 `s100p_yolo_detection`，上传图片并运行 YOLO。
