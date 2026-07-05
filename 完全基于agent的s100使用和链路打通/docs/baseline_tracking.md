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
config/home_assistant_env_example.txt
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

## 2026-05-30 Half-Hour Audit Loop

Added a fixed half-hour audit loop before continuing the two baseline tracks:

```text
runbook: docs/baseline_audit_runbook.md
script: scripts/windows/baseline-audit.ps1
pid file: logs/baseline-audit/baseline_audit_loop.pid
latest report: logs/baseline-audit/baseline_audit_20260530-151543.md
decision: continue-non-nas-readonly-only
```

Tracking impact: the current path is allowed to continue only for non-NAS
read-only work. NAS-backed refreshes and overnight status checks stay held while
`169.254.110.209` remains unreachable from S100P.

## 2026-05-30 B-003 Local Readiness While NAS Is Held

Updated `dream7b_readiness_probe` so it skips `/mnt/nas/openclaw/models` when
the NAS mount point is only `autofs` and not a real NFS/CIFS mount. This keeps
non-NAS read-only B-003 checks from blocking on the current NAS L2/IP issue.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_dream7b_local_readiness_no_nas.md
report: /root/.openclaw/workspace/reports/models/dream7b_readiness_20260530-152249.md
verdict: blocked_no_model
runtime summary: llama.cpp,torch-transformers
model-like files: 0
NAS model dir: skipped_not_mounted, fstype=autofs
```

Tracking impact: B-003 remains `doing`, but the current blocker is now more
precise: local runtime exists, local model files are absent, and NAS-backed
model discovery is paused until the NAS link comes back.

## 2026-05-30 Local Read-Only Baseline Refresh

Added a bounded Windows entrypoint for non-NAS read-only progress:

```text
script: scripts/windows/s100p-task.ps1
action: refresh-baseline-local-readonly
progress doc: docs/baseline_progress_2026-05-30_local_readonly_refresh.md
```

The action writes reports under `/root/.openclaw/workspace` only, and the
report generators now label this as local fallback evidence rather than
NAS-backed evidence.

Latest local fallback evidence:

```text
security audit: /root/.openclaw/workspace/logs/probes/security_audit_20260530-161432.md
service preflight: /root/.openclaw/workspace/reports/security/service_execution_preflight_20260530-161442.md
service confirmation template: /root/.openclaw/workspace/reports/security/service_confirmation_template_20260530-161442.md
control action template: /root/.openclaw/workspace/reports/control/control_action_template_20260530-161443.md
sandbox status: /root/.openclaw/workspace/logs/probes/sandbox_status_20260530-161442.md
sandbox smoke: /root/.openclaw/workspace/logs/probes/sandbox_isolation_smoke_20260530-161443.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-161443.md
teacher briefing: /root/.openclaw/workspace/reports/teacher/teacher_baseline_briefing_20260530-161443.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-161443.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-161444.md
NAS workspace mount check: warn, autofs_not_reached, fstype=autofs
NAS workspace: autofs_not_reached
artifact scope: local workspace fallback; NAS not verified
overall: not_ready
A-006: blocked_runtime, runtime_available=no, runtime_choice=missing, smoke=blocked_runtime_missing
B-009: blocked_review, template present, enabled=0, executed=0
B-010 preflight: blocked_no_confirmations, template present
```

Tracking impact: A-003 and B-001 are now correctly marked not ready while NAS is
only an autofs mount point. B-010 is also explicitly gated by missing service
convergence confirmations, so no service disable or firewall change is allowed
from this lane. The refresh order now generates teacher briefing before
acceptance/trend/manifest, so the final manifest hashes the same-round evidence
pack. A-006 is now driven by the latest sandbox status and isolation smoke
reports rather than a hard-coded blocked state; current package candidates
exist, but no runtime was installed because the active audit lane is read-only.
B-010 now has a same-round machine-readable confirmation template artifact, but
the runtime confirmation config remains deliberately absent. B-009 now has a
same-round reviewed-action/audit template artifact, but the runtime control
allowlist remains deliberately disabled and no action was executed. Non-NAS
read-only reporting can continue without overstating NAS-backed acceptance.

## 2026-05-30 A-006 Sandbox Gate Refresh

Refreshed the sandbox gate so A-006 can move based on real evidence instead of
static acceptance text.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_a006_sandbox_gate_refresh.md
sandbox status: /root/.openclaw/workspace/logs/probes/sandbox_status_20260530-155716.md
sandbox smoke: /root/.openclaw/workspace/logs/probes/sandbox_isolation_smoke_20260530-155717.md
docker/podman/runc/containerd: missing
package candidates: docker.io, podman, containerd, runc available for arm64
free space: 29G on / and /var
sunrise subuid/subgid: present
acceptance: A-006 blocked_runtime, smoke=blocked_runtime_missing
```

