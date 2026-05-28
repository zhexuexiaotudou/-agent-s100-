# 工具执行白名单

第一版 OpenClaw + S100P 不允许 agent 随意执行 shell。工具执行应从只读探针开始，再逐步开放采集类和写入类脚本。

## 白名单目录

```text
scripts/probes/
scripts/robot/
```

第一阶段只开放 `scripts/probes/`。这些脚本必须满足：

- 默认只读，不修改系统配置。
- 输出写入 `/tmp` 或 `/mnt/nas/openclaw/logs/probes`。
- 拒绝危险路径，例如 `/`、`/root`、`/home`、`/mnt/nas`。
- 不打印 token、API key、SSH key 或飞书 Secret。

## 当前候选脚本

| 脚本 | 类型 | 默认输出 | 用途 |
| --- | --- | --- | --- |
| `scripts/probes/openclaw_status_probe.sh` | 只读 | `/tmp/openclaw-probes`，NAS 挂载后优先 `/mnt/nas/openclaw/logs/probes` | 采集 OpenClaw、网络、Feishu/Tavily 配置摘要和 NAS 挂载状态 |
| `scripts/probes/log_diagnose.sh` | 只读 | `/tmp/openclaw-probes`，NAS 挂载后优先 `/mnt/nas/openclaw/logs/probes` | 从日志目录生成错误摘要、关键匹配和建议检查命令 |
| `scripts/probes/index_documents.sh` | 只读 | `/tmp/openclaw-probes`，NAS 挂载后优先 `/mnt/nas/openclaw/reports` | 对文本类文档生成路径、大小、修改时间、SHA256 和 preview 索引 |
| `scripts/probes/document_daily_summary_probe.sh` | 只读 | `/mnt/nas/openclaw/reports/daily-summary` | 对 NAS 文档生成每日 metadata summary 和 JSON 摘要 |
| `scripts/probes/sandbox_status_probe.sh` | 只读 | `/tmp/openclaw-probes`，NAS 挂载后优先 `/mnt/nas/openclaw/logs/probes` | 采集 Docker/Podman/runc、服务、包、namespace 和 cgroup 状态 |
| `scripts/probes/image_caption_probe.sh` | 只读 | `/root/.openclaw/workspace/reports/image-captions`，NAS 挂载后优先 `/mnt/nas/openclaw/reports` | 对图片生成 metadata caption、尺寸、hash 和 JSONL 索引 |
| `scripts/probes/browser_smoke_probe.sh` | 只读 | `/root/.openclaw/workspace/reports/browser-smoke`，NAS 挂载后优先 `/mnt/nas/openclaw/reports` | 打开本地测试页、截图并生成浏览器 smoke 报告 |
| `scripts/probes/rosbag_snapshot_probe.sh` | 采集 | `/root/.openclaw/workspace/robot_datasets`，NAS 挂载后优先 `/mnt/nas/openclaw/robot_datasets` | 对低风险 ROS 状态 topic 做短时 rosbag snapshot，并生成报告 |

## 执行入口

第一版不要直接让 OpenClaw 调任意 shell。统一入口是：

```bash
scripts/run_allowlisted_tool.sh <tool_id> [args]
```

当前只允许：

```bash
scripts/run_allowlisted_tool.sh openclaw_status_probe
scripts/run_allowlisted_tool.sh openclaw_status_probe /tmp/openclaw-probe-test
scripts/run_allowlisted_tool.sh log_diagnose /tmp/openclaw
scripts/run_allowlisted_tool.sh index_documents /mnt/nas/openclaw/documents /mnt/nas/openclaw/reports
scripts/run_allowlisted_tool.sh document_daily_summary_probe /mnt/nas/openclaw/documents /mnt/nas/openclaw/reports/daily-summary
scripts/run_allowlisted_tool.sh sandbox_status_probe /root/.openclaw/workspace/logs/probes
scripts/run_allowlisted_tool.sh image_caption_probe /root/.openclaw/workspace/photos /root/.openclaw/workspace/reports/image-captions
scripts/run_allowlisted_tool.sh baseline_status_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
scripts/run_allowlisted_tool.sh browser_smoke_probe /root/.openclaw/workspace/reports/browser-smoke
scripts/run_allowlisted_tool.sh rosbag_snapshot_probe /root/.openclaw/workspace/robot_datasets /root/.openclaw/workspace/logs/probes
```

