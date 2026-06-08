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

## Project Reference And Documentation Audit

Current project reference entrypoints:

- Current Dream 7B S100 BPU status: the bounded seq16 batch-generation path now defaults to `batch_count: 16`, uses `dream7b-bpu-fine-batch-forward` once per diffusion step, has verified single-run `max_bpu_loading: 100.0` in `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/batch_generation_telemetry_probe.json`, and has verified three-round sustained generation in `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_sustained_20260606-190058/batch_generation_sustained_probe.json`.
- Current Dream 7B utilization diagnosis: `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-211927/utilization_gap_probe.json` reports `verdict: ok_dream7b_bpu_utilization_gap_probe`, `diagnosis: hbm_reload_dominated`, `max_observed_bpu_loading: 100.0`, `avg_observed_bpu_loading_across_reports: 8.978`, `runtime_load_to_run_ratio: 8.399`, and `systemd_load_to_run_ratio: 8.48`.
- Current Dream 7B persistent pair cache boundary: `/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_pair_cache_20260605-234349/persistent_pair_cache_probe.json` reports `verdict: ok_dream7b_bpu_persistent_pair_cache_probe`, `pair_worker_count: 5`, `ready_pair_worker_count: 1`, `all_pair_workers_ready: False`, and `launch_stopped_reason: pair_01_seg04_07__seg07_10 did not reach ready status`.
- Current Dream 7B held-pair residency matrix: `/mnt/nas/openclaw/reports/models/dream7b_bpu_held_pair_residency_matrix_20260605-235813/held_pair_residency_matrix_probe.json` reports `verdict: ok_dream7b_bpu_held_pair_residency_matrix_probe`, `ready_holder_pair_count: 5`, `matrix_entry_count: 20`, `successful_pair_edge_count: 0`, `failed_pair_edge_count: 20`, and `max_resident_pair_count_observed: 1`.
- Current Dream 7B single-segment residency matrix: `/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_residency_matrix_20260606-002628/single_segment_residency_matrix_probe.json` reports `verdict: ok_dream7b_bpu_single_segment_residency_matrix_probe`, `segment_count: 10`, `ready_holder_segment_count: 10`, `matrix_entry_count: 90`, `successful_segment_edge_count: 90`, `failed_segment_edge_count: 0`, and `max_resident_segment_count_observed: 2`.
- Current Dream 7B persistent segment cache boundary: `/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_segment_cache_20260606-005633/persistent_segment_cache_probe.json` reports `verdict: ok_dream7b_bpu_persistent_segment_cache_probe`, `segment_worker_count: 10`, `ready_segment_worker_count: 2`, `failed_segment_worker_count: 1`, `all_segment_workers_ready: False`, `launch_stopped_reason: segment_02_seg04_07 did not reach ready status`, and `max_resident_segment_count_observed: 2`.
- Current Dream 7B single-segment triplet residency: `/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_20260606-121243/single_segment_triplet_residency_probe.json` reports `verdict: ok_dream7b_bpu_single_segment_triplet_residency_probe`, `tested_triplet_combination_count: 120`, `successful_triplet_count: 20`, `failed_triplet_count: 100`, and `max_resident_segment_count_observed: 3`.
- Current Dream 7B seeded quad residency: `/mnt/nas/openclaw/reports/models/dream7b_bpu_seeded_quad_residency_20260606-124305/seeded_quad_residency_probe.json` reports `verdict: ok_dream7b_bpu_seeded_quad_residency_probe`, `source_successful_triplet_count: 20`, `seeded_quad_candidate_count: 84`, `tested_seeded_quad_count: 84`, `successful_seeded_quad_count: 0`, `failed_seeded_quad_count: 84`, and `max_resident_segment_count_observed: 3`.
- Current Dream 7B persistent triplet topology: `/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_triplet_topology_20260606-131107/persistent_triplet_topology_probe.json` reports `verdict: ok_dream7b_bpu_persistent_triplet_topology_probe`, `source_successful_triplet_count: 20`, `tested_triplet_topology_count: 20`, `stable_triplet_topology_count: 20`, `failed_triplet_topology_count: 0`, `selected_topology: [0, 1, 8]`, and `max_resident_segment_count_observed: 3`.
- Current Dream 7B window3 forward feasibility: `/mnt/nas/openclaw/reports/models/dream7b_bpu_window3_forward_feasibility_20260606-133931/window3_forward_feasibility_probe.json` reports `verdict: ok_dream7b_bpu_window3_forward_feasibility_probe`, `direct_window3_forward_supported: False`, `expected_window3_failure_observed: True`, `stderr_contains_memory_alloc_failure: True`, and `returncode: 1`.
- Current Dream 7B selected triplet forward path: `/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_triplet_forward_path_20260606-135729/selected_triplet_forward_path_probe.json` reports `verdict: ok_dream7b_bpu_selected_triplet_forward_path_probe`, `selected_triplet_forward_supported: False`, `reboot_or_disconnect_observed: True`, `expected_reboot_guard_observed: True`, `selected_topology: [0, 1, 8]`, and `next_optimization_target: do not promote selected triplet forward path; test smaller resident sets or vendor-supported multi-segment HBM residency instead`.
- Current S100 official LLM/Qwen baseline: `/mnt/nas/openclaw/reports/models/s100_official_llm_baseline_20260606-004107/official_llm_baseline_probe.json` reports `verdict: ok_s100_official_llm_baseline_probe`, `sdk_exists: True`, `config_dir_count: 8`, `official_hbm_download_entry_count: 14`, `qwen_existing_hbm_count: 1`, `qwen_hbm_exists_from_multichat: True`, `official_qwen_local_runtime_report_present: True`, `official_qwen_runtime_completed: False`, `official_qwen_runtime_returncode: -11`, `official_qwen_memory_alloc_failure_observed: True`, and `similar_issue_evidence_available_for_official_qwen: True`.
- Current official Qwen runtime comparison: `/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/official_qwen_runtime_probe.json` reports `verdict: ok_s100_official_qwen_runtime_probe`, `qwen_hbm_size_bytes: 1917038584`, `ldd_missing_dependency_observed: False`, `hbm_load_success_observed: True`, `prefill_model_load_success_observed: True`, `decode_model_load_success_observed: True`, `init_model_success_observed: True`, `memory_alloc_failure_observed: True`, `ion_alloc_failure_observed: True`, `bpu_mem_pool_alloc_error_observed: True`, `segmentation_fault_observed: True`, and `official_qwen_runtime_supported_on_current_s100p_state: False`.
- Current official Qwen performance-mode retest: `/mnt/nas/openclaw/reports/models/s100_official_qwen_performance_mode_retest_20260606-003908/performance_mode_retest_probe.json` reports `before_values: {'0x2b047000': '0x0000007E', '0x2b047004': '0x00EC4EC4'}`, `after_values: {'0x2b047000': '0x00000099', '0x2b047004': '0x00000099'}`, `target_applied: True`, `runtime_completed_after_performance_mode: False`, `runtime_returncode_after_performance_mode: -11`, and `memory_alloc_failure_observed_after_performance_mode: True`.
- Current S100 BPU memory-pool preflight: `/mnt/nas/openclaw/reports/models/s100_bpu_memory_pool_20260606-010941/bpu_memory_pool_probe.json` reports `verdict: ok_s100_bpu_memory_pool_probe`, `ion_debug_present: True`, `ion_all_heap_info_exists: True`, `cma_reserved_heap_total_size: 1073741824`, `ion_cma_heap_total_size: 536870912`, `carveout_heap_total_size: 536870912`, `system_heap_total_size: 0`, `system_contig_heap_total_size: 0`, `ion_heap_bpu_allocation_sizes.carveout: 3145728`, `reserved_memory_summary.bpu_region@9A000000.reg.size_mib: 96.0`, `latest_official_qwen_memory_alloc_failure_observed: True`, `latest_dream_diagnosis: hbm_reload_dominated`, and `next_probe_target: run a minimal HBMEM/UCP common-buffer allocation matrix against the exact backend/heap flags used by official Qwen; performance-mode register apply alone did not clear official Qwen allocation failure`.
- Current S100 HBMEM/UCP allocation matrix: `/mnt/nas/openclaw/reports/models/s100_hbmem_common_buffer_matrix_20260606-012033/hbmem_common_buffer_matrix_probe.json` reports `verdict: ok_s100_hbmem_common_buffer_matrix_probe`, `ucp_enabled: True`, `hbmem_alloc_case_count: 28`, `hbmem_alloc_success_count: 28`, `qwen_log_sizes: [786432, 2359296]`, `qwen_log_size_success_count: 14`, `qwen_log_size_failure_count: 0`, `ucp_case_count: 8`, `ucp_success_count: 8`, and `next_probe_target: compare these direct HBMEM/UCP allocation results with official Qwen's backend: 9 failure path and inspect libhbucp backend-to-hbmem flag selection if direct allocations pass`.
- Current S100 Qwen backend 9 baseline: `/mnt/nas/openclaw/reports/models/s100_qwen_backend9_baseline_20260606-013902/qwen_backend9_baseline_probe.json` reports `verdict: ok_s100_qwen_backend9_baseline_probe`, `config_has_bpu_core: False`, `demo_default_bpu_core_value: -1`, `demo_default_infer_backend: XLM_INFER_BACKEND_BPU_ANY`, `observed_backend_values: [9]`, `observed_backend_bit_matches_from_hb_ucp_header: {'9': ['HB_UCP_BPU_CORE_0', 'HB_UCP_BPU_CORE_3']}`, `backend_9_equals_hb_ucp_bpu_core_any: False`, `observed_ucp_alloc_failure_sizes: [786432, 1572864]`, `stderr_alloc_error_lens: [2359296]`, `direct_hbmem_matrix_qwen_sizes_pass: True`, `official_qwen_has_similar_bpu_memory_issue: True`, `official_qwen_issue_not_raw_size_only: True`, and `next_probe_target: run a controlled official Qwen bpu_core sweep by copying qwen_multichat_config.json and adding exact bpu_core values -1, 0, 1, 2, and 3`.
- Current S100 Qwen `bpu_core` sweep: `/mnt/nas/openclaw/reports/models/s100_qwen_bpu_core_sweep_20260606-015133/qwen_bpu_core_sweep_probe.json` reports `verdict: ok_s100_qwen_bpu_core_sweep_probe`, `tested_bpu_core_values: [-1, 0, 1, 2, 3]`, `backend_values_by_core: {'-1': [9], '0': [9], '1': [9], '2': [9], '3': [9]}`, `runtime_completed_by_core: {'-1': False, '0': False, '1': True, '2': True, '3': True}`, `segmentation_fault_by_core: {'-1': True, '0': True, '1': False, '2': False, '3': False}`, `functional_success_by_core: {'-1': False, '0': False, '1': False, '2': False, '3': False}`, `all_cases_failed_functionally: True`, `any_case_functional_success: False`, and `interpretation: explicit bpu_core values changed the official Qwen crash behavior, but no tested core produced functional inference; core pinning alone is not sufficient`.
- Current Dream 7B BPU scheduling params: `/mnt/nas/openclaw/reports/models/dream7b_bpu_scheduling_params_20260606-020548/scheduling_params_probe.json` reports `verdict: ok_dream7b_bpu_scheduling_params_probe`, `tested_cores: ['default', '0', '1', '2', '3']`, `run_ok_by_core: {'default': True, '0': True, '1': False, '2': False, '3': False}`, `returncode_by_core: {'default': 0, '0': 0, '1': -6, '2': -6, '3': -6}`, `schedule_backend_unsupported_by_core: {'default': False, '0': False, '1': True, '2': True, '3': True}`, `core0_explicit_supported: True`, `nonzero_cores_supported: False`, and `next_probe_target: treat Dream bpu_cores as a model-specific scheduling constraint; do not port Qwen bpu_core values directly`.
- Current Dream 7B deployment acceptance: `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-234652/deployment_acceptance_probe.json` reports `check_count: 25`, `passed_check_count: 25`, `min_batch_generate_count: 16`, `min_batch_generate_sustained_round_count: 3`, `utilization_gap.ok: True`, `persistent_pair_cache.ok: True`, `held_pair_residency_matrix.ok: True`, `single_segment_residency_matrix.ok: True`, `persistent_segment_cache.ok: True`, `single_segment_triplet_residency.ok: True`, `seeded_quad_residency.ok: True`, `persistent_triplet_topology.ok: True`, `window3_forward_feasibility.ok: True`, and `selected_triplet_forward_path.ok: True`.
- Current boundary: this is real Dream 7B BPU execution with a bounded seq16 batch-generation bridge; it is still not a complete production text-generation service.
- [docs/project_reference.md](docs/project_reference.md): command interfaces, configuration keys, architecture, decisions, development log, requirements, and TODOs.
- [docs/documentation_audit_runbook.md](docs/documentation_audit_runbook.md): post-task documentation verification workflow.
- [docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md](docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md): current Dream 7B segmented S100 BPU HBM evidence.
- [scripts/dream7b-bpu-fine-batch-forward.sh](scripts/dream7b-bpu-fine-batch-forward.sh): reusable Dream 7B fine-split BPU batch forward wrapper for independent seq16 token batches.
- [scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh](scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh): runs a bounded Dream 7B BPU batch-size sweep for `dream7b-bpu-fine-batch-forward` and records HBM load amortization.
- [scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh](scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh): wraps the fine-forward repeat probe for longer `pair_in_process` repeated-run evidence with a default `DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO` gate.
- [scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh](scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh): runs Dream 7B BPU forward while sampling `hrt_ucp_monitor` BPU loading telemetry.
- [scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh](scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh): verifies Dream 7B base/fine HBM artifact inventory, NAS/local-cache size consistency, and base `manifest.sha256` integrity.
- [scripts/dream7b-bpu-batch-queue-runner.sh](scripts/dream7b-bpu-batch-queue-runner.sh): service-level JSONL queue runner that batches independent seq16 requests into `dream7b-bpu-fine-batch-forward`.
- [scripts/dream7b-bpu-batch-queue-service.sh](scripts/dream7b-bpu-batch-queue-service.sh): directory-backed Dream 7B BPU queue service loop over `pending`, `processing`, `done`, and `failed` job directories.
- [scripts/install_dream7b_bpu_queue_service.sh](scripts/install_dream7b_bpu_queue_service.sh): installs and manages `dream7b-bpu-batch-queue.service` for the NAS-backed Dream 7B BPU queue on S100P.
- [scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh](scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh): verifies `dream7b-bpu-batch-queue.service` is active, enabled, and points at the expected NAS queue and report directories.
- [scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh](scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh): submits multiple JSONL jobs through the NAS-backed systemd queue and verifies real BPU completion.
- [scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh](scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh): submits one multi-request JSONL job through the NAS-backed systemd queue and verifies `batch_count`.
- [scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh](scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh): submits a multi-request JSONL job through the NAS-backed systemd queue and verifies default `--drain-all` processing. Historical reports include five-request `[4, 1]`, eight-request `[4, 4]`, and eight-request `[8]`; the current service default is `--max-batch-size 16` and the latest sixteen-request drain report verifies `[16]`.
- [scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh](scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh): lightweight real BPU canary that submits a small JSONL job through the NAS-backed systemd queue and verifies service status, `final_shapes`, batching, and lock-path fields.
- [scripts/dream7b-bpu-text-queue-submit.sh](scripts/dream7b-bpu-text-queue-submit.sh): reusable S100P command that encodes a Dream 7B prompt through the local tokenizer and atomically submits one seq16 JSONL job into the NAS-backed BPU queue.
- [scripts/dream7b-bpu-text-queue-run.sh](scripts/dream7b-bpu-text-queue-run.sh): reusable S100P command that calls `dream7b-bpu-text-queue-submit`, waits for `dream7b-bpu-batch-queue.service`, and returns BPU `topk_last_position` plus tokenizer-decoded `topk_last_position_decoded` output.
- [scripts/probes/dream7b_bpu_text_queue_systemd_probe.sh](scripts/probes/dream7b_bpu_text_queue_systemd_probe.sh): verifies the text queue systemd path by calling `dream7b-bpu-text-queue-run` and checking service status, queue summary, tokenizer, decoded top-k, and BPU output fields.
- [scripts/dream7b-bpu-diffusion-generate.sh](scripts/dream7b-bpu-diffusion-generate.sh): reusable S100P bounded seq16 Dream diffusion generation command that calls `dream7b-bpu-fine-forward` for BPU logits and writes `generation.json` plus `generation.md`.
- [scripts/probes/dream7b_bpu_diffusion_generate_telemetry_probe.sh](scripts/probes/dream7b_bpu_diffusion_generate_telemetry_probe.sh): runs `dream7b-bpu-diffusion-generate` while sampling `hrt_ucp_monitor` and verifies both generation fields and BPU loading telemetry.
- [scripts/dream7b-bpu-diffusion-batch-generate.sh](scripts/dream7b-bpu-diffusion-batch-generate.sh): reusable S100P bounded seq16 batch Dream diffusion generation command that calls `dream7b-bpu-fine-batch-forward` once per diffusion step.
- [scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh](scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh): runs `dream7b-bpu-diffusion-batch-generate` while sampling `hrt_ucp_monitor` and verifies batch generation, batch forward counts, and BPU loading telemetry.
- [scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh](scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh): runs repeated bounded seq16 batch Dream diffusion generations while sampling `hrt_ucp_monitor` and verifies sustained generation count, batch counts, forward counts, and BPU loading telemetry.
- [scripts/probes/dream7b_bpu_utilization_gap_probe.sh](scripts/probes/dream7b_bpu_utilization_gap_probe.sh): aggregates the latest Dream 7B BPU batch, telemetry, sustained generation, and systemd reports to diagnose whether current average BPU utilization is still dominated by HBM reload overhead.
- [scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh](scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh): tests whether all five fine pair runtimes can be held as persistent workers, recording the current memory-allocation boundary before implementing any pair-worker pipeline.
- [scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh](scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh): holds each fine pair in turn and attempts every other pair, producing the pair coexistence matrix for the next split/runtime-residency decision.
- [scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh](scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh): holds each fine single segment in turn and attempts every other single segment, proving whether pair-size HBM is the current residency blocker.
- [scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh](scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh): launches single-segment HBM runtimes sequentially and records the current maximum resident segment count before attempting a persistent single-segment worker pipeline.
- [scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh](scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh): tests all 120 three-single-segment residency combinations and records successful triplets for the next seeded persistent topology.
- [scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh](scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh): expands successful triplets into seeded four-segment candidates and records whether the current HBM residency boundary can exceed three single segments.
- [scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh](scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh): replays successful three-single-segment residency groups as long-lived workers and records stable triplet topology candidates for the next forward-path experiment.
- [scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh](scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh): tests whether the existing fine batch forward path can directly use packed adjacent three-segment windows and records the current memory-allocation failure boundary.
- [scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh](scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh): tests or records the selected `[0, 1, 8]` triplet forward-path attempt and guards against retrying an observed reboot/disconnect unless `DREAM7B_BPU_SELECTED_TRIPLET_ALLOW_CRASH_RETRY=1`.
- [scripts/probes/s100_official_llm_baseline_probe.sh](scripts/probes/s100_official_llm_baseline_probe.sh): report-only comparison of the official S100 LLM/Qwen SDK layout against the current custom segmented Dream 7B BPU route.
- [scripts/probes/s100_official_qwen_runtime_probe.sh](scripts/probes/s100_official_qwen_runtime_probe.sh): bounded official Qwen `oellm_multichat` runtime probe that reads `qwen_multichat_config.json`, captures stdout/stderr/ldd, and compares BPU memory failures against the Dream 7B route.
- [scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh](scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh): controlled official performance-mode register apply through `/usr/bin/devmem`, followed by an official Qwen runtime retest.
- [scripts/probes/s100_bpu_memory_pool_probe.sh](scripts/probes/s100_bpu_memory_pool_probe.sh): read-only S100P BPU/common-buffer/ION/HBMEM preflight that records `devmem`, performance registers, direct debugfs ION heap totals, BPU ION allocations, BPU iovmm counters, device-tree reserved-memory nodes, official Qwen, and Dream utilization evidence.
- [scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh](scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh): compiles and runs a minimal S100P HBMEM/UCP common-buffer allocation matrix covering the official Qwen failure sizes `786432` and `2359296`.
- [scripts/probes/s100_qwen_backend9_baseline_probe.sh](scripts/probes/s100_qwen_backend9_baseline_probe.sh): read-only official Qwen backend 9 baseline probe that records `qwen_multichat_config.json`, `oellm_multichat_demo.cc` `bpu_core` behavior, `/usr/include/hobot/hb_ucp.h` backend constants, `libhbucp.so` symbols/strings, and the Qwen memory failure comparison against Dream 7B.
- [scripts/probes/s100_qwen_bpu_core_sweep_probe.sh](scripts/probes/s100_qwen_bpu_core_sweep_probe.sh): controlled official Qwen `bpu_core` sweep that copies `qwen_multichat_config.json`, adds exact `bpu_core` values `-1`, `0`, `1`, `2`, and `3`, and records backend, memory, prefill, crash, and functional-success outcomes.
- [scripts/probes/dream7b_bpu_scheduling_params_probe.sh](scripts/probes/dream7b_bpu_scheduling_params_probe.sh): isolated-child Dream 7B `HB_HBMRuntime.set_scheduling_params(..., bpu_cores=...)` probe for default and exact cores `0`, `1`, `2`, and `3`.
- [scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh](scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh): submits sustained NAS-backed systemd queue batches while sampling `hrt_ucp_monitor` BPU loading telemetry.
- [scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh](scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh): report-only retention and stale-file policy probe for Dream 7B BPU queue `pending`, `processing`, `done`, and `failed` directories.
- [scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh](scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh): report-only deployment acceptance gate that aggregates the latest Dream 7B BPU service, HBM artifact inventory, batch capacity, systemd batch/drain/canary/text-queue/diffusion-generate/batch-generation/telemetry, long-repeat, selected-triplet-forward-path, and queue-retention reports.
- [scripts/probes/dream7b_bpu_batch_capacity_probe.sh](scripts/probes/dream7b_bpu_batch_capacity_probe.sh): probes independent seq16 batch capacity through `dream7b-bpu-fine-batch-forward` and verifies the current 8/12/16 capacity boundary.
- [scripts/probes/dream7b_bpu_batch_queue_control_probe.sh](scripts/probes/dream7b_bpu_batch_queue_control_probe.sh): verifies queue `cancelled`, `not_after_epoch_ms`, skipped request, and durable JSONL state behavior.
- [scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh](scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh): verifies queue runner `bpu_lock` single-flight behavior without calling the real BPU.
- [scripts/probes/project_docs_consistency_probe.sh](scripts/probes/project_docs_consistency_probe.sh): repeatable documentation consistency probe.

