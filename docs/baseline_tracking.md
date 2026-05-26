# Baseline Tracking

本文把 baseline 拆成 Codex 可跟踪的任务。每个任务都应开 GitHub issue，或者至少在本文中更新状态。

状态定义：

| 状态 | 含义 |
| --- | --- |
| `todo` | 尚未开始 |
| `doing` | 正在实机验证 |
| `blocked` | 被硬件、网络、权限或依赖阻塞 |
| `verified` | 已通过验收并有证据 |
| `dropped` | 明确不进当前 baseline |

## Epic A：S100P PC Parity

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| A-001 | S100P 硬件/系统盘点 | verified | 记录 Ubuntu、kernel、架构、磁盘、网络、Node/npm、OpenClaw 状态 |
| A-002 | RDK Studio 部署 OpenClaw Gateway | verified | Gateway 可启动，Control UI 可访问，重启后恢复 |
| A-003 | NAS workspace 挂载到 S100P | blocked | S100P 可读写 NAS，重启后自动挂载 |
| A-004 | WebChat/Feishu smoke test | verified | 消息能触发命令并返回状态 |
| A-005 | 工具执行 allowlist | doing | 只允许执行 `scripts/` 下白名单脚本 |
| A-006 | Docker / sandbox 验证 | blocked | 非主会话不能写宿主机敏感路径 |
| A-007 | Browser automation smoke test | doing | 能打开测试网页、截图、保存到 NAS |
| A-008 | ROS2 status 工具 | verified | OpenClaw 能查询 ROS2 node/topic/service |
| A-009 | ROS bag 采集工具 | doing | 聊天命令能开始/停止采集，并写入 NAS；本地 start/status/stop self-test 已通过 runner 和 OpenClaw 插件验证 |
| A-010 | 7x24 稳定性测试 | doing | 连续运行 7 天，记录重启、内存、磁盘、日志；本地 snapshot probe 已通过 runner 和 OpenClaw 插件验证 |

## Epic B：AI NAS Homework

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| B-001 | NAS 资料库目录规范 | verified | 定义 documents/photos/videos/robot_datasets/logs/reports |
| B-002 | 文档索引和摘要 | doing | 对 NAS 文档生成索引和每日摘要 |
| B-003 | 图片 caption baseline | todo | 对图片生成 caption，支持文本搜索 |
| B-004 | 机器人数据集 card | doing | 每次采集自动生成 dataset card |
| B-005 | 日志分析助手 | doing | 给定日志目录，输出失败摘要、关键错误、建议命令 |
| B-006 | GitHub/Codex workflow | verified | issue -> branch -> PR -> Codex review 链路已走通；远端 issue `#2`、branch `baseline/s100p-nas-baselines`、draft PR `#3` 和 Codex review `4367946668` 已验证 |
| B-007 | 周报/实验报告生成 | doing | 从 NAS 日志和数据集生成 Markdown 周报；本地 workspace fallback 已通过 runner 和 OpenClaw 插件验证 |
| B-008 | Home Assistant / 设备只读状态 | todo | 只查询状态，不做控制 |
| B-009 | 低风险自动化控制 | doing | 白名单 + 二次确认 + 审计日志；本地 policy/audit preflight 已通过 runner 和 OpenClaw 插件验证，尚未开放实际执行 |
| B-010 | 安全审计清单 | doing | 检查 token、NAS 权限、Gateway 暴露、sandbox；本地 workspace fallback 已通过 runner 和 OpenClaw 插件验证 |

## 当前最近事实

- Windows 共享网络已使 S100P 通过 `192.168.137.10` 上网。
- S100P 已手动安装 Node.js `v20.19.2` arm64 tarball，并修正 `/usr/bin/node` 链接后 `node -v` 成功。
- RDK Studio 已通过 `root@192.168.137.10:22` 重新连接 S100P。
- RDK Studio 页面已显示 OpenClaw 部署成功。
- 实战记录见 `docs/04_openclaw_windows_ics_deploy.md`。

## 2026-05-27 当前进展核对

