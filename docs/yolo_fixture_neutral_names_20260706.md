# YOLO fixture neutral-name verification, 2026-07-06

## Scope

This note records the S100P-side rename of the YOLO v2 demo fixture files from
object-descriptive names to neutral camera-style names. The goal is to avoid a
customer-facing demo that appears to retrieve results by filename.

Host checked:

- SSH target: `sunrise@192.168.127.10`
- OpenClaw service: `openclaw-gateway.service` active
- Qwen service: `qwen25-local-openai-gateway.service` active
- Fixture root: `/mnt/nas/openclaw/yolo_v2_fixture`

## Rename Map

Images:

- `images/laptop_book_keyboard_mouse_tv.jpg` -> `images/IMG_20260705_0001.jpg`
- `images/person_car_street.jpg` -> `images/IMG_20260705_0002.jpg`
- `images/person_bus_stop_sign.jpg` -> `images/IMG_20260705_0003.jpg`
- `images/person_kite_scene.jpg` -> `images/IMG_20260705_0004.jpg`

Videos:

- `videos/laptop_book_keyboard_mouse_tv.mp4` -> `videos/VID_20260705_0001.mp4`
- `videos/person_car_street.mp4` -> `videos/VID_20260705_0002.mp4`
- `videos/person_bus_stop_sign.mp4` -> `videos/VID_20260705_0003.mp4`
- `videos/person_kite_scene.mp4` -> `videos/VID_20260705_0004.mp4`

Post-rename fixture listing:

```text
images/IMG_20260705_0001.jpg
images/IMG_20260705_0002.jpg
images/IMG_20260705_0003.jpg
images/IMG_20260705_0004.jpg
videos/VID_20260705_0001.mp4
videos/VID_20260705_0002.mp4
videos/VID_20260705_0003.mp4
videos/VID_20260705_0004.mp4
```

## Rebuild Evidence

Both the active service DB and the legacy runbook DB were rebuilt so no checked
runtime index keeps the old object-descriptive titles.

Active service DB:

- DB: `/mnt/nas/openclaw/reports/qwen25_ai_nas/yolo_index/runtime/yolo_index.db`
- Evidence run: `/mnt/nas/openclaw/reports/qwen25_ai_nas/yolo_index/evidence/yolo_run_8c8800ceba5e4e1b`
- Assets: 8
- Images: 4
- Videos: 4
- Keyframes: 4
- Detections: 66
- Errors: 0

Legacy runbook DB:

- DB: `/mnt/nas/openclaw/reports/yolo_index/runtime/yolo_index.db`
- Evidence run: `/mnt/nas/openclaw/reports/yolo_index/evidence/yolo_run_b59f73fc467147bb`
- Assets: 8
- Images: 4
- Videos: 4
- Keyframes: 4
- Detections: 66
- Errors: 0

Both DBs now report titles like `IMG 20260705 0002` and
`VID 20260705 0002`; no asset title in either DB uses the old
`person/car/bus/kite/laptop/book/keyboard/mouse/tv/stop sign` fixture names.

## Customer-Path Verification

Authentication:

- Endpoint: `POST http://127.0.0.1:8765/api/identity/login`
- User: `admin`
- Result: HTTP 200, token returned

Direct YOLO search:

- Endpoint: `POST http://127.0.0.1:8765/api/yolo-index/search`
- Query semantic: find images with people
- Modality: `image`
- Labels: `["person"]`
- Result count: 3
- Titles: `IMG 20260705 0002`, `IMG 20260705 0003`, `IMG 20260705 0004`
- Privacy: `raw_path_returned=false`, `cloud_used=false`

AI assistant path:

- Endpoint: `POST http://127.0.0.1:8765/api/copilot/chat`
- Query semantic: find images with people
- Route: `local_yolo_search`
- Labels: `["person"]`
- Result count: 3
- Display names:
  - `IMG_20260705_0002.jpg`
  - `IMG_20260705_0003.jpg`
  - `IMG_20260705_0004.jpg`

Preview check:

- First result: `IMG_20260705_0002.jpg`
- Preview endpoint returned HTTP 200
- Content-Type: `image/jpeg`
- First bytes: `ffd8ffe0...`
- JPEG magic: true

## Notes

- One intermediate HTTP test using a PowerShell here-string sent Chinese text
  through SSH stdin and produced a false negative due to local encoding. The
  final verification constructed the Chinese query with Unicode escapes on the
  S100P side and passed.
- The search result is still an object-detection result. `person` only means
  the YOLO index detected a person-class object; it is not face recognition and
  does not identify a specific person.
- No model weights, raw filesystem paths, or private media were committed.
