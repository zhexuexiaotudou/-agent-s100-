# 26000_multimodal_schema_and_flags_gate

- ok: `True`

```json
{
  "feature_flags": {
    "asr_enabled": false,
    "audio_transcript_enabled": false,
    "biometric_recognition_enabled": false,
    "cloud_asr_enabled": false,
    "cloud_ocr_enabled": false,
    "cloud_vision_enabled": false,
    "destructive_actions_enabled": false,
    "document_embedding_enabled": false,
    "face_identification_enabled": false,
    "image_embedding_enabled": true,
    "image_embedding_required_for_delivery": true,
    "multimodal_metadata_index_enabled": true,
    "multimodal_search_enabled": true,
    "ocr_enabled": false,
    "qwen_tool_execution_enabled": false,
    "sensitive_attribute_inference_enabled": false,
    "vector_extension_enabled": "auto",
    "vector_numpy_fallback_enabled": true,
    "video_keyframe_embedding_enabled": false,
    "video_keyframe_enabled": false
  },
  "ok": true,
  "tables": [
    "mm_assets",
    "mm_embeddings",
    "mm_media_metadata",
    "mm_search_results",
    "mm_search_runs",
    "mm_text_chunks",
    "mm_text_chunks_fts",
    "mm_text_chunks_fts_config",
    "mm_text_chunks_fts_content",
    "mm_text_chunks_fts_data",
    "mm_text_chunks_fts_docsize",
    "mm_text_chunks_fts_idx",
    "mm_thumbnails",
    "mm_video_keyframes"
  ]
}
```
