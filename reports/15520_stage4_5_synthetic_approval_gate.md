# stage4_5_synthetic_approval_gate

- verdict: `ok_stage4_5_synthetic_approval_gate`
- generated_at: `2026-07-04T13:57:36.802436+08:00`
- passed: `7/7`

## Checks

- `PASS` candidate exists from self-created synthetic source
- `PASS` operator approval file created and scoped
- `PASS` approval forbids destructive and autonomous actions
- `PASS` approval manifest has valid one-action copy proposal
- `PASS` manifest hash is self-consistent
- `PASS` manifest copied to S100P report root
- `PASS` policy still copy-only

## Failures

- none

## Detail

```json
{
  "candidate_json": "operator_candidates/stage4_5_self_created_synthetic_route_candidate.json",
  "approval_json": "operator_approval/stage4_5_self_created_synthetic_route_execute_approved.json",
  "manifest_json": "operator_candidates/stage4_5_self_created_synthetic_route_approval_manifest.json",
  "remote_manifest_path": "/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/approval_manifest.json",
  "manifest_id": "apm-f96cdcaac8399b5c",
  "manifest_sha256": "69f33f4910640280cfc7062ebb7d1c144256d7b82a9d689c66b4c3dc109a97c9",
  "scp": {
    "returncode": 0,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_tail": ""
  }
}
```
