# S100P + NAS + OpenClaw Baseline 汇报稿

Date: 2026-05-28

本文面向导师汇报，按两个问题回答当前进展：

1. PC 上装 OpenClaw 能做的事，S100P 能不能实现类似效果？
2. 高价位 AI NAS / OpenClaw NAS 常做的事，S100P + TS-264C 能抄到什么程度？

## 一句话结论

当前已经不是“只在本地 workspace 跑通”的状态，而是已经推进到
`S100P + TS-264C NAS` 的 NAS-backed smoke baseline：

- S100P 能常驻 OpenClaw Gateway，飞书入口可用，能通过白名单工具执行探针。
- TS-264C 已通过 NFS v4.1 持久化挂载到 `/mnt/nas/openclaw`，重启后 automount 和写入验证通过。
- 文档索引、日志诊断、浏览器截图、ROS bag session、dataset card、实验报告、稳定性采样、安全审计都已经能写入 NAS。
- 仍未完成的是 7 天稳定性、sandbox runtime、服务收敛策略、Home Assistant 真实配置、控制动作策略和真实业务数据填充。

## Baseline A：S100P 能否接近 PC OpenClaw 效果

### 已经实现的类似 PC 能力

| 能力 | 当前状态 | 证据 |
| --- | --- | --- |
| OpenClaw Gateway 常驻 | verified | Gateway active-listening，飞书 WebSocket ready，消息 received/dispatch complete 已观察到。 |
| 飞书入口 | verified | 群聊/私聊消息能触发 agent；`99991672` contact 权限只是非阻断告警。 |
| 联网搜索 | verified | Tavily 作为 OpenClaw 搜索源已验证。 |
| NAS workspace | verified | `169.254.110.209:/OpenClawWorkspace` 持久化挂载到 `/mnt/nas/openclaw`，重启后可写。 |
| 浏览器自动化 | verified | Headless Chromium 打开本地页面并截图到 NAS，PNG 校验通过。 |
| ROS2 状态查询 | verified | 可读取 node/topic/service 状态。 |
| ROS bag 采集 | doing | NAS-backed start/status/stop self-test 已通过；长时间命名采集策略未定。 |
| 稳定性采样 | doing | systemd timer 已切到 NAS 输出；当前 2 个 snapshot，仍需 168 小时样本。 |
| 工具白名单 | doing | narrow plugin/runner 可用；broad exec 平台级阻断仍未完全验证。 |
| Sandbox | blocked | S100P 当前无 Docker/Podman/runc runtime。 |

### 关键差异

和 PC 相比，S100P 的优势不是算力或桌面交互，而是低功耗、常驻、靠近机器人和 NAS：

- PC 可以随手开 OpenClaw，但用户电脑不会一直开机。
- S100P 可以作为常驻 agent 入口，自动恢复网络、NAS、OpenClaw Gateway 和飞书链路。
- NAS 让日志、报告、数据集和恢复证据不依赖 PC 本地磁盘。

因此，S100P 的定位不是替代 PC 的所有交互体验，而是替代 PC 做常驻网关、数据落盘、机器人侧工具执行和自动巡检。

## Baseline B：AI NAS / OpenClaw NAS 能力抄作业

### 已经抄到的能力

| AI NAS 常见能力 | S100P + NAS 当前实现 | 状态 |
| --- | --- | --- |
| 统一 workspace | TS-264C NFS `/OpenClawWorkspace` 挂到 S100P | verified |
| 文档索引 | 对 NAS 文档生成 Markdown 索引、hash、preview | doing |
| 图片 caption / 搜索 | 对 NAS 图片生成 metadata caption 和 JSONL index | doing |
| 日志诊断 | 从 NAS logs 输出错误摘要、关键匹配、建议命令 | verified |
| 机器人数据集管理 | ROS bag session 写 NAS，并生成 `DATASET_CARD.md` | verified |
| 实验/周报 | 从 NAS logs、reports、datasets 汇总 Markdown 报告 | verified |
| 稳定性报告 | NAS-backed snapshot + summary，timer 自动采样 | doing |
| 安全审计 | Gateway 暴露、NAS mount、secret scan、服务监听审计 | doing |
| 设备只读状态 | Home Assistant read-only preflight 已有 | doing |
| 低风险控制 | control policy/audit preflight 已有，未开放执行 | doing |

### 当前 NAS-backed 证据总览

```text
NAS workspace: /mnt/nas/openclaw
Baseline roll-up: /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-183640.md
Experiment report: /mnt/nas/openclaw/reports/experiments/experiment_report_20260528-182242.md
Document index: /mnt/nas/openclaw/reports/document_index_20260528-182111.md
Browser screenshot: /mnt/nas/openclaw/reports/browser-smoke/browser_smoke_20260528-182111.png
ROS bag dataset: /mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117/
Dataset card: /mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117/DATASET_CARD.md
Log diagnosis: /mnt/nas/openclaw/logs/probes/log_diagnosis_20260528-181546.md
Image caption index: /mnt/nas/openclaw/reports/image-captions/image_caption_index_20260528-182530.md
Security audit: /mnt/nas/openclaw/logs/probes/security_audit_20260528-182530.md
Service policy: /mnt/nas/openclaw/logs/probes/service_policy_20260528-183619.md
```

## S100P + NAS 对这件事的帮助

S100P + NAS 的价值主要体现在四点：

1. **常驻入口**：PC 关机后，OpenClaw Gateway、飞书入口、采样任务仍可在 S100P 上运行。
2. **统一落盘**：所有日志、报告、ROS bag、dataset card、截图、索引都写 NAS，不依赖 PC。
3. **断电后恢复**：Windows 开机托盘工具负责检查 `PC -> S100P -> NAS -> OpenClaw/飞书` 链路；S100P 重启后 NFS automount 可恢复。
4. **机器人侧数据闭环**：S100P 靠近 ROS2/TROS 和机器人数据，NAS 负责长期存储，OpenClaw 负责触发和汇总。

## 当前阻塞和不擅自处理的项

这些项需要用户或外部平台决策，当前只记录不自动改：

- A-006：是否安装 Docker/Podman/runc，或第一版明确不做 sandbox。
- A-010：需要持续运行满 168 小时，不能用单次 smoke 替代。
- B-008：需要 Home Assistant URL/token 才能读取真实设备状态。
- B-009：需要控制动作 allowlist、二次确认文案和审计策略，才能开放执行。
- B-010：是否关闭 NFS/RPC、x11vnc、iiod 或改防火墙，需要确认不会影响 RDK Studio/硬件工具。
- 飞书 `99991672`：contact scope 权限需要在飞书开放平台申请，不阻塞消息收发。

## 下一步建议

优先顺序：

1. 让 A-010 自动采样继续跑，累计 168 小时后生成稳定性验收报告。
2. 用真实文档、真实图片、真实机器人数据替换 smoke 数据，再重跑 experiment report。
3. 明确 B-003 是否只做 metadata caption，还是接入语义视觉模型。
4. 决策 B-010 服务收敛策略，只在确认后执行 disable/firewall。
5. 如果要做智能家居/设备联动，再补 Home Assistant URL/token 和 B-009 控制 allowlist。

当前可汇报结论：S100P + NAS 已经跑通了一个可恢复、可观察、可写 NAS 的 OpenClaw 常驻 baseline；它已经能覆盖 PC OpenClaw 的一部分核心功能，并且开始具备 AI NAS 的日志、数据集、报告和审计雏形。
