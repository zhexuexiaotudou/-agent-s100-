# stage5_default_service_emergency_rollback_gate

- verdict: `ok_stage5_default_service_emergency_rollback_gate`
- generated_at: `2026-07-04T14:36:44.551203+08:00`
- passed: `5/5`

## Checks

- `PASS` rollback and status scripts exist
- `PASS` local rollback dry-run passes
- `PASS` remote rollback dry-run passes
- `PASS` remote status command passes
- `PASS` OpenClaw/Qwen health OK after rollback dry-run

## Failures

- none

## Detail

```json
{
  "local_dry_run": {
    "returncode": 0,
    "stdout": "{\"copy_execute_enabled\": false, \"copy_rollback_enabled\": false, \"flags_file\": \"F:\\\\Project\\\\Digua\\\\configs\\\\harness_default_service_feature_flags.json\", \"mode\": \"--dry-run\", \"ok\": true, \"readonly_workspaces_enabled\": true, \"token_budget_gate_enabled\": true}",
    "stderr": ""
  },
  "remote_dry_run": {
    "returncode": 0,
    "elapsed_ms": 249.881,
    "stdout_hash": "ae097db7e841179e690c0c78df36936f0a3f8e8e136c13837a668fe55e6e682d",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "{\"copy_execute_enabled\": false, \"copy_rollback_enabled\": false, \"flags_file\": \"/mnt/nas/openclaw/configs/harness_default_service_feature_flags.json\", \"mode\": \"--dry-run\", \"ok\": true, \"readonly_workspaces_enabled\": true, \"token_budget_gate_enabled\": true}\n"
  },
  "remote_status": {
    "returncode": 0,
    "elapsed_ms": 944.095,
    "stdout_hash": "8ce7358ef321a96433f788c7e2e2a95bd5b9b26c2f72d95a673332402aa31631",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "{\n  \"ok\": true,\n  \"service\": \"harness_default_service\",\n  \"policy_id\": \"digua_stage5_harness_default_service_policy_v1\",\n  \"readonly_workspaces_enabled\": true,\n  \"token_budget_gate_enabled\": true,\n  \"privacy_redaction_gate_enabled\": true,\n  \"copy_routes\": [\n    \"/api/nas/copy/preview\",\n    \"/api/nas/copy/dry-run\",\n    \"/api/nas/copy/confirm\",\n    \"/api/nas/copy/execute\",\n    \"/api/nas/copy/rollback\"\n  ],\n  \"copy_execute_enabled\": true,\n  \"copy_execute_requires\": {\n    \"user_confirmation\": true,\n    \"signed_token\": true,\n    \"source_rehash\": true,\n    \"target_absent\": true,\n    \"dispatcher\": true\n  },\n  \"forbidden_actions\": [\n    \"delete\",\n    \"move\",\n    \"rename\",\n    \"chmod\",\n    \"chown\",\n    \"overwrite\",\n    \"recursive\",\n    \"recursive_delete\",\n    \"arbitrary_shell\"\n  ],\n  \"qwen_execution_authority\": false,\n  \"cloud_private_raw_egress\": false,\n  \"dispatcher\": \"/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh\",\n  \"dispatcher_exists\": true,\n  \"dispatcher_sha256\": \"d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a\",\n  \"raw_private_content_in_status\": false\n}"
  }
}
```
