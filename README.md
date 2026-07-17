# Digua S100P / OpenClaw AI-NAS Demo

This workspace is the evidence and demo repo for turning an S100P board into an
always-on AI-NAS gateway: OpenClaw provides the NAS-facing experience, Qwen runs
locally on S100P, and an edge-cloud router decides when a request can leave the
device.

## UI and Product Access

The preserved `/ui` redesign was completed locally on 2026-07-16 and deployed
to the powered S100P/NAS system on 2026-07-17. It keeps the native HTML/CSS/JS
stack, routes, API calls, identity, ACL, controlled-copy, and soft-delete
boundaries. The user entry point is now `http://digua.local/`, with
`http://192.168.127.10/` as the verified fallback. The portal, local Qwen 1.5B,
local Qwen 7B CPU, and guarded MiniMax bridge remain loopback-only on ports
8765, 18080, 18081, and 18082.

The live acceptance covered mDNS and fallback access, authentication and roles,
four mobile viewports, reboot recovery, Internet-route loss, NFS loss and
recovery, timed network rollback, access-only rollback/upgrade, secret-free
QR/access-card generation, and a private Tailscale HTTPS Serve path. The current
verdict is
`product_access_lan_tailscale_pass_cloudflare_ready_for_external_validation`:
`https://digua.tail7c6cbb.ts.net/` is verified as tailnet-only, maps the approved
Tailscale identity to the local administrator, rejects unmapped identities, and
survives reboot and disable/re-enable rollback. Cloudflare remains the optional
`configured_but_external_validation_pending` path. Physical-phone QR and PWA
installation are not claimed yet.

Design history is recorded in
[`docs/offline_ui_delivery_20260716.md`](docs/offline_ui_delivery_20260716.md).
Current architecture and gate evidence are in
[`docs/product_access/PRODUCT_ACCESS_ARCHITECTURE.md`](docs/product_access/PRODUCT_ACCESS_ARCHITECTURE.md)
and [`reports/access/40600_product_acceptance_gate.md`](reports/access/40600_product_acceptance_gate.md).

The album recovery deployed on 2026-07-18 scopes the visible library to the 100
photos under `Personal/Photos`, removes the legacy 24-photo intermediate state,
loads previews with bounded concurrency, and rejects text placeholders that use
image suffixes. A follow-up product-entry fix loads real NAS capacity on every
authenticated route and permits the local `blob:` preview URLs required by the
image viewer. The product-access identity bridge now also tolerates short locks
on the NAS-hosted identity database: established sessions avoid redundant
per-request bridge validation, while a new bridge returns an explicit JSON 503
instead of dropping the browser connection when the lock persists. Live counts,
lock-contention evidence, soft-delete evidence, and rollback points are recorded
in
[`docs/album_preview_recovery_20260718.md`](docs/album_preview_recovery_20260718.md).

The AI Assistant now has an explicit model selector for local Qwen2.5 1.5B,
local Qwen2.5 7B, and cloud MiniMax 2.7. Identity and NAS tool requests remain
local; selecting MiniMax still requires a local privacy decision before any
cloud call. The verified 7B route is CPU-backed because real BPU text generation
failed the 2026-07-18 allocation check. Implementation, live acceptance, and the
correction to the older shadow claim are recorded in
[`docs/assistant_model_selector_20260718.md`](docs/assistant_model_selector_20260718.md).

## Current Status

Status timestamp: 2026-07-18 04:35 CST.

The three demo expectations are now satisfied on the S100P test machine:

| Demo | Expected behavior | Current result | Evidence |
| --- | --- | --- | --- |
| 1. S100P as resident gateway | S100P keeps the AI gateway online after login/logout and exposes a stable local entry point | `openclaw-gateway.service`, `qwen25-local-openai-gateway.service`, and `qwen7b-cpu.service` are active; persistent user services are enabled and `loginctl` linger is `yes` | OpenClaw `/api/health` on `127.0.0.1:8765`; Qwen health on `127.0.0.1:18080` and `127.0.0.1:18081` |
| 2. OpenClaw implements AI-NAS | OpenClaw can drive NAS operations, not just chat | `ok_ai_nas_openclaw_nas_control_gate`, 10/10 checks passed | `/mnt/nas/openclaw/reports/qwen25_ai_nas/openclaw_nas_control_gate_20260629-210023-832862/openclaw_nas_control_gate.json` |
| 3. Edge + cloud routing | Every query first enters local Qwen; private/simple requests stay on S100P; public complex requests can use a controlled cloud endpoint | Production portal keeps identity questions local and routes only `privacy_level=none` complex work through the loopback OpenClaw bridge to `custom-gateway/MiniMax-M2.7`; both authenticated HTTP cases returned 200 | [`docs/openclaw_minimax_cloud_overflow_20260718.md`](docs/openclaw_minimax_cloud_overflow_20260718.md) |

