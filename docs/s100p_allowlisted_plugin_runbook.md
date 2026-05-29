# S100P Allowlisted OpenClaw Plugin Runbook

This runbook is the next A-005 hardening step after exec approvals were shown not to block the tested `openclaw agent --agent main` path.

## Purpose

Expose a narrow OpenClaw tool instead of asking the agent to call broad `system.run`.

Plugin:

```text
openclaw-plugins/s100p-allowlisted-tools
```

Tool:

```text
s100p_run_probe
```

Allowed `tool_id` values:

```text
openclaw_status_probe
nas_discovery_probe
ros2_status_probe
sandbox_status_probe
security_audit_probe
service_policy_probe
service_hardening_plan_probe
service_convergence_decision_probe
service_execution_preflight_probe
stability_snapshot_probe
stability_summary_probe
image_caption_probe
vision_caption_readiness_probe
dream7b_readiness_probe
home_assistant_status_probe
control_action_policy_probe
browser_smoke_probe
rosbag_snapshot_probe
rosbag_session_probe
rosbag_capture_policy_probe
experiment_report_probe
baseline_status_probe
baseline_gap_decision_probe
log_diagnose
index_documents
document_daily_summary_probe
```

The plugin internally calls:

```text
/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh
```

It never accepts arbitrary shell text or arbitrary script paths.

## Install On S100P

Sync the plugin to:

```text
/root/.openclaw/workspace/plugins/s100p-allowlisted-tools
```

Then install:

```bash
PATH=/root/.local/lib/node-v24.16.0-linux-arm64/bin:/root/.npm-global/bin:$PATH \
openclaw plugins install /root/.openclaw/workspace/plugins/s100p-allowlisted-tools
```

Restart the gateway afterward.

## Acceptance

- `openclaw plugins list` shows `s100p-allowlisted-tools` loaded.
- Asking the agent to use `s100p_run_probe` with `tool_id=ros2_status_probe` returns a report path under `/root/.openclaw/workspace/logs/probes`.
- Asking the agent to use `tool_id=log_diagnose` returns a diagnosis report under `/root/.openclaw/workspace/logs/probes`.
- Asking the agent to use `tool_id=index_documents` returns an index report under `/root/.openclaw/workspace/reports`.
- Asking for any unlisted `tool_id` is rejected by schema or plugin validation.
- The broad `system.run` route must not be considered fixed until a negative test proves non-allowlisted commands cannot execute.

## 2026-05-27 Install Attempt

The plugin draft was synced to the S100P and passed Node syntax checking:

```text
node --check index.js
```

The first `openclaw plugins install` attempt failed validation:

```text
Config invalid
Problem:
  - plugins: plugin: plugin manifest requires configSchema
```

After adding empty `configSchema` fields, OpenClaw still reported the same validation failure. The failed install also created:

```text
/root/.openclaw/extensions/s100p-allowlisted-tools
```

That draft extension directory caused `openclaw config validate` to fail because plugin discovery walked dependency package manifests under `node_modules`. The directory was removed, and config validation returned to:

```text
Config valid: ~/.openclaw/openclaw.json
```

The package was then changed to a zero-dependency plugin that imports the board's installed OpenClaw SDK directly and does not vendor `node_modules`. That version installed and loaded successfully:

```text
Installed plugin: s100p-allowlisted-tools
S100P Allowlisted Tools | s100p-allowlisted-tools | loaded
```

`plugins.allow` was set to an explicit list that includes `s100p-allowlisted-tools`, so this non-bundled plugin no longer relies on auto-load discovery.

Agent validation showed a real tool call:

```text
toolCall name: s100p_run_probe
arguments: {"tool_id":"ros2_status_probe"}
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-033810.md
```

After setting `tools.exec.security=deny`, the narrow plugin still worked:

```text
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-033957.md
nodes: 0
topics: 2
services: 0
```

Plugin-level invalid input validation passed:

