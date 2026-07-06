# stage10_release_upgrade_rollback_gate

verdict: `ok_stage10_release_upgrade_rollback_gate`

- PASS: upgrade dry-run ok - 
- PASS: upgrade is dry-run - {'backup_root': '/opt/digua-ai-nas_backup_20260706-210340', 'blockers': [], 'config_backup_required': True, 'db_migration_destructive': False, 'dry_run': True, 'install_root': '/opt/digua-ai-nas', 'ok': True, 'rollback_command': 'bash release/install/upgrade_s100p.sh --rollback-from /opt/digua-ai-nas_backup_20260706-210340'}
- PASS: backup planned - {'backup_root': '/opt/digua-ai-nas_backup_20260706-210340', 'blockers': [], 'config_backup_required': True, 'db_migration_destructive': False, 'dry_run': True, 'install_root': '/opt/digua-ai-nas', 'ok': True, 'rollback_command': 'bash release/install/upgrade_s100p.sh --rollback-from /opt/digua-ai-nas_backup_20260706-210340'}
- PASS: uninstall dry-run ok - 
- PASS: uninstall does not remove NAS data - {'actions': ['disable:openclaw-gateway.service', 'stop:openclaw-gateway.service', 'disable:qwen25-local-openai-gateway.service', 'stop:qwen25-local-openai-gateway.service', 'disable:digua-ai-index-worker.service', 'stop:digua-ai-index-worker.service', 'disable:digua-ai-nightly-index.timer', 'stop:digua-ai-nightly-index.timer', 'remove_install_root:/opt/digua-ai-nas'], 'dry_run': True, 'install_root': '/opt/digua-ai-nas', 'nas_data_removed': False, 'ok': True, 'personal_data_removed': False, 'systemd_mode': 'user'}
