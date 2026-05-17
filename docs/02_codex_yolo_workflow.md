# 02. 使用 Codex 在 S100P 上跑通 YOLO

本文记录本次实际由 Codex agent 在 S100P 上跑通 YOLO 的过程。

## 1. 前置条件

电脑和 S100P 已经通过网线直连，并且 SSH 可用：

```text
S100P IP：<BOARD_IP>，本次实测常见值为 `192.168.127.10`
用户名：<BOARD_USER>，本次实测为 `sunrise`
密码：默认口令仅用于首次本地实验，跑通后应修改或改用 SSH key
```

Windows 侧验证：

```powershell
Test-NetConnection <BOARD_IP> -Port 22
```

## 2. Codex 做的第一轮探测

Codex 先通过 SSH 检查系统：

```bash
hostname
uname -a
cat /etc/os-release
```

实测结果：

```text
Ubuntu 22.04.5 LTS
aarch64
```

然后检查 ROS2：

```bash
ls -ld /opt/ros /opt/ros/humble
source /opt/ros/humble/setup.bash
which ros2
```

结论：

- 板上有 ROS2 Humble：`/opt/ros/humble`
- 一开始没有完整的 `/opt/tros/humble` 示例环境

## 3. 检查模型文件

Codex 检查 S100P 预置模型：

```bash
find /opt/hobot/model /app/model -maxdepth 5 -type f 2>/dev/null | grep -Ei "yolo|hbm|hbmodel|bin"
```

确认存在：

```text
/opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm
/opt/hobot/model/s100/basic/yolov10_640x640_nv12.hbm
/opt/hobot/model/s100/basic/yolo11m_detect_nashe_640x640_nv12.hbm
```

本次使用：

```text
/opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm
```

## 4. 补齐 TogetheROS.Bot YOLO 示例环境

板端直连电脑时没有默认网关和 DNS，无法直接从板端 apt 拉包。因此 Codex 使用电脑下载官方 arm64 包，再传到 S100P 离线安装。

可复现的离线安装步骤见：[03. 离线补齐 TogetheROS.Bot YOLO 示例环境](03_offline_tros_install.md)。

关键包包括：

```text
tros-humble-dnn-node-example
tros-humble-dnn-node
tros-humble-ai-msgs
tros-humble-hbm-img-msgs
tros-humble-hobot-cv
tros-humble-websocket
hobot-dnn
```

安装过程中 `hobot-dnn` 的 postinst 会构建 Python 扩展，需要离线补齐 Python wheel：

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

还遇到过一次系统时间导致的 ninja 错误：

```text
ninja: error: manifest 'build.ninja' still dirty after 100 tries, perhaps system time is not set
```

修复方法是把板端时间同步到电脑当前时间：

```bash
sudo date -s "YYYY-MM-DD HH:MM:SS"
```

完成后确认 ROS 包可见：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

for p in dnn_node_example dnn_node ai_msgs hbm_img_msgs hobot_cv websocket; do
  printf "$p="
  ros2 pkg prefix $p 2>/dev/null || echo MISSING
done
```

成功结果应类似：

```text
dnn_node_example=/opt/tros/humble
dnn_node=/opt/tros/humble
ai_msgs=/opt/tros/humble
hbm_img_msgs=/opt/tros/humble
hobot_cv=/opt/tros/humble
websocket=/opt/tros/humble
```

## 5. 首次跑 YOLOv8

创建运行目录：

```bash
mkdir -p ~/yolo_s100p_run
cd ~/yolo_s100p_run
```

启动环境：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash
```

运行官方安装版示例包：

```bash
ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:=config/yolov8workconfig.json \
  dnn_example_image:=config/target.jpg
```

注意：安装版配置目录是扁平结构，使用：

```text
config/yolov8workconfig.json
config/target.jpg
```

不要写成源码仓库里的：

```text
config/s100/yolov8workconfig.json
config/common/target.jpg
```

## 6. 成功日志

跑通时日志中会出现：

```text
model_file_name: /opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm
name: yolov8n_640x640_nv12
Dnn node feed with local image
out box size
Draw result to file: render_feedback_0_0.jpeg
```

一次默认图检测结果包括：

```text
potted plant
couch
vase
book
```

这说明：

- BPU 模型加载成功
- 本地图片回灌成功
- YOLO 后处理成功
- 检测框渲染成功

## 7. 查看结果图

结果图在运行目录：

```text
~/yolo_s100p_run/render_feedback_0_0.jpeg
```

在 S100P 上启动 HTTP 服务：

```bash
cd ~/yolo_s100p_run
python3 -m http.server 9000 --bind 0.0.0.0
```

电脑浏览器打开：

```text
http://<BOARD_IP>:9000/render_feedback_0_0.jpeg
```

如果为了避免缓存，可以复制成新的文件名：

```bash
cp render_feedback_0_0.jpeg render_test_result.jpeg
```

然后打开：

```text
http://<BOARD_IP>:9000/render_test_result.jpeg
```

`--bind 0.0.0.0` 只建议用于本地直连实验。用完后停止 HTTP 服务。

## 8. 跑用户上传图片

如果用户把图片上传到：

```text
~/yolo_s100p_run/test2.jpg
```

运行：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

cd ~/yolo_s100p_run
timeout 25 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:=config/yolov8workconfig.json \
  dnn_example_image:=test2.jpg

cp render_feedback_0_0.jpeg render_test2_result.jpeg
```

查看：

```text
http://<BOARD_IP>:9000/render_test2_result.jpeg
```

本次 `test2.jpg` 实测检测到：

```text
person  0.943509
tie     0.391805
laptop  0.351481
tie     0.277876
```

## 9. Agent 执行原则

Codex 这类 agent 在 S100P 上执行任务时，应遵循：

1. 先检查网络和 SSH。
2. 再检查 ROS2/TROS 环境。
3. 再检查模型文件。
4. 再运行最小闭环示例。
5. 以日志和输出文件作为成功判据。
6. 每次换输入图片，都生成新的结果文件名，避免浏览器缓存误导。

## 10. 最小可复用命令

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

cd ~/yolo_s100p_run
timeout 25 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:=config/yolov8workconfig.json \
  dnn_example_image:=test.jpg

cp render_feedback_0_0.jpeg render_test_result.jpeg
```

浏览器：

```text
http://<BOARD_IP>:9000/render_test_result.jpeg
```

## 11. 脚本化工作流

Windows 侧检查网络：

```powershell
.\scripts\check_s100p_network.ps1 -BoardIp <BOARD_IP>
```

把待检测图片上传到板端：

```powershell
scp .\test.jpg sunrise@<BOARD_IP>:/home/sunrise/yolo_s100p_run/test.jpg
```

板端运行：

```bash
cd <repo>
bash scripts/run_yolo_image.sh test.jpg render_test_result.jpeg
```

Windows 侧拉取：

```powershell
.\scripts\fetch_yolo_result.ps1 -BoardIp <BOARD_IP> -RemoteFile render_test_result.jpeg -Force
```
