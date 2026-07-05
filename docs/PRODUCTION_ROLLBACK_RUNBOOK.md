# Production Rollback Runbook

Rollback is a controlled service restart/revert point, not a permission expansion.

1. Preserve current evidence with `scripts/production/collect_production_evidence.sh`.
2. Run `scripts/production/rollback_ui_v2_default_service.sh` in dry-run mode.
3. If operator-approved, set `AI_NAS_OPERATOR_APPROVED_PRODUCTION_ROLLBACK=1` and run the script on S100P.
4. Re-run `/api/health`, `/api/harness/status`, `/api/agent-runtime/status`, `/api/journal/health`, and browser UI checks.
5. If NAS copy route was exercised, rollback only the hash-verified target file created by that action.
