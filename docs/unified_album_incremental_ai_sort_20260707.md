# 2026-07-07 unified album incremental AI sort acceptance

## Scope

This record covers the S100P NAS web UI album fix requested on 2026-07-07:

- Keep only one visible album entry named "相册"; remove the separate visible "AI 相册" entry.
- The album page shows all indexed NAS images in the AI album material scope.
- New images are incrementally indexed and synced into AI Space; already indexed images are skipped.
- The album page uses local AI classification chips in the same page.
- Photo cards do not show filenames. They show preview, size, time, and local category tags.
- Preview access stays behind the authenticated `/api/media/preview?path_hash=...` endpoint and does not return raw paths.

## Environment

- Host: S100P, SSH user `sunrise`, board IP `192.168.127.10`.
- Web URL through local tunnel: `http://127.0.0.1:8765/ui?refresh=20260707-unified-album3#media`.
- Portal process after restart: `python3 scripts/probes/ai_nas_operator_portal_server.py --bind 127.0.0.1 --port 8765 ...`.
- Personal root: `/mnt/nas/openclaw/Personal`.
- Report root: `/mnt/nas/openclaw/reports/qwen25_ai_nas`.

## Changes

- `web/static/digua_ai_nas_v2.js`
  - Removed the visible navigation/page route for separate AI album.
  - Changed `/ai-album` route to the unified `media` page for compatibility.
  - Album page now fetches `/api/media/photos?limit=500` and renders up to 500 photos.
  - AI Space assets are fetched with `/api/ai-space/assets?limit=10000`.
  - Photo list loading is no longer blocked by optional AI classification endpoint failures.
  - Photo cards hide filenames and show size, time, preview, and category tags.

- `scripts/probes/ai_nas_operator_portal_server.py`
  - Added `POST /api/ai-album/auto-organize` incremental indexing/sync path.
  - Passed query payload through GET `/api/ai-space/*`, so `limit=10000` is honored.
  - Fixed `Content-Disposition` for non-ASCII filenames by using ASCII fallback plus `filename*=UTF-8''...`.

- `scripts/probes/ai_nas_media.py`
  - Added indexed-row access for internal sync.
  - Added path-hash lookup for authenticated media preview.

## Validation

Local checks:

- `python -m py_compile scripts/probes/ai_nas_media.py scripts/probes/ai_nas_operator_portal_server.py`: passed.
- `node --check web/static/digua_ai_nas_v2.js`: passed.
- Fixed-string checks for visible legacy labels:
  - `AI 相册`: no match in active UI bundle.
  - `相册列表`: no match in active UI bundle.

S100P API checks through `http://127.0.0.1:8765`:

- `/api/health`: HTTP 200.
- `POST /api/ai-album/auto-organize`:
  - `changed=false`
  - `view_rebuilt=false`
  - `media_images_indexed=132`
  - `ai_space_images_after=155`
- `/api/media/photos?limit=500`: 132 photos.
- `/api/ai-space/assets?limit=10000`: 429 assets, including 155 image assets.
- First 12 `/api/media/preview?path_hash=...` requests: 12/12 HTTP 200, including Chinese-filename images that previously closed the connection.

Browser acceptance:

- In-app browser opened `http://127.0.0.1:8765/ui?refresh=20260707-unified-album2#media`; after the final `待整理` filtering patch, `/ui` serves `20260707-unified-album3`.
- Visible page title: `相册`.
- Card count in DOM: 132.
- Category chip count after final filtering: 16 including the `全部` chip.
- Example chips after final filtering: `全部 132`, `待整理 29`, `人物照片 27`, `票据发票 18`, `白色上衣 16`, `宠物动物 15`, `书本文具 15`, `截图资料 12`.
- Visible text did not contain `AI 相册`, `相册列表`, or filename patterns such as `IMG_`, `.png`, `.jpg`, `receipt_001`, `screenshot_001`, `contract_001`.
- First 24 visible thumbnail images loaded as blob previews.
- Cards show size and time, for example `121 KB · 2026/7/6 22:35:27`.

## Boundaries

- This implementation performs virtual AI classification and persistent index sync. It does not physically move, rename, delete, or overwrite user files.
- Follow-up manual cleanup on 2026-07-07 adds an explicit user-triggered soft-delete path to `.trash`; it is not part of automatic AI sorting and still does not allow Qwen autonomous delete.
- Cloud use remains disabled for this path.
- Raw filesystem paths are not returned to the browser for previews.
- `qwen25-local-openai-gateway.service` being inactive does not block this album page path; album indexing and preview were validated without Qwen execution.