| 项 | 当前状态 | 证据 |
| --- | --- | --- |
| OpenClaw Gateway | verified | RDK Studio 后端健康检查返回 `gatewayRunning=true`、`aiReady=true`、版本 `OpenClaw 2026.3.28` |
| Gateway 暴露面 | verified | 板端 `ss -ltnp` 显示 Gateway 仅监听 `127.0.0.1:18789` 和 `[::1]:18789` |
| 飞书私聊/群聊入口 | verified | Gateway 日志显示 Feishu WebSocket ready、群消息 received、dispatching to agent、dispatch complete |
| 飞书群聊策略 | verified | OpenClaw 配置为 `groupPolicy=open`、`requireMention=true`，群里需要 `@小土豆` |
| 联网搜索 | verified | OpenClaw 搜索源已从 DuckDuckGo 切到 Tavily，agent 联网查询 RDK S100P 返回来源结果 |
| NAS 挂载 | blocked | 板端当前无 `/mnt/nas` 和 `/mnt/nas/openclaw`，需要 TS-264C 共享地址、账号和挂载方式 |
| NAS 挂载预检 | doing | `check_nas_mount_inputs.sh` 已通过板端 smoke test，危险挂载点被拒绝；`mount_openclaw_nas.sh` 已补齐 dry-run/显式 apply 的挂载入口；`cifs-utils` 已安装，`mount.cifs=ok` |
| 飞书联系人权限 | follow-up | 日志仍提示缺少 `contact:contact.base:readonly`，当前不阻塞消息和搜索，但建议在飞书开放平台补权限并发布 |
| 工具白名单 | doing | `run_allowlisted_tool.sh` 和 `s100p-allowlisted-tools` 已通过板端验证：OpenClaw 可触发 7 个白名单 tool_id；但 broad exec 负向测试仍失败 |
| Sandbox 状态探针 | blocked | `sandbox_status_probe` 已通过 runner 和 OpenClaw 插件验证，报告 `runtime_available: no`、`isolation_verdict: blocked`；板端当前无 Docker/Podman/runc |
| Browser smoke | doing | `browser_smoke_probe` 已通过 runner 和 OpenClaw 插件验证，能打开本地测试页并截图到 `/root/.openclaw/workspace/reports/browser-smoke`；NAS 挂载后需复测 NAS 输出 |
| ROS2 状态工具 | verified | `s100p_run_probe` 真实调用 `ros2_status_probe`，报告写入 `/root/.openclaw/workspace/logs/probes`，当前 nodes=0、topics=2 |
| ROS bag snapshot | doing | `rosbag_snapshot_probe` 已通过 runner 和 OpenClaw 插件验证，能短时记录 `/rosout`、`/parameter_events` 到 `/root/.openclaw/workspace/robot_datasets`；完整 start/stop 和 NAS 输出仍待做 |
| Dataset card | doing | `rosbag_snapshot_probe` 已能在本地 workspace fallback 下为每次 snapshot 生成 `DATASET_CARD.md`；NAS 挂载后需复测 NAS 目录 |
| 日志诊断 | doing | `log_diagnose` 已通过板端 smoke test，并通过 OpenClaw 插件写入 `/root/.openclaw/workspace/logs/probes/log_diagnosis_20260527-034730.md`；NAS 挂载后需复测 NAS 路径 |
| 文档索引 | doing | `index_documents` 已通过板端 smoke test，并通过 OpenClaw 插件写入 `/root/.openclaw/workspace/reports/document_index_20260527-034707.md`；NAS 挂载后需复测 NAS 路径 |

## 下一步推进顺序

1. A-003：拿到 TS-264C 共享信息后，先挂载只限 `/OpenClawWorkspace` 的专用共享到 `/mnt/nas/openclaw`，并验证重启后自动挂载。
2. A-005：在 NAS workspace 和本仓库 `scripts/` 下建立工具白名单，只允许执行经过审计的脚本。
3. B-002/B-005：在 NAS 目录可写后，先做文档索引/日志分析，不急着做图片 caption。
4. A-008/A-009：ROS2 status 和 ROS bag 采集依赖 NAS 落盘，放在 NAS 挂载之后。

## Codex 每次更新 issue 时应补充

- 当前板端 IP。
- 当前执行用户。
- 是否使用 Windows ICS 共享网络。
- OpenClaw 页面状态截图。
- 关键命令输出。
- 失败日志路径。
- 是否需要 GPT Pro 复审。

## 2026-05-27 B-003 Update

`image_caption_probe` provides a local workspace fallback for deterministic
metadata captions and JSONL search records.

Implementation:

```text
script: scripts/probes/image_caption_probe.sh
allowlist id: image_caption_probe
input: /root/.openclaw/workspace/photos
output: /root/.openclaw/workspace/reports/image-captions
```

