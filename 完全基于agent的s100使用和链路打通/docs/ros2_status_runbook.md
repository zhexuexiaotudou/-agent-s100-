# ROS2 Status Probe Runbook

This runbook covers the first read-only ROS2/TROS status tool for the S100P baseline.

## Scope

`scripts/probes/ros2_status_probe.sh` only reads ROS2 state. It does not start nodes, stop nodes, publish messages, write bags, or modify system configuration.

The probe sources these setup files when present:

```bash
/opt/ros/humble/setup.bash
/opt/tros/humble/setup.bash
```

It writes a Markdown report to `/tmp/openclaw-probes` by default, to `/root/.openclaw/workspace/logs/probes` when triggered from the OpenClaw workspace, or to `/mnt/nas/openclaw/logs/probes` after the NAS workspace is mounted and writable.

## Allowlisted Entry Point

Run the probe through the allowlist wrapper:

```bash
scripts/run_allowlisted_tool.sh ros2_status_probe
scripts/run_allowlisted_tool.sh ros2_status_probe /tmp/openclaw-probe-test
/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh ros2_status_probe /root/.openclaw/workspace/logs/probes
```

Direct arbitrary shell execution is intentionally out of scope for this baseline.

## Report Contents

The report includes:

- ROS2 and TROS install path status.
- `ros2 --help` command availability.
- `ros2 node list`.
- `ros2 topic list`.
- `ros2 service list`.
- Package hints for Hobot/TogetheROS-related packages.
- Package prefix checks for common packages.

All ROS commands are bounded with a timeout where `timeout` is available, so a broken daemon or graph query should not hang the tool indefinitely.

## Acceptance Checks

On the S100P:

```bash
bash -n scripts/run_allowlisted_tool.sh
bash -n scripts/probes/ros2_status_probe.sh
bash scripts/run_allowlisted_tool.sh list
report="$(bash scripts/run_allowlisted_tool.sh ros2_status_probe /tmp/openclaw-probe-test)"
test -f "$report"
grep -q '# ROS2 Status' "$report"
grep -q 'ros2 node list' "$report"
grep -q 'ros2 topic list' "$report"
grep -q 'ros2 service list' "$report"
! bash scripts/run_allowlisted_tool.sh ros2_status_probe /root
```

Success means the allowlisted command can produce a status report and refuses unsafe output directories. It does not yet prove that OpenClaw chat can trigger the tool end to end; that remains part of A-005/A-008 integration.

## 2026-05-27 OpenClaw Agent Validation

The allowlisted scripts were synced to:

```text
/root/.openclaw/workspace/scripts/
```

`/root/.openclaw/workspace/TOOLS.md` contains marker:

```text
OPENCLAW_ALLOWLIST_TOOLS_V1
```

OpenClaw agent command used for validation:

```bash
PATH=/root/.local/lib/node-v24.16.0-linux-arm64/bin:/root/.npm-global/bin:$PATH \
openclaw agent --agent main --timeout 180 --message "Follow TOOLS.md S100P Allowlisted Local Tools. Run only this allowlisted command directly, without wrapping it in bash: /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh ros2_status_probe /root/.openclaw/workspace/logs/probes. Reply with the report path and a short node topic service summary."
```

Agent response reported:

```text
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-031142.md
nodes: none
topics: /parameter_events, /rosout
services: none
```