Documentation rule:

- Do not guess identifiers such as command names, JSON keys, environment variables, paths, fields, services, or model names.
- Before writing an identifier, read the related source file, config file, runtime report, or log and copy the exact spelling.
- After each task that changes code, scripts, config, reports, decisions, or requirements, run:

```bash
bash scripts/probes/project_docs_consistency_probe.sh /tmp/project_docs_consistency
```

If the check is not run, the task note must say why.

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
- [docs/baseline_progress_2026-06-02_startup_link_repair.md](docs/baseline_progress_2026-06-02_startup_link_repair.md): boot-time ICS reset, real NFS autofs verification, and OpenClaw/Feishu readiness coverage.
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
- [docs/baseline_progress_2026-05-29_acceptance_gate.md](docs/baseline_progress_2026-05-29_acceptance_gate.md): read-only pass/collecting/blocked acceptance matrix for every A/B baseline item.
- [docs/baseline_progress_2026-05-29_acceptance_trend.md](docs/baseline_progress_2026-05-29_acceptance_trend.md): read-only trend report across saved baseline acceptance snapshots.
- [docs/baseline_progress_2026-05-29_evidence_manifest.md](docs/baseline_progress_2026-05-29_evidence_manifest.md): read-only SHA256 manifest for the current baseline evidence files.
- [docs/baseline_progress_2026-05-29_overnight_runner_queue.md](docs/baseline_progress_2026-05-29_overnight_runner_queue.md): bounded queue for starting the next updated overnight runner after the currently running sampler exits.
- [docs/baseline_progress_2026-05-30_windows_s100p_entrypoint.md](docs/baseline_progress_2026-05-30_windows_s100p_entrypoint.md): fixed Windows PowerShell entrypoint for routine S100P SSH diagnostics and read-only baseline refreshes.
- [docs/baseline_progress_2026-05-30_nas_blocked_hold.md](docs/baseline_progress_2026-05-30_nas_blocked_hold.md): current NAS physical/IP reachability hold, evidence, and resume steps.
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
- [scripts/probes/baseline_acceptance_probe.sh](scripts/probes/baseline_acceptance_probe.sh): writes a read-only acceptance gate matrix for all A/B baseline IDs.
- [scripts/probes/baseline_acceptance_trend_probe.sh](scripts/probes/baseline_acceptance_trend_probe.sh): writes a read-only trend report across acceptance snapshots.
- [scripts/probes/baseline_evidence_manifest_probe.sh](scripts/probes/baseline_evidence_manifest_probe.sh): writes a read-only evidence manifest with size, mtime, and SHA256 hashes.
- [scripts/probes/teacher_baseline_briefing_probe.sh](scripts/probes/teacher_baseline_briefing_probe.sh): writes a Chinese teacher-facing Markdown/JSON briefing from latest NAS evidence.
- [scripts/probes/nas_discovery_probe.sh](scripts/probes/nas_discovery_probe.sh): writes passive NAS mount/network/tooling readiness evidence.
- [scripts/mount_openclaw_nas.sh](scripts/mount_openclaw_nas.sh): dry-run first NAS mount helper for `/mnt/nas/openclaw`.
- [scripts/overnight_baseline_runner.sh](scripts/overnight_baseline_runner.sh): read-only overnight sampler that keeps writing stability and baseline roll-up evidence to NAS.
- [scripts/start_overnight_baseline_runner.sh](scripts/start_overnight_baseline_runner.sh): bounded launcher for the overnight sampler.
- [scripts/check_overnight_baseline_runner.sh](scripts/check_overnight_baseline_runner.sh): read-only status report for the latest overnight sampler JSONL and PID.
- [scripts/summarize_overnight_baseline_runner.sh](scripts/summarize_overnight_baseline_runner.sh): read-only interim/final summary for the latest overnight sampler run.
- [scripts/queue_next_overnight_baseline_runner.sh](scripts/queue_next_overnight_baseline_runner.sh): waits for the current overnight sampler PID to exit, then launches the next updated sampler without running two samplers concurrently.
- [scripts/check_overnight_queue.sh](scripts/check_overnight_queue.sh): read-only status report for the latest queued overnight sampler launcher.
- [scripts/windows/s100p-task.ps1](scripts/windows/s100p-task.ps1): fixed Windows entrypoint for allowlisted S100P SSH diagnostics, NAS runtime repair, OpenClaw status, overnight status, and read-only baseline refreshes.

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
scripts/run_allowlisted_tool.sh baseline_acceptance_probe
scripts/run_allowlisted_tool.sh baseline_acceptance_trend_probe
scripts/run_allowlisted_tool.sh baseline_evidence_manifest_probe
scripts/run_allowlisted_tool.sh teacher_baseline_briefing_probe
scripts/run_allowlisted_tool.sh nas_discovery_probe
scripts/run_allowlisted_tool.sh rosbag_capture_policy_probe
scripts/run_allowlisted_tool.sh rosbag_named_capture_probe
```
