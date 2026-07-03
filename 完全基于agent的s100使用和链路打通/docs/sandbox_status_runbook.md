# Sandbox Status Runbook

This runbook supports A-006: Docker / sandbox validation.

## Goal

A-006 is verified only when a non-main sandboxed session can run tools without being able to write host-sensitive paths.

The first step is a read-only status probe that records whether the S100P has a usable container runtime:

```text
scripts/probes/sandbox_status_probe.sh
```

## Execution

Through the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh sandbox_status_probe /root/.openclaw/workspace/logs/probes
```

Through the OpenClaw plugin:

```text
s100p_run_probe tool_id=sandbox_status_probe
```

## What It Checks

- `docker`, `podman`, `runc`, `containerd`, and `ctr` commands.
- `docker` and `containerd` service state.
- Installed package versions.
- Kernel namespace entries under `/proc/self/ns`.
- Cgroup support.

The probe is read-only except for writing its report file.

## Acceptance Boundary

This probe alone does not verify A-006. It only answers whether the board is ready for the isolation test.

A-006 requires a follow-up test that:

1. Starts a sandbox/container with only a temporary bind mount.
2. Proves that writes to an approved temporary path work.
3. Proves that host-sensitive paths such as `/root`, `/etc`, and the OpenClaw config directory are not writable from the sandbox.
4. Writes the evidence report under `/root/.openclaw/workspace/logs/probes` or the NAS probe directory.

If no container runtime is installed, A-006 remains blocked on runtime setup.
