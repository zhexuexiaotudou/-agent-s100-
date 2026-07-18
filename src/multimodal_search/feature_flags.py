from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MultimodalFeatureFlags:
    multimodal_search_enabled: bool = True
    multimodal_metadata_index_enabled: bool = True
    image_embedding_enabled: bool = True
    image_embedding_required_for_delivery: bool = True
    production_semantic_model_required: bool = True
    min_live_image_embeddings: int = 5
    image_semantic_min_score: float = 0.24
    image_semantic_relative_margin: float = 0.015
    document_embedding_enabled: bool = False
    ocr_enabled: bool = False
    video_keyframe_enabled: bool = False
    video_keyframe_embedding_enabled: bool = False
    subtitle_extraction_enabled: bool = True
    local_asr_required_for_delivery: bool = True
    audio_transcript_enabled: bool = False
    asr_enabled: bool = False
    local_vlm_caption_enabled: bool = False
    symbolic_caption_enabled: bool = True
    vector_extension_enabled: str = "auto"
    vector_numpy_fallback_enabled: bool = True
    cloud_vision_enabled: bool = False
    cloud_ocr_enabled: bool = False
    cloud_asr_enabled: bool = False
    face_identification_enabled: bool = False
    biometric_recognition_enabled: bool = False
    sensitive_attribute_inference_enabled: bool = False
    qwen_tool_execution_enabled: bool = False
    destructive_actions_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_feature_flags(path: str | Path | None = None) -> MultimodalFeatureFlags:
    if path is None:
        return MultimodalFeatureFlags()
    p = Path(path)
    if not p.exists():
        return MultimodalFeatureFlags()
    data = json.loads(p.read_text(encoding="utf-8"))
    valid = {field.name for field in MultimodalFeatureFlags.__dataclass_fields__.values()}
    return MultimodalFeatureFlags(**{key: value for key, value in data.items() if key in valid})
