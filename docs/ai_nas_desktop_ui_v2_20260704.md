# 地瓜 AI-NAS desktop UI v2 implementation note

Date: 2026-07-04

## Scope

Implemented a new browser UI surface based on the six supplied desktop mockups
and the Codex-executable design deconstruction file.

The new UI is served as a static, componentized SPA at:

```text
/ui
```

The previous web UI files were archived under:

```text
web/archive/20260704_pre_v2/
```

## Implementation path

- Added a token-first CSS system for colors, typography, spacing, radius, and
  shadow.
- Added reusable vanilla JS render components for layout, navigation, cards,
  tables, forms, empty states, loading skeletons, badges, panels, and state
  surfaces.
- Added six routeable hash pages: dashboard, AI assistant, files, documents,
  journal, and audit.
- Kept the current Python `ThreadingHTTPServer` stack. No UI library was added.
- Kept existing backend permission, journal, harness, and copy-route APIs
  unchanged.

## Security and product boundaries

- The UI keeps "本地优先" visible in the top bar.
- Private locations are shown as simplified paths, not full local or NAS paths.
- The file page exposes a controlled copy stepper with preview, dry-run,
  confirm, and execute stages.
- High-risk default controls are not added to the new UI.
- Audit entries show allowed and refused records without turning refused actions
  into executable retries.

## Validation record

Validation commands and visual QA results should be appended after each local
implementation run. The expected final verdict candidate is:

```text
ui_desktop_ready_with_minor_visual_fixes
```

## 2026-07-04 local validation

Environment:

- Host: Windows desktop, local browser UI server only.
- Server command: `python scripts/probes/ai_nas_operator_portal_server.py --bind 127.0.0.1 --port 8766 --no-refresh --report-root tmp\ui_v2_server`
- URL: `http://127.0.0.1:8766/ui`
- Scope: browser UI v2, static assets, route rendering, existing API smoke.

Checks:

- JavaScript syntax: `node --check web\static\digua_ai_nas_v2.js` passed.
- Python syntax: `python -m py_compile scripts\probes\ai_nas_operator_portal_server.py src\openclaw\routes\harness_status_routes.py src\openclaw\routes\journal_routes.py src\openclaw\routes\nas_copy_routes.py` passed.
- Tests: `py -3 -m pytest tests` passed, 66 tests.
- Product self-check: `py -3 SELF_CHECK.py` passed.
- HTTP smoke: `/ui`, `/static/digua_ai_nas_v2.css`, `/static/digua_ai_nas_v2.js`, and `/api/harness/status` all returned 200 on `127.0.0.1:8766`.

Visual QA:

- Browser plugin DOM snapshot was unavailable in this local app runtime because the plugin raised `TypeError: o.incrementalAriaSnapshot is not a function`.
- Fallback QA used Playwright with installed Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`.
- Desktop screenshot: `C:\Users\zhexu\AppData\Local\Temp\digua-ui-v2-desktop-rerun.png`.
- Assistant interaction screenshot: `C:\Users\zhexu\AppData\Local\Temp\digua-ui-v2-assistant-interaction-rerun.png`.
- Mobile files screenshot: `C:\Users\zhexu\AppData\Local\Temp\digua-ui-v2-mobile-files-rerun.png`.
- Routes checked: `#dashboard`, `#assistant`, `#files`, `#documents`, `#journal`, `#audit`.
- Every checked route rendered a nonblank page, had no console errors, had no horizontal overflow, and included loading, empty, error, success, and disabled state surfaces.

Known visual deltas from the supplied mockups:

- Brand/product icons are inline SVG-style application icons rather than the richer generated icon artwork from the mockups.
- The dashboard hero illustration is simplified CSS/SVG treatment, not a bitmap server-and-shield render.
- State panels were initially visible on every route for QA coverage, but this
  was later corrected because static Error/Disabled examples looked like real
  service failures in the production UI.
- Mobile layout is a responsive adaptation with bottom navigation rather than a one-to-one crop of the desktop mockups.

