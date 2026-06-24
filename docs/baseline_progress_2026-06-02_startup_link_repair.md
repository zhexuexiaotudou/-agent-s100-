# 2026-06-02 Startup Link Repair

## Scope

This note records the repair for the Windows -> S100P -> QNAP NAS -> OpenClaw/Feishu startup checker.

Working tree source during the repair:

- Runtime workspace: `F:\Project\Digua`
- Repository path: `F:\Project\Digua\完全基于agent的s100使用和链路打通`
- Local log used for diagnosis: `F:\Project\Digua\logs\link-check\2026-06-02.jsonl`
- Checker config: `scripts/startup_link_check/link-check.config.json`

## Failure

The checker reported three failures after boot:

- `S100P 外网/DNS`: S100P could reach the Windows gateway `192.168.137.1`, but could not reach `223.5.5.5` or resolve Feishu.
- `S100P -> NAS/NFS`: NAS ICMP worked, but the checker treated the autofs placeholder at `/mnt/nas/openclaw` as a failed NFS mount.
- `OpenClaw/飞书`: `openclaw-gateway.service` was active, but the checker timed out or judged too early before `ws client ready`.

## Root Causes

1. Windows ICS could be enabled in the UI while the actual NAT forwarding path was stale after boot. Restarting `SharedAccess` and rebinding `WLAN -> 以太网` restored S100P Internet access.
2. The checker validated `/mnt/nas/openclaw` directly. With systemd autofs this can show only the autofs layer; it must touch a real child path, then verify `findmnt -T /mnt/nas/openclaw/tmp` includes `nfs4`.
3. OpenClaw startup can need more than 8 seconds to emit `ws client ready`. Inline `systemctl status | grep` checks were also fragile over Windows PowerShell -> SSH stdin quoting. A minimal shell checker now confirms root user service state and today's OpenClaw log.

## Script Coverage Added

Updated `scripts/startup_link_check/S100P-NAS-LinkCheck.ps1`:

- Adds `Ensure-WindowsIcsSharing -ForceReset`.
- Runs the startup check under the existing high-privilege scheduled task so ICS can be repaired automatically.
- Rechecks Windows dual IP after ICS reset because ICS may remove `192.168.127.2/24`.
- Forces the NAS/NFS test through `scripts.startup_link_check.nas.probeDir` (`/mnt/nas/openclaw/tmp`) and requires a real `nfs4` mount plus a write probe.
- Uses a small OpenClaw readiness script instead of a fragile inline `systemctl status` pipeline.

New helper scripts:

- `scripts/startup_link_check/check_openclaw_feishu.sh`: confirms root user `openclaw-gateway.service` is active and today's `/tmp/openclaw/openclaw-YYYY-MM-DD.log` contains `ws client ready`.
- `scripts/startup_link_check/Repair-IcsSharing.ps1`: standalone Windows ICS repair utility for `WLAN -> 以太网`.

Updated config:

- NAS IP: `169.254.143.37`
- NAS export: `/OpenClawWorkspace`
- S100P NAS-side address: `169.254.8.10/16`
- S100P default gateway: `192.168.137.1`

## Verification

Fast no-GUI check from the local workspace passed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File F:\Project\Digua\scripts\startup_link_check\S100P-NAS-LinkCheck.ps1 -NoGui -NoDelay
```

High-privilege scheduled-task startup path also passed. The final run ended with:

```text
status=FIXED
failures=[]
networkOk=true
nasOk=true
openclawOk=true
```

The final successful steps included:

- `S100P 外网/DNS`: `S100P_INTERNET_OK`
- `S100P -> NAS/NFS`: `NAS_LINK_OK`
- `OpenClaw/飞书`: `OPENCLAW_READY`

## Next-Boot Expected Behavior

If the same boot-time state recurs, the checker should now:

1. Reset Windows ICS and rebind `WLAN -> 以太网`.
2. Re-add `192.168.127.2/24` if ICS reset removes it.
3. Restore S100P route/DNS through `192.168.137.1`.
4. Trigger and verify real NAS NFS mount/write through `/mnt/nas/openclaw/tmp`.
5. Restart OpenClaw only when needed and confirm Feishu WebSocket readiness from the current-day log.
