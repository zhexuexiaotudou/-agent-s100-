# Baseline Progress: A-006 and B-010 Dry-Run Refresh

Date: 2026-05-28

This note records the post-approval refresh for the sandbox and service-security
items. No runtime was installed, and no service or firewall setting was changed.

## A-006 Sandbox Status

```text
report: /mnt/nas/openclaw/logs/probes/sandbox_status_20260528-232100.md
runtime_available: no
isolation_verdict: blocked
reason: Docker/Podman/runc are not installed or not available.
```

Tracking status: A-006 remains `blocked` unless the project chooses to install
Docker/Podman/runc, or explicitly drops sandbox isolation from the first
baseline.

## B-010 Security Audit

```text
report: /mnt/nas/openclaw/logs/probes/security_audit_20260528-232101.md
OpenClaw config validation: pass
Gateway exposure: pass, loopback only
NAS workspace mount: pass, mounted
Workspace secret scan: warn, redacted metadata hit
Non-loopback listeners: warn, 19
```

## B-010 Service Policy and Hardening Plan

```text
service_policy: /mnt/nas/openclaw/logs/probes/service_policy_20260528-232101.md
hardening_plan: /mnt/nas/openclaw/logs/probes/service_hardening_plan_20260528-232101.md
OpenClaw Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC server stack: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

The hardening plan remains dry-run only. It prints candidate `systemctl`
commands for review but does not execute them.

## Latest Roll-Up

```text
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-232125.md
```

Tracking status:

- A-006 remains blocked by missing sandbox runtime.
- B-010 remains doing because service keep/disable/firewall decisions are still
  intentionally pending.
