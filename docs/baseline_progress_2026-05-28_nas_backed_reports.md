# Baseline Progress: NAS-backed Logs, Reports, And Stability Evidence

Date: 2026-05-28

本文记录 A-003 持久化 NFS 挂载验证后，把 B-005、B-007、A-010 从本地
workspace fallback 推进到 `/mnt/nas/openclaw` 的实测结果。

## Verdict

| Baseline | 当前状态 | 证据 |
| --- | --- | --- |
| B-005 日志分析助手 | verified | `log_diagnose.sh` 已读取 NAS 上的 Windows link-check JSONL，并生成失败模式、近期匹配和建议检查命令。 |
| B-007 周报/实验报告生成 | doing | NAS-backed Markdown 报告已生成；但 NAS 内文档索引、浏览器截图、ROS bag、dataset card 还需要继续填充。 |
| A-010 7x24 稳定性测试 | doing | NAS-backed snapshot 和 summary 已生成，当前 verdict 为 `collecting`，还不是 7 天验收结论。 |

## Inputs

Windows 开机链路检测日志已复制到 NAS：

```text
/mnt/nas/openclaw/logs/windows-link-check/pc_link_check_2026-05-28.jsonl
```

探针脚本同步到 S100P：

```text
/root/.openclaw/workspace/scripts/probes/log_diagnose.sh
/root/.openclaw/workspace/scripts/probes/stability_snapshot_probe.sh
/root/.openclaw/workspace/scripts/probes/stability_summary_probe.sh
/root/.openclaw/workspace/scripts/probes/experiment_report_probe.sh
```

运行入口：

```bash
LOG_REPORT=$(bash scripts/probes/log_diagnose.sh /mnt/nas/openclaw/logs /mnt/nas/openclaw/logs/probes)
SNAP_REPORT=$(bash scripts/probes/stability_snapshot_probe.sh /mnt/nas/openclaw/logs/probes)
SUMMARY_REPORT=$(bash scripts/probes/stability_summary_probe.sh /mnt/nas/openclaw/logs/probes /mnt/nas/openclaw/reports/stability)
EXP_REPORT=$(env OPENCLAW_WORKSPACE_DIR=/mnt/nas/openclaw bash scripts/probes/experiment_report_probe.sh /mnt/nas/openclaw/reports/experiments)
```

## B-005 Log Diagnosis

输出：

```text
/mnt/nas/openclaw/logs/probes/log_diagnosis_20260528-181546.md
```

摘要：

```text
log_dir: /mnt/nas/openclaw/logs
total_matches: 14
exception/fatal: 1
generic error/failed: 13
permission denied: 12
timeout: 1
```

主要发现：

- 绝大多数匹配来自飞书 `99991672` contact 权限提示；该问题不阻断消息收发，仍作为 follow-up。
- 检测到一次旧版托盘 GUI 的 `不能对 Null 值表达式调用方法` 异常；后续版本已经改为隐藏托盘启动和按需打开窗口。
- 报告给出了后续检查命令，包括 gateway user service、OpenClaw 日志、监听端口和 NAS mount。

B-005 可以标为 `verified`：它已经能以 NAS 日志目录为输入，输出失败摘要、关键错误和建议命令。

## A-010 Stability Evidence

Snapshot 输出：

```text
/mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-181546.md
```

关键字段：

```text
Gateway status: active-listening
NAS workspace: mounted
Reboot records visible: 11
Kernel OOM matches in last 24h: 0
Gateway error-like log matches in last 24h: 0
NAS disk: 169.254.110.209:/OpenClawWorkspace mounted at /mnt/nas/openclaw
```

Summary 输出：

```text
/mnt/nas/openclaw/reports/stability/stability_summary_20260528-181555.md
```

关键字段：

```text
Snapshot count: 1
Elapsed hours: 0.00
Observed Gateway Statuses: active-listening
Observed NAS Statuses: mounted
Verdict: collecting
```

A-010 仍保持 `doing`。当前已经证明采样和汇总可以落到 NAS，但 7x24 验收需要至少
168 小时样本，并且趋势保持干净。

## B-007 Experiment Report

先修正 `experiment_report_probe.sh` 的文案：当
`OPENCLAW_WORKSPACE_DIR=/mnt/nas/openclaw` 时，报告不再误写
`NAS-backed acceptance is pending`，而是标记：

```text
nas_backed_mode: verified
```

复跑输出：

```text
/mnt/nas/openclaw/reports/experiments/experiment_report_20260528-181734.md
```

摘要：

```text
workspace: /mnt/nas/openclaw
nas_backed_mode: verified
Probe reports: 2
Experiment reports: 2
Browser smoke screenshots: 0
Document indexes: 0
ROS bag datasets: 0
Dataset cards: 0
```

报告中的当前阻塞项已经改为：

```text
NAS-backed report generation is verified; remaining acceptance needs richer NAS artifacts from B-002, A-007, A-009, and B-004.
```

B-007 继续保持 `doing`：生成链路已经在 NAS 上跑通，但“像高价位 AI NAS 一样自动产出周报”的验收还需要把文档索引、浏览器截图、ROS bag 和 dataset card 填进去。

## Baseline Impact

- B-005: `verified`
- B-007: remains `doing`, NAS-backed report generation path verified
- A-010: remains `doing`, NAS-backed collection started
- 下一步优先级：B-002 文档索引、A-007 浏览器截图、A-009 ROS bag session、B-004 dataset card 全部切到 `/mnt/nas/openclaw`
