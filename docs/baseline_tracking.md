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
| A-003 | NAS workspace 挂载到 S100P | verified | NFS v4.1 运行时挂载、`/etc/fstab` 持久化、S100P 重启后 systemd automount 和写入测试均已验证 |
| A-004 | WebChat/Feishu smoke test | verified | 消息能触发命令并返回状态 |
| A-005 | 工具执行 allowlist | verified | 只允许执行白名单探针；2026-05-28 负向测试中 agent 拒绝非白名单 `/usr/bin/touch`，marker 未创建 |
| A-006 | Docker / sandbox 验证 | blocked | 非主会话不能写宿主机敏感路径 |
| A-007 | Browser automation smoke test | verified | Headless Chromium 能打开测试网页、截图并保存到 NAS，PNG 校验通过 |
| A-008 | ROS2 status 工具 | verified | OpenClaw 能查询 ROS2 node/topic/service |
| A-009 | ROS bag 采集工具 | verified | NAS-backed start/status/stop self-test、命名采集 policy 和一次人工批准的 300 秒 named capture 均已通过 |
| A-010 | 7x24 稳定性测试 | doing | systemd timer 已切到 NAS-backed 输出；当前 74 个 snapshot、24.15h、verdict=`collecting`；新一轮 10h overnight runner 正在运行 |

## Epic B：AI NAS Homework

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| B-001 | NAS 资料库目录规范 | verified | 定义 documents/photos/videos/robot_datasets/logs/reports |
| B-002 | 文档索引和摘要 | verified | NAS-backed 文档索引和 deterministic 每日摘要均已生成 |
| B-003 | 图片 caption / Dream 7B readiness baseline | doing | NAS-backed metadata caption 和 JSONL index 已跑通；semantic vision caption 未跑通；Dream 7B readiness 证实 runtime 存在但缺模型文件 |
| B-004 | 机器人数据集 card | verified | NAS-backed ROS bag session 已自动生成 `DATASET_CARD.md` |
| B-005 | 日志分析助手 | verified | 已从 NAS 日志目录读取 Windows link-check JSONL，输出失败摘要、关键错误和建议命令 |
| B-006 | GitHub/Codex workflow | verified | issue -> branch -> PR -> Codex review 链路已走通；远端 issue `#2`、branch `baseline/s100p-nas-baselines`、draft PR `#3` 和 Codex review `4367969950` 已验证 |
| B-007 | 周报/实验报告生成 | verified | 已从 NAS logs/probes、文档索引、浏览器截图、ROS bag 和 dataset card 生成 Markdown 实验报告 |
| B-008 | Home Assistant / 设备只读状态 | doing | NAS-backed read-only preflight 已生成，未调用控制 API；真实读取需要 HA URL/token |
| B-009 | 低风险自动化控制 | doing | disabled-by-default policy 已生成并通过 NAS/OpenClaw preflight；启用动作数为 0，仍需真实 reviewed action 和 request/approve/execute audit |
| B-010 | 安全审计清单 | doing | NAS-backed security audit、service policy、hardening dry-run、service convergence decision pack 和 execution preflight 已生成；执行 disable/firewall 前仍需填写确认门 |

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
| NAS 挂载 | verified | QNAP `169.254.110.209:/OpenClawWorkspace` 已通过 NFS v4.1 持久化挂载到 `/mnt/nas/openclaw`；S100P 重启后 automount 和写入测试通过 |
| 开机自恢复链路 | verified | Windows 托盘工具已验证登录后自动检查 `PC -> S100P -> NAS -> OpenClaw/飞书`，并确认 Windows 双 IP、S100P 双网段、NAS NFS 可写、Gateway active 和飞书消息日志；见 `docs/baseline_progress_2026-05-28_startup_self_heal.md` |
| NAS 挂载预检 | verified | `check_nas_mount_inputs.sh` 已通过板端 smoke test，危险挂载点被拒绝；`mount_openclaw_nas.sh` 已补齐 dry-run/显式 apply 的挂载入口；NFS v4.1 automount 和写入测试已通过 |
| 飞书联系人权限 | follow-up | 日志仍提示缺少 `contact:contact.base:readonly`，当前不阻塞消息和搜索，但建议在飞书开放平台补权限并发布 |
| 工具白名单 | verified | `run_allowlisted_tool.sh` 和 `s100p-allowlisted-tools` 已通过板端验证；2026-05-28 broad exec 负向复测拒绝非白名单 `/usr/bin/touch` |
| Sandbox 状态探针 | blocked | `sandbox_status_probe` 已通过 runner 和 OpenClaw 插件验证，报告 `runtime_available: no`、`isolation_verdict: blocked`；板端当前无 Docker/Podman/runc |
| Browser smoke | verified | `browser_smoke_probe` 已通过 NAS-backed runner 验证，能打开本地测试页并截图到 `/mnt/nas/openclaw/reports/browser-smoke`，PNG magic 校验通过 |
| ROS2 状态工具 | verified | `s100p_run_probe` 真实调用 `ros2_status_probe`，报告写入 `/root/.openclaw/workspace/logs/probes`，当前 nodes=0、topics=2 |
| ROS bag session | verified | NAS-backed `rosbag_session_probe` 已完成 start/status/stop self-test，并生成 dataset card；`rosbag_capture_policy_probe` 已生成命名采集策略 |
| Dataset card | verified | NAS-backed ROS bag session 已在 `/mnt/nas/openclaw/robot_datasets/.../DATASET_CARD.md` 生成数据集卡片 |
| 日志诊断 | verified | `log_diagnose` 已从 NAS logs 输出 `/mnt/nas/openclaw/logs/probes/log_diagnosis_20260528-181546.md` |
| 文档索引 | verified | `index_documents` 和 `document_daily_summary_probe` 已生成 NAS-backed 文档索引与每日摘要 |

