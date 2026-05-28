# Baseline Progress: A-010 NAS-backed Stability Sampler

Date: 2026-05-28

本文记录 A-010 stability sampler 从本地 workspace 输出切换到 NAS 输出后的最新采样状态。

## Verdict

| Item | Status | Evidence |
| --- | --- | --- |
| systemd timer | active | `openclaw-stability-sampler.timer` enabled and waiting. |
| output directory | NAS-backed | service writes to `/mnt/nas/openclaw/logs/probes`. |
| latest summary | collecting | 10 snapshots, elapsed 4.29h, OOM=0, Gateway error-like logs=0. |
| acceptance | not yet | A-010 still needs at least 168 hours of clean samples. |

## Previous State

Before this update, the timer was active but still wrote to the local workspace:

```text
Environment=OPENCLAW_PROBE_DIR=/root/.openclaw/workspace/logs/probes
ExecStart=/usr/bin/env bash .../stability_snapshot_probe.sh /root/.openclaw/workspace/logs/probes
```

## Updated Service

Current service:

```text
Environment=OPENCLAW_PROBE_DIR=/mnt/nas/openclaw/logs/probes
ExecStart=/usr/bin/env bash /root/.openclaw/workspace/scripts/probes/stability_snapshot_probe.sh /mnt/nas/openclaw/logs/probes
```

Timer:

```text
openclaw-stability-sampler.timer: active (waiting)
OnBootSec=2min
OnUnitActiveSec=1800s
Persistent=true
```

## Latest NAS Summary

Output:

```text
/mnt/nas/openclaw/reports/stability/stability_summary_20260528-223427.md
```

Key fields:

```text
Snapshot count: 10
First snapshot: 2026-05-28T18:15:46+08:00
Last snapshot: 2026-05-28T22:33:22+08:00
Elapsed hours: 4.29
Max kernel OOM matches in last 24h: 0
Max Gateway error-like matches in last 24h: 0
Verdict: collecting
Observed Gateway Statuses: 10 active-listening
Observed NAS Statuses: 10 mounted
```

The latest snapshot was:

```text
/mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-223322.md
```

## Baseline Impact

- A-010 remains `doing`: the sampler is NAS-backed and clean so far, but the acceptance threshold is 168 hours.
- A-003 remains `verified`: NAS mount supports sampler output and report output.
- The next no-touch action is to keep the timer running and periodically regenerate `stability_summary_probe` and `baseline_status_probe`.
