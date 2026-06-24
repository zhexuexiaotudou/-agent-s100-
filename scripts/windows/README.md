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
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action refresh-baseline-readonly
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 -Action run-startup-link-check
```

Action boundaries:

- `ssh-smoke`: confirms SSH key login only.
- `diagnose-nas`: read-only NAS-side network and mount diagnostics.
- `repair-nas-runtime`: runtime-only reset of S100P `eth0`, neighbor cache, and
  `169.254.8.10/16` route. It does not touch `eth1`, Windows networking, NAS
  settings, services, or firewall.
- `diagnose-openclaw`: read-only gateway status and recent log summary.
- `check-overnight`: read-only overnight runner and queue status.
- `refresh-baseline-readonly`: runs allowlisted read-only baseline report
  generators.
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
