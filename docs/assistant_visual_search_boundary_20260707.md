# AI Assistant Visual Search Boundary - 2026-07-07

## Decision

Natural-language image search must not use album primary categories as the default retrieval path.

The correct default path is:

1. Query intent parsing in the assistant/router.
2. YOLO object index for supported object labels such as person, car, cat, dog.
3. Local multimodal semantic retrieval using the image/text embedding stack.
4. Return an honest empty visual-search result if both indexes miss.

Album primary categories are allowed only when the user explicitly asks for an album category or category-filtered view, for example "按相册分类找人物生活" or "人物生活分类里的照片".

## Why

Album categories are coarse organization labels. They are useful for browsing and filtering, but they are not evidence that the photo matches a natural-language description. Queries such as "找有人的图片", "白色上衣的人", "海边红色车", or "文档截图里有合同" require visual/object/attribute evidence, not a broad album bucket.

## Implementation

- `scripts/probes/ai_nas_operator_portal_server.py`
  - Added `AI_ALBUM_EXPLICIT_CATEGORY_QUERY_TERMS`.
  - `_copilot_album_category_for_intent()` now requires an explicit album-category request.
  - Image/video searches no longer fall back to read-only file inventory when visual indexes miss.
  - YOLO empty results no longer terminate search; the assistant continues to multimodal retrieval.
  - Natural-language image-search cards must resolve to a current media-album image preview; stale multimodal rows or fixture rows without a resolvable preview are filtered out.
  - Assistant result enrichment now checks the media album `path_hash` resolver before the storage hash resolver, so 32-character album hashes use `/api/media/preview`.
- `src/yolo_index/labels.py`
  - Replaced mojibake Chinese aliases with Unicode-safe aliases so Chinese queries such as "找有人的图片" map to the YOLO `person` label.
- `src/yolo_index/backend.py`
  - Added S100P `ImageUtils` ROI log parsing for lines such as `target type: person` and `roi.type: person, x_offset...`.
  - The parser still prefers official `det rect... score...` lines when present, and only falls back to ROI logs when score-bearing detection lines are absent.
- `tests/test_yolo_index_core.py`
  - Added regression coverage for the S100P ROI log format so detected `person`, `bus`, and `stop sign` boxes are not silently dropped.
- `src/multimodal_search/query_planner.py`
  - Added Chinese person terms to the visual query text so CLIP/SigLIP-style retrieval can use `person/people/portrait` semantics when a production model is configured.
- `src/multimodal_search/hybrid_retriever.py`
  - Catches image-embedding vector-dimension/runtime failures and returns degraded metadata/FTS results instead of closing the HTTP request.
- `web/static/digua_ai_nas_v2.js`
  - Assistant capability copy now says image search uses YOLO first, then local multimodal semantic retrieval.
- `web/ai_nas_desktop_v2.html`
  - Cache bust updated to `20260707-visual-search-boundary1`.

## Verification

Environment:

```text
Host: sunrise@ubuntu
SSH target: 192.168.127.10
Portal: http://127.0.0.1:8765/ui
Portal bind: 127.0.0.1:8765
Personal root: /mnt/nas/openclaw/Personal
Report root: /mnt/nas/openclaw/reports/qwen25_ai_nas
```

Static checks:

```text
py -3 -m py_compile scripts\probes\ai_nas_operator_portal_server.py src\yolo_index\labels.py src\multimodal_search\query_planner.py src\multimodal_search\hybrid_retriever.py
python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py src/yolo_index/labels.py src/multimodal_search/query_planner.py src/multimodal_search/hybrid_retriever.py
```

Live API checks after S100P restart:

```text
query: 找有人的图片
assistant_mode: local_multimodal_search
retrieval_mode: fts_first_plus_image_embedding
labels: person
result_count: 8
album_category: null
fallback_inventory_performed: false
degraded: true
degraded_reason: image_embedding_search_failed:ValueError
first_result: white_shirt_person.jpg
```

```text
query: 按相册分类找人物生活的照片
assistant_mode: local_ai_album_category_search
retrieval_mode: ai_album_primary_category
labels: person
result_count: 16
album_category: 人物生活
fallback_inventory_performed: false
degraded: false
first_result: 人物生活照片 1
```

Direct multimodal route no longer closes the HTTP connection on the current vector mismatch:

```text
POST /api/multimodal-search/query {"query":"找有人的图片","top_k":5}
ok: true
result_count: 5
degraded: true
degraded_reason: image_embedding_search_failed:ValueError
```

Follow-up live check after requiring real media previews:

```text
query: 找有人的图片
assistant_mode: local_multimodal_search
retrieval_mode: fts_first_plus_image_embedding
result_count: 0
album_category: null
fallback_inventory_performed: false
degraded: true
degraded_reason: image_embedding_search_failed:ValueError
invalid_preview_cards_shown: 0
```

The previous stale results such as `white_shirt_person.jpg` and
`red_shirt_person.jpg` were filtered because they did not resolve to a current
media-album preview.

