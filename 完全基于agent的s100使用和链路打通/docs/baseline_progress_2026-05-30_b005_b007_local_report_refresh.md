# Baseline Progress: B-005/B-007 Local Report Refresh

Date: 2026-05-30

The active audit lane is `continue-non-nas-readonly-only`, so this pass only
refreshed local fallback log diagnosis and experiment report artifacts. It did
not depend on NAS, change services, or call external models.

## Implementation

`refresh-baseline-local-readonly` now runs:

```text
log_diagnose /root/.openclaw/workspace/logs /root/.openclaw/workspace/logs/probes
experiment_report_probe /root/.openclaw/workspace/reports/experiments
```

Both run before `baseline_status_probe`, `baseline_acceptance_probe`, and
`baseline_evidence_manifest_probe`, so B-005/B-007 point at same-round evidence.

## Latest Evidence

```text
log diagnosis: /root/.openclaw/workspace/logs/probes/log_diagnosis_20260530-170419.md
experiment report: /root/.openclaw/workspace/reports/experiments/experiment_report_20260530-170419.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-170420.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-170420.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-170420.md
manifest entries: log_diagnosis true sha256=89dd45b7ea77b089; experiment_report true sha256=a0ecfec1576075df
```

The log diagnosis found 12 local matches in historical probe logs, mostly
known ROS bag smoke-test errors and the sample error log. The experiment report
summarized the current local fallback artifact set:

```text
probe reports: 240
browser smoke screenshots: 3
document indexes: 11
document daily summaries: 9
ROS bag datasets: 7
dataset cards: 4
nas_backed_mode: fallback
```

## Tracking Impact

B-005 and B-007 remain local fallback evidence while NAS is down, but they no
longer rely on stale 2026-05-27 reports. Final NAS-backed reporting still needs
the NAS link restored and the same reports regenerated under `/mnt/nas/openclaw`.