Tracking impact: A-006 remains blocked because no sandbox runtime is installed,
but the next step is now explicit and auditable. The new smoke probe is
allowlisted and will not install packages or pull images; when the audit lane
permits a non-read-only system change, install one runtime package, provide an
approved local image if needed, and rerun the bounded isolation smoke that
proves only approved temporary mounts are writable.

## 2026-05-30 B-010 Confirmation Template Refresh

Added a read-only confirmation template artifact for B-010 so the service
convergence decision is no longer only prose.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_b010_confirmation_template_local.md
confirmation template: /root/.openclaw/workspace/reports/security/service_confirmation_template_20260530-160717.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-160717.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-160718.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-160718.md
current signals: gateway_loopback=yes, ssh_present=yes, nfs_rpc_present=yes, x11vnc_present=no, vnc_listening=yes, iiod_present=yes, iiod_listening=yes
```

Tracking impact: B-010 remains `blocked_confirmations`. The template is a report
artifact only; it is not copied to
`/root/.openclaw/workspace/config/service_convergence_confirmations.json` and
does not approve any service or firewall changes.

## 2026-05-30 B-009 Control Template Refresh

Added a read-only reviewed-action template artifact for B-009 so the control
path has a machine-readable request/approval shape before any execution path is
implemented.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_b009_control_template_local.md
control template: /root/.openclaw/workspace/reports/control/control_action_template_20260530-161443.md
control policy: /root/.openclaw/workspace/logs/probes/control_action_policy_20260530-161443.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-161443.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-161443.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-161444.md
```

Tracking impact: B-009 remains `blocked_review`. The template is a report
artifact only; it is not copied to
`/root/.openclaw/workspace/config/control_action_allowlist.json` and does not
call Home Assistant or any device API.

## 2026-05-30 B-008 Home Assistant Template Refresh

Added a read-only Home Assistant configuration template artifact for B-008 so
the external config requirement is explicit before any real HA read is tried.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_b008_home_assistant_template_local.md
config template: /root/.openclaw/workspace/reports/home-assistant/home_assistant_config_template_20260530-162335.md
status probe: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260530-162335.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-162335.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-162335.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-162336.md
manifest entry: home_assistant_template true sha256=157a04e234999bf1
```

Tracking impact: B-008 remains `blocked_external_config`. The template is a
report artifact only; it is not copied to
`/root/.openclaw/workspace/config/home_assistant.env`, does not print or store a
real token, and does not call Home Assistant. The read-only status probe
correctly stayed at `blocked_no_config`.

## 2026-05-30 B-003 Dream 7B Config Template Refresh

Added a read-only Dream 7B deployment configuration template artifact for B-003
so the missing runtime config step is explicit before any bounded smoke test is
attempted.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_b003_dream7b_config_template_local.md
config template: /root/.openclaw/workspace/reports/models/dream7b_config_template_20260530-163050.md
readiness: /root/.openclaw/workspace/reports/models/dream7b_readiness_20260530-163050.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-163051.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-163051.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-163051.md
manifest entry: dream7b_config_template true sha256=7cf73c7e864136eb
```

Tracking impact: B-003 remains `blocked_external_model`. The template is a
report artifact only; it is not copied to
`/root/.openclaw/workspace/config/dream7b_deployment.json`, does not download
model files, does not start a model server, and does not run inference.

## 2026-05-30 B-002 Local Document Summary Refresh