## 下一步推进顺序

1. A-010：保持 systemd timer 运行到 168 小时，再生成最终稳定性验收摘要。
2. A-006：决定是否安装 Docker/Podman/runc，或把 sandbox runtime 明确移出第一版 baseline。
3. A-009：若要进入真实机器人数据采集，执行一次人工批准的 named capture，并按现有 policy 做保留/清理。
4. B-003：决定第一版是否只保留 metadata caption，还是安装/挂载语义视觉模型或 Dream 7B 模型文件。
5. B-008/B-009/B-010：等待 Home Assistant token、控制 allowlist 和服务收敛策略，不在无人值守时修改。

## 2026-05-28 Startup Self-Heal Update

Windows 侧新增开机自启动托盘工具：

```text
scripts/startup_link_check/
task: S100P-NAS-OpenClaw-LinkCheck
mode: hidden PowerShell + tray resident UI
```

实测日志：

```text
F:\Project\Digua\logs\link-check\2026-05-28.jsonl
```

关键证据：

```text
run_start: startInTray=true, useStartupDelay=true
Windows: 192.168.127.2/24 and 192.168.137.1/24 OK
PC -> S100P: ping and SSH key OK
S100P: eth1 dual IP, default route, DNS, open.feishu.cn OK
NAS: 169.254.110.209:/OpenClawWorkspace mounted at /mnt/nas/openclaw and writable
OpenClaw/Feishu: openclaw-gateway.service active, received message, dispatch complete
run_end: status=OK, windowsOk=true, sshOk=true, networkOk=true, nasOk=true, openclawOk=true
```

Tracking impact:

- A-003 is now superseded by the 2026-05-28 persistent NFS evidence below.
- A-004 remains `verified`: Feishu message receive/dispatch is repeatedly observed.
- A-010 remains `doing`: PC login recovery is verified, but the 7-day stability criterion is still collecting.
- B-005 remains `doing`: link-check JSONL is now a structured input source for future log diagnosis.
- B-010 remains `doing`: the tool redacts local logs and keeps Feishu `99991672` as non-blocking, but service hardening is not finalized.

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

Tracking status: verified for passive local discovery. 后续已经拿到 TS-264C
host/share/account 信息，并通过 NFS 完成运行时挂载；见本文末尾 QNAP NAS
直连与 NFS 挂载更新。

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

## 2026-05-27 QNAP NAS 直连与 NFS 挂载更新

新增审阅记录：

```text
docs/baseline_progress_2026-05-27_qnap_nfs_mount.md
```

当前已验证状态：

