# Digua Journal User Guide

## Start

Run the local production gates:

```bash
python3 scripts/probes/digua_journal_production_deployment.py
```

Run only the collector smoke path:

```bash
sh scripts/run_journal_collectors_once.sh
```

Run only the end-to-end smoke path:

```bash
sh scripts/run_journal_e2e_smoke.sh
```

## Routes

The route adapter exposes:

- `GET /api/journal/health`
- `GET /api/journal/timeline`
- `GET /api/journal/projects`
- `POST /api/journal/manual-entry`
- `POST /api/journal/generate-summary`
- `POST /api/journal/export`

The page shell is available at `/journal` when OpenClaw serves `web/digua_journal.html` and the static assets.

## Rollback

Disable the feature flag:

```bash
sh scripts/disable_journal_feature.sh
```

Rollback does not delete journal evidence. It only disables the route/workspace flag and keeps cloud generation, Qwen tool execution, and real NAS writes disabled.

## Evidence

Gate reports are under `reports/21000` through `reports/21140`. Summary and export evidence is under `evidence/digua_journal/`.
