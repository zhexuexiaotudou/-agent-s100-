# real_nas_copy_candidate_execute_rollback_gate

- verdict: `ok_real_nas_copy_candidate_execute_rollback_gate`
- generated_at: `2026-07-04T12:03:57.522849+08:00`
- passed: `8/8`

## Checks

- `PASS` remote setup and scp succeeded
- `PASS` remote real NAS copy test process returned zero
- `PASS` source synthetic file created and retained
- `PASS` copy verified by target sha256
- `PASS` rollback removed copied target only
- `PASS` no existing user file touched
- `PASS` OpenClaw/Qwen health OK before and after
- `PASS` protected ports unchanged

## Failures

- none

## Detail

```json
{
  "run_id": "real_nas_copy_candidate_20260704-120353",
  "remote_tmp": "/tmp/digua_real_nas_copy_candidate_real_nas_copy_candidate_20260704-120353",
  "remote_report_root": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353",
  "local_evidence_json": "evidence/real_nas_copy_candidate_test_latest.json",
  "local_evidence_md": "evidence/real_nas_copy_candidate_test_latest.md",
  "remote_run": {
    "returncode": 0,
    "elapsed_ms": 548.938,
    "stdout_hash": "b8809b15e568379b015e291a1e7a54a361a020bc3091286403be3cbd77596920",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "\"rollback_failed_count\": 0, \"rollback_json\": \"/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_rollback_copy_20260704-120358-531115/action_rollback_copy.json\", \"rollback_manifest\": \"/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_execute_copy_20260704-120358-412357/rollback_manifest.json\", \"rollback_removed_count\": 1, \"rollback_result\": {\"returncode\": 0, \"stderr_tail\": \"\", \"stdout_tail\": \"/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_rollback_copy_20260704-120358-531115/action_rollback_copy.md\\n/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_rollback_copy_20260704-120358-531115/action_rollback_copy.json\\n\"}, \"rollback_verified\": true, \"run_id\": \"real_nas_copy_candidate_20260704-120353\", \"source_absolute_path\": \"/mnt/nas/openclaw/Personal/Collections/CodexPreflight/source/real_nas_copy_candidate_20260704-120353_source.txt\", \"source_created\": true, \"source_existed_before\": false, \"source_modified_after_copy_or_rollback\": false, \"source_relative_path\": \"Collections/CodexPreflight/source/real_nas_copy_candidate_20260704-120353_source.txt\", \"source_retained\": true, \"source_sha256\": \"78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea\", \"source_sha256_after\": \"78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea\", \"source_size_bytes\": 229, \"status\": \"passed\", \"target_absolute_path\": \"/mnt/nas/openclaw/Personal/Collections/CodexPreflight/target/real_nas_copy_candidate_20260704-120353_copied.txt\", \"target_existed_before\": false, \"target_missing_after_rollback\": true, \"target_relative_path\": \"Collections/CodexPreflight/target/real_nas_copy_candidate_20260704-120353_copied.txt\", \"target_sha256_after_copy\": \"78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea\", \"target_size_after_copy\": 229, \"unexpected_existing_path\": false}\n"
  },
  "parsed_result": {
    "action_id": "copy-8cc4bc19a64f5085",
    "approval_phrase_hash": "9664c05c9a25372ce1ed6b5ca6389d155e8fbe9c4f04b96d32e0a7b294e5bcdb",
    "candidate_json": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/real_nas_copy_candidate.json",
    "checks": {
      "copy_verified": true,
      "existing_user_file_touched": false,
      "rollback_verified": true,
      "source_created": true,
      "source_hash_unchanged": true,
      "source_retained": true,
      "target_absent_before": true,
      "target_missing_after_rollback": true
    },
    "copy_verified": true,
    "errors": [],
    "execute_result": {
      "returncode": 0,
      "stderr_tail": "",
      "stdout_tail": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_execute_copy_20260704-120358-412357/action_execute_copy.md\n/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_execute_copy_20260704-120358-412357/action_execute_copy.json\n"
    },
    "execution_json": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_execute_copy_20260704-120358-412357/action_execute_copy.json",
    "generated_at": "2026-07-04T12:03:58.309522+08:00",
    "manifest_id": "apm-dcbc69f49f6632f5",
    "manifest_path": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/real_nas_copy_approval_manifest.json",
    "personal_root": "/mnt/nas/openclaw/Personal",
    "real_nas_write_scope": "create synthetic source, copy to synthetic target, rollback copied target only",
    "rollback_failed_count": 0,
    "rollback_json": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_rollback_copy_20260704-120358-531115/action_rollback_copy.json",
    "rollback_manifest": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_execute_copy_20260704-120358-412357/rollback_manifest.json",
    "rollback_removed_count": 1,
    "rollback_result": {
      "returncode": 0,
      "stderr_tail": "",
      "stdout_tail": "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_rollback_copy_20260704-120358-531115/action_rollback_copy.md\n/mnt/nas/openclaw/reports/real_nas_copy_candidate_test/real_nas_copy_candidate_20260704-120353/action_rollback_copy_20260704-120358-531115/action_rollback_copy.json\n"
    },
    "rollback_verified": true,
    "run_id": "real_nas_copy_candidate_20260704-120353",
    "source_absolute_path": "/mnt/nas/openclaw/Personal/Collections/CodexPreflight/source/real_nas_copy_candidate_20260704-120353_source.txt",
    "source_created": true,
    "source_existed_before": false,
    "source_modified_after_copy_or_rollback": false,
    "source_relative_path": "Collections/CodexPreflight/source/real_nas_copy_candidate_20260704-120353_source.txt",
    "source_retained": true,
    "source_sha256": "78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea",
    "source_sha256_after": "78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea",
    "source_size_bytes": 229,
    "status": "passed",
    "target_absolute_path": "/mnt/nas/openclaw/Personal/Collections/CodexPreflight/target/real_nas_copy_candidate_20260704-120353_copied.txt",
    "target_existed_before": false,
    "target_missing_after_rollback": true,
    "target_relative_path": "Collections/CodexPreflight/target/real_nas_copy_candidate_20260704-120353_copied.txt",
    "target_sha256_after_copy": "78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea",
    "target_size_after_copy": 229,
    "unexpected_existing_path": false
  },
  "before_ports": {
    "ports": [
      8765,
      18080,
      18888,
      18889
    ],
    "stdout": "LISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \nLISTEN 0      511            [::1]:18765         [::]:*                                       \n",
    "stdout_hash": "4170b1d0f75ae557d7940ef33784686dac6599043a03b2a83cb298f28127b891",
    "returncode": 0
  },
  "after_ports": {
    "ports": [
      8765,
      18080,
      18888,
      18889
    ],
    "stdout": "LISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \nLISTEN 0      511            [::1]:18765         [::]:*                                       \n",
    "stdout_hash": "4170b1d0f75ae557d7940ef33784686dac6599043a03b2a83cb298f28127b891",
    "returncode": 0
  }
}
```
