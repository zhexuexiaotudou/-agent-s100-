# Upload Auto Classify Runbook

## Preconditions

- Gateway runs with `--personal-root /mnt/nas/openclaw/Personal`.
- The authenticated user has write permission for `Uploads` and read permission for relevant photo roots.
- Product feature flags keep destructive actions disabled.

## API Smoke

```bash
python3 scripts/product_demo_seed_data.py --root /mnt/nas/openclaw/demo_data
python3 gates/stage7_media_album_nonzero_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
python3 gates/stage7_upload_auto_classify_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
python3 gates/stage7_chinese_smart_naming_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
python3 gates/stage7_smart_album_classification_delivery_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
```

## Expected Evidence

- Media photo count is nonzero.
- Upload result contains `asset_id`, queue jobs, smart category hits, and Chinese smart naming metadata.
- `人物照片` and `白色上衣` are both hit for `white_shirt_person.jpg`.
- API responses do not return raw absolute paths.
- Original file is not renamed or moved.

## Rollback

No destructive action is executed by this flow. If a generated upload fixture must be removed after manual review, delete only the test upload directory with explicit operator approval.