Verdict:

```text
ui_desktop_ready_with_minor_visual_fixes
```

## 2026-07-04 real NAS file explorer update

Reason:

- The first v2 file page still rendered mock file names. It did not behave like a real NAS file explorer.
- The file page now uses `/api/storage/list?path=<relative-path>` as the only file-list source.
- The UI does not directly access local disks or the whole NAS. It submits relative paths and lets the server resolve them under the configured Personal root.

Implementation:

- Added token-backed storage login handling in the v2 UI.
- Added an explorer-style toolbar with breadcrumbs, search, refresh, and up-level navigation.
- Added folder click-through from root to arbitrary child directories.
- Added dynamic left folder tree based on real root/current-directory entries.
- Added file/folder detail panel with real `relative_path`, parent path, type, size, modified time, and configured Personal root.
- Disabled new-folder/upload/share controls in this UI version because write flows are still governed by the harness copy route and should not be implied as direct file-manager writes.
- Fixed `/api/storage/list` query parsing to use standard decoded query parameters, so paths such as `Documents%2FInvoices` resolve correctly.
- Added read-only `/api/storage/download` with Bearer auth, read ACL check, relative-path normalization, and storage-root confinement.

S100P/NAS validation:

- S100P SSH user: `sunrise`.
- S100P board IP checked: `192.168.127.10`.
- Network check: TCP 22 reachable.
- NAS root checked on S100P: `/mnt/nas/openclaw/Personal`.
- Real root entries observed: `.snapshots`, `.trash`, `.versions`, `Collections`, `Documents`, `Inbox`, `Movies`, `Photos`.
- Deep path check: `Documents/Invoices` returned `2024`, `2025`, `2026`.
- Parent navigation check: `Documents/Invoices` parent resolved as `Documents`.

Rendered QA:

- Main OpenClaw service on S100P `127.0.0.1:8765` was not restarted.
- Temporary v2 server started on S100P loopback only: `127.0.0.1:18766`.
- Windows local SSH tunnel: `127.0.0.1:8767 -> S100P 127.0.0.1:18766`.
- Browser URL used for QA: `http://127.0.0.1:8767/ui#files`.
- Interaction path: login -> `Documents` -> `Invoices` -> up one level.
- Browser console errors: none after the no-token probe was removed.
- Screenshot: `C:\Users\zhexu\AppData\Local\Temp\digua-ui-v2-real-nas-invoices.png`.
- Screenshot: `C:\Users\zhexu\AppData\Local\Temp\digua-ui-v2-real-nas-documents-up.png`.

Checks:

- `node --check web\static\digua_ai_nas_v2.js` passed.
- `python -m py_compile scripts\probes\ai_nas_operator_portal_server.py` passed.
- `py -3 -m pytest tests` passed, 66 tests.
- `py -3 SELF_CHECK.py` passed.

Verdict:

```text
real_nas_file_explorer_ready_for_review
```

## 2026-07-05 assistant local chat route update

Reason:

- The AI assistant page previously rendered normal prompts such as
  `总结一下地瓜 AI-NAS 当前有哪些核心能力。` as a generic safety-boundary result
  because `/api/copilot/chat` returned `nas_action.operation=none` and the
  frontend only interpreted NAS action payloads.
- This made the page look like a router trace instead of a conversational
  assistant.

Implementation:

- Kept quoted-path NAS actions on the existing read-only/list/copy Harness
  routes.
- Added a local chat fallback for non-file prompts through the local Qwen
  OpenAI-compatible endpoint with `disable_ai_nas_tools=true`.
- The frontend now displays `assistant_mode=local_qwen_chat` answers directly.
- Added static asset cache busting for the v2 UI HTML so browser tabs load the
  new assistant logic.

Validation:

- `py -3 -m py_compile scripts\probes\ai_nas_operator_portal_server.py` passed.
- `node --check web\static\digua_ai_nas_v2.js` passed with the bundled Codex
  Node runtime.
