# AI-NAS Web UI Product Design Cleanup - 2026-07-06

## Scope

- Target host: S100P `sunrise@192.168.127.10`
- Runtime path: `/mnt/nas/openclaw/web`
- Updated local files:
  - `web/ai_nas_desktop_v2.html`
  - `web/static/digua_ai_nas_v2.js`
  - `web/static/digua_ai_nas_v2.css`
- Browser URL used for validation: `http://127.0.0.1:18765/ui?qa=20260706-product-ui-cleanup`

## Product Cleanup

- Replaced visible R&D terms such as `Trace ID`, `Workspace Harness`, raw policy IDs, mock evidence, benchmark-only labels, and raw operation names with product-facing labels.
- Dashboard now uses live local state and empty states instead of static demo cards.
- AI assistant panels now show product capabilities, evidence, and privacy boundaries instead of fake agents or raw traces.
- Audit page now shows local service, user action, status, resource summary, and record number; raw internal trace wording is hidden.
- Settings page hides raw Linux deployment paths and policy IDs, and maps risk actions to Chinese product labels.
- Token pages show token/privacy/quality status with product labels; raw report paths are not surfaced in settings.

## S100P Deployment

Updated files were copied to:

```text
/mnt/nas/openclaw/web/ai_nas_desktop_v2.html
/mnt/nas/openclaw/web/static/digua_ai_nas_v2.js
/mnt/nas/openclaw/web/static/digua_ai_nas_v2.css
```

The web shell references:

```text
digua_ai_nas_v2.css?v=20260706-product-ui-cleanup
digua_ai_nas_v2.js?v=20260706-product-ui-cleanup
```

## Validation

- `node --check web/static/digua_ai_nas_v2.js`: passed.
- S100P service: `openclaw-gateway.service` active.
- S100P health: `curl http://127.0.0.1:8765/api/health`: passed.
- Remote `/ui` loads `20260706-product-ui-cleanup`: passed.
- Remote static scan found no visible-product cleanup blockers for:
  - `Trace ID`
  - `Workspace Harness`
  - `Harness`
  - `Policy ID`
  - `Personal Root`
  - `web-ui-verify`
  - `mockup-evidence`
  - `tool_trace_id`
  - fake IP/model strings
  - raw benchmark/report English labels
- Edge headless login-state validation passed for:
  - Dashboard
  - AI Assistant
  - Audit
  - Settings
  - Agent Runtime
- Final settings validation showed no `chown`, `recursive_delete`, `arbitrary_shell`, raw policy ID, raw trace ID, or raw report path.

## Evidence Artifacts

- Unauthenticated audit screenshot:
  - `C:\Users\zhexu\AppData\Local\Temp\digua_product_ui_cleanup_audit.png`
- Authenticated settings screenshot:
  - `C:\Users\zhexu\AppData\Local\Temp\digua_product_ui_cleanup_settings_authed.png`

## Boundary

- No backend permission expansion was made.
- No public gateway exposure was added.
- The in-app Browser connector timed out during long DOM automation after reconnect; final browser validation used Microsoft Edge headless with DevTools Protocol against the same local web URL.

## Responsive Product UI Follow-up - 2026-07-06

### Additional Cleanup

- Reworked shared display helpers so user-facing cards no longer default to raw paths, hashes, trace IDs, route IDs, API paths, or camera-style filenames.
- Reports now show product titles such as `Evidence report 1` / `Gate report 5` instead of raw report filenames.
- File browsing hides system/test folders such as dot-folders and Codex/Qwen verification folders from the default product view.
- Assistant multimodal results now show `Photo 1`, `Photo 2`, `Photo 3` in cards and evidence panels instead of camera filenames.
- Mobile file and audit tables collapse to the columns that matter for product use instead of preserving the desktop table width.
- Search inputs, service pills, evidence rows, report cards, and assistant text now have explicit responsive width and overflow rules.

### Deployment And Validation

- Updated S100P files:
  - `/mnt/nas/openclaw/web/static/digua_ai_nas_v2.js`
  - `/mnt/nas/openclaw/web/static/digua_ai_nas_v2.css`
  - `/mnt/nas/openclaw/web/ai_nas_desktop_v2.html`
- Current web asset version: `20260706-responsive-product-ui`.
- `node --check web/static/digua_ai_nas_v2.js`: passed locally and on S100P.
- Remote static scan found no visible occurrences of raw R&D strings including `/mnt/nas`, `Trace ID`, `Workspace Harness`, `Personal root`, `copy route`, `SHA256`, `/api/copilot/chat`, or `/api/token-budget/route`.
- Microsoft Edge + Playwright checked 25 live UI cases:
  - pages: dashboard, documents, reports, files, assistant, settings, audit, media
  - viewports: 1365x768, 1024x720, 390x844
  - assistant prompt path: `找出有人的照片`
  - result: `ok=true`, `checked=25`, `failing=[]`

### Screenshot Evidence

