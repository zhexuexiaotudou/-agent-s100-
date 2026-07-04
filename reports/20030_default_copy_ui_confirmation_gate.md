# default_copy_ui_confirmation_gate

- verdict: `ok_default_copy_ui_confirmation_gate`
- generated_at: `2026-07-04T14:35:47.478413+08:00`
- passed: `6/6`

## Checks

- `PASS` UI assets exist
- `PASS` desktop and mobile render evidence exists
- `PASS` UI contains confirmation and dispatcher boundary text
- `PASS` UI contains sanitized harness status panel
- `PASS` UI does not expose forbidden action controls
- `PASS` UI does not include private raw content markers

## Failures

- none

## Detail

```json
{
  "html": "web/templates/copy_confirm.html",
  "js": "web/static/copy_confirm.js",
  "status_js": "web/static/harness_status.js",
  "css": "web/static/copy_confirm.css",
  "desktop": "evidence/stage5_default_service/screenshots/desktop_static_render.txt",
  "mobile": "evidence/stage5_default_service/screenshots/mobile_static_render.txt"
}
```