- `py -3 -m pytest tests -q` passed, 99 tests.
- S100P deployment:
  - SSH user: `sunrise`.
  - Board IP: `192.168.127.10`.
  - Services before deployment: `openclaw-gateway.service` active,
    `qwen25-local-openai-gateway.service` active.
  - Updated files deployed to `/mnt/nas/openclaw`.
  - `systemctl --user restart openclaw-gateway.service` completed and
    `/api/health` returned OK.
- Live API checks on S100P:
  - `POST /api/copilot/chat` with a project capability prompt returned a local
    assistant answer without granting Qwen tool execution authority.
  - `POST /api/token-budget/route` for the same prompt returned
    `route=local_only`, `cloud_allowed=false`, `cloud_call_avoided=true`.
  - `POST /api/copilot/chat` with `列出 "Inbox"` still returned
    `nas_action.operation=list`, `status=completed`.
  - A generic non-project prompt entered `assistant_mode=local_qwen_chat` with
    the local Qwen model and no tool execution authority.
- Browser QA through `http://127.0.0.1:18765/ui?qa=20260705-local-chat-2#assistant`:
  - Page title: `地瓜 AI-NAS Desktop UI v2`.
  - CSS/JS loaded with `?v=20260705-local-chat`.
  - The target prompt rendered a visible capability answer with local-only route
    evidence and no cloud/tool execution.
  - The old `该意图已进入安全边界检查` text did not appear.
  - Browser console error/warn count: 0.

Remaining boundary:

- The local Qwen route is connected for plain prompts, but current S100P Qwen
  generation can be conservative or low quality on broad open-ended chat. Product
  claims should remain bounded to local Qwen text assistance and
  Harness-governed NAS workflows.

## 2026-07-05 production UI state panel cleanup

Reason:

- The generic `Loading / Empty / Error / Success / Disabled` row was a static QA
  state-surface sample, not live service status.
- In production it was misleading because `本地服务暂不可用` looked like an
  unresolved runtime error even when the S100P services were healthy.

Implementation:

- `renderStatePanel()` now returns nothing by default.
- The state panel can still be rendered for development review by opening the UI
  with `?debugStates=1`.
- The v2 HTML static asset version was bumped to
  `20260705-state-panels-hidden` so browser tabs fetch the corrected script.

Expected production behavior:

- Normal pages no longer show the bottom QA state row.
- Real errors still appear in the specific page area that failed, for example
  assistant request failure, file-list failure, or document-query failure.

## 2026-07-05 direct Qwen chat correction

Reason:

- The previous assistant fallback mixed two behaviors: some project questions
  used a deterministic platform-context answer, while other questions called
  Qwen.
- Generic prompts such as `你是谁` could hang and then fail because the 8765
  copilot layer prepended a long platform context before forwarding to the Qwen
  gateway. The 8765 request timed out around 90 seconds, and the Qwen gateway
  later logged a broken pipe because the caller had already disconnected.

Implementation:

- Removed the deterministic `local_context_answer` route.
- Non-file assistant prompts now forward the exact user prompt to the S100P Qwen
  endpoint at `127.0.0.1:18080/v1/chat/completions`.
- The payload still sets `disable_ai_nas_tools=true` and
  `qwen_execution_authority=false`; this only disables autonomous tool calls and
  does not replace Qwen's text generation.
- Static asset version bumped to `20260705-qwen-direct-chat`.

Expected behavior:

- `你是谁` and other ordinary chat prompts should return
  `assistant_mode=local_qwen_chat`.
- Quoted NAS path actions such as `list "Inbox"` continue to use the existing
  read-only/list/copy Harness routes instead of Qwen free text.

## 2026-07-05 assistant search closed loop

Reason:

- After direct Qwen chat was connected, all unquoted assistant prompts entered
  `local_qwen_chat`.
- Search requests such as `搜索 NAS 里有人的照片` were therefore answered by Qwen as
  ordinary chat, and Qwen correctly said it could not directly access personal
  photos. That was a product-routing gap, not a YOLO/Qwen capability proof.

