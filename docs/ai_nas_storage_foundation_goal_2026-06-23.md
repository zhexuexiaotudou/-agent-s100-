# AI-NAS Storage Foundation Goal 1

## Scope

Goal 1 closes the NAS storage foundation before AI demo features. The bounded
data root is:

```text
/mnt/nas/openclaw/Personal
```

Standard first-level data directories are `Movies`, `Documents`, `Photos`, and
`Inbox`. All web file operations resolve requested paths under this Personal
root before touching the filesystem.

## Implemented Surface

- Disk/root discovery, writable check, mount metadata, and capacity statistics:
  `GET /api/storage/status`
- Directory browsing:
  `GET /api/storage/list?path=<relative-path>`
- Download:
  `GET /api/storage/download?path=<relative-file-path>`
- Upload:
  `POST /api/storage/upload?path=<relative-directory>`
- Rename:
  `POST /api/storage/rename`
- Move:
  `POST /api/storage/move`
- Copy:
  `POST /api/storage/copy`
- Delete:
  `DELETE /api/storage/file?path=<relative-path>`

The operator portal injects a `NAS Storage` section that uses these APIs for
browser-side file management.

## Safety Rules

- Absolute paths and `..` traversal are rejected before filesystem access.
- Upload, rename, move, and copy refuse to overwrite existing targets.
- Delete refuses the Personal root and refuses non-empty directories.
- File operations are recorded in SQLite `file_operations`.
- Index scans maintain `sha256`, `mtime_ns`, `mtime`, and `size_bytes` in
  SQLite `records`.

## Gate

Run:

```powershell
C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\probes\ai_nas_storage_foundation_gate_probe.py --report-root tmp\nas_storage_foundation_gate_local --file-count 10000
```

Latest passing local gate:

```text
tmp\nas_storage_foundation_gate_local\nas_storage_foundation_gate_20260623-020641-752390\nas_storage_foundation_gate.json
```

Verdict:

```text
ok_nas_storage_foundation_gate
```

The gate starts the portal server, performs real HTTP browse/upload/download/
rename/copy/move/delete calls, verifies traversal blocking, creates 10000 files,
builds the SQLite index, checks operation logs, and runs SQLite integrity and
quick checks.

## Service Command

For the deployed S100P/NAS target:

```bash
python3 /mnt/nas/openclaw/scripts/probes/ai_nas_operator_portal_server.py \
  --bind 0.0.0.0 \
  --port 8765 \
  --report-root /mnt/nas/openclaw/reports/ai_nas_mvp \
  --personal-root /mnt/nas/openclaw/Personal \
  --sqlite-index-path /mnt/nas/openclaw/reports/ai_nas_mvp/personal_inventory.sqlite3 \
  --storage-max-files 50000
```