```text
S100P eth1: 192.168.137.10/24，默认路由走 Windows ICS 192.168.137.1
S100P eth0: 169.254.8.10/16，不设置默认路由
QNAP NAS: 169.254.110.209
QNAP share/export: /OpenClawWorkspace
S100P mountpoint: /mnt/nas/openclaw
选定协议: NFS v4.1
运行时挂载: verified
NAS 写入测试: verified
```

关键发现：

```text
SMB 登录和写入测试可用，但 SMB 内核挂载被阻塞，因为 S100P 当前内核没有
cifs 模块。A-003 的可用挂载路径是 NFS。
```

Tracking status: A-003 已从 `blocked` 调整为 `doing`。暂时不能标成完整
`verified`，因为 `/etc/fstab`
尚未写入，也还没有验证重启后自动挂载。

## 2026-05-28 A-003 Persistent NFS Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_a003_persistent_nfs.md
```

当前已验证状态：

```text
S100P eth0: 169.254.8.10/16, static netplan, NAS-only route
S100P eth1: 192.168.127.10/24 and 192.168.137.10/24, default via 192.168.137.1
NAS: 169.254.110.209
NFS export: /OpenClawWorkspace
fstab: 169.254.110.209:/OpenClawWorkspace /mnt/nas/openclaw nfs4 defaults,nofail,x-systemd.automount,_netdev 0 0
reboot validation: findmnt shows autofs + nfs4, write test passed
```

关键修复：

```text
重启后 NAS 路由一度错误走 eth1，因为 netplan 把 eth0 配成 DHCP。
已改为 eth0 固定 169.254.8.10/16，并同步修复 Windows startup_link_check 工具，
避免后续自恢复程序再次把 eth0 写回 DHCP。
```

Tracking status: A-003 is now `verified`.

## 2026-05-28 NAS-backed Reports Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_nas_backed_reports.md
```

NAS-backed 复测结果：

```text
B-005 log diagnosis:
  /mnt/nas/openclaw/logs/probes/log_diagnosis_20260528-181546.md
  total_matches=14
  top patterns: permission denied/contact scope, generic failed, timeout

A-010 stability snapshot:
  /mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-181546.md
  Gateway status=active-listening
  NAS workspace=mounted
  Kernel OOM last 24h=0
  Gateway error-like logs last 24h=0

A-010 stability summary:
  /mnt/nas/openclaw/reports/stability/stability_summary_20260528-181555.md
  Snapshot count=1
  Verdict=collecting

B-007 experiment report:
  /mnt/nas/openclaw/reports/experiments/experiment_report_20260528-181734.md
  workspace=/mnt/nas/openclaw
  nas_backed_mode=verified
```

Tracking impact:

- B-005 is now `verified`: NAS 日志目录输入、失败摘要、关键错误和建议命令均已跑通。
- B-007 remains `doing`: NAS-backed report 生成链路已跑通，但还需要填充 B-002/A-007/A-009/B-004 产物。
- A-010 remains `doing`: NAS-backed 采样与 summary 已开始，7x24 样本仍在 collecting。

## 2026-05-28 NAS Core Artifacts Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_nas_core_artifacts.md
```

NAS-backed core artifact 复测结果：

```text
B-002 document index:
  /mnt/nas/openclaw/reports/document_index_20260528-182111.md
  indexed_files=1

A-007 browser smoke:
  /mnt/nas/openclaw/reports/browser-smoke/browser_smoke_20260528-182111.md
  /mnt/nas/openclaw/reports/browser-smoke/browser_smoke_20260528-182111.png
  visible_marker=yes
  screenshot_status=captured
  png_magic=89504e470d0a1a0a
  verdict=ok

A-009/B-004 ROS bag session:
  /mnt/nas/openclaw/logs/probes/rosbag_session_20260528-182117.md
  /mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117/DATASET_CARD.md
  start_status=started
  status_after_start=running
  stop_status=sent_sigint
  metadata_exists=yes
  verdict=ok

B-007 experiment report:
  /mnt/nas/openclaw/reports/experiments/experiment_report_20260528-182242.md
  Probe reports=3
  Browser smoke screenshots=1
  Document indexes=1
  ROS bag datasets=1
  Dataset cards=1