Implementation:

- `copilot_chat()` now detects local NAS search intent before generic Qwen chat.
- Object/photo/video search with supported labels enters
  `assistant_mode=local_yolo_search` and calls `/api/yolo-index/search`.
- General image/video/document search enters
  `assistant_mode=local_multimodal_search` and calls
  `/api/multimodal-search/query`.
- The frontend renders `search.results` directly in the assistant answer card,
  including `asset_id`, redacted title, evidence reference, labels and score.
- Static asset version bumped to `20260705-search-closed-loop`.

Safety boundary:

- This route detects generic objects such as `person`; it does not perform face
  recognition, child/person identity matching, or raw absolute path disclosure.
- Qwen still has `qwen_execution_authority=false`; local search is performed by
  the OpenClaw API layer after authenticated assistant entry.

Expected behavior:

- `搜索 NAS 里有人的照片` should return `assistant_mode=local_yolo_search`, display
  local results when the YOLO index has `person` detections, and never fall back
  to a generic Qwen refusal.
- If the local index has no match, the assistant should still return a completed
  local-search empty result with the degraded reason instead of asking the user
  to use another search engine.

## 2026-07-05 Qwen-first copilot orchestrator

Reason:

- The assistant search closed loop fixed photo search, but it routed search
  before Qwen. The product requirement is stronger: every user message must
  first enter the S100P Qwen decision layer, then dispatch to local NAS tools,
  local Qwen chat, or cloud overflow according to privacy and task type.
- Customer-facing validation must use the same assistant chat path as the web
  product, not only direct module APIs.

Implementation:

- `/api/copilot/chat` now calls the local Qwen gateway router first for every
  non-empty message. The router payload uses
  `metadata.purpose=edge_cloud_route_classifier`, sends the original user query,
  and keeps `qwen_execution_authority=false`.
- The copilot dispatcher maps Qwen-routed local intents to existing APIs:
  YOLO/multimodal search, document FTS RAG, storage list/inspect/create-folder,
  controlled copy route, snapshot creation, backup task creation/run, media
  summary/index/album, journal summary/manual entry, audit summary, report list,
  ops/app/storage summaries, and local Qwen general chat.
- Public non-private complex prompts route to cloud overflow. On this S100P
  deployment no real cloud URL is configured, so `cloud_overflow_stub` returns a
  controlled local answer and confirms no cloud payload was sent.
- The assistant UI now renders `qwen_router` evidence: Qwen route, privacy
  level, task complexity, local tool, classifier, fallback state and reason.
- Static asset version bumped to `20260705-qwen-copilot-orchestrator`.

Safety boundary:

- Qwen remains a classifier/advisor and does not receive NAS write authority.
- Private NAS content, photos, documents, invoices, contracts, backups,
  snapshots and uncertain tasks stay local.
- Mutating actions still use the existing authenticated API/ACL/Harness layer.
  Destructive rename/delete/move/overwrite/shell actions remain blocked unless a
  future reviewed allowlist route explicitly enables them.

Verification:

- Local test suite: `py -m pytest -q` -> `102 passed`.
- S100P deployment backup:
  `/mnt/nas/openclaw/reports/qwen25_ai_nas/copilot_qwen_router_backup_20260705-223032`.
- Remote checks after deploy:
  `python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py`,
  `node --check web/static/digua_ai_nas_v2.js`,
  `systemctl --user restart openclaw-gateway.service`,
  `curl -fsS http://127.0.0.1:8765/api/health`,
  `curl -fsS http://127.0.0.1:18080/health`.
- Live assistant-chat cases through `/api/copilot/chat` all returned
  `qwen_execution_authority=false`:
  `你是谁` -> `local_qwen_chat`;
  `搜索 NAS 里有人的照片` -> `local_yolo_search`, 3 `person` results;
  `list "Documents"` -> `local_storage_list`;
  `总结 Documents 里的发票文档` -> `local_document_query`;
  create folder -> `local_storage_create_folder`;
  snapshot -> `local_snapshot_create`;
  backup task -> `local_backup_create_task`;
  media status -> `local_media_summary`;
  journal summary -> `local_journal_summary`;
  audit summary -> `local_audit_summary`;
  reports list -> `local_reports_list`;
  public non-private market strategy -> `cloud_overflow_stub` because
  `AI_NAS_CLOUD_CHAT_URL` is not configured.
