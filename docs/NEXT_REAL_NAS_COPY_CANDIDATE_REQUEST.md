# Next Real NAS Copy Candidate Request

To progress beyond the current safe block, provide exactly one candidate JSON file with this schema:

```json
{
  "action_type": "copy",
  "source_relative_path": "Documents/example.txt",
  "target_relative_path": "Collections/CodexPreflight/example.txt",
  "source_sha256": "<64 hex chars from a separate readonly hash check>",
  "expected_size_bytes": 12345,
  "source_owner_scope": "operator_owned",
  "target_exists_now": false
}
```

Rules:

- Paths are relative to `/mnt/nas/openclaw/Personal` and must not start with `Personal/`.
- Target must start with `Collections/`.
- First candidate must be a single file and <= 1048576 bytes.
- No delete, chmod, overwrite, recursive operation, move, or rename.
- No cloud-derived writes and no Qwen autonomous writes.
- This candidate enables only a materialized dry-run diff, not execution.