白名单清单同时记录在：

```text
scripts/tool_allowlist.json
```

## 验收命令

S100P 板端：

```bash
bash -n scripts/run_allowlisted_tool.sh
bash -n scripts/probes/openclaw_status_probe.sh
bash scripts/run_allowlisted_tool.sh list
bash scripts/run_allowlisted_tool.sh openclaw_status_probe /tmp/openclaw-probe-test
bash scripts/run_allowlisted_tool.sh log_diagnose /tmp/openclaw /tmp/openclaw-probe-test
bash scripts/run_allowlisted_tool.sh ../../etc/passwd
```

成功判据：

- 命令输出一个 `openclaw_status_*.txt` 路径。
- 报告中包含 `openclaw-gateway`、`openclaw config summary`、`nas mount`。
- 报告中不包含明文 API key、token 或 Secret。
- 非白名单 ID 必须被拒绝。

## 2026-05-27 验证记录

### NAS discovery

Additional allowlisted tool:

```text
nas_discovery_probe  Generate a passive/read-only NAS readiness report
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh nas_discovery_probe /root/.openclaw/workspace/logs/probes
```

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/nas_discovery_20260527-055322.md
OpenClaw runId: 84bd443b-b882-437b-9c88-c5e891c7d01c
OpenClaw report: /root/.openclaw/workspace/logs/probes/nas_discovery_20260527-055418.md
/mnt/nas/openclaw: not_mounted
mount.cifs: ok
mount.nfs: ok
Neighbor entries: 1
```

### 状态探针

在 S100P 板端通过 RDK Studio 后端执行临时目录 smoke test：

```text
MANIFEST_OK
openclaw_status_probe  Read-only OpenClaw/network/NAS status probe
REPORT=/tmp/openclaw-probe-test/openclaw_status_20260527-024239.txt
Tool is not allowlisted: ../../etc/passwd
ALLOWLIST_RUNNER_OK
```

验证覆盖：

- `scripts/run_allowlisted_tool.sh` 语法检查通过。
- `scripts/probes/openclaw_status_probe.sh` 语法检查通过。
- `scripts/tool_allowlist.json` 可解析，包含 `openclaw_status_probe`。
- 白名单 ID 可以运行并生成报告。
- 非白名单 ID 被拒绝。
- 报告检查未发现明文 Tavily key、API key、token 或 Secret。

### 日志诊断

在 S100P 板端通过临时 HTTP 只读服务拉取当前脚本后执行 smoke test：

```text
MANIFEST_LOG_OK
openclaw_status_probe  Read-only OpenClaw/network/NAS status probe
log_diagnose           Read-only log error summary report
REPORT=/tmp/openclaw-probe-test/log_diagnosis_20260527-024819.md
# Log Diagnosis
## Top Error Patterns
## Recent Matches
## Suggested Checks
- connection refused: 1
- exception/fatal: 1
- generic error/failed: 1
- permission denied: 1
Refusing log path outside approved directories: /root
LOG_DIAGNOSE_OK
```

验证覆盖：

- `log_diagnose` 已在 `scripts/tool_allowlist.json` 中登记。
- `scripts/probes/log_diagnose.sh` 语法检查通过。
- 示例日志能生成 Markdown 诊断报告。
- 报告包含错误模式、最近匹配和建议检查命令。
- 非批准日志路径 `/root` 被 runner 拒绝。
- 报告检查未发现明文 Tavily key、API key、token 或 Secret。

### 文档索引

在 S100P 板端通过临时 HTTP 只读服务拉取当前脚本后执行 smoke test：

```text
MANIFEST_INDEX_OK
REPORT=/tmp/openclaw-probe-test/document_index_20260527-025409.md
# Document Index
- indexed_files: 2
Refusing input path outside approved document directories: /root
INDEX_DOCUMENTS_OK
```

验证覆盖：

- `index_documents` 已在 `scripts/tool_allowlist.json` 中登记。
- `scripts/probes/index_documents.sh` 语法检查通过。
- 白名单入口能生成文档索引报告。
- 非批准输入路径 `/root` 被 runner 拒绝。

### Experiment report

Additional allowlisted tool:

```text
experiment_report_probe  Generate a Markdown summary from workspace reports and datasets
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh experiment_report_probe /root/.openclaw/workspace/reports/experiments
```

Board validation:

```text
runner report: /root/.openclaw/workspace/reports/experiments/experiment_report_20260527-044531.md
runner exit: 0
OpenClaw runId: 274ef269-05fd-406c-a0b6-64e756b77530
OpenClaw report: /root/.openclaw/workspace/reports/experiments/experiment_report_20260527-044552.md
```

### Security audit

Additional allowlisted tool:

```text
security_audit_probe  Generate a redacted security audit from board state
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh security_audit_probe /root/.openclaw/workspace/logs/probes
```

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/security_audit_20260527-045500.md
OpenClaw runId: c9778552-a4d7-494e-b325-e3eab7906086
OpenClaw report: /root/.openclaw/workspace/logs/probes/security_audit_20260527-045534.md
Gateway exposure: pass
Workspace secret scan: pass
Non-loopback listeners: warn
NAS workspace mount: warn
```

