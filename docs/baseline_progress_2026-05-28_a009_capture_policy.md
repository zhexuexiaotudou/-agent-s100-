# Baseline Progress: A-009 Named ROS Bag Capture Policy

Date: 2026-05-28

This note records the read-only A-009 policy step for longer named ROS bag captures. It does not start a long recording and does not send robot commands.

## Verdict

| Item | Status | Evidence |
| --- | --- | --- |
| Policy probe | verified | `rosbag_capture_policy_probe` is allowlisted and runs on S100P. |
| NAS output | verified | Report and JSON policy were written under `/mnt/nas/openclaw/logs/probes`. |
| OpenClaw tool call | verified | `s100p_run_probe` successfully called `tool_id=rosbag_capture_policy_probe` after Gateway restart. |
| Topic classification | verified | Current approved topics detected: `/rosout`, `/parameter_events`; command-like topics detected: `none`. |
| Final named capture | pending | Requires one operator-approved named capture under this policy. |

## Output

```text
/mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.md
/mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.json
/root/.openclaw/workspace/logs/probes/rosbag_capture_policy_20260528-224912.md
```

## Policy Summary

```text
session name regex: ^[a-z0-9][a-z0-9_-]{2,63}$
default duration: 300 seconds
maximum duration: 1800 seconds
approved topics: /rosout /parameter_events /tf /tf_static /joint_states /diagnostics
retention: 14 days or 20 GB
cleanup: report-only until operator approved
robot motion: never sends commands; capture only
```

## Baseline Impact

- A-009 remains `doing`, but the remaining gap is now narrower: one operator-approved named capture under the policy.
- The previous open gap, "longer named capture policy remains", is closed by this report.
- This work does not affect A-006 sandbox status and does not change robot behavior.
