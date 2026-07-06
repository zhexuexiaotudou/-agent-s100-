# AI Space Product Acceptance - 2026-07-06

## Scope

This pass implements and validates the Stage 7 AI Space delivery route:

- live local CLIP image embeddings
- non-identifying person attribute search
- AI Space catalog
- virtual smart classification
- local subtitle extraction
- product job queue API
- product dashboard/status integration

Target environment:

- S100P host: `sunrise@192.168.127.10`
- NAS mount: `169.254.143.37:/OpenClawWorkspace` at `/mnt/nas/openclaw`
- OpenClaw gateway: `openclaw-gateway.service`, active
- Qwen gateway: `qwen25-local-openai-gateway.service`, active
- CLIP model: `ai_nas_clip_vit_base_patch32`, local NAS model directory
- ASR model: `whisper_tiny`, local NAS model directory

## New APIs

- `GET /api/person-attribute/status`
- `POST /api/person-attribute/rebuild`
- `POST /api/person-attribute/search`
- `GET /api/ai-space/status`
- `POST /api/ai-space/rebuild`
- `POST /api/ai-space/search`
- `GET /api/ai-space/assets`
- `GET /api/ai-space/asset/<asset_id>`
- `GET /api/ai-space/facets`
- `GET /api/smart-classification/status`
- `POST /api/smart-classification/categories`
- `GET /api/smart-classification/categories`
- `POST /api/smart-classification/rebuild`
- `GET /api/smart-classification/category/<category_id>/items`
- `POST /api/smart-classification/category/<category_id>/materialize-copy-plan`
- `GET /api/subtitle/status`
- `POST /api/subtitle/extract`
- `GET /api/subtitle/transcript/<asset_id>`
- `POST /api/subtitle/search`
- `POST /api/subtitle/summarize`
- `GET /api/jobs/status`
- `POST /api/jobs/enqueue`
- `GET /api/jobs/<job_id>`
- `GET /api/jobs/recent`
- `POST /api/jobs/cancel`

## UI

- `/ai-space`
- `/smart-classification`
- `/subtitle-extraction`

## Systemd

Installed but not enabled:

- `configs/systemd/digua-ai-index-worker.service`
- `configs/systemd/digua-ai-nightly-index.timer`

The worker/timer are intentionally disabled until real job execution handlers
are attached. The queue API is live and product-smoke covered.

## Commands

```bash
cd /mnt/nas/openclaw

DIGUA_CLIP_BACKEND=clip \
DIGUA_CLIP_MODEL_DIR=/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32 \
DIGUA_CLIP_DEVICE=cpu \
DIGUA_CLIP_REQUIRE_PRODUCTION=1 \
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

DIGUA_ASR_BACKEND=transformers_whisper \
DIGUA_ASR_MODEL_DIR=/mnt/nas/openclaw/models/whisper_tiny \
DIGUA_ASR_REQUIRE_REAL=1 \
python3 gates/stage7_subtitle_extraction_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal

DIGUA_CLIP_BACKEND=clip \
DIGUA_CLIP_MODEL_DIR=/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32 \
DIGUA_CLIP_DEVICE=cpu \
DIGUA_CLIP_REQUIRE_PRODUCTION=1 \
DIGUA_ASR_BACKEND=transformers_whisper \
DIGUA_ASR_MODEL_DIR=/mnt/nas/openclaw/models/whisper_tiny \
DIGUA_ASR_REQUIRE_REAL=1 \
python3 gates/stage7_ai_space_product_delivery_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal --no-rebuild

python3 scripts/product_smoke_test.py \
  --base-url http://127.0.0.1:8765 \
  --report-root /mnt/nas/openclaw/reports/product_delivery
```

## Acceptance Results

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Live CLIP | `ok_stage6_multimodal_live_clip_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage6_multimodal_live_clip_gate.json` |
| Person attribute | `ok_stage6_person_attribute_search_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage6_person_attribute_search_gate.json` |
| AI Space | `ok_stage7_ai_space_catalog_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_ai_space_catalog_gate.json` |
| Smart classification | `ok_stage7_smart_classification_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_smart_classification_gate.json` |
| Subtitle extraction | `ok_stage7_subtitle_extraction_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_subtitle_extraction_gate.json` |
| Stage 7 aggregate | `ok_stage7_ai_space_product_delivery_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_ai_space_product_delivery_gate.json` |
| Product smoke | `ok_product_smoke_test` | `/mnt/nas/openclaw/reports/product_delivery/product_smoke_test_20260706-125500/product_smoke_test.json` |

Final product status:

```text
failed_modules=[]
degraded_modules=[]
warning_count=0
multimodal.embedding_count=17
multimodal.production_semantic_embedding_count=17
person_attribute.person_detection_count=31
person_attribute.attribute_count=31
ai_space.asset_count=220
smart_classification.category_count=12
smart_classification.membership_count=986
subtitle.segment_count=1
cloud_vision_enabled=false
cloud_asr_enabled=false
face_identification_enabled=false
biometric_recognition_enabled=false
sensitive_attribute_inference_enabled=false
```

## Boundaries

- Person attribute search is not face recognition and not identity recognition.
- No age, gender, race, ethnicity, emotion, health, or disability inference is enabled.
- Smart classification creates virtual collections only; it does not directly
  rename or move source files.
- Materialized physical organization is available only through the separate
  Auto Organizer plan/dry-run/approve/execute/rollback contract.
- Uncontrolled move/rename, delete, overwrite, recursive operation, Qwen
  autonomous execution, and cloud-derived private writes remain disabled.
- Cloud vision, cloud OCR, and cloud ASR remain disabled.
- The ASR demo transcript uses synthetic audio generated by
  `scripts/product_demo_seed_data.py`; it validates local ASR mechanics, SRT/VTT
  output, and indexing, but production demos should use real user-provided media.

## External Wording

Allowed:

```text
Digua AI-NAS now supports local AI Space organization on S100P: local CLIP image
embeddings, local non-identifying person attribute search, local subtitle
extraction, virtual smart categories, and evidence-referenced results with
path redaction.
```

Forbidden:

```text
face recognition; family member identity recognition; age/gender/race/emotion
inference; cloud vision or cloud ASR; arbitrary or automatic delete/move/rename;
complete replacement of a commercial NAS OS.
```
