# AI-NAS Multimodal Semantics Roadmap

Date: 2026-06-23

## Current Evidence

The current official vision route is demo-ready, not production-complete:

- `docs/ai_nas_official_vision_route_2026-06-23.md`
- verdict: `ok_ai_nas_official_vision_route_demo_ready`
- image detection: official S100 YOLO route verified on S100P
- video route: frame extraction plus YOLO verified on S100P
- OCR: official PP-OCRv3 HBM model-info verified; production wrapper is still
  a remaining risk in the vision route document
- semantic image retrieval: LLM-caption-first contract is now the product
  direction; local visual embedding remains fallback/plumbing evidence only

## Product Principle

Visual AI features must return evidence, not just labels. Every image, video,
OCR, or semantic-search result needs:

- source path or source ID within caller permission scope;
- model/runtime used;
- confidence or deterministic matching reason;
- generated artifact path;
- privacy classification if people, children, faces, GPS, or documents are
  detected;
- refusal or redaction behavior for inaccessible sources.

## Roadmap

| Stage | Capability | Current status | Work needed | Gate |
| --- | --- | --- | --- | --- |
| M1 | Object detection for images | S100P YOLO verified | Wrap as AI-NAS worker with report contract and ACL filtering | `ai_nas_image_detection_worker_gate` |
| M2 | Video frame indexing | Frame extraction + YOLO verified | Persist sampled frame index, source timestamps, and evidence links | `ai_nas_video_frame_index_gate` |
| M3 | OCR for images/PDF screenshots | PP-OCRv3 HBM available; wrapper risk remains | Production wrapper, text normalization, layout metadata, ACL-filtered OCR index | `ai_nas_ocr_worker_gate` |
| M4 | LLM-caption-first semantic image search | Caption-first fixture gate added; local fallback still available | Attach an OpenAI-compatible or S100P vision-caption worker, persist structured captions, filter by ACL, test Chinese/English prompts | `ai_nas_llm_caption_visual_search_gate` then `ai_nas_semantic_image_search_gate` |
| M5 | Duplicate and similar media | Current local photo pipeline has duplicate/similar evidence | Add cross-album/cross-device manifests and approval flow | `ai_nas_media_duplicate_manifest_gate` |
| M6 | Person/face privacy | Not production-gated | Avoid identity claims by default; add opt-in private face grouping only if legally and product-approved | `ai_nas_person_privacy_gate` |
| M7 | Location/time/event grouping | Metadata and timeline exist in limited form | EXIF/GPS privacy filter, event clustering, time-zone handling, hidden-source redaction | `ai_nas_event_grouping_gate` |
| M8 | Multimodal conversation | Not separately gated | Conversation state links text, OCR, image labels, frames, and approvals | `ai_nas_multimodal_conversation_gate` |

## OCR Contract

OCR output is content, not metadata. It must be permission-scoped and cited like
document text.

Minimum OCR worker output:

```json
{
  "source_id": "string",
  "caller_visible": true,
  "runtime": "official_s100_ppocrv3_or_named_fallback",
  "text_blocks": [
    {
      "text": "string",
      "bbox": [0, 0, 0, 0],
      "confidence": 0.0
    }
  ],
  "artifact_paths": {
    "json": "string",
    "markdown": "string"
  }
}
```

## Video Frame Contract

Video understanding for the next release should stay frame-based:

- sample frames deterministically by time or scene-change rule;
- store `video_source_id`, `frame_index`, `timestamp_ms`, `frame_path`, and
  detection/OCR outputs;
- answer questions with frame timestamps and source citations;
- avoid claims about full temporal reasoning until a separate video model gate
  exists.

## Person, Face, And Privacy Policy

Default release behavior:

- Detect generic `person` only when a verified detector returns that class.
- Do not identify people by name.
- Do not build face clusters by default.
- Do not expose child/person labels across permission boundaries.
- Treat EXIF GPS as sensitive content.
- Do not show hidden-person counts such as "there are more private photos."

Any future person/face feature must be opt-in, per-library scoped, reversible,
and covered by `ai_nas_person_privacy_gate`.

## Semantic Search Gate Definition

The semantic search path should be caption-first:

1. A large vision model writes a structured caption for every photo.
2. The index persists caption, objects, generic people, clothing, colors,
   visible text, model identity, and privacy flags in SQLite.
3. Retrieval uses caption/attribute evidence first, then optional embedding or
   CLIP-style reranking.
4. Whole-image color hints are not enough for clothing queries such as
   "person wearing a white top."

`ai_nas_llm_caption_visual_search_gate` validates the first product slice:

- a white-top person fixture is found for Chinese and English queries;
- white car, white wall, white document/screenshot, and non-white clothing
  fixtures do not enter the top-5 for white-top queries;
- face recognition and identity matching are not performed.

`ai_nas_semantic_image_search_gate` should then include:

- at least 50 images across cars, people, meals, screenshots, documents, and
  irrelevant negatives;
- Chinese and English natural-language queries;
- one user who can see all images and one user who can see only a subset;
- proof that inaccessible images do not affect returned labels, counts, or
  thumbnails;
- artifact paths for embeddings, search results, model/runtime identity, and
  report summaries;
- fallback behavior when the selected caption runtime is unavailable.

Expected verdict:

```text
ok_ai_nas_semantic_image_search_gate
```

## Release Wording Boundary

Allowed after the current local gate:

> The search contract is caption-first and can distinguish a white top from
> whole-image white distractors in controlled fixtures. Production use still
> requires a configured large vision-caption provider.

Allowed before production caption provider deployment:

> Official S100 image detection and frame-based video route are demo-ready, with
> local visual embedding fallback for coarse semantic search evidence.

Not allowed until future gates pass:

> Production caption coverage for all photos, production face/person identity
> semantics, full video understanding, or permission-complete multimodal search.
