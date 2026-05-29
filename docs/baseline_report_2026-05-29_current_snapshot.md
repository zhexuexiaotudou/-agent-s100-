# S100P + NAS + OpenClaw Baseline 当前快照

Date: 2026-05-29 19:34 CST

本文面向导师汇报，按两个问题回答当前进展：

1. PC 上装 OpenClaw 能做的事情，用 S100P 是否能实现类似效果？
2. 高价位 AI NAS / OpenClaw NAS 常见能力，S100P + NAS 已经抄到什么程度？

## 一句话结论

S100P + NAS 已经跑通了一个可恢复、可观测、可写 NAS 的 OpenClaw 常驻 baseline。它还不能替代 PC 的完整交互体验，也不能宣称 Dream 7B 已部署，但已经能覆盖 PC OpenClaw 的一部分核心自动化能力：飞书入口、白名单工具执行、NAS 落盘、ROS2/ROS bag 只读或受控采集、日志诊断、报告汇总和安全审计。

当前最新证据：

```text
overnight runner: running, pid=278801, completed_iterations=7, failed_event_count=0
A-010 stability: 78 snapshots, 25.15h, verdict=collecting
Gateway: active-listening
NAS: mounted
Allowlisted tools: 27
Gap report: /mnt/nas/openclaw/reports/baseline-status/baseline_gap_decision_20260529-193407.md
```

## Baseline A：S100P 接近 PC OpenClaw 的程度

| 能力 | 当前状态 | 证据/结论 |
| --- | --- | --- |
| OpenClaw Gateway 常驻 | verified | Gateway 仅 loopback 监听，当前 active-listening。 |
| 飞书入口 | verified | 飞书入口已能触发 OpenClaw；`99991672` contact 权限仅作为非阻断告警。 |
| 白名单工具执行 | verified | OpenClaw agent 只能调用已登记 `s100p_run_probe` 工具；非白名单执行已做负向验证。 |
| NAS workspace | verified | TS-264C NFS workspace 挂载到 `/mnt/nas/openclaw`，可写，作为所有报告和数据集落盘位置。 |
| ROS2 状态查询 | verified | 可读 node/topic/service 状态。 |
| ROS bag 采集 | verified | start/status/stop self-test、命名采集 policy、一次 300 秒人工批准 named capture 均已通过。 |
| 浏览器自动化 smoke | verified | Headless Chromium 截图写入 NAS，PNG 校验通过。 |
| 稳定性采样 | doing | 78 snapshots、25.15h、0 failed runner events；仍需达到 168h。 |
| Sandbox/runtime 隔离 | blocked | 当前无 Docker/Podman/runc runtime，需要安装或明确排除第一版 baseline。 |

结论：S100P 当前适合替代 PC 的“常驻入口、工具执行和机器人/NAS 侧自动化”角色，不适合作为 PC 桌面体验的完全替代。它的价值在于低功耗常驻、断电/重启后恢复、靠近机器人数据源、把证据持续写入 NAS。

## Baseline B：AI NAS / OpenClaw NAS 能力抄作业进展

| AI NAS 常见能力 | 当前实现 | 状态 |
| --- | --- | --- |
| 统一 workspace | `/mnt/nas/openclaw` 作为报告、日志、数据集、索引根目录 | verified |
| 文档索引/每日摘要 | deterministic document index + daily summary | verified |
| 图片检索/caption | metadata caption + JSONL index；semantic vision readiness 仍缺本地模型 | doing |
| Dream 7B / 本地 DLM | runtime 候选存在，但 model files 为 0 | blocked_no_model |
| 日志诊断 | 从 NAS logs 生成错误摘要、关键匹配和建议 | verified |
| 机器人数据集管理 | ROS bag + `DATASET_CARD.md` 已写 NAS | verified |
| 实验/周报生成 | 从 NAS reports/logs/datasets 汇总 Markdown report | verified |
| 设备只读状态 | Home Assistant read-only preflight 已有，但缺 URL/token | doing |
| 低风险控制 | disabled-by-default policy ready，enabled=0，executed=0 | doing |
| 安全审计/服务收敛 | security audit、decision pack、execution preflight 均已有 | doing |

## 当前最重要的证据文件

```text
Stability summary:
/mnt/nas/openclaw/reports/stability/stability_summary_20260529-192504.md

Overnight summary:
/mnt/nas/openclaw/reports/baseline-status/overnight_baseline_20260529-162329_summary.md

Gap decision:
/mnt/nas/openclaw/reports/baseline-status/baseline_gap_decision_20260529-193407.md

Baseline roll-up:
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260529-193407.md

Dream 7B readiness:
/mnt/nas/openclaw/reports/models/dream7b_readiness_20260529-155315.md

B-010 execution preflight:
/mnt/nas/openclaw/reports/security/service_execution_preflight_20260529-191608.md
```

## 不能夸大的点

- A-010 还没有 7x24 验收，只是 25.15h 的 clean collecting。
- Dream 7B 还没有部署成功；当前结论是有 runtime 候选但没有模型文件。
- B-008 没有真实 Home Assistant 状态读取，因为缺 URL/token。
- B-009 没有执行任何控制动作，因为没有 reviewed action allowlist 和审批记录。
- B-010 没有执行服务关闭或防火墙修改，因为 confirmation config 仍缺失。

## 下一步

1. 让 A-010 持续跑到 168h，再生成最终稳定性验收摘要。
2. 若 Dream 7B 进入第一版 baseline，挂载或安装模型文件后跑 bounded local inference smoke test。
3. 若要做设备状态，提供 Home Assistant URL/token，只允许 `GET /api/` 和 `GET /api/states`。
4. 若要做低风险控制，先补 reviewed action allowlist、确认语句和 audit retention。
5. 若要收敛服务暴露面，先填写 `service_convergence_confirmations.json`，再跑 execution preflight；没有确认前不执行 `systemctl disable` 或防火墙命令。