### Service policy

Additional allowlisted tool:

```text
service_policy_probe  Generate a read-only keep/disable/firewall policy plan
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh service_policy_probe /root/.openclaw/workspace/logs/probes
```

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/service_policy_20260527-050451.md
OpenClaw runId: e71ee679-f023-4e7f-97b5-3a2fec8e9c58
OpenClaw report: /root/.openclaw/workspace/logs/probes/service_policy_20260527-050558.md
OpenClaw Gateway: loopback, keep
SSH: present, keep
NFS/RPC server stack: present, disable after role confirmation
x11vnc: present, disable after role confirmation
iiod: present, keep if needed, otherwise disable or firewall
```

### Service hardening plan

Additional allowlisted tool:

```text
service_hardening_plan_probe  Generate a dry-run service hardening command plan
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh service_hardening_plan_probe /root/.openclaw/workspace/logs/probes
```

The report is read-only. It prints reviewable commands but does not execute
`systemctl`, `ufw`, or firewall changes.

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/service_hardening_plan_20260527-060031.md
OpenClaw runId: 154148d8-0224-45ae-95db-d4cf7e06a841
OpenClaw report: /root/.openclaw/workspace/logs/probes/service_hardening_plan_20260527-060121.md
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

### Stability snapshot

Additional allowlisted tool:

```text
stability_snapshot_probe  Generate a point-in-time uptime/resource/log snapshot
stability_summary_probe   Aggregate stability snapshots into a trend and acceptance-gap report
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh stability_snapshot_probe /root/.openclaw/workspace/logs/probes
scripts/run_allowlisted_tool.sh stability_summary_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/stability
```

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260527-051433.md
OpenClaw runId: 814bec32-5de1-4b0d-8ed1-750d34ce01dd
OpenClaw report: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260527-051515.md
Gateway status: active-listening
Kernel OOM matches in last 24h: 0
Gateway error-like log matches in last 24h: 0
```

Summary validation:

```text
runner report: /root/.openclaw/workspace/reports/stability/stability_summary_20260527-053046.md
OpenClaw runId: f499de43-4ce1-4818-a758-085d14af7d57
OpenClaw report: /root/.openclaw/workspace/reports/stability/stability_summary_20260527-053412.md
Snapshot count: 5
Elapsed hours: 0.22
Verdict: collecting
```

### ROS bag session

Additional allowlisted tool:

```text
rosbag_session_probe  Start/status/stop ROS bag self-test for low-risk topics
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh rosbag_session_probe /root/.openclaw/workspace/robot_datasets /root/.openclaw/workspace/logs/probes
```

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/rosbag_session_20260527-051843.md
OpenClaw runId: 0256a6af-2384-4456-bc4e-cb3a244761f2
OpenClaw report: /root/.openclaw/workspace/logs/probes/rosbag_session_20260527-052005.md
start_status: started
status_after_start: running
stop_status: sent_sigint
metadata_exists: yes
verdict: ok
```

### Image caption index

Additional allowlisted tool:

```text
image_caption_probe  Generate deterministic metadata captions and JSONL image search records
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh image_caption_probe /root/.openclaw/workspace/photos /root/.openclaw/workspace/reports/image-captions
```

Board validation:

```text
runner report: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-053923.md
OpenClaw runId: 542ea1c1-d708-48b3-9291-d97d1dba68f2
OpenClaw report: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-054009.md
Image records count: 1
caption: Image file smoke red dot, 1x1px
```

### Baseline status roll-up

Additional allowlisted tool:

```text
baseline_status_probe  Generate a read-only roll-up report for both baseline tracks
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh baseline_status_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
```

Board validation:

```text
runner report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-054653.md
OpenClaw runId: a0c43c05-a929-4a2a-9a94-2a3305139a52
OpenClaw report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-054753.md
Allowlisted tool count: 15
Progress docs: 15
NAS workspace status: not_mounted
```

### Home Assistant read-only status

Additional allowlisted tool:

```text
home_assistant_status_probe  Read-only Home Assistant/device-state preflight for B-008
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh home_assistant_status_probe /root/.openclaw/workspace/logs/probes
```

Safety boundary:

```text
GET /api/
GET /api/states
control_api_called: no
services_api_called: no
```

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061143.md
OpenClaw runId: e08850e5-7d55-4dcc-814c-a26b22cf8c80
OpenClaw report: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061252.md
verdict: blocked_no_config
```

### Control action policy preflight

Additional allowlisted tool:

```text
control_action_policy_probe  Read-only low-risk control policy and audit preflight for B-009
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh control_action_policy_probe /root/.openclaw/workspace/logs/probes
```

Safety boundary:

```text
action_executed: no
control_endpoint_called: no
```

Board validation:

```text
runner report: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061806.md
OpenClaw runId: f164f6ea-caf6-4581-929c-eed39b105ecc
OpenClaw report: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061906.md
verdict: blocked_no_policy
action_executed: no
```

### ROS bag named capture policy

Additional allowlisted tool:

```text
rosbag_capture_policy_probe  Read-only named ROS bag capture policy and topic classification
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh rosbag_capture_policy_probe /mnt/nas/openclaw/logs/probes
```

Safety boundary:

```text
mode: read-only policy and topic classification
robot_motion: never sends commands; capture only
retention_cleanup: report-only until approved
```

Board validation:

```text
runner report: /mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.md
policy_json: /mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.json
Approved Topics Detected Now: /rosout, /parameter_events
Command-like Topics Detected And Excluded: none
verdict: draft_policy_ready
```

### Semantic vision caption readiness

Additional allowlisted tool:

```text
vision_caption_readiness_probe  Read-only local semantic vision caption readiness for B-003
```

Approved runner entry:

```bash
scripts/run_allowlisted_tool.sh vision_caption_readiness_probe /mnt/nas/openclaw/photos /mnt/nas/openclaw/reports/image-captions
```

Safety boundary:

```text
mode: read-only
external_api_called: no
image_upload: no
model_install: no
```

Board validation:

```text
runner report: /mnt/nas/openclaw/reports/image-captions/vision_caption_readiness_20260528-230810.md
OpenClaw report: /root/.openclaw/workspace/reports/image-captions/vision_caption_readiness_20260528-230826.md
verdict: blocked_no_semantic_runtime
image files: 1
local model-like files: 0
semantic runtime: no
```

This keeps B-003 honest: metadata captioning is verified, but semantic captions
are blocked until a local vision model is installed or mounted.

### Operator-approved ROS bag named capture

Additional allowlisted tool:

```text
rosbag_named_capture_probe  Operator-approved bounded named ROS bag capture
```

Approved runner entry:

```bash
ROSBAG_NAMED_CAPTURE_SECONDS=300 \
scripts/run_allowlisted_tool.sh rosbag_named_capture_probe \
  /mnt/nas/openclaw/robot_datasets \
  /mnt/nas/openclaw/logs/probes
```

Safety boundary:

```text
operator_approval: chat_approved_2026-05-28
session name: generated by script only
duration: bounded, max 1800 seconds
robot_motion: never sends commands
topics: approved status topics only
```

Board validation:

```text
report: /mnt/nas/openclaw/logs/probes/rosbag_named_capture_20260528-231319.md
session_id: approved_named_capture_20260528-231319
duration_seconds: 300
topics_requested: /rosout /parameter_events
record_exit: 0
metadata_exists: yes
dataset_card: /mnt/nas/openclaw/robot_datasets/approved_named_capture_20260528-231319/DATASET_CARD.md
verdict: ok
```