- Web UI verification used
  `http://127.0.0.1:18765/ui?qa=20260705-qwen-copilot-orchestrator#assistant`
  and submitted `搜索 NAS 里有人的照片`. The page rendered local search results
  and Qwen router evidence (`local`, `high`, `local_nas_search`,
  `qwen_gateway_structured_router`, fallback `否`). Screenshot:
  `C:/Users/zhexu/AppData/Local/Temp/digua_qwen_copilot_ui_verified.png`.

## 2026-07-05 assistant search product UI cleanup

Reason:

- The assistant search route worked functionally, but the answer card still
  looked like a developer/debug report: evidence ids, asset ids, bbox-related
  detections, classifier fields and trace hashes were visible by default.
- Customer-facing photo search should show previews, filenames, dates, match
  reason and privacy state first. Technical routing details should be available
  only on demand.

Implementation:

- `/api/yolo-index/search` now includes `file_type`, `size_bytes` and `mtime`
  in result rows, so the assistant can render file-oriented metadata without
  exposing raw absolute paths.
- `/api/copilot/chat` enriches local search results with a `display` object:
  `name`, `date_label`, `type_label`, `size_label`, `match_label`,
  `match_score_label`, `privacy_label` and `location_label`.
- A new authenticated `/api/storage/preview-by-hash` route serves inline
  previews by path hash. The lookup is bounded to the user's `Personal` root
  with ACL checks plus the explicit YOLO v2 fixture image root used by the
  current S100P demo index. It does not scan the whole NAS and does not return
  relative or absolute paths in the assistant payload.
- The assistant UI now renders local search results as product cards with image
  preview, filename, date, type/size, object match and local privacy tags.
- The always-visible service section was reduced to useful product indicators:
  processing location, privacy level, input token count, local route type and
  model/source. Detailed route fields are behind a native `查看详情` disclosure.
- The desktop side panel label `推理过程（Trace）` was renamed to `处理进度`.
- Static asset version bumped to `20260705-search-product-ui`.

Safety boundary:

- Qwen still has `qwen_execution_authority=false`; preview and search are
  served by authenticated OpenClaw local APIs.
- The route still detects generic `person` objects only. It does not perform
  face recognition or identity matching.
- The preview route is hash-based and allowlisted; it is not a raw NAS file
  browser.

Verification:

- Local checks:
  `node --check web/static/digua_ai_nas_v2.js`,
  `py -m py_compile scripts/probes/ai_nas_operator_portal_server.py src/yolo_index/service.py`,
  `py -m pytest tests/test_copilot_local_qwen_chat.py -q` -> `7 passed`,
  `py -m pytest -q` -> `103 passed`.
- S100P target confirmed: `192.168.127.10:22`, SSH user `sunrise`, host
  `ubuntu`, `openclaw-gateway.service` active.
- S100P deploy checks:
  `python3 -m py_compile /mnt/nas/openclaw/scripts/probes/ai_nas_operator_portal_server.py /mnt/nas/openclaw/src/yolo_index/service.py`,
  `/opt/node-v22.19.0-linux-arm64/bin/node --check /mnt/nas/openclaw/web/static/digua_ai_nas_v2.js`,
  `systemctl --user restart openclaw-gateway.service`,
  `systemctl --user is-active openclaw-gateway.service` -> `active`.
- Live assistant API through `http://127.0.0.1:18765/api/copilot/chat`,
  prompt `搜索 NAS 里有人的照片`, returned `assistant_mode=local_yolo_search`,
  `result_count=3`, filenames
  `person_car_street.jpg`, `person_bus_stop_sign.jpg`,
  `person_kite_scene.jpg`, privacy `本地私有`, `cloud_used=false`.
