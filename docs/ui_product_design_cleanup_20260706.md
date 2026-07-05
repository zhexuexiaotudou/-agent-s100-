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
