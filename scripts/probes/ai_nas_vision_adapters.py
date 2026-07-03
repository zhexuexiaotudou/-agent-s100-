#!/usr/bin/env python3
"""Adapter registry for product-grade vision components."""

from __future__ import annotations

import importlib.util
import os
import shutil


def _env(name: str) -> str:
    return str(os.environ.get(name) or "").strip()


def _module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _command(name: str) -> bool:
    return shutil.which(name) is not None


def _adapter(
    name: str,
    kind: str,
    *,
    ready: bool,
    product_grade: bool,
    runtime: str,
    model_id: str = "",
    endpoint: str = "",
    fallback: str = "",
    failure_reason: str = "",
    confidence_cap: float = 1.0,
    required_for: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "kind": kind,
        "ready": bool(ready),
        "product_grade": bool(product_grade),
        "runtime": runtime,
        "model_id": model_id,
        "endpoint_configured": bool(endpoint),
        "fallback": fallback,
        "failure_reason": "" if ready else failure_reason,
        "confidence_cap": max(0.0, min(1.0, float(confidence_cap))),
        "required_for": required_for or [],
    }


def build_vision_adapter_registry() -> dict:
    caption_endpoint = _env("AI_NAS_VISION_CAPTION_ENDPOINT")
    caption_model = _env("AI_NAS_VISION_CAPTION_MODEL")
    embedding_endpoint = _env("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT")
    embedding_model = _env("AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL") or _env("AI_NAS_SIGLIP_MODEL") or _env("AI_NAS_CLIP_MODEL")
    detector_endpoint = _env("AI_NAS_VISION_DETECTOR_ENDPOINT") or _env("AI_NAS_YOLO_ENDPOINT")
    detector_model = _env("AI_NAS_VISION_DETECTOR_MODEL") or _env("AI_NAS_YOLO_MODEL")
    region_endpoint = _env("AI_NAS_VISION_REGION_ENDPOINT") or _env("AI_NAS_REGION_ATTRIBUTE_ENDPOINT")
    region_model = _env("AI_NAS_HUMAN_PARSING_MODEL") or _env("AI_NAS_REGION_ATTRIBUTE_MODEL")

    ocr_endpoint = _env("AI_NAS_OCR_ENDPOINT")
    ocr_model = _env("AI_NAS_OCR_MODEL")
    tesseract_ready = _command("tesseract") or _module("pytesseract")
    paddleocr_ready = _module("paddleocr")
    onnx_ready = _module("onnxruntime")
    torch_ready = _module("torch")
    transformers_ready = _module("transformers")
    cv_ready = _module("cv2")
    pil_ready = _module("PIL")
    numpy_ready = _module("numpy")
    sqlite_vec_ready = _module("sqlite_vec")

    ocr_ready = bool(ocr_endpoint or paddleocr_ready or tesseract_ready)
    embedding_ready = bool(embedding_endpoint or (embedding_model and (onnx_ready or torch_ready or transformers_ready)))
    detector_ready = bool(detector_endpoint or (detector_model and (onnx_ready or torch_ready)))
    region_ready = bool(region_endpoint or (region_model and (onnx_ready or torch_ready or cv_ready)))

    adapters = [
        _adapter(
            "ocr.primary",
            "ocr",
            ready=ocr_ready,
            product_grade=bool(ocr_endpoint or paddleocr_ready),
            runtime="http_json_ocr" if ocr_endpoint else ("paddleocr" if paddleocr_ready else ("tesseract" if tesseract_ready else "none")),
            model_id=ocr_model or ("paddleocr" if paddleocr_ready else ("tesseract" if tesseract_ready else "")),
            endpoint=ocr_endpoint,
            fallback="tesseract" if tesseract_ready and not paddleocr_ready else "",
            failure_reason="missing_AI_NAS_OCR_ENDPOINT_or_paddleocr_or_tesseract",
            confidence_cap=0.70 if tesseract_ready and not (ocr_endpoint or paddleocr_ready) else (1.0 if ocr_ready else 0.0),
            required_for=["document_search", "screenshot_search", "receipt_invoice_search"],
        ),
        _adapter(
            "caption.openai_compatible_vlm",
            "caption_vlm",
            ready=bool(caption_endpoint and caption_model),
            product_grade=bool(caption_endpoint and caption_model),
            runtime="openai_compatible_http" if caption_endpoint else "none",
            model_id=caption_model,
            endpoint=caption_endpoint,
            failure_reason="AI_NAS_VISION_CAPTION_ENDPOINT_and_MODEL_not_configured",
            confidence_cap=1.0 if caption_endpoint and caption_model else 0.45,
            required_for=["rich_caption", "relationship_search", "top_n_visual_verification"],
        ),
        _adapter(
            "embedding.image_text",
            "image_text_embedding",
            ready=embedding_ready,
            product_grade=embedding_ready,
            runtime="http" if embedding_endpoint else ("onnxruntime" if onnx_ready else ("torch" if torch_ready else "none")),
            model_id=embedding_model,
            endpoint=embedding_endpoint,
            fallback="local_visual_embedding_v1",
            failure_reason="no_clip_siglip_or_image_text_embedding_adapter_configured",
            confidence_cap=1.0 if embedding_ready else 0.48,
            required_for=["free_text_image_search", "semantic_scene_search", "multilingual_image_search"],
        ),
        _adapter(
            "detector.person_object",
            "detector",
            ready=detector_ready,
            product_grade=detector_ready,
            runtime="http" if detector_endpoint else ("onnxruntime" if onnx_ready else ("torch" if torch_ready else "none")),
            model_id=detector_model,
            endpoint=detector_endpoint,
            failure_reason="no_yolo_or_detector_adapter_configured",
            confidence_cap=1.0 if detector_ready else 0.40,
            required_for=["person_search", "object_localization", "region_attributes"],
        ),
        _adapter(
            "region.upper_clothing",
            "region_attributes",
            ready=region_ready,
            product_grade=region_ready,
            runtime="http" if region_endpoint else ("onnxruntime" if onnx_ready else ("torch" if torch_ready else ("opencv" if cv_ready else "none"))),
            model_id=region_model,
            endpoint=region_endpoint,
            failure_reason="no_human_parsing_or_region_attribute_model_configured",
            confidence_cap=1.0 if region_ready else 0.40,
            required_for=["upper_clothing_color", "bag_color", "fine_grained_person_attributes"],
        ),
        _adapter(
            "vector.sqlite_exact",
            "vector_store",
            ready=True,
            product_grade=sqlite_vec_ready,
            runtime="sqlite_vec" if sqlite_vec_ready else "sqlite_json_exact_fallback",
            model_id="sqlite_vec" if sqlite_vec_ready else "sqlite_exact",
            fallback="sqlite_json_exact_fallback",
            confidence_cap=1.0,
            required_for=["small_library_vector_search", "development_gate"],
        ),
        _adapter(
            "evidence.artifact_store",
            "evidence",
            ready=True,
            product_grade=True,
            runtime="sqlite_and_authenticated_http",
            model_id="vision_artifacts",
            confidence_cap=1.0,
            required_for=["auditable_results", "ui_evidence_drawer", "acl_safe_artifacts"],
        ),
    ]
    return {
        "registry_schema": "ai_nas_vision_adapter_registry_v1",
        "adapters": adapters,
        "ready_by_kind": {item["kind"]: item["ready"] for item in adapters},
        "product_grade_by_kind": {item["kind"]: item["product_grade"] for item in adapters},
        "missing_product_adapters": [
            item["kind"] for item in adapters
            if item["kind"] not in {"vector_store", "evidence"} and not item["product_grade"]
        ],
    }
