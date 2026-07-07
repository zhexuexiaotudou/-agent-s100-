# 2026-07-07 manual trash soft-delete acceptance

## Scope

This record covers the manual delete option requested for AI assistant evidence cards and the unified album page.

The implemented behavior is a controlled soft-delete:

- Openable AI assistant document evidence can show a trash button when it has a Personal relative path.
- Openable AI assistant image results can show a trash button when they have a media `path_hash`.
- Album photo cards show a trash button when the indexed photo has a `path_hash`.
- The browser calls `POST /api/storage/trash`; it does not call a permanent delete endpoint.
- The server moves eligible Personal files into `.trash` and records `expires_at` 30 days after deletion.
- Expired trash entries are cleaned by `SnapshotStore.cleanup_expired_trash(30)`, including a startup cleanup call.

## Safety boundary

- This is manual user-triggered soft-delete only.
- Qwen still has no autonomous NAS write/delete authority.
- Only files under the configured Personal root can be trashed.
- `.trash`, `.snapshots`, and `.versions` recovery areas are protected.
- Files from demo/material roots outside Personal can still be previewed where allowed, but trashing them is rejected.
- The UI does not return raw filesystem paths; it sends `relative_path` for documents or `path_hash` for photos.

## Code changes

- `scripts/probes/ai_nas_snapshot.py`
  - Adds `expires_at` to trash entries, with an idempotent SQLite migration.
  - Adds `cleanup_expired_trash(30)` for permanent cleanup after retention.
- `scripts/probes/ai_nas_media.py`
  - Adds `photo_path_by_hash()` and `remove_photo_path()` so deleted album photos disappear from the media index.
- `scripts/probes/ai_nas_operator_portal_server.py`
  - Adds `GET /api/storage/trash`.
  - Adds `POST /api/storage/trash`.
  - Adds `POST /api/storage/trash/cleanup`.
  - Restricts trash operations to Personal files with read and write ACL.
- `web/static/digua_ai_nas_v2.js`
  - Adds trash buttons to openable document evidence, image search results, media photo cards, and legacy AI album cards.
  - Adds a confirmation workflow and refreshes current views after success.
  - Prevents the trash button from triggering double-click open handlers.
- `web/static/digua_ai_nas_v2.css`
  - Adds local styles for trash buttons, evidence-card actions, and confirmation panels.
- `tests/test_storage_trash_soft_delete.py`
  - Verifies path-hash photo trash moves the file into `.trash`, removes the media index row, and keeps a 30-day retention record.
  - Verifies expired trash cleanup removes unrestored trash files.
- `tests/test_ui_v2_security_boundaries.py`
  - Verifies the UI uses `storageTrash...` soft-delete actions and no permanent delete API.

## Local validation

- `python -m py_compile scripts/probes/ai_nas_operator_portal_server.py scripts/probes/ai_nas_snapshot.py scripts/probes/ai_nas_media.py`: passed.
- `node --check web/static/digua_ai_nas_v2.js`: passed.
- `python -m unittest -v tests.test_ui_v2_security_boundaries tests.test_storage_trash_soft_delete`: passed, 7 tests.
- `python -m unittest -v tests.test_document_fts_rag tests.test_copilot_local_qwen_chat`: passed, 20 tests.

## Live S100P validation

- Files synced to `/mnt/nas/openclaw` on S100P.
- Remote syntax/tests:
  - `python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py scripts/probes/ai_nas_snapshot.py scripts/probes/ai_nas_media.py`: passed.
  - `node --check web/static/digua_ai_nas_v2.js`: passed.
  - `python3 -m unittest -v tests.test_ui_v2_security_boundaries tests.test_storage_trash_soft_delete`: passed, 7 tests.
  - `python3 -m unittest -v tests.test_document_fts_rag tests.test_copilot_local_qwen_chat`: passed, 20 tests.
- Portal restarted on port `8765`; `/api/health` returned HTTP 200.
- API soft-delete probe:
  - Uploaded `Inbox/codex_trash_probe_1783430559.txt`.
  - `POST /api/storage/trash` returned HTTP 200, `moved_to_trash=true`, `physical_file_deleted=false`, `retention_days=30`.
  - Authenticated download of the original path after trash returned HTTP 404 `file_not_found`.
- API image path-hash probe:
  - Uploaded a temporary PNG to `Uploads`.
  - Preview before trash returned HTTP 200.
  - `POST /api/storage/trash` by `path_hash` returned HTTP 200, `moved_to_trash=true`, `media_index.removed=1`.
  - Preview after trash returned HTTP 404 `preview_not_found_or_not_authorized`, `raw_path_returned=false`.
- Browser UI probe:
  - Opened `http://127.0.0.1:8765/ui?refresh=trash-soft-delete-20260707#media`.
  - Visible page title was `相册`.
  - The first rendered batch had 24 photo cards and 24 `storageTrashPrompt` buttons, each with `data-trash-kind="image"` and `data-trash-path-hash`.
  - Asked the AI assistant `2026年5月20日家庭开支账单金额是多少？`.
  - The answer included `1314`, badge `本地文档返回`, 2 openable document evidence cards, and 2 document trash buttons with `data-trash-relative-path`.
  - Opened the trash confirmation workflow for one document evidence card and cancelled it; the real document was not trashed during UI confirmation testing.
