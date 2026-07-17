# Media Album UI Fix - 2026-07-07

## Scope

This note records the S100P OpenClaw album UI fix for three operator-visible
issues:

- Photo rows in the album page showed no thumbnails.
- Double-clicking a photo row did not open an image preview.
- Album cards in the album list did not open the selected album.
- The image preview dialog initially had no zoom, rotation, fit/reset, or pan
  controls.

The fix applies to the authenticated local Web UI at `http://127.0.0.1:8765/ui`.
The gateway remains loopback-only.

## Environment

- Host: S100P over SSH as `sunrise@192.168.127.10`.
- Runtime root: `/mnt/nas/openclaw`.
- Service: `openclaw-gateway.service`.
- UI bundle: `web/static/digua_ai_nas_v2.js` and
  `web/static/digua_ai_nas_v2.css`.
- Backend modules:
  - `scripts/probes/ai_nas_operator_portal_server.py`
  - `scripts/probes/ai_nas_media.py`

## Cause

The album page rendered media-index photo records as static document rows. Those
records only carried the media database `path_hash`, so they were not compatible
with the existing storage preview route that expects a different storage hash.
The page also listed albums without a click handler that loaded album contents.

## Implemented Path

Backend:

- Added `GET /api/media/album?name=<album>` for authenticated album-detail
  reads.
- Added `GET /api/media/preview?path_hash=<media_path_hash>` for authenticated
  thumbnail and full preview reads.
- Added `MediaCenter.photo_path_by_hash(...)` so the server can resolve a media
  record internally without exposing the raw NAS path to the client.
- The preview route resolves the path under the configured Personal root and
  rechecks `state.can_read(user, relative_path)` before serving the file.

Frontend:

- Album cards are rendered as buttons with `data-action="mediaSelectAlbum"`.
- Selecting an album fetches `/api/media/album` and shows that album's photos.
- Photo-card grids use `/api/media/preview?path_hash=...&variant=thumbnail` and
  receive a longest-edge 480 px image when Pillow is available. The route is
  compatible with Pillow 9 and current Pillow releases.
- Photo cards are keyboard-focusable and double-clickable through the existing
  image viewer path.
- The selected album state can be cleared with the page action "show all".
- The image viewer now supports zoom in, zoom out, fit/reset, rotate, mouse
  wheel zoom, keyboard zoom shortcuts, and drag-to-pan.
- The image viewer fetches and browser-decodes the full preview independently;
  it does not reuse the bounded grid thumbnail as the original image.
- Empty, non-image, or undecodable Blob responses are evicted and retried once
  instead of being cached as successful viewer sources.
- A 12-second preview fetch timeout now switches the dialog to an explicit
  retry/failure state instead of leaving the operator on an infinite spinner.

## Verification

Local static checks:

```powershell
py -3 -m py_compile scripts\probes\ai_nas_operator_portal_server.py scripts\probes\ai_nas_media.py
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --check web\static\digua_ai_nas_v2.js
```

S100P deployment and service check:

```bash
python3 -m py_compile /mnt/nas/openclaw/scripts/probes/ai_nas_operator_portal_server.py /mnt/nas/openclaw/scripts/probes/ai_nas_media.py
systemctl --user restart openclaw-gateway.service
systemctl --user is-active openclaw-gateway.service
curl -fsS http://127.0.0.1:8765/api/health
```

Observed result:

- `openclaw-gateway.service`: `active`
- Health route: OK

Authenticated API check from Windows loopback:

- Album detail route returned `ok: true`.
- Selected album photo count: `3`.
- `raw_path_returned`: `false`.
- Preview route returned HTTP `200`.
- Preview `Content-Type`: `image/jpeg`.
- Preview payload size: `14051` bytes.

Browser UI check in the in-app browser:

- Main album page showed 3 album cards and 22 photo cards.
- The first viewport loaded 12 thumbnail images without console errors.
- Selecting album `smart classification acceptance records` opened the album.
- The selected album view showed 3 photo cards and 3 loaded thumbnails.
- Double-clicking the first selected-album photo opened the image viewer.
- The image viewer showed a blob-backed image with no error text.

Additional image viewer QA after zoom enhancement:

- Target image: `IMG_0001_recording_20260706_223105.png`.
- Opening the target image used a `blob:` object URL immediately.
- The viewer toolbar exposed `zoom out`, `zoom in`, `fit window`, and `rotate`.
- Zoom in changed the rendered state from `100%` to `120%`.
- Rotate changed the transform to include `rotate(90deg)`.
- Drag-to-pan changed the transform to include a nonzero translate offset.
- Fit/reset returned the transform to `translate(0px, 0px) rotate(0deg)
  scale(1)` and zoom text to `100%`.
- Browser console check had no error or warning entries.

## Boundaries

- No raw filesystem path is returned by the new album or preview routes.
- The preview route remains authenticated and ACL-checked.
- No NAS-wide permission expansion was made.
- No public gateway exposure was added.
- This is a Web UI and local API interaction fix. It does not claim mobile app
  parity or production-grade face/person identity recognition.

## 7.9 Reliability Recheck - 2026-07-18

- S100P current media rows: 101 valid RGB JPEG files.
- Bounded thumbnail production gate: 101/101 passed, longest edge 480 px,
  aggregate response size about 3.17 MB.
- Largest-five original preview gate: 5/5 passed; the 6000×3376 source remained
  full resolution in the viewer path.
- Media list and album payloads now use the same ACL decision as the preview
  endpoint, so an inaccessible photo is not rendered as a permanently broken
  card.
