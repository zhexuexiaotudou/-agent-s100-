# Troubleshooting

Run preflight, verify install, product smoke, then collect a support bundle:

```bash
bash release/install/preflight_check.sh
python3 release/scripts/verify_install.py
python3 scripts/product_smoke_test.py --base-url http://127.0.0.1:8765
python3 release/scripts/collect_support_bundle.py
```