The latest Qwen AI-NAS acceptance packet also passed:

- Verdict: `ok_qwen25_ai_nas_acceptance_packet`
- Route: `ai_nas_allowlisted_tools`
- Generated reports: personal inventory, evidence report, case packet, folder RAG, and gateway turn reports
- Evidence: `/mnt/nas/openclaw/reports/models/qwen25_ai_nas_acceptance_20260629-210016/qwen25_ai_nas_acceptance.json`

## Harness Default Service Status

The AI-NAS harness is now integrated into the default OpenClaw service path with
limited, user-confirmed copy enabled.

- Final verdict: `harness_default_service_integrated_limited_copy_enabled`
- Final packet: `01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json`
- Review package: `evidence_for_gptpro/digua_ai_nas_harness_default_service_for_gptpro_20260704-143537.zip`
- Package SHA256: `38bc412b3cf0bbf1a159bdc75413a680f9cc2f3c5ec14d9878a8fb962e0c2fbf`
- Live status endpoint: `http://127.0.0.1:8765/api/harness/status` on S100P

The default harness path allows bounded copy flows and the Auto Organizer
controlled move+rename flow. Both require explicit product policy, typed
approval or equivalent operator confirmation, target no-overwrite guarantees,
and rollback evidence. Uncontrolled move/rename, delete, chmod, chown,
overwrite, recursive operations, arbitrary shell execution, Qwen autonomous
tool execution, and private raw cloud egress remain out of scope.

## Product Delivery Acceptance

The roadmap product-smoke loop is now available on S100P.

- Product status API: `http://127.0.0.1:8765/api/product/status` on S100P
- Product evidence API: `http://127.0.0.1:8765/api/product/evidence/latest` on S100P
- Product smoke verdict: `ok_product_smoke_test`
- Product smoke report: `/mnt/nas/openclaw/reports/product_delivery/product_smoke_test_20260706-142946/product_smoke_test.json`
- Final readiness verdict: `ready_ai_nas_production_readiness_gate`
- Final readiness report: `/mnt/nas/openclaw/reports/product_delivery/production_readiness_gate_20260706-025926-730286/production_readiness_gate.json`
- Acceptance note: `docs/product_delivery_acceptance_20260706.md`

The live product smoke verified `failure_count=0`, `warning_count=0`,
`production_ready=true`, `yolo_runtime_target=s100p_bpu_hbm`,
`yolo_detection_count=66`, `multimodal_embedding_count=5`,
`ai_space_asset_count=13`, `smart_category_count=29`,
`smart_name_count=43`, and `subtitle_segment_count=1`.

## Demo Product Delivery Acceptance

The multimodal Auto Organizer delivery gate is passing on the S100P real
machine.

