# S100P/NAS startup link hardening acceptance — 2026-07-17

## Incident

After the NAS and S100P were powered on, the Windows management Ethernet link was initially unplugged. When it was connected later, PC → S100P and S100P → NAS Ethernet became reachable, but `/mnt/nas/openclaw` was not mounted and the AI-NAS portal and local Qwen services were unavailable.

The live boot journal showed the exact race:

- systemd attempted `169.254.143.37:/OpenClawWorkspace` at boot and received `mount.nfs4: Network is unreachable`;
- repeated requests exhausted the unit start limit, leaving both `mnt-nas-openclaw.mount` and `.automount` failed;
- `eth0` reached `1 Gbps/full` only after those failed attempts;
- the old Windows tray checker ran once while Ethernet was disconnected and did not retry after the cable was inserted;
- the old OpenClaw check still looked for a historical Feishu log marker and reported a false failure even though the current system gateway was healthy.

## Verified environment

- S100P: Ubuntu 22.04.5 LTS, kernel `6.1.158-rt58-DR-4.0.5-2603031328-g9f678e-g6caa4d`;
- OpenClaw: `2026.6.10 (aa69b12)`, system gateway bound to loopback port `18765`;
- NAS: QNAP TS-264C, NFS export `169.254.143.37:/OpenClawWorkspace`, mounted at `/mnt/nas/openclaw`;
- management path: Windows `192.168.127.2` → S100P `192.168.127.10` over SSH as `sunrise`;
- internet sharing: Windows WLAN → Ethernet ICS, S100P default route via `192.168.137.1`.

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

## Delivery and production evidence

- implementation commit: `5633b43bf713ddf3acfde731fe87f6079f695a71`;
- merged main revision: `8eb4a6edbed3811981b57a36f8818a08976e6eaa` (PR #14);
- CI: `startup-link-check-contract` and `offline-regression` passed before merge;
- Windows scheduled task: `S100P-NAS-OpenClaw-LinkCheck`, still using the established highest-privilege task and the canonical `F:\Project\Digua\scripts\startup_link_check\S100P-NAS-LinkCheck.ps1` path;
- production run: 2026-07-17 16:31:12–16:32:10, final `status=OK`, with all Windows, SSH, clock, network, NAS, storage and OpenClaw gates true;
- runtime SHA-256: PowerShell `143F8008F1A334494473336EB96CFF9DD6EBF2C1A8A1D2367A41D52A3097A0B1`, config `8CB2FFE177A5EAB923F71D96473372D647DF902876F452361B84600D549E7313`, remote shell check `43E8965EC66E774B62085BB414D230E760F496B96030FB397A56A78F982C1FC6`;
- rollback point: main revision `49c8cf9`; restore the three startup-check runtime files from that revision and restart the scheduled task.

## Residual warning

The final S100P check showed the root filesystem at 95% used with about 2.2 GB available; the NAS was 15% used. This did not block the link acceptance, but the root filesystem remains an operational warning and should be handled through the repository's read-only-first storage cleanup workflow before it reaches the 98% failure threshold.

No Gateway listener was exposed to the public network, NAS access remained limited to the existing `/OpenClawWorkspace` export, and no robot-control permission was added. GPT Pro review is optional for architecture review and is not required for this operational acceptance.

## Storage warning resolution

The warning above was resolved on 2026-07-17. Low-risk caches were cleaned and the complete 25.59 GB board-local Dream7B HBM tree was archived to NAS with 40/40 source and NAS SHA-256 verification. The original path is now a compatibility symlink to the dated NAS archive. The final link-check reported root usage at 33%, about 31.0 GB available, NAS usage at 17%, and all service health gates passing. See `docs/s100p_root_storage_cleanup_20260717.md`.
