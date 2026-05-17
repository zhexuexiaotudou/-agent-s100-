# 完全基于 agent 的 S100 使用和链路打通

这个仓库沉淀一套面向 RDK S100P 的 agent 工作流：从拿到板子、烧录系统、连接电脑和 RDK Studio，到使用 Codex 这类 agent 在 S100P 上跑通 YOLO 目标检测。

它不是官方文档的重复整理，而是“官方手册 + 本地实测 + agent 执行记录”的可复用知识库。

## 目标

- 让第一次接触 S100P 的用户能按步骤把板子接入电脑。
- 让 agent 能根据文档和脚本复现关键链路。
- 把易踩坑的网络、RDK Studio、远程桌面、YOLO 推理流程沉淀为可维护资产。

## 已跑通链路

1. 使用 XBurn 以 `DFU + Fastboot` 模式烧录 S100P 系统。
2. 用网线连接电脑和 S100P 右侧网口，也就是板端 `eth1`。
3. 用 MobaXterm 登录板子并通过 `ifconfig -a` 获取 `eth1` IP。
4. 在 Windows 上将对应以太网 IPv4 配置到 `192.168.127.x` 网段。
5. 在 RDK Studio 中用 `SSH 网络连接` 添加 S100P。
6. 通过 Codex/SSH 补齐 TogetheROS.Bot YOLO 示例环境。
7. 使用 `dnn_node_example` + S100P BPU `.hbm` 模型跑通 YOLOv8。
8. 通过 HTTP 或 RDK Studio 文件功能查看 `render_feedback_0_0.jpeg` 结果图。

## 仓库结构

```text
.
├─ README.md
├─ docs/
│  ├─ 01_s100p_bringup.md
│  ├─ 02_codex_yolo_workflow.md
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

## 快速开始

板卡和电脑直连后，先在 Windows PowerShell 检查网络：

```powershell
.\scripts\check_s100p_network.ps1 -BoardIp 192.168.127.10
```

在 S100P 上跑 YOLO：

```bash
bash scripts/run_yolo_image.sh test.jpg render_test_result.jpeg
```

从 Windows 拉取结果图：

```powershell
.\scripts\fetch_yolo_result.ps1 -BoardIp 192.168.127.10 -RemoteFile render_test_result.jpeg
```

## 官方参考

- S100 系列烧录教程：https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/install_os/rdk_s100/instruction
- 远程登录说明：https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/remote_login/
- hobot_dnn 仓库：https://github.com/D-Robotics/hobot_dnn

## 说明

本仓库记录的是一次真实跑通链路。不同系统镜像、RDK Studio 版本、网络拓扑和板端预装包可能存在差异。遇到差异时，优先保留成功日志和失败日志，再更新对应 skill。
