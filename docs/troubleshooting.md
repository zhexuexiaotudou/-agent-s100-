# Troubleshooting

## 快速排障表

| 现象 | 可能原因 | 检查命令 | 期望输出 | 修复动作 |
| --- | --- | --- | --- | --- |
| RDK Studio 添加设备失败 | 网线接错口或 Windows IP 不在同一网段 | `ping <BOARD_IP>` | 有回复 | 确认连接 S100P 右侧 `eth1`，Windows IPv4 配到 `192.168.127.x/24` |
| ping 通但 SSH 不通 | SSH 服务或 IP 错误 | `Test-NetConnection <BOARD_IP> -Port 22` | `TcpTestSucceeded : True` | 确认板端 IP，必要时重启板端或检查 ssh 服务 |
| 板端不能 apt install | 直连网络没有网关/DNS | `ip route`、`cat /etc/resolv.conf` | 可能没有默认路由 | 使用离线安装，见 `docs/03_offline_tros_install.md` |
| `ros2` 找不到 | 未 source ROS 环境 | `which ros2` | `/opt/ros/humble/bin/ros2` | `source /opt/ros/humble/setup.bash` |
| `dnn_node_example` 找不到 | TROS 示例包未安装或未 source | `ros2 pkg prefix dnn_node_example` | `/opt/tros/humble` | 安装/修复 TROS，执行 `source /opt/tros/humble/setup.bash` |
| YOLO 配置文件找不到 | 使用了源码仓库路径而不是安装版路径 | `ls config/yolov8workconfig.json` | 文件存在 | 安装版使用 `config/yolov8workconfig.json` |
| YOLO 无结果图 | 输入图片、模型或 launch 失败 | `tail -n 120 yolo_run.log` | 出现模型加载和 `Draw result` | 检查图片路径、模型文件、ROS 包 |
| 浏览器显示旧图 | 浏览器缓存 | URL 后加 `?t=数字` | 新图片显示 | 每次输出新文件名，例如 `render_test2_result.jpeg` |
| RDK Studio 文件下载报 `atob` | Studio 前端下载/预览编码问题 | 无 | YOLO 文件本身仍存在 | 用 HTTP 服务或 `scp` 获取结果图 |
| RDK Studio 远程桌面黑屏 | VNC/RDP 画面服务问题 | `ss -lntp \| grep 5900` | 5900 有监听 | 不阻塞 YOLO，先用 HTTP 看图；必要时重启 x11vnc |

## HTTP 查看结果图

板端：

```bash
cd /home/sunrise/yolo_s100p_run
python3 -m http.server 9000 --bind 0.0.0.0
```

电脑浏览器：

```text
http://<BOARD_IP>:9000/render_test_result.jpeg
```

安全提醒：这个 HTTP 服务只适合本地直连实验，用完后停止。

## RDK Studio 远程桌面

RDK Studio 远程桌面依赖 VNC/x11vnc。默认端口常见为：

```text
5900
```

常见实验口令：

```text
88888888
```

检查：

```bash
systemctl --user status x11vnc-s100p.service
ss -lntp | grep 5900
```

重启：

```bash
systemctl --user restart x11vnc-s100p.service
```