```

Tracking impact:

- A-007 is now `verified`: 浏览器自动化截图已经保存到 NAS。
- B-004 is now `verified`: NAS-backed ROS bag session 自动生成 dataset card。
- B-007 is now `verified`: NAS-backed Markdown 实验报告已经汇总核心产物。
- B-002 remains `doing`: 文档索引已跑通，但每日摘要未做。
- A-009 remains `doing`: start/status/stop self-test 已写入 NAS，但长时间命名采集策略未定。

## 2026-05-28 NAS Image Caption And Security Audit Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_image_security_nas.md
```

NAS-backed 复测结果：

```text
B-003 image caption:
  /mnt/nas/openclaw/reports/image-captions/image_caption_index_20260528-182530.md
  /mnt/nas/openclaw/reports/image-captions/image_caption_index_20260528-182530.jsonl
  Image records=1
  dimensions=780x493
  mode=deterministic metadata captions

B-010 security audit:
  /mnt/nas/openclaw/logs/probes/security_audit_20260528-182530.md
  OpenClaw config validation=pass
  Gateway exposure=pass, loopback only
  NAS workspace mount=pass, mounted
  Workspace secret scan=pass
  Non-loopback listeners=warn, 19
```

Tracking impact:

- B-003 moves from `todo` to `doing`: metadata caption 和 JSONL index 已可写入 NAS。
- B-010 remains `doing`: audit 已 NAS-backed，但 NFS/RPC、x11vnc、iiod、SSH 的 keep/disable/firewall 策略未定。

## 2026-05-28 NAS-backed Baseline Status Roll-up

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_nas_baseline_status.md
```

汇总报告：

```text
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-182846.md
```

核心状态：

```text
OpenClaw Gateway=active-listening
Stability sampler timer=active
NAS workspace=mounted
Allowlisted tool count=19
Probe reports=11
Workspace reports=10
Dataset cards=1
Image caption JSONL indexes=1
Stability snapshots=1
```

这份 roll-up 确认当前 NAS-backed smoke baseline 已经覆盖：

- A-003/A-007/A-009/A-010
- B-002/B-003/B-004/B-005/B-007/B-010

仍未解除的主阻塞：

- A-006 sandbox runtime 或 drop 决策
- A-010 168 小时稳定性样本
- B-008 Home Assistant URL/token
- B-009 控制动作策略
- B-010 服务 keep/disable/firewall 策略

## 2026-05-28 NAS Home Assistant And Control Preflight Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_ha_control_preflight_nas.md
```

NAS-backed 预检结果：

```text
B-008 Home Assistant:
  /mnt/nas/openclaw/logs/probes/home_assistant_status_20260528-183050.md
  mode=read-only
  control_api_called=no
  services_api_called=no
  Verdict=blocked_no_config

B-009 Control policy:
  /mnt/nas/openclaw/logs/probes/control_action_policy_20260528-183050.md
  action_executed=no
  control_endpoint_called=no
  Policy status=missing
  Verdict=blocked_no_policy

Updated roll-up:
  /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-183114.md
```

Tracking impact:

- B-008 remains `doing`: 工具链已可写 NAS，但没有 HA URL/token。
- B-009 remains `doing`: policy/audit 预检已可写 NAS，但没有控制 allowlist，且未开放执行。

## 2026-05-28 A-010 NAS Sampler Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_a010_nas_sampler.md
```

定时器输出已从本地切到 NAS：

```text
Environment=OPENCLAW_PROBE_DIR=/mnt/nas/openclaw/logs/probes
ExecStart=... stability_snapshot_probe.sh /mnt/nas/openclaw/logs/probes
openclaw-stability-sampler.timer=active
```

立即执行证据：

```text
/mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-183318.md
service exit=status=0/SUCCESS
```

最新 summary：

```text
/mnt/nas/openclaw/reports/stability/stability_summary_20260528-183432.md
Snapshot count=2
Elapsed hours=0.29
Gateway statuses=2 active-listening
NAS statuses=2 mounted
Verdict=collecting
```

Tracking impact:

- A-010 remains `doing`: 已进入 NAS-backed 自动采样，但离 168 小时验收还早。

## 2026-05-28 NAS Service Policy Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_service_policy_nas.md
```

NAS-backed 输出：

```text
/mnt/nas/openclaw/logs/probes/service_policy_20260528-183619.md
/mnt/nas/openclaw/logs/probes/service_hardening_plan_20260528-183619.md
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-183640.md
```

当前策略建议：

