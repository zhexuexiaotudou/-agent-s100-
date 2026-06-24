#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_ID,
    IMAGE_EMBEDDING_DIM,
    IMAGE_EMBEDDING_MODEL_ID,
    cosine_similarity,
    embed_text_local_hash,
    ensure_report_dir,
    image_embedding_runtime_status,
    iso_now,
    local_visual_embedding,
    safe_write_json,
    safe_write_text,
)
from ai_nas_embedding_backend_readiness_probe import (
    IMAGE_MODEL_ENV,
    TEXT_MODEL_ENV,
    configured_image_model_dir,
    configured_text_model_dir,
    model_dir_status,
    try_clip_smoke,
    try_sentence_transformer_smoke,
    try_transformers_text_embedding_smoke,
)


TOOL_ID = "ai_nas_embedding_runtime_contract"


def module_status(names: list[str]) -> dict:
    status = {}
    for name in names:
        spec = importlib.util.find_spec(name)
        if spec is None:
            status[name] = {"importable": False, "version": None, "error": "module not found"}
            continue
        try:
            module = importlib.import_module(name)
            status[name] = {
                "importable": True,
                "version": str(getattr(module, "__version__", "")),
                "error": None,
            }
        except Exception as exc:
            status[name] = {
                "importable": False,
                "version": None,
                "error": f"{type(exc).__name__}:{exc}",
            }
    return status


def text_fallback_smoke() -> dict:
    query = "2024 renovation payment contract"
    related = "renovation contract final payment receipt 2024"
    unrelated = "kids beach photo picnic album"
    query_vector = embed_text_local_hash(query)
    related_vector = embed_text_local_hash(related)
    unrelated_vector = embed_text_local_hash(unrelated)
    related_score = cosine_similarity(query_vector, related_vector)
    unrelated_score = cosine_similarity(query_vector, unrelated_vector)
    return {
        "ok": len(query_vector) == EMBEDDING_DIM and any(value != 0.0 for value in query_vector),
        "backend": EMBEDDING_MODEL_ID,
        "production": False,
        "dim": EMBEDDING_DIM,
        "related_score": round(related_score, 6),
        "unrelated_score": round(unrelated_score, 6),
        "ranking_sane": related_score > unrelated_score,
        "limitation": "deterministic feature hashing validates vector plumbing only; it is not semantic sentence embedding",
    }


def visual_fallback_smoke(fixture_image: Path) -> dict:
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (96, 96), (238, 244, 250))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 18, 82, 78), outline=(245, 245, 245), fill=(232, 232, 232), width=2)
        draw.rectangle((18, 54, 74, 70), fill=(255, 255, 255), outline=(120, 120, 120))
        draw.ellipse((22, 66, 34, 78), fill=(40, 40, 40))
        draw.ellipse((60, 66, 72, 78), fill=(40, 40, 40))
        image.save(fixture_image)
        vector, metadata = local_visual_embedding(fixture_image)
        return {
            "ok": len(vector) == IMAGE_EMBEDDING_DIM and any(value != 0.0 for value in vector),
            "backend": IMAGE_EMBEDDING_MODEL_ID,
            "production": False,
            "dim": IMAGE_EMBEDDING_DIM,
            "fixture_image": str(fixture_image),
            "metadata": metadata,
            "limitation": "PIL histogram embedding validates local image vector plumbing only; it is not CLIP semantics",
        }
    except Exception as exc:
        return {
            "ok": False,
            "backend": IMAGE_EMBEDDING_MODEL_ID,
            "production": False,
            "dim": IMAGE_EMBEDDING_DIM,
            "fixture_image": str(fixture_image),
            "error": f"{type(exc).__name__}:{exc}",
        }


