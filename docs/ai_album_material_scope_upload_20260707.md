# AI Album material scope and upload fix, 2026-07-07

## Scope

This note records the 2026-07-07 S100P-side fix for two user-facing gaps:

- NAS demo/test images, videos, and documents outside project development artifacts must be included in the AI assistant material-inventory scope.
- The Web UI album surfaces need a visible image-upload entry.

The change keeps destructive organization actions out of scope. Auto Organizer
still uses its own allowlisted Personal source roots and controlled approval
flow for physical move/rename operations.

## Implementation

Updated files:

- `scripts/probes/ai_nas_operator_portal_server.py`
- `web/static/digua_ai_nas_v2.js`

Server additions:

- Added an AI Album material scope allowlist:
  - Personal material roots: `Photos`, `Movies`, `Documents`, `DemoDocs`,
    `Uploads`, `Inbox`, `Collections`, `Sorted`, `AI整理`.
  - NAS demo/test roots: `demo_data`, `yolo_v2_fixture`, `documents`,
    `photos`, `robot_datasets`.
  - Demo corpus material roots: `demo_corpus/samples_generated`,
    `demo_corpus/downloaded`.
- Explicitly excludes project artifacts such as `src`, `scripts`, `docs`,
  `reports`, `logs`, `models`, `runtimes`, `tmp`, `release`, `gates`,
  `tests`, and hidden/snapshot/recycle roots.
- Added `GET /api/ai-album/scope`.
- Added `POST /api/ai-album/rebuild`.
- Added a read-only material inventory path used by AI assistant fallback
  inventory responses.
- Extended media preview authorization so indexed allowlisted demo/test images
  can be previewed without exposing raw paths.

UI additions:

- Added an `上传图片` button to both `相册` and `AI 相册`.
- The button opens an image file picker and uploads through existing
  `POST /api/media/upload`.
- Uploads are saved under Personal `Uploads` with `auto_process=false`, then
  the UI refreshes current album and AI Album state.
- Web refresh buttons are read-only refreshes. Full index rebuild remains a
  backend/API operation because synchronous CLIP/YOLO rebuilds are too slow for
  a foreground page button on S100P.

## S100P validation

Environment:

- Host: `sunrise@192.168.127.10`
- Observed remote user/host from SSH command: `msizhexu@MSI`
- Gateway bind: `127.0.0.1:8765`
- Personal root: `/mnt/nas/openclaw/Personal`
- Report root: `/mnt/nas/openclaw/reports/qwen25_ai_nas`
- Services after deployment:
  - `openclaw-gateway.service`: `active`
  - `qwen25-local-openai-gateway.service`: `active`

Checks:

```text
python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py
node --check web/static/digua_ai_nas_v2.js
curl http://127.0.0.1:8765/api/health -> HTTP 200
```

`GET /api/ai-album/scope` with admin auth returned:

```text
ok=True
included_root_count=16
included=[
  Personal/Photos, Personal/Movies, Personal/Documents, Personal/DemoDocs,
  Personal/Uploads, Personal/Inbox, Personal/Collections, Personal/Sorted,
  Personal/AI整理, demo_data, yolo_v2_fixture, documents, photos,
  robot_datasets, demo_corpus/samples_generated, demo_corpus/downloaded
]
excluded_policy contains src=True
raw_path_returned=False
```

AI assistant inventory query:

```text
message=查询 NAS 里面的图片、视频和文档有哪些，做一个盘点
assistant_mode=local_storage_inventory
organizer_scope=demo_test_personal_material_only
file_count=340
top_level_count=16
type_counts={'TXT': 111, '照片': 67, 'Markdown': 61, '图片': 39, 'PDF': 29, 'CSV': 28, '视频': 5}
raw_path_returned=False
```

Upload smoke:

```text
POST /api/media/upload
filename=codex_upload_smoke_20260707_140339.png
target_dir=Uploads
auto_process=false
ok=True
asset_id returned=True
raw_path_returned=False
jobs=1
```

`GET /api/media/photos?limit=8` then returned the smoke image as the newest
photo and included a preview `path_hash`.

Windows loopback check:

```text
Invoke-WebRequest http://127.0.0.1:8765/api/health -> 200
Invoke-WebRequest http://127.0.0.1:8765/static/digua_ai_nas_v2.js
  contains 上传图片, mediaUploadChoose, 图片已上传到相册
```

## Boundary

Two foreground full-rebuild attempts were intentionally stopped:

- `POST /api/ai-album/rebuild` with `run_yolo=true` and `yolo_max_files=300`
  was too slow because the S100P YOLO backend launches ROS/BPU work per image.
- `POST /api/ai-album/rebuild` with `run_yolo=false` still ran a full
  multimodal/CLIP rebuild and held CPU for multiple minutes.

Therefore Web UI refresh now performs read-only state reloads. Full rebuild
remains available as an API operation, but should be moved behind an async job
before it becomes a normal UI button.

