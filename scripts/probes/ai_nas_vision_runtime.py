#!/usr/bin/env python3
"""Runtime discovery for the product-grade vision data plane."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess

from ai_nas_vision_adapters import build_vision_adapter_registry
from ai_nas_ocr_adapter import product_ocr_runtime_status
from ai_nas_embedding_adapter import product_embedding_runtime_status
from ai_nas_region_adapter import product_region_runtime_status


def _env(name: str) -> str:
    return str(os.environ.get(name) or "").strip()


def _module_status(name: str) -> dict:
    spec = importlib.util.find_spec(name)
    return {
        "name": name,
        "importable": spec is not None,
    }


def _command_status(name: str, args: list[str] | None = None, timeout: int = 4) -> dict:
    exe = shutil.which(name)
    payload = {"command": name, "path": exe, "available": bool(exe)}
    if not exe:
        return payload
    try:
        proc = subprocess.run([exe, *(args or [])], capture_output=True, text=True, timeout=timeout)
        payload.update(
            {
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:300],
                "stderr": (proc.stderr or "")[:300],
            }
        )
    except Exception as exc:
        payload.update({"error": f"{type(exc).__name__}:{exc}"})
    return payload


def vision_product_runtime_status() -> dict:
    caption_endpoint = _env("AI_NAS_VISION_CAPTION_ENDPOINT")
    caption_model = _env("AI_NAS_VISION_CAPTION_MODEL")
    embedding_endpoint = _env("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT")
    embedding_model = (
        _env("AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL")
        or _env("AI_NAS_SIGLIP_MODEL")
        or _env("AI_NAS_CLIP_MODEL")
    )
    detector_endpoint = _env("AI_NAS_VISION_DETECTOR_ENDPOINT") or _env("AI_NAS_YOLO_ENDPOINT")
    detector_model = _env("AI_NAS_VISION_DETECTOR_MODEL") or _env("AI_NAS_YOLO_MODEL")
    region_endpoint = _env("AI_NAS_VISION_REGION_ENDPOINT") or _env("AI_NAS_REGION_ATTRIBUTE_ENDPOINT")
    region_model = _env("AI_NAS_HUMAN_PARSING_MODEL") or _env("AI_NAS_REGION_ATTRIBUTE_MODEL")

    pil = _module_status("PIL")
    numpy = _module_status("numpy")
    pytesseract = _module_status("pytesseract")
    tesseract = _command_status("tesseract", ["--version"])
    paddleocr = _module_status("paddleocr")
    onnxruntime = _module_status("onnxruntime")
    torch = _module_status("torch")
    transformers = _module_status("transformers")
    cv2 = _module_status("cv2")
    sqlite_vec = _module_status("sqlite_vec")

    product_ocr = product_ocr_runtime_status()
    product_embedding = product_embedding_runtime_status()
    product_region = product_region_runtime_status()
    ocr_ready = bool(product_ocr.get("ready") or tesseract.get("available") or pytesseract["importable"] or paddleocr["importable"])
    caption_ready = bool(caption_endpoint and caption_model)
    embedding_ready = bool(
        product_embedding.get("ready")
        or embedding_endpoint
        or (embedding_model and (onnxruntime["importable"] or torch["importable"] or transformers["importable"]))
    )
    detector_ready = bool(
        product_region.get("ready")
        or detector_endpoint
        or (detector_model and (onnxruntime["importable"] or torch["importable"]))
    )
    region_attribute_ready = bool(
        product_region.get("ready")
        or region_endpoint
        or (region_model and (onnxruntime["importable"] or torch["importable"] or cv2["importable"])
        )
    )
    vector_store_ready = True

    components = {
        "ocr": {
            "ready": ocr_ready,
            "preferred": "product_http_ocr" if product_ocr.get("ready") else ("paddleocr" if paddleocr["importable"] else ("tesseract" if tesseract.get("available") else "none")),
            "product_http_ocr": product_ocr,
            "tesseract": tesseract,
            "pytesseract": pytesseract,
            "paddleocr": paddleocr,
        },
        "caption_vlm": {
            "ready": caption_ready,
            "endpoint_configured": bool(caption_endpoint),
            "model_id": caption_model,
            "provider": "openai_compatible" if caption_endpoint else "not_configured",
        },
        "image_text_embedding": {
            "ready": embedding_ready,
            "endpoint_configured": bool(product_embedding.get("endpoint_configured") or embedding_endpoint),
            "model_id": product_embedding.get("model_id") or embedding_model,
            "product_http_embedding": product_embedding,
            "onnxruntime": onnxruntime,
            "torch": torch,
            "transformers": transformers,
            "fallback": "local_visual_embedding_v1_is_not_product_semantic_embedding",
        },
        "detector": {
            "ready": detector_ready,
            "endpoint_configured": bool(product_region.get("endpoint_configured") or detector_endpoint),
            "model_id": product_region.get("model_id") or detector_model,
            "product_http_region": product_region,
            "onnxruntime": onnxruntime,
            "torch": torch,
        },
        "region_attributes": {
            "ready": region_attribute_ready,
            "endpoint_configured": bool(product_region.get("endpoint_configured") or region_endpoint),
            "model_id": product_region.get("model_id") or region_model,
            "product_http_region": product_region,
            "cv2": cv2,
            "pil": pil,
            "numpy": numpy,
        },
        "vector_store": {
            "ready": vector_store_ready,
            "backend": "sqlite_json_exact_fallback",
            "sqlite_vec": sqlite_vec,
            "production_ann_ready": sqlite_vec["importable"],
        },
        "evidence": {
            "ready": True,
            "artifact_schema": "vision_artifacts",
            "result_schema": "vision evidence list with model_id/runtime/confidence/degradation",
        },
    }
    missing_for_product = [
        name for name in ("ocr", "caption_vlm", "image_text_embedding", "detector", "region_attributes")
        if not components[name]["ready"]
    ]
    registry = build_vision_adapter_registry()
    return {
        "ok": True,
        "runtime_schema": "ai_nas_vision_runtime_v1",
        "product_ready": not missing_for_product,
        "missing_for_product": missing_for_product,
        "components": components,
        "adapter_registry": registry,
        "policy": {
            "text_llm_role": "query_rewrite_tool_routing_evidence_explanation",
            "vision_is_separate_data_plane": True,
            "do_not_claim_visual_understanding_when_degraded": True,
        },
    }
