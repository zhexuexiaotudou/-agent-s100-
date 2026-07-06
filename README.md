# Digua S100P / OpenClaw AI-NAS Demo

This workspace is the evidence and demo repo for turning an S100P board into an
always-on AI-NAS gateway: OpenClaw provides the NAS-facing experience, Qwen runs
locally on S100P, and an edge-cloud router decides when a request can leave the
device.

## Current Status

Status timestamp: 2026-07-06 14:29 CST.

The three demo expectations are now satisfied on the S100P test machine:

| Demo | Expected behavior | Current result | Evidence |
| --- | --- | --- | --- |
| 1. S100P as resident gateway | S100P keeps the AI gateway online after login/logout and exposes a stable local entry point | `openclaw-gateway.service` and `qwen25-local-openai-gateway.service` are both `active/enabled`; `loginctl` linger is `yes` | OpenClaw `/api/health` on `127.0.0.1:8765`; Qwen `/health` on `127.0.0.1:18080` |
| 2. OpenClaw implements AI-NAS | OpenClaw can drive NAS operations, not just chat | `ok_ai_nas_openclaw_nas_control_gate`, 10/10 checks passed | `/mnt/nas/openclaw/reports/qwen25_ai_nas/openclaw_nas_control_gate_20260629-210023-832862/openclaw_nas_control_gate.json` |
| 3. Edge + cloud routing | Every query first enters local Qwen; private/simple requests stay on S100P; public complex requests can use a controlled cloud endpoint | `ok_ai_nas_edge_cloud_router`; 3/3 classifications came from `qwen_structured_json`; 2 local, 1 cloud; no privacy query was sent to cloud | `/mnt/nas/openclaw/reports/qwen25_ai_nas/edge_cloud_router_20260629-210034-495865/edge_cloud_router.json` |

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

The default harness path allows only bounded copy flows that pass policy,
typed approval, signed approval token, source rehash, target-absent check, and
the allowlisted dispatcher. Delete, move, rename, chmod, chown, overwrite,
recursive operations, arbitrary shell execution, Qwen autonomous tool execution,
and private raw cloud egress remain out of scope.

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
- **Privacy floor**: invoice, family photo, chat screenshot, NAS folder, finance,
  and other private requests are forced local even if the cloud path exists.
- **Evidence-first delivery**: every demo claim is backed by JSON/Markdown
  reports on `/mnt/nas/openclaw/reports/...`, not by screenshots alone.
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
| `scripts/product_smoke_test.py` | Product-level live HTTP smoke gate for `/api/product/status`, evidence, YOLO, multimodal, and harness boundaries |
| `gates/stage7_ai_space_product_delivery_gate.py` | Aggregate product gate for live CLIP, person attributes, AI Space, smart classification, and subtitle extraction |
| `src/person_attribute/` | Local-only non-identifying person attribute search |
| `src/ai_space/` | AI Space catalog and facets |
| `src/smart_classification/` | Virtual smart classification collections |
| `src/subtitle_extraction/` | Local ASR transcript, SRT/VTT, and search support |
| `src/product_jobs/` | Product background job queue API |
| `src/harness/` | Harness policy, copy route guard, and token-budget integration |
| `src/openclaw/` | OpenClaw default-service middleware and API route adapters |
| `gates/stage*_gates.py` | Stage-gated AI-NAS harness validation scripts |
| `reports/` | Gate outputs, trace JSONL, and regression evidence |
| `evidence_for_gptpro/` | Packaged review bundles with SHA256 sidecars |
| `configs/systemd/qwen25-local-openai-gateway.service` | S100P resident Qwen gateway unit |
| `configs/systemd/openclaw-gateway.service` | S100P resident OpenClaw AI-NAS portal gateway unit |
| `dream_s100p_lladacpp/` | Isolated Dream7B llada.cpp-style research track; not a product route |
| `docs/` | Project decisions, runbooks, acceptance notes, and demo scripts |
| `tmp/demo_three_features_final_recheck/` | Local copies of the latest recheck reports |

## Verification Commands

Run these from `F:\Project\Digua` on the Windows host.

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'systemctl --user is-active openclaw-gateway.service; systemctl --user is-active qwen25-local-openai-gateway.service; curl -fsS http://127.0.0.1:8765/api/health; curl -fsS http://127.0.0.1:18080/health'
```

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

## Boundaries

- The router demo uses a controlled local cloud stub unless `--cloud-base-url`
  is explicitly pointed at a real cloud service.
- Qwen `/health` still contains historical model/profile metadata fields that
  can look inconsistent. For acceptance, use the gate verdicts and generated
  report paths above as the source of truth.
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
