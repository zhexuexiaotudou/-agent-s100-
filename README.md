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
│  ├─ 04_openclaw_windows_ics_deploy.md
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
   ├─ run_allowlisted_tool.sh
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
- [docs/nas_workspace_spec.md](docs/nas_workspace_spec.md)：TS-264C 专用 workspace 目录规范和验收命令。
- [docs/nas_mount_runbook.md](docs/nas_mount_runbook.md)：TS-264C 挂载到 S100P 的预检、挂载和自动恢复流程。
- [docs/tool_allowlist.md](docs/tool_allowlist.md)：OpenClaw 可触发脚本的白名单边界。
- [docs/document_index_runbook.md](docs/document_index_runbook.md)：NAS 文档索引的白名单执行流程。
- [docs/security_model.md](docs/security_model.md)：Gateway、NAS、token、机器人控制的安全边界。
- [docs/pro_model_handoff.md](docs/pro_model_handoff.md)：给 GPT Pro 做阶段性复审的提示词模板。
- [docs/github_issue_seed.md](docs/github_issue_seed.md)：GitHub issue 顶层入口草稿。
- [docs/04_openclaw_windows_ics_deploy.md](docs/04_openclaw_windows_ics_deploy.md)：Windows 共享网络部署 OpenClaw 的实战记录。

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

## 2026-05-27 Baseline Additions

New OpenClaw + NAS baseline artifacts:

