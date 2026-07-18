# Multimodal Search v1 Architecture

Date: 2026-07-05

## Scope

Multimodal Search v1 adds local-first NAS search across documents, images, video files, audio files, code, and archives. It is built for the current AI NAS route: OpenClaw/Qwen can understand and summarize returned evidence, but execution remains in the deterministic Workspace Harness/API layer.

## Components

- `src/multimodal_search/schema.py`: SQLite schema for assets, FTS chunks, media metadata, embeddings, search runs, and result evidence.
- `src/multimodal_search/indexer.py`: allowlisted-root scanner and index builder.
- `src/multimodal_search/hybrid_retriever.py`: FTS-first retrieval with metadata fallback and image embedding candidates when the query permits images.
- `src/multimodal_search/image_embedding_adapter.py`: local Pillow/Numpy image-text embedding adapter for color/brightness/aspect retrieval. It is not a face or biometric model.
- `src/multimodal_search/search_api.py`: service API used by route adapters and tests.
- `src/openclaw/routes/multimodal_search_routes.py`: OpenClaw route adapter.
- `web/templates/multimodal_search.html` plus `web/static/digua_multimodal_search.*`: static UI v2 search surface.

## Retrieval Path

1. Scan only allowlisted local/NAS roots.
2. Store redacted titles, hashed paths, file metadata, text chunks, and local embeddings.
3. Query planner redacts secrets and detects modality filters.
4. Retriever combines FTS, metadata, and image embeddings using a deterministic fusion score.
5. API returns evidence refs, redacted snippets, modality, score components, privacy level, and path hash. It does not return raw local/NAS paths.

## Assistant image relevance selection

For assistant image requests, `top_k` is a bounded candidate cap, not a target
result count. The assistant first distinguishes explicit object labels from
semantic visual concepts. Queries that resolve to a YOLO label require evidence
from `yolo_object_index`; a successful empty YOLO result is returned as zero and
never falls through to CLIP. If the object-search service is unavailable or
fails, the assistant reports that failure instead of substituting semantic
images that do not prove the requested object is present.

For non-object semantic requests, the planner translates supported Chinese visual concepts into
English CLIP variants and evaluates OR concepts independently. For example,
`花或者建筑` becomes one flower variant and one building/architecture variant
so a strong result from one concept cannot suppress the other concept.

`HybridRetriever` applies two gates to every variant:

- absolute image cosine score at or above `image_semantic_min_score`;
- score within `image_semantic_relative_margin` of that variant's best local
  candidate.

The defaults are `0.24` and `0.015` in
`configs/multimodal_search_feature_flags.json`. Selected variants are unioned,
deduplicated by asset, and sorted by evidence score. Image modality only scopes
the candidate set; it is not itself positive metadata evidence. The response
exposes candidate, selected, filtered, variant, and threshold counts under
`relevance_policy`, so zero, one, or several cards are all valid outcomes.

Unsupported Chinese visual concepts do not fall back to a generic `photo`
embedding. They return `unsupported_chinese_visual_concept` with zero results,
preventing weak but visually unrelated candidates from being presented as
matches.

## Optional Capabilities

OCR, video keyframe content indexing, keyframe embedding, audio transcript, and ASR are disabled by default in `configs/multimodal_search_feature_flags.json`. Video/audio are indexed in metadata-only mode in v1.

## Security Boundary

- Cloud vision/OCR/ASR are disabled.
- Face identification, biometric recognition, and sensitive attribute inference are disabled.
- Qwen has no tool execution authority for this feature.
- Destructive actions are disabled.
- Gateway exposure remains local/private; no public Gateway exposure is required.
