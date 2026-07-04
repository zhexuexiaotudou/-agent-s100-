# copy_route_contract_gate

- verdict: `ok_copy_route_contract_gate`
- generated_at: `2026-07-04T12:31:21.304027+08:00`
- passed: `6/6`

## Checks

- `PASS` contract/config/UI docs exist
- `PASS` required route names documented
- `PASS` execute and rollback disabled by default
- `PASS` policy is copy-only bounded candidate
- `PASS` Qwen no execution authority documented
- `PASS` destructive actions forbidden in policy

## Failures

- none

## Detail

```json
{
  "policy": {
    "policy_id": "digua_stage4_4_copy_route_policy_v1",
    "workspace_id": "nas_action",
    "allowed_action_type": "copy",
    "allowed_source_prefixes": [
      "Collections/CodexPreflight/source/"
    ],
    "allowed_target_prefixes": [
      "Collections/CodexPreflight/target/"
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
  "feature_flags": {
    "preview_enabled": true,
    "dry_run_enabled": true,
    "confirm_enabled": true,
    "execute_enabled": false,
    "rollback_enabled": false,
    "execute_canary_enabled": false,
    "require_operator_approval_file": true,
    "require_execute_env": true
  },
  "docs": [
    "docs/STAGE4_4_COPY_ROUTE_CONTRACT.md",
    "docs/STAGE4_4_OPENCLAW_COPY_UI_CONFIRMATION_SPEC.md",
    "docs/STAGE4_4_COPY_CONFIRMATION_COPYWRITING.md",
    "evidence/stage4_4_ui_wireframe_text.md"
  ]
}
```