```text
OpenClaw Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC server stack: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

Tracking impact:

- B-010 remains `doing`: 计划和证据已 NAS-backed，但没有用户确认前不实际停服务或改防火墙。

## 2026-05-28 B-002 Document Daily Summary Update

新增审阅记录：

```text
docs/baseline_progress_2026-05-28_document_daily_summary.md
```

新增探针：

```text
scripts/probes/document_daily_summary_probe.sh
tool_id=document_daily_summary_probe
```

NAS-backed 输出：

```text
/mnt/nas/openclaw/reports/daily-summary/document_daily_summary_20260528-184329.md
/mnt/nas/openclaw/reports/daily-summary/document_daily_summary_20260528-184329.json
```

验证结果：

```text
Total documents=1
Modified last 24h=1
Top directory=baseline_reports
File type=.md
Refusing input path outside approved document directories: /root
Tool is not allowlisted: ../../etc/passwd
```

更新后的汇总：

```text
/mnt/nas/openclaw/reports/experiments/experiment_report_20260528-184444.md
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-184444.md
Allowlisted tool count=20
Document daily summaries=1
```

Tracking impact:

- B-002 is now `verified` for deterministic metadata summary.
- 如果后续要语义/LLM 摘要，可作为增强项，不阻塞当前 baseline。
## 2026-05-28 B-003 Semantic Vision Readiness Update

`vision_caption_readiness_probe` was added to separate deterministic metadata
image indexing from true semantic vision captioning.

Evidence:

```text
NAS runner report: /mnt/nas/openclaw/reports/image-captions/vision_caption_readiness_20260528-230810.md
OpenClaw tool report: /root/.openclaw/workspace/reports/image-captions/vision_caption_readiness_20260528-230826.md
verdict: blocked_no_semantic_runtime
image files: 1
local model-like files: 0
semantic runtime: no
```

Tracking status: B-003 remains `doing`. Metadata caption and JSONL indexing are
verified, but semantic image captioning is not verified because no local vision
model files were found. The next decision is either to install/mount a local
vision caption model or scope B-003 v1 as metadata-only.

## 2026-05-29 B-003 Dream 7B / Local DLM Readiness Update

`dream7b_readiness_probe` was added to separate "S100P can run OpenClaw
gateway/tools" from "S100P can host a local 7B DLM".

Board evidence through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_readiness_20260529-155315.md
verdict: blocked_no_model
memory total: 21.3 GiB
runtime summary: llama.cpp,torch-transformers
model-like files: 0
dream-named files: 0
```

OpenClaw agent evidence through `s100p_run_probe`:

```text
report: /root/.openclaw/workspace/reports/models/dream7b_readiness_20260529-160626.md
verdict: blocked_no_model
runtime summary: llama.cpp, torch-transformers
model file count: 0
memory total: 21.3 GiB
```

NAS baseline roll-up:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260529-160424.md
B-003: Dream 7B/local DLM readiness has runtime evidence but no model files
remaining gap: mount/install Dream 7B model files or explicitly keep local DLM out of first baseline
```

Tracking status: B-003 remains `doing`. The S100P has runtime candidates
(`llama_cpp` Python module plus `torch`/`transformers`), but there are no Dream
7B or model-like files under the approved model directories. No Dream 7B
deployment or inference claim should be made until model files are installed or
mounted and a bounded local smoke test passes.

## 2026-05-28 A-009 Operator-Approved Named Capture Update

`rosbag_named_capture_probe` was added for the first approved named capture
under the A-009 policy.

Evidence:

```text
report: /mnt/nas/openclaw/logs/probes/rosbag_named_capture_20260528-231319.md
session_id: approved_named_capture_20260528-231319
bag_dir: /mnt/nas/openclaw/robot_datasets/approved_named_capture_20260528-231319
duration_seconds: 300
topics_requested: /rosout /parameter_events
record_exit: 0
metadata_exists: yes
dataset_card: /mnt/nas/openclaw/robot_datasets/approved_named_capture_20260528-231319/DATASET_CARD.md
verdict: ok
```

Tracking status: A-009 is verified for baseline capture mechanics. Future real
captures still need reviewed topic selection and retention-cleanup approval.

## 2026-05-28 B-010 Service Convergence Decision Update

`service_convergence_decision_probe` was added to consolidate the latest
security audit, service policy, hardening dry-run, listener snapshot, and
service snapshot into one read-only decision pack.

Evidence:

```text
NAS runner report: /mnt/nas/openclaw/reports/security/service_convergence_decision_20260528-235327.md
OpenClaw tool report: /root/.openclaw/workspace/reports/security/service_convergence_decision_20260528-234753.md
Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