```text
INVALID_TOOL_REJECT_OK
tool_id must be one of: openclaw_status_probe, ros2_status_probe
```

Important: broad local command execution is still not blocked by OpenClaw's `tools.exec.security=deny` in the tested `openclaw agent --agent main` path. This plugin is a narrow approved path, not a complete platform-level fix for broad `system.run`.

## 2026-05-27 Docs And Logs Extension

The plugin was extended to expose the two B-series read-only workflows through the same narrow tool boundary:

```text
log_diagnose
index_documents
```

The updated local plugin validates exactly these IDs:

```text
openclaw_status_probe
nas_discovery_probe
ros2_status_probe
sandbox_status_probe
security_audit_probe
service_policy_probe
service_hardening_plan_probe
service_convergence_decision_probe
service_execution_preflight_probe
stability_snapshot_probe
stability_summary_probe
image_caption_probe
vision_caption_readiness_probe
dream7b_readiness_probe
home_assistant_status_probe
control_action_policy_probe
browser_smoke_probe
rosbag_snapshot_probe
rosbag_session_probe
rosbag_capture_policy_probe
experiment_report_probe
baseline_status_probe
baseline_gap_decision_probe
log_diagnose
index_documents
document_daily_summary_probe
```

Board evidence through real `s100p_run_probe` tool calls:

```text
tool_id: index_documents
report: /root/.openclaw/workspace/reports/document_index_20260527-034707.md
indexed_files: 2
input: /root/.openclaw/workspace/documents
files: baseline-note.md, robot-log.txt
```

```text
tool_id: log_diagnose
report: /root/.openclaw/workspace/logs/probes/log_diagnosis_20260527-034730.md
generic error/failed: 3
connection refused: 1
exception/fatal: 1
permission denied: 1
```

This verifies B-002 and B-005 against the local workspace fallback path. The NAS-backed path is still pending until `/mnt/nas/openclaw` is mounted.

## 2026-05-27 Sandbox Status Extension

The plugin was extended with one more read-only probe:

```text
sandbox_status_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: 4dc92c37-5c14-4095-8ca9-69bb93f5e4c8
tool_id: sandbox_status_probe
report: /root/.openclaw/workspace/logs/probes/sandbox_status_20260527-040824.md
runtime_available: no
isolation_verdict: blocked
```

This verifies the narrow plugin path for A-006 status collection. It does not verify sandbox isolation because the board currently has no Docker, Podman, or runc runtime available.

## 2026-05-27 Browser Smoke Extension

The plugin was extended with:

```text
browser_smoke_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: ba47a596-91af-4773-bad2-30d72bafc893
tool_id: browser_smoke_probe
report: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260527-042131.md
screenshot: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260527-042131.png
screenshot_status: captured
visible_marker: yes
verdict: ok
```

This verifies the A-007 local workspace fallback path. NAS-backed screenshot output still waits for `/mnt/nas/openclaw`.

## 2026-05-27 ROS Bag Snapshot Extension

The plugin was extended with:

```text
rosbag_snapshot_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: bb64fe15-5e85-43a5-8de4-0d6c2036f8f4
tool_id: rosbag_snapshot_probe
report: /root/.openclaw/workspace/logs/probes/rosbag_snapshot_20260527-043114.md
bag_dir: /root/.openclaw/workspace/robot_datasets/rosbag_snapshot_20260527-043114
topics_requested: /rosout /parameter_events
metadata_exists: yes
verdict: ok
```

This verifies the A-009 local workspace fallback for bounded ROS bag snapshots. It is not the final long-running start/stop capture flow.

## 2026-05-27 Experiment Report Extension

The plugin was extended with:

```text
experiment_report_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: 274ef269-05fd-406c-a0b6-64e756b77530
tool_id: experiment_report_probe
report: /root/.openclaw/workspace/reports/experiments/experiment_report_20260527-044552.md
Probe reports: 15
Experiment reports: 6
Browser smoke screenshots: 3
Document indexes: 2
ROS bag datasets: 5
Dataset cards: 2
```

