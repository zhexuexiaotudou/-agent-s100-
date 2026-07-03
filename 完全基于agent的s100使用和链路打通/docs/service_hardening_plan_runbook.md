# Service Hardening Plan Runbook

This runbook supports B-010: service exposure and security audit.

## Goal

Turn the existing read-only security audit into an operator-reviewed hardening
plan without changing the board.

The probe generates:

- Current service exposure decisions.
- Dry-run disable commands for NFS/RPC, x11vnc, and iiod when present.
- Firewall-only alternatives.
- Post-change verification commands.
- Evidence from listening sockets, running services, and RPC map.

The probe never runs `systemctl disable`, `systemctl mask`, `ufw`, or any other
mutation command.

## Entry Point

Use the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh service_hardening_plan_probe [output_dir]
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
{"tool_id":"service_hardening_plan_probe"}
```

## Acceptance

Local readiness is verified when:

- The runner writes `service_hardening_plan_*.md`.
- The OpenClaw agent can call `s100p_run_probe` with `tool_id=service_hardening_plan_probe`.
- The report includes a dry-run disable plan and post-change verification commands.

B-010 is still not complete until an operator confirms which services to keep,
disable, or firewall, and the post-change security audit is clean.

## Service Convergence Decision Pack

Use this read-only follow-up when the security audit, service policy, and
hardening dry-run already exist and the operator needs one consolidated review
document:

```bash
scripts/run_allowlisted_tool.sh service_convergence_decision_probe \
  /mnt/nas/openclaw/logs/probes \
  /mnt/nas/openclaw/reports/security
```

The pack records the current listener/service signals, recommended
keep/disable/firewall decisions, candidate commands, rollback commands, and
post-change verification commands. It does not execute any of those commands.

Current 2026-05-28 recommendations:

```text
OpenClaw Gateway: keep-loopback
SSH: keep-trusted-management
NFS/RPC server stack: disable-if-client-only
x11vnc: disable-if-unused
iiod: keep-or-firewall
```
