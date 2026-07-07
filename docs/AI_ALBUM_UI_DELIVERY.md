# AI Album UI Delivery

## Scope

This note records the AI Album workspace added to the existing OpenClaw
AI-NAS v2 desktop UI. The new workspace keeps the existing UI color system and
turns the previous separate AI Space, media album, smart-classification, person
attribute, and Auto Organizer capabilities into one product-facing page.

Primary route:

- `http://127.0.0.1:8765/ai-album`

The route serves the same authenticated v2 Web UI bundle as `/ui` and opens the
`AI 相册` page directly.

## Implemented Path

Frontend:

- Added the `AI 相册` navigation item and dashboard shortcut.
- Added a three-column desktop workspace:
  - left smart-category and modality filters
  - center search, tabs, plan status, and asset grid
  - right selected-asset detail panel
- Added local search presets for invoices, white-clothes person queries,
  contracts, and the unsafe identity-recognition test query.
- Added asset cards with real thumbnails from `/api/media/preview?path_hash=...`.
- Reused the existing image viewer, including double-click open, zoom, fit,
  rotate, wheel zoom, and drag-to-pan.
- Added selected-asset detail with smart naming, OCR status, evidence count,
  category tags, and safety flags.
- Added an Auto Organizer plan workflow panel with plan, dry-run, approve,
  execute, and rollback controls. The page does not auto-execute a plan.

Backend route:

- `GET /ai-album` now serves `web/ai_nas_desktop_v2.html`.

API wiring:

- `GET /api/ai-space/status`
- `GET /api/ai-space/facets`
- `GET /api/ai-space/assets`
- `POST /api/ai-space/search`
- `GET /api/media/photos`
- `GET /api/media/preview`
- `GET /api/smart-classification/categories`
- `POST /api/person-attribute/search`
- `GET /api/auto-organize/status`
- `POST /api/auto-organize/plan`
- `POST /api/auto-organize/dry-run`
- `POST /api/auto-organize/approve`
- `POST /api/auto-organize/execute`
- `POST /api/auto-organize/rollback`

## Safety Boundary

- Identity-recognition style queries such as `这个人是谁` are blocked in the
  UI before calling the person-attribute API.
- The page presents `face_identification_enabled=false`,
  `biometric_recognition_enabled=false`, and
  `sensitive_attribute_inference_enabled=false` for the blocked query path.
- No delete, overwrite, raw-path, chmod, chown, arbitrary shell, or NAS-wide
  action is exposed by the AI Album UI.
- Auto Organizer execution still requires a generated plan, a dry-run/approval
  flow, and the service-side rollback path. The UI does not auto-run execute.
- Gateway exposure remains loopback-only.
- Private raw files are not sent to cloud services by this UI path.

## Gate

The new gate validates the route, static UI wiring, local identity-query block,
real API responses, media preview bytes, and Auto Organizer safety flags.

```bash
python3 gates/stage11_ai_album_ui_gate.py \
  --base-url http://127.0.0.1:8765 \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas
```

Expected report paths:

- `reports/stage11_ai_album_ui_gate.json`
- `reports/stage11_ai_album_ui_gate.md`

## Demo Steps

1. Open `http://127.0.0.1:8765/ai-album`.
2. Log in through the existing local identity token if needed.
3. Confirm the AI Space count, media-preview count, cloud flag, and raw-path
   flag in the KPI strip.
4. Click a smart category or tab and confirm the asset grid updates.
5. Double-click a thumbnail and verify the image viewer opens with zoom,
   rotate, fit/reset, wheel zoom, and pan.
6. Search `票据发票` or `穿白色上衣的人` and confirm the result area updates from
   real local API responses.
7. Search `这个人是谁` and confirm the UI blocks the query locally.
8. Click `生成整理计划` and confirm the workflow shows a plan or a safe blocker
   without exposing raw paths or delete/overwrite actions.

## Verification

Local static checks before S100P deployment:

```powershell
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --check web\static\digua_ai_nas_v2.js
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile scripts\probes\ai_nas_operator_portal_server.py gates\stage11_ai_album_ui_gate.py
```

S100P live verification is recorded after deployment in the final acceptance
section of this note.

## S100P Live Acceptance - 2026-07-07

Environment:

- Host: S100P over SSH as `sunrise@192.168.127.10`.
- Board network observed during acceptance:
  - `eth1`: `192.168.127.10/24`, `192.168.137.10/24`
  - `lo`: `127.0.0.1/8`
- Runtime root: `/mnt/nas/openclaw`.
- Service: `openclaw-gateway.service`.
- Qwen local gateway service: `qwen25-local-openai-gateway.service`.

Deployment and service check:

```bash
python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py gates/stage11_ai_album_ui_gate.py
systemctl --user restart openclaw-gateway.service
systemctl --user is-active openclaw-gateway.service
curl -fsS http://127.0.0.1:8765/api/health
```

Observed result:

- `openclaw-gateway.service`: `active`
- `qwen25-local-openai-gateway.service`: `active` before deployment
- `/api/health`: `ok=true`
- `/ai-album` served the v2 UI bundle with static resource version
  `20260707-ai-album6`.

Stage 11 gate:

```bash
python3 gates/stage11_ai_album_ui_gate.py \
  --base-url http://127.0.0.1:8765 \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --timeout 60
```

Observed result:

- Verdict: `ok_stage11_ai_album_ui_gate`
- Report: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage11_ai_album_ui_gate.json`
- Markdown: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage11_ai_album_ui_gate.md`
- AI Space assets: `4`
- Media photos: `22`
- Preview route: HTTP `200`, `image/png`, `123788` bytes
- Safety checks passed for delete blocked, overwrite blocked, Qwen execution
  authority blocked, no raw path return, and cloud private processing off.

Browser acceptance in the in-app browser:

- Opened `http://127.0.0.1:8765/ai-album`.
- KPI strip showed:
  - `AI Space 素材`: `4`
  - `媒体预览`: `22`
  - `云端调用`: `关闭`
  - `原始路径`: `关闭`
- Tabs showed:
  - `全部 4`
  - `照片 4`
  - `人物/服装 4`
  - `票据 4`
  - `合同 4`
  - `资料 4`
  - `视频 0`
- Smart category `票据发票` filtered to `4` cards.
- Search `票据发票` returned `4` local results.
- Search `这个人是谁` was blocked locally with the message
  `已拦截身份识别类查询：这个人是谁`.
- AI Album thumbnails loaded as `blob:` images from the media preview route.
- A quick double-click before thumbnails were fully loaded opened the image
  viewer and waited for the shared in-flight preview request instead of
  timing out.
- Image viewer controls were verified:
  - zoom changed from `100%` to `120%`
  - rotate changed the transform to include `rotate(90deg)`
  - fit/reset returned to `translate(0px, 0px) rotate(0deg) scale(1)`
- Auto Organizer plan workflow opened with `3` candidate items and showed:
  - `删除允许`: `关闭`
  - `覆盖允许`: `关闭`
  - `Qwen 执行权`: `关闭`
  - `原始路径返回`: `关闭`
  - no `aiAlbumDelete`, `aiAlbumOverwrite`, or `aiAlbumRawPath` action
- Browser console check returned zero error/warning entries.

## Boundaries

- This UI integrates the current AI Space catalog. It does not claim full
  mobile-photo-app parity.
- Symbolic summaries are still local index summaries, not cloud VLM captions.
- Person Attribute Search remains non-identifying and must not be used for face
  identity recognition.
- Physical organization is still routed through Auto Organizer plan and
  approval APIs; smart classification itself remains virtual.
