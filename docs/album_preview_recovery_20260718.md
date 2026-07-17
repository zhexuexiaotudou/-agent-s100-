# Album preview recovery acceptance (2026-07-18)

## Problem verified

The live album page mixed three separate behaviors:

- `/api/media/summary` returned only the newest 24 indexed images before the UI requested the full list.
- Opening the page synchronously ran `POST /api/ai-album/auto-organize`, delaying the first usable render.
- Ten 27-37 byte text placeholders with `.jpg`/`.png` suffixes were indexed as images and sorted before the real photo corpus.

The canonical album corpus remains the 100 Picsum photos under
`Personal/Photos/picsum_replacement_20260707`. A separate real Pexels upload is
used by assistant visual-search acceptance and must remain available to that
workflow without changing the album count.

## Implementation

- The web album now requests `scope=library`, which limits album rows and stats
  to `Personal/Photos` while leaving other indexed images available to assistant
  and file workflows.
- The scoped summary returns the complete bounded photo list instead of the
  legacy 24-row preview.
- Page entry is read-only and no longer waits for automatic organization.
  Explicit refresh/organize actions remain available.
- Preview hydration starts with six visible candidates and uses a four-request
  concurrency queue plus browser lazy decoding.
- Album uploads now target `Personal/Photos/Uploads`, so they remain in the
  visible library. The generic `Personal/Uploads` workflow is unchanged.
- Media indexing validates image signatures and removes stale index rows for
  text files masquerading as supported image formats. Media upload rejects the
  same invalid content before writing it.
- `sync_upstream_album_runtime.sh` updates only the media/index portal runtime,
  backs up both replaced files, restarts only the user-scoped OpenClaw portal,
  verifies health and hashes, and automatically restores on failure.

## Local verification

- Python compile: passed.
- JavaScript syntax: passed.
- Full offline unit suite: 174/174 passed.
- Dedicated recovery coverage verifies 30 library photos are not capped at 24,
  assistant uploads are excluded from library scope, and text placeholders are
  rejected.

## Live acceptance

Pending merge and deployment. The final record must include the merged commit,
runtime backup path, ten soft-delete records, scoped API count, loaded browser
card count, preview success sample, and rollback point.
