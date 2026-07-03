# Stage 3 Readonly Shadow Dry-Run Plan V3

Stage 3 name: `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.

Allowed:

- OpenClaw foreground path unchanged
- local Qwen gateway unchanged
- sidecar/harness shadow observation only
- `nas_search` readonly
- `document_rag` readonly
- Qwen advisor/summarizer only
- deterministic policy chooses workspace/tool
- dispatcher executes only allowlisted read-only tools
- runtime trace, redaction, and rollback evidence

Forbidden:

- write/destructive operations
- permission modification
- `ops_recovery`
- `admin_audit` product closure
- sidecar as foreground gateway
- Qwen autonomous tool router
- private cloud egress
- Dream7B foreground
- PostgreSQL/pgvector as default dependency

Entry blocker: Qwen persistence must be applied and verified before this plan can become active Stage 3.