- `C:\Users\zhexu\AppData\Local\Temp\digua_product_ui_documents_desktop_final_camera.png`
- `C:\Users\zhexu\AppData\Local\Temp\digua_product_ui_reports_mobile_final_camera.png`
- `C:\Users\zhexu\AppData\Local\Temp\digua_product_ui_files_mobile_final_camera.png`
- `C:\Users\zhexu\AppData\Local\Temp\digua_product_ui_assistant_person_desktop_final_camera.png`

## NAS Inventory Copilot Fix - 2026-07-06

### Issue

The assistant prompt `nas上有什么文件，分别是什么类型的，占多大空间` previously fell through to generic `local_qwen_chat`. Qwen answered with a general NAS definition instead of executing a local NAS inventory task.

### Fix

- Added a dedicated `storage_inventory` copilot intent for natural-language NAS file inventory questions.
- Added the `local_storage_inventory` local tool route and a read-only `storage_inventory_payload` that scans the configured personal root under existing read ACL checks.
- Returned product-facing inventory fields: visible entry names, file/folder type, estimated size, file count, folder count, modified time, and type summary.
- Rendered inventory results in the assistant as product cards and KPI chips rather than raw JSON, paths, policy IDs, or trace parameters.
- Updated the assistant route panel to show a stable product label such as `本地文件服务` from the copilot response instead of borrowing token-budget route labels.

### S100P Deployment

Updated files were copied to:

```text
/mnt/nas/openclaw/scripts/probes/ai_nas_operator_portal_server.py
/mnt/nas/openclaw/web/static/digua_ai_nas_v2.js
/mnt/nas/openclaw/web/ai_nas_desktop_v2.html
```

The current web shell references:

```text
digua_ai_nas_v2.css?v=20260706-storage-inventory
digua_ai_nas_v2.js?v=20260706-storage-inventory
```

The user-level `openclaw-gateway.service` was restarted and recovered on `127.0.0.1:8765`; the local proxy remained available on `127.0.0.1:18765`.

### Validation

- Local Python compile: `py -3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py`: passed.
- Local JS syntax: `node --check web/static/digua_ai_nas_v2.js`: passed.
- S100P Python compile: `python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py`: passed.
- S100P JS syntax: `node --check web/static/digua_ai_nas_v2.js`: passed.
- API prompt test through `http://127.0.0.1:18765/api/copilot/chat`: passed.
  - `assistant_mode`: `local_storage_inventory`
  - `route`: `local_storage_inventory`
  - `nas_action.operation`: `inventory`
  - `cloud_used`: `false`
  - result summary: 6 top-level entries, 164 files, 32 folders, estimated 165.1 KB
- Browser product-flow test through `/ui#assistant`: passed.
  - The page showed `文件盘点`, `本地文件返回`, and `本地文件服务`.
  - The page did not show the generic NAS encyclopedia answer.
  - The result was displayed as KPI cards and directory cards.

### Evidence Artifact

- `C:\Users\zhexu\AppData\Local\Temp\digua_ai_nas_storage_inventory_ui_final_pass_20260706.png`

### Boundary

- No 24-hour soak test was started.
- No cloud request was made for the NAS inventory prompt.
- No write, delete, move, rename, chmod, recursive, or shell execution permission was granted to Qwen.
- The inventory scan is read-only and remains bounded by the configured personal root and current ACL checks.

## NAS Inventory Count-Prompt Follow-up - 2026-07-06

### Issue

The shorter prompt `NAS里有多少文件` was still falling through to `local_qwen_chat` because the first inventory intent patch covered `有什么文件 / 哪些文件 / 类型 / 空间` but did not cover count-only wording such as `多少文件`, `几个文件`, `文件数`, or `文件数量`.

### Fix

- Expanded `COPILOT_STORAGE_INVENTORY_TERMS` to include count and statistics wording.
- Added explicit inventory guards for prompts that combine NAS scope with file scope and count/shape terms.
- Kept `NAS是什么` and `你是谁` on normal Qwen chat so generic knowledge questions do not accidentally trigger file tools.

### Validation

- Local intent tests passed:
  - `NAS里有多少文件` -> `local_storage_inventory`
  - `nas里面有多少个文件` -> `local_storage_inventory`
  - `NAS里有什么文件` -> `local_storage_inventory`
  - `NAS文件分别是什么类型，占多大空间` -> `local_storage_inventory`
  - `NAS是什么` -> normal `local_qwen_chat`
  - `你是谁` -> no file tool
- S100P deployed backend compile: passed.
- User-level `openclaw-gateway.service`: restarted and active.
- API validation through `http://127.0.0.1:18765/api/copilot/chat`: passed.
  - `NAS里有多少文件` -> `assistant_mode=local_storage_inventory`, `nas_action.operation=inventory`, `cloud_used=false`
  - `NAS是什么` -> `assistant_mode=local_qwen_chat`
- Browser validation through `/ui#assistant` with `NAS里有多少文件`: passed.
  - The page showed `文件盘点`, `本地文件返回`, file count `164`, and no old Qwen fallback/refusal.

### Evidence Artifact

- `C:\Users\zhexu\AppData\Local\Temp\digua_ai_nas_count_prompt_final_20260706.png`
