## Qwen2.5 7B Promotion Decision 2026-06-25

### Decision

Promote the Qwen2.5-7B-Instruct from shadow route (port 18081) to production
baseline (port 18080), replacing Qwen2.5-1.5B-Instruct.

### Pre-Promotion Gates (All Passed)

| Gate | Evidence | Date |
|---|---|---|
| 18080 baseline healthy | `ok_qwen25_ai_nas_acceptance_packet` | 2026-06-24 23:38 CST |
| 18081 shadow accepted | `ok_qwen25_7b_shadow_acceptance_packet` | 2026-06-24 23:53 CST |
| No BPU/buffer allocation failure | journalctl grep returned `NO_CRITICAL_MATCHES_FOUND` | 2026-06-25 |
| 7B reports generated | `qwen25_7b_ai_nas/` (4 subdirs) + `qwen25_7b_gateway/` (1 turn) | 2026-06-25 |
| HBM checksum verified | `a857af160c4effb0fcd5a22cab90f793` matches official | 2026-06-24 |
| Chat latency acceptable | 6286ms chat completion | 2026-06-24 |

### Promotion Action

1. Stop `qwen25-local-openai-gateway.service` (port 18080, 1.5B)
2. Backup `qwen25_official_route_policy.json` → `qwen25_official_route_policy_1.5B_backup.json`
3. Update `qwen25_official_route_policy.json` to point to 7B HBM/config
4. Start `qwen25-local-openai-gateway.service`
5. Run `qwen25_ai_nas_acceptance_packet.py` against 18080
6. Test NAS Web OS with real files via browser
7. After all tests pass, stop `qwen25-7b-shadow-openai-gateway.service` (port 18081)

### Rollback Plan

Revert `qwen25_official_route_policy.json` from the 1.5B backup, restart 18080 service.

### Post-Promotion State

- Service: `qwen25-local-openai-gateway.service`
- Port: 18080
- Model: `Qwen2.5-7B-Instruct-S100P-official`
- HBM: `Qwen2.5_7B_Instruct_1024.hbm` (7.9 GB)
- Profile: `qwen25_7b_instruct_cache_len_1024_q8`
- Report roots: `qwen25_ai_nas/` and `qwen25_gateway/`

### Evidence Paths

- Shadow acceptance: /mnt/nas/openclaw/reports/models/qwen25_7b_shadow_acceptance_20260624-235347/
- Baseline acceptance: /mnt/nas/openclaw/reports/models/qwen25_ai_nas_acceptance_20260624-233835/
- Shadow gateway logs: /mnt/nas/openclaw/reports/qwen25_7b_gateway/
- Shadow AI-NAS reports: /mnt/nas/openclaw/reports/qwen25_7b_ai_nas/
