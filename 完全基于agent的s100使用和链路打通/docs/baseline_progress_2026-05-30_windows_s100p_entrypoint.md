# Baseline Progress: Windows S100P Task Entrypoint

Date: 2026-05-30

Added a fixed Windows-side task entrypoint so Codex can reuse one stable
PowerShell command prefix for routine S100P operations instead of generating a
new SSH command string for every check.

## Added

```text
scripts/windows/s100p-task.ps1
scripts/windows/README.md
```

## Supported Actions

```text
ssh-smoke
diagnose-nas
repair-nas-runtime
diagnose-openclaw
check-overnight
refresh-baseline-readonly
run-startup-link-check
```

## Approval Boundary

The intended stable local prefix is:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1
```

This keeps future S100P interactions behind a small action allowlist. Private
values such as NAS admin passwords, Home Assistant tokens, and Dream 7B model
paths are still operator-provided inputs.

## Validation

PowerShell parser:

```text
PowerShell parse OK
```

SSH smoke:

```text
S100P_SSH_OK
ubuntu
sunrise
2026-05-30T13:12:18+08:00
```

NAS diagnosis through the fixed entrypoint:

```text
eth0: UP, 169.254.8.10/16
route to NAS: 169.254.110.209 dev eth0 src 169.254.8.10
neighbor: 169.254.110.209 FAILED
ping: 2 transmitted, 0 received
autofs mountpoint: /mnt/nas/openclaw present
openclaw: active
```

OpenClaw diagnosis through the fixed entrypoint:

```text
openclaw-gateway.service: active
gateway listeners: 127.0.0.1:18789 and [::1]:18789
ssh listener: 0.0.0.0:22 and [::]:22
```

## Impact

This does not close A-010 or the external-input blockers. It reduces friction
for continuing the two baseline tracks because repeated S100P checks can now
use the same local command prefix and a bounded action set.
