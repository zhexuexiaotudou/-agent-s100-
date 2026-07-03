# Baseline Progress: A-009 Named Capture Request Local Refresh

Date: 2026-05-30

The active audit lane is `continue-non-nas-readonly-only`, so this pass only
generated a ROS bag named-capture request template. It did not start recording,
create a dataset directory, delete existing bags, or send robot commands.

## Implementation

```text
script: scripts/probes/rosbag_named_capture_request_probe.sh
allowlist id: rosbag_named_capture_request_probe
windows action: refresh-baseline-local-readonly
output: /root/.openclaw/workspace/reports/rosbag
```

The request template captures:

```text
session_name: replace_with_reviewed_session_name
duration_seconds: 300
topics: /rosout, /parameter_events
dataset_root: /root/.openclaw/workspace/robot_datasets
requires_operator_approval: true
```

## Latest Evidence

```text
request template: /root/.openclaw/workspace/reports/rosbag/rosbag_named_capture_request_20260530-165826.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-165839.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-165839.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-165839.md
manifest entry: rosbag_capture_request true sha256=fac1165b95bbf5a7
```

Current topic signals:

```text
approved topics detected: /rosout /parameter_events
command-like topics excluded: none_detected
latest policy: /root/.openclaw/workspace/logs/probes/rosbag_capture_policy_20260528-224912.md
latest session: /root/.openclaw/workspace/logs/probes/rosbag_session_20260527-052005.md
```

## Tracking Impact

A-009 is now stricter in the acceptance gate: it is `review`, not `pass`, until
one real approved named capture exists. This keeps the baseline from confusing
policy/template readiness with final capture verification.
