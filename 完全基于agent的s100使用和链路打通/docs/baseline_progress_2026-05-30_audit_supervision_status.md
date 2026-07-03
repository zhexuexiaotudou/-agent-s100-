# Baseline Progress: Audit Supervision Status

Date: 2026-05-30

Added a unified read-only supervision status command for the baseline audit
system. It now defaults to Codex-session-only mode after removing Windows-level
background scheduling.

## Implementation

```text
script: scripts/windows/baseline-audit-supervision.ps1
inputs:
  - scripts/windows/baseline-audit-watchdog-task.ps1 -Action status
  - scripts/windows/baseline-audit-watchdog.ps1 -Action status
  - latest managed audit-loop status payload
```

Command:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-supervision.ps1
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-supervision.ps1 -FailOnUnhealthy
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-supervision.ps1 -RequireBackgroundAutomation
```

## Latest Evidence

```text
supervisionHealthy: true
mode: codex-session-only
backgroundAutomationRequired: false
baselineLane: continue-non-nas-readonly-only
startupTaskHealthy: true
safeProgressTaskHealthy: true
safeProgressTaskHealthIgnored: false
watchdogHealthy: true
loopHealthy: true
latestReportFresh: true
requiredChecksOk: true
a010Readable: true
safe progress task installed: false
watchdog task installed: false
watchdog running: false
audit loop running: false
latest audit report: logs/baseline-audit/baseline_audit_20260530-203423.md
A-010 checkpointStatus: collecting
A-010 snapshotCount: 139
FailOnUnhealthy: exit=0
```

## Tracking Impact

Routine review now has a single machine-readable status command without
requiring Windows background automation. It verifies the current decision lane,
required audit checks, and embedded A-010 checkpoint metrics. Automation can use
`-FailOnUnhealthy` as a gate before starting Codex-session work.

If background automation is explicitly re-enabled later,
`-RequireBackgroundAutomation` restores the stricter task/watchdog/loop health
requirements.
