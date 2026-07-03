# Baseline Progress: A-010 Automatic Audit Refresh

Date: 2026-05-30

The active audit lane is `continue-non-nas-readonly-only`. The next-action
queue shows A-010 collection as the only safe continuing action, so the
half-hour audit loop now performs an automatic narrow A-010 read-only refresh
after each successful audit.

## Implementation

Added a scoped S100P action:

```text
refresh-a010-local-readonly
```

It only runs:

```text
stability_snapshot_probe
stability_summary_probe
stability_checkpoint_probe
baseline_status_probe
baseline_acceptance_probe
baseline_acceptance_trend_probe
baseline_next_action_queue_probe
baseline_evidence_manifest_probe
```

It does not run browser smoke, document indexing, control templates, service
templates, Home Assistant probes, model probes, NAS mount work, or credential
writes.

`baseline-audit.ps1` now accepts:

```powershell
-RefreshA010ReadOnly
```

When the decision is `continue-non-nas-readonly-only`,
`continue-nas-backed-baseline`, or `continue`, this switch triggers the scoped
A-010 refresh and records the command result in the audit report.

## Latest Evidence

```text
background loop pid: 133404
background loop command: powershell.exe ... baseline-audit.ps1 -Iterations 0 -IntervalMinutes 30 -RemoteTimeoutSeconds 45 -RefreshA010ReadOnly
audit report: logs/baseline-audit/baseline_audit_20260530-175041.md
audit command result: s100p-refresh-a010-local-readonly exit=0
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-175057.md
```

Latest checkpoint:

```text
snapshot_count: 93
elapsed_hours: 84.64
continuous_start: 2026-05-30T16:48:29+08:00
continuous_elapsed_hours: 1.04
continuous_remaining_hours: 166.96
continuous_eta: 2026-06-06T16:48:29+08:00
checkpoint_status: collecting
```

## Tracking Impact

A-010 can now continue collecting without manual refresh commands while the
audit loop is running. The audit still preserves the current route decision and
continues to hold NAS-backed, control, runtime, model, and Home Assistant work
behind their prerequisites.

## 2026-05-30 Structured Metric Update

The audit loop now reads the latest A-010 checkpoint JSON after each automatic
refresh and writes the main values directly into the audit report.

Latest evidence:

```text
background loop pid: 145804
background loop command: powershell.exe ... baseline-audit.ps1 -Iterations 0 -IntervalMinutes 30 -RemoteTimeoutSeconds 45 -RefreshA010ReadOnly
audit report: logs/baseline-audit/baseline_audit_20260530-175806.md
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-175822.md
checkpointStatus: collecting
snapshotCount: 97
continuousElapsedHours: 1.16
continuousRemainingHours: 166.84
continuousEta: 2026-06-06T16:48:29+08:00
snapshotsWithGatewayErrors: 0
snapshotsWithOomErrors: 0
```

This removes the need to open the S100P checkpoint report for routine audit
review; the audit Markdown and JSON carry the key continuity metrics.
