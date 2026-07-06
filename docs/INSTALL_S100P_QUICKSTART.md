# Install S100P Quickstart

Dry-run first:

```bash
bash release/install/install_s100p.sh --dry-run
```

Install with a NAS:

```bash
sudo bash release/install/install_s100p.sh \
  --nas-protocol nfs \
  --nas-host 192.168.1.20 \
  --nas-share /OpenClawWorkspace \
  --mount-point /mnt/nas/openclaw \
  --personal-root /mnt/nas/openclaw/Personal \
  --install-root /opt/digua-ai-nas
```

The installer creates a venv under the install root, writes path-only config,
and keeps services loopback-scoped by default.

