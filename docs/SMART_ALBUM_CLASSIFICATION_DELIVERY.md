# Smart Album Classification Delivery

Status: implemented for Stage 7 live acceptance.

## S100P Acceptance - 2026-07-06

Target environment:

- S100P host: `sunrise@192.168.127.10`
- NAS mount: `/mnt/nas/openclaw`
- Personal root: `/mnt/nas/openclaw/Personal`
- Portal: `http://127.0.0.1:8765`
- CLIP model: `/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32`
- YOLO runtime: `s100p_bpu_hbm`

Accepted verdicts:

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Media album nonzero | `ok_stage7_media_album_nonzero_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_media_album_nonzero_gate.json` |
| Upload auto-classify | `ok_stage7_upload_auto_classify_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_upload_auto_classify_gate.json` |
| Chinese smart naming | `ok_stage7_chinese_smart_naming_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_chinese_smart_naming_gate.json` |
| Aggregate delivery | `ok_stage7_smart_album_classification_delivery_gate` | `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_smart_album_classification_delivery_gate.json` |
| Product smoke | `ok_product_smoke_test` | `/mnt/nas/openclaw/reports/product_delivery/product_smoke_test_20260706-142946/product_smoke_test.json` |

Live smoke summary:

```text
failure_count=0
warning_count=0
production_ready=true
yolo_runtime_target=s100p_bpu_hbm
yolo_detection_count=66
ai_space_asset_count=13
smart_category_count=29
smart_name_count=43
```

Upload acceptance sample:

```text
asset_id=mm_fb98a8eb7d323bbbdea2f181
category_hits=人物照片, 白色上衣
display_name_zh=人物照片_白色上衣_照片_20260706_429
suggested_filename_zh=人物照片_白色上衣_照片_20260706_429.jpg
physical_file_renamed=false
cloud_used=false
raw_path_returned=false
```

Operational note: the Chinese naming gate uses four bounded demo files for
semantic coverage, while final smoke restores the controlled
`/mnt/nas/openclaw/yolo_v2_fixture` YOLO baseline so product-level status keeps
real S100P BPU detections and person-attribute rows. This does not move,
rename, delete, or overwrite user NAS files.

## Product Flow

1. `POST /api/media/upload` saves an image under the authenticated user's Personal NAS space.
2. The upload event records queue jobs for media upload, multimodal rebuild, YOLO index, person-attribute rebuild, smart classification, smart naming, and AI Space rebuild.
3. `MediaCenter` indexes the saved image into the media album database and exposes only redacted fields such as `asset_id`, `path_hash`, and `title_redacted`.
4. Smart classification creates virtual album memberships. It does not move, rename, delete, or overwrite source files.
5. Smart naming writes `display_name_zh` and `suggested_filename_zh` into `smart_asset_names`.
6. AI Space surfaces the Chinese display name and suggested filename together with categories, labels, and evidence refs.

## APIs

- `GET /api/media/status`
- `POST /api/media/index`
- `GET /api/media/photos`
- `GET /api/media/timeline`
- `GET /api/media/albums`
- `GET /api/media/duplicates`
- `POST /api/media/upload`
- `POST /api/smart-naming/generate`
- `POST /api/smart-naming/batch-generate`
- `GET /api/smart-naming/item/<asset_id>`

## Gates

- `gates/stage7_media_album_nonzero_gate.py`
- `gates/stage7_upload_auto_classify_gate.py`
- `gates/stage7_chinese_smart_naming_gate.py`
- `gates/stage7_smart_album_classification_delivery_gate.py`

## Current Boundary

- Physical organization is a Copy Plan only.
- Copy execution still requires Harness preview, dry-run, typed approval, execute, and rollback manifest.
- No face recognition, identity recognition, age/gender/race/emotion/health inference, or cloud person recognition is enabled.
