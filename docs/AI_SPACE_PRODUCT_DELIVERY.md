# AI Space Product Delivery

AI Space is the unified catalog layer for photos, video, audio, documents, and
other NAS assets. It reuses local multimodal, YOLO, person-attribute, subtitle,
and smart-classification evidence.

API:

- `GET /api/ai-space/status`
- `POST /api/ai-space/rebuild`
- `POST /api/ai-space/search`
- `GET /api/ai-space/assets`
- `GET /api/ai-space/asset/<asset_id>`
- `GET /api/ai-space/facets`

UI:

- `/ai-space`

Boundary:

- symbolic summaries are not VLM captions
- no raw absolute paths are returned
- cloud vision remains disabled

Gate:

```bash
python3 gates/stage7_ai_space_catalog_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
```
