# AI-NAS Product Delivery Acceptance - 2026-07-06

## Scope

This acceptance pass implements the roadmap requirement to expose a product-level
status surface and a repeatable smoke command for the S100P + OpenClaw + NAS
delivery route.

Target environment:

- S100P host: `sunrise@192.168.127.10`
- Kernel: `Linux ubuntu 6.1.158-rt58-DR-4.0.5-2603031328-g9f678e-g6caa4d`
- Network: `eth1` has `192.168.127.10/24` and `192.168.137.10/24`; default route still goes through `192.168.137.1`
- NAS mount: `169.254.143.37:/OpenClawWorkspace` mounted at `/mnt/nas/openclaw`
- OpenClaw service: `openclaw-gateway.service`, active after restart
- Qwen service: `qwen25-local-openai-gateway.service`, active; health endpoint uses `Qwen2.5-1.5B-Instruct-S100P-official`

## Changes Landed

- Added read-only product APIs:
  - `GET /api/product/status`
  - `GET /api/product/evidence/latest`
- Added `scripts/product_smoke_test.py`.
- Updated `configs/systemd/openclaw-gateway.service` so the portal also reads
  `/mnt/nas/openclaw/reports/product_delivery` as an evidence root.
- Fixed `scripts/probes/ai_nas_common.py` so `sqlite_index_status()` uses an
  immutable read-only SQLite connection. This prevents report-only readiness
  gates from attempting WAL or lock sidecar writes against root-owned/NFS
  index files.
- Synced `openclaw-plugins/s100p-allowlisted-tools/*` into
  `/mnt/nas/openclaw/openclaw-plugins/s100p-allowlisted-tools/` so the deployed
  workspace contains the canonical AI-NAS tool map used by governance gates.

## Commands

```bash
cd /mnt/nas/openclaw

python3 scripts/probes/ai_nas_allowlist_governance_audit_probe.py \
  --deploy-root /mnt/nas/openclaw \
  --source-root /mnt/nas/openclaw \
  --report-root /mnt/nas/openclaw/reports/product_delivery

python3 scripts/probes/ai_nas_production_readiness_gate_probe.py \
  --personal-root /mnt/nas/openclaw/Personal \
  --report-root /mnt/nas/openclaw/reports/product_delivery \
  --sqlite-index-path /mnt/nas/openclaw/reports/ai_nas_mvp/personal_inventory.sqlite3 \
  --deploy-root /mnt/nas/openclaw \
  --evidence-root /mnt/nas/openclaw/reports/ai_nas_mvp \
  --evidence-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --evidence-root /mnt/nas/openclaw/reports/models \
  --evidence-root /mnt/nas/openclaw/reports/product_delivery

python3 scripts/product_smoke_test.py \
  --base-url http://127.0.0.1:8765 \
  --report-root /mnt/nas/openclaw/reports/product_delivery
```

## Acceptance Results

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Allowlist governance | `ok_ai_nas_allowlist_governance` | `/mnt/nas/openclaw/reports/product_delivery/allowlist_governance_audit_20260706-025059-413759/allowlist_governance_audit.json` |
| Production readiness | `ready_ai_nas_production_readiness_gate` | `/mnt/nas/openclaw/reports/product_delivery/production_readiness_gate_20260706-025926-730286/production_readiness_gate.json` |
| Product smoke | `ok_product_smoke_test` | `/mnt/nas/openclaw/reports/product_delivery/product_smoke_test_20260706-142946/product_smoke_test.json` |

Product smoke summary:

```text
failure_count=0
warning_count=0
production_ready=true
readiness_verdict=ready_ai_nas_production_readiness_gate
yolo_runtime_target=s100p_bpu_hbm
yolo_detection_count=66
multimodal_embedding_count=5
ai_space_asset_count=13
smart_category_count=29
smart_name_count=43
subtitle_segment_count=1
```

Live product status summary:

```text
overall.status=ok
overall.production_ready=true
failed_modules=[]
degraded_modules=[]
yolo.runtime_target=s100p_bpu_hbm
yolo.indexed_count=8
yolo.detection_count=66
yolo.keyframe_count=4
yolo.cloud_used=false
yolo.raw_path_rows=0
```

## Boundaries

- `GET /api/product/status` and `GET /api/product/evidence/latest` intentionally
  omit absolute NAS/Linux/Windows paths. They return status, metrics, and
  `evidence_ref` values only.
- The smoke test verifies that product status and product evidence do not expose
  raw absolute paths.
- The latest smoke pass has no degraded modules. Multimodal still uses bounded
  product evidence roots for smoke rather than claiming full-NAS semantic
  coverage.
- The final readiness gate still records warnings for systemd index daemon
  install evidence, long NAS-backed soak, production CLIP rows, scanned-content
  OCR fallback, face recognition out-of-scope, operator-approved real recovery
  drill, and one `_probe` alias warning. These are not blockers in the current
  readiness gate and must not be described as eliminated.
- Gateway exposure remains loopback/LAN scoped; no public gateway exposure was
  added.
- No delete, move, rename, overwrite, recursive operation, arbitrary shell, or
  broader NAS permission was enabled.

## GPT Pro Review

GPT Pro review is optional for this pass. If requested, review should focus on
whether the remaining readiness warnings should stay as documented boundaries or
be promoted into the next product hardening milestone.
