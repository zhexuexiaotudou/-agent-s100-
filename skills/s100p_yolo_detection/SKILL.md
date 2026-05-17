# Skill: S100P YOLO 图片检测

## 触发条件

用户已经通过 SSH 或 RDK Studio 接入 S100P，希望在 S100P 上对本地图片运行 YOLO 检测。

## 不适用

需要实时摄像头流、模型训练、ONNX/PyTorch 直接推理或模型转换时，不使用本 skill。

## 前置条件

- `<BOARD_IP>` 可 SSH。
- ROS2 Humble 可用：`/opt/ros/humble`。
- TogetheROS.Bot 可用：`/opt/tros/humble`。
- `dnn_node_example` 可见。
- S100P BPU `.hbm` 模型存在。

## 变量

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `<YOLO_WORKDIR>` | `/home/sunrise/yolo_s100p_run` | 工作目录 |
| `<INPUT_IMAGE>` | `test.jpg` | 输入图片 |
| `<OUTPUT_IMAGE>` | `render_test_result.jpeg` | 输出结果 |
| `<CONFIG_FILE>` | `config/yolov8workconfig.json` | 安装版示例配置 |
| `<MODEL_FILE>` | `/opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm` | S100P BPU 模型 |

## 环境检查

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

ros2 pkg prefix dnn_node_example
ls -l <MODEL_FILE>
ls -l <YOLO_WORKDIR>/<INPUT_IMAGE>
ls -l <YOLO_WORKDIR>/<CONFIG_FILE>
```

期望：

- `ros2 pkg prefix dnn_node_example` 输出 `/opt/tros/humble`。
- 模型、图片、配置文件都存在。

## 准备工作目录

```bash
mkdir -p <YOLO_WORKDIR>
```

如果安装版示例第一次运行，会把 `config` 复制到当前目录。也可以先运行一次默认图，或确认：

```bash
ls <YOLO_WORKDIR>/config/yolov8workconfig.json
```

## 运行检测

推荐使用仓库脚本：

```bash
YOLO_WORKDIR=<YOLO_WORKDIR> bash scripts/run_yolo_image.sh <INPUT_IMAGE> <OUTPUT_IMAGE>
```

手工命令：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

cd <YOLO_WORKDIR>
timeout 25 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:=<CONFIG_FILE> \
  dnn_example_image:=<INPUT_IMAGE>

cp render_feedback_0_0.jpeg <OUTPUT_IMAGE>
```

## 成功判据

日志出现：

```text
out box size
Draw result to file: render_feedback_0_0.jpeg
```

结果图存在：

```bash
ls -l <YOLO_WORKDIR>/<OUTPUT_IMAGE>
```

## 查看结果

```bash
cd <YOLO_WORKDIR>
python3 -m http.server 9000 --bind 0.0.0.0
```

电脑浏览器：

```text
http://<BOARD_IP>:9000/<OUTPUT_IMAGE>
```

## 失败处理

| 现象 | 处理 |
| --- | --- |
| `ros2` 找不到 | 重新 source `/opt/ros/humble/setup.bash` |
| `dnn_node_example` 找不到 | 检查 `/opt/tros/humble` 和离线安装 |
| 配置文件缺失 | 使用安装版路径 `config/yolov8workconfig.json` |
| 模型缺失 | 检查 `hobot-models-basic` 或 `/opt/hobot/model/s100/basic` |
| 没有结果图 | 查看 `yolo_run.log` 或 ROS launch 日志 |
| HTTP 端口冲突 | 换端口，如 `python3 -m http.server 9001` |
| 浏览器旧图 | 换输出文件名或 URL 加 `?t=数字` |

## 下一步

把成功日志、输入图名、输出图名和检测类别记录回文档或 issue。