- Stage 9 verdict: `ok_stage9_demo_product_delivery_gate`
- Stage 9 report: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage9_demo_product_delivery_gate.json`
- Product smoke report: `/mnt/nas/openclaw/reports/qwen25_ai_nas/product_smoke_test_20260706-154654/product_smoke_test.json`
- GPT Pro bundle: `/mnt/nas/openclaw/evidence_for_gptpro/digua_demo_product_delivery_20260706-154654.zip`
- Bundle SHA256: `e79382b588b7a1a8ff0ab991ed8c334578928925282d9089f9452e1b59d5d708`

Validated additions:

- Auto Organizer: controlled move+rename, conflict-safe suffixing,
  delete/overwrite blocking, rollback manifest, and rollback restore.
- Assistant Trace: global 10-step trace contract for assistant entrypoints
  without hidden chain-of-thought storage.
- Demo 3 explain endpoints: Qwen router explain, token-budget explain,
  privacy-tokenizer debug, and assistant trace APIs.
- Resident link: `openclaw-gateway.service` and
  `qwen25-local-openai-gateway.service` are both active; portal remains
  loopback-scoped on `127.0.0.1:8765`.

## Final Demo Recording Readiness

The final demo hardening loop is passing on the S100P real machine with
user-like flows.

- Final verdict: `ok_stage9_final_recording_readiness_gate`
- Final report: `reports/stage9_final_recording_readiness_gate.json`
- Final report markdown: `reports/stage9_final_recording_readiness_gate.md`
- GPT Pro evidence bundle: `evidence_for_gptpro/digua_final_recording_readiness_20260706-175314.zip`
- Bundle SHA256: `c59b2e8ebfbdc2621a09fa892da6008962fd70b8719602b3dcf8c068166a2982`
- Recording readiness note: `docs/DEMO_PRODUCT_RECORDING_READINESS_20260706.md`

Validated final additions:

- Auto Organizer classifies neutral filenames through AI Space and smart
  classification indexes before falling back to filename heuristics.
- `/api/assistant/chat` records the ten standard trace steps from real router,
  privacy, token-budget, tool-execution, and safety context.
- OCR/RAG product endpoints are available at `/api/document-rag/query`,
  `/api/ocr/query`, and `/api/ocr/status`.
- Demo 2 replayed upload, local indexing, AI Space/multimodal/person safety,
  YOLO search, OCR/RAG, Auto Organizer approve/execute, and rollback.
- Demo 3 replayed assistant requests for local media search, private document
  summarization, and public complex routing.
- Final safety flags remained false for raw path return, delete, overwrite,
  uncontrolled move/rename, hidden chain-of-thought storage, and private cloud
  egress.

Current boundary: the real S100P YOLO backend completed local processing and
indexed assets, but the final demo image set produced zero YOLO boxes. This is
recorded as a smoke warning, not a synthetic pass. Person Attribute Search is
therefore degraded for detection-derived attributes in this final packet, while
unsafe identity and sensitive attribute inference remain blocked.

## Product-Grade Hardening

The final hardening pass after Stage 9 adds stricter product contracts for the
recording flows.

- Audit: `reports/final_product_hardening_audit/final_product_hardening_audit.md`
- Hardening note: `docs/PRODUCT_GRADE_HARDENING_20260706.md`
- Auto Organizer now blocks product fallback when no AI index evidence exists:
  `blocker=ai_index_missing_for_asset`.
- Assistant Trace now separates non-synthetic product traces from synthetic
  diagnostic traces.
- OCR/RAG now has dedicated document and OCR route modules plus an `ocr_rag`
  product-status card.

S100P live acceptance for this hardening pass passed:

- Final verdict: `ok_stage9_final_recording_readiness_gate`
- Final report: `reports/stage9_final_recording_readiness_gate.json`
- GPT Pro evidence bundle:
  `evidence_for_gptpro/digua_final_recording_readiness_20260706-184743.zip`
- Bundle SHA256:
  `17f578ccf3749da09a56994b39a06ff618cd42c8121c93d75f2d814ca0b89fc2`

Current boundary: product smoke has `failure_count=0` and
`production_ready=true`, while YOLO and Person Attribute remain degraded for
the same real-data reason: the S100P YOLO backend completed with
`runtime_target=s100p_bpu_hbm`, but the current demo images produced zero boxes.

## Stage 10 Release Product Delivery

Stage 10 turns the current demo system into a release-oriented S100P package
and adds a reproducible demo corpus workflow. The following verdict, report and
two hashes are the historical 0.1.0 acceptance from 2026-07-06; they remain as
trace evidence and are not the checksum of the current 0.2.0 package.

- Final S100P verdict: `ok_stage10_release_product_delivery_gate`
- Acceptance note: `docs/STAGE10_RELEASE_PRODUCT_DELIVERY_ACCEPTANCE_20260706.md`
- Final report: `reports/stage10_release_product_delivery_gate.json`
- Product smoke: `reports/product_smoke_test_20260706-210340/product_smoke_test.json`
- S100P package SHA256:
  `66caaca4df00914ea18111f9fc1fbcb1fdd861f75a33c6ed63a7685d1a72b51a`
- Evidence bundle SHA256:
  `3a4ace7dc4fd3e1abdb4f8a7a9c1d28118adf06d17c1f1f88e659fc8796c61fa`

- Historical release package command:
  `python3 scripts/build_release.py --version 0.1.0 --out dist/`
- Final release gate:
  `python3 gates/stage10_release_product_delivery_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --base-url http://127.0.0.1:8765 --timeout 240`
