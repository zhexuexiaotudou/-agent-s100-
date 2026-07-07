# 2026-07-07 album Picsum replacement acceptance

## Request

Replace the existing 132 album images with 100 randomly selected free image assets stored on the NAS.

## Source

- Source site: Lorem Picsum, `https://picsum.photos/`.
- Selection method: fetch `/v2/list` pages, randomly sample image IDs, then download stable 1024x768 JPEG URLs via `/id/{image}/1024/768.jpg`.
- Source license context: Picsum uses Unsplash-backed images, and Unsplash's license page allows free image downloads and use. Keep the downloaded image manifest as provenance for demo/test usage.

## Execution

Environment:

- Host: S100P `ubuntu`.
- SSH user: `sunrise`.
- Board IP: `192.168.127.10`.
- NAS root: `/mnt/nas/openclaw`.
- Portal: `http://127.0.0.1:8765`.
- `openclaw-gateway.service`: active.
- `qwen25-local-openai-gateway.service`: inactive; not required for this media replacement task.

Source/destination paths:

- Old-image manifest:
  `/mnt/nas/openclaw/reports/qwen25_ai_nas/album_replacement_20260707T070456Z/deleted_old_132_manifest.json`
- Delete result:
  `/mnt/nas/openclaw/reports/qwen25_ai_nas/album_replacement_20260707T070456Z/delete_result.json`
- New-image manifest:
  `/mnt/nas/openclaw/reports/qwen25_ai_nas/album_replacement_20260707T070456Z/downloaded_picsum_100_manifest.json`
- New image directory:
  `/mnt/nas/openclaw/Personal/Photos/picsum_replacement_20260707`

Guardrails:

- Deletion was limited to the 132 image rows currently indexed in `reports/qwen25_ai_nas/media.sqlite3`.
- Each old path was verified to be inside the controlled album material scope before deletion, including `Personal/AI整理`.
- A SHA256/path manifest was written before unlinking files.
- Project source, reports, model files, and other NAS artifacts were not targeted.
- Stale asset rows were removed from media, multimodal, AI Space, smart classification, YOLO, person attribute, and subtitle runtime DBs by asset ID.

## Results

Physical file replacement:

- Old manifest count: 132.
- Old paths still existing after deletion: 0.
- New manifest count: 100.
- New paths existing after download: 100.
- Target directory JPEG count: 100.

Index and API validation:

- `POST /api/ai-album/auto-organize` with `force=true`: `ok=true`.
- Auto organize result:
  - `changed=true`
  - `view_rebuilt=true`
  - `media_images_indexed=100`
  - `multimodal_images=122`
  - `ai_space_images_before=23`
  - `ai_space_images_after=123`
- `/api/media/photos?limit=500`: 100 photos.
- Old filename pattern matches in media DB: 0.
- First 12 `/api/media/preview?path_hash=...` requests: 12/12 HTTP 200.

Browser validation:

- URL opened: `http://127.0.0.1:8765/ui?refresh=20260707-picsum-replacement#media`.
- Visible album card count: 100.
- Visible chips: `全部 100`, `待整理 100`.
- Visible page did not contain `AI 相册`, `相册列表`, old file names, or the previous 132 count.
- First 12 visible cards had preview URLs and loaded previews.
- Cards still show only size/time/category text, not filenames.

## Boundary

The random Picsum images have no local object-detection or human-curated category evidence in this run. The album therefore honestly shows `待整理 100` rather than fabricating content-based categories.
