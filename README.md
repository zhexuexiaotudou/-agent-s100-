# 完全基于 agent 的 S100 使用和链路打通

> Chinese-first documentation for an agent-driven RDK S100P bring-up workflow: flash OS, connect the board to a Windows host, add it to RDK Studio, and use Codex-like agents to run YOLO on the S100P BPU.

这个仓库沉淀一套面向 RDK S100P 的 agent 工作流：从拿到板子、烧录系统、连接电脑和 RDK Studio，到使用 Codex 这类 agent 在 S100P 上跑通 YOLO 目标检测。

它不是官方文档的重复整理，而是“官方手册 + 本地实测 + agent 执行记录”的可复用知识库。

## 如果你刚拿到 S100P

建议按下面的顺序使用这个 repo，不要一上来直接让 agent 跑 YOLO。

1. 先打开并阅读 [docs/01_s100p_bringup.md](docs/01_s100p_bringup.md)。
   这一步解决拿到板子后的基础问题：烧录系统、确认 `eth1` 网口、设置 Windows 静态 IP、确认电脑能 ping 通 S100P、确认 SSH 能连上。

2. 网络和 SSH 打通后，再把整个 repo 喂给 Codex。
   推荐把仓库作为 Codex 的工作目录打开，或者把下面这段话发给 Codex：

```text
请阅读这个 repo 的 README、docs/01_s100p_bringup.md、docs/02_codex_yolo_workflow.md、
docs/agent_operation.md 和 skills 目录。我的目标是从一块刚烧录好的 RDK S100P 开始，
打通电脑直连、RDK Studio 接入，并在 S100P 上用本地图片跑通 YOLO 目标检测。
请先检查当前处在哪一步，再按 repo 里的流程执行，不要跳过网络和 SSH 验证。
```

3. 如果已经能 SSH 到板子，再让 Codex 按 [docs/02_codex_yolo_workflow.md](docs/02_codex_yolo_workflow.md) 跑 YOLO。
   这一步会上传图片、在 S100P 上执行 YOLO、生成渲染结果图，并告诉你应该打开哪个结果网址。

4. 如果卡住，先查 [docs/troubleshooting.md](docs/troubleshooting.md)。
   排错时把错误截图、命令输出、板端 IP 和当前步骤告诉 Codex，让它按仓库里的检查项继续定位。

一句话版本：新手先读 `docs/01_s100p_bringup.md`，把网络和 SSH 打通；然后把整个 repo 交给 Codex，让 Codex 按文档和 `skills/` 目录继续执行。

## 状态和范围

状态：实验性，已在一台 RDK S100P 和一台 Windows 主机上跑通。

已覆盖：

- Windows 主机和 S100P 通过网线直连。
- S100P 右侧网口，也就是板端 `eth1`。
- RDK Studio 通过 SSH 网络连接添加设备。
- ROS2 Humble + TogetheROS.Bot `dnn_node_example`。
- S100P BPU `.hbm` YOLOv8 图片检测。

暂不覆盖：

- 摄像头实时流完整产品化部署。
- 自训练模型转换、量化和 `.hbm` 生成。
- 多板卡网络拓扑。
- 生产环境安全加固。

## 测试环境

| 项目 | 本次实测值 |
| --- | --- |
| 板卡 | RDK S100P |
| 板端系统 | Ubuntu 22.04.5 LTS |
| 架构 | aarch64 |
| ROS | ROS2 Humble, `/opt/ros/humble` |
| TogetheROS.Bot | `/opt/tros/humble` |
| Windows 侧工具 | PowerShell, MobaXterm, RDK Studio |
| 直连板端 IP 示例 | `192.168.127.10` |
| 电脑静态 IP 示例 | `192.168.127.2/24` |
| YOLO 模型 | `/opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm` |

文档中用 `<BOARD_IP>` 表示板端 IP。`192.168.127.10` 只是本次实测常见值。

## 安全提醒

- `sunrise/sunrise`、`root/root`、`88888888` 这类默认口令只适合本地实验室直连环境。
- 第一次跑通后应修改默认密码，或改用 SSH key。
- 不要把板卡暴露到不可信局域网。
- `python3 -m http.server --bind 0.0.0.0` 会在板端所有网卡上开放文件访问，用完应停止。

## 仓库结构

```text
.
├─ README.md
├─ CONTRIBUTING.md
├─ docs/
│  ├─ 01_s100p_bringup.md
│  ├─ 02_codex_yolo_workflow.md
│  ├─ 03_offline_tros_install.md
│  ├─ agent_operation.md
│  ├─ openclaw_s100p_nas_baseline.md
│  ├─ baseline_tracking.md
│  ├─ pro_model_handoff.md
│  ├─ security_model.md
│  ├─ review_checklist.md
│  └─ troubleshooting.md
├─ skills/
│  ├─ s100p_burn_os/SKILL.md
│  ├─ s100p_network_link/SKILL.md
│  ├─ s100p_rdk_studio/SKILL.md
│  └─ s100p_yolo_detection/SKILL.md
└─ scripts/
   ├─ check_s100p_network.ps1
   ├─ run_yolo_image.sh
   └─ fetch_yolo_result.ps1
```