- Windows access note:
  `docs/openclaw_windows_loopback_access_20260706.md` explains why Windows
  `http://127.0.0.1:8765/ui` needs an SSH tunnel to the S100P loopback gateway.
- Demo corpus: `demo_corpus/` contains recipes, manifests, license notices,
  Wikimedia/Open Images downloaders, synthetic OCR/RAG document generation,
  Personal demo-root builder, and verification scripts.
- Package integrity checks confirm generated demo fixtures declared in manifests
  are present in the release tarball.
- Release installer: `release/install/install_s100p.sh` supports preflight,
  NAS mount planning, model path verification, venv setup, systemd unit
  planning, first-run wizard, upgrade, rollback, uninstall, and support bundle
  collection.

Current 0.2.0 package outputs:

- `dist/digua-ai-nas-s100p-0.2.0.tar.gz`
- `dist/digua-ai-nas-s100p-0.2.0.zip`
- `dist/digua-ai-nas-s100p-0.2.0.sha256`
- `dist/release_manifest.json`

User quickstart (guided, secret-safe):

```bash
sudo ./deploy/product_access/install.sh
```

The product installer installs the required Ubuntu network/NAS helpers, runs
secret-free NAS discovery, asks only for values and authorization scope that
cannot be proven automatically, supports local Qwen or an OpenAI-compatible
cloud provider, keeps remote access and private raw cloud egress disabled by
default, then generates the one-time LAN claim QR and access card. See
[`docs/product_access/FIRST_TIME_SETUP.md`](docs/product_access/FIRST_TIME_SETUP.md)
and [`docs/NEW_USER_AI_NAS_DEPLOYMENT_CN.md`](docs/NEW_USER_AI_NAS_DEPLOYMENT_CN.md).

The offline clean-install simulation is documented in
[`docs/OFFLINE_DEPLOYMENT_WIZARD_20260717.md`](docs/OFFLINE_DEPLOYMENT_WIZARD_20260717.md).
It explicitly reports `simulation=true` and `production_verified=false`. The
non-destructive access-only coexistence install, upgrade, rollback, reboot, NAS
mount and LAN acceptance have now passed on the real S100P/NAS system. A fully
destructive clean install remains CI-simulated so the existing services,
identity, indexes and NAS data are not erased merely to repeat first-install
provisioning.

The exact 0.2.0 appliance evidence, including the release commit and checksum,
two real reboot boot IDs, 18 automated S100P checks, LAN endpoints, rollback
points and remaining manual boundaries, is recorded in
[`docs/NEW_USER_AI_NAS_PRODUCT_DELIVERY_ACCEPTANCE_20260717.md`](docs/NEW_USER_AI_NAS_PRODUCT_DELIVERY_ACCEPTANCE_20260717.md).
System-scope appliance services are the supported default. A legacy user-scope
Qwen unit must not run at the same time as the system unit on port 18080.

Stage 10 safety boundary:

- model weights are not bundled;
- third-party images are not bundled by default;
- private user data and runtime DB files are excluded from release packages;
- Gateway defaults to loopback/LAN, not public internet;
- NAS access remains allowlisted to the configured OpenClaw workspace;
- delete, overwrite, uncontrolled move/rename, Qwen autonomous file execution,
  hidden chain-of-thought storage, cloud vision/OCR/ASR, and private raw cloud
  egress remain disabled.

Current Stage 10 recording boundary: YOLO bbox recording must either show real
`detection_count > 0` or record the explicit blocker
`yolo_demo_images_not_detectable`. Do not claim bbox detection while the live
S100P product smoke reports zero YOLO boxes.

## AI Album UI Workspace

The existing v2 Web UI now includes an `AI 相册` workspace at `/ai-album`.
It combines AI Space, media previews, smart classification, person-attribute
search, smart naming, and Auto Organizer plan generation into one local
AI-NAS album page.

- Route: `http://127.0.0.1:8765/ai-album` on S100P loopback.
- Delivery note: `docs/AI_ALBUM_UI_DELIVERY.md`
- Gate: `gates/stage11_ai_album_ui_gate.py`
- S100P verdict: `ok_stage11_ai_album_ui_gate`
- S100P report:
  `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage11_ai_album_ui_gate.json`