- Preview endpoint check:
  `/api/storage/preview-by-hash?path_hash=cb25394d66c2f600f8619ac4ea8f3ce1173a074dd0511d1916537eb587e5dff1`
  with Authorization returned `200 OK`, `Content-Type: image/jpeg`,
  `Content-Disposition: inline; filename="person_car_street.jpg"`.
- In-app Browser verification used
  `http://127.0.0.1:18765/ui?qa=20260705-search-product-ui#assistant` and
  submitted `搜索 NAS 里有人的照片`. The rendered page showed 3 preview cards,
  default-closed `查看详情`, no visible asset ids/trace hash/classifier dump, and
  no app console warnings/errors.
- Screenshot evidence:
  `C:/Users/zhexu/AppData/Local/Temp/digua_search_product_ui_cards_verified.png`,
  `C:/Users/zhexu/AppData/Local/Temp/digua_search_product_ui_details_verified.png`,
  `C:/Users/zhexu/AppData/Local/Temp/digua_search_product_ui_desktop_cards_ready.png`.

## 2026-07-05 all assistant result product UI cleanup

Reason:

- The photo search answer was productized first, but other Copilot actions still
  risked exposing raw route/debug fields or backend-style summaries. Customer
  usage enters through the AI assistant, so every local action needs a
  user-facing card, KPI strip or empty state.
- Report cards also briefly exposed full internal `/mnt/nas/openclaw/...` paths
  as default card metadata. Those paths are useful for troubleshooting but are
  not appropriate as the primary customer UI.

Implementation:

- `web/static/digua_ai_nas_v2.js` now dispatches all `assistant_mode` /
  `nas_action.operation` results through product renderers:
  local YOLO search, document RAG, storage list/inspect/create-folder,
  snapshot/backup operations, media index/album/summary, journal summary/manual
  entry, storage status, ops health, app/plugin status, audit summary, reports
  list and cloud-overflow boundary.
- Each product result uses a concise title, KPI strip, repeated result cards,
  operation card or compact empty state. Detailed route/service facts remain
  behind the default-closed `查看详情` disclosure.
- `presentAssistantAnswer()` suppresses raw Python dict-style summary strings in
  the visible answer area for media, ops, apps, audit and reports summaries.
- `scripts/probes/ai_nas_operator_portal_server.py` routes explicit path
  inspection terms such as `检查 "Documents"` before document RAG, while keeping
  `总结 Documents 里的发票文档` on the document-query path.
- Backend summary answers for media, ops, apps, audit, reports and storage are
  now user-readable product sentences instead of raw dict dumps.
- Report list cards now show report type, modified time, size and export state;
  full internal paths are not shown in the default card line.
- Static asset version remains `20260705-all-assistant-product-ui`.

Verification:

- Local checks:
  `py -m py_compile scripts/probes/ai_nas_operator_portal_server.py`,
  `node --check web/static/digua_ai_nas_v2.js` via Codex bundled Node,
  `py -m pytest tests/test_copilot_local_qwen_chat.py -q` -> `7 passed`,
  `py -m pytest -q` -> `103 passed`.
- S100P target confirmed through existing tunnel and SSH key:
  `127.0.0.1:18765 -> 192.168.127.10:8765`, SSH user `sunrise`, host
  `ubuntu`.
- S100P deploy checks:
  `python3 -m py_compile /mnt/nas/openclaw/scripts/probes/ai_nas_operator_portal_server.py`,
  `/opt/node-v22.19.0-linux-arm64/bin/node --check /mnt/nas/openclaw/web/static/digua_ai_nas_v2.js`,
  `systemctl --user restart openclaw-gateway.service`,
  `systemctl --user is-active openclaw-gateway.service` -> `active`.
