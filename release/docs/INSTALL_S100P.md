# S100P Deployment Guide

This is a guided appliance installation, not an optimistic copy script. The
installer stops when the board, BPU, NAS mount source, required Qwen runtime
paths, administrator bootstrap, or authenticated verification cannot be proven.

## 1. Prepare and transfer the package

On the development machine, build and verify the release archive:

```bash
python3 scripts/build_release.py --version 0.2.0 --out dist
sha256sum -c dist/digua-ai-nas-s100p-0.2.0.sha256
scp dist/digua-ai-nas-s100p-0.2.0.tar.gz sunrise@S100P_IP:/tmp/
```

On S100P, extract into a temporary directory. Do not extract over an existing
installation:

```bash
mkdir -p /tmp/digua-release
tar -xzf /tmp/digua-ai-nas-s100p-0.2.0.tar.gz -C /tmp/digua-release
cd /tmp/digua-release
```

## 2. Discover the NAS and prepare only inputs that cannot be inferred

The package can inspect existing mounts, passive neighbour/mDNS state and an
explicitly supplied host without logging in, mounting, changing state or
scanning a subnet:

```bash
python3 release/install/deploy_wizard.py --discover-only
python3 release/install/discover_nas.py --host 192.168.1.20
```

The guide presents discovered candidates, NFS/SMB availability,
guest-visible exports/shares and likely vendor management URLs. The user must
still confirm the dedicated allowed share. If discovery cannot prove a value,
the guide asks for the NAS IP/hostname, enabled protocol and export/share name.

## 3. Prepare NAS authorization and a model provider

Use a dedicated NAS export/share for Digua. Do not grant the application the
whole NAS. For SMB, create the credentials file yourself and protect it:

```bash
sudo install -d -m 700 /etc/digua-ai-nas
sudo sh -c 'umask 077; printf "username=YOUR_USER\npassword=YOUR_PASSWORD\n" > /etc/digua-ai-nas/smb.credentials'
sudo chmod 600 /etc/digua-ai-nas/smb.credentials
```

The guide asks for the Qwen model directory, runtime executable, runtime config,
runtime library directory and active HBM file. CLIP, YOLO, OCR and ASR are
optional at install time and remain visibly degraded until configured.

Cloud mode instead uses an HTTPS OpenAI-compatible endpoint. Copy
`release/configs/deploy.cloud.example.json`, set the base URL and model ID, and
provide the API key only through the configured environment variable:

```bash
read -rsp 'Cloud API key: ' DIGUA_CLOUD_API_KEY; export DIGUA_CLOUD_API_KEY
sudo -E python3 release/install/deploy_wizard.py \
  --config release/configs/deploy.cloud.example.json --non-interactive --yes
unset DIGUA_CLOUD_API_KEY
```

The key is written to a protected S100P-only file; it is never written into the
deployment config, report, systemd unit or release archive. NAS-scoped and
privacy-classified prompts are handled by local allowlisted tools and are not
forwarded to the cloud provider.

## 4. Run the guide

System service mode is the recommended appliance mode. Run:

```bash
sudo -E python3 release/install/deploy_wizard.py
```

The guide selects the original sudo user (normally `sunrise`) as the
unprivileged service account. systemd runs the portal, Qwen gateway and worker
as that user, and NAS/report write tests are performed with the same identity;
root-only write success is not accepted.

### Keep one Qwen service scope

The appliance install uses the system unit. A legacy user unit with the same
name may still be pulled in by a user-scope OpenClaw unit even when that Qwen
unit is disabled. If both scopes run, they race for `127.0.0.1:18080` and the
system unit enters an auto-restart loop. Check before upgrade:

```bash
systemctl is-enabled qwen25-local-openai-gateway.service
systemctl --user is-enabled qwen25-local-openai-gateway.service
systemctl --user list-dependencies --reverse qwen25-local-openai-gateway.service
sudo ss -ltnp | grep ':18080 '
```