Tracking status: B-010 remains `doing`. The review pack is now available from
both the runner and the OpenClaw tool path, but no service or firewall changes
have been executed. Execution still needs confirmation that S100P is
NFS-client-only, x11vnc is unused, and iiod is not required by hardware tooling.

## 2026-05-29 A-010 Stability Refresh

The NAS-backed stability collector is still running and the summary was
refreshed after the Dream 7B readiness work.

Evidence:

```text
summary: /mnt/nas/openclaw/reports/stability/stability_summary_20260529-161307.md
baseline roll-up: /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260529-161308.md
snapshot count: 65
first snapshot: 2026-05-28T18:15:46+08:00
last snapshot: 2026-05-29T16:03:36+08:00
elapsed hours: 21.80
gateway statuses: 65 active-listening
NAS statuses: 65 mounted
kernel OOM matches in last 24h: 0
gateway error-like matches in last 24h: 0
verdict: collecting
```

Tracking status: A-010 remains `doing`. The trend is clean so far, but it is
not a 7x24 pass until the elapsed time reaches at least 168 hours.

## 2026-05-29 Overnight Runner Restart

The previous overnight runner completed cleanly and a new 10-hour read-only
runner was started to keep collecting baseline evidence.

Previous runner:

```text
summary: /mnt/nas/openclaw/reports/baseline-status/overnight_baseline_20260528-232330_summary.md
pid: 72079
process_status: not_running
verdict: complete_no_failed_events
completed_iterations_observed: 20
event_count: 114
failed_event_count: 0
```

New runner:

```text
pid: 278801
launch_log: /mnt/nas/openclaw/logs/overnight/overnight_launch_20260529-162329.out
status_report: /mnt/nas/openclaw/reports/baseline-status/overnight_baseline_20260529-162329_status.md
process_status: running
completed_iterations_observed: 1
failed_event_count: 0
next_iteration_after: 2026-05-29T16:53:51+08:00
```

Latest A-010 evidence after restart:

```text
summary: /mnt/nas/openclaw/reports/stability/stability_summary_20260529-162339.md
snapshot count: 66
elapsed hours: 22.13
gateway statuses: 66 active-listening
NAS statuses: 66 mounted
verdict: collecting
```

Tracking status: A-010 remains `doing`. This keeps the evidence stream alive
but still does not satisfy the 168-hour acceptance gate.

## 2026-05-29 Baseline Gap Decision Update

`baseline_gap_decision_probe` was added as a read-only decision summary for the
two baseline tracks. It classifies the remaining work into automation-safe next
actions versus external inputs or operator decisions.

NAS runner evidence:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_gap_decision_20260529-184105.md
A-010: 74 snapshots, 24.15 elapsed hours, verdict=collecting
overnight runner: running, iterations=5, failed=0
Dream 7B: blocked_no_model
Home Assistant: blocked_no_config
Control policy: policy_ready_no_execution, enabled=0, executed=0
```

OpenClaw agent evidence:

```text
report: /root/.openclaw/workspace/reports/baseline-status/baseline_gap_decision_20260529-184923.md
A-010 elapsed hours: 24.15
overnight process status: running
failed event count: 0
external inputs: B-003 model files; B-008 HA URL/token; B-009 reviewed action allowlist; B-010 service confirmations
```

Tracking impact: the baseline is not generally stuck. A-010 can continue
collecting automatically, while B-003/B-008/B-009/B-010 need explicit external
inputs or operator decisions before they can be closed.

## 2026-05-29 B-010 Service Execution Preflight Update

`service_execution_preflight_probe` was added as a read-only confirmation gate
for service convergence execution. It validates whether the operator has
confirmed Gateway loopback, SSH management need, NFS/RPC client-only status,
x11vnc usage, and iiod handling.

Evidence:

```text
report: /mnt/nas/openclaw/reports/security/service_execution_preflight_20260529-191608.md
verdict: blocked_no_confirmations
config status: missing
missing confirmations: gateway_loopback_only, ssh_management_required, nfs_rpc_client_only, x11vnc_unused, iiod_unused_or_firewall
service/firewall changes executed: no
```

OpenClaw agent evidence:

```text
report: /root/.openclaw/workspace/reports/security/service_execution_preflight_20260529-192933.md
verdict: blocked_no_confirmations
service/firewall changes executed: none
```

Gap roll-up evidence:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_gap_decision_20260529-191625.md
Service execution preflight: /mnt/nas/openclaw/reports/security/service_execution_preflight_20260529-191608.md
B-010 classification: blocked_no_confirmations
```

