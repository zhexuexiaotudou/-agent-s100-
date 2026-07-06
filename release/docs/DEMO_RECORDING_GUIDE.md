# Demo Recording Guide

Use the Stage 10 gate:

```bash
python3 gates/stage10_release_product_delivery_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal \
  --base-url http://127.0.0.1:8765
```

If YOLO indexes assets but returns zero boxes, record the explicit blocker and
do not claim bbox detection.

