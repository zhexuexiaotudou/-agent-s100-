# Baseline Progress: B-010 Confirmation Template Local Refresh

Date: 2026-05-30

The half-hour audit gate still reports:

```text
decision: continue-non-nas-readonly-only
NAS target: 169.254.110.209 unreachable
S100P SSH: ok
OpenClaw gateway: ok
```

This pass stayed inside the allowed lane. It generated a read-only confirmation
template artifact and did not write runtime approval config, stop services,
change firewall rules, install packages, or touch NAS-backed paths.

## New Gate Artifact

`service_confirmation_template_probe` now writes a machine-readable B-010
template artifact under the report directory:

```text
script: scripts/probes/service_confirmation_template_probe.sh
tool_id: service_confirmation_template_probe
report: /root/.openclaw/workspace/reports/security/service_confirmation_template_20260530-160717.md
json: /root/.openclaw/workspace/reports/security/service_confirmation_template_20260530-160717.json
```

The template is intentionally not written to:

```text
/root/.openclaw/workspace/config/service_convergence_confirmations.json
```

## Current Signals

```text
gateway_loopback: yes
ssh_present: yes
nfs_rpc_present: yes
x11vnc_present: no
vnc_listening: yes
iiod_present: yes
iiod_listening: yes
```

The required confirmations remain default `false`:

```text
gateway_loopback_only
ssh_management_required
nfs_rpc_client_only
x11vnc_unused
iiod_unused_or_firewall
```

## Latest Report Chain

```text
security audit: /root/.openclaw/workspace/logs/probes/security_audit_20260530-160706.md
service decision: /root/.openclaw/workspace/reports/security/service_convergence_decision_20260530-160717.md
confirmation template: /root/.openclaw/workspace/reports/security/service_confirmation_template_20260530-160717.md
execution preflight: /root/.openclaw/workspace/reports/security/service_execution_preflight_20260530-160717.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-160717.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-160718.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-160718.md
```

## Tracking Impact

B-010 remains `blocked_confirmations`, but the missing confirmation step is now
a concrete machine-readable template artifact in the same report chain. The next
step is still review and deliberate filling of the runtime confirmation config;
even a complete config only moves to manual execution review and does not
execute service or firewall changes.
