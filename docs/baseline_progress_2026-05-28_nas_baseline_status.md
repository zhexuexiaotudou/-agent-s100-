# Baseline Progress: NAS-backed Baseline Status Roll-up

Date: 2026-05-28

本文记录 `baseline_status_probe.sh` 从本地 workspace 汇总推进到 NAS-backed 汇总后的最新状态。它的作用是给当前两条 baseline 生成总览：哪些已经有 NAS 证据，哪些仍是 smoke baseline，哪些必须等待用户或外部平台决策。

## Latest Output

```text
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-225904.md
```

Script fixes already in place:

- When `workspace=/mnt/nas/openclaw`, the tool allowlist and GitHub marker files can fall back to `/root/.openclaw/workspace`.
- The roll-up no longer hard-codes stale NAS status; it derives status from the current NAS mount and latest NAS reports.
- `B-004` dataset card, `B-005` log diagnosis, and `B-007` experiment report are reported separately.

## Current System Summary

```text
OpenClaw Gateway: active-listening
Stability sampler timer: active
NAS workspace: mounted
Allowlisted tool count: 21
Progress docs: 19
Probe reports: 26
Workspace reports: 26
Dataset cards: 1
Image caption JSONL indexes: 1
Document daily summaries: 1
Stability snapshots: 10
```

## Latest NAS Evidence

```text
Stability snapshot: /mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-223322.md
Stability summary: /mnt/nas/openclaw/reports/stability/stability_summary_20260528-223427.md
Document index: /mnt/nas/openclaw/reports/document_index_20260528-182111.md
Document daily summary: /mnt/nas/openclaw/reports/daily-summary/document_daily_summary_20260528-184329.md
Browser smoke: /mnt/nas/openclaw/reports/browser-smoke/browser_smoke_20260528-182111.md
Log diagnosis: /mnt/nas/openclaw/logs/probes/log_diagnosis_20260528-181546.md
Image caption index: /mnt/nas/openclaw/reports/image-captions/image_caption_index_20260528-182530.md
Experiment report: /mnt/nas/openclaw/reports/experiments/experiment_report_20260528-184444.md
Security audit: /mnt/nas/openclaw/logs/probes/security_audit_20260528-182530.md
Service policy: /mnt/nas/openclaw/logs/probes/service_policy_20260528-183619.md
ROS bag session: /mnt/nas/openclaw/logs/probes/rosbag_session_20260528-182117.md
ROS bag capture policy: /mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.md
Dataset card: /mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117/DATASET_CARD.md
Home Assistant status: /mnt/nas/openclaw/logs/probes/home_assistant_status_20260528-183050.md
Control action policy: /mnt/nas/openclaw/logs/probes/control_action_policy_20260528-225702.md
GitHub issue: https://github.com/zhexuexiaotudou/-agent-s100-/issues/2
GitHub PR: https://github.com/zhexuexiaotudou/-agent-s100-/pull/3 review_id=4367969950
```

## Baseline Meaning

Already backed by NAS evidence:

- A-003 NAS workspace mount
- A-007 browser smoke screenshot
- A-009 bounded ROS bag session
- A-009 named capture policy
- A-010 stability snapshot and summary collection
- B-002 document index and deterministic daily summary
- B-003 metadata image caption index
- B-004 dataset card
- B-005 log diagnosis
- B-007 experiment report
- B-008 Home Assistant read-only preflight
- B-009 disabled-by-default control action policy preflight
- B-010 security audit and service policy plan

Still requiring later decisions or external information:

- A-006 Docker/Podman/runc sandbox runtime or explicit drop decision
- A-009 one operator-approved named capture under the policy
- A-010 168-hour stability sample window
- B-003 whether semantic vision captioning belongs in the first baseline
- B-008 Home Assistant URL/token
- B-009 reviewed real entity/action entries plus request/approve/execute audit
- B-010 NFS/RPC, x11vnc, iiod, and SSH keep/disable/firewall decisions

## Current Use

This roll-up is suitable as the current baseline overview in the teacher-facing report. It is not the final acceptance report. It says the S100P + NAS core chain has moved from local fallback to NAS-backed smoke baseline, while long-term stability, sandbox runtime, service hardening, and real data filling remain in progress.
