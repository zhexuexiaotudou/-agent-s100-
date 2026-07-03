# Baseline Status Runbook

This runbook supports progress tracking across the two OpenClaw + NAS baseline
tracks.

## Goal

Generate a single read-only Markdown report that answers:

- Which probes and reports currently exist.
- Whether OpenClaw Gateway is up.
- Whether the A-010 stability timer is active.
- Whether `/mnt/nas/openclaw` is mounted.
- Which allowlisted tools are available.
- Which baseline items still need NAS, 7-day runtime, service decisions, or
  semantic captioning.

## Entry Point

Use the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh baseline_status_probe [workspace_dir] [report_dir]
```

Default local fallback:

```text
workspace_dir: /root/.openclaw/workspace
report_dir: /root/.openclaw/workspace/reports/baseline-status
```

NAS-backed report output after A-003 is complete:

```text
report_dir: /mnt/nas/openclaw/reports/baseline-status
```

## OpenClaw Tool

The narrow OpenClaw plugin exposes the same workflow through:

```text
s100p_run_probe
```

with:

```json
{"tool_id":"baseline_status_probe"}
```

## Output

The probe writes:

```text
baseline_status_*.md
```

The report is intentionally a roll-up, not a replacement for individual
progress evidence files.

## Acceptance

Readiness is verified when:

- The runner writes a report under `/root/.openclaw/workspace/reports/baseline-status`.
- The OpenClaw agent can call `s100p_run_probe` with `tool_id=baseline_status_probe`.
- The report includes current system state, allowlisted tool count, latest
  evidence files, and next best actions.
