# Install S100P Advanced

Advanced operators can run each step separately:

```bash
bash release/install/preflight_check.sh --mount-point /mnt/nas/openclaw
bash release/install/configure_nas_mount.sh --dry-run --nas-protocol nfs --nas-host 192.168.1.20 --nas-share /OpenClawWorkspace
bash release/install/configure_models.sh --dry-run
bash release/install/install_systemd_units.sh --dry-run --mode user
python3 release/install/first_run_wizard.py --nas-mount /mnt/nas/openclaw --personal-root /mnt/nas/openclaw/Personal
```

Use `--apply` only after reviewing the JSON plan. Do not expose the gateway to
the public internet.

