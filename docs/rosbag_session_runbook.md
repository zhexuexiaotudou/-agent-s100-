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
