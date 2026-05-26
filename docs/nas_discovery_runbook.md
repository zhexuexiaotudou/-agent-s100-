# NAS Discovery Runbook

This runbook supports A-003: mount the TS-264C OpenClaw workspace on S100P.

## Goal

Before credentials are available, collect read-only evidence about whether the
board is ready to mount a NAS share:

- Current `/mnt/nas/openclaw` state.
- Network interfaces and routes.
- Passive neighbor table.
- SMB/NFS tooling availability.
- Passive mDNS service hints when `avahi-browse` is installed.

The probe does not scan a subnet, does not log in to a NAS, and does not mount
anything.

## Entry Point

Use the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh nas_discovery_probe [output_dir]
```

Default local fallback:

```text
/root/.openclaw/workspace/logs/probes
```

NAS-backed output after A-003 is complete:

```text
/mnt/nas/openclaw/logs/probes
```

## OpenClaw Tool

The narrow OpenClaw plugin exposes the same workflow through:

```text
s100p_run_probe
```

with:

```json
{"tool_id":"nas_discovery_probe"}
```

## Output

The probe writes:

```text
nas_discovery_*.md
```

## Acceptance

Local readiness is verified when:

- The runner writes a report under `/root/.openclaw/workspace/logs/probes`.
- The OpenClaw agent can call `s100p_run_probe` with `tool_id=nas_discovery_probe`.
- The report includes mount state, routes, neighbors, and SMB/NFS dependency state.

A-003 is still blocked until the actual TS-264C host/share/account information
is available and the mount is validated across reboot.
