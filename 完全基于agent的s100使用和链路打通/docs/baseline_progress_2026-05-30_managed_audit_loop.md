# Baseline Progress: Managed Audit Loop

Date: 2026-05-30

The background audit loop is now managed through a fixed Windows entrypoint
instead of ad-hoc `Start-Process` commands.

## Implementation

Added:

```text
scripts/windows/baseline-audit-loop.ps1
```

Supported actions:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action ensure
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action restart
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action stop
```

The managed loop writes:

```text
logs/baseline-audit/baseline_audit_loop.pid
logs/baseline-audit/baseline_audit_loop.command.txt
logs/baseline-audit/baseline_audit_loop.started.json
```

By default, the managed loop starts `baseline-audit.ps1` with
`-RefreshA010ReadOnly`, so every half-hour audit also performs the scoped A-010
read-only refresh when the current decision allows it.

`status` defaults to JSON for operator review and log capture. For PowerShell
automation, add `-AsObject` to return a `PSCustomObject` with the same fields:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -Command '$status = & ".\scripts\windows\baseline-audit-loop.ps1" -Action status -AsObject; $status.latestDecision'
```

The status payload includes the latest audit report path, JSON path, decision,
core checks, embedded A-010 checkpoint metrics, and findings. It also checks
audit freshness:

```text
configuredIntervalMinutes: interval recorded when the loop was started
staleGraceMinutes: extra allowed delay before a report is considered stale
latestReportAgeMinutes: current age of the newest audit report
latestReportFresh: true when latestReportAgeMinutes <= interval + grace
loopHealthy: true when the loop process is running and the latest report is fresh
```

`ensure` is idempotent: it returns `healthy` without changing the process when
the loop is healthy, and restarts the loop only when the process is missing or
the latest report is stale.

## Latest Evidence

```text
pid: 148112
status command: powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action status
latest report: logs/baseline-audit/baseline_audit_20260530-192508.md
started metadata: logs/baseline-audit/baseline_audit_loop.started.json
refreshA010ReadOnly: true
latestDecision: continue-non-nas-readonly-only
loopHealthy: true
latestReportFresh: true
ensure status: healthy, action=none
```

Latest report includes:

```text
decision: continue-non-nas-readonly-only
s100p-refresh-a010-local-readonly: exit=0
s100p-read-a010-latest-checkpoint-json: exit=0
A-010 checkpoint: /root/.openclaw/workspace/reports/stability/stability_checkpoint_20260530-192616.md
checkpointStatus: collecting
snapshotCount: 122
continuousElapsedHours: 2.61
continuousRemainingHours: 165.39
continuousEta: 2026-06-06T16:48:29+08:00
```

## Tracking Impact

Loop operations are now reproducible and auditable. Future starts/restarts
should use `baseline-audit-loop.ps1` instead of hand-written PowerShell process
launches. Routine status review no longer requires manually opening the latest
audit JSON because the managed status command surfaces the same decision and
A-010 continuity metrics directly.