Tracking status: B-003 can move from `todo` to `doing` after board validation.
It is not semantic vision captioning yet, and NAS-backed photo indexing remains
pending until A-003 is mounted.

Board validation evidence:

```text
runner report: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-053923.md
OpenClaw runId: 542ea1c1-d708-48b3-9291-d97d1dba68f2
OpenClaw report: /root/.openclaw/workspace/reports/image-captions/image_caption_index_20260527-054009.md
Image records count: 1
caption: Image file smoke red dot, 1x1px
```

Tracking status: B-003 is now `doing`; local metadata caption and JSONL search
records are verified, while NAS-backed indexing and semantic visual captions
remain pending.

## 2026-05-27 Baseline Status Roll-Up

`baseline_status_probe` was added to generate one read-only status dashboard for
both baseline tracks.

Implementation:

```text
script: scripts/probes/baseline_status_probe.sh
allowlist id: baseline_status_probe
workspace: /root/.openclaw/workspace
output: /root/.openclaw/workspace/reports/baseline-status
```

Board validation evidence:

```text
runner report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-054653.md
OpenClaw runId: a0c43c05-a929-4a2a-9a94-2a3305139a52
OpenClaw report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-054753.md
Allowlisted tool count: 15
Progress docs: 15
NAS workspace status: not_mounted
```

Tracking status: verified for local roll-up reporting. It does not mark the two
baselines complete; it gives the current progress and blockers in one report.

## 2026-05-27 A-003 NAS Discovery Update

`nas_discovery_probe` was added as a passive, read-only A-003 readiness probe.

Implementation:

```text
script: scripts/probes/nas_discovery_probe.sh
allowlist id: nas_discovery_probe
output: /root/.openclaw/workspace/logs/probes
```

It records current mount state, routes, neighbor table, SMB/NFS tooling, and
mDNS hints when available. It does not scan the network, log in, or mount
anything.

Board validation evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/nas_discovery_20260527-055322.md
OpenClaw runId: 84bd443b-b882-437b-9c88-c5e891c7d01c
OpenClaw report: /root/.openclaw/workspace/logs/probes/nas_discovery_20260527-055418.md
/mnt/nas/openclaw: not_mounted
mount.cifs: ok
mount.nfs: ok
Neighbor entries: 1
```

Tracking status: verified for passive local discovery. A-003 remains blocked for
actual mount until the TS-264C host/share/account details are available.

## 2026-05-27 B-010 Service Hardening Plan Update

`service_hardening_plan_probe` was added to generate a dry-run operator command
plan for B-010.

Implementation:

```text
script: scripts/probes/service_hardening_plan_probe.sh
allowlist id: service_hardening_plan_probe
output: /root/.openclaw/workspace/logs/probes
```

The probe prints reviewable `systemctl` and firewall commands, plus post-change
verification commands, but does not execute any service or firewall changes.

Board validation evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/service_hardening_plan_20260527-060031.md
OpenClaw runId: 154148d8-0224-45ae-95db-d4cf7e06a841
OpenClaw report: /root/.openclaw/workspace/logs/probes/service_hardening_plan_20260527-060121.md
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

Tracking status: verified for local dry-run planning. B-010 remains `doing`
until the operator chooses keep/disable/firewall actions and a post-change audit
is clean.

## 2026-05-27 B-007 Update

`experiment_report_probe` is verified for local workspace fallback through both the allowlist runner and the narrow OpenClaw plugin.

Evidence:

```text
runner report: /root/.openclaw/workspace/reports/experiments/experiment_report_20260527-044531.md
runner exit: 0
OpenClaw runId: 274ef269-05fd-406c-a0b6-64e756b77530
OpenClaw report: /root/.openclaw/workspace/reports/experiments/experiment_report_20260527-044552.md
Probe reports: 15
Experiment reports: 6
Browser smoke screenshots: 3
Document indexes: 2
ROS bag datasets: 5
Dataset cards: 2
```

Tracking status: B-007 remains `doing` until the same report is generated under `/mnt/nas/openclaw/reports/experiments` after A-003 is mounted.

## 2026-05-27 B-010 Update

`security_audit_probe` is verified for local workspace fallback through both the allowlist runner and the narrow OpenClaw plugin.

Evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/security_audit_20260527-045500.md
OpenClaw runId: c9778552-a4d7-494e-b325-e3eab7906086
OpenClaw runId: e08be89a-f0ee-43d2-8b4a-cf8ab92a7ff3
OpenClaw report: /root/.openclaw/workspace/logs/probes/security_audit_20260527-045534.md
OpenClaw report: /root/.openclaw/workspace/logs/probes/security_audit_20260527-050149.md
OpenClaw config validation: pass
Gateway exposure: pass, loopback only
Tavily plugin: pass
S100P allowlisted plugin: pass
Non-loopback listeners: warn, 19 non-loopback listeners
Non-loopback listener categories: nfs-rpc, admin, remote-desktop, hardware-daemon
Service policy runId: e71ee679-f023-4e7f-97b5-3a2fec8e9c58
Service policy report: /root/.openclaw/workspace/logs/probes/service_policy_20260527-050558.md
Service policy summary: keep Gateway loopback and SSH; decide whether to disable NFS/RPC, x11vnc, and iiod
NAS workspace mount: warn, not_mounted
Workspace secret scan: pass
```

