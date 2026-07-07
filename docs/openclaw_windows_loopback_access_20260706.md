# OpenClaw Windows Loopback Access Note - 2026-07-06

## Symptom

Running this on the Windows workstation can fail with `Unable to connect to the
remote server`:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/ui
```

This does not by itself mean the S100P OpenClaw gateway is down. `127.0.0.1`
from Windows is the Windows loopback interface, while the product gateway is
intentionally bound to the S100P loopback interface.

## Verified Runtime

Live S100P check on 2026-07-06:

```text
S100P host: 192.168.127.10
S100P user: sunrise
openclaw-gateway.service: active, enabled
qwen25-local-openai-gateway.service: active, enabled
S100P listeners: 127.0.0.1:8765 and 127.0.0.1:18080
S100P curl http://127.0.0.1:8765/api/health: HTTP 200
S100P curl http://127.0.0.1:8765/ui: HTTP 200
S100P curl http://127.0.0.1:18080/health: HTTP 200
```

## Windows Access Path

Keep the gateway loopback-scoped on S100P and create a local SSH tunnel from
Windows when browser or PowerShell access is needed:

```powershell
Start-Process -WindowStyle Hidden `
  -FilePath C:\Windows\System32\OpenSSH\ssh.exe `
  -ArgumentList @(
    '-N',
    '-L', '127.0.0.1:8765:127.0.0.1:8765',
    '-i', 'C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519',
    '-o', 'BatchMode=yes',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=30',
    '-o', 'StrictHostKeyChecking=accept-new',
    'sunrise@192.168.127.10'
  )
```

Then verify from Windows:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/ui |
  Select-Object StatusCode
```

Expected result:

```text
StatusCode
----------
       200
```

## Boundary

Do not rebind the gateway to a public interface just to make Windows
`127.0.0.1` work. The approved access path is SSH forwarding or another
reviewed LAN/Tailscale-only entry point.

## Related Fix

`scripts/windows/s100p-task.ps1` now normalizes CRLF stdin before piping its
embedded shell scripts into remote `bash`. Without that normalization,
read-only actions such as `ssh-smoke` and `diagnose-openclaw` can fail with
messages such as `set: -: invalid option` even when SSH and the S100P services
are healthy.