- [docs/ros2_status_runbook.md](docs/ros2_status_runbook.md): read-only ROS2/TROS status probe workflow.
- [docs/baseline_progress_2026-05-27_ros2_status.md](docs/baseline_progress_2026-05-27_ros2_status.md): board validation evidence for A-008.
- [docs/openclaw_exec_approvals_runbook.md](docs/openclaw_exec_approvals_runbook.md): OpenClaw exec approvals policy for A-005.
- [docs/baseline_progress_2026-05-27_exec_policy.md](docs/baseline_progress_2026-05-27_exec_policy.md): A-005 positive and negative validation evidence.
- [docs/baseline_status_runbook.md](docs/baseline_status_runbook.md): roll-up status report workflow for both baseline tracks.
- [docs/baseline_progress_2026-05-27_baseline_status.md](docs/baseline_progress_2026-05-27_baseline_status.md): status dashboard progress evidence.
- [docs/nas_discovery_runbook.md](docs/nas_discovery_runbook.md): passive NAS readiness discovery before credentials are available.
- [docs/baseline_progress_2026-05-27_nas_discovery.md](docs/baseline_progress_2026-05-27_nas_discovery.md): A-003 passive NAS discovery progress.
- [docs/baseline_progress_2026-05-27_nas_mount_helper.md](docs/baseline_progress_2026-05-27_nas_mount_helper.md): A-003 dry-run mount helper evidence.
- [docs/baseline_progress_2026-05-27_docs_logs_plugin.md](docs/baseline_progress_2026-05-27_docs_logs_plugin.md): B-002/B-005 local fallback evidence through the narrow OpenClaw plugin.
- [docs/sandbox_status_runbook.md](docs/sandbox_status_runbook.md): read-only Docker/Podman/sandbox status probe workflow.
- [docs/baseline_progress_2026-05-27_sandbox_status.md](docs/baseline_progress_2026-05-27_sandbox_status.md): A-006 status evidence and runtime blocker.
- [docs/browser_smoke_runbook.md](docs/browser_smoke_runbook.md): headless Chromium local page screenshot workflow.
- [docs/baseline_progress_2026-05-27_browser_smoke.md](docs/baseline_progress_2026-05-27_browser_smoke.md): A-007 local browser smoke evidence.
- [docs/rosbag_snapshot_runbook.md](docs/rosbag_snapshot_runbook.md): bounded ROS bag snapshot workflow.
- [docs/baseline_progress_2026-05-27_rosbag_snapshot.md](docs/baseline_progress_2026-05-27_rosbag_snapshot.md): A-009 local ROS bag snapshot evidence.
- [docs/rosbag_session_runbook.md](docs/rosbag_session_runbook.md): start/status/stop ROS bag self-test workflow.
- [docs/baseline_progress_2026-05-27_rosbag_session.md](docs/baseline_progress_2026-05-27_rosbag_session.md): A-009 local ROS bag session evidence.
- [docs/dataset_card_runbook.md](docs/dataset_card_runbook.md): dataset card format for robot captures.
- [docs/baseline_progress_2026-05-27_dataset_card.md](docs/baseline_progress_2026-05-27_dataset_card.md): B-004 local dataset card evidence.
- [docs/image_caption_runbook.md](docs/image_caption_runbook.md): deterministic metadata caption and JSONL index workflow for B-003.
- [docs/baseline_progress_2026-05-27_image_caption.md](docs/baseline_progress_2026-05-27_image_caption.md): B-003 local image caption/index progress.
- [docs/home_assistant_status_runbook.md](docs/home_assistant_status_runbook.md): read-only Home Assistant/device-state preflight for B-008.
- [docs/baseline_progress_2026-05-27_home_assistant_status.md](docs/baseline_progress_2026-05-27_home_assistant_status.md): B-008 read-only status progress.
- [docs/control_action_policy_runbook.md](docs/control_action_policy_runbook.md): low-risk control allowlist and audit preflight for B-009.
- [docs/baseline_progress_2026-05-27_control_action_policy.md](docs/baseline_progress_2026-05-27_control_action_policy.md): B-009 policy preflight progress.
- [docs/experiment_report_runbook.md](docs/experiment_report_runbook.md): experiment report generation from existing workspace artifacts.
- [docs/baseline_progress_2026-05-27_experiment_report.md](docs/baseline_progress_2026-05-27_experiment_report.md): B-007 local experiment report evidence.
- [docs/security_audit_runbook.md](docs/security_audit_runbook.md): redacted Gateway, plugin, listener, NAS, and secret metadata audit workflow.
- [docs/baseline_progress_2026-05-27_security_audit.md](docs/baseline_progress_2026-05-27_security_audit.md): B-010 local security audit evidence.
- [docs/service_hardening_plan_runbook.md](docs/service_hardening_plan_runbook.md): read-only dry-run command plan for B-010 service hardening.
- [docs/baseline_progress_2026-05-27_service_hardening_plan.md](docs/baseline_progress_2026-05-27_service_hardening_plan.md): B-010 service hardening plan progress.
- [docs/github_workflow_runbook.md](docs/github_workflow_runbook.md): local readiness workflow for issue -> branch -> PR -> review.
- [docs/baseline_progress_2026-05-27_github_workflow.md](docs/baseline_progress_2026-05-27_github_workflow.md): B-006 local GitHub/Codex workflow readiness evidence.
- [docs/github_remote_issue.md](docs/github_remote_issue.md): remote GitHub issue evidence for B-006.
- [docs/github_remote_pr.md](docs/github_remote_pr.md): remote draft PR and Codex review evidence for B-006.
- [docs/stability_snapshot_runbook.md](docs/stability_snapshot_runbook.md): point-in-time stability sampling for A-010.
- [docs/baseline_progress_2026-05-27_stability_snapshot.md](docs/baseline_progress_2026-05-27_stability_snapshot.md): A-010 local stability snapshot evidence.
- [scripts/install_stability_sampler.sh](scripts/install_stability_sampler.sh): operator-only systemd timer installer for repeated A-010 stability snapshots.
- [docs/s100p_allowlisted_plugin_runbook.md](docs/s100p_allowlisted_plugin_runbook.md): narrow OpenClaw plugin plan for approved S100P probes.
- [scripts/probes/ros2_status_probe.sh](scripts/probes/ros2_status_probe.sh): collects ROS2 command, node, topic, service, and package status.
- [scripts/probes/sandbox_status_probe.sh](scripts/probes/sandbox_status_probe.sh): collects container runtime, namespace, and cgroup status.
- [scripts/probes/browser_smoke_probe.sh](scripts/probes/browser_smoke_probe.sh): captures a local browser smoke screenshot and report.
- [scripts/probes/rosbag_snapshot_probe.sh](scripts/probes/rosbag_snapshot_probe.sh): records a bounded ROS bag snapshot and report.
- [scripts/probes/rosbag_session_probe.sh](scripts/probes/rosbag_session_probe.sh): runs a bounded start/status/stop ROS bag self-test.
- [scripts/probes/rosbag_capture_policy_probe.sh](scripts/probes/rosbag_capture_policy_probe.sh): writes a read-only named ROS bag capture policy and topic classification report.
- [scripts/probes/experiment_report_probe.sh](scripts/probes/experiment_report_probe.sh): summarizes workspace reports and datasets into a Markdown experiment report.
- [scripts/probes/security_audit_probe.sh](scripts/probes/security_audit_probe.sh): writes a redacted security audit report.
- [scripts/probes/service_policy_probe.sh](scripts/probes/service_policy_probe.sh): writes a read-only keep/disable/firewall policy plan for exposed services.
- [scripts/probes/service_hardening_plan_probe.sh](scripts/probes/service_hardening_plan_probe.sh): writes a dry-run hardening command plan without changing services.
- [scripts/probes/service_execution_preflight_probe.sh](scripts/probes/service_execution_preflight_probe.sh): writes a read-only B-010 confirmation-gate preflight without changing services or firewall rules.
- [scripts/probes/github_workflow_probe.ps1](scripts/probes/github_workflow_probe.ps1): writes a local GitHub/Codex readiness report.
- [scripts/probes/stability_snapshot_probe.sh](scripts/probes/stability_snapshot_probe.sh): writes a point-in-time uptime/resource/log stability snapshot.
- [scripts/probes/stability_summary_probe.sh](scripts/probes/stability_summary_probe.sh): aggregates A-010 stability snapshots into a trend and acceptance-gap report.
- [scripts/startup_link_check/](scripts/startup_link_check/): Windows tray startup checker for the PC -> S100P -> NAS -> OpenClaw/Feishu chain.
- [docs/baseline_progress_2026-05-28_startup_self_heal.md](docs/baseline_progress_2026-05-28_startup_self_heal.md): startup self-heal evidence for A-003/A-004/A-010 and B-005/B-010.
- [docs/baseline_progress_2026-05-28_a005_negative_retest.md](docs/baseline_progress_2026-05-28_a005_negative_retest.md): A-005 current OpenClaw agent-policy negative exec retest evidence.
- [docs/baseline_progress_2026-05-28_a003_persistent_nfs.md](docs/baseline_progress_2026-05-28_a003_persistent_nfs.md): A-003 reboot-verified persistent NFS automount evidence.
- [docs/baseline_progress_2026-05-28_nas_backed_reports.md](docs/baseline_progress_2026-05-28_nas_backed_reports.md): NAS-backed B-005 log diagnosis, B-007 experiment report, and A-010 stability collection evidence.
- [docs/baseline_progress_2026-05-28_nas_core_artifacts.md](docs/baseline_progress_2026-05-28_nas_core_artifacts.md): NAS-backed document index, browser screenshot, ROS bag session, dataset card, and experiment report evidence.
- [docs/baseline_progress_2026-05-28_image_security_nas.md](docs/baseline_progress_2026-05-28_image_security_nas.md): NAS-backed image metadata caption and security audit evidence.
- [docs/baseline_progress_2026-05-28_nas_baseline_status.md](docs/baseline_progress_2026-05-28_nas_baseline_status.md): NAS-backed roll-up status report for both baseline tracks.
- [docs/baseline_progress_2026-05-28_ha_control_preflight_nas.md](docs/baseline_progress_2026-05-28_ha_control_preflight_nas.md): NAS-backed Home Assistant read-only and control policy preflight evidence.
- [docs/baseline_progress_2026-05-28_b009_disabled_policy.md](docs/baseline_progress_2026-05-28_b009_disabled_policy.md): B-009 disabled-by-default control policy and no-execution preflight evidence.
- [docs/baseline_progress_2026-05-28_a010_nas_sampler.md](docs/baseline_progress_2026-05-28_a010_nas_sampler.md): A-010 stability sampler moved to NAS-backed output.
- [docs/baseline_progress_2026-05-29_overnight_runner_restart.md](docs/baseline_progress_2026-05-29_overnight_runner_restart.md): second overnight runner launch evidence and A-010 stability refresh.
- [docs/baseline_progress_2026-05-29_gap_decision.md](docs/baseline_progress_2026-05-29_gap_decision.md): read-only gap decision evidence for remaining baseline blockers.
- [docs/baseline_progress_2026-05-29_external_input_templates.md](docs/baseline_progress_2026-05-29_external_input_templates.md): handoff templates for Dream 7B smoke, Home Assistant config, B-009 control policy, and B-010 service confirmations.
- [docs/baseline_progress_2026-05-29_teacher_briefing_probe.md](docs/baseline_progress_2026-05-29_teacher_briefing_probe.md): read-only generator for teacher-facing two-baseline briefing packages.
- [docs/baseline_progress_2026-05-29_overnight_teacher_briefing.md](docs/baseline_progress_2026-05-29_overnight_teacher_briefing.md): overnight runner update that includes teacher-facing briefing output in the NAS evidence loop.
- [docs/baseline_progress_2026-05-28_service_policy_nas.md](docs/baseline_progress_2026-05-28_service_policy_nas.md): NAS-backed service policy and hardening dry-run evidence.
- [docs/baseline_progress_2026-05-28_b010_service_convergence_decision.md](docs/baseline_progress_2026-05-28_b010_service_convergence_decision.md): B-010 service convergence decision pack evidence.
- [docs/baseline_report_2026-05-28_nas_backed_smoke.md](docs/baseline_report_2026-05-28_nas_backed_smoke.md): current teacher-facing summary for the two baseline questions.
- [docs/baseline_report_2026-05-29_current_snapshot.md](docs/baseline_report_2026-05-29_current_snapshot.md): latest teacher-facing snapshot with A-010, Dream 7B, gap decision, and B-010 execution preflight evidence.
- [reports/teacher/openclaw_s100p_nas_baseline_20260528.tex](reports/teacher/openclaw_s100p_nas_baseline_20260528.tex) and [reports/teacher/openclaw_s100p_nas_baseline_20260528.pdf](reports/teacher/openclaw_s100p_nas_baseline_20260528.pdf): LaTeX source and compiled teacher-facing PDF report for the PC OpenClaw vs S100P+NAS baseline comparison.
- [docs/baseline_progress_2026-05-28_document_daily_summary.md](docs/baseline_progress_2026-05-28_document_daily_summary.md): B-002 NAS-backed deterministic document daily summary evidence.
- [scripts/probes/image_caption_probe.sh](scripts/probes/image_caption_probe.sh): writes deterministic image metadata captions and JSONL search records.
- [scripts/probes/dream7b_readiness_probe.sh](scripts/probes/dream7b_readiness_probe.sh): writes a read-only Dream 7B / local DLM deployment readiness report.
- [scripts/probes/dream7b_smoke_probe.sh](scripts/probes/dream7b_smoke_probe.sh): runs one bounded local Dream 7B smoke test only after an explicit local model config exists.
- [scripts/probes/document_daily_summary_probe.sh](scripts/probes/document_daily_summary_probe.sh): writes deterministic NAS document daily summaries.
- [scripts/probes/home_assistant_status_probe.sh](scripts/probes/home_assistant_status_probe.sh): writes a read-only Home Assistant status preflight report.
- [scripts/probes/control_action_policy_probe.sh](scripts/probes/control_action_policy_probe.sh): writes a read-only low-risk control policy and audit preflight report.
- [config/control_action_allowlist.disabled.json](config/control_action_allowlist.disabled.json): disabled-by-default B-009 control policy template.
- [config/service_convergence_confirmations.disabled.json](config/service_convergence_confirmations.disabled.json): disabled-by-default B-010 service convergence confirmation template.
- [config/dream7b_deployment.example.json](config/dream7b_deployment.example.json): Dream 7B local model path and bounded smoke-test config template.
- [config/home_assistant.env.example](config/home_assistant.env.example): read-only Home Assistant URL/token environment template.
- [scripts/probes/baseline_status_probe.sh](scripts/probes/baseline_status_probe.sh): writes a read-only roll-up status report for both baseline tracks.
- [scripts/probes/baseline_gap_decision_probe.sh](scripts/probes/baseline_gap_decision_probe.sh): writes a read-only remaining-gap and next-decision report for both baseline tracks.
- [scripts/probes/teacher_baseline_briefing_probe.sh](scripts/probes/teacher_baseline_briefing_probe.sh): writes a Chinese teacher-facing Markdown/JSON briefing from latest NAS evidence.
- [scripts/probes/nas_discovery_probe.sh](scripts/probes/nas_discovery_probe.sh): writes passive NAS mount/network/tooling readiness evidence.
- [scripts/mount_openclaw_nas.sh](scripts/mount_openclaw_nas.sh): dry-run first NAS mount helper for `/mnt/nas/openclaw`.
- [scripts/overnight_baseline_runner.sh](scripts/overnight_baseline_runner.sh): read-only overnight sampler that keeps writing stability and baseline roll-up evidence to NAS.
- [scripts/start_overnight_baseline_runner.sh](scripts/start_overnight_baseline_runner.sh): bounded launcher for the overnight sampler.
- [scripts/check_overnight_baseline_runner.sh](scripts/check_overnight_baseline_runner.sh): read-only status report for the latest overnight sampler JSONL and PID.
- [scripts/summarize_overnight_baseline_runner.sh](scripts/summarize_overnight_baseline_runner.sh): read-only interim/final summary for the latest overnight sampler run.