Added deterministic local document index and daily summary generation to the
`refresh-baseline-local-readonly` lane when
`/root/.openclaw/workspace/documents` exists.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_b002_document_summary_local.md
document index: /root/.openclaw/workspace/reports/document_index_20260530-163624.md
daily summary: /root/.openclaw/workspace/reports/daily-summary/document_daily_summary_20260530-163624.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-163636.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-163637.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-163637.md
manifest entries: document_daily_summary true sha256=492d1224b42b3300; document_index true sha256=a26cc08bd4b67493
```

Tracking impact: B-002 now has both local fallback document index and daily
summary evidence. This is deterministic metadata reporting only; NAS-backed
document coverage still waits for the NAS link to recover.

## 2026-05-30 A-003 NAS Link Blocker Refresh

Added targeted read-only NAS link blocker evidence to the
`refresh-baseline-local-readonly` lane.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_a003_nas_link_blocker_local.md
nas link blocker: /root/.openclaw/workspace/logs/probes/nas_link_blocker_20260530-164450.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-164504.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-164505.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-164505.md
manifest entry: nas_link_blocker true sha256=5d6b616e5e2d2cf5
verdict: blocked_l2_no_neighbor
```

Tracking impact: A-003 and B-001 remain failed, but the failure is now tied to
same-round link evidence: S100P routes the target through `eth0`, ping receives
0 packets, and the neighbor state is `FAILED`/`INCOMPLETE`. Restore NAS L2/IP
reachability before any mount or credential work can succeed.

## 2026-05-30 A-010 Local Stability Refresh

Added local fallback A-010 stability snapshot and summary generation to the
`refresh-baseline-local-readonly` lane.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_a010_local_stability_refresh.md
snapshot: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260530-164956.md
summary: /root/.openclaw/workspace/reports/stability/stability_summary_20260530-165005.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-165019.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-165019.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-165019.md
manifest entry: stability_summary true sha256=74ab0bf0bf1bdeac
snapshot count: 82
elapsed hours: 83.62
verdict: collecting
```

Tracking impact: A-010 remains `collecting`, but the local fallback evidence
stream now continues while NAS-backed collection is blocked. The latest
snapshot records NAS as `autofs_not_reached` and skips `df /mnt/nas/openclaw`
unless the NAS workspace is a real NFS/CIFS mount.

## 2026-05-30 A-009 Named Capture Request Refresh

Added a read-only named-capture request template to the
`refresh-baseline-local-readonly` lane and tightened A-009 acceptance so policy
readiness is not confused with a completed named capture.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_a009_named_capture_request_local.md
request template: /root/.openclaw/workspace/reports/rosbag/rosbag_named_capture_request_20260530-165826.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-165839.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-165839.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-165839.md
manifest entry: rosbag_capture_request true sha256=fac1165b95bbf5a7
acceptance: A-009 review, named=missing
```

Tracking impact: A-009 now has a fixed approval/request artifact, but it is not
final. A real approved named capture must still be run before A-009 is treated
as verified.

## 2026-05-30 B-005/B-007 Local Report Refresh

Added local fallback log diagnosis and experiment report generation to the
`refresh-baseline-local-readonly` lane.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_b005_b007_local_report_refresh.md
log diagnosis: /root/.openclaw/workspace/logs/probes/log_diagnosis_20260530-170419.md
experiment report: /root/.openclaw/workspace/reports/experiments/experiment_report_20260530-170419.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-170420.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-170420.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-170420.md
manifest entries: log_diagnosis true sha256=89dd45b7ea77b089; experiment_report true sha256=a0ecfec1576075df
```

Tracking impact: B-005 and B-007 now refresh same-round local fallback evidence
inside the main report loop. NAS-backed report acceptance remains held until
the NAS link is restored.

## 2026-05-30 A-007/B-004 Local Refresh

Added local browser smoke refresh and read-only dataset card inventory to the
`refresh-baseline-local-readonly` lane.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_a007_b004_local_refresh.md
browser smoke: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260530-171336.md
browser verdict: ok
dataset inventory: /root/.openclaw/workspace/reports/robot-datasets/dataset_card_inventory_20260530-171340.md
dataset card count: 4
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-171354.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-171354.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-171355.md
```

Tracking impact: A-007 is now current local fallback evidence, not a stale
2026-05-27 report. B-004 has a current inventory over the four existing dataset
cards. A-009 remains `review` because inventory/request artifacts are not a
substitute for a real approved named capture.

