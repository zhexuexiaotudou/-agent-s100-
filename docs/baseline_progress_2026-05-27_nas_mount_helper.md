# Baseline Progress: NAS Mount Helper

Date: 2026-05-27

## Status

| Item | Status | Evidence |
| --- | --- | --- |
| A-003 mount execution helper | verified dry-run | `scripts/mount_openclaw_nas.sh` was synced to the S100P and produced a safe dry-run plan for `/mnt/nas/openclaw`. |
| A-003 real NAS mount | pending external input | TS-264C host, protocol, share/export, account, and credential are still needed. |
| SMB dependency | verified | `cifs-utils` was installed on the S100P; `mount.cifs` is now `/usr/sbin/mount.cifs`. |

## Script Boundary

Script:

```text
scripts/mount_openclaw_nas.sh
```

Safety choices:

- Default mode is dry-run.
- `--apply` is required before mounting or writing credentials.
- `--write-fstab` is required before appending persistent mount configuration.
- The mountpoint must be `/mnt/nas/openclaw` or a child path.
- SMB credentials are read from `OPENCLAW_NAS_PASSWORD` only when `--create-credentials` is explicitly set.
- NAS passwords are not stored in the repository.

## Board Validation

The script was uploaded to:

```text
/root/.openclaw/workspace/scripts/mount_openclaw_nas.sh
```

The workspace initialization script was also uploaded because `--init-workspace` depends on it:

```text
/root/.openclaw/workspace/scripts/init_nas_workspace.sh
```

Syntax check:

```text
bash -n /root/.openclaw/workspace/scripts/mount_openclaw_nas.sh
mount_syntax:0
bash -n /root/.openclaw/workspace/scripts/init_nas_workspace.sh
init_syntax:0
```

Dry-run command:

```bash
/root/.openclaw/workspace/scripts/mount_openclaw_nas.sh \
  --protocol smb \
  --host 192.168.137.1 \
  --share OpenClawWorkspace
```

Dry-run output:

```text
protocol=smb
host=192.168.137.1
share=OpenClawWorkspace
mountpoint=/mnt/nas/openclaw
source=//192.168.137.1/OpenClawWorkspace
mode=dry-run
mount.cifs=missing
ping=ok
already_mounted=no
DRY_RUN_DONE
```

The host used here was the Windows ICS host for reachability smoke testing, not the final TS-264C NAS address.

Unsafe mountpoint rejection:

```text
/root/.openclaw/workspace/scripts/mount_openclaw_nas.sh \
  --protocol smb \
  --host 192.168.137.1 \
  --share OpenClawWorkspace \
  --mountpoint /mnt/nas

unsafe_exit:2
Refusing mountpoint outside /mnt/nas/openclaw: /mnt/nas
```

## 2026-05-27 SMB Dependency Installed

Before installation:

```text
mount.cifs=missing
apt_get=ok
ping_ip=ok
ping_dns=ok
cifs-utils Installed: (none)
cifs-utils Candidate: 2:6.14-1ubuntu0.3
```

Command executed on the S100P:

```bash
DEBIAN_FRONTEND=noninteractive apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y cifs-utils
```

After installation:

```text
/usr/sbin/mount.cifs
mount.cifs version: 6.14
cifs-utils Installed: 2:6.14-1ubuntu0.3
```

Dry-run after installation:

```text
mount.cifs=ok
ping=ok
already_mounted=no
DRY_RUN_DONE
```

Additional direct check:

```text
/usr/sbin/mount.cifs
tcp_445=ok
already_mounted=no
```

OpenClaw health after the package install remained OK:

```text
gatewayRunning=true
aiReady=true
```

## Next Acceptance

After TS-264C share details are available:

1. Run the helper in dry-run mode against the real NAS host.
2. Run with `--apply --create-credentials --init-workspace`.
3. Verify `findmnt /mnt/nas/openclaw`.
4. Re-run B-002 and B-005 against the NAS-backed paths.
5. Only then run with `--write-fstab --apply` and validate after reboot.
