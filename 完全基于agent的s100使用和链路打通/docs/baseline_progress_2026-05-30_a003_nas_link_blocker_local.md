# Baseline Progress: A-003 NAS Link Blocker Local Refresh

Date: 2026-05-30

The active audit lane is `continue-non-nas-readonly-only`, so this pass only
added targeted read-only NAS link evidence. It did not log in to the NAS, mount
or unmount anything, scan the network, or use credentials.

## Implementation

```text
script: scripts/probes/nas_link_blocker_probe.sh
allowlist id: nas_link_blocker_probe
windows action: refresh-baseline-local-readonly
target: 169.254.110.209
output: /root/.openclaw/workspace/logs/probes
```

The probe records route, interface, mount fstype, one ping, and neighbor state.
It is scoped to private/link-local target addresses.

## Latest Evidence

```text
nas link blocker: /root/.openclaw/workspace/logs/probes/nas_link_blocker_20260530-164450.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-164504.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-164505.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-164505.md
manifest entry: nas_link_blocker true sha256=5d6b616e5e2d2cf5
```

Key result:

```text
verdict: blocked_l2_no_neighbor
route: 169.254.110.209 dev eth0 src 169.254.8.10
interface: eth0 UP 169.254.8.10/16
mount: autofs_not_reached, fstype=autofs
ping: 1 transmitted, 0 received
neighbor before ping: FAILED
neighbor after ping: INCOMPLETE
```

## Tracking Impact

A-003 and B-001 remain failed, but the blocker is now more precise and
machine-recorded in the baseline evidence chain. Credentials or NAS login cannot
repair this state until the physical/link-layer path responds and the target is
reachable from S100P.
