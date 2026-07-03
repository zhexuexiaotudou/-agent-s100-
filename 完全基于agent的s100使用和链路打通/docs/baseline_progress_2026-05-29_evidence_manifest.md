# Baseline Progress: Evidence Manifest

Date: 2026-05-29

This adds a read-only evidence manifest for the two baseline tracks.

## Added

```text
script: scripts/probes/baseline_evidence_manifest_probe.sh
tool_id: baseline_evidence_manifest_probe
output: /mnt/nas/openclaw/reports/baseline-status/baseline_evidence_manifest_*.md
json: /mnt/nas/openclaw/reports/baseline-status/baseline_evidence_manifest_*.json
```

## Purpose

The acceptance gate references many NAS-backed reports. The manifest makes those references auditable by recording each current evidence file's path, size, mtime, and SHA256 hash.

This gives later reviews a stable proof bundle without copying private logs into the repository.

## Safety Boundary

```text
mode: read-only
system_changes: no
service_changes: no
firewall_changes: no
control_actions: no
model_inference: no
```

Future overnight runner launches include `baseline_evidence_manifest_probe` per iteration, and the summary helper surfaces `latest_baseline_evidence_manifest`.

## Board Validation

Allowlist runner evidence:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_evidence_manifest_20260529-204913.md
entry_count: 35
hashed_file_count: 35
missing_count: 0
```

OpenClaw agent evidence through `s100p_run_probe`:

```text
tool_id: baseline_evidence_manifest_probe
report: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260529-205038.md
entry_count: 36
hashed_file_count: 36
missing_count: 0
```
