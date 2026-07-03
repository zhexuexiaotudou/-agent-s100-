# Windows S100P Task Entrypoint

Use this folder to keep Codex-side S100P operations behind a small set of fixed
PowerShell commands. The goal is to reduce repeated approval prompts caused by
slightly different ad-hoc `ssh` and `scp` command strings.

Primary entrypoint:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action diagnose-nas
```

Useful actions:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action ssh-smoke
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action diagnose-nas
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action repair-nas-runtime
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action diagnose-openclaw
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action check-overnight
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action validate-baseline-scripts-readonly
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action refresh-a010-local-readonly
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action read-a010-latest-checkpoint-json
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action read-remote-report-file -RemotePath /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_YYYYMMDD-HHMMSS.md
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action refresh-baseline-readonly
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action refresh-baseline-local-readonly
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action run-startup-link-check
```

Baseline audit:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit.ps1 -Iterations 1
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit.ps1 -Iterations 0 -IntervalMinutes 30
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit.ps1 -Iterations 0 -IntervalMinutes 30 -RefreshA010ReadOnly
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action ensure
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action restart
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-loop.ps1 -Action stop
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action ensure
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action restart
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog.ps1 -Action stop
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action install
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-watchdog-task.ps1 -Action uninstall
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-supervision.ps1
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-audit-supervision.ps1 -FailOnUnhealthy
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress.ps1 -Action refresh -TimeoutSeconds 180
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action install -IntervalMinutes 30 -TimeoutSeconds 180
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action status
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action start
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-safe-progress-task.ps1 -Action uninstall
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-completion-audit.ps1
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\baseline-completion-audit.ps1 -FailIfIncomplete
```

Current operating mode is Codex-session-only review. Do not install
`baseline-safe-progress-task.ps1`, `baseline-audit-watchdog-task.ps1`, or the
persistent audit loop unless the operator explicitly asks for background
automation again. The scripts remain available for manual Codex-run checks, but
Windows should not run baseline checks every 30 minutes by itself.

The audit writes timestamped Markdown and JSON reports under
`logs/baseline-audit/`. It reuses this entrypoint for remote checks and
classifies whether work should continue on NAS-backed tasks, continue only on
non-NAS read-only tasks, or hold blocked items. It also checks local JSON,
allowlist/wrapper alignment, and S100P-side Bash/JSON syntax so new probes keep
the same maintenance shape. Use `baseline-audit-loop.ps1` for persistent loop
management so pid, command, and start metadata stay in one place. Its `status`
action emits JSON by default and supports `-AsObject` for PowerShell automation
that needs direct access to `latestDecision`, `latestChecks`,
`latestA010Checkpoint`, or `latestFindings`. It also reports `loopHealthy` and
`latestReportFresh` so automation can detect a stale half-hour audit loop.
Use `ensure` for idempotent guard checks: it does nothing when the loop is
healthy and restarts the managed loop when the report is stale or the process is
missing.
Use `baseline-audit-watchdog.ps1` to run that guard automatically every 5
minutes and write heartbeat records under `logs/baseline-audit/`. Watchdog
status is healthy only when the process is running, the heartbeat is fresh, and
the latest heartbeat has no `error` field.
Use `baseline-audit-watchdog-task.ps1` to install or verify the Windows logon
task that calls the watchdog `ensure` action after login.
Use `baseline-audit-supervision.ps1` as the single read-only gate before new
baseline work. By default it uses Codex-session-only mode, where uninstalled
background tasks and stopped watchdog/loop processes are expected. Pass
`-RequireBackgroundAutomation` only if the operator has explicitly requested
Windows-level scheduled checks again.
Use `baseline-safe-progress.ps1` for routine baseline advancement. It starts
from the supervision gate, maps the current audit lane to the allowed refresh
action, writes a local report under `logs/baseline-audit/`, and runs the
completion audit after successful refreshes.
Use `baseline-safe-progress-task.ps1` only when background scheduling is
explicitly requested; otherwise keep it uninstalled.
Use `baseline-completion-audit.ps1` as the final completion gate. It reads the
latest safe-progress and acceptance evidence, lists not-ready baseline items,
and returns non-zero with `-FailIfIncomplete` until completion is proven.
Safe-progress and its internal completion audit use the supervision script's
repair-mode switch to ignore only the currently running safe-progress task
health, preventing a previous task failure from blocking its own repair path.
The operator review gate is read-only; it proves review packets are ready but
does not approve or execute capture, control, service, or firewall changes.
The external input gate is also read-only; it proves the B-003/B-008 handoff
packets are ready without writing credentials, copying models, or calling
control APIs.
The infrastructure gate is read-only; it proves the A-003/A-006/B-001 handoff
packets are ready without NAS login, mount/unmount, network changes, runtime
installs, or service/firewall changes.

Action boundaries:

- `ssh-smoke`: confirms SSH key login only.
- `diagnose-nas`: read-only NAS-side network and mount diagnostics.
- `repair-nas-runtime`: runtime-only reset of S100P `eth0`, neighbor cache, and
  `169.254.8.10/16` route. It does not touch `eth1`, Windows networking, NAS
  settings, services, or firewall.
- `diagnose-openclaw`: read-only gateway status and recent log summary.
- `check-overnight`: read-only overnight runner and queue status.
- `validate-baseline-scripts-readonly`: read-only S100P-side syntax validation
  for the allowlisted tool wrapper, probe scripts, and tool allowlist JSON.
- `refresh-a010-local-readonly`: scoped read-only A-010 stability snapshot,
  summary, checkpoint, and baseline status refresh for audit-loop automation.
- `read-a010-latest-checkpoint-json`: read-only latest A-010 checkpoint JSON
  extraction for embedding continuity metrics in audit reports.
- `read-remote-report-file`: bounded read-only extraction for files under
  `/root/.openclaw/workspace/reports/` or
  `/root/.openclaw/workspace/logs/probes/`; paths with traversal or unsupported
  characters are rejected, and output is capped with `-MaxLines`.
- `refresh-baseline-readonly`: runs allowlisted read-only baseline report
  generators.
- `refresh-baseline-local-readonly`: runs the same read-only baseline reporting
  loop, plus B-002 deterministic document index/daily summary when a local
  documents directory exists, A-003/B-001 targeted NAS link-blocker evidence,
  A-006 sandbox status/isolation smoke, A-009 named capture request template,
  A-010 local stability snapshot/summary/checkpoint projection, B-005 local
  log diagnosis, B-007 local experiment report generation, and B-010 read-only security/service
  preflights and confirmation template generation.
  It also refreshes the B-003 Dream 7B config template, the B-008 Home
  Assistant template/status, the B-009 control-action template/preflight, A-007
  local browser smoke, B-004 read-only dataset card inventory, and a lane-aware
  baseline next-action queue. All of this runs against
  `/root/.openclaw/workspace` only for periods when NAS is not a real mounted
  NFS/CIFS workspace. The A-006 smoke does not install packages or pull images;
  the B-004 inventory does not record ROS bags or create datasets; the
  B-003/B-008/B-009/B-010 templates are written as report artifacts, not as
  runtime credentials or approval.
  It also refreshes the A-009/B-009/B-010 operator review packet gate.
  It also refreshes the B-003/B-008 external input packet gate.
  It also refreshes the A-003/A-006/B-001 infrastructure packet gate.
- `run-startup-link-check`: runs the local tray checker in `-NoGui -NoDelay`
  mode.

Configuration is loaded from:

```text
scripts/startup_link_check/link-check.config.json
```

When Codex needs access, approve the stable prefix for this entrypoint instead
of each generated SSH command. Private values such as NAS admin password,
Home Assistant token, or Dream 7B model paths should still be supplied by the
operator only when needed.
