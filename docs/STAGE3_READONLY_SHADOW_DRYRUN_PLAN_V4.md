# Stage 3 Readonly Shadow Dry-Run Plan V4

Stage 3 name: `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.

Entry requirements:

1. Qwen persistence is applied and verified.
2. `qwen25-local-openai-gateway.service` is active and enabled.
3. Qwen restart test passes.
4. Rollback plan is verified.
5. Policy-first contract is inherited as passing.
6. Qwen advisor is disabled or optional and non-authoritative.
7. Post-persistence readonly shadow soak passes.
8. No write/destructive/admin/recovery workspace is exposed.
9. No production route change occurs.
10. No private cloud egress occurs.
11. OpenClaw and Qwen health pass.

Allowed scope:

- OpenClaw foreground path unchanged
- local Qwen gateway unchanged except persistence management
- sidecar/harness shadow observation only
- `nas_search` readonly
- `document_rag` readonly
- deterministic policy chooses workspace/tool
- dispatcher executes only allowlisted read-only tools
- runtime trace, redaction, and rollback evidence

Forbidden:

- write/destructive/admin/recovery operations
- sidecar as foreground gateway
- Qwen autonomous tool router
- private cloud egress
- Dream7B foreground
- PostgreSQL/pgvector as default dependency