This verifies the B-007 local workspace fallback for experiment report generation. NAS-backed report output still waits for `/mnt/nas/openclaw`.

## 2026-05-27 Security Audit Extension

The plugin was extended with:

```text
security_audit_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: c9778552-a4d7-494e-b325-e3eab7906086
runId: e08be89a-f0ee-43d2-8b4a-cf8ab92a7ff3
tool_id: security_audit_probe
report: /root/.openclaw/workspace/logs/probes/security_audit_20260527-045534.md
report: /root/.openclaw/workspace/logs/probes/security_audit_20260527-050149.md
OpenClaw config validation: pass
Gateway exposure: pass
Tavily plugin: pass
S100P allowlisted plugin: pass
Non-loopback listeners: warn
Non-loopback listener categories: nfs-rpc, admin, remote-desktop, hardware-daemon
NAS workspace mount: warn
Workspace secret scan: pass
```

This verifies the B-010 local workspace fallback for redacted security audits and classified listener review. Final B-010 acceptance still needs NAS-backed report output and a final keep/close decision for exposed non-loopback services.

## 2026-05-27 Service Policy Extension

The plugin was extended with:

```text
service_policy_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: e71ee679-f023-4e7f-97b5-3a2fec8e9c58
tool_id: service_policy_probe
report: /root/.openclaw/workspace/logs/probes/service_policy_20260527-050558.md
OpenClaw Gateway: loopback, keep
SSH: present, keep for trusted management
NFS/RPC server stack: present, disable after confirming S100P is not exporting NFS shares
x11vnc: present, disable after confirming RDK Studio terminal/file access is enough
iiod: present, keep if needed; otherwise disable or firewall
```

This makes the B-010 hardening decision explicit without changing board services.

## 2026-05-27 Stability Snapshot Extension

The plugin was extended with:

```text
stability_snapshot_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: 814bec32-5de1-4b0d-8ed1-750d34ce01dd
tool_id: stability_snapshot_probe
report: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260527-051515.md
Gateway status: active-listening
NAS workspace: not_mounted
Kernel OOM matches in last 24h: 0
Gateway error-like log matches in last 24h: 0
```

This verifies A-010 snapshot collection, not the full 7-day endurance run.

## 2026-05-27 ROS Bag Session Extension

The plugin was extended with:

```text
rosbag_session_probe
```

Board evidence through a real OpenClaw agent turn:

```text
runId: 0256a6af-2384-4456-bc4e-cb3a244761f2
tool_id: rosbag_session_probe
report: /root/.openclaw/workspace/logs/probes/rosbag_session_20260527-052005.md
start_status: started
status_after_start: running
stop_status: sent_sigint
metadata_exists: yes
verdict: ok
```

## 2026-05-27 Stability Summary Extension

The plugin was extended with:

```text
stability_summary_probe
```

Board evidence through the allowlist runner:

```text
report: /root/.openclaw/workspace/reports/stability/stability_summary_20260527-053046.md
Snapshot count: 5
Elapsed hours: 0.22
Verdict: collecting
```

## 2026-05-27 Image Caption Extension

The plugin was extended with:

```text
image_caption_probe
```

Board evidence through the allowlist runner:

```text
report: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-053923.md
jsonl: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-053923.jsonl
Image records: 1
caption: Image file smoke red dot, 1x1px
dimensions: 1x1
```

Board evidence through a real OpenClaw agent turn:

```text
runId: 542ea1c1-d708-48b3-9291-d97d1dba68f2
tool_id: image_caption_probe
report: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-054009.md
jsonl: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-054009.jsonl
Image records count: 1
```

## 2026-05-27 Baseline Status Extension

The plugin was extended with:

```text
baseline_status_probe
```

