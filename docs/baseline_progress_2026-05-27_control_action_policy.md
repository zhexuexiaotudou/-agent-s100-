# B-009 Control Action Policy Progress

## Objective

Add the first safe gate for low-risk automation control: policy and audit
preflight only, without executing any action.

## Implementation

```text
script: scripts/probes/control_action_policy_probe.sh
allowlist id: control_action_policy_probe
default output: /root/.openclaw/workspace/logs/probes
policy path: /root/.openclaw/workspace/config/control_action_allowlist.json
audit path: /root/.openclaw/workspace/logs/control-audit
runbook: docs/control_action_policy_runbook.md
```

The probe explicitly reports:

```text
action_executed: no
control_endpoint_called: no
```

## Current Expected State

Without a reviewed control policy file, the expected verdict is:

```text
blocked_no_policy
```

That proves the B-009 preflight path exists and refuses to imply control
readiness before a whitelist and confirmation phrase are reviewed.

## Validation Evidence

Board runner evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061806.md
action_executed: no
control_endpoint_called: no
Policy status: missing
Audit JSONL files: 0
Verdict: blocked_no_policy
```

OpenClaw agent evidence:

```text
OpenClaw runId: f164f6ea-caf6-4581-929c-eed39b105ecc
OpenClaw report: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061906.md
agent status: ok
verdict: blocked_no_policy
action_executed: no
```

Baseline roll-up evidence:

```text
report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-061920.md
Allowlisted tool count: 19
Progress docs: 19
Control action policy: /root/.openclaw/workspace/logs/probes/control_action_policy_20260527-061906.md
NAS workspace: not_mounted
```

Tracking status: B-009 is now `doing`. The policy/audit preflight path is
verified; real control remains blocked until a reviewed disabled allowlist,
two-step approval path, and audit retention policy exist.
