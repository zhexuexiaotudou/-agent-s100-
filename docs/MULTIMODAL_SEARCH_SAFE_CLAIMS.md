# Multimodal Search v1 Safe Claims

Date: 2026-07-05

## Supported Claims

- Local-first multimodal indexing is implemented for documents, images, video metadata, audio metadata, code, and archives.
- Document search uses SQLite FTS with redacted snippets and evidence references.
- Image search uses a local lightweight Pillow/Numpy embedding adapter for safe color/brightness/aspect-oriented retrieval unless a real CLIP/SigLIP-compatible backend is separately validated by `26120_real_image_text_embedding_gate`.
- Video and audio are indexed in metadata-only mode while content-level keyframe/OCR/ASR features remain disabled by feature flag.
- API responses avoid raw local/NAS paths and return hashed path identifiers only.
- Qwen may consume returned evidence, but Qwen does not execute tools or mutate NAS data in this feature.

## Claims To Avoid

- Do not claim general-purpose visual understanding comparable to OpenCLIP/SigLIP unless a real model is installed and validated.
- Do not claim face recognition, identity matching, biometric recognition, or sensitive attribute inference.
- Do not claim OCR, ASR, or video content understanding while the relevant flags are disabled.
- Do not claim whole-NAS access. v1 is allowlisted-root only.
- Do not claim public Gateway exposure or cloud processing.
- Do not claim 24-hour stability evidence for this feature. The current requested validation excludes 24-hour soak.

## Current Release Target

The intended v1 target is `multimodal_search_v1_deliverable_limited_semantic_ready` unless a real local CLIP/SigLIP-compatible image-text backend is detected and evaluated on this machine or on the S100P local appliance.

Safe user-facing wording for the limited target:

> Digua AI-NAS v1 provides local-first multimodal indexing and lightweight image search based on local visual features such as color, brightness, aspect, and metadata. It does not yet claim general-purpose OpenCLIP/SigLIP visual-semantic understanding.
