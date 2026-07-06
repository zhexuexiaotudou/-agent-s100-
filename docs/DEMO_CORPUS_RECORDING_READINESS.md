# Demo Corpus Recording Readiness

Run on S100P after copying the latest repo contents to `/mnt/nas/openclaw`:

```bash
export DIGUA_DEMO_AUTH_TOKEN="$(cat /tmp/stage9_demo_token.txt)"
python3 gates/stage10_demo_corpus_recording_readiness_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal \
  --base-url http://127.0.0.1:8765 \
  --qwen-url http://127.0.0.1:18080/health \
  --timeout 240
```

The gate aggregates license, corpus download/generated-file verification, live
index status, authenticated golden queries, Auto Organizer AI-index flow, and
YOLO bbox readiness. If the real S100P YOLO backend indexes assets but current
demo images still produce zero boxes, the gate records
`recording_blocker=yolo_demo_images_not_detectable` instead of pretending that
bboxes exist.

