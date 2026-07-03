# Security Audit Runbook

This runbook supports B-010: security audit checklist for the OpenClaw + S100P + NAS baseline.

## Goal

Run a repeatable, read-only audit that checks the first security boundary before treating the baseline as stable:

- OpenClaw config validity.
- Gateway listener exposure.
- Tavily plugin loaded state.
- S100P allowlisted plugin loaded state.
- Non-loopback listeners that need review.
- NAS workspace mount state.
- Workspace secret-like metadata without printing secret values.

## Entry Point

Use the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh security_audit_probe [output_dir]
scripts/run_allowlisted_tool.sh service_policy_probe [output_dir]
scripts/run_allowlisted_tool.sh service_hardening_plan_probe [output_dir]
```

Default local fallback output:

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
{"tool_id":"security_audit_probe"}
{"tool_id":"service_policy_probe"}
{"tool_id":"service_hardening_plan_probe"}
```

The plugin does not accept arbitrary commands or script paths.

## Secret Handling

The probe intentionally does not print secret values. It only reports whether secret-like metadata appears in scanned workspace files and prints path plus line number for review.

## Acceptance

Local fallback is verified when:

- The runner writes `security_audit_*.md` under `/root/.openclaw/workspace/logs/probes`.
- The OpenClaw agent can call `s100p_run_probe` with `tool_id=security_audit_probe`.
- The report shows Gateway exposure as loopback-only.
- The report confirms Tavily and `s100p-allowlisted-tools` are loaded.
- Any non-loopback listeners are listed for review.
- Non-loopback listeners are classified into `admin`, `nfs-rpc`, `remote-desktop`, `hardware-daemon`, `fail`, or `review`.
- Secret-like scan does not print raw secrets.

NAS-backed acceptance still requires the same report under:

```text
/mnt/nas/openclaw/logs/probes
```

## Listener Review Policy

The first baseline does not blindly close board services from an audit script. It classifies them so the final service policy can be reviewed without breaking RDK Studio access.

| Category | Meaning | Default action |
| --- | --- | --- |
| `admin` | SSH or equivalent management listener | Keep only on trusted LAN/Tailscale; prefer key auth. |
| `nfs-rpc` | NFS, rpcbind, mountd, statd, or kernel RPC listener | Disable if S100P is not serving NFS; otherwise firewall to trusted LAN only. |
| `remote-desktop` | VNC or desktop remoting | Disable unless RDK Studio desktop access is required. |
| `hardware-daemon` | Hardware access daemon such as `iiod` | Keep only if the corresponding hardware tooling is needed. |
| `fail` | OpenClaw Gateway or another forbidden listener exposed on non-loopback | Fix before treating B-010 as verified. |
| `review` | Unclassified listener | Investigate and classify before final acceptance. |

## Service Policy Plan

`service_policy_probe` is read-only. It does not stop, disable, or firewall services. It turns the listener review into a policy matrix with manual commands.

Current baseline policy:

| Component | Default decision |
| --- | --- |
| OpenClaw Gateway | Keep loopback-only. |
| SSH | Keep for management on trusted LAN/Tailscale; move toward key auth. |
| NFS/RPC server stack | Disable if S100P is only an NAS client and TS-264C is the NAS. |
| x11vnc | Disable if RDK Studio terminal/file access is enough. |
| iiod | Keep only if IIO hardware tooling is needed; otherwise disable or firewall. |

Commands emitted by the report are intentionally manual. Do not run them until the service role is confirmed.

## Service Hardening Dry-Run

`service_hardening_plan_probe` turns the policy matrix into a reviewable command
plan. It is still read-only:

- It does not stop services.
- It does not disable or mask units.
- It does not change firewall rules.

Use it before making service decisions:

```bash
scripts/run_allowlisted_tool.sh service_hardening_plan_probe /root/.openclaw/workspace/logs/probes
```