Exactly one Qwen gateway may own port 18080. For an appliance deployment keep
the system unit, preserve the legacy user-unit file as a rollback copy, and
mask the user unit. Do not delete the legacy file. Run these commands as the
service user, not from a root login:

```bash
unit_dir="$HOME/.config/systemd/user"
unit="qwen25-local-openai-gateway.service"
backup="$unit_dir/$unit.pre-system-scope-$(date +%Y%m%d)"
systemctl --user stop "$unit"
mv "$unit_dir/$unit" "$backup"
systemctl --user mask "$unit"
systemctl --user daemon-reload
sudo systemctl restart "$unit"
```

Verify that the user unit is `masked`, the system unit is `active`, and the
system unit MainPID owns port 18080. To roll back, first stop the system unit,
then restore the preserved file and start only the user unit:

```bash
unit_dir="$HOME/.config/systemd/user"
unit="qwen25-local-openai-gateway.service"
backup="$unit_dir/$unit.pre-system-scope-YYYYMMDD"
sudo systemctl stop qwen25-local-openai-gateway.service
systemctl --user unmask qwen25-local-openai-gateway.service
mv "$backup" "$unit_dir/$unit"
systemctl --user daemon-reload
systemctl --user start "$unit"
```

Do not execute the migration when `$unit_dir/$unit` is absent or already a
symlink; inspect the current unit and backup paths first.

The administrator password is read with a hidden prompt, passed only through a
process environment variable, and is never included in a command, report, unit
file, or repository file. The guide performs these gates in order:

1. secret-free NAS candidate discovery and explicit user scope approval;
2. strict S100P/BPU/systemd preflight;
3. NAS reachability and actual NFS/CIFS mount with a managed `/etc/fstab` block;
4. mounted source/type and writable Personal-root verification;
5. local-runtime paths or cloud-provider configuration verification;
6. application copy, isolated venv and optional wheelhouse install;
7. rendered loopback-only systemd units and service start;
8. real identity-store administrator bootstrap and authenticated verification.

The mount helper backs up `/etc/fstab` before replacing only the block between
`# BEGIN DIGUA-AI-NAS` and `# END DIGUA-AI-NAS`. A local directory is rejected
as a NAS unless `--allow-local-storage` is explicitly supplied.

For an offline Python dependency install, place compatible S100P wheels in a
directory and set `wheelhouse` in the guide JSON config. The installer then uses
`pip --no-index --find-links`. Vendor BPU runtimes remain device-managed.
Start from `release/configs/deploy.example.json`; keep passwords out of that
file and provide them only through the configured password environment variable.

## 5. Access and verify

The services bind to S100P loopback. From the PC:

```bash
ssh -N -L 8765:127.0.0.1:8765 -L 18080:127.0.0.1:18080 sunrise@S100P_IP
```

Then open `http://127.0.0.1:8765/ui`. Verification requires a real administrator
session; `/api/health` is the only unauthenticated product check:

```bash
export DIGUA_ADMIN_USERNAME=admin
read -rsp 'Admin password: ' DIGUA_ADMIN_PASSWORD; export DIGUA_ADMIN_PASSWORD
python3 release/scripts/verify_install.py --username "$DIGUA_ADMIN_USERNAME"
unset DIGUA_ADMIN_PASSWORD
```

Qwen `/health` returns HTTP 503 unless the runtime executable, config, library
directory and HBM file all exist. A running HTTP process is not inference
readiness.

## Simulation boundary

`--simulate-root /tmp/digua-clean-install` creates an isolated filesystem,
simulated fstab, rendered units, venv and real identity SQLite database without
mounting a NAS or invoking systemd. Its report always contains
`simulation=true` and `production_verified=false`. It proves orchestration and
rollback-safe file generation only; it does not prove S100P, NAS, models,
services, reboot persistence or inference.
