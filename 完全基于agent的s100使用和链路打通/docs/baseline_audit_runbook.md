# Baseline Audit Runbook

This runbook fixes the review cadence for the two baseline tracks:

- Baseline A: S100P parity with the useful parts of PC OpenClaw.
- Baseline B: S100P + NAS coverage of AI NAS / OpenClaw NAS functions.

The audit must run before new work starts and then every 30 minutes while the
baseline work continues.

## Command

One-shot audit:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit.ps1 -Iterations 1
```

Continuous 30-minute audit loop:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit.ps1 -Iterations 0 -IntervalMinutes 30
```

Continuous 30-minute audit loop with scoped A-010 read-only refresh:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit.ps1 -Iterations 0 -IntervalMinutes 30 -RefreshA010ReadOnly
```

Managed loop commands:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action ensure
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action restart
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action stop
```

Managed watchdog commands:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action ensure
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action restart
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action stop
```

Watchdog startup task commands:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action install
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action uninstall
```

Unified supervision check:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-supervision.ps1
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-supervision.ps1 -FailOnUnhealthy
```

Read approved remote reports without ad-hoc SSH:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action read-remote-report-file -RemotePath /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_YYYYMMDD-HHMMSS.md -MaxLines 240
```

Lane-aware safe progress runner:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress.ps1 -Action refresh -TimeoutSeconds 180
```

Safe progress schedule:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action install -IntervalMinutes 30 -TimeoutSeconds 180
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action uninstall
```

Completion audit gate:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-completion-audit.ps1
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-completion-audit.ps1 -FailIfIncomplete
```

The watchdog checks the managed loop every 5 minutes by default. It calls
`baseline-audit-loop.ps1 -Action ensure`, writes a heartbeat JSONL record, and
keeps process launch behavior behind the same fixed entrypoints. Watchdog
health requires a running process, a fresh heartbeat, and a clean heartbeat
without an `error` field.

The scheduled task `Digua-Baseline-Audit-Watchdog` runs at Windows logon and
calls `baseline-audit-watchdog.ps1 -Action ensure`, restoring the watchdog and
managed audit loop without a manual shell command.

`status` emits JSON by default. Use `-AsObject` when another PowerShell command
needs to consume the result without reparsing JSON text:

```powershell
powershell.exe -ExecutionPolicy Bypass -Command '$status = & ".\scripts\windows\baseline-audit-loop.ps1" -Action status -AsObject; $status.latestA010Checkpoint.continuousEta'
```

The status output includes `loopHealthy`, `latestReportFresh`,
`latestReportAgeMinutes`, `configuredIntervalMinutes`, `staleGraceMinutes`, and
`staleAfterMinutes`. Treat `loopHealthy=false` as an audit-system failure to
repair before starting new baseline work.

Use `ensure` for unattended guard checks. It returns `healthy` and leaves the
process untouched when the loop is current; otherwise it restarts the loop
through the same managed entrypoint.

Reports are written to:

```text
logs/baseline-audit/
```

The managed loop also writes:

```text
logs/baseline-audit/baseline_audit_loop.pid
logs/baseline-audit/baseline_audit_loop.command.txt
logs/baseline-audit/baseline_audit_loop.started.json
logs/baseline-audit/baseline_audit_watchdog.pid
logs/baseline-audit/baseline_audit_watchdog.command.txt
logs/baseline-audit/baseline_audit_watchdog.started.json
logs/baseline-audit/baseline_audit_watchdog.heartbeat.jsonl
```

## Consistency Checks

Each audit verifies:

- PowerShell parser checks for Windows entrypoints.
- UTF-8 JSON parsing for `scripts/tool_allowlist.json` and
  `scripts/startup_link_check/link-check.config.json`.
- `tool_allowlist.json` entries stay aligned with
  `scripts/run_allowlisted_tool.sh`: each tool must have a script file, wrapper
  case branch, matching script reference, mode, and approved output prefixes.
- S100P-side Bash syntax for `scripts/run_allowlisted_tool.sh` and
  `scripts/probes/*.sh`.
- S100P-side JSON parsing for `/root/.openclaw/workspace/scripts/tool_allowlist.json`.
- When `-RefreshA010ReadOnly` is set and the decision allows read-only work,
  the audit runs the scoped A-010 refresh, reads the latest checkpoint JSON, and
  embeds the core continuity metrics in the audit Markdown/JSON report.
- The managed loop `status` command exposes the latest report path, JSON path,
  decision, checks, findings, and embedded A-010 checkpoint metrics so routine
  review can be done from one fixed command surface.
- The managed loop status also flags stale audit output, so a running process
  without a recent report is not mistaken for a healthy half-hour review loop.
- The managed loop `ensure` action provides the repair path for stale or missing
  audit loops without introducing another ad-hoc process-launch command.
- The managed watchdog runs that repair check unattended, so the half-hour audit
  process does not rely on manual supervision.
- The Windows logon task restores the watchdog after login, reducing the chance
  that a reboot or logout leaves the baseline work without audit supervision.
- The unified supervision check is the preferred read-only gate before new
  baseline work. It aggregates the watchdog logon task, safe-progress cadence
  task, watchdog, loop, latest audit checks, lane, and A-010 checkpoint health
  into one machine-readable result.

## Decision Rules

- `continue-nas-backed-baseline`: S100P SSH, OpenClaw, NAS reachability, and the
  NAS mount are all confirmed. NAS-backed baseline probes may continue.
- `continue-non-nas-readonly-only`: S100P SSH and OpenClaw are healthy, but NAS
  is not reachable. Continue only non-NAS read-only checks and documentation.
- `hold-blocked-items`: a blocker exists. Do not widen scope or run service,
  firewall, mount, or control actions until the blocker is resolved.
- `continue`: local checks are clean, but no stronger NAS-backed decision was
  reached.

## Maintenance Rules

- Reuse `scripts/windows/s100p-task.ps1`; do not add new ad-hoc SSH command
  shapes for routine checks.
- Keep NAS credentials and private tokens out of committed files and audit
  output.
- Treat NAS ARP or ping failure as a physical/link/IP issue, not a password
  issue.
- Do not run B-009 control actions or B-010 service/firewall changes unless the
  disabled-by-default config has been reviewed and the preflight passes.
- New probes should be read-only by default and should be added to the existing
  allowlist before any agent path calls them.
- Routine report inspection should use `s100p-task.ps1 -Action
  read-remote-report-file` instead of ad-hoc SSH. It is restricted to report and
  probe-log paths and caps output by line count.
- Routine baseline refresh should use `baseline-safe-progress.ps1 -Action
  refresh`. It gates on supervision health, selects the refresh command from the
  current audit lane, writes a local safe-progress report, and runs the
  completion audit against the refreshed evidence.
- The scheduled safe-progress task runs the same lane-aware runner every 30
  minutes. It must remain healthy before claiming unattended baseline progress.
- The completion audit is the final goal gate. Do not mark both baseline tracks
  complete unless `completionProven=true`; `-FailIfIncomplete` returns non-zero
  while any baseline item is not ready.
