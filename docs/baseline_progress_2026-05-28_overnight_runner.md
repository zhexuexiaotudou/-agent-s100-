# Baseline Progress: Overnight Baseline Runner

Date: 2026-05-28

This note records the overnight S100P background runner used to continue the two
baseline tracks while Codex or the PC can be left unattended.

## Scripts

```text
scripts/overnight_baseline_runner.sh
scripts/start_overnight_baseline_runner.sh
scripts/check_overnight_baseline_runner.sh
```

Default behavior:

- duration: 10 hours
- interval: 1800 seconds
- output root: `/mnt/nas/openclaw/logs/overnight`
- mode: read-only probes and reports

Each iteration runs:

- `stability_snapshot_probe`
- `stability_summary_probe`
- `baseline_status_probe`

The first iteration and every fourth iteration also run:

- `openclaw_status_probe`
- `security_audit_probe`

The runner does not install packages, change services, change firewall rules, or
delete data.

## Current Background Run

```text
pid: 72079
launch_log: /mnt/nas/openclaw/logs/overnight/overnight_launch_20260528-232330.out
jsonl: /mnt/nas/openclaw/logs/overnight/overnight_baseline_20260528-232330.jsonl
report: /mnt/nas/openclaw/logs/overnight/overnight_baseline_20260528-232330.md
pid_file: /mnt/nas/openclaw/logs/overnight/overnight_baseline_20260528-232330.pid
```

First iteration evidence:

```text
stability_snapshot: /mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-232330.md
stability_summary: /mnt/nas/openclaw/reports/stability/stability_summary_20260528-232339.md
baseline_status: /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-232339.md
openclaw_status: /mnt/nas/openclaw/logs/probes/openclaw_status_20260528-232340.txt
security_audit: /mnt/nas/openclaw/logs/probes/security_audit_20260528-232340.md
```

## How To Check

```bash
sudo ps -p 72079 -o pid=,etime=,cmd=
sudo tail -n 20 /mnt/nas/openclaw/logs/overnight/overnight_baseline_20260528-232330.jsonl
sudo /root/.openclaw/workspace/scripts/check_overnight_baseline_runner.sh
```

The status checker writes a Markdown report under:

```text
/mnt/nas/openclaw/reports/baseline-status/overnight_baseline_YYYYmmdd-HHMMSS_status.md
```

It summarizes whether the process is still running, how many iterations are
visible in JSONL, latest events by action, and whether any failed events have
been recorded.

Current status-check evidence:

```text
status_report: /mnt/nas/openclaw/reports/baseline-status/overnight_baseline_20260528-232330_status.md
pid: 72079
process_status: running
completed_iterations_observed: 1
event_count: 8
failed_event_count: 0
last_event_action: iteration_end
last_event_status: ok
```

## How To Stop

```bash
sudo kill 72079
```

Stopping the runner only stops future overnight sampling. It does not affect the
existing systemd stability sampler or any already written NAS reports.
