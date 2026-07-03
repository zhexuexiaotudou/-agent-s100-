# Stage 3 Readonly Shadow Dry-Run Plan

Entry is allowed only after Stage 2.6 returns `ready_for_stage3_readonly_shadow_dryrun`.

Minimum dry-run scope:

1. Keep OpenClaw and Qwen foreground routes unchanged.
2. Keep sidecar localhost-only and read-only.
3. Continue using `ai_nas_allowlisted_tool.sh` for every dispatcher call.
4. Record Qwen structured decision, policy decision, dispatcher result, redaction status, and rollback marker per run.
5. Keep write/destructive/admin/recovery workspaces disabled.
6. Keep cloud egress public-only and redacted.
7. Keep SQLite as default persistence.
8. Keep Zleap lab-only or skipped.