Board evidence through the allowlist runner:

```text
report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-054653.md
Allowlisted tool count: 15
Progress docs: 15
NAS workspace: not_mounted
```

Board evidence through a real OpenClaw agent turn:

```text
runId: a0c43c05-a929-4a2a-9a94-2a3305139a52
tool_id: baseline_status_probe
report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-054753.md
Allowlisted tool count: 15
Progress docs: 15
NAS workspace status: not_mounted
```

## 2026-05-27 NAS Discovery Extension

The plugin was extended with:

```text
nas_discovery_probe
```

Board evidence through the allowlist runner:

```text
report: /root/.openclaw/workspace/logs/probes/nas_discovery_20260527-055322.md
/mnt/nas/openclaw: not_mounted
Neighbor entries: 1
mount.cifs: ok
mount.nfs: ok
```

Board evidence through a real OpenClaw agent turn:

```text
runId: 84bd443b-b882-437b-9c88-c5e891c7d01c
tool_id: nas_discovery_probe
report: /root/.openclaw/workspace/logs/probes/nas_discovery_20260527-055418.md
/mnt/nas/openclaw: not_mounted
mount.cifs: ok
mount.nfs: ok
Neighbor entries: 1
```

## 2026-05-27 Service Hardening Plan Extension

The plugin was extended with:

```text
service_hardening_plan_probe
```

Board evidence through the allowlist runner:

```text
report: /root/.openclaw/workspace/logs/probes/service_hardening_plan_20260527-060031.md
NFS/RPC server stack: present, disable-if-client-only
x11vnc: present, disable-if-unused
iiod: present, keep-or-firewall
```

Board evidence through a real OpenClaw agent turn:

```text
runId: 154148d8-0224-45ae-95db-d4cf7e06a841
tool_id: service_hardening_plan_probe
report: /root/.openclaw/workspace/logs/probes/service_hardening_plan_20260527-060121.md
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

Board evidence through a real OpenClaw agent turn:

```text
runId: f499de43-4ce1-4818-a758-085d14af7d57
tool_id: stability_summary_probe
report: /root/.openclaw/workspace/reports/stability/stability_summary_20260527-053412.md
Snapshot count: 5
Max kernel OOM matches in last 24h: 0
Max Gateway error-like matches in last 24h: 0
Verdict: collecting
```

This verifies the A-009 local start/status/stop self-test path. It is still bounded and limited to low-risk ROS status topics.

## 2026-05-28 ROS Bag Capture Policy Extension

The plugin was extended with:

```text
rosbag_capture_policy_probe
```

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.md
policy_json: /mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.json
verdict: draft_policy_ready
approved topics detected: /rosout, /parameter_events
command-like topics detected: none
```

After restarting `openclaw-gateway.service`, board evidence through a real OpenClaw agent turn:

```text
tool_id: rosbag_capture_policy_probe
report: /root/.openclaw/workspace/logs/probes/rosbag_capture_policy_20260528-224912.md
verdict: draft_policy_ready
approved topics detected: /rosout, /parameter_events
command-like topics detected: none
```

This closes the A-009 named-capture policy gap without launching a long recording. Final A-009 verification still needs one operator-approved named capture under this policy.

## 2026-05-28 B-003 Semantic Vision Readiness Extension

The plugin was extended with:

```text
vision_caption_readiness_probe
```

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/image-captions/vision_caption_readiness_20260528-230810.md
verdict: blocked_no_semantic_runtime
image files: 1
local model-like files: 0
semantic runtime: no
```

After restarting `openclaw-gateway.service`, board evidence through a real
OpenClaw agent turn:

```text
tool_id: vision_caption_readiness_probe
report: /root/.openclaw/workspace/reports/image-captions/vision_caption_readiness_20260528-230826.md
verdict: blocked_no_semantic_runtime
image count: 1
local model-like file count: 0
semantic runtime: no
```

This verifies the narrow tool path for B-003 semantic readiness. It does not
verify semantic caption generation; the board has no detected local vision model
files yet.

## 2026-05-29 Dream 7B / Local DLM Readiness Extension

The plugin was extended with:

```text
dream7b_readiness_probe
```

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_readiness_20260529-155315.md
verdict: blocked_no_model
memory total: 21.3 GiB
runtime summary: llama.cpp,torch-transformers
model-like files: 0
dream-named files: 0
```

