# 03. 离线补齐 TogetheROS.Bot YOLO 示例环境

本次实践中，S100P 通过网线直连 Windows 主机后没有默认网关和 DNS，因此板端不能直接 `apt install`。Codex 采用的办法是：电脑下载官方 arm64 包和 Python wheel，再传到板端离线安装。

如果你的板端已经能访问互联网，可以优先使用官方 apt 安装方式。本文件记录的是离线链路。

## 1. 目标

让以下 ROS 包在板端可见：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

ros2 pkg prefix dnn_node_example
ros2 pkg prefix dnn_node
ros2 pkg prefix ai_msgs
ros2 pkg prefix hbm_img_msgs
ros2 pkg prefix hobot_cv
ros2 pkg prefix websocket
```

期望都输出：

```text
/opt/tros/humble
```

## 2. 官方包源

本次实测使用的 S100 apt 包索引：

```text
http://archive.d-robotics.cc/ubuntu-rdk-s100-beta/dists/jammy/main/binary-arm64/Packages.gz
```

目标架构：

```text
arm64
```

## 3. 关键 deb 包

本次离线安装涉及：

```text
hobot-dnn
tros-humble-ros-workspace
tros-humble-ai-msgs
tros-humble-hbm-img-msgs
tros-humble-img-msgs
tros-humble-hobot-cv
tros-humble-hobot-codec
tros-humble-hobot-image-publisher
tros-humble-hobot-usb-cam
tros-humble-mipi-cam
tros-humble-websocket
tros-humble-dnn-node
tros-humble-dnn-node-example
```

注意：版本可能随官方源变化。开源复现时应记录实际下载版本。

## 4. Python wheel

`hobot-dnn` 安装脚本会构建 Python 扩展。离线环境需要提前准备：

```text
pybind11
scikit-build-core
packaging
pathspec
exceptiongroup
typing_extensions
tomli
ninja
```

`ninja` 需要 Linux aarch64 wheel。Windows 主机下载时应指定平台，例如：

```powershell
py -m pip download --dest .\s100_wheels --only-binary=:all: --platform manylinux2014_aarch64 --python-version 310 --implementation cp --abi cp310 ninja
```

纯 Python 包可以直接下载：

```powershell
py -m pip download --dest .\s100_wheels pybind11 scikit-build-core packaging pathspec exceptiongroup typing_extensions
py -m pip download --dest .\s100_wheels --only-binary=:all: --platform any --python-version 310 --implementation py --abi none tomli
```

## 5. 传输到板端

```powershell
scp .\s100_debs\*.deb sunrise@<BOARD_IP>:/tmp/s100_debs/
scp .\s100_wheels\*.whl sunrise@<BOARD_IP>:/tmp/s100_wheels/
```

如果目录不存在：

```powershell
ssh sunrise@<BOARD_IP> "mkdir -p /tmp/s100_debs /tmp/s100_wheels"
```

## 6. 安装

板端执行：

```bash
sudo dpkg -i /tmp/s100_debs/*.deb
```

如果 `hobot-dnn` 因 pip 离线依赖失败，执行：

```bash
sudo env PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/s100_wheels DEBIAN_FRONTEND=noninteractive dpkg --configure -a
```

如果出现：

```text
ninja: error: manifest 'build.ninja' still dirty after 100 tries, perhaps system time is not set
```

先同步板端时间：

```bash
sudo date -s "YYYY-MM-DD HH:MM:SS"
```

再重试：

```bash
sudo env PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/s100_wheels DEBIAN_FRONTEND=noninteractive dpkg --configure -a
```

## 7. 验证

```bash
dpkg -l | grep -E "hobot-dnn|tros-humble-dnn-node"
dpkg --audit
```

期望没有未配置的 `hobot-dnn`、`tros-humble-dnn-node`、`tros-humble-dnn-node-example`。

再检查 ROS 包：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

for p in dnn_node_example dnn_node ai_msgs hbm_img_msgs hobot_cv websocket; do
  printf "$p="
  ros2 pkg prefix "$p" 2>/dev/null || echo MISSING
done
```

期望：

```text
dnn_node_example=/opt/tros/humble
dnn_node=/opt/tros/humble
ai_msgs=/opt/tros/humble
hbm_img_msgs=/opt/tros/humble
hobot_cv=/opt/tros/humble
websocket=/opt/tros/humble
```
