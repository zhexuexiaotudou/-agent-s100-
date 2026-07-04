# Stage4 Write Action Design Dossier

- Scope: local synthetic sandbox only until a separate human/GPT Pro review approves a later real-NAS Stage4.
- First canary actions: copy, rename, and move in `tmp/digua_ai_nas_write_sandbox`.
- Explicitly excluded: real NAS writes, delete/destructive actions, recovery/admin actions, cloud upload of private context, Qwen autonomous tool execution, and arbitrary shell/script paths.
- Authority chain: deterministic policy -> signed approval token -> before-state hash -> rollback-plan hash -> human confirmation -> allowlisted sandbox action.
- Required evidence for any future expansion: before/after manifest, rollback manifest, immutable audit record, action-specific allowlist, and post-action health check.
