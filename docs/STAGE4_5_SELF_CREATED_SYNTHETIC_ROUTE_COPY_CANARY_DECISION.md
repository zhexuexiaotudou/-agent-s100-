# Stage 4.5 Self-Created Synthetic Route Copy Canary Decision

- final_verdict: `self_created_synthetic_route_copy_canary_passed_target_rolled_back`
- route_execute_executed: `True`
- route_rollback_executed: `True`
- target_missing_after_rollback: `True`
- source_retained_after_rollback: `True`
- source_relative_path: `Collections/CodexPreflight/source/stage4_5_self_created_route_canary_20260704-135733.txt`
- target_relative_path: `Collections/CodexPreflight/target/stage4_5_self_created_route_canary_20260704-135733_copied.txt`
- package: `F:\Project\Digua\evidence_for_gptpro\digua_ai_nas_stage4_5_self_created_synthetic_route_canary_for_gptpro_20260704-135733.zip`
- sha256: `ba4395656b28815c3213db9fae36153e12a281c576e42e946a6acc8c6ad82f59`

Stage 4.5 proves one route-level execute canary on a Codex-created, non-sensitive synthetic source under `Collections/CodexPreflight/source`. The target was created only through `ai_nas_action_execute_copy` behind the copy route guard and was removed only through `ai_nas_action_rollback_copy`.

The global copy route execute/rollback feature flags remain closed. This stage does not authorize arbitrary NAS copy, real user-file copy, overwrite, delete, move, rename, chmod, chown, recursive copy, Qwen autonomous execution, or cloud-derived private writes.
