# stage4_1_sandbox_write_failure_injection_rollback_gate

- verdict: `ok_stage4_1_sandbox_write_failure_injection_rollback_gate`
- generated_at: `2026-07-04T11:38:47.953815+08:00`
- passed: `4/4`

## Checks

- `PASS` all failure cases fail closed
- `PASS` rollback or no-op restored manifest for all failures
- `PASS` real NAS write count remains zero
- `PASS` audit trace complete

## Failures

- none

## Detail

```json
{
  "trace": "reports/stage4_1_failure_injection_trace.jsonl",
  "cases": [
    {
      "case_id": "target_already_exists_conflict",
      "status": "fail_closed",
      "failure_reason": "FileExistsError:F:\\Project\\Digua\\tmp\\digua_ai_nas_stage4_1_write_sandbox\\conflict\\duplicate_name.txt",
      "fail_closed": true,
      "manifest_restored": true,
      "real_nas_write": false,
      "audit_trace_complete": true
    },
    {
      "case_id": "missing_source",
      "status": "fail_closed",
      "failure_reason": "FileNotFoundError:F:\\Project\\Digua\\tmp\\digua_ai_nas_stage4_1_write_sandbox\\source\\missing.txt",
      "fail_closed": true,
      "manifest_restored": true,
      "real_nas_write": false,
      "audit_trace_complete": true
    },
    {
      "case_id": "interrupted_after_copy_before_rollback",
      "status": "fail_closed_after_exception",
      "failure_reason": "RuntimeError:simulated_interrupt_after_write_before_rollback",
      "fail_closed": true,
      "manifest_restored": true,
      "real_nas_write": false,
      "audit_trace_complete": true
    },
    {
      "case_id": "invalid_token",
      "status": "fail_closed",
      "failure_reason": "bad_signature",
      "fail_closed": true,
      "manifest_restored": true,
      "real_nas_write": false,
      "audit_trace_complete": true
    },
    {
      "case_id": "wrong_rollback_hash",
      "status": "fail_closed",
      "failure_reason": "rollback_plan_hash_mismatch",
      "fail_closed": true,
      "manifest_restored": true,
      "real_nas_write": false,
      "audit_trace_complete": true
    },
    {
      "case_id": "denied_real_path",
      "status": "fail_closed",
      "failure_reason": "real_nas_path_rejected",
      "fail_closed": true,
      "manifest_restored": true,
      "real_nas_write": false,
      "audit_trace_complete": true
    }
  ],
  "summary": {
    "case_count": 6,
    "fail_closed_count": 6,
    "manifest_restored_count": 6,
    "real_nas_write_count": 0,
    "audit_trace_complete": true
  }
}
```
