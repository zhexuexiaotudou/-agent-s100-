# Skill: S100P YOLO 图片检测

## 触发条件

用户已经通过 SSH 或 RDK Studio 接入 S100P，希望在 S100P 上对本地图片运行 YOLO 检测。

## 前置条件

- ROS2 Humble 可用：`/opt/ros/humble`
- TogetheROS.Bot 可用：`/opt/tros/humble`
- `dnn_node_example` 可见
- S100P BPU 模型存在：

  ```text
  /opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm
  ```

## 环境检查

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

ros2 pkg prefix dnn_node_example
ls -l /opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm
```

## 运行检测

假设图片在：

```text
~/yolo_s100p_run/test.jpg
```

运行：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

cd ~/yolo_s100p_run
timeout 25 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:=config/yolov8workconfig.json \
  dnn_example_image:=test.jpg

cp render_feedback_0_0.jpeg render_test_result.jpeg
```

## 成功判据

日志出现：

```text
out box size
Draw result to file: render_feedback_0_0.jpeg
```

结果图存在：

```bash
ls -l render_test_result.jpeg
```

## 查看结果

启动 HTTP：

```bash
cd ~/yolo_s100p_run
python3 -m http.server 9000 --bind 0.0.0.0
```

电脑浏览器打开：

```text
http://192.168.127.10:9000/render_test_result.jpeg
```

## 注意

- 安装版配置使用 `config/yolov8workconfig.json`。
- 每次换图片建议使用新的输出文件名，避免浏览器缓存。
- 这个流程使用的是 Horizon BPU `.hbm` 模型，不是 PyTorch/ONNX 原生模型。
