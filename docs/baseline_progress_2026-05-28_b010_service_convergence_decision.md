# Baseline Progress: B-010 Service Convergence Decision Pack

Date: 2026-05-28

This note records the B-010 follow-up after the NAS-backed security audit,
service policy report, and hardening dry-run. The new decision pack is still
read-only: it does not stop services, edit firewall rules, or delete anything.

## New Probe

```text
script: scripts/probes/service_convergence_decision_probe.sh
tool_id: service_convergence_decision_probe
mode: read-only
default input: /mnt/nas/openclaw/logs/probes
default output: /mnt/nas/openclaw/reports/security
```

The probe consolidates:

- latest security audit;
- latest service policy report;
- latest service hardening dry-run;
- current listener snapshot;
- current running service snapshot;
- recommended keep/disable/firewall decision;
- candidate execution commands;
- rollback commands;
- post-change verification commands.

## NAS Runner Evidence

```text
report: /mnt/nas/openclaw/reports/security/service_convergence_decision_20260528-235327.md
Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
mode: read-only decision pack
```

Current signal highlights:

```text
OpenClaw Gateway loopback: yes
SSH service present: yes
NFS/RPC server stack present: yes
VNC port/listener present: yes
iiod service present: yes
iiod port/listener present: yes
```

## OpenClaw Tool Evidence

The actual OpenClaw extension path was:

```text
/root/.openclaw/extensions/s100p-allowlisted-tools/index.js
```

After updating that extension copy and restarting `openclaw-gateway.service`,
the agent could call the new tool:

```text
tool_id: service_convergence_decision_probe
report: /root/.openclaw/workspace/reports/security/service_convergence_decision_20260528-234753.md
Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```

## Tracking Impact

B-010 remains `doing`.

What is now verified:

- security audit exists;
- service policy exists;
- hardening plan exists;
- service convergence decision pack exists on NAS;
- the OpenClaw allowlisted tool path can generate the same decision pack.

Remaining gap:

- the operator must confirm whether S100P is NFS-client-only, whether x11vnc is
  unused, and whether iiod is required by D-Robotics/IIO tooling;
- only after those confirmations should disable/firewall commands be executed;
- after any execution, rerun security audit and baseline status.
