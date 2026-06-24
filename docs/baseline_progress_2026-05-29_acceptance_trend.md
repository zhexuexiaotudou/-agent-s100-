# Baseline Progress: Acceptance Trend

Date: 2026-05-29

This adds a read-only trend report over saved `baseline_acceptance_*.json` snapshots.

## Added

```text
script: scripts/probes/baseline_acceptance_trend_probe.sh
tool_id: baseline_acceptance_trend_probe
output: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_trend_*.md
json: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_trend_*.json
```

## Purpose

The acceptance gate answers "what is pass or blocked now." The trend probe answers "what changed across acceptance snapshots." This is useful during the long A-010 window because it shows whether any baseline item has moved from blocked to pass, from collecting to pass, or regressed.

## Safety Boundary

```text
mode: read-only
system_changes: no
service_changes: no
firewall_changes: no
control_actions: no
model_inference: no
```

Future overnight runner launches include both `baseline_acceptance_probe` and `baseline_acceptance_trend_probe`.

Implementation note: the trend reader deliberately uses `baseline_acceptance_[0-9]*.json` so it does not ingest its own `baseline_acceptance_trend_*.json` outputs.

## Board Validation

Allowlist runner evidence:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_trend_20260529-203510.md
source_count: 2
latest_overall: not_ready
changed_items: none
bad_sources: []
```

OpenClaw agent evidence through `s100p_run_probe`:

```text
tool_id: baseline_acceptance_trend_probe
report: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_trend_20260529-203703.md
source_count: 2
latest_overall: not_ready
changed item summary: none
```
