# Baseline Progress: Safe Progress Schedule

Date: 2026-05-30

Added, then removed, a Windows scheduled task for the lane-aware safe progress
runner after clarifying that review should happen only during Codex work
sessions.

## Implementation

```text
task script: scripts/windows/baseline-safe-progress-task.ps1
task name: Digua-Baseline-Safe-Progress
runner: scripts/windows/baseline-safe-progress.ps1 -Action refresh -TimeoutSeconds 180
interval: 30 minutes
trigger: time trigger with PT30M repetition
current state: uninstalled
```

The runner still starts with the unified supervision gate and maps the current
audit lane to an allowed refresh action when run manually from Codex. There is
no longer a Windows-level 30-minute scheduled run.

## Latest Evidence

```text
task installed: true
task last run: 2026-05-30T20:00:26+08:00
task last result: 0
task next run: 2026-05-30T20:30:25+08:00
task removed: true
task installed after removal: false
watchdog task installed after removal: false
audit loop running after removal: false
watchdog running after removal: false
latest safe-progress report: logs/baseline-audit/baseline_safe_progress_20260530-200108.json
latest manual safe-progress report: logs/baseline-audit/baseline_safe_progress_20260530-202343.json
selectedRefreshAction: refresh-baseline-local-readonly
refreshExitCode: 0
outputPathCount: 35
A-010 snapshotCount: 136
A-010 continuousRemainingHours: 164.42
completionAuditOk: true
completionProven: false
completionNotReadyCount: 9
latest audit report: logs/baseline-audit/baseline_audit_20260530-202650.md
```

After adding the infrastructure gate, a manual safe-progress refresh produced
35 output paths, including the review, external-input, and infrastructure gates,
without changing the scheduled cadence.

The 19:30 run exposed a self-gating issue after mutex hardening: safe-progress
could be blocked by its own previous task result. The supervision script now
supports an internal repair-mode switch, and the task was re-run through the
scheduled-task entry point with `lastTaskResult=0`.

## Tracking Impact

Baseline evidence refresh no longer has an unattended Windows cadence. The
half-hour review requirement is now interpreted as a Codex-session process
discipline: when Codex is actively working, it should pause and review progress
periodically, but the computer should not run or display scheduled checks on
its own.
