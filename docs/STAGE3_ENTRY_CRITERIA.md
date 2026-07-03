# Stage 3 Entry Criteria

Stage 3 requires all of these:

1. OpenClaw and Qwen service units are present, enabled, and live-health checked.
2. Read-only sidecar calls execute through `ai_nas_allowlisted_tool.sh` with trace completeness >= 0.99.
3. No write/destructive/admin/recovery tools are exposed.
4. Rollback leaves OpenClaw, Qwen, dispatcher, protected ports, and Dream/llama process state unchanged.
5. Cloud egress remains public/redacted only.
