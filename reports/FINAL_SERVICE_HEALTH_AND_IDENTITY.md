# Final Service Health and Identity

Generated: 2026-07-04T11:54:15+08:00

## Pass Criteria

- `openclaw_health_ok`: `True`
- `qwen_health_ok`: `True`
- `qwen_model_identity_recorded`: `True`
- `system_qwen_active_enabled`: `True`
- `system_openclaw_active_enabled`: `True`
- `dispatcher_hash_recorded`: `True`
- `protected_ports_recorded`: `True`
- `dream7b_not_product_foreground`: `True`

## Service State

- `system_qwen_active`: `active` rc=`0`
- `system_qwen_enabled`: `enabled` rc=`0`
- `system_openclaw_active`: `active` rc=`0`
- `system_openclaw_enabled`: `enabled` rc=`0`
- `user_qwen_active`: `inactive` rc=`3`
- `user_qwen_enabled`: `enabled` rc=`0`
- `user_openclaw_active`: `active` rc=`0`
- `user_openclaw_enabled`: `enabled` rc=`0`
- `linger`: `yes` rc=`0`

## HTTP

- `openclaw_api_health`: ok=`True` status=`200` elapsed_ms=`855.284`
- `openclaw_root`: ok=`True` status=`200` elapsed_ms=`1.317`
- `qwen_health`: ok=`True` status=`200` elapsed_ms=`2.202`
- `qwen_models`: ok=`True` status=`200` elapsed_ms=`1.114`

## Boundaries

- User-level qwen25-local-openai-gateway.service may be inactive; current active route is system-level qwen25-local-openai-gateway.service.
- S100P default route currently uses 192.168.137.1; do not claim PC network independence without a fresh route/NAT recheck.
