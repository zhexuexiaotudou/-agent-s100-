# Baseline Progress: Gap Decision Report

Date: 2026-05-29

This note adds a read-only report that turns the current baseline evidence into
an explicit next-decision table. It is meant to prevent the baseline work from
looking blocked as a whole when only specific items require external inputs.

## New Probe

```text
script: scripts/probes/baseline_gap_decision_probe.sh
tool_id: baseline_gap_decision_probe
mode: read-only
default input: /mnt/nas/openclaw
default output: /mnt/nas/openclaw/reports/baseline-status
```

Safety boundary:

```text
system_changes: no
service_changes: no
firewall_changes: no
control_actions: no
model_downloads: no
secret_printing: no
```

## Board Validation

NAS-backed runner evidence:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_gap_decision_20260529-184105.md
A-010: 74 snapshots, 24.15 elapsed hours, verdict=collecting
overnight runner: running, iterations=5, failed=0
Dream 7B: blocked_no_model
Home Assistant: blocked_no_config
Control policy: policy_ready_no_execution, enabled=0, executed=0
Service convergence: decision pack present
```

OpenClaw agent evidence through `s100p_run_probe`:

```text
report: /root/.openclaw/workspace/reports/baseline-status/baseline_gap_decision_20260529-184923.md
A-010 elapsed hours: 24.15
overnight process status: running
overnight iterations: 5
failed event count: 0
external inputs: B-003 model files; B-008 HA URL/token; B-009 reviewed action allowlist; B-010 service confirmations
```

Latest refreshed roll-up:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260529-184247.md
allowlisted tool count: 26
```

## Baseline Meaning

The automation-safe work is still A-010 collection plus read-only security and
status refreshes. The remaining blockers are now separated into four explicit
external decisions: Dream 7B model files, Home Assistant credentials, reviewed
control actions, and service keep/disable/firewall confirmations.