## 2026-05-30 Audit Consistency Hardening

Hardened the half-hour audit loop so it checks local script conventions and
remote script parseability, not only route selection.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_audit_consistency_hardening.md
manual audit: logs/baseline-audit/baseline_audit_20260530-172027.md
background loop pid: 152304
background loop first report: logs/baseline-audit/baseline_audit_20260530-172101.md
decision: continue-non-nas-readonly-only
jsonSyntaxOk: True
allowlistConsistencyOk: True
remoteScriptValidationOk: True
```

Tracking impact: future probe additions now fail the audit if
`tool_allowlist.json`, `scripts/run_allowlisted_tool.sh`, local script files,
or S100P-side Bash/JSON syntax drift apart. NAS-backed work remains blocked by
the same L2/IP reachability failure.

## 2026-05-30 Next Action Queue

Added a read-only lane-aware next-action queue to the local fallback refresh
loop.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_next_action_queue.md
next action queue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-173108.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-173108.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-173108.md
manifest entry: baseline_next_action_queue true sha256=6b24a7a693d4c01c
```

Tracking impact: the current queue says A-010 collection is the only safe
continuing action under `continue-non-nas-readonly-only`. The remaining
not-ready items are explicitly classified as external link, external runtime,
external input, or operator-review prerequisites.

## 2026-05-30 A-010 Checkpoint Projection

Added a read-only A-010 checkpoint projection to the local fallback refresh
loop.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_a010_checkpoint_projection.md
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-173803.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-173819.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-173820.md
manifest entry: stability_checkpoint true sha256=f12c0c8f5c2f1279
```

Current checkpoint:

```text
snapshot_count: 89
elapsed_hours: 84.42
remaining_hours: 83.58
eta_at_current_span: 2026-06-03T05:12:41+08:00
median_interval_hours: 0.5
max_interval_hours: 46.66
gateway_error_snapshots: 0
oom_error_snapshots: 0
checkpoint_status: collecting
```

Tracking impact: A-010 remains `collecting`, but the remaining 7x24 window is
now explicit and machine-readable. Continue read-only snapshots until at least
168 elapsed hours, then generate final A-010 acceptance evidence.

### 2026-05-30 A-010 Continuity Correction

The A-010 checkpoint now distinguishes total snapshot span from continuous
coverage. A gap larger than 2 hours resets the continuous window.

Evidence:

```text
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-174510.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-174526.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-174526.md
manifest entry: stability_checkpoint true sha256=7d842b58b5149165
```

Current continuity-aware checkpoint:

```text
snapshot_count: 90
elapsed_hours: 84.54
max_gap_hours: 2.0
gap_event_count: 1
largest_gap_hours: 46.66
continuous_start: 2026-05-30T16:48:29+08:00
continuous_elapsed_hours: 0.94
continuous_remaining_hours: 167.06
continuous_eta: 2026-06-06T16:48:29+08:00
checkpoint_status: collecting
```

Tracking impact: the previous total-span ETA is not sufficient for A-010
acceptance. Continue collecting against the continuous-window clock.

### 2026-05-30 A-010 Automatic Audit Refresh

Added a scoped A-010 refresh path to the half-hour audit loop.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_a010_automatic_audit_refresh.md
background loop pid: 133404
audit report: logs/baseline-audit/baseline_audit_20260530-175041.md
audit command result: s100p-refresh-a010-local-readonly exit=0
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-175057.md
```

Latest automatic checkpoint:

```text
snapshot_count: 93
elapsed_hours: 84.64
continuous_start: 2026-05-30T16:48:29+08:00
continuous_elapsed_hours: 1.04
continuous_remaining_hours: 166.96
continuous_eta: 2026-06-06T16:48:29+08:00
checkpoint_status: collecting
```

Tracking impact: A-010 now advances automatically every half-hour audit cycle
while the loop is running and the audit decision allows non-NAS read-only work.

### 2026-05-30 A-010 Structured Audit Metrics

The audit loop now reads the latest A-010 checkpoint JSON after the automatic
refresh and embeds the core continuity metrics directly in each audit Markdown
and JSON report.

