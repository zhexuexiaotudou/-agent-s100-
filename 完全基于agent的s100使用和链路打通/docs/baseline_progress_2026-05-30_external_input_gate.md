# Baseline Progress: External Input Gate

Date: 2026-05-30

Added a read-only external input gate for baseline items that are blocked by
missing model/config material rather than by unclear implementation state.

## Implementation

```text
probe: scripts/probes/external_input_gate_probe.sh
allowlist id: external_input_gate_probe
refresh path: scripts/windows/s100p-task.ps1 -Action refresh-baseline-local-readonly
output: /root/.openclaw/workspace/reports/external-inputs/external_input_gate_*.md
```

The probe reviews existing artifacts for:

```text
B-003: Dream 7B readiness, config template, and bounded smoke gate
B-008: Home Assistant env template and read-only status gate
```

Boundary:

```text
does not write Home Assistant credentials
does not download, copy, or install model files
does not write Dream 7B runtime config
does not call Home Assistant service/control endpoints
does not run model inference
```

## Latest Evidence

```text
external input gate: /root/.openclaw/workspace/reports/external-inputs/external_input_gate_20260530-201112.md
overall: external_input_packets_ready
ready_count: 2
blocked_count: 0
B-003: waiting_for_model_files_and_runtime_config
B-008: waiting_for_home_assistant_env
safe-progress report: logs/baseline-audit/baseline_safe_progress_20260530-201119.md
latest acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-201113.md
latest next action queue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-201113.md
latest evidence manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-201113.md
manifest external gate sha256: 57ff61ed73e430fcb942d30d567a35debc59439f060b808d7d0656931463f0b6
manifest missing_count: 0
completionProven: false
completionNotReadyCount: 9
```

## Tracking Impact

B-003 and B-008 now have machine-readable external-input packets. The queue can
distinguish "waiting for a concrete external input" from "the audit has not
prepared the required material yet", while still keeping credentials and model
files outside automation.
