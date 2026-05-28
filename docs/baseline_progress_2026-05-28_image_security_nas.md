# Baseline Progress: NAS-backed Image Caption And Security Audit

Date: 2026-05-28

本文记录两项不需要外部审批的 NAS-backed 复测：B-003 图片 metadata caption，
以及 B-010 security audit。

## Verdict

| Baseline | 当前状态 | 证据 |
| --- | --- | --- |
| B-003 图片 caption baseline | doing | NAS-backed deterministic metadata caption 和 JSONL index 已跑通；semantic vision caption 仍未做。 |
| B-010 安全审计清单 | doing | NAS-backed security audit 已生成，Gateway loopback-only、NAS mounted、secret scan pass；服务收敛策略仍未定。 |

## B-003 Image Caption

输入样本：

```text
/mnt/nas/openclaw/photos/browser-smoke/browser_smoke_20260528-182111.png
```

该样本来自 A-007 browser smoke 的真实 NAS 截图。输出：

```text
/mnt/nas/openclaw/reports/image-captions/image_caption_index_20260528-182530.md
/mnt/nas/openclaw/reports/image-captions/image_caption_index_20260528-182530.jsonl
```

关键字段：

```text
Image records: 1
relative_path: browser-smoke/browser_smoke_20260528-182111.png
caption: Image file browser smoke browser smoke 20260528 182111, 780x493px
bytes: 25855
dimensions: 780x493
sha256: adf57bdac4f2a7d5d71d46f63bb15530c7d50195f691976490659456bead6c9c
```

当前结论：

- B-003 已从 `todo` 推进到 `doing`。
- metadata caption 和 JSONL 搜索记录可以落到 NAS。
- 这还不是语义视觉 caption；后续要么接入视觉模型，要么明确第一版只做 metadata caption。

## B-010 Security Audit

输出：

```text
/mnt/nas/openclaw/logs/probes/security_audit_20260528-182530.md
```

Verdict matrix：

```text
OpenClaw config validation: pass
Gateway exposure: pass, loopback only
Tavily plugin: pass
S100P allowlisted plugin: pass
Non-loopback listeners: warn, 19 non-loopback listeners
NAS workspace mount: pass, mounted
Workspace secret scan: pass, no secret-like text found in scanned workspace files
```

关键安全结论：

- OpenClaw Gateway 仍只监听 `127.0.0.1:18789`、`127.0.0.1:18791` 和 `[::1]:18789`，没有暴露到非 loopback。
- NAS workspace 已挂载，且安全审计报告可以写入 NAS。
- NAS workspace 扫描未发现 secret-like text。
- 仍有 19 个非 loopback listener 需要人工服务策略决策，主要类别：
  - NFS/RPC: `rpcbind`、`rpc.mountd`、`rpc.statd`、`2049`
  - remote desktop: `x11vnc:5900`
  - hardware daemon: `iiod:30431`
  - admin: `sshd:22`

当前结论：

- B-010 仍保持 `doing`，因为我不应在无人值守时关闭远程桌面、RPC/NFS 或硬件 daemon。
- 可以确认安全审计本身已经 NAS-backed；后续要做的是服务 keep/disable/firewall 决策和复测。

## Deferred Because It Needs User Or Policy Approval

- 是否禁用 S100P 本机 NFS server/RPC 服务。
- 是否禁用 `x11vnc`，或者仅在需要 RDK Studio 桌面时保留。
- 是否禁用或防火墙限制 `iiod`。
- 飞书 contact scope `99991672` 权限申请。
- A-006 Docker/Podman/runc sandbox runtime 选择。
