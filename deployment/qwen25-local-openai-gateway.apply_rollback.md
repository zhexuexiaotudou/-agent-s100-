# Qwen Gateway Candidate Apply/Rollback

Dry-run only in Stage 2.7. Do not apply without explicit operator approval.

Apply outline:

1. Snapshot current `pid/cmdline/cwd/env_hash/config_hash`.
2. Copy `deployment/qwen25-local-openai-gateway.service.candidate` to `/etc/systemd/system/qwen25-local-openai-gateway.service`.
3. Run `sudo systemctl daemon-reload`.
4. Stop only the current unmanaged Qwen process under an approved maintenance window.
5. Run `sudo systemctl enable --now qwen25-local-openai-gateway.service`.
6. Verify `curl http://127.0.0.1:18080/health` and `/v1/models`.

Rollback outline:

1. `sudo systemctl disable --now qwen25-local-openai-gateway.service`.
2. Restore previous launch command exactly as captured in report `6010`.
3. Verify 18080 health and model identity.