- Scope: local search, smart-category browsing, thumbnail grid, double-click
  image viewer, selected-asset details, identity-query UI block, and controlled
  Auto Organizer plan workflow.
- Boundary: no face identity recognition, no sensitive attribute inference, no
  raw path display, no delete/overwrite UI, no public gateway exposure.

## AI Space Product Acceptance

The AI Space / Smart Classification / Subtitle Extraction delivery gate is now
passing on S100P.

- Stage 7 verdict: `ok_stage7_ai_space_product_delivery_gate`
- Stage 7 report: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_ai_space_product_delivery_gate.json`
- GPT Pro bundle: `/mnt/nas/openclaw/evidence_for_gptpro/digua_ai_space_product_delivery_latest.zip`
- Acceptance note: `docs/AI_SPACE_PRODUCT_ACCEPTANCE_20260706.md`

Validated modules:

- Live local CLIP image embeddings: `model_family=clip`, `vector_dim=512`,
  `production_semantic_embedding_count=17`, `cloud_used=false`.
- Person Attribute Search: `person_detection_count=31`, `attribute_count=31`,
  identity requests are blocked.
- AI Space: `asset_count=220`, `evidence_count=220`, no raw path return.
- Smart Classification: `category_count=12`, `membership_count=986`, virtual
  collections only; no physical file move.
- Subtitle Extraction: local `transformers_whisper` backend, `segment_count=1`,
  SRT/VTT generated, `cloud_used=false`.

## Smart Album Upload And Chinese Naming Acceptance

The smart album auto-classification and Chinese naming delivery gate is passing
on S100P.

- Stage 7 verdict: `ok_stage7_smart_album_classification_delivery_gate`
- Stage 7 report: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_smart_album_classification_delivery_gate.json`
- Product smoke report: `/mnt/nas/openclaw/reports/product_delivery/product_smoke_test_20260706-142946/product_smoke_test.json`
- GPT Pro bundle: `/mnt/nas/openclaw/evidence_for_gptpro/digua_smart_album_classification_delivery_latest.zip`
- Delivery note: `docs/SMART_ALBUM_CLASSIFICATION_DELIVERY.md`

Validated flow:

- `POST /api/media/upload` saves the uploaded image under Personal NAS and
  records media upload, multimodal rebuild, YOLO index, person-attribute,
  smart-classification, smart-naming, and AI Space jobs.
- Uploaded `white_shirt_person_004.jpg` returned asset
  `mm_fb98a8eb7d323bbbdea2f181`, hit `人物照片` and `白色上衣`, and generated
  `人物照片_白色上衣_照片_20260706_429.jpg`.
- Chinese naming gate verified the format
  `主类别_核心特征_场景或属性_日期_序号`, no illegal filename characters, no
  phone/ID-style sensitive numbers, and sample names for `人物照片`, `猫咪`,
  `票据发票`, and `笔记本电脑`.
- Final live smoke after fixture restoration verified `yolo_detection_count=66`,
  `person_detection_count=31`, `ai_space_asset_count=13`,
  `smart_category_count=29`, and `smart_name_count=43`.

## Demo Story

The project story should be told as a progression from "running a model on a
board" to "shipping a private AI-NAS appliance".

1. The S100P is not a one-off accelerator demo. It is the resident gateway that
   stays online through systemd user services and becomes the local AI control
   plane for a NAS.
2. OpenClaw is the NAS product surface. It turns user intent into real NAS
   workflows: list files, search folders, generate evidence packets, copy/rename
   files, block unauthorized writes, and require confirmation for destructive
   actions.
3. Qwen is the local decision layer. All user queries first enter local Qwen.
   The router asks Qwen whether the request is simple enough to handle locally
   and whether it is privacy-sensitive. Only public, complex work is allowed to
   go to a controlled cloud endpoint.
4. The value proposition is token saving plus privacy protection: the endpoint
   keeps private NAS context on the device and uses cloud only as overflow, not
   as the default path.

Recommended one-line pitch:

> S100P + OpenClaw turns a normal NAS into a privacy-first AI-NAS: local Qwen
> handles private file intelligence on the device, while cloud is used only for
> public complex tasks that pass the local router.

## Highlights

- **Resident gateway**: `qwen25-local-openai-gateway.service` serves the local
  OpenAI-compatible Qwen endpoint at `127.0.0.1:18080`; `openclaw-gateway.service`
  serves the AI-NAS Web OS / operator portal at `127.0.0.1:8765`.
