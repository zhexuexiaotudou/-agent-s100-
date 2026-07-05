# Multimodal Search Real Image Embedding Status

Date: 2026-07-05

## Current Boundary

The v1 deliverable defaults to `digua-local-visual-text-embedding-v1`, implemented with local Pillow/Numpy features. This backend is local-only and useful for coarse image retrieval, but it is not OpenCLIP, SigLIP, or a general image-text semantic model.

## Upgrade Gate

The release may claim `multimodal_search_v1_real_image_semantic_ready` only when both gates pass:

- `reports/multimodal_search/26120_real_image_text_embedding_gate.json`
- `reports/multimodal_search/26130_real_image_semantic_eval_gate.json`

The gate must show a validated local or S100P-local CLIP/SigLIP-compatible backend, model identity, vector dimension, and semantic eval result. Old evidence snapshots are not enough.

## Safe Wording

Use:

> Local-first multimodal search with lightweight local image feature embeddings and metadata-aware evidence retrieval.

Avoid:

> OpenCLIP/SigLIP-level visual-semantic search, clothing/person attribute understanding, OCR/ASR/video content understanding, or face/identity recognition.
