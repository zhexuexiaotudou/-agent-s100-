# Demo Product Gap Audit

Generated at: `2026-07-06T14:45:00+08:00`

Scope: read-only pre-implementation audit for the multimodal demo product prompt.

## Demo 1 Link Readiness

| Check | Current Evidence | Screen Recordable | Gap | Fix |
|---|---|---:|---|---|
| PC to S100P SSH | `sunrise@192.168.127.10` reachable, host is `ubuntu` on `aarch64` | Yes | None | Keep using SSH key `s100p_linkcheck_ed25519` |
| NAS mount | `169.254.143.37:/OpenClawWorkspace` mounted at `/mnt/nas/openclaw` | Yes | None | Keep mount visible in recording |
| AI-NAS portal | `http://127.0.0.1:8765/api/health` ok | Yes | `openclaw-gateway.service` is inactive, while the portal process is live | Use live 8765 portal evidence now; repair/rename systemd unit later if needed |
| Qwen local gateway | `http://127.0.0.1:18080/health` ok; user unit active | Yes | None | Keep endpoint in Demo 3 |
| Product and harness status | `/api/product/status` and `/api/harness/status` ok | Yes | Harness still says move/rename forbidden | Update boundary after Auto Organizer is implemented |

## Demo 2 Feature Readiness

| Feature | Currently Demoable | Current Evidence | Product Gap | Must Implement |
|---|---:|---|---|---|
| AI Space / smart album | Yes | Stage 7 AI Space and live product smoke evidence | Keep evidence bounded; no raw paths | Stage 8 aggregate gate |
| Upload image auto-classify + Chinese naming | Yes | Stage 7 smart album gate and product smoke evidence | Physical organization still not enabled | Auto Organizer should consume generated names |
| Multimodal/person-attribute search | Yes | Live CLIP, YOLO, person-attribute evidence | Needs consolidated Demo 2 gate | Stage 8 Demo 2 gate |
| OCR + document RAG | Partial | Existing product status and multimodal text chunk path | OCR/RAG remains evidence-bounded; do not overclaim full production OCR | Demo 2 gate should report OCR evidence and boundary |
| Controlled move + Chinese rename organization | No | `src/auto_organizer` missing; product smoke requires move/rename forbidden | No controlled move_and_rename, approval, rollback manifest, or delete-block gate | Implement Auto Organizer service, route, UI, and gates |

## Demo 3 Router And Trace Readiness

| Check | Current State | Screen Recordable | Gap | Fix |
|---|---|---:|---|---|
| Qwen first-touch router | Existing edge-cloud router evidence | Yes | Needs Stage 8 consolidated query gate | Add Demo 3 gate |
| Token budget | Existing token-budget routes | Partial | No `/api/token-budget/explain` endpoint found | Add explain-compatible response through trace gate or route |
| Privacy tokenizer debug | No route found | No | `/api/privacy-tokenizer/debug` missing | Add route or record tokenizer step in assistant trace |
| Global assistant trace | `src/assistant_trace` missing | No | No product-grade trace for every entry point | Implement assistant trace DB, API, wrappers, and global coverage gate |

## Verified Missing Pieces

- `src/auto_organizer`: missing.
- `src/assistant_trace`: missing.
- `scripts/product_smoke_test.py` still requires `move` and `rename` in `forbidden_actions`.
- `configs/product_feature_flags.json` still records `smart_naming_physical_rename_enabled=false`.
- Current smart classification is virtual and materializes only a copy plan.

## Required Implementation

1. Add Auto Organizer with controlled `move_and_rename`, dry-run, approval, execute, rollback, rollback manifest, delete block, overwrite block, and raw-path-safe responses.
2. Update product smoke and claim boundary to: uncontrolled move/rename forbidden; controlled move/rename allowed only through Auto Organizer; delete and overwrite still forbidden.
3. Add Assistant Trace module and APIs with redacted steps, no hidden chain-of-thought, no raw absolute paths, and no private content.
4. Add Stage 8 demo gates and Stage 9 aggregate product delivery gate.

## Safety Boundary To Preserve

- Delete remains forbidden.
- Overwrite remains forbidden.
- Recursive destructive operations remain forbidden.
- Arbitrary shell remains forbidden.
- Qwen has no autonomous file-operation authority.
- Cloud private raw egress remains false.
- No face recognition, identity recognition, age/gender/race/emotion/health inference, or cloud person recognition is enabled.
