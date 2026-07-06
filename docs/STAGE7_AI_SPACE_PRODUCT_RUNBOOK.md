# Stage 7 AI Space Product Runbook

Run on S100P:

```bash
cd /mnt/nas/openclaw

python3 gates/stage6_multimodal_live_clip_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal

python3 gates/stage6_person_attribute_search_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal

python3 gates/stage7_ai_space_catalog_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal

python3 gates/stage7_smart_classification_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal

python3 gates/stage7_subtitle_extraction_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal

python3 gates/stage7_ai_space_product_delivery_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
```

Expected blocker if no local ASR model is installed:

```text
stage7_subtitle_extraction_gate -> blocked_stage7_subtitle_extraction_gate
```
