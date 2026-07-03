# Baseline Progress: B-009 Control Template Local Refresh

Date: 2026-05-30

The half-hour audit gate still reports:

```text
decision: continue-non-nas-readonly-only
NAS target: 169.254.110.209 unreachable
S100P SSH: ok
OpenClaw gateway: ok
```

This pass stayed read-only. It generated a B-009 reviewed-action template
artifact and reran the control policy preflight without writing the runtime
allowlist, calling Home Assistant, or executing any control action.

## New Gate Artifact

```text
script: scripts/probes/control_action_template_probe.sh
tool_id: control_action_template_probe
report: /root/.openclaw/workspace/reports/control/control_action_template_20260530-161443.md
json: /root/.openclaw/workspace/reports/control/control_action_template_20260530-161443.json
target runtime policy: /root/.openclaw/workspace/config/control_action_allowlist.json
```

The template includes:

```text
disabled reviewed-action draft
request audit record template
approval audit record template
retention policy shape
```

## Current Signals

```text
runtime_policy: present
home_assistant_config: missing
audit_directory: present
control_verdict: policy_ready_no_execution
enabled actions: 0
executed records: 0
```

## Latest Report Chain

```text
control template: /root/.openclaw/workspace/reports/control/control_action_template_20260530-161443.md
control policy: /root/.openclaw/workspace/logs/probes/control_action_policy_20260530-161443.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-161443.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-161443.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-161444.md
```

## Tracking Impact

B-009 remains `blocked_review`. The missing step is no longer ambiguous: review
real Home Assistant entity/action entries, deliberately write the runtime
allowlist, then add request/approve/execute audit records before any execution
path can be considered.
