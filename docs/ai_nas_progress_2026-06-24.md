# AI-NAS Progress Update 2026-06-24

This note summarizes the current Digua / AI-NAS product progress that should be
tracked from this S100P + NAS repository. The raw gate JSON files and temporary
runtime reports stay in the local Digua workspace or NAS report folders; this
repo keeps the stable public summary, boundaries, and next engineering tasks.

## Current Position

The project has moved beyond the initial S100P bring-up baseline into a bounded
AI-NAS prototype:

- S100P provides the local AI route and OpenClaw control layer.
- NAS provides the Personal data root, report storage, media library, and
  durable workspace.
- The Web NAS OS portal now covers storage, media, backup, users, system,
  audit, search, and AI entry points.
- Search and AI answers are expected to be evidence-first: every accepted result
  should carry a path or source id, reasons, confidence, and permission scope.

The release boundary is still conservative. This is not a complete production
replacement for a high-end NAS appliance. RAID, native snapshots, full backup
engines, NVR, full mobile apps, Docker/VM app centers, real-time transcoding,
and face recognition remain out of scope for self-developed replacement.

## Verified Product Progress

| Area | Current status | Evidence boundary |
| --- | --- | --- |
| Ten AI-NAS goals | Verified | `ok_ai_nas_ten_goal_s100p_closure_gate`, `goals_ok=10/10` |
| Storage foundation | Verified | HTTP + SQLite + traversal-blocking storage foundation gate |
| Identity and ACL | Verified | `ok_nas_acl_identity_gate`; Web/API/AI retrieval must share permission checks |
| Personal root integration | Verified | Controlled real Personal root seed, search, and download path covered |
| Web NAS OS portal | Verified | `ok_nas_integrated_portal_gate`, 19/19 |
| OpenClaw NAS control | Verified | Storage list/upload/download/rename/copy/move/delete path covered |
| Qwen text route | Verified | Text entry uses the official local S100P Qwen2.5 route |
| Document search and RAG | Verified in bounded gates | SQLite/FTS, embedding search, folder RAG, grounded evidence contracts |
| Official PP-OCR bridge | Verified | Scanned image/PDF OCR results are written back to `ocr_results` and document index |
| Photo pipeline | Verified for coarse semantics | EXIF, GPS, labels, pHash, local visual embeddings, bounded photo search |
| Visual search portal | Verified at portal level | `ok_ai_nas_visual_search_gate`, but not yet mature fine-grained visual semantics |
| Scheduled rules | Verified | User-visible `index_refresh`, `duplicate_report`, and `folder_summary` dry-run rules |
| Media library | Verified | Movie metadata parsing, subtitles/poster sidecars, player links, no real-time transcoding claim |
| PWA/mobile entry | Verified structurally | Manifest, icon, service worker, mobile portal flows; no native backup app replacement |
| Production readiness | Currently ready in latest local gate | Latest local regression reported `ready_ai_nas_production_readiness_gate` with 0 blockers; face recognition remains a warning/out-of-scope item |

## What Changed Since The Earlier Baseline

1. The AI-NAS work is no longer just a product sketch. It now has named gates for
   storage, identity, snapshot/recovery, backup/sync, portal, media, copilot,
   ops, app ecosystem, and top-level product closure.
2. The Personal root path is now represented by controlled real test data rather
   than only fixture folders.
3. OCR is no longer a generic blocker: the official S100P PP-OCR wrapper has a
   bridge into the document index path in the current local evidence.
4. The portal now includes scheduled organization rules, enhanced media cards,
   and PWA/mobile shell resources.
5. Permission-aware retrieval is treated as a cross-cutting invariant, not a UI
   feature. Hidden files must not influence results, counts, labels, thumbnails,
   or assistant wording.

## Current Visual Search Gap

The weak point is fine-grained image understanding and database embeddings. The
current local visual embedding path is useful as a fallback, but it is not enough
for queries such as:

```text
找穿白色上衣的照片
white shirt photo
白色 T 恤的人
```

The reason is straightforward: whole-image color histograms and path labels can
confuse white clothes with white cars, white walls, white documents, or white
backgrounds. The next visual search milestone needs region-level semantics:

- detect `person`;
- localize upper-body or clothing regions;
- extract clothing attributes such as color and garment type;
- combine those attributes with CLIP/SigLIP/Chinese-CLIP-style text-image
  embeddings;
- run all candidate generation and final return through ACL filtering;
- return evidence such as `person detected`, `upper_clothing=white`,
  `model_id`, `confidence`, and `acl_visible=true`.

The handoff prompt and implementation contract are in
[`docs/ai_nas_visual_search_embedding_handoff.md`](ai_nas_visual_search_embedding_handoff.md).

## Next Gates

The next work should be implemented as explicit gates rather than ad hoc demos:

| Gate | Purpose |
| --- | --- |
| `ai_nas_image_attribute_index_gate` | Prove region-level person/clothing/object attributes are indexed with model/runtime identity |
| `ai_nas_semantic_image_search_gate` | Prove Chinese and English natural-language image search over at least 50 mixed images |
| `ai_nas_visual_acl_leakage_gate` | Prove invisible images do not affect labels, counts, ranking, thumbnails, or assistant wording |
| `ai_nas_visual_search_portal_gate` | Prove the Web portal and chat route display evidence-backed visual results |

Minimum evaluation cases:

- person wearing a white top;
- person wearing a non-white top;
- white car;
- white wall or background;
- white document/screenshot;
- meal, beach, and irrelevant negative images;
- one principal who can see all images;
- one principal who can see only a subset.

## Recommended Next Implementation Order

1. Add a visual attribute schema beside the existing image embedding table.
2. Build an offline index worker for photo thumbnails, person/object regions,
   clothing colors, captions, and text-image embeddings.
3. Add query parsing for Chinese and English clothing/color/object intents.
4. Add reranking that combines text-image similarity with structured attributes.
5. Add ACL leakage tests before exposing results in the portal.
6. Wire the OpenClaw/Qwen chat route so photo queries use visual search, not
   generic text search.