The allowlist runner now includes:

```bash
scripts/run_allowlisted_tool.sh ros2_status_probe
scripts/run_allowlisted_tool.sh experiment_report_probe
scripts/run_allowlisted_tool.sh security_audit_probe
scripts/run_allowlisted_tool.sh service_policy_probe
scripts/run_allowlisted_tool.sh service_hardening_plan_probe
scripts/run_allowlisted_tool.sh service_convergence_decision_probe
scripts/run_allowlisted_tool.sh service_execution_preflight_probe
scripts/run_allowlisted_tool.sh stability_snapshot_probe
scripts/run_allowlisted_tool.sh stability_summary_probe
scripts/run_allowlisted_tool.sh image_caption_probe
scripts/run_allowlisted_tool.sh vision_caption_readiness_probe
scripts/run_allowlisted_tool.sh dream7b_readiness_probe
scripts/run_allowlisted_tool.sh dream7b_smoke_probe
scripts/run_allowlisted_tool.sh document_daily_summary_probe
scripts/run_allowlisted_tool.sh home_assistant_status_probe
scripts/run_allowlisted_tool.sh control_action_policy_probe
scripts/run_allowlisted_tool.sh baseline_status_probe
scripts/run_allowlisted_tool.sh baseline_gap_decision_probe
scripts/run_allowlisted_tool.sh teacher_baseline_briefing_probe
scripts/run_allowlisted_tool.sh nas_discovery_probe
scripts/run_allowlisted_tool.sh rosbag_capture_policy_probe
scripts/run_allowlisted_tool.sh rosbag_named_capture_probe
```
