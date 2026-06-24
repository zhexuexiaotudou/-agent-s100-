# AI-NAS Visual Search And Embedding Handoff

This handoff turns the current visual-search weakness into a concrete design
request for GPT Pro or a follow-up Codex implementation thread.

## Problem

The current AI-NAS photo search can use EXIF, GPS, labels, pHash, OCR text, and a
local visual embedding fallback. That is enough for bounded coarse queries such
as `white car`, `beach photo`, or `invoice screenshot`, but it is not enough for
fine-grained natural-language photo search:

```text
找穿白色上衣的照片
white shirt photo
白色 T 恤的人
```

The next version must distinguish white clothing from white backgrounds, white
cars, white walls, and white documents. That requires region-level visual
evidence, not only whole-image color statistics.

## Non-Negotiable Constraints

- Stay local/offline by default. Do not upload private NAS photos to cloud
  services unless a separate user-approved mode exists.
- Web, API, and AI retrieval must use the same ACL model.
- Hidden images must not influence returned results, counts, labels, captions,
  thumbnails, or assistant wording.
- Do not perform face recognition, face clustering, or identity matching by
  default.
- Generic `person` detection is allowed when supported by a verified detector.
- EXIF GPS, children/person terms, documents, receipts, and screenshots must be
  privacy-classified.
- Every result must include evidence: source path or id, model/runtime,
  confidence, matched attributes, artifact path, and permission state.

## Target Architecture

```text
NAS Personal root
  -> file scanner
  -> thumbnail and metadata extractor
  -> OCR worker for screenshots/documents
  -> object/person detector
  -> clothing/region attribute extractor
  -> caption and embedding worker
  -> SQLite + vector rows + artifact reports
  -> ACL-aware visual search API
  -> Web NAS OS / OpenClaw chat route
```

The architecture should support three evidence layers:

1. Metadata evidence: EXIF, GPS, file path, folder, time, OCR text.
2. Region evidence: detected person/object boxes, clothing region, color, class.
3. Embedding evidence: text-image similarity from CLIP/SigLIP/Chinese-CLIP or a
   named local fallback.

## Suggested Schema

The exact table names can be adjusted to match the existing SQLite index, but
the following contracts should exist.

### `image_embeddings`

| Field | Purpose |
| --- | --- |
| `path` | Absolute source path or stable file id |
| `relative_path` | NAS-relative path used for display and ACL checks |
| `model_id` | Runtime/model id, for example `clip_vit_b32_s100p` |
| `dim` | Embedding dimension |
| `vector_json` | Serialized vector or pointer to vector storage |
| `status` | `completed`, `blocked_missing_runtime`, `failed`, etc. |
| `engine` | `transformers.CLIPModel`, `SigLIP`, `local_visual_fallback`, etc. |
| `metadata_json` | Runtime and preprocessing metadata |
| `updated_at` | Last index time |

### `image_regions`

| Field | Purpose |
| --- | --- |
| `region_id` | Stable region id |
| `path` | Source file |
| `region_type` | `person`, `upper_body`, `clothing`, `object`, `document` |
| `bbox_json` | Bounding box in image coordinates |
| `label` | Detector class |
| `confidence` | Detector confidence |
| `model_id` | Detector/runtime identity |
| `artifact_path` | JSON/preview artifact |

### `image_attributes`

| Field | Purpose |
| --- | --- |
| `attribute_id` | Stable attribute id |
| `region_id` | Linked region |
| `attribute_type` | `color`, `garment_type`, `object_type`, `privacy_class` |
| `value` | `white`, `shirt`, `car`, `sensitive_gps`, etc. |
| `confidence` | Attribute confidence |
| `evidence_json` | Color samples, classifier scores, reason text |

### `visual_search_artifacts`

| Field | Purpose |
| --- | --- |
| `query_id` | Search/report id |
| `principal` | Caller identity or role used for ACL filtering |
| `query_text` | Original query |
| `normalized_intents_json` | Parsed color/object/person/clothing/time intents |
| `results_json` | Returned paths, scores, reasons, and hidden-source policy result |
| `model_versions_json` | Runtime identities used by the search |

## Query Contract For "White Shirt"

For `找穿白色上衣的照片`, the system should not search for white pixels in the
whole image. It should:

1. Parse the query as:

```json
{
  "target": "photo",
  "entity": "person",
  "region": "upper_clothing",
  "attributes": {
    "color": ["white", "off-white", "light gray"],
    "garment_type": ["shirt", "t-shirt", "top", "upper_clothing"]
  }
}
```

2. Retrieve only images visible to the caller or apply ACL filters before any
   user-visible result is generated.
3. Use image embedding recall to find candidates.
4. Require region evidence for high-confidence matches:

```text
person detected;
upper_clothing region detected;
upper_clothing.color=white;
text_image_similarity=0.73;
acl_visible=true
```

5. Penalize or reject candidates where `white` is attached to `car`, `wall`,
   `document`, `background`, or other non-clothing regions.

## API Surface

Candidate endpoints:

```text
POST /api/vision/index
GET  /api/vision/search?query=<text>&limit=20
GET  /api/media/search?type=image&query=<text>&limit=20
```

