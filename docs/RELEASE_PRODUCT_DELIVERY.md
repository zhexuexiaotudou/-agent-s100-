# Release Product Delivery

Stage 10 adds a one-stop S100P release package under `release/` plus
`scripts/build_release.py`.

## Package Command

```bash
python3 scripts/build_release.py --version 0.1.0 --out dist/
```

Outputs:

- `dist/digua-ai-nas-s100p-0.1.0.tar.gz`
- `dist/digua-ai-nas-s100p-0.1.0.zip`
- `dist/digua-ai-nas-s100p-0.1.0.sha256`
- `dist/release_manifest.json`

The package excludes model weights, third-party images, private user data,
runtime DB files, secrets, and downloaded corpus files.

## Final Gate

```bash
python3 gates/stage10_release_product_delivery_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal \
  --base-url http://127.0.0.1:8765 \
  --timeout 240
```

