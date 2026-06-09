# OpenClaw Entry Demo Runbook

## Purpose

Demonstrate that S100P is the OpenClaw entry host, while the PC is only a normal viewer/operator and NAS provides persistence.

## Scope

In scope:

- S100P `openclaw-gateway` service status.
- S100P listener evidence for port `18789`.
- NAS mount and NAS report persistence under `/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry`.
- A recording workflow that avoids elevated Windows operations.

Out of scope:

- Robot capability.
- ROS2.
- rosbag.
- Dream 7B BPU deployment.
- Public internet exposure of the gateway.

## Command

Run on S100P from the repository checkout:

```bash
scripts/run_allowlisted_tool.sh openclaw_entry_demo_probe
```

Optional explicit report root:

```bash
scripts/run_allowlisted_tool.sh openclaw_entry_demo_probe /mnt/nas/openclaw/reports/teacher-demos/openclaw-entry
```

## Output

The probe prints the generated Markdown report path. The report directory contains:

```text
openclaw_entry_demo.md
openclaw_entry_demo.json
captures/hostname.txt
captures/uname.txt
captures/id.txt
captures/ip_addr.txt
captures/ip_route.txt
captures/nas_findmnt.txt
captures/nas_mount.txt
captures/openclaw_gateway_status.txt
captures/openclaw_gateway_active.txt
captures/port_18789.txt
```

If `scripts/probes/openclaw_status_probe.sh` is present, the demo probe also records its generated report path under:

```text
openclaw_status_probe.report
```

## Recording Steps

1. On the PC, show only the normal browser or chat entry. Do not run elevated Windows tools during the recording.
2. Ask OpenClaw to execute the allowlisted command:

```bash
scripts/run_allowlisted_tool.sh openclaw_entry_demo_probe
```

3. Open the generated `openclaw_entry_demo.md`.
4. Show that the report is stored under `/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry` when NAS is mounted.
5. Show `openclaw_gateway_status`, `openclaw_gateway_active`, `port_18789`, and NAS mount capture entries in the report.

## Acceptance

- `openclaw_entry_demo.json` contains `verdict: ok_openclaw_entry_demo_probe`.
- `openclaw_entry_demo.json` contains `claims.openclaw_runs_on_s100p: validated_by_openclaw_gateway_status_and_port_capture`.
- `openclaw_entry_demo.json` contains `claims.pc_high_privilege_required: not_required_by_demo_procedure`.
- `openclaw_entry_demo.json` contains `claims.pc_unsafe_writes: not_required_by_demo_procedure`.
- `openclaw_entry_demo.json` contains `claims.persistence: nas_report_root_when_/mnt/nas/openclaw_is_mounted_and_writable`.

## Safety Boundary

- No service changes.
- No firewall changes.
- No package installs.
- No model inference.
- No PC file writes are required by the demo.
- NAS writes are bounded to report files under the approved report root.
