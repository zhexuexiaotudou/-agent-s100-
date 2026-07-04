# stage4_5_route_execute_canary_gate

- verdict: `ok_stage4_5_route_execute_canary_gate`
- generated_at: `2026-07-04T13:57:39.042656+08:00`
- passed: `9/9`

## Checks

- `PASS` candidate exists for execute canary
- `PASS` source still matches and target absent immediately before execute
- `PASS` route guard authorizes execute only under scoped canary
- `PASS` allowlisted dispatcher execute ran
- `PASS` exactly one copy executed
- `PASS` target hash equals source hash after execute
- `PASS` source retained unchanged after execute
- `PASS` execute audit forbids delete/move/overwrite
- `PASS` execute trace has no raw paths/private content

## Failures

- none

## Detail

```json
{
  "trace": "reports/stage4_5_route_execute_trace.jsonl",
  "pre_execute_verify": {
    "source_exists": true,
    "source_is_file": true,
    "source_is_symlink": false,
    "source_relative_path": "Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt",
    "source_sha256": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c",
    "source_sha256_matches": true,
    "source_size_bytes": 199,
    "target_exists": false,
    "target_is_symlink": false,
    "target_parent_exists": true,
    "target_parent_is_symlink": false,
    "target_relative_path": "Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt"
  },
  "route_decision": {
    "allowed": true,
    "route": "execute",
    "status": "execute_authorized_for_allowlisted_dispatcher",
    "reason_codes": [],
    "response": {
      "route": "execute",
      "status": "execute_authorized_for_allowlisted_dispatcher",
      "action_type": "copy",
      "candidate_fingerprint": "9845850926bccef5ba5aeb9b9d39ada668e9a4a7821958e727f97f6e0d6b62c7",
      "source_path_hash": "c3f8de23135918ad682a2e22e1d7e8fabc4f062c48b1e0d6cc9fe17e4eca89b8",
      "target_path_hash": "bb91fbd04ec4d493fb5ffec67a573bda42fbe61dec72c668b146865f86835cf2",
      "source_sha256_prefix": "7c17e4552a22",
      "expected_size_bytes": 199,
      "target_root": "Collections",
      "raw_paths_in_response": false,
      "private_content_in_response": false,
      "dispatcher_tool": "ai_nas_action_execute_copy",
      "execution_performed_by_guard": false,
      "writes_performed": false,
      "blocked_safely": false
    },
    "audit_event": {
      "event_id": "copy-route-df4b809096f54b05",
      "tool_id": "ai_nas_route_copy_guard_v1",
      "route": "execute",
      "allowed": true,
      "reason_codes": [],
      "candidate_fingerprint": "9845850926bccef5ba5aeb9b9d39ada668e9a4a7821958e727f97f6e0d6b62c7",
      "source_path_hash": "c3f8de23135918ad682a2e22e1d7e8fabc4f062c48b1e0d6cc9fe17e4eca89b8",
      "target_path_hash": "bb91fbd04ec4d493fb5ffec67a573bda42fbe61dec72c668b146865f86835cf2",
      "args_hash": "efbd843bbaca4b4b67fe633768930c8a07e177a652d084af38764dc974d3ec31",
      "qwen_execution_authority": false,
      "cloud_private_egress": false,
      "raw_private_content_logged": false,
      "dispatcher_tool": "ai_nas_action_execute_copy",
      "execution_performed_by_guard": false,
      "operator_approved": true,
      "env_enabled": true,
      "approval_file_present": true,
      "token_validation_reason": "approval_token_ok"
    }
  },
  "dispatcher_run": {
    "returncode": 0,
    "elapsed_ms": 400.356,
    "stdout_hash": "616e989164e5f4e075f64b006ffdcec18f443687590da75b134f1e92509d9ed3",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c\", \"source_absolute_path\": \"/mnt/nas/openclaw/Personal/Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt\", \"source_relative_path\": \"Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt\", \"source_sha256\": \"7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c\", \"target_absolute_path\": \"/mnt/nas/openclaw/Personal/Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt\", \"target_relative_path\": \"Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt\"}], \"rollback_allowed\": true, \"rollback_policy\": \"remove only copied targets listed here after verifying target_sha256; never touch source files\", \"source_execution_tool\": \"ai_nas_action_execute_copy\"}, \"status\": \"completed\", \"tool_id\": \"ai_nas_action_execute_copy\"}, \"returncode\": 0, \"rollback_manifest_path\": \"/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/rollback_manifest.json\", \"source_exists_after\": true, \"source_sha256_after\": \"7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c\", \"started_at\": \"2026-07-04T13:57:41+08:00\", \"stderr_hash\": \"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\", \"stderr_tail\": \"\", \"stdout_hash\": \"cb6d64c7357cf98790b699568311435c3cba9dfe8aff1c8b1b6addac2eef49a9\", \"stdout_tail\": \"/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/action_execute_copy.md\\n/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/action_execute_copy.json\\n\", \"target_exists_after\": true, \"target_sha256_after\": \"7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c\"}\n"
  },
  "dispatcher_result": {
    "action": "execute",
    "report_path": "/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/action_execute_copy.json",
    "report_payload": {
      "approval_phrase_accepted": true,
      "audit": {
        "copy_performed": true,
        "delete_performed": false,
        "move_performed": false,
        "overwrite_performed": false,
        "source_files_modified": false,
        "writes": "copied files under Personal/Collections plus Markdown/JSON execution and rollback manifests"
      },
      "executed_actions": [
        {
          "action_id": "copy-f2b798dc7adfe1ec",
          "delete_source": false,
          "move_source": false,
          "overwrite": false,
          "source_absolute_path": "/mnt/nas/openclaw/Personal/Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt",
          "source_relative_path": "Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt",
          "source_sha256": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c",
          "status": "copied",
          "target_absolute_path": "/mnt/nas/openclaw/Personal/Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt",
          "target_relative_path": "Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt",
          "target_sha256": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c"
        }
      ],
      "executed_count": 1,
      "failed_actions": [],
      "failed_count": 0,
      "generated_at": "2026-07-04T13:57:41.403847+08:00",
      "manifest_id": "apm-f96cdcaac8399b5c",
      "manifest_path": "/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/approval_manifest.json",
      "personal_root": "/mnt/nas/openclaw/Personal",
      "requested_action_count": 1,
      "rollback_manifest": {
        "generated_at": "2026-07-04T13:57:41.403797+08:00",
        "manifest_id": "apm-f96cdcaac8399b5c",
        "rollback_actions": [
          {
            "action_id": "copy-f2b798dc7adfe1ec",
            "expected_target_sha256": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c",
            "source_absolute_path": "/mnt/nas/openclaw/Personal/Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt",
            "source_relative_path": "Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt",
            "source_sha256": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c",
            "target_absolute_path": "/mnt/nas/openclaw/Personal/Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt",
            "target_relative_path": "Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt"
          }
        ],
        "rollback_allowed": true,
        "rollback_policy": "remove only copied targets listed here after verifying target_sha256; never touch source files",
        "source_execution_tool": "ai_nas_action_execute_copy"
      },
      "status": "completed",
      "tool_id": "ai_nas_action_execute_copy"
    },
    "returncode": 0,
    "rollback_manifest_path": "/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/rollback_manifest.json",
    "source_exists_after": true,
    "source_sha256_after": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c",
    "started_at": "2026-07-04T13:57:41+08:00",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_tail": "",
    "stdout_hash": "cb6d64c7357cf98790b699568311435c3cba9dfe8aff1c8b1b6addac2eef49a9",
    "stdout_tail": "/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/action_execute_copy.md\n/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/action_execute_copy.json\n",
    "target_exists_after": true,
    "target_sha256_after": "7c17e4552a221e467550974c8007f3a1fabb75ab30b1f75908f675c7482cb09c"
  },
  "executed_action_count": 1,
  "rollback_manifest_path": "/mnt/nas/openclaw/reports/stage4_5_route_canary_stage4_5_self_created_route_canary_20260704-135733/reports/action_execute_copy_20260704-135741-403876/rollback_manifest.json"
}
```
