# Baseline Progress: ROS2 Status Probe

Date: 2026-05-27

## Status

| Item | Status | Evidence |
| --- | --- | --- |
| A-008 ROS2 status tool | verified | `ros2_status_probe` is implemented, allowlisted, synced into the OpenClaw workspace, and successfully triggered through `openclaw agent --agent main`. |
| A-005 tool allowlist | doing | The allowlist runner lists `ros2_status_probe` and rejects unsafe output path `/root`. |
| OpenClaw workspace command path | verified | The allowlist scripts were synced to `/root/.openclaw/workspace/scripts/`, and `TOOLS.md` contains the `OPENCLAW_ALLOWLIST_TOOLS_V1` instructions block. The agent wrote `/root/.openclaw/workspace/logs/probes/ros2_status_20260527-031142.md`. |

## Verified On Board

Smoke test output:

```text
MANIFEST_ROS2_OK
REPORT=/tmp/openclaw-ros2-test/out2/ros2_status_20260527-030034.md
ROS2_STATUS_CLEAN_OK
```

The generated report confirms:

- `/opt/ros/humble` exists.
- `/opt/tros/humble` exists.
- `ros2` resolves to `/opt/ros/humble/bin/ros2`.
- `ros2 topic list` currently returns `/parameter_events` and `/rosout`.
- `ros2 node list` currently returns no nodes.
- `ros2 service list` currently returns no services.
- Package hints include `ai_msgs`, `dnn_node`, `dnn_node_example`, `hobot_codec`, `hobot_cv`, `hobot_image_publisher`, `hobot_usb_cam`, `img_msgs`, `mipi_cam`, and `websocket`.
- The report did not contain plain-text Tavily keys, API keys, tokens, secrets, or passwords.

## Remaining Work

OpenClaw agent trigger evidence:

```text
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-031142.md
nodes: none
topics: /parameter_events, /rosout
services: none
```

A-005 remains `doing` because `TOOLS.md` gives the agent the approved command path, but the platform still exposes broader local command execution in the `openclaw agent --agent main` path. On 2026-05-27, after applying gateway approvals and `tools.exec.security=allowlist`, a non-allowlisted `/usr/bin/touch /tmp/openclaw_policy_nonallowlisted_0325` command still created the marker file. Full verification requires either platform-level command restriction that actually blocks non-allowlisted commands or a narrower OpenClaw tool/plugin surface.
