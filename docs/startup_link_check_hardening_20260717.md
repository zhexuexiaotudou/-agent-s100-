# S100P/NAS startup link hardening acceptance — 2026-07-17

## Incident

After the NAS and S100P were powered on, the Windows management Ethernet link was initially unplugged. When it was connected later, PC → S100P and S100P → NAS Ethernet became reachable, but `/mnt/nas/openclaw` was not mounted and the AI-NAS portal and local Qwen services were unavailable.

The live boot journal showed the exact race:

- systemd attempted `169.254.143.37:/OpenClawWorkspace` at boot and received `mount.nfs4: Network is unreachable`;
- repeated requests exhausted the unit start limit, leaving both `mnt-nas-openclaw.mount` and `.automount` failed;
- `eth0` reached `1 Gbps/full` only after those failed attempts;
- the old Windows tray checker ran once while Ethernet was disconnected and did not retry after the cable was inserted;
- the old OpenClaw check still looked for a historical Feishu log marker and reported a false failure even though the current system gateway was healthy.

## Live repair

The real S100P was repaired without changing the NAS export:

- reset both mount and automount failed states;
- started the automount and NFS mount;
- verified the exact source `169.254.143.37:/OpenClawWorkspace` at `/mnt/nas/openclaw`;
- passed a write → read → delete probe in `/mnt/nas/openclaw/tmp`;
- restarted the sunrise-user AI-NAS portal and Qwen services;
- re-established Windows WLAN → Ethernet ICS using the existing highest-privilege scheduled task;
- confirmed that NTP restored the S100P clock after internet connectivity returned.

## Checker hardening

The checker now covers the current topology and the observed failure families:

1. Automatic tray retries recover from a cable or NAS that comes online after Windows logon.
2. Remote scripts are normalized from CRLF to LF before `bash -s`; this closes a Windows/Linux false-positive path discovered during this acceptance.
3. ICS is checked first and force-reset only after an S100P DNS/HTTPS failure.
4. The S100P clock is compared with Windows and repaired when drift exceeds the configured threshold.
5. NAS recovery validates the current NFS export, resets both mount units, verifies the exact source, and removes the temporary write probe.
6. OpenClaw checks distinguish the system gateway from the sunrise-user portal and Qwen services and require all three loopback HTTP health checks.
7. Root-disk pressure is reported at 90% and becomes a failed gate at 98%.
8. `-SelfTest` validates configuration, PowerShell syntax, secret redaction, recovery markers, and the service-check contract; GitHub Actions runs it on `windows-latest`.

## Acceptance evidence

The final normal-path run reported:

- Windows Ethernet: `1 Gbps`;
- PC → S100P ping/SSH/key: OK;
- S100P clock skew: `1s`;
- S100P gateway, DNS, and HTTPS to `open.weixin.qq.com`: OK;
- NAS NFS mount and write/read/delete probe: OK;
- system OpenClaw `18765/health`: HTTP 200;
- AI-NAS portal `8765/api/health`: HTTP 200;
- local Qwen `18080/health`: HTTP 200.

A controlled failure test stopped the sunrise-user portal and Qwen services. The checker returned `FIXED`, restarted the stack, and restored all three service health checks.

## Residual warning

The S100P root filesystem was 96% used with about 2.1 GB available. This did not block the link acceptance, but it remains an operational warning and should be handled through the repository's read-only-first storage cleanup workflow before it reaches the 98% failure threshold.