Tracking impact: B-010 remains `doing`, but the next step is now concrete and
auditable: fill and review `service_convergence_confirmations.json`, then rerun
the preflight before any manual service or firewall command is considered.

## 2026-05-29 External Input Template Update

Added deterministic templates for blockers that require private or operator
inputs:

```text
config/dream7b_deployment.example.json
config/home_assistant.env.example
scripts/probes/dream7b_smoke_probe.sh
docs/baseline_progress_2026-05-29_external_input_templates.md
```

Evidence:

```text
runner smoke report: /mnt/nas/openclaw/reports/models/dream7b_smoke_20260529-195131.md
OpenClaw smoke report: /root/.openclaw/workspace/reports/models/dream7b_smoke_20260529-195337.md
verdict: blocked_no_config
allowlisted tool count: 28
latest baseline status: /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260529-195217.md
latest gap decision: /mnt/nas/openclaw/reports/baseline-status/baseline_gap_decision_20260529-195218.md
```

Tracking impact:

- B-003 remains `doing`, but Dream 7B now has a two-step gate: readiness first,
  then bounded smoke after model files and config exist.
- B-008 remains `doing`; the required HA URL/token shape is documented without
  committing secrets.
- B-009 and B-010 remain disabled-by-default; no action, service, or firewall
  execution is enabled by this update.

## 2026-05-29 Teacher Briefing Probe Update

Added a read-only generator for the teacher-facing two-baseline briefing:

```text
script: scripts/probes/teacher_baseline_briefing_probe.sh
tool_id: teacher_baseline_briefing_probe
output: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_*.md
```

Tracking impact: this does not close any blocked external-input gate, but it
turns the latest NAS evidence into a repeatable report that directly answers
the two supervisor questions without hand-editing the snapshot each time.

Evidence:

```text
runner report: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_20260529-200427.md
OpenClaw report: /root/.openclaw/workspace/reports/teacher/teacher_baseline_briefing_20260529-200724.md
A-010: 80 snapshots, 25.66h, collecting
Dream 7B: readiness=blocked_no_model; smoke=blocked_no_config
```

## 2026-05-29 Overnight Teacher Briefing Update

The future overnight runner loop now includes `teacher_baseline_briefing_probe`
after `baseline_gap_decision_probe`, and the summary helper surfaces
`latest_teacher_baseline_briefing`.

Evidence:

```text
manual teacher briefing: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_20260529-201154.md
overnight summary: /mnt/nas/openclaw/reports/baseline-status/overnight_baseline_20260529-162329_summary.md
latest_teacher_baseline_briefing: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_20260529-201154.md
completed_iterations_observed: 8
failed_event_count: 0
```

Tracking impact: future overnight evidence will include a refreshed supervisor-facing report in the same NAS-backed evidence stream as A-010 stability and baseline gap reports.

## 2026-05-29 Acceptance Gate Update

Added a read-only acceptance matrix:

```text
script: scripts/probes/baseline_acceptance_probe.sh
tool_id: baseline_acceptance_probe
output: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_*.md
```

Tracking impact: final baseline completion is now auditable item by item. The
gate keeps A-010 as `collecting`, B-003 as externally blocked by missing model
files/config, B-008 as blocked by missing HA config, B-009 as blocked by missing
reviewed action approval, and B-010 as blocked by missing service confirmations.

Evidence:

```text
runner report: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_20260529-202537.md
OpenClaw report: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260529-202642.md
overall: not_ready
pass count: 14
A-010 latest: 82 snapshots, 26.16h, collecting
not ready: A-006, A-010, B-003, B-008, B-009, B-010
```

