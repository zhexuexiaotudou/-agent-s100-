# Multimodal Search v1 Safe Claims

Date: 2026-07-05

## Supported Claims

- Local-first multimodal indexing is implemented for documents, images, video metadata, audio metadata, code, and archives.
- Document search uses SQLite FTS with redacted snippets and evidence references.
- Image search uses a local lightweight Pillow/Numpy embedding adapter for safe color/brightness/aspect-oriented retrieval.
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

The intended v1 target is `multimodal_search_v1_ready_with_optional_ocr_video_audio_disabled`: image embedding, document FTS, metadata indexing, API, UI files, eval, tests, and privacy boundaries pass; optional OCR/video/audio content extraction remains disabled.
