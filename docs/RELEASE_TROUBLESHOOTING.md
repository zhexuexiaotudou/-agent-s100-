# Release Troubleshooting

Start with:

```bash
bash release/install/preflight_check.sh --mount-point /mnt/nas/openclaw
python3 release/scripts/verify_install.py --base-url http://127.0.0.1:8765
python3 scripts/product_smoke_test.py --base-url http://127.0.0.1:8765 --report-root /mnt/nas/openclaw/reports/product_delivery
python3 release/scripts/collect_support_bundle.py --out /mnt/nas/openclaw/reports/release_support.zip
```

Common blockers:

- `arch_not_aarch64`: the installer is not running on S100P.
- `systemd_user_unavailable`: enable user lingering or run in system mode.
- `disk_free_below_1g`: free NAS or install-root space.
- model paths missing: configure model env vars; do not copy weights into repo.
- YOLO zero boxes: record `yolo_demo_images_not_detectable`; do not fake
  detection evidence.