Evidence:

```text
background loop pid: 145804
audit report: logs/baseline-audit/baseline_audit_20260530-175806.md
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-175822.md
```

Latest embedded audit metrics:

```text
checkpointStatus: collecting
snapshotCount: 97
elapsedHours: 84.76
maxGapHours: 2.0
gapEventCount: 1
continuousStartAt: 2026-05-30T16:48:29+08:00
continuousElapsedHours: 1.16
continuousRemainingHours: 166.84
continuousEta: 2026-06-06T16:48:29+08:00
snapshotsWithGatewayErrors: 0
snapshotsWithOomErrors: 0
```

Tracking impact: routine audit review no longer requires opening S100P-side
checkpoint files; the local audit report is enough to confirm whether A-010 is
still collecting cleanly.

## 2026-05-30 Managed Audit Loop

Added a managed loop entrypoint so persistent audit operations no longer depend
on ad-hoc process launch commands.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_managed_audit_loop.md
script: scripts/windows/baseline-audit-loop.ps1
pid: 148112
latest report: logs/baseline-audit/baseline_audit_20260530-180250.md
started metadata: logs/baseline-audit/baseline_audit_loop.started.json
refreshA010ReadOnly: true
```

Tracking impact: start/status/restart/stop for the half-hour audit loop now use
one fixed command surface. The loop still follows the current decision
vocabulary and continues only the scoped A-010 read-only refresh while NAS is
unreachable.

### 2026-05-30 Managed Audit Status Payload

The managed loop status command now surfaces the latest audit decision and
embedded A-010 continuity metrics directly.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_managed_audit_loop.md
script: scripts/windows/baseline-audit-loop.ps1
default output: JSON
PowerShell automation output: -AsObject
idempotent repair action: ensure
latestDecision: continue-non-nas-readonly-only
latest checkpoint status: collecting
continuous_eta: 2026-06-06T16:48:29+08:00
loopHealthy: true
latestReportFresh: true
ensure status: healthy, action=none
```

Tracking impact: routine half-hour review now has one stable local command for
operator and automation status checks. Reviewers can confirm the current lane,
local/remote consistency checks, A-010 progress, and NAS blocker findings
without manually opening the latest report files. The status payload also
detects stale output, so a running process without a fresh report is treated as
an audit-system failure rather than a healthy review loop. The `ensure` action
adds an unattended repair path for a missing or stale loop while keeping process
launches behind the same managed command surface.

### 2026-05-30 Audit Watchdog

Added a managed watchdog around the half-hour audit loop.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_audit_watchdog.md
script: scripts/windows/baseline-audit-watchdog.ps1
startup task script: scripts/windows/baseline-audit-watchdog-task.ps1
watchdog pid: 150532
watchdogHealthy: true
heartbeatFresh: true
heartbeatClean: true
last heartbeat ensureStatus: healthy
last heartbeat ensureAction: none
guarded audit loop pid: 148112
guarded audit loop healthy: true
latest decision: continue-non-nas-readonly-only
startup task: Digua-Baseline-Audit-Watchdog
startup task installed: true
startup task last run: 2026-05-30T18:30:32+08:00
startup task last result: 0
```

Tracking impact: the audit loop is now supervised by a second local process
that calls the managed `ensure` action every 5 minutes. This keeps the requested
half-hour review cadence alive without requiring manual checks unless the
watchdog itself reports unhealthy. The Windows logon task now calls the
watchdog `ensure` action after login, so the audit supervision recovers after a
user login without a manual shell command.

### 2026-05-30 Audit Supervision Status

Added a single read-only supervision status command.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_audit_supervision_status.md
script: scripts/windows/baseline-audit-supervision.ps1
supervisionHealthy: true
baselineLane: continue-non-nas-readonly-only
startupTaskHealthy: true
safeProgressTaskHealthy: true
watchdogHealthy: true
loopHealthy: true
latestReportFresh: true
requiredChecksOk: true
a010Readable: true
safe progress task next run: 2026-05-30T19:30:25+08:00
safe progress task repetition: PT30M
latest audit report: logs/baseline-audit/baseline_audit_20260530-192508.md
A-010 snapshotCount: 122
FailOnUnhealthy: exit=0
```

