# Baseline Progress: NAS-backed Baseline Status Roll-up

Date: 2026-05-28

本文记录 `baseline_status_probe.sh` 从本地 workspace 汇总推进到 NAS-backed 汇总。
它的作用是给当前两条 baseline 生成一份总览：哪些已经有 NAS 证据，哪些还只是
smoke baseline，哪些必须等用户或外部平台决策。

## Output

```text
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-183640.md
```

脚本修正：

- 当 `workspace=/mnt/nas/openclaw` 时，工具白名单和 GitHub marker 从
  `/root/.openclaw/workspace` fallback 读取。
- 汇总表不再硬编码“NAS 未挂载”旧状态，而是按 NAS 上最新报告自动判断。
- `B-004` dataset card、`B-005` log diagnosis、`B-007` experiment report
  被单独列入总览。

## Current System Summary

```text
OpenClaw Gateway: active-listening
Stability sampler timer: active
NAS workspace: mounted
Allowlisted tool count: 19
Progress docs: 19
Probe reports: 16
Workspace reports: 16
Dataset cards: 1
Image caption JSONL indexes: 1
Stability snapshots: 1
```

## Latest NAS Evidence

```text
Stability snapshot: /mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-181546.md
Stability summary: /mnt/nas/openclaw/reports/stability/stability_summary_20260528-181555.md
Document index: /mnt/nas/openclaw/reports/document_index_20260528-182111.md
Browser smoke: /mnt/nas/openclaw/reports/browser-smoke/browser_smoke_20260528-182111.md
Log diagnosis: /mnt/nas/openclaw/logs/probes/log_diagnosis_20260528-181546.md
Image caption index: /mnt/nas/openclaw/reports/image-captions/image_caption_index_20260528-182530.md
Experiment report: /mnt/nas/openclaw/reports/experiments/experiment_report_20260528-182242.md
Security audit: /mnt/nas/openclaw/logs/probes/security_audit_20260528-182530.md
Service policy: /mnt/nas/openclaw/logs/probes/service_policy_20260528-183619.md
Service hardening plan: /mnt/nas/openclaw/logs/probes/service_hardening_plan_20260528-183619.md
ROS bag session: /mnt/nas/openclaw/logs/probes/rosbag_session_20260528-182117.md
Dataset card: /mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117/DATASET_CARD.md
GitHub issue: https://github.com/zhexuexiaotudou/-agent-s100-/issues/2
GitHub PR: https://github.com/zhexuexiaotudou/-agent-s100-/pull/3 review_id=4367969950
Home Assistant status: /mnt/nas/openclaw/logs/probes/home_assistant_status_20260528-183050.md
Control action policy: /mnt/nas/openclaw/logs/probes/control_action_policy_20260528-183050.md
```

## Roll-up Meaning

已经具备 NAS-backed 证据的项：

- A-003 NAS workspace mount
- A-007 browser smoke screenshot
- A-009 bounded ROS bag session
- A-010 stability snapshot/summary collection
- B-002 document index
- B-003 metadata image caption index
- B-004 dataset card
- B-005 log diagnosis
- B-007 experiment report
- B-008 Home Assistant read-only preflight
- B-009 control action policy preflight
- B-010 security audit

仍需要后续决策或外部信息的项：

- A-005 broad exec 的平台级阻断证据
- A-006 Docker/Podman/runc sandbox runtime 或 drop 决策
- A-009 长时间命名采集策略
- A-010 168 小时稳定性样本
- B-002 每日摘要
- B-003 semantic vision caption 是否纳入第一版
- B-008 Home Assistant URL/token
- B-009 control action allowlist、二次确认和审计策略
- B-010 NFS/RPC、x11vnc、iiod、SSH 的 keep/disable/firewall 策略

## Current Use

这份 roll-up 适合放在老师汇报里作为“当前 baseline 总览”。它不是最终验收报告；
它说明 S100P + NAS 的核心链路已经从本地 fallback 推进到 NAS-backed smoke baseline，
但长期稳定性、sandbox、服务收敛和真实数据填充仍在进行。
