# Stage 2 S100P Risk Register

| Risk | Evidence | Mitigation |
|---|---|---|
| Qwen service unit may be missing even when 18080 is healthy | `reports/3020_s100p_live_provider_route_integrity_gate.json` | Recreate/verify persistent unit before Stage 3 |
| Sidecar is still sidecar-like, not production foreground | `reports/3030_s100p_sidecar_isolation_gate.json` | Keep opt-in isolated port |
| Write tools are intentionally disabled | `reports/3040_*.json`, `reports/3050_*.json` | Add signed approval and rollback gates before write |
| Cloud private egress risk | `reports/3060_s100p_live_acl_redaction_cloud_egress_gate.json` | Keep cloud disabled or redacted-only |
