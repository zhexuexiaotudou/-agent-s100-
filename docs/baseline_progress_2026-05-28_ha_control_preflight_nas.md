# Baseline Progress: NAS-backed Home Assistant And Control Preflight

Date: 2026-05-28

本文记录 B-008 和 B-009 的 NAS-backed 预检。两项都只做只读/策略检查，不接真实设备，
不调用控制接口，也不执行任何控制动作。

## Verdict

| Baseline | 当前状态 | 证据 |
| --- | --- | --- |
| B-008 Home Assistant / 设备只读状态 | doing | NAS-backed read-only preflight 已生成；阻塞在没有 `HOME_ASSISTANT_URL` 和 token。 |
| B-009 低风险自动化控制 | doing | NAS-backed control policy preflight 已生成；阻塞在没有控制 allowlist policy。 |

## B-008 Home Assistant Read-only Preflight

输出：

```text
/mnt/nas/openclaw/logs/probes/home_assistant_status_20260528-183050.md
```

关键字段：

```text
mode: read-only
control_api_called: no
services_api_called: no
URL configured: no
Token configured: no
GET /api/ status: not_attempted
GET /api/states status: not_attempted
Verdict: blocked_no_config
```

当前结论：

- B-008 的工具链可以把预检报告写入 NAS。
- 因为没有 Home Assistant URL/token，未发起任何 API 请求。
- 后续只有在用户提供 URL/token 后，才会调用 `GET /api/` 和 `GET /api/states`。

## B-009 Control Policy Preflight

输出：

```text
/mnt/nas/openclaw/logs/probes/control_action_policy_20260528-183050.md
```

关键字段：

```text
mode: read-only policy and audit preflight
action_executed: no
control_endpoint_called: no
Policy status: missing
Action count: 0
Audit JSONL files: 0
Pending records: 0
Approved records: 0
Executed records: 0
Verdict: blocked_no_policy
```

当前结论：

- B-009 的 preflight 可以写入 NAS。
- 当前没有任何控制策略，也没有执行任何控制动作。
- 后续只有在创建并审阅 `control_action_allowlist.json` 后，才考虑实现 request/approve/execute 路径。

## Updated Roll-up

预检完成后重跑了 NAS-backed baseline status：

```text
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-183114.md
```

关键变化：

```text
Probe reports: 13
Workspace reports: 12
Home Assistant status: /mnt/nas/openclaw/logs/probes/home_assistant_status_20260528-183050.md
Control action policy: /mnt/nas/openclaw/logs/probes/control_action_policy_20260528-183050.md
```

这两项均保持 `doing`，因为真正读取设备状态和控制策略都需要用户提供外部配置或明确审批。
