# Experiment Report Runbook

This runbook supports B-007: weekly or experiment report generation from existing OpenClaw workspace artifacts.

## Goal

Generate a small Markdown report from the current workspace without giving the agent arbitrary shell access.

The first baseline report summarizes:

- Probe report count.
- Existing experiment report count.
- Browser smoke screenshots.
- Document indexes.
- ROS bag dataset directories.
- Dataset cards.
- Latest probe reports.
- Latest dataset cards.
- Latest browser smoke reports.
- Latest document indexes.
- Current blockers and suggested next actions.

## Entry Point

Use the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh experiment_report_probe [report_dir]
```

Default local fallback output:

```text
/root/.openclaw/workspace/reports/experiments
```

NAS-backed output after A-003 is complete:

```text
/mnt/nas/openclaw/reports/experiments
```
## OpenClaw Tool

The narrow OpenClaw plugin exposes the same workflow through:

```text
s100p_run_probe
```

with:

```json
{"tool_id":"experiment_report_probe"}
```

The plugin does not accept arbitrary commands or script paths.

## Acceptance

Local fallback is verified when:

- The runner writes `experiment_report_*.md` under `/root/.openclaw/workspace/reports/experiments`.
- The OpenClaw agent can call `s100p_run_probe` with `tool_id=experiment_report_probe`.
- The report includes a `Summary` table with counts for probe reports, browser screenshots, document indexes, ROS bag datasets, and dataset cards.

NAS-backed acceptance still requires the same flow to write under:

```text
/mnt/nas/openclaw/reports/experiments
```