## 2026-05-29 Acceptance Trend Update

Added a read-only trend report over saved acceptance snapshots:

```text
script: scripts/probes/baseline_acceptance_trend_probe.sh
tool_id: baseline_acceptance_trend_probe
output: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_trend_*.md
```

Tracking impact: long-running A-010 evidence can now show not only the latest
gate status, but whether any item changed between acceptance snapshots. Future
overnight runner launches will generate both acceptance and acceptance-trend
reports per iteration.

Evidence:

```text
runner trend report: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_trend_20260529-203510.md
OpenClaw trend report: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_trend_20260529-203703.md
source_count: 2
latest_overall: not_ready
changed_items: none
```

## 2026-05-29 Evidence Manifest Update

Added a read-only evidence manifest:

```text
script: scripts/probes/baseline_evidence_manifest_probe.sh
tool_id: baseline_evidence_manifest_probe
output: /mnt/nas/openclaw/reports/baseline-status/baseline_evidence_manifest_*.md
```

Tracking impact: the current acceptance, trend, teacher briefing, stability, model, HA, control, security, document, image, experiment, browser, and ROS evidence files can now be hashed and recorded in a single manifest for later review.

Evidence:

```text
runner manifest: /mnt/nas/openclaw/reports/baseline-status/baseline_evidence_manifest_20260529-204913.md
OpenClaw manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260529-205038.md
runner entry_count: 35
OpenClaw entry_count: 36
missing_count: 0
```

## 2026-05-29 Overnight Runner Queue Update

Added a bounded queue so the next updated overnight runner starts only after
the currently running sampler exits. This avoids concurrent sampler processes
while ensuring future iterations include the newer acceptance, trend, evidence
manifest, and teacher briefing probes.

Evidence:

```text
script: scripts/queue_next_overnight_baseline_runner.sh
status script: scripts/check_overnight_queue.sh
remote install: /root/.openclaw/workspace/scripts
bash syntax: pass
current runner pid: 278801
current runner status: running
current runner completed iterations: 10
current runner failed events: 0
queue pid: 362168
queue status report: /mnt/nas/openclaw/reports/baseline-status/overnight_queue_status_20260529-210410.md
latest queue status report: /mnt/nas/openclaw/reports/baseline-status/overnight_queue_status_20260529-211239.md
queue log: /mnt/nas/openclaw/logs/overnight/overnight_queue_20260529-210322.log
queue status: running, waiting_for_pid=278801
duplicate queue attempt: refused, existing pid=362168
```

Tracking impact: A-010 remains `doing`. The collection stream is now protected
against a gap after the old runner exits, and the next 10-hour runner will use
the updated evidence loop.

## 2026-05-30 Windows S100P Entrypoint Update

Added a fixed Windows-side PowerShell entrypoint to reduce repeated approval
prompts from changing ad-hoc SSH command strings:

```text
script: scripts/windows/s100p-task.ps1
docs: scripts/windows/README.md
progress doc: docs/baseline_progress_2026-05-30_windows_s100p_entrypoint.md
stable prefix: powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1
```

Validated actions:

```text
ssh-smoke: S100P_SSH_OK, ubuntu, sunrise
diagnose-nas: eth0 UP, 169.254.8.10/16, 169.254.110.209 neighbor FAILED
diagnose-openclaw: openclaw-gateway.service active, loopback gateway listener
```

Tracking impact: this does not close any baseline acceptance item directly,
but it gives future A-010/B-track checks a stable Windows command boundary and
keeps routine S100P operations behind a bounded action set.

## 2026-05-30 NAS Hold

NAS recovery is intentionally paused because the operator is away from the
physical NAS and cannot reboot it or inspect the Ethernet port.

Evidence:

```text
PC -> S100P: ok
S100P eth0: UP, 169.254.8.10/16
S100P internet/DNS: ok
OpenClaw gateway: active
NAS target: 169.254.110.209
NAS neighbor: FAILED / INCOMPLETE
NAS ping: 0 received
```

Tracking impact: A-003/A-010 and NAS-backed B-track evidence collection cannot
be completed while NAS has no L2/ARP response. Resume from
`docs/baseline_progress_2026-05-30_nas_blocked_hold.md` after checking NAS
power, Ethernet port/cable, and static IP.
