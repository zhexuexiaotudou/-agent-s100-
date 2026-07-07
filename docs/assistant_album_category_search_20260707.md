# AI Assistant Album Category Search Fix - 2026-07-07

> Superseded boundary note: this implementation was later narrowed by
> `docs/assistant_visual_search_boundary_20260707.md`. Album primary categories
> are no longer the default fallback for natural-language image search; they are
> only valid for explicit album-category queries.
> The verification below is retained as historical evidence for that earlier
> fallback, not as the current target behavior for queries like "找有人的图片".

## Target

Fix the AI assistant path for queries such as "找出 NAS 里有人物的照片" so it returns real NAS photo cards from the organized album index instead of falling back to a read-only file inventory.

## Change

- Backend: `scripts/probes/ai_nas_operator_portal_server.py`
  - Added album-primary category aliases for common photo intents.
  - Added a local album-primary search fallback for empty YOLO/multimodal search results.
  - Queries for people/person photos now map to `cat_album_primary_people` / `人物生活`.
  - Returned results include redacted metadata, media `path_hash`, `/api/media/preview` URL, size, time, and match evidence.
  - Raw NAS paths are not returned; cloud vision is not used.
- Frontend: `web/static/digua_ai_nas_v2.js`
  - Added display labels for `local_ai_album_category_search` and `ai_album_primary_category`.
- Cache bust: `web/ai_nas_desktop_v2.html`
  - Updated static asset version to `20260707-assistant-album-search1`.

## S100P Environment

- Host: `sunrise@ubuntu`
- SSH target: `192.168.127.10`
- Portal: `http://127.0.0.1:8765/ui`
- Portal bind remains `127.0.0.1:8765`.
- Personal root: `/mnt/nas/openclaw/Personal`
- Report root: `/mnt/nas/openclaw/reports/qwen25_ai_nas`

## Verification

Static checks:

```text
py -3 -m py_compile scripts\probes\ai_nas_operator_portal_server.py
node.exe --check web\static\digua_ai_nas_v2.js
python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py
node --check web/static/digua_ai_nas_v2.js
```

Live API check after S100P restart:

```text
query: 找出nas里有人物的照片
assistant_mode: local_ai_album_category_search
retrieval_mode: ai_album_primary_category
album_category: 人物生活
result_count: 16
fallback_inventory_performed: false
first_preview: /api/media/preview?path_hash=32c11025c7a24c2648a646b6b5ce4ae1
preview_status: 200 image/jpeg
```

Equivalent query checks:

```text
找有人的图片 -> local_ai_album_category_search, 人物生活, 16, preview=true
找人物照片 -> local_ai_album_category_search, 人物生活, 16, preview=true
find people photos in nas -> local_ai_album_category_search, 人物生活, 16, preview=true
```

Browser check:

```text
URL: http://127.0.0.1:8765/ui?refresh=20260707-assistant-album-search1#assistant
query: 找出nas里有人物的照片
visible result: 本地 NAS 相册分类索引
visible category: 人物生活
visible result count: 16 个照片
rendered cards: 8
preview URLs: 8
loaded previews during check: 6
file inventory fallback visible: false
console errors/warnings: []
```

## Boundaries

- The result means generic people/person-category photos, not face recognition or identity recognition.
- No raw NAS path is returned to the browser.
- No cloud vision/OCR call is used.
- The assistant shows the first 8 cards; the album page remains the full browsing surface.
