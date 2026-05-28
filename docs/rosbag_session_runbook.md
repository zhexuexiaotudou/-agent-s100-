# ROS Bag Session Runbook

This runbook supports A-009: ROS bag start/stop capture from OpenClaw.

## Goal

Verify the mechanics of a start/status/stop recording session without exposing arbitrary ROS topics or unbounded background tasks to the agent.

The first implementation is a self-test:

- Starts a `ros2 bag record` process.
- Records only low-risk status topics.
- Checks that the process is running.
- Stops it with `SIGINT`.
- Writes a bag, state file, dataset card, and report.

## Entry Point

Use the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh rosbag_session_probe [dataset_dir] [report_dir]
scripts/run_allowlisted_tool.sh rosbag_capture_policy_probe [output_dir]
scripts/run_allowlisted_tool.sh rosbag_named_capture_probe [dataset_dir] [report_dir]
```

OpenClaw plugin:

```json
{"tool_id":"rosbag_session_probe"}
```

## Topics

The self-test records these topics when available:

```text
/rosout
/parameter_events
```

It does not command robot movement.

## Named Capture Policy

Before running longer named captures, generate the read-only policy report:

```bash
scripts/run_allowlisted_tool.sh rosbag_capture_policy_probe /mnt/nas/openclaw/logs/probes
```

The policy report defines:

- session name regex: `^[a-z0-9][a-z0-9_-]{2,63}$`
- default duration: 300 seconds
- maximum duration: 1800 seconds
- approved topics: `/rosout`, `/parameter_events`, `/tf`, `/tf_static`, `/joint_states`, `/diagnostics`
- retention: 14 days or 20 GB, report-only cleanup until approved
- safety boundary: capture only, never robot motion

## Output

Dataset directory:

```text
/root/.openclaw/workspace/robot_datasets/rosbag_session_YYYYmmdd-HHMMSS
```

Report:

```text
/root/.openclaw/workspace/logs/probes/rosbag_session_YYYYmmdd-HHMMSS.md
```

State files:

```text
/root/.openclaw/workspace/logs/probes/rosbag_sessions/
```

## Acceptance

Local fallback is verified when:

- `start_status: started`
- `status_after_start: running`
- `stop_status: sent_sigint`
- `record_exit: 0`
- `metadata_exists: yes`
- `verdict: ok`
- `DATASET_CARD.md`, `metadata.yaml`, and `.db3` exist.
- OpenClaw can trigger the probe through `s100p_run_probe`.

NAS-backed acceptance still requires re-running under:

```text
/mnt/nas/openclaw/robot_datasets
/mnt/nas/openclaw/logs/probes
```

after A-003 is complete.

The current NAS-backed policy evidence is:

```text
/mnt/nas/openclaw/logs/probes/rosbag_capture_policy_20260528-224523.md
```

It detected `/rosout` and `/parameter_events` as approved topics and found no command-like topics to exclude.

## Operator-Approved Named Capture

After the policy exists, run exactly one approved named capture from the runner:

```bash
ROSBAG_NAMED_CAPTURE_SECONDS=300 \
scripts/run_allowlisted_tool.sh rosbag_named_capture_probe \
  /mnt/nas/openclaw/robot_datasets \
  /mnt/nas/openclaw/logs/probes
```

Current evidence:

```text
report: /mnt/nas/openclaw/logs/probes/rosbag_named_capture_20260528-231319.md
session_id: approved_named_capture_20260528-231319
bag_dir: /mnt/nas/openclaw/robot_datasets/approved_named_capture_20260528-231319
duration_seconds: 300
topics_requested: /rosout /parameter_events
record_exit: 0
metadata_exists: yes
dataset_card: /mnt/nas/openclaw/robot_datasets/approved_named_capture_20260528-231319/DATASET_CARD.md
verdict: ok
```

This verifies the A-009 baseline capture mechanics. Future real experiment
captures still need reviewed topic selection and retention cleanup approval.