## OpenClaw + NAS Baseline

S100P 跑通基础链路后，下一阶段目标是把它作为 OpenClaw 主上位机，并把 TS-264C NAS 作为 workspace、memory、logs、数据集和备份中心。

这部分按两个角度建立 baseline：

1. S100P 能否实现 PC 上 OpenClaw 的类似效果。
2. 高价位 AI NAS / OpenClaw NAS 的产品功能，哪些可以用 S100P + TS-264C 抄作业。

入口文档：

- [docs/openclaw_s100p_nas_baseline.md](docs/openclaw_s100p_nas_baseline.md)：baseline 定义和落地顺序。
- [docs/baseline_tracking.md](docs/baseline_tracking.md)：Codex 跟踪任务矩阵。
- [docs/security_model.md](docs/security_model.md)：Gateway、NAS、token、机器人控制的安全边界。
- [docs/pro_model_handoff.md](docs/pro_model_handoff.md)：给 GPT Pro 做阶段性复审的提示词模板。

协作方式：

- Codex 负责实机执行、GitHub issue、脚本、文档和证据。
- GPT Pro 负责阶段性架构复审、baseline 拆分和高风险判断。
- Pro 的建议必须由 Codex 实测或标记为假设后才能写入稳定 baseline。

## 复现路径

### 1. 烧录系统

执行位置：Windows 主机 + S100P 物理操作。

按官方教程使用 XBurn，以 `DFU + Fastboot` 模式烧录 S100P 系统：

[S100 系列烧录教程](https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/install_os/rdk_s100/instruction)

详细沉淀见：[docs/01_s100p_bringup.md](docs/01_s100p_bringup.md)。

### 2. 打通电脑和 S100P 网络

执行位置：Windows 主机。

用网线连接电脑和 S100P 右侧网口。通过 MobaXterm 或串口进入板端，执行：

```bash
ifconfig -a
```

记录 `eth1` 的 IP，例如 `<BOARD_IP>=192.168.127.10`。

Windows 以太网 IPv4 示例：

```text
IP 地址：192.168.127.2
子网掩码：255.255.255.0
默认网关：留空
DNS：留空
```

检查网络：

```powershell
.\scripts\check_s100p_network.ps1 -BoardIp <BOARD_IP>
```

成功判据：

```text
Ping: OK
TcpTestSucceeded : True
```

### 3. 加入 RDK Studio

执行位置：RDK Studio。

添加设备时选择：

```text
SSH 网络连接
```

填写 `<BOARD_IP>`、板端用户名和密码。成功后 RDK Studio 能打开终端和文件。

### 4. 用 agent 跑 YOLO

执行位置：S100P 板端。

把 `scripts/run_yolo_image.sh` 复制到 S100P，或者在板端 clone 本仓库。假设图片在：

```text
/home/sunrise/yolo_s100p_run/test.jpg
```

运行：

```bash
bash scripts/run_yolo_image.sh test.jpg render_test_result.jpeg
```

脚本默认工作目录：

```text
/home/sunrise/yolo_s100p_run
```

可通过环境变量覆盖：

```bash
YOLO_WORKDIR=/home/sunrise/yolo_s100p_run \
YOLO_LAUNCH_TIMEOUT=25 \
bash scripts/run_yolo_image.sh test.jpg render_test_result.jpeg
```

### 5. 查看结果

执行位置：S100P 板端启动服务，Windows 浏览器查看。

```bash
cd /home/sunrise/yolo_s100p_run
python3 -m http.server 9000 --bind 0.0.0.0
```

浏览器打开：

```text
http://<BOARD_IP>:9000/render_test_result.jpeg
```

或从 Windows 拉取：

```powershell
.\scripts\fetch_yolo_result.ps1 -BoardIp <BOARD_IP> -RemoteFile render_test_result.jpeg
```

## Agent 工作方式

本仓库把经验拆成 4 个可复用 skill：

1. `s100p_burn_os`：烧录系统。
2. `s100p_network_link`：电脑和板卡直连网络。
3. `s100p_rdk_studio`：RDK Studio 接入。
4. `s100p_yolo_detection`：上传图片、运行 YOLO、查看结果。

agent 每次执行后应记录：

- 使用的板端 IP、系统版本和 RDK Studio 版本。
- 执行命令。
- 成功或失败日志。
- 结果图路径和浏览器 URL。
- 对 repo 文档或脚本的改进建议。

详细 agent 操作边界见：[docs/agent_operation.md](docs/agent_operation.md)。

## 官方参考

- [S100 系列烧录教程](https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/install_os/rdk_s100/instruction)
- [远程登录说明](https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/remote_login/)
- [D-Robotics/hobot_dnn](https://github.com/D-Robotics/hobot_dnn)

## 贡献

提交 issue 或 PR 时，请附上：

- 板卡型号和镜像版本。
- RDK Studio 版本。
- 主机系统和网络配置。
- 完整命令。
- 关键日志。
- 结果图或失败截图。

License: MIT.
