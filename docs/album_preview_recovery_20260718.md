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
- S100P Python 3.11 grammar parse: passed.
- JavaScript syntax: passed.
- Full offline unit suite and GitHub CI: passed.
- Dedicated recovery coverage verifies 30 library photos are not capped at 24,
  assistant uploads are excluded from library scope, and text placeholders are
  rejected.

## Live acceptance

Merged delivery:

- Album fix: PR #44, merge commit `1cdc6aef1167a3ffe3844ce3fdb7a8a345baa405`.
- S100P Python 3.11 compatibility: PR #45, merge commit
  `54b80d63d19aa8f30d657c52383c6b2ba019ec91`.
- All required GitHub checks passed before each merge.

Deployment and rollback:

- Album runtime backup:
  `/mnt/nas/openclaw/reports/product_delivery/album_runtime_backups/20260717T163848Z`.
- Product-access backup:
  `/var/backups/digua-ai-nas/access-only-20260717T163851Z`.
- The deployed backend and web file hashes match merged source.
- `openclaw-gateway.service` and `digua-product-access.service` are active.
- `qwen25-local-openai-gateway.service` was already inactive, was not touched,
  and is not required by album indexing or preview.

Data recovery:

- The ten 27-37 byte placeholders were verified by exact relative path, size,
  SHA-256, and `Placeholder: ` content before mutation.
- All ten were moved through authenticated `/api/storage/trash` soft-delete,
  with 30-day retention and `physical_file_deleted=false`.
- Manifest and results:
  `/mnt/nas/openclaw/reports/qwen25_ai_nas/album_placeholder_cleanup_20260717T164046Z`.
- The canonical Picsum directory still contains exactly 100 files. The real
  Pexels assistant-search fixture remains present under `Personal/Uploads`.

Live API acceptance:

- `GET /api/media/summary?scope=library`: 100 photos, 223.0 ms.
- `GET /api/media/photos?limit=500&scope=library`: 100 photos, 223.2 ms.
- Unscoped indexed photos: 101 (100 library photos plus one real assistant fixture).
- First six library previews: 6/6 HTTP 200, valid JPEG signatures, 107.2-137.3 ms each.
- Deployed HTML serves cache version `20260718-album-recovery`.
- Acceptance JSON:
  `/mnt/nas/openclaw/reports/qwen25_ai_nas/album_placeholder_cleanup_20260717T164046Z/live_acceptance.json`.

Initial browser boundary:

- The deployed page opened successfully at
  `http://digua.local/ui?refresh=54b80d63#media` and rendered the current login
  boundary. Automated control was interrupted while entering the temporary
  visual-acceptance account, so an authenticated browser card-count screenshot
  is not claimed. The temporary account was removed from both identity stores.
- The scoped API count and real preview reads above are the production
  acceptance evidence for the first deployment.

Authenticated browser follow-up:

- User validation found two remaining presentation failures even though the
  NAS and preview APIs were healthy: the sidebar stayed at the disconnected
  placeholder on direct album/assistant entry, and fetched previews did not
  render.
- PR #50 (`9d10145a2fb0704842f26399a9aa4785e9bf4774`) loads
  `/api/storage/status` during every authenticated session restore and after
  login, allows local `blob:` image/media URLs in the product-access CSP, and
  advances the UI/service-worker caches to `20260718-live-media` and
  `digua-shell-v3`.
- All three required CI checks passed before merge. The access-only deployment
  preserved the backend and NAS data; rollback backup:
  `/var/backups/digua-ai-nas/access-only-20260717T172020Z`.
- The authenticated Chrome page at
  `http://digua.local/ui?refresh=9d10145a#media` rendered `327 GB / 2.0 TB`,
  `16%`, and 100 album rows. The same page's access log recorded the new static
  assets, `GET /api/storage/status` 200, scoped summary 200, and the first six
  preview requests 6/6 HTTP 200. The live `/ui` CSP includes
  `img-src 'self' data: blob:`. Browser control became unstable while capturing
  a screenshot, so a screenshot artifact is not claimed.

Deployment packaging follow-up:

- Preflight found that the product-access delivery builder omitted
  `configs/systemd/openclaw-gateway.service`, even though the installer requires
  it. Deployment used the same merged file as a bounded staging supplement.
- The builder now includes that file, and a contract test prevents recurrence.