- Live assistant API through `http://127.0.0.1:18765/api/copilot/chat` passed
  these user-entry prompts:
  `搜索 NAS 里有人的照片` -> `local_yolo_search`, 3 image results;
  `list "Documents"` -> `local_storage_list`, 7 entries;
  `检查 "Documents"` -> `local_storage_list`, 7 entries;
  `总结 Documents 里的发票文档` -> `local_document_query`, local no-evidence
  answer;
  `查看 NAS 存储状态` -> `local_storage_status`;
  `查看媒体库状态` -> `local_media_summary`;
  `查看运行健康状态` -> `local_ops_summary`;
  `查看应用插件状态` -> `local_apps_summary`;
  `查看审计摘要` -> `local_audit_summary`;
  `列出本地报告` -> `local_reports_list`, 80 reports;
  `请基于公开信息分析 AI NAS 市场趋势，不引用本地文件` ->
  `cloud_overflow_stub`, no cloud payload sent because `AI_NAS_CLOUD_CHAT_URL`
  is not configured.
- In-app Browser verification used
  `http://127.0.0.1:18765/ui?qa=20260705-all-assistant-product-ui#assistant`.
  Real textbox submissions verified product sections/cards for image search,
  storage list, document query, storage status, media summary, ops summary, app
  summary, audit summary, report list and cloud boundary. The visible page had
  default-closed `查看详情` and no visible `Trace Hash`, `asset_id` or raw dict
  dumps.
- A controlled test folder `CodexProductUiSmoke` was created via the assistant
  to verify the create-folder product path. This is an explicit smoke artifact
  under the bounded Personal root, not a source-file mutation.

Boundary:

- After the final report-card path hiding patch, the in-app Browser control
  channel could still list the page tab but repeatedly timed out attaching to
  the tab for one more visual re-render. The final report-card change was
  therefore verified by remote JS syntax check, remote code marker
  `reportMeta`, and live API data shape. The broader product UI matrix above was
  already verified through real browser submissions before that last one-line
  metadata tightening.

## 2026-07-06 image result double-click viewer

Reason:

- Local image search cards showed useful previews, but they behaved like static
  cards. For a NAS product, users expect file results to open with the same
  basic muscle memory as Windows Explorer: double-click the item to inspect it.

Implementation:

- Image search result cards now carry `role="button"`, keyboard focus, and
  `data-image-preview-url` metadata when an authenticated preview is available.
- Double-clicking an image result opens a full-page image viewer overlay.
  The viewer shows the file name, date/type/size, match reason and a contained
  large image.
- The large image reuses the same authenticated `/api/storage/preview-by-hash`
  path and Blob cache used by thumbnails. No raw NAS path is exposed and no new
  NAS permission is added.
- The viewer can be closed by the close button, backdrop click, or `Esc`.
- Static asset version bumped to `20260706-image-viewer`.

Verification:

- Local checks:
  `node --check web/static/digua_ai_nas_v2.js` via Codex bundled Node,
  `py -m pytest tests/test_copilot_local_qwen_chat.py -q` -> `7 passed`,
  `py -m pytest -q` -> `103 passed`.
- S100P deploy checks:
  `/opt/node-v22.19.0-linux-arm64/bin/node --check /mnt/nas/openclaw/web/static/digua_ai_nas_v2.js`,
  `systemctl --user is-active openclaw-gateway.service` -> `active`.
- Browser verification used
  `http://127.0.0.1:18765/ui?qa=20260706-image-viewer#assistant` and submitted
  `找到有人的图片`.
- The page rendered 3 openable image cards:
  `person_car_street.jpg`, `person_bus_stop_sign.jpg`,
  `person_kite_scene.jpg`.
- Double-clicking `person_car_street.jpg` opened the image viewer with a Blob
  image source, title `person_car_street.jpg`, and metadata
  `2026-07-05 19:32 · 照片 · 2.1 MB · 人 · 90.2%`.
- Close button returned to the 3-card result grid. A follow-up `Esc` close test
  also returned to the same 3-card grid.
- Screenshot evidence:
  `C:/Users/zhexu/AppData/Local/Temp/digua_image_viewer_double_click_verified.png`.