Explicit album-category search still returns real album cards:

```text
query: 按相册分类找人物生活的照片
assistant_mode: local_ai_album_category_search
retrieval_mode: ai_album_primary_category
result_count: 16
album_category: 人物生活
invalid_preview_cards_shown: 0
first_result: picsum_random_058_id_1008.jpg
first_preview: /api/media/preview?path_hash=32c11025c7a24c2648a646b6b5ce4ae1
preview_status: 200 image/jpeg
```

Superseded live gap before the 2026-07-07 YOLO parser fix:

```text
/api/yolo-index/status: indexed_count=1, detection_count=0, degraded_reason=no_yolo_detections_indexed
/api/multimodal-search/status: current image model vector_dim=16, existing vector store dimension=512
```

At that point the routing boundary was correct, but natural-language visual search still needed one of these follow-up gates:

1. rebuild and verify the YOLO/person-attribute index on the current 101-photo demo set, or
2. restore/rebuild a consistent 512-d CLIP/SigLIP image-text index for semantic visual queries.

## 2026-07-07 YOLO Closure Update

Root cause:

```text
The S100P YOLO runtime was deployed and producing detection evidence, but the
active parser only recognized `det rect: ... det type: ... score: ...`.
The live S100P logs for the current route emitted `target type: ...` and
`roi.type: ..., x_offset: ... y_offset: ... width: ... height: ...`, so valid
boxes were not inserted into `mm_yolo_detections`.
```

Code verification:

```text
py -3 -m unittest -v tests.test_yolo_index_core
python3 -m unittest -v tests.test_yolo_index_core
python3 -m py_compile src/yolo_index/backend.py scripts/probes/ai_nas_operator_portal_server.py
```

Live rebuild on S100P:

```text
POST /api/yolo-index/rebuild
scope: 16 real current album candidate images from /mnt/nas/openclaw/Personal
run_id: yolo_run_53f36f4ff7a04689
asset_count: 16
detection_count: 27
errors: 0
backend: s100p_tros_dnn_node_example
runtime_target: s100p_bpu_hbm
cloud_used: false
raw_path_returned: false
elapsed_ms: 490814.855
```

Current live status:

```text
GET /api/yolo-index/status
indexed_count: 16
detection_count: 27
label_counts: person=17, kite=4, bicycle=1, cell phone=1, chair=1, potted plant=1, snowboard=1, vase=1
degraded: false
```

Person attribute rebuild:

```text
POST /api/person-attribute/rebuild
inserted: 17
skipped_no_path: 0
person_detection_count: 17
attribute_count: 17
face_identification_enabled: false
biometric_recognition_enabled: false
sensitive_attribute_inference_enabled: false
cloud_used: false
raw_path_returned: false
degraded: false
```

Assistant API acceptance:

```text
POST /api/copilot/chat {"message":"找有人的图片"}
assistant_mode: local_yolo_search
route: local_yolo_search
labels: person
result_count: 8
degraded: false
first_result: pexels-franco-monsalvo-252430633-38454765.jpg
first_match: 人 91.8%
first_preview: /api/storage/preview-by-hash?path_hash=290da76f98a7434bde973aa1547f6e144bc99a9780f10677d9504be8d61e5ead
preview_status: 200 image/jpeg
cloud_used: false
qwen_execution_authority: false
raw_path_leaked: false
```

Web UI acceptance:

```text
URL: http://127.0.0.1:8765/ui#assistant
Flow: AI 助手 -> 输入“找有人的图片” -> 发送
Rendered result: 本地检索返回, 8 个照片, 未上云
Preview images: 8/8 loaded with non-zero naturalWidth/naturalHeight
Console errors/warnings: 0 relevant entries
```

Updated boundary:

```text
The generic "找有人的图片" flow is now closed through real S100P YOLO object detections and real NAS preview cards.
Fine-grained semantic queries such as "找穿白色上衣的人" still require the B-016 region/person clothing attribute gate or a consistent production image-text embedding index.
Full 101-photo YOLO coverage should be implemented as an incremental/background job because the S100P official ROS example route took about 491 seconds for 16 images.
```

## Expected Behavior

For natural-language image search:

```text
找有人的图片
```

The assistant should use `local_yolo_search` when YOLO has person detections, otherwise `local_multimodal_search`. It should not return `local_ai_album_category_search` unless the query explicitly asks for an album category.

If no visual index result is available, it should say the object/semantic index did not return matching images. It should not list top-level folders as if they were photo results.

For explicit album-category filtering:

```text
按相册分类找人物生活的照片
```

The assistant may use `local_ai_album_category_search`.

## Boundaries

- "person" means generic person detection/category evidence, not face recognition or identity recognition.
- Fine-grained queries such as clothing color require B-016 style region-level person/clothing/object attributes; album category is not sufficient.
- No raw NAS path is returned.
- No cloud vision call is used.
