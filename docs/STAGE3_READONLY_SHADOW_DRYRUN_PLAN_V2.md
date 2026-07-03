# Stage 3 Readonly Shadow Dry-Run Plan V2

Do not start Stage 3 until `6060_stage3_readonly_shadow_go_no_go_gate` passes.

Policy-first path:

1. Apply and verify Qwen persistence under an approved maintenance window.
2. Keep deterministic policy router as the final workspace/tool authority.
3. Use Qwen as local summarizer/advisor unless structured decision gates later pass.
4. Route all real read-only tool calls through `ai_nas_allowlisted_tool.sh`.
5. Keep write/destructive/admin/recovery workspaces disabled.
6. Keep cloud public-only and redacted.
7. Keep SQLite default and Zleap lab-only/skipped.