- **Real NAS actions**: the OpenClaw gate validates login, directory listing,
  rename, copy, delete confirmation, viewer read-only behavior, ACL-protected
  copy targets, and direct storage mutation ACL enforcement.
- **Local-first router**: the edge-cloud probe requires Qwen to produce
  structured JSON. Policy is only a privacy/failure fallback.
- **OpenClaw-owned cloud overflow**: public complex requests use the
  loopback-only bridge on `127.0.0.1:18082`, which calls the existing OpenClaw
  `custom-gateway/MiniMax-M2.7` provider. The portal never reads or stores the
  MiniMax provider token.
- **Privacy floor**: invoice, family photo, chat screenshot, NAS folder, finance,
  and other private requests are forced local even if the cloud path exists.
- **Evidence-first delivery**: every demo claim is backed by JSON/Markdown
  reports on `/mnt/nas/openclaw/reports/...`, not by screenshots alone.
- **Controlled Auto Organizer**: physical organization is now allowed only
  through the Auto Organizer plan/dry-run/approve/execute/rollback flow. It
  does not enable arbitrary NAS move/rename, delete, overwrite, or Qwen
  autonomous file operations.
- **Model pivot is clear**: Dream7B artifacts are retained as toolchain history;
  the current product route is Qwen + OpenClaw + AI-NAS gates. The current
  Dream7B seq128 S100P logits-validity research status is summarized in
  `docs/DREAM7B_S100P_SEQ128_LOGITS_VALIDITY_ROUTE_STATUS_20260704.md`.
- **Dream7B research route reset**: the llada.cpp-style correctness-first track
  now lives under `dream_s100p_lladacpp/`; the 31-row HF/PyTorch truth set,
  validation gate, and truth-replay block-driver gate have passed. The route is
  stopped at `bpu_operator_alignment_failed_review_required` until true per-op
  BPU outputs, layout records, and quant scale evidence exist.

## Repository Layout

| Path | Role |
| --- | --- |
| `scripts/qwen25_openai_gateway.py` | Local Qwen OpenAI-compatible gateway and structured edge-cloud classifier entry |
| `scripts/probes/ai_nas_edge_cloud_router_probe.py` | End-to-end local-first edge-cloud router gate |
| `scripts/probes/qwen25_ai_nas_acceptance_packet.py` | Qwen AI-NAS acceptance packet generator |
| `scripts/probes/ai_nas_openclaw_nas_control_gate_probe.py` | OpenClaw NAS control, ACL, and destructive-action gate |
| `scripts/probes/ai_nas_operator_portal_server.py` | AI-NAS Web OS / operator portal server |
| `scripts/probes/openclaw_cloud_inference_bridge.py` | Loopback-only authenticated adapter from portal cloud overflow to the fixed OpenClaw MiniMax provider |
| `scripts/product_smoke_test.py` | Product-level live HTTP smoke gate for `/api/product/status`, evidence, YOLO, multimodal, and harness boundaries |
| `gates/stage7_ai_space_product_delivery_gate.py` | Aggregate product gate for live CLIP, person attributes, AI Space, smart classification, and subtitle extraction |
| `src/person_attribute/` | Local-only non-identifying person attribute search |
| `src/ai_space/` | AI Space catalog and facets |
| `src/smart_classification/` | Virtual smart classification collections |
| `src/subtitle_extraction/` | Local ASR transcript, SRT/VTT, and search support |
| `src/auto_organizer/` | Controlled move+rename planner, executor, conflict policy, and rollback |
| `src/assistant_trace/` | Global assistant execution trace schema, recorder, and routes |
| `src/product_jobs/` | Product background job queue API |
| `src/harness/` | Harness policy, copy route guard, and token-budget integration |
| `src/openclaw/` | OpenClaw default-service middleware and API route adapters |
| `gates/stage*_gates.py` | Stage-gated AI-NAS harness validation scripts |
| `reports/` | Gate outputs, trace JSONL, and regression evidence |
| `evidence_for_gptpro/` | Packaged review bundles with SHA256 sidecars |
| `configs/systemd/qwen25-local-openai-gateway.service` | S100P resident Qwen gateway unit |
| `configs/systemd/openclaw-gateway.service` | S100P resident OpenClaw AI-NAS portal gateway unit |
| `configs/systemd/digua-openclaw-cloud-bridge.service` | Root system unit for the loopback OpenClaw cloud inference bridge |
| `dream_s100p_lladacpp/` | Isolated Dream7B llada.cpp-style research track; not a product route |
| `docs/` | Project decisions, runbooks, acceptance notes, and demo scripts |
| `tmp/demo_three_features_final_recheck/` | Local copies of the latest recheck reports |