def install_manifest(modules: dict, text_model: dict, image_model: dict) -> dict:
    missing = []
    if not (
        modules.get("sentence_transformers", {}).get("importable")
        or modules.get("transformers", {}).get("importable")
    ):
        missing.append("sentence_transformers Python package")
    if not modules.get("torch", {}).get("importable"):
        missing.append("torch Python package")
    if not (
        modules.get("transformers", {}).get("importable")
        or modules.get("clip", {}).get("importable")
        or modules.get("open_clip", {}).get("importable")
    ):
        missing.append("one CLIP runtime package: transformers, clip, or open_clip")
    if not text_model.get("ready"):
        missing.append(f"local text embedding model directory with markers via {TEXT_MODEL_ENV}")
    if not image_model.get("ready"):
        missing.append(f"local image CLIP model directory with markers via {IMAGE_MODEL_ENV}")
    return {
        "missing_requirements": missing,
        "windows_operator_steps": [
            "Install sentence-transformers, torch, and a CLIP-capable runtime into the Python environment used by OpenClaw tools.",
            f"Set {TEXT_MODEL_ENV} to a local sentence-transformer model directory containing config.json/modules.json.",
            f"Set {IMAGE_MODEL_ENV} to a local CLIP model directory containing config.json/preprocessor_config.json or open_clip_config.json.",
            "Re-run ai_nas_embedding_runtime_contract and ai_nas_embedding_backend_readiness without enabling network downloads.",
        ],
        "linux_operator_steps": [
            "Pre-provision embedding and CLIP Python packages in the S100P/OpenClaw runtime image.",
            f"Mount or copy local model directories and export {TEXT_MODEL_ENV} and {IMAGE_MODEL_ENV}.",
            "Re-run this contract before claiming production semantic search or image semantic search readiness.",
        ],
        "acceptance_required": [
            "sentence-transformer smoke runs from local model files only",
            "CLIP text/image smoke runs from local model files only",
            "no model download or network call occurs during tool execution",
            "fallback model_id values remain distinct from production model_id values",
            "every semantic result includes reasons, evidence, confidence, model_id, and limitations",
            "face recognition remains out of scope until a separate privacy/compliance review is approved",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS production embedding and CLIP runtime contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--text-model-dir", type=Path, default=None)
    parser.add_argument("--image-model-dir", type=Path, default=None)
    parser.add_argument("--fixture-root", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "embedding_runtime_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    fixture_root.mkdir(parents=True, exist_ok=True)
    text_model_dir = configured_text_model_dir(args.text_model_dir)
    image_model_dir = configured_image_model_dir(args.image_model_dir)

    modules = module_status(["sentence_transformers", "transformers", "torch", "clip", "open_clip", "PIL", "numpy", "sklearn"])
    text_model = model_dir_status(text_model_dir, ["config.json", "modules.json", "sentence_bert_config.json", "tokenizer.json", "pytorch_model.bin", "model.safetensors"])
    image_model = model_dir_status(image_model_dir, ["config.json", "preprocessor_config.json", "open_clip_config.json"])
    local_text = text_fallback_smoke()
    local_visual = visual_fallback_smoke(fixture_root / "white_car_fixture.png")
    production_text = try_sentence_transformer_smoke(text_model_dir)
    production_hf_text = try_transformers_text_embedding_smoke(text_model_dir)
    production_image = try_clip_smoke(image_model_dir)
    image_runtime = image_embedding_runtime_status()
    manifest = install_manifest(modules, text_model, image_model)

    production_text_ready = bool(production_text.get("ok") or production_hf_text.get("ok"))
    production_image_ready = bool(production_image.get("ok"))
    production_ready = production_text_ready and production_image_ready
    blockers = []
    if not local_text.get("ok"):
        blockers.append("local_text_fallback_smoke_failed")
    if not local_visual.get("ok"):
        blockers.append("local_visual_fallback_smoke_failed")
    if not production_text_ready:
        blockers.append("production_text_embedding_smoke_not_ready")
    if not production_image_ready:
        blockers.append("production_image_clip_smoke_not_ready")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_embedding_runtime_contract" if production_ready else "limited_ai_nas_embedding_runtime_contract",
        "production_embedding_ready": production_ready,
        "scope": "local-only runtime contract for AI-NAS text embedding and image CLIP search",
        "module_status": modules,
        "image_runtime_status": image_runtime,
        "configured_model_dirs": {
            "text": text_model,
            "image": image_model,
            "env": {
                TEXT_MODEL_ENV: os.environ.get(TEXT_MODEL_ENV),
                IMAGE_MODEL_ENV: os.environ.get(IMAGE_MODEL_ENV),
            },
        },
        "smoke": {
            "local_text_fallback": local_text,
            "local_visual_fallback": local_visual,
            "production_text_embedding": production_text,
            "production_hf_text_embedding": production_hf_text,
            "production_image_clip": production_image,
        },
        "install_manifest": manifest,
        "summary": {
            "local_text_fallback_ready": bool(local_text.get("ok")),
            "local_visual_fallback_ready": bool(local_visual.get("ok")),
            "production_text_ready": production_text_ready,
            "production_image_ready": production_image_ready,
            "production_embedding_ready": production_ready,
            "missing_requirements": manifest["missing_requirements"],
            "blockers": blockers,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "download_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "face_recognition_performed": False,
            "writes": "isolated image fixture plus Markdown/JSON embedding runtime contract report only",
        },
    }

    json_path = run_dir / "embedding_runtime_contract.json"
    md_path = run_dir / "embedding_runtime_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Embedding Runtime Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- production_embedding_ready: `{production_ready}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- local_text_fallback_ready: `{payload['summary']['local_text_fallback_ready']}`",
        f"- local_visual_fallback_ready: `{payload['summary']['local_visual_fallback_ready']}`",
        f"- production_text_ready: `{production_text_ready}`",
        f"- production_image_ready: `{production_image_ready}`",
        f"- blockers: `{blockers}`",
        "",
        "## Missing Requirements",
        "",
    ]
    if not manifest["missing_requirements"]:
        lines.append("- No production embedding runtime requirement is missing.")
    for item in manifest["missing_requirements"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Module Status", ""])
    for name, status in modules.items():
        lines.append(f"- {name}: `{status}`")
    lines.extend(["", "## Smoke", ""])
    for name, status in payload["smoke"].items():
        lines.append(f"- {name}: `{status}`")
    lines.extend(["", "## Acceptance Required", ""])
    for item in manifest["acceptance_required"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
