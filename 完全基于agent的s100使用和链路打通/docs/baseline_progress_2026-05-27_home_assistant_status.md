# B-008 Home Assistant Read-Only Status Progress

## Objective

Add a safe preflight path for Home Assistant or device-state integration:
read-only status checks first, no device control.

## Implementation

```text
script: scripts/probes/home_assistant_status_probe.sh
allowlist id: home_assistant_status_probe
default output: /root/.openclaw/workspace/logs/probes
runbook: docs/home_assistant_status_runbook.md
```

The probe only attempts:

```text
GET /api/
GET /api/states
```

It explicitly does not call `/api/services` or any control endpoint.

## Current Expected State

If no Home Assistant URL/token is configured on the S100P, the expected verdict
is:

```text
blocked_no_config
```

That still proves the B-008 tool path exists and remains read-only. Final B-008
verification requires real Home Assistant URL/token plus successful `200`
responses from both read-only endpoints.

## Validation Evidence

Board runner evidence:

```text
runner report: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061143.md
control_api_called: no
services_api_called: no
GET /api/ status: not_attempted
GET /api/states status: not_attempted
verdict: blocked_no_config
```

OpenClaw agent evidence:

```text
OpenClaw runId: e08850e5-7d55-4dcc-814c-a26b22cf8c80
OpenClaw report: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061252.md
agent status: ok
verdict: blocked_no_config
```

Baseline roll-up evidence:

```text
report: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260527-061310.md
Allowlisted tool count: 18
Progress docs: 18
Home Assistant status: /root/.openclaw/workspace/logs/probes/home_assistant_status_20260527-061252.md
NAS workspace: not_mounted
```

Tracking status: B-008 is now `doing`. The read-only tool path is verified; the
real Home Assistant state read remains blocked until URL/token are provided.