## Verification Commands

Run these from `F:\Project\Digua` on the Windows host.

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'systemctl --user is-active openclaw-gateway.service; systemctl is-active qwen25-local-openai-gateway.service || systemctl --user is-active qwen25-local-openai-gateway.service; sudo systemctl is-active digua-openclaw-cloud-bridge.service; ss -ltnp "sport = :18080"; curl -fsS http://127.0.0.1:8765/api/health; curl -fsS http://127.0.0.1:18080/health; curl -fsS http://127.0.0.1:18082/health'
```

Exactly one system- or user-scoped Qwen unit should own loopback port `18080`.
If both scopes are started, resolve the duplicate ownership before treating unit
status as production evidence; an HTTP 200 alone does not prove service-manager
convergence.

```powershell
py -3 scripts\probes\qwen25_ai_nas_acceptance_packet.py --out-root tmp\demo_three_features_final_recheck
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw/scripts/probes && python3 ai_nas_openclaw_nas_control_gate_probe.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw/scripts/probes && python3 ai_nas_edge_cloud_router_probe.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --use-qwen-classifier --require-qwen-touch --qwen-base-url http://127.0.0.1:18080 --execute-cloud --use-local-cloud-stub --require-cloud-call --timeout 180'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw && python3 scripts/product_smoke_test.py --base-url http://127.0.0.1:8765 --report-root /mnt/nas/openclaw/reports/product_delivery'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw && DIGUA_CLIP_BACKEND=clip DIGUA_CLIP_MODEL_DIR=/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32 DIGUA_CLIP_DEVICE=cpu DIGUA_CLIP_REQUIRE_PRODUCTION=1 DIGUA_ASR_BACKEND=transformers_whisper DIGUA_ASR_MODEL_DIR=/mnt/nas/openclaw/models/whisper_tiny DIGUA_ASR_REQUIRE_REAL=1 python3 gates/stage7_ai_space_product_delivery_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --no-rebuild'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw && DIGUA_CLIP_BACKEND=clip DIGUA_CLIP_MODEL_DIR=/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32 DIGUA_CLIP_DEVICE=cpu DIGUA_CLIP_REQUIRE_PRODUCTION=1 DIGUA_ASR_BACKEND=transformers_whisper DIGUA_ASR_MODEL_DIR=/mnt/nas/openclaw/models/whisper_tiny DIGUA_ASR_REQUIRE_REAL=1 python3 gates/stage9_demo_product_delivery_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --base-url http://127.0.0.1:8765 --qwen-url http://127.0.0.1:18080/health --timeout 45'
```

## Boundaries

- The standalone router probe still uses a controlled local cloud stub unless
  `--cloud-base-url` is explicitly set. The production portal is different: it
  uses the loopback OpenClaw bridge and only forwards public, non-private,
  complex requests to MiniMax. See
  `docs/openclaw_minimax_cloud_overflow_20260718.md`.
- Qwen `/health` now returns HTTP 503 unless its runtime executable, config,
  library directory and active HBM file exist. Live inference still requires a
  real request and cannot be accepted from health metadata alone.
- Do not claim face recognition, family member identity recognition, age/gender/race/emotion/health inference, cloud vision, or cloud ASR.
- Smart Classification creates virtual collections by default. Physical organization must go through Copy Plan / Harness approval and rollback.
- The subtitle gate validates local ASR mechanics with a synthetic demo audio fixture; production demos should use real user-provided media.
- Dream7B is no longer the promoted product path. It remains useful as runtime,
  batching, telemetry, and validation history. The latest seq128 segmented-HBM
  research route is logits-invalid for the current full-BPU path and must stay
  out of generation/product routing until a logits-valid candidate exists.
- The local checkout is now a valid git repo with remote
  `https://github.com/zhexuexiaotudou/-agent-s100-.git`. Large unrelated
  Dream7B, tokenizer, and journal artifacts are not part of the harness upload
  scope unless explicitly staged.
