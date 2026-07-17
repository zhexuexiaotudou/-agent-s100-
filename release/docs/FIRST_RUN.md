# First Run

The deployment guide runs first-run automatically after service installation.
It creates the initial administrator in the same
`reports/qwen25_ai_nas/identity.sqlite3` used by the portal, logs in to obtain a
short-lived session, and passes that session only in memory to the authenticated
product smoke.

There is no static `admin_token` file and no default password. To rerun the
bootstrap/verification step manually:

```bash
read -rsp 'Admin password: ' DIGUA_ADMIN_PASSWORD; export DIGUA_ADMIN_PASSWORD
python3 release/install/first_run_wizard.py \
  --install-root /opt/digua-ai-nas \
  --app-root /opt/digua-ai-nas/app \
  --nas-mount /mnt/nas/openclaw \
  --personal-root /mnt/nas/openclaw/Personal \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --admin-username admin
unset DIGUA_ADMIN_PASSWORD
```

If the username already exists, the wizard verifies the supplied password; it
does not reset or replace the account.
