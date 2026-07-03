# Stage 3 Policy-First Architecture

Stage 3 candidate architecture is `policy-first deterministic router + Qwen summarizer/advisor`.

Execution authority:

- workspace decision authority: deterministic policy router
- tool decision authority: `workspace_tool_policy` plus `workspace_arg_policy`
- execution authority: `ai_nas_allowlisted_tool.sh`
- Qwen role: local summarizer/advisor only

Trace schema:

- `policy_decision`
- `qwen_advisory`
- `final_tool_source = policy`
- `qwen_has_execution_authority = false`

Allowed Stage 3 readonly shadow workspaces:

- `nas_search`
- `document_rag`

Disabled Stage 3 readonly shadow workspaces:

- `nas_action`
- `ops_recovery`
- `admin_audit`
- `web_cloud_research` with private NAS content
- Dream7B foreground tools

The sidecar/harness cannot bypass the deterministic policy layer or call arbitrary shell/script paths. Cloud private egress stays disabled. PostgreSQL/pgvector remains out of the default production dependency path.
