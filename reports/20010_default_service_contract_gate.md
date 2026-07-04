# default_service_contract_gate

- verdict: `ok_default_service_contract_gate`
- generated_at: `2026-07-04T14:35:38.990367+08:00`
- passed: `7/7`

## Checks

- `PASS` contract and config files exist
- `PASS` default service enabled
- `PASS` copy execute enabled only with required gates
- `PASS` delete/move/rename/chmod disabled
- `PASS` Qwen tool execution disabled
- `PASS` cloud private raw egress disabled
- `PASS` copy route policy includes Stage5 smoke prefixes

## Failures

- none

## Detail

```json
{
  "feature_flags": {
    "harness_default_service_enabled": true,
    "readonly_workspaces_enabled": true,
    "token_budget_gate_enabled": true,
    "privacy_redaction_gate_enabled": true,
    "copy_preview_enabled": true,
    "copy_dry_run_enabled": true,
    "copy_confirm_enabled": true,
    "copy_execute_enabled": true,
    "copy_rollback_enabled": true,
    "copy_execute_requires_user_confirmation": true,
    "copy_execute_requires_signed_token": true,
    "copy_execute_requires_source_rehash": true,
    "copy_execute_requires_target_absent": true,
    "copy_execute_requires_dispatcher": true,
    "copy_execute_max_file_size_bytes": 1048576,
    "copy_execute_allowed_target_prefixes": [
      "Collections/"
    ],
    "copy_execute_disallow_overwrite": true,
    "delete_enabled": false,
    "move_enabled": false,
    "rename_enabled": false,
    "chmod_enabled": false,
    "chown_enabled": false,
    "recursive_copy_enabled": false,
    "qwen_tool_execution_enabled": false,
    "cloud_private_raw_egress_enabled": false
  },
  "policy": {
    "policy_id": "digua_stage5_harness_default_service_policy_v1",
    "default_service_role": "policy_first_openclaw_middleware",
    "readonly_workspaces": [
      "nas_search",
      "document_rag",
      "media_photo",
      "admin_audit"
    ],
    "write_workspaces": [
      "nas_action"
    ],
    "allowed_write_actions": [
      "copy"
    ],
    "forbidden_actions": [
      "delete",
      "move",
      "rename",
      "chmod",
      "chown",
      "overwrite",
      "recursive",
      "recursive_delete",
      "arbitrary_shell"
    ],
    "copy_route": {
      "route_guard": "src.harness.copy_route_guard",
      "execute_tool_id": "ai_nas_action_execute_copy",
      "rollback_tool_id": "ai_nas_action_rollback_copy",
      "dispatcher": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh",
      "source_prefixes": [
        "Collections/CodexPreflight/source/",
        "Collections/CodexPreflight/stage5_default_service/source/"
      ],
      "target_prefixes": [
        "Collections/CodexPreflight/target/",
        "Collections/CodexPreflight/stage5_default_service/target/"
      ],
      "target_root_prefix": "Collections/",
      "max_file_size_bytes": 1048576,
      "requires_preview": true,
      "requires_dry_run": true,
      "requires_typed_approval_phrase": true,
      "requires_signed_token": true,
      "requires_source_rehash": true,
      "requires_target_absent": true,
      "requires_allowlist_dispatcher": true,
      "requires_rollback_manifest": true,
      "disallow_overwrite": true,
      "disallow_recursive": true
    },
    "qwen": {
      "advisory_only": true,
      "tool_execution_authority": false,
      "source_target_selection_authority": false
    },
    "cloud": {
      "private_raw_content_egress_allowed": false,
      "requires_privacy_redaction": true,
      "requires_token_budget_gate": true
    },
    "default_status_endpoint": "/api/harness/status",
    "copy_routes": [
      "/api/nas/copy/preview",
      "/api/nas/copy/dry-run",
      "/api/nas/copy/confirm",
      "/api/nas/copy/execute",
      "/api/nas/copy/rollback"
    ],
    "rollback_boundary": "rollback may remove only the copied target listed in the action-bound rollback manifest after target sha256 verification; source files are never deleted"
  },
  "copy_route_policy": {
    "policy_id": "digua_stage4_4_copy_route_policy_v1",
    "workspace_id": "nas_action",
    "allowed_action_type": "copy",
    "allowed_source_prefixes": [
      "Collections/CodexPreflight/source/",
      "Collections/CodexPreflight/stage5_default_service/source/"
    ],
    "allowed_target_prefixes": [
      "Collections/CodexPreflight/target/",
      "Collections/CodexPreflight/stage5_default_service/target/"
    ],
    "allowed_source_owner_scopes": [
      "operator_visible",
      "codex_synthetic"
    ],
    "target_root_prefix": "Collections/",
    "max_size_bytes": 1048576,
    "approval_ttl_seconds": 600,
    "require_source_hash": true,
    "require_target_absent": true,
    "require_target_parent_exists": true,
    "forbid_symlink": true,
    "forbid_recursive": true,
    "forbid_overwrite": true,
    "forbid_qwen_autonomous": true,
    "forbid_cloud_derived": true,
    "forbidden_action_types": [
      "delete",
      "move",
      "rename",
      "chmod",
      "chown",
      "overwrite",
      "recursive",
      "recursive_delete",
      "shell"
    ]
  },
  "contract_doc": "docs/HARNESS_DEFAULT_SERVICE_CONTRACT.md"
}
```