Tracking impact: new baseline work can now start by running one status command
instead of manually checking the scheduled tasks, watchdog, managed audit loop,
latest audit JSON, safe-progress cadence, and A-010 checkpoint separately.

## 2026-05-30 Local Read-Only Refresh 18:39

Ran a supervision-gated local read-only refresh for both baseline tracks.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_local_refresh_1839.md
supervisionHealthy: true
baselineLane: continue-non-nas-readonly-only
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-183954.md
next action queue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-183955.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-183955.md
overall: not_ready
pass: 11
fail: 2
collecting: 1
manifest entry_count: 83
manifest missing_count: 0
A-010 snapshot_count: 110
A-010 continuous_remaining_hours: 166.15
```

Tracking impact: the two baselines have fresh local fallback evidence under the
current non-NAS read-only lane. The only safe continuing action remains A-010
collection. `s100p-task.ps1` also gained the bounded
`read-remote-report-file` action so future report inspection stays behind the
same fixed Windows entrypoint instead of ad-hoc SSH.

## 2026-05-30 Safe Progress Runner

Added a lane-aware runner for routine baseline advancement.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_safe_progress_runner.md
script: scripts/windows/baseline-safe-progress.ps1
baselineLane: continue-non-nas-readonly-only
selectedRefreshAction: refresh-baseline-local-readonly
refreshExitCode: 0
outputPathCount: 32
runner report: logs/baseline-audit/baseline_safe_progress_20260530-193836.md
latestBaselineAcceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-193830.md
latestBaselineNextActionQueue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-193830.md
latestBaselineEvidenceManifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-193830.md
A-010 snapshotCount: 126
A-010 continuousRemainingHours: 165.17
latest audit report: logs/baseline-audit/baseline_audit_20260530-193345.md
latest audit A-010 snapshotCount: 124
completionAuditOk: true
completionProven: false
completionNotReadyCount: 9
completionAuditReport: logs/baseline-audit/baseline_completion_audit_20260530-193841.md
```

Tracking impact: a single command now handles supervision, lane selection, safe
refresh execution, evidence-path capture, and completion auditing. Under the
current lane it runs only the non-NAS local read-only refresh.

## 2026-05-30 Safe Progress Schedule

Added a Windows scheduled task for unattended lane-aware baseline refresh.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_safe_progress_schedule.md
task script: scripts/windows/baseline-safe-progress-task.ps1
task name: Digua-Baseline-Safe-Progress
interval: PT30M
task last run: 2026-05-30T20:00:26+08:00
task last result: 0
task next run: 2026-05-30T20:30:25+08:00
latest safe-progress report: logs/baseline-audit/baseline_safe_progress_20260530-200108.json
selectedRefreshAction: refresh-baseline-local-readonly
refreshExitCode: 0
outputPathCount: 33
A-010 snapshotCount: 131
A-010 continuousRemainingHours: 164.8
completionAuditOk: true
completionProven: false
completionNotReadyCount: 9
latest audit report: logs/baseline-audit/baseline_audit_20260530-201335.md
```

Tracking impact: the two-baseline local evidence refresh now runs on a 30-minute
cadence, but still passes through supervision health and audit-lane selection
before doing work.

Repair note: the 19:30 task failure came from safe-progress treating its own
previous scheduled-task result as a hard gate. Supervision now exposes a
reported internal repair-mode switch for the safe-progress runner, while normal
supervision still requires `safeProgressTaskHealthy=true`.

## 2026-05-30 Completion Audit

Added a final completion audit gate for the two baseline tracks.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_completion_audit.md
script: scripts/windows/baseline-completion-audit.ps1
completion audit: logs/baseline-audit/baseline_completion_audit_20260530-201323.md
completionProven: false
supervisionHealthy: true
baselineLane: continue-non-nas-readonly-only
acceptanceOverall: not_ready
itemCount: 20
provenCount: 11
notReadyCount: 9
FailIfIncomplete: exit=3
latest audit report: logs/baseline-audit/baseline_audit_20260530-201335.md
A-010 snapshotCount: 135
```

Tracking impact: completion is now machine-gated. The goal should remain active
until this audit reports `completionProven=true`; the current report lists the
nine not-ready baseline items and their required next actions.

