# YOLO Index Rollback Runbook

## Trigger

Rollback if the default OpenClaw service fails to start, `/api/health` is unavailable, YOLO routes return server errors after restart, or UI regression blocks the existing multimodal page.

## Procedure

1. Keep the S100P on the LAN; do not expose the gateway publicly.
2. Use the deployment backup directory created before sync.
3. Run:

```bash
cd /mnt/nas/openclaw
bash scripts/production/rollback_yolo_index_service.sh /mnt/nas/openclaw/reports/yolo_production/deploy_backup_<timestamp>
curl -fsS http://127.0.0.1:8765/api/health
```

## Data

The rollback restores code only. It does not delete YOLO evidence, runtime DBs, or reports. If a runtime DB must be removed later, handle that as a separate operator-approved cleanup because it is generated evidence.
