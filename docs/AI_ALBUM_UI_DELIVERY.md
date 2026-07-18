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

## Assistant photo-search relevance policy - 2026-07-18

The AI assistant no longer treats the requested result count as a target that
must be filled. `top_k` is now only a bounded candidate cap; the returned card
count is determined by local evidence and may be zero, one, or several.

The failure baseline for `找出有花或者有建筑的照片` returned exactly eight
cards at displayed scores from `27.2%` to `36.6%`. The first result had no image
embedding score and received `0.35` only because the metadata query used
`modality=image` as an `OR` match. The remaining weak CLIP candidates were kept
only because no relevance threshold existed.

The corrected contract is:

- Image modality is a scope filter, not positive relevance evidence.
- Chinese flower and building concepts are translated into separate English
  CLIP queries so an `OR` request can retrieve both concepts independently.
- Each semantic concept must pass the configured absolute cosine floor
  (`0.24`) and remain within `0.015` of that concept's best local result.
- Results from multiple concepts are deduplicated and sorted by evidence; the
  UI renders the dynamic result count without padding to eight.
- A Chinese visual concept that the deterministic local vocabulary cannot
  translate returns zero semantic candidates instead of falling back to a
  generic “photo” query.
- The response records candidate count, selected count, filtered-low-relevance
  count, variant count, and effective thresholds under `relevance_policy`.

Before deployment, the changed retriever was run read-only against the current
S100P production index. The flower/building query evaluated 77 unique
candidates, kept 4, and filtered 73. Visual inspection confirmed the retained
set contained one flower photo and three building/city photos. The unsupported
control `找出月球基地里的紫色潜艇照片` returned zero candidates.

## Assistant photo-search live acceptance - 2026-07-18

Source delivery:

- Feature PR: [#86](https://github.com/zhexuexiaotudou/-agent-s100-/pull/86)
- Squash merge on `main`: `d7b962acb86a87bc201259c2c4922f34ee21b6f8`
- CI: startup-link contract, repository tests, and offline regression all
  passed before merge.
- Local verification before the PR included 66 focused tests, 232 full-suite
  tests, Python compilation, JavaScript syntax validation, and
  `git diff --check`.

Deployment target and parity:

- Runtime: `/mnt/nas/openclaw` on `sunrise@192.168.127.10`.
- Service restart: `openclaw-gateway.service` entered active state at
  `2026-07-18 10:22:56 CST`.
- Local and S100P SHA-256 hashes matched for the feature-flags JSON, portal
  server, feature-flags module, retriever, planner, and search API.
- Rollback snapshot:
  `/mnt/nas/openclaw/backups/photo-search-relevance/20260718-102044`.

The first direct upload of the portal server failed because its deployed file
was owned by `root:root` with mode `0755`; the other files had already copied.
The corrected path uploaded the portal file to `/tmp`, replaced it with
`sudo install`, rechecked all six hashes, compiled the Python files, parsed the
JSON configuration, and only then restarted the service. This partial-deploy
failure must not be treated as a successful rollout merely because systemd can
restart.

Authenticated live API acceptance:

- `找出有花或者有建筑的照片` routed to
  `local_multimodal_search` and evaluated 77 unique candidates.
- It returned 4 cards, selected 4, filtered 73, and recorded two concept
  thresholds: `0.255324` and `0.258363`.
- Retained files were `picsum_random_097_id_859.jpg`,
  `picsum_random_071_id_306.jpg`, `picsum_random_085_id_953.jpg`, and
  `picsum_random_062_id_1067.jpg`.
- Browser inspection showed a brick building, a water lily, an architectural
  interior, and a city skyline. No unrelated padding cards were present.
- `找出月球基地里的紫色潜艇照片` returned zero with
  `unsupported_chinese_visual_concept`.
- `找出有人的照片` remained on `local_yolo_search` and returned 9 person
  detections from `yolo_object_index`.
- All three controls reported `cloud_used=false`.

The in-app browser at `http://127.0.0.1:18766/ui#assistant` independently
rendered `4 个照片 · 未上云`, loaded all four previews, and displayed the same
dynamic result set as the API. This completes the production acceptance for
the relevance-only result-count contract.

## Explicit object-evidence enforcement - 2026-07-18

The live prompt `找有狗的图片` exposed a separate fallback defect after the
semantic relevance fix. Intent parsing correctly produced `labels=["dog"]`,
and direct YOLO search returned zero with `no_matching_yolo_detection`, but the
assistant then fell through to CLIP and displayed two plant/flower images at
approximately `0.258` similarity. Those images contained no dog detections and
therefore could not satisfy the explicit object request.

The corrected contract makes an explicit object label a hard evidence
requirement:

- a successful YOLO result, including an empty result, is final;
- empty YOLO evidence returns zero instead of calling multimodal CLIP;
- unavailable or failed object search reports an error rather than silently
  changing retrieval semantics;
- semantic CLIP remains available for non-object concepts such as flowers,
  buildings, food, and landscapes.

Source and deployment evidence:

- Fix PR: [#88](https://github.com/zhexuexiaotudou/-agent-s100-/pull/88)
- Squash merge on `main`: `323cdb8b867db73ebeb2e3ba5569af7403e969fb`
- CI: repository tests, startup-link contract, and offline regression passed.
- Local tests: 54 assistant tests and 250 full-suite tests passed.
- Runtime script SHA-256 matched between merged `main` and S100P:
  `a02afc8774943dd89ee92335d79e7cacfedb234218bf5a4563e5a736508dd5c0`.
- `openclaw-gateway.service` restarted active at
  `2026-07-18 10:51:03 CST`.
- Rollback snapshot:
  `/mnt/nas/openclaw/backups/strict-object-photo-search/20260718-105100`.

Production acceptance after restart:

- `找有狗的图片`: `local_yolo_search`, `labels=["dog"]`, zero results,
  `no_matching_yolo_detection`, and `cloud_used=false`.
- Browser rendering: `0 个结果 · 未上云`, with no plant or flower cards.
- Control `找出有人的照片`: 9 YOLO person results.
- Control `找出有花或者有建筑的照片`: 4 dynamically selected CLIP results.
