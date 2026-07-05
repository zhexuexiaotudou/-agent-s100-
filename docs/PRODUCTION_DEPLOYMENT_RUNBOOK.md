# Production Deployment Runbook

Status: `hold_due_to_24h_stability_failure`.

## Scope

- Default service: S100P `openclaw-gateway.service` on loopback `127.0.0.1:8765`.
- Model gateway: local Qwen-compatible service on `127.0.0.1:18080`.
- NAS scope: bounded `Personal` workspace and allowlisted `Collections/CodexPreflight` copy route only.
- Public exposure: not allowed. The gateway must stay behind local/LAN operator access.

## Preflight

1. SSH to S100P with the reviewed key.
2. Run `scripts/production/check_production_status.sh`.
3. Confirm `/api/health`, `/api/harness/status`, `/api/agent-runtime/status`, `/api/journal/health`, and Qwen `/health` are 2xx.
4. Confirm the production package self-check is clean before sharing any artifact.

## Deploy

`scripts/production/deploy_ui_v2_to_default_service.sh` is dry-run by default. A real restart requires:

```bash
AI_NAS_OPERATOR_APPROVED_PRODUCTION_DEPLOYMENT=1 scripts/production/deploy_ui_v2_to_default_service.sh
```

The script does not change bind address, NAS permissions, Qwen authority, or Dream7B routing.
