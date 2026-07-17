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
5. Resolve the exact portal unit before restarting it:

   ```bash
   systemctl --user show openclaw-gateway.service \
     -p FragmentPath -p WorkingDirectory -p ExecStart -p MainPID
   ```

   For the AI-NAS portal this must show `/home/sunrise/.config/systemd/user/openclaw-gateway.service`,
   working directory `/mnt/nas/openclaw`, the Python portal server, and port `8765`. The root user also
   has a different unit with the same name that starts the Node OpenClaw gateway on port `18789`.
   `sudo ... systemctl --user restart openclaw-gateway.service` targets that root unit and does not
   reload the AI-NAS portal.
6. Record the merge commit from `origin/main`. Do not deploy complete backend or frontend files from a
   feature branch based on a rollback branch; port the change onto current `main`, run the combined
   regression suite, and merge it first.

## Deploy

`scripts/production/deploy_ui_v2_to_default_service.sh` is dry-run by default. A real restart requires:

```bash
AI_NAS_OPERATOR_APPROVED_PRODUCTION_DEPLOYMENT=1 scripts/production/deploy_ui_v2_to_default_service.sh
```

The script does not change bind address, NAS permissions, Qwen authority, or Dream7B routing.

Before replacing runtime files, back up the current portal backend, related runtime modules, HTML, and
frontend JS under `/mnt/nas/openclaw/deployment/backups/<merge>-<timestamp>`. After deployment, restart
the `sunrise` user unit with `systemctl --user restart openclaw-gateway.service`, verify its `MainPID`
changed, and check the deployed file hashes.

## Post-deploy smoke

Run authenticated checks through the real portal path, not only unit health:

1. “你是谁” returns the deterministic local identity with no cloud call.
2. A known dated personal-history query enters local document RAG and returns traceable evidence.
3. A public, current, complex prompt can reach MiniMax through the guarded loopback bridge; private and
   NAS prompts cannot.
4. `/api/media/photos` lists only visible images and a returned `path_hash` succeeds through
   `/api/media/preview?variant=thumbnail`.
5. Open `/ui`, log in, submit one assistant prompt, and inspect the visible answer and model details.
