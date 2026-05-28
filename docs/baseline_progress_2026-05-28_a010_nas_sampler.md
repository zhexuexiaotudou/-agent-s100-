# Baseline Progress: A-010 NAS-backed Stability Sampler

Date: 2026-05-28

本文记录 A-010 stability sampler 从本地 workspace 输出切换到 NAS 输出。

## Verdict

| Item | Status | Evidence |
| --- | --- | --- |
| systemd timer | active | `openclaw-stability-sampler.timer` enabled and waiting. |
| output directory | NAS-backed | service now writes to `/mnt/nas/openclaw/logs/probes`. |
| immediate run | pass | service exited `status=0/SUCCESS` and generated a NAS snapshot. |
| summary | collecting | 2 snapshots, elapsed 0.29h, OOM=0, Gateway error-like logs=0. |

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

Immediate run evidence:

```text
Process: ExecStart=...stability_snapshot_probe.sh /mnt/nas/openclaw/logs/probes (code=exited, status=0/SUCCESS)
/mnt/nas/openclaw/logs/probes/stability_snapshot_20260528-183318.md
```

## Updated Summary

Output:

```text
/mnt/nas/openclaw/reports/stability/stability_summary_20260528-183432.md
```

Key fields:

```text
Snapshot count: 2
First snapshot: 2026-05-28T18:15:46+08:00
Last snapshot: 2026-05-28T18:33:19+08:00
Elapsed hours: 0.29
Max kernel OOM matches in last 24h: 0
Max Gateway error-like matches in last 24h: 0
Verdict: collecting
Observed Gateway Statuses: 2 active-listening
Observed NAS Statuses: 2 mounted
```

`stability_summary_probe.sh` 也已修正：当 input/report 都在 NAS 路径下时，不再输出
“A-003 挂载后再做 NAS-backed”的旧提示，而是输出：

```text
NAS-backed stability collection is active; continue collecting until the 168-hour threshold is reached.
```

## Baseline Impact

- A-010 remains `doing`: timer 已经 NAS-backed，但 7x24 验收至少需要 168 小时样本。
- A-003 remains `verified`: NAS mount 支撑了 sampler 输出。
- 后续只需要持续采样并定期 rerun summary/roll-up，不需要用户盯着。
