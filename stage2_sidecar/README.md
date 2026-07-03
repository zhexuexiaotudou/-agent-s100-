# Stage 2 Sidecar Mock Runtime

This directory contains a read-only sidecar-style runtime for Digua AI-NAS
Stage 2 trials. It is not a production route and must not replace OpenClaw,
Qwen, or the AI-NAS allowlist dispatcher.

Defaults:

- bind: `127.0.0.1`
- port: `19080`
- provider: `http://127.0.0.1:18080/v1`
- exposed tools: `mock.nas_search`, `mock.document_rag`

Hard boundaries:

- no write/destructive NAS tools;
- no `ops_recovery`;
- no `admin_audit`;
- no Dream7B foreground;
- no protected ports `8765`, `18080`, `18888`, `18889`;
- no arbitrary script paths.

Start:

`bash scripts/start_stage2_sidecar_mock.sh`

Stop:

`bash scripts/stop_stage2_sidecar_mock.sh`
