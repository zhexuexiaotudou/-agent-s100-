# Technical Features Safe Version

- Local-first route: requests first reach S100P/Qwen before cloud routing.
- Policy-first harness: workspace, tool exposure, argument logging and redaction are controlled before execution.
- Single execution entrance: real tool calls use `ai_nas_allowlisted_tool.sh`.
- SQLite/FTS/document retrieval: current evidence supports metadata indexing, FTS, embeddings table presence and Qwen-assisted query understanding; do not overclaim production vector semantic search.
- Audit and rollback: runtime traces, denial records, cloud egress redaction, sandbox canary and rollback manifests are recorded.
- Boundary: real NAS writes remain locked; sandbox canary is not a real NAS write.
