# Qwen Gateway Systemd Apply/Rollback

This unit may only be applied under explicit operator approval. Stage 2.9 accepts either `AI_NAS_OPERATOR_APPROVED_QWEN_SYSTEMD_APPLY=1` or `operator_approval/qwen_systemd_apply_approved.json` with `approved=true`, operator identity, timestamp, target unit SHA256, maintenance window, and rollback acknowledgement.

## Preconditions

1. Snapshot current 18080 owner: PID, user, cwd, cmdline hash, and env hash if readable.
2. Verify `curl http://127.0.0.1:18080/health`.
3. Verify `curl http://127.0.0.1:18080/v1/models`.
4. Verify OpenClaw health at `http://127.0.0.1:8765/api/health` or `http://127.0.0.1:8765/health`.
5. Snapshot protected ports with `ss -lntp | grep -E '8765|18080|18888|18889'`.
6. Record SHA256 for:
   - `deployment/qwen25-local-openai-gateway.service.candidate`
   - `/mnt/nas/openclaw/configs/qwen25_official_route_policy.json`
   - `/mnt/nas/openclaw/scripts/qwen25_openai_gateway.py`

## Apply

1. Copy `deployment/qwen25-local-openai-gateway.service.candidate` to `/etc/systemd/system/qwen25-local-openai-gateway.service`.
2. Run `sudo systemctl daemon-reload`.
3. Stop only the current unmanaged Qwen process inside the approved maintenance window.
4. Run `sudo systemctl enable --now qwen25-local-openai-gateway.service`.
5. Verify:
   - `systemctl is-active qwen25-local-openai-gateway.service`
   - `systemctl is-enabled qwen25-local-openai-gateway.service`
   - `curl http://127.0.0.1:18080/health`
   - `curl http://127.0.0.1:18080/v1/models`
6. Run restart test:
   - `sudo systemctl restart qwen25-local-openai-gateway.service`
   - recheck health and models
7. Confirm OpenClaw health and protected ports are unchanged outside expected 18080 service management.

## Rollback

Real rollback also requires explicit operator approval through `AI_NAS_OPERATOR_APPROVED_QWEN_SYSTEMD_ROLLBACK=1`.

Dry-run verification checks that these commands are complete and that the current Preconditions can be judged:

1. `sudo systemctl disable --now qwen25-local-openai-gateway.service`
2. Restore the previously captured unmanaged Qwen launch command if the service must be removed.
3. Verify 18080 health and model identity, or explicitly document that Qwen is intentionally stopped.
4. Recheck OpenClaw health and protected ports.

Rollback must not mutate OpenClaw, 8765, 18888, 18889, Dream7B foreground routing, write/destructive/admin/recovery workspaces, or cloud private-egress policy.
