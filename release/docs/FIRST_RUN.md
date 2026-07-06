# First Run

After installation:

```bash
python3 release/install/first_run_wizard.py \
  --nas-mount /mnt/nas/openclaw \
  --personal-root /mnt/nas/openclaw/Personal \
  --base-url http://127.0.0.1:8765
```

The wizard verifies NAS/Personal roots, model paths, product smoke, admin token
creation, and optional demo corpus setup.

