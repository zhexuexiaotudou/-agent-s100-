# Baseline Progress: ROS Bag Snapshot

Date: 2026-05-27

## Status

| Item | Status | Evidence |
| --- | --- | --- |
| A-009 bounded local snapshot | verified path | `rosbag_snapshot_probe` recorded `/rosout` and `/parameter_events` into the local workspace. |
| A-009 OpenClaw plugin trigger | verified path | `s100p_run_probe` ran `rosbag_snapshot_probe` and returned `metadata_exists: yes`, `verdict: ok`. |
| A-009 full start/stop capture | pending | The current implementation is a bounded snapshot, not a long-running start/stop recorder. |
| A-009 NAS-backed output | pending | `/mnt/nas/openclaw` is not mounted yet. |

## Runtime Discovery

Board ROS bag capability:

```text
ros2 bag commands: convert, info, list, play, record, reindex
ros-humble-rosbag2 installed
ros-humble-rosbag2-storage-default-plugins installed
```

Current ROS graph:

```text
/parameter_events
/rosout
```

## Probe Added

New bounded capture script:

```text
scripts/probes/rosbag_snapshot_probe.sh
```

Allowlist entry:

```text
scripts/run_allowlisted_tool.sh rosbag_snapshot_probe
```

OpenClaw plugin entry:

```text
s100p_run_probe tool_id=rosbag_snapshot_probe
```

## Implementation Fixes

Two issues were found and fixed during board validation:

1. ROS setup scripts are not compatible with `set -u` when `AMENT_TRACE_SETUP_FILES` is undefined. The probe now temporarily disables nounset while sourcing ROS/TROS setup files.
2. `ros2 bag record -o` requires that the output directory does not already exist. The probe now lets `ros2 bag record` create the bag directory.

The OpenClaw plugin environment also lacked ROS logging defaults, so the probe now sets:

```text
HOME=/root
ROS_LOG_DIR=<report_dir>/<run_id>.ros_logs
```

## Runner Evidence

Runner report:

```text
/root/.openclaw/workspace/logs/probes/rosbag_snapshot_20260527-042845.md
```

Observed facts:

```text
bag_dir: /root/.openclaw/workspace/robot_datasets/rosbag_snapshot_20260527-042845
topics_requested: /rosout /parameter_events
metadata_exists: yes
verdict: ok
metadata.yaml 1769 bytes
rosbag_snapshot_20260527-042845_0.db3 24576 bytes
```

## OpenClaw Plugin Evidence

The OpenClaw agent used the real `s100p_run_probe` tool:

```text
runId: bb64fe15-5e85-43a5-8de4-0d6c2036f8f4
tool_id: rosbag_snapshot_probe
report: /root/.openclaw/workspace/logs/probes/rosbag_snapshot_20260527-043114.md
bag_dir: /root/.openclaw/workspace/robot_datasets/rosbag_snapshot_20260527-043114
topics_requested: /rosout /parameter_events
metadata_exists: yes
verdict: ok
metadata.yaml 1487 bytes
rosbag_snapshot_20260527-043114_0.db3 24576 bytes
```

## Current A-009 Verdict

A-009 has a verified local workspace fallback for bounded ROS bag snapshots.

It is not fully complete because:

- The baseline asks for start/stop capture.
- Output still needs to move to `/mnt/nas/openclaw/robot_datasets` after A-003 completes.

Dataset card generation has since been added and verified separately in:

```text
docs/baseline_progress_2026-05-27_dataset_card.md
```
