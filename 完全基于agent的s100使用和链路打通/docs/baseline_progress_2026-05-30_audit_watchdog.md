# Baseline Progress: Audit Watchdog

Date: 2026-05-30

Added a managed watchdog for the half-hour baseline audit loop.

## Implementation

```text
script: scripts/windows/baseline-audit-watchdog.ps1
startup task script: scripts/windows/baseline-audit-watchdog-task.ps1
default check interval: 5 minutes
guarded command: scripts/windows/baseline-audit-loop.ps1 -Action ensure
startup task: Digua-Baseline-Audit-Watchdog
```

Supported actions:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action ensure
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action restart
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action stop
```

Startup task actions:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action install
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action uninstall
```

The watchdog writes:

```text
logs/baseline-audit/baseline_audit_watchdog.pid
logs/baseline-audit/baseline_audit_watchdog.command.txt
logs/baseline-audit/baseline_audit_watchdog.started.json
logs/baseline-audit/baseline_audit_watchdog.heartbeat.jsonl
```

## Latest Evidence

```text
watchdog pid: 150532
watchdogHealthy: true
heartbeatFresh: true
heartbeatClean: true
last heartbeat ensureStatus: healthy
last heartbeat ensureAction: none
guarded audit loop pid: 148112
guarded audit loop healthy: true
latest decision: continue-non-nas-readonly-only
latest audit report: logs/baseline-audit/baseline_audit_20260530-192508.md
startup task installed: true
startup task name: Digua-Baseline-Audit-Watchdog
startup task trigger: logon
startup task last run: 2026-05-30T18:30:32+08:00
startup task last result: 0
```

## Tracking Impact

The half-hour audit loop now has an unattended local repair path. If the audit
loop process exits or its latest report becomes stale, the watchdog calls the
managed `ensure` action and restarts the loop through the same fixed command
surface. This reduces manual review to inspecting reports and blockers rather
than supervising the audit process itself.

The Windows scheduled task now calls the watchdog `ensure` action at logon, so
the watchdog and audit loop are restored after a user login without manually
starting the scripts.
