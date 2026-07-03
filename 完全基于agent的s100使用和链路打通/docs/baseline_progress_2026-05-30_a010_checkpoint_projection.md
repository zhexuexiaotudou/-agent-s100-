# Baseline Progress: A-010 Checkpoint Projection

Date: 2026-05-30

The active audit lane is `continue-non-nas-readonly-only`, and the next-action
queue shows A-010 collection as the only safe continuing baseline action. This
pass added an explicit stability checkpoint so the remaining 7x24 window can be
tracked without manual arithmetic.

## Implementation

`refresh-baseline-local-readonly` now runs:

```text
stability_checkpoint_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/stability 168
```

The checkpoint is read-only. It reads existing stability snapshots and the
latest stability summary, then writes Markdown and JSON with elapsed hours,
remaining hours, ETA, interval statistics, and clean/error counters.

## Latest Evidence

```text
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-173803.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-173819.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-173820.md
manifest entry: stability_checkpoint true sha256=f12c0c8f5c2f1279
```

Checkpoint values:

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

## 2026-05-30 Continuity Update

The checkpoint now evaluates continuous coverage, not only total span from the
first to latest snapshot. The configured maximum allowed gap is 2 hours.

Latest continuity-aware evidence:

```text
checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-174510.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-174526.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-174526.md
manifest entry: stability_checkpoint true sha256=7d842b58b5149165
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

This supersedes the earlier ETA based on total span. A-010 must use the
continuous-window ETA unless the gap threshold or evidence policy is explicitly
changed.

## Tracking Impact

A-010 remains `collecting`, not pass. The queue now has stronger evidence for
why continuing collection is the only safe next action under the current audit
lane. Final A-010 acceptance still requires at least 168 elapsed hours with a
clean trend, and NAS-backed evidence remains blocked until A-003/B-001 recover.
