# Baseline Progress: A-006 Sandbox Gate Refresh

Date: 2026-05-30

The half-hour audit gate still reports:

```text
decision: continue-non-nas-readonly-only
NAS target: 169.254.110.209 unreachable
S100P SSH: ok
OpenClaw gateway: ok
```

Because the current lane is read-only, no Docker, Podman, runc, containerd,
service, or firewall package was installed or changed in this pass.

## Gate Change

`baseline_acceptance_probe` no longer hard-codes A-006 as blocked. It now reads
the latest sandbox status report and derives A-006 from:

```text
runtime_available
runtime_choice
isolation_verdict
```

`sandbox_isolation_smoke_probe` is now allowlisted as the final A-006 smoke
gate. It does not install packages or pull images. If a runtime and local image
exist, it runs with network disabled, a read-only container filesystem, a
temporary tmpfs, and exactly one writable temporary host mount.

This keeps the acceptance gate maintainable: if a sandbox runtime is later
installed and a bounded isolation smoke passes, the gate can move without
rewriting the acceptance probe.

## Latest Evidence

```text
sandbox status: /root/.openclaw/workspace/logs/probes/sandbox_status_20260530-155716.md
sandbox smoke: /root/.openclaw/workspace/logs/probes/sandbox_isolation_smoke_20260530-155717.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-155717.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-155717.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-155717.md
```

Sandbox status summary:

```text
docker: missing
podman: missing
runc: missing
containerd: missing
architecture: arm64
root filesystem free: 29G
/var free: 29G
docker.io candidate: 29.1.3-0ubuntu3~22.04.2
podman candidate: 3.4.4+ds1-1ubuntu1.22.04.3
containerd candidate: 2.2.1-0ubuntu1~22.04.1
runc candidate: 1.3.4-0ubuntu1~22.04.1
sunrise subuid/subgid: present
runtime_available: no
runtime_choice: missing
isolation_verdict: blocked
smoke verdict: blocked_runtime_missing
```

## Tracking Impact

A-006 is still `blocked_runtime`, but the blocker is now evidence-backed by a
fresh local fallback report and package candidates. The next non-read-only step,
when the audit lane allows it, is to install one runtime package, then run a
bounded isolation smoke that proves only approved temporary mounts are writable.
