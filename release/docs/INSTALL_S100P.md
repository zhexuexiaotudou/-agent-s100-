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

## 2. Prepare NAS and model inputs

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

## 3. Run the guide

System service mode is the recommended appliance mode. Run:

```bash
sudo -E python3 release/install/deploy_wizard.py
```

The guide selects the original sudo user (normally `sunrise`) as the
unprivileged service account. systemd runs the portal, Qwen gateway and worker
as that user, and NAS/report write tests are performed with the same identity;
root-only write success is not accepted.

The administrator password is read with a hidden prompt, passed only through a
process environment variable, and is never included in a command, report, unit
file, or repository file. The guide performs these gates in order:

1. strict S100P/BPU/systemd preflight;
2. NAS reachability and actual NFS/CIFS mount with a managed `/etc/fstab` block;
3. mounted source/type and writable Personal-root verification;
4. required Qwen runtime/model path verification and environment generation;
5. application copy, isolated venv and optional wheelhouse install;
6. rendered loopback-only systemd units and service start;
7. real identity-store administrator bootstrap and authenticated verification.

The mount helper backs up `/etc/fstab` before replacing only the block between
`# BEGIN DIGUA-AI-NAS` and `# END DIGUA-AI-NAS`. A local directory is rejected
as a NAS unless `--allow-local-storage` is explicitly supplied.

For an offline Python dependency install, place compatible S100P wheels in a
directory and set `wheelhouse` in the guide JSON config. The installer then uses
`pip --no-index --find-links`. Vendor BPU runtimes remain device-managed.
Start from `release/configs/deploy.example.json`; keep passwords out of that
file and provide them only through the configured password environment variable.

## 4. Access and verify

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
