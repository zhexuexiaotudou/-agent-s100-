# ROS Bag Snapshot Runbook

This runbook supports A-009: ROS bag capture from OpenClaw.

## Goal

Provide a low-risk first capture path before full start/stop background recording exists.

The first implementation is bounded:

- Records only low-risk status topics currently present on the ROS graph.
- Defaults to 5 seconds.
- Rejects output paths outside approved dataset/report directories.
- Writes a Markdown report with bag metadata.

Script:

```text
scripts/probes/rosbag_snapshot_probe.sh
```

## Execution

Through the allowlist runner:

```bash
ROSBAG_SNAPSHOT_SECONDS=3 \
scripts/run_allowlisted_tool.sh \
  rosbag_snapshot_probe \
  /root/.openclaw/workspace/robot_datasets \
  /root/.openclaw/workspace/logs/probes
```

Through the OpenClaw plugin:

```text
s100p_run_probe tool_id=rosbag_snapshot_probe
```

## Topics

The first snapshot records these topics when available:

```text
/rosout
/parameter_events
```

It does not command robot movement or subscribe to high-bandwidth sensor streams.

## Output

Dataset directory:

```text
/root/.openclaw/workspace/robot_datasets/rosbag_snapshot_YYYYmmdd-HHMMSS
```

Report:

```text
/root/.openclaw/workspace/logs/probes/rosbag_snapshot_YYYYmmdd-HHMMSS.md
```

The report includes:

- Bag directory.
- Requested topics.
- Whether `metadata.yaml` exists.
- Dataset card path.
- Record command exit.
- Bag files and sizes.
- `ros2 bag info` output when available.

## Acceptance

Local fallback is verified when:

- `metadata_exists: yes`
- `DATASET_CARD.md` exists beside the bag.
- `verdict: ok`
- `metadata.yaml` exists.
- A `.db3` file exists.
- OpenClaw can trigger the probe through `s100p_run_probe`.

NAS-backed acceptance still requires re-running with:

```text
/mnt/nas/openclaw/robot_datasets
/mnt/nas/openclaw/logs/probes
```

after A-003 is complete.

## Next Step Toward Full A-009

The first start/status/stop self-test is now covered by:

```text
scripts/probes/rosbag_session_probe.sh
```

See:

```text
docs/rosbag_session_runbook.md
```

Full A-009 still needs NAS-backed output and a policy for longer named capture sessions.
