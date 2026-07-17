# Update and Rollback

Preview every operation first. Backups contain the application installation;
NAS Personal data is never copied, removed or rolled back by these commands.

```bash
bash release/install/upgrade_s100p.sh --dry-run --install-root /opt/digua-ai-nas
sudo bash release/install/upgrade_s100p.sh --apply --install-root /opt/digua-ai-nas
```

To replace the installation from an already verified extracted tree:

```bash
sudo bash release/install/upgrade_s100p.sh --apply \
  --install-root /opt/digua-ai-nas \
  --source-root /tmp/digua-new-install
```

The old install is preserved. Roll back with the implemented `--rollback-from`
path shown in the upgrade report:

```bash
sudo bash release/install/upgrade_s100p.sh --apply \
  --install-root /opt/digua-ai-nas \
  --rollback-from /opt/digua-ai-nas_backup_TIMESTAMP
```

Rollback stops the three current services, preserves the failed installation,
restores a copy of the selected backup, and starts the services. Run
authenticated verification afterward; service restart alone is not acceptance.

Uninstall recognizes only the three current services and rejects unsafe roots:

```bash
bash release/install/uninstall_s100p.sh --dry-run --install-root /opt/digua-ai-nas
sudo bash release/install/uninstall_s100p.sh --apply --install-root /opt/digua-ai-nas
```
