# Digua AI-NAS S100P Release

This release directory packages the S100P + NAS deployment surface for Digua
AI-NAS. It is designed for a user who owns an RDK S100P, a normal NAS, and a PC
for first-time configuration.

The release package provides:

- preflight checks for S100P, Python, systemd, ports, NAS reachability, and disk
  space;
- NAS mount configuration helpers for NFS, SMB/CIFS, and local directory mode;
- model path verification without bundling model weights;
- loopback-scoped OpenClaw/Qwen/index-worker systemd units;
- first-run wizard, product smoke, demo corpus gate runner, support bundle
  collection, reset, upgrade, rollback, and uninstall commands.

## Safe Defaults

- No public Gateway exposure.
- No bundled model weights.
- No bundled third-party images.
- NAS access is scoped to a configured mount and Personal root.
- Delete and overwrite remain disabled by default.
- Controlled move/rename requires Auto Organizer plan, approval, execution, and
  rollback evidence.
- Qwen has no autonomous file-execution authority.

## Quickstart

```bash
sudo -E python3 release/install/deploy_wizard.py
```

For repeatable CI, supply a JSON answer file and an isolated simulation root.
Simulation is always labeled non-production:

```bash
sudo -E python3 release/install/deploy_wizard.py \
  --config deploy.json --non-interactive --yes \
  --simulate-root /tmp/digua-clean-install
```

See `release/docs/INSTALL_S100P.md` for package transfer, NAS credentials,
model/runtime inputs, authenticated acceptance and rollback.