Result shape:

```json
{
  "ok": true,
  "results": [
    {
      "relative_path": "Photos/2026/example.jpg",
      "open_url": "/api/storage/open?path=...",
      "preview_url": "/api/media/thumb?path=...",
      "confidence": 0.82,
      "matched_attributes": ["person", "upper_clothing:white"],
      "reasons": [
        "Detected person region",
        "Upper clothing color classified as white",
        "Text-image similarity matched the query"
      ],
      "model": {
        "detector": "named_detector_runtime",
        "embedding": "named_clip_or_fallback_runtime"
      },
      "privacy": {
        "face_recognition_performed": false,
        "gps_sensitive": false,
        "person_identity_verified": false
      }
    }
  ]
}
```

## Gate Requirements

### `ai_nas_image_attribute_index_gate`

Proves that the indexer can extract and persist image regions, clothing/object
attributes, model identity, confidence, and artifacts.

### `ai_nas_semantic_image_search_gate`

Minimum fixture:

- at least 50 images;
- person wearing a white top;
- person wearing non-white tops;
- white car;
- white background/wall;
- white document or screenshot;
- meals, beach, irrelevant negatives;
- Chinese and English queries.

Required metrics:

- precision@5;
- recall@10;
- false positives by class;
- false negatives by class;
- confidence distribution;
- fallback behavior when the production embedding runtime is unavailable.

### `ai_nas_visual_acl_leakage_gate`

Use at least two principals:

- one user can see all images;
- one user can see only a subset.

The restricted user must not see or infer hidden-image paths, thumbnails,
captions, labels, counts, rejected candidates, or "more private photos exist"
wording.

### `ai_nas_visual_search_portal_gate`

Proves that Web NAS OS and OpenClaw/Qwen chat route visual queries to the visual
search endpoint and render evidence-backed results.

## GPT Pro Prompt

```text
You are a senior local AI-NAS product architect and visual retrieval/vector
database engineer. Design an implementable upgrade plan for my Digua / AI-NAS
project so a user can type queries such as "找穿白色上衣的照片", "white shirt
photo", or "白色 T 恤的人" and the system returns the correct NAS photos with
thumbnail, path, evidence, and confidence.

Project context:
- Local workspace: F:\Project\Digua.
- Product shape: low-cost NAS + S100P local AI layer + OpenClaw control layer +
  Web NAS OS portal.
- Core code anchors:
  - scripts/probes/ai_nas_operator_portal_server.py
  - scripts/probes/ai_nas_common.py
  - scripts/probes/ai_nas_identity.py
  - scripts/probes/ai_nas_media.py
  - scripts/probes/nas_web_os_portal.html
- Current system already has SQLite indexing, file search, text/document
  embeddings, OCR, photo metadata, EXIF/GPS, pHash, local visual embedding
  fallback, and a bounded photo semantic search prototype.
- Current weakness: image embeddings are mostly PIL histogram / metadata /
  filename-label level. They cannot reliably understand fine-grained semantics
  such as "wearing a white top". A white wall, white car, white document, and
  white shirt can be confused.
- Existing functions to consider:
  - image_embedding_runtime_status()
  - ensure_image_embeddings_for_photos()
  - search_photo_semantic_index()
- Existing vision route: S100P official vision/YOLO route, PP-OCR, and local
  Qwen2.5 text entry exist, but do not assume production CLIP/multimodal search
  is complete.
- Must prefer local/offline processing. Do not upload private NAS photos to a
  cloud service by default.
- Web, API, and AI retrieval must share the same permission model. Search
  results must be ACL/visible-path filtered and must not leak hidden photo
  paths, counts, labels, thumbnails, or wording such as "there are more private
  photos".
- Do not do face recognition, face clustering, or identity matching by default.
  Generic person detection is allowed. Future face/person identity features
  require opt-in, per-library authorization, revocation, and a separate privacy
  gate.
- Every result must return evidence, not only labels: source path/source id,
  thumbnail/open URL, model/runtime, matched attributes, confidence, generated
  embedding/detection artifact path, privacy classification, and degradation
  reason when applicable.

Please output:
1. Diagnosis: why the current local visual embedding/metadata search cannot
   solve "white shirt" reliably.
2. Architecture: offline indexing pipeline and query pipeline.
3. Model strategy: quick MVP and higher-quality production path, including
   Chinese query support and fallback behavior.
4. Database schema: image embeddings, regions, attributes, captions/artifacts,
   ACL scope, model/runtime versioning, and orphan cleanup.
5. Exact "white shirt" implementation: person/upper-body/clothing region first,
   then clothing color and garment type; reject white car/wall/document matches.
6. API/UI changes for Web NAS OS and OpenClaw/Qwen chat routing.
7. Permission and privacy rules.
8. Gate design: ai_nas_image_attribute_index_gate,
   ai_nas_semantic_image_search_gate, ai_nas_visual_acl_leakage_gate, and
   ai_nas_visual_search_portal_gate.
9. Three-stage implementation order: MVP, usable version, production hardening.
10. A checklist detailed enough for Codex to start editing the codebase.
```
