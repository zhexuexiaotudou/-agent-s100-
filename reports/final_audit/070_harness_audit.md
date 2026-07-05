# 070 Harness Audit

- 24h default service stability observation is not proven by this audit.

| field | value |
| --- | --- |
| generated_at | 2026-07-05T13:44:26+08:00 |
| harness_status | complete_except_24h_soak |
| packet_final_verdict | harness_default_service_integrated_limited_copy_enabled |
| all_gates_pass | True |
| live_ok | True |
| copy_routes | ['/api/nas/copy/preview', '/api/nas/copy/dry-run', '/api/nas/copy/confirm', '/api/nas/copy/execute', '/api/nas/copy/rollback'] |
| forbidden_actions | ['delete', 'move', 'rename', 'chmod', 'chown', 'overwrite', 'recursive', 'recursive_delete', 'arbitrary_shell'] |
| qwen_execution_authority | False |
| cloud_private_raw_egress | False |
| dispatcher_exists | True |
| remaining_enhancement | 24h default service stability observation is not proven by this audit. |
