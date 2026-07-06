# Release Upgrade And Rollback

Dry-run:

```bash
bash release/install/upgrade_s100p.sh --dry-run
bash release/install/uninstall_s100p.sh --dry-run
```

Upgrade apply creates a config/runtime backup before replacing files. Rollback
restores the previous install root and leaves NAS Personal data untouched.
Uninstall disables services and removes only the install root; it does not
remove NAS data.