## 2026-05-30 Operator Review Gate

Added a unified read-only operator review gate for A-009, B-009, and B-010.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_operator_review_gate.md
probe: scripts/probes/operator_review_gate_probe.sh
allowlist id: operator_review_gate_probe
review gate: /root/.openclaw/workspace/reports/review-gates/operator_review_gate_20260530-200101.md
overall: review_packets_ready
ready_count: 3
blocked_count: 0
A-009: ready_for_operator_review
B-009: ready_for_operator_review
B-010: ready_for_confirmation_review
safe-progress report: logs/baseline-audit/baseline_safe_progress_20260530-200108.md
latest acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-200102.md
latest next action queue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-200102.md
latest evidence manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-200102.md
manifest missing_count: 0
completionProven: false
completionNotReadyCount: 9
```

Tracking impact: the needs-operator-review items now have a maintained packet
gate. The system can prove that review materials are ready without treating
that readiness as approval to run capture, control, service, or firewall
actions.

The next-action queue now classifies A-009, B-009, and B-010 as
`ready_for_operator_decision`, instead of mixing them with incomplete review
packets.

## 2026-05-30 External Input Gate

Added a unified read-only external input gate for B-003 and B-008.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_external_input_gate.md
probe: scripts/probes/external_input_gate_probe.sh
allowlist id: external_input_gate_probe
external input gate: /root/.openclaw/workspace/reports/external-inputs/external_input_gate_20260530-201112.md
overall: external_input_packets_ready
ready_count: 2
blocked_count: 0
B-003: waiting_for_model_files_and_runtime_config
B-008: waiting_for_home_assistant_env
safe-progress report: logs/baseline-audit/baseline_safe_progress_20260530-201119.md
latest acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-201113.md
latest next action queue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-201113.md
latest evidence manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-201113.md
manifest missing_count: 0
completionProven: false
completionNotReadyCount: 9
```

Tracking impact: B-003 and B-008 are now represented as ready external-input
handoffs. The system can prove what input is missing without writing secrets,
moving model files, calling Home Assistant control APIs, or running model
inference.

## 2026-05-30 Infrastructure Gate

Added a unified read-only infrastructure gate for A-003, A-006, and B-001.

Evidence:

```text
progress doc: docs/baseline_progress_2026-05-30_infrastructure_gate.md
probe: scripts/probes/infrastructure_gate_probe.sh
allowlist id: infrastructure_gate_probe
infrastructure gate: /root/.openclaw/workspace/reports/infrastructure/infrastructure_gate_20260530-202335.md
overall: infrastructure_packets_ready
ready_count: 3
blocked_count: 0
A-003: waiting_for_nas_link_repair
A-006: waiting_for_runtime_install_or_scope_decision
B-001: waiting_for_nas_link_repair
safe-progress report: logs/baseline-audit/baseline_safe_progress_20260530-202343.md
latest acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-202337.md
latest next action queue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-202337.md
latest evidence manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-202337.md
manifest missing_count: 0
completionProven: false
completionNotReadyCount: 9
```

Tracking impact: A-003, A-006, and B-001 are now represented as ready
infrastructure-action handoffs. The system can prove what action is needed
without using NAS credentials, mounting filesystems, changing networking,
installing runtimes, or changing services/firewall.

The next-action queue now classifies A-003, A-006, and B-001 as
`ready_for_infrastructure_action`, instead of mixing them with incomplete
evidence or generic external blockers.

## 2026-05-30 Session-Only Audit Mode

Removed Windows-level recurring checks after clarifying that half-hour review
means Codex should review its own progress while actively working, not that the
computer should run scheduled checks by itself.

Evidence:

```text
safe progress task: Digua-Baseline-Safe-Progress uninstalled
watchdog task: Digua-Baseline-Audit-Watchdog uninstalled
audit loop: stopped
watchdog process: stopped
supervision mode: codex-session-only
supervisionHealthy: true
backgroundAutomationRequired: false
```

Tracking impact: the audit scripts and reports remain available, but there is
no OS-level 30-minute timer. Future Codex turns should run the audit gates
explicitly when doing work and review progress during the active session only.
