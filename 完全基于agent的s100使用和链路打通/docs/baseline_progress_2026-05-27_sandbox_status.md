# Baseline Progress: Sandbox Status

Date: 2026-05-27

## Status

| Item | Status | Evidence |
| --- | --- | --- |
| A-006 read-only sandbox probe | verified path | `sandbox_status_probe` runs through the allowlist runner and OpenClaw plugin. |
| A-006 isolation test | blocked | The S100P currently has no Docker, Podman, or runc runtime available. |

## Runtime Preflight

Board check before adding the probe:

```text
docker=missing
podman=missing
runc=missing
docker_service=inactive
containerd_service=inactive
```

Kernel namespace entries exist:

```text
cgroup ipc mnt net pid pid_for_children time time_for_children user uts
```

This means the kernel has namespace support, but the user-space container runtime needed for A-006 is absent.

## Probe Added

New read-only probe:

```text
scripts/probes/sandbox_status_probe.sh
```

New allowlist runner entry:

```text
scripts/run_allowlisted_tool.sh sandbox_status_probe /root/.openclaw/workspace/logs/probes
```

OpenClaw plugin entry:

```text
s100p_run_probe tool_id=sandbox_status_probe
```

The probe checks Docker, Podman, runc, containerd, service state, package state, namespace entries, and cgroup support. It does not modify sandbox configuration.

## Board Runner Evidence

Direct allowlist runner output:

```text
REPORT=/root/.openclaw/workspace/logs/probes/sandbox_status_20260527-040658.md
| docker | missing |
| podman | missing |
| runc | missing |
| docker | inactive
- runtime_available: no
- isolation_verdict: blocked
```

## OpenClaw Plugin Evidence

The OpenClaw agent used the real `s100p_run_probe` tool:

```text
runId: 4dc92c37-5c14-4095-8ca9-69bb93f5e4c8
tool: s100p_run_probe
tool_id: sandbox_status_probe
report: /root/.openclaw/workspace/logs/probes/sandbox_status_20260527-040824.md
runtime_available: no
isolation_verdict: blocked
```

Plugin schema includes:

```text
sandbox_status_probe
```

## Current A-006 Verdict

A-006 is not verified. The status probe is verified, but the isolation test cannot run until a container runtime is installed and explicitly accepted as part of the baseline.

Next implementation choice:

- Install and configure a runtime such as Docker or Podman, then run a temporary bind-mount isolation test.
- Or drop A-006 from the first baseline if S100P should avoid container runtime overhead.