Board evidence through a real OpenClaw agent turn:

```text
tool_id: dream7b_readiness_probe
report: /root/.openclaw/workspace/reports/models/dream7b_readiness_20260529-160626.md
verdict: blocked_no_model
runtime summary: llama.cpp, torch-transformers
model file count: 0
memory total: 21.3 GiB
```

This verifies the narrow tool path for the Dream 7B deployment gate. It does not
verify Dream 7B deployment or inference; model files are absent from the approved
model directories.

## 2026-05-29 Dream 7B Smoke Gate Extension

The plugin and allowlist runner now include:

```text
dream7b_smoke_probe
```

This is the second gate after readiness. It requires
`/root/.openclaw/workspace/config/dream7b_deployment.json` or another approved
config path, and the configured model must live under an approved local model
root. It runs one bounded local inference and writes a report; if config/model
files are missing, it reports a blocked state and does not download anything.

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_smoke_20260529-195131.md
verdict: blocked_no_config
```

Board evidence through a real OpenClaw agent turn:

```text
tool_id: dream7b_smoke_probe
report: /root/.openclaw/workspace/reports/models/dream7b_smoke_20260529-195337.md
verdict: blocked_no_config
```

## 2026-05-29 Teacher Briefing Extension

The plugin was extended with:

```text
teacher_baseline_briefing_probe
```

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_20260529-200427.md
```

Board evidence through a real OpenClaw agent turn:

```text
tool_id: teacher_baseline_briefing_probe
report: /root/.openclaw/workspace/reports/teacher/teacher_baseline_briefing_20260529-200724.md
```

This verifies the narrow tool path for regenerating a teacher-facing two-baseline
briefing from the latest NAS evidence.

## 2026-05-29 Baseline Acceptance Extension

The plugin was extended with:

```text
baseline_acceptance_probe
```

This produces a read-only acceptance matrix for every A/B baseline item. It is
intended for final completion audits and does not execute controls, service
changes, firewall changes, or model inference.

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_20260529-202537.md
overall: not_ready
```

Board evidence through a real OpenClaw agent turn:

```text
tool_id: baseline_acceptance_probe
report: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260529-202642.md
overall: not_ready
```

## 2026-05-29 Baseline Acceptance Trend Extension

The plugin was extended with:

```text
baseline_acceptance_trend_probe
```

This reads saved acceptance JSON snapshots and reports whether any A/B baseline
item changed status across time. It is read-only and intended for long-running
A-010 monitoring.

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_trend_20260529-203510.md
source_count: 2
latest_overall: not_ready
```

Board evidence through a real OpenClaw agent turn:

```text
tool_id: baseline_acceptance_trend_probe
report: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_trend_20260529-203703.md
source_count: 2
latest_overall: not_ready
```

## 2026-05-28 B-010 Service Convergence Decision Extension

The plugin was extended with:

```text
service_convergence_decision_probe
```

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/security/service_convergence_decision_20260528-235327.md
Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

After updating the actual loaded extension copy at
`/root/.openclaw/extensions/s100p-allowlisted-tools/index.js` and restarting
`openclaw-gateway.service`, board evidence through a real OpenClaw agent turn:

```text
tool_id: service_convergence_decision_probe
report: /root/.openclaw/workspace/reports/security/service_convergence_decision_20260528-234753.md
Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

This verifies the narrow tool path for the B-010 decision pack. It deliberately
does not stop services or edit firewall rules.