Tracking status: B-010 remains `doing` until NAS-backed audit output is validated and the final service policy decides whether to keep or close NFS/RPC, x11vnc, and iiod.

## 2026-05-27 B-006 Update

`github_workflow_probe.ps1` is verified on the Windows/Codex workstation.

Evidence:

```text
report: reports/github-workflow/github_workflow_20260527-050933.md
origin: https://github.com/zhexuexiaotudou/-agent-s100-.git
origin reachability: pass, refs/heads/main returned
current branch: main
upstream: origin/main
git identity: pass
issue seed: pass, docs/github_issue_seed.md exists
GitHub CLI: warn, gh CLI not found
working tree: warn, 32 changed or untracked paths
PR readiness: blocked until a scoped commit/branch is created
```

Tracking status: B-006 remained `doing` at this point because no remote issue,
branch, pushed draft PR, or review evidence existed yet.

Remote issue evidence:

```text
repository: zhexuexiaotudou/-agent-s100-
issue: #2
url: https://github.com/zhexuexiaotudou/-agent-s100-/issues/2
title: Track OpenClaw S100P PC parity and AI NAS baselines
created_at_utc: 2026-05-26T22:21:56Z
conversation_lock: locked
lock_reason: spam
lock_time_utc: 2026-05-26T22:24:05Z
```

Updated readiness report:

```text
report: reports/github-workflow/github_workflow_20260527-062317.md
Remote issue marker: pass
Working tree: warn, 52 changed or untracked paths
PR readiness: blocked, create a scoped commit before PR
```

Draft PR evidence:

```text
branch: baseline/s100p-nas-baselines
commit: cd93e0a8ca094a80161a362d6288c190260282bb
pull_request: #3
url: https://github.com/zhexuexiaotudou/-agent-s100-/pull/3
state: open
draft: true
review_id: 4367946668
review_type: Codex COMMENT review
```

Updated readiness report:

```text
report: reports/github-workflow/github_workflow_20260527-063039.md
Remote issue marker: pass
Remote PR marker: pass
Working tree: warn, 5 changed or untracked paths before recording this marker commit
```

Tracking status: B-006 is now `verified` for the issue -> branch -> draft PR ->
Codex review workflow. The PR remains draft and unmerged while the broader
baseline still has NAS, stability, and service-policy blockers.

## 2026-05-27 A-010 Update

`stability_snapshot_probe` is verified for local point-in-time stability sampling through both the allowlist runner and the narrow OpenClaw plugin.

Evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260527-051433.md
OpenClaw runId: 814bec32-5de1-4b0d-8ed1-750d34ce01dd
OpenClaw report: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260527-051515.md
Gateway status: active-listening
NAS workspace: not_mounted
Reboot records visible: 9
Kernel OOM matches in last 24h: 0
Gateway error-like log matches in last 24h: 0
```

Tracking status: A-010 remains `doing` until the snapshot is collected repeatedly for 7 days and summarized, preferably to NAS after A-003 is mounted.

## 2026-05-27 Tavily Search Update

Tavily is configured as the active OpenClaw web search source and was verified
through a live `openclaw agent` run.

Evidence:

```text
config file: /root/.openclaw/openclaw.json
tools.web.search.provider: tavily
tools.web.search.enabled: true
plugins.entries.tavily.enabled: true
plugins.entries.tavily.config.webSearch.apiKey: set
openclaw config validate: pass
plugin status: Tavily loaded
OpenClaw runId: b495689d-e68e-4622-bad4-01ac6ffeba26
agent status: ok
agent provider/model: custom-gateway / MiniMax-M2.7
agent tools exposed: web_search, tavily_search, tavily_extract
test query: online search for RDK S100P
test result: returned source URLs including developer.d-robotics.cc/rdks100
```

Tracking status: online search remains `verified`.

## 2026-05-27 B-008 Home Assistant Update

`home_assistant_status_probe` was added as a read-only Home Assistant/device
state preflight for B-008.

Implementation:

```text
script: scripts/probes/home_assistant_status_probe.sh
allowlist id: home_assistant_status_probe
output: /root/.openclaw/workspace/logs/probes
```

Safety boundary:

```text
GET /api/
GET /api/states
control_api_called: no
services_api_called: no
```

Board validation evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061143.md
OpenClaw runId: e08850e5-7d55-4dcc-814c-a26b22cf8c80
OpenClaw report: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061252.md
verdict: blocked_no_config
```

Roll-up evidence:

```text
report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-061310.md
Allowlisted tool count: 18
Progress docs: 18
Home Assistant status: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061252.md
NAS workspace: not_mounted
```

Tracking status: B-008 is now `doing`. The read-only tool path is verified; the
real Home Assistant state read requires URL/token.

## 2026-05-27 B-009 Control Policy Update

`control_action_policy_probe` was added as the first B-009 gate: low-risk
control policy and audit preflight only.

Implementation:

```text
script: scripts/probes/control_action_policy_probe.sh
allowlist id: control_action_policy_probe
policy file: /root/.openclaw/workspace/config/control_action_allowlist.json
audit directory: /root/.openclaw/workspace/logs/control-audit
output: /root/.openclaw/workspace/logs/probes
```

Safety boundary:

```text
action_executed: no
control_endpoint_called: no
```

Board validation evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061806.md
OpenClaw runId: f164f6ea-caf6-4581-929c-eed39b105ecc
OpenClaw report: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061906.md
verdict: blocked_no_policy
action_executed: no
```

Roll-up evidence:

```text
report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-061920.md
Allowlisted tool count: 19
Progress docs: 19
Control action policy: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061906.md
NAS workspace: not_mounted
```

Tracking status: B-009 is now `doing`. The policy/audit preflight is verified;
real control remains blocked until a reviewed disabled allowlist, two-step
approval path, and audit retention policy exist.

Sampler implementation:

```text
script: scripts/install_stability_sampler.sh
service: openclaw-stability-sampler.service
timer: openclaw-stability-sampler.timer
default interval: 1800 seconds
default output: /root/.openclaw/workspace/logs/probes
```

The sampler installer is operator-only and is intentionally not exposed through
the OpenClaw conversation allowlist. It moves A-010 from one-shot snapshots to
scheduled evidence collection, but the 7x24 pass still requires a full 7-day
sample set and trend summary.

Board install evidence:

```text
timer state: active (waiting)
first service exit: status=0/SUCCESS
first scheduled report: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260527-052549.md
next trigger: 2026-05-27 05:55:49 CST
```

Summary probe implementation:

```text
script: scripts/probes/stability_summary_probe.sh
allowlist id: stability_summary_probe
input: /root/.openclaw/workspace/logs/probes
output: /root/.openclaw/workspace/reports/stability
```

Summary probe evidence:

```text
runner report: /root/.openclaw/workspace/reports/stability/stability_summary_20260527-053046.md
OpenClaw runId: f499de43-4ce1-4818-a758-085d14af7d57
OpenClaw report: /root/.openclaw/workspace/reports/stability/stability_summary_20260527-053412.md
Snapshot count: 5
Elapsed hours: 0.22
Verdict: collecting
```

## 2026-05-27 A-009 Session Update

`rosbag_session_probe` is verified for local start/status/stop self-tests through both the allowlist runner and the narrow OpenClaw plugin.

Evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/rosbag_session_20260527-051843.md
OpenClaw runId: 0256a6af-2384-4456-bc4e-cb3a244761f2
OpenClaw report: /root/.openclaw/workspace/logs/probes/rosbag_session_20260527-052005.md
start_status: started
status_after_start: running
stop_status: sent_sigint
record_exit: 0
metadata_exists: yes
verdict: ok
```

Tracking status: A-009 remains `doing` until NAS-backed session output is validated and a policy is chosen for longer named capture sessions.
