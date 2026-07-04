# real_nas_preflight_dryrun_diff_gate

- verdict: `ok_real_nas_preflight_dryrun_diff_gate`
- generated_at: `2026-07-04T11:48:24.709152+08:00`
- passed: `4/4`

## Checks

- `PASS` dry-run diff report written
- `PASS` dry-run performed zero real writes
- `PASS` no destructive effect planned
- `PASS` candidate missing or invalid blocks safely, valid candidate stays dry-run only

## Failures

- none

## Detail

```json
{
  "diff_json": "reports/real_nas_preflight_dryrun_diff_redacted.json",
  "diff_md": "reports/real_nas_preflight_dryrun_diff_redacted.md",
  "diff": {
    "generated_at": "2026-07-04T11:48:24.707818+08:00",
    "dryrun_only": true,
    "candidate_present": false,
    "candidate_hash": null,
    "block_reason": "missing_explicit_candidate",
    "safe_block": true,
    "would_create_one_file": false,
    "would_modify_source": false,
    "would_delete_anything": false,
    "would_overwrite": false,
    "would_call_execute_copy": false,
    "would_call_rollback_copy": false,
    "approval_phrase_generated": false,
    "next_required_gate": "provide one explicit low-risk copy candidate before materialized dry-run diff"
  },
  "verdict_note": "safe_block_no_materialized_diff"
}
```
