# Troubleshooting

## RDK Studio 添加设备失败

检查顺序：

1. 网线是否连接 S100P 右侧网口。
2. MobaXterm 中 `ifconfig -a` 是否能看到 `eth1` IP。
3. Windows 以太网 IPv4 是否配置到同一网段。
4. Windows 是否能 `ping <板端IP>`。
5. Windows 是否能 `Test-NetConnection <板端IP> -Port 22`。
6. RDK Studio 是否选择 `SSH 网络连接`。

## 板端没有外网

直连电脑时，Windows 给板卡配置的是同网段静态 IP，默认网关和 DNS 留空，所以板端没有外网是正常的。

如果需要安装包，可以：

- 临时给板端配置可上网网络。
- 或在电脑下载 arm64 包和 Python wheel 后传到板端离线安装。

## `ros2` 找不到

先执行：

```bash
source /opt/ros/humble/setup.bash
```

如果要使用 TogetheROS.Bot 包，再执行：

```bash
source /opt/tros/humble/setup.bash
```

## `dnn_node_example` 找不到

检查：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash
ros2 pkg prefix dnn_node_example
```

如果没有输出，说明示例包未安装或环境未 source。

## YOLO 配置文件找不到

安装版示例使用：

```text
config/yolov8workconfig.json
```

不要使用源码目录里的：

```text
config/s100/yolov8workconfig.json
```

## YOLO 结果图没更新

浏览器可能缓存旧图。建议每次复制为新文件名：

```bash
cp render_feedback_0_0.jpeg render_test2_result.jpeg
```

或在 URL 后加参数：

```text
http://192.168.127.10:9000/render_test2_result.jpeg?t=3
```

## RDK Studio 文件下载报 `atob`

这是 RDK Studio 前端文件下载/预览的编码问题，不代表 YOLO 失败。

替代方法：

```bash
cd ~/yolo_s100p_run
python3 -m http.server 9000 --bind 0.0.0.0
```

浏览器打开结果图。

## RDK Studio 远程桌面黑屏

黑屏不影响 YOLO。先用 HTTP 或 scp 查看结果图。

如果要修远程桌面，检查：

```bash
systemctl --user status x11vnc-s100p.service
ss -lntp | grep 5900
```

RDK Studio 默认 VNC 口令常用：

```text
88888888
```
