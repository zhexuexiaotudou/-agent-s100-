# Baseline Progress: Acceptance Gate

Date: 2026-05-29

This adds a read-only acceptance gate for the two tracked baselines.

## Added

```text
script: scripts/probes/baseline_acceptance_probe.sh
tool_id: baseline_acceptance_probe
output: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_*.md
json: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_*.json
```

## Purpose

The existing status, gap, and teacher briefing reports explain progress. The acceptance gate is stricter: it lists every A/B baseline item and classifies it as `pass`, `collecting`, `blocked_*`, `missing_evidence`, `review`, or `fail`.

This makes the final completion audit concrete:

- A-010 cannot pass until 168h stability evidence exists.
- B-003 cannot pass until Dream 7B/model files and bounded smoke are available, or the scope is explicitly changed.
- B-008 cannot pass without Home Assistant URL/token and a read-only state check.
- B-009 cannot pass while enabled actions are 0 and no reviewed approval audit exists.
- B-010 cannot pass while service convergence confirmations are missing.

## Safety Boundary

```text
mode: read-only
system_changes: no
service_changes: no
firewall_changes: no
control_actions: no
model_inference: no
```

The future overnight runner also includes `baseline_acceptance_probe` per iteration, and the summary helper surfaces `latest_baseline_acceptance`.

## Board Validation

Allowlist runner evidence:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_acceptance_20260529-202537.md
overall: not_ready
pass: 14
not ready: A-006, A-010, B-003, B-008, B-009, B-010
allowlisted_tools: 30
```

OpenClaw agent evidence through `s100p_run_probe`:

```text
tool_id: baseline_acceptance_probe
report: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260529-202642.md
overall: not_ready
A-010: 82 snapshots, 26.16h, collecting
not ready: A-006 blocked_runtime; A-010 collecting; B-003 blocked_external_model; B-008 blocked_external_config; B-009 blocked_review; B-010 blocked_confirmations
```
