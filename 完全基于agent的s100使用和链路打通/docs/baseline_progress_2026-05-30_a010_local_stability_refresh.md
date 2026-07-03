# Baseline Progress: A-010 Local Stability Refresh

Date: 2026-05-30

The active audit lane is `continue-non-nas-readonly-only`, so this pass only
refreshed local fallback A-010 stability evidence. It did not depend on NAS and
did not treat local evidence as NAS-backed acceptance.

## Implementation

`refresh-baseline-local-readonly` now runs:

```text
stability_snapshot_probe /root/.openclaw/workspace/logs/probes
stability_summary_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/stability
```

`stability_snapshot_probe` was corrected to classify `/mnt/nas/openclaw` by
fstype. When the mount point is only `autofs`, it records
`autofs_not_reached` and skips `df /mnt/nas/openclaw` to avoid triggering the
current NAS hang path.

## Latest Evidence

```text
snapshot: /root/.openclaw/workspace/logs/probes/stability_snapshot_20260530-164956.md
summary: /root/.openclaw/workspace/reports/stability/stability_summary_20260530-165005.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-165019.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-165019.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-165019.md
manifest entry: stability_summary true sha256=74ab0bf0bf1bdeac
```

Latest summary:

```text
snapshot count: 82
first snapshot: 2026-05-27T05:12:36+08:00
last snapshot: 2026-05-30T16:49:56+08:00
elapsed hours: 83.62
max kernel OOM matches in last 24h: 0
max Gateway error-like matches in last 24h: 0
verdict: collecting
latest NAS workspace: autofs_not_reached
latest NAS fstype: autofs
```

## Tracking Impact

A-010 remains `collecting`; it is not a 7x24 pass until elapsed hours reaches
168 and the trend stays clean. This change prevents local A-010 evidence from
stalling while NAS-backed collection is held by the current L2/IP NAS blocker.
