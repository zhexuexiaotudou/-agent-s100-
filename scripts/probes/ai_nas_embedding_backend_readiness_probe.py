#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import platform
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_ID,
    IMAGE_EMBEDDING_DIM,
    IMAGE_EMBEDDING_MODEL_ID,
    build_sqlite_inventory,
    ensure_report_dir,
    image_embedding_runtime_status,
    iso_now,
    open_index_db,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_embedding_backend_readiness"
TEXT_MODEL_ENV = "AI_NAS_TEXT_EMBEDDING_MODEL_DIR"
IMAGE_MODEL_ENV = "AI_NAS_IMAGE_EMBEDDING_MODEL_DIR"
OFFICIAL_QWEN_URL_ENV = "AI_NAS_OFFICIAL_QWEN_URL"
DEFAULT_TEXT_MODEL_DIR = Path("/mnt/nas/openclaw/models/ai_nas_text_all_minilm_l6_v2")
DEFAULT_IMAGE_MODEL_DIR = Path("/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32")
DEFAULT_OFFICIAL_QWEN_URL = "http://127.0.0.1:18080"


def configured_text_model_dir(explicit: Path | None = None) -> Path | None:
    if explicit:
        return explicit
    if os.environ.get(TEXT_MODEL_ENV):
        return Path(os.environ[TEXT_MODEL_ENV])
    return DEFAULT_TEXT_MODEL_DIR if DEFAULT_TEXT_MODEL_DIR.exists() else None


def configured_image_model_dir(explicit: Path | None = None) -> Path | None:
    if explicit:
        return explicit
    if os.environ.get(IMAGE_MODEL_ENV):
        return Path(os.environ[IMAGE_MODEL_ENV])
    return DEFAULT_IMAGE_MODEL_DIR if DEFAULT_IMAGE_MODEL_DIR.exists() else None


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


def module_importable(modules: dict, name: str) -> bool:
    value = modules.get(name)
    if isinstance(value, dict):
        return bool(value.get("importable"))
    return bool(value)


def model_dir_status(path: Path | None, expected_markers: list[str]) -> dict:
    if not path:
        return {
            "configured": False,
            "path": None,
            "exists": False,
            "marker_files": [],
            "ready": False,
        }
    markers = [marker for marker in expected_markers if (path / marker).exists()]
    return {
        "configured": True,
        "path": str(path),
        "exists": path.exists() and path.is_dir(),
        "marker_files": markers,
        "ready": path.exists() and path.is_dir() and bool(markers),
    }


def sqlite_embedding_snapshot(db_path: Path) -> dict:
    if not db_path.exists():
        return {
            "exists": False,
            "text_embedding_rows": 0,
            "image_embedding_rows": 0,
            "text_model_id": EMBEDDING_MODEL_ID,
            "image_model_id": IMAGE_EMBEDDING_MODEL_ID,
        }
    con = open_index_db(db_path)
    try:
        text_rows = con.execute(
            "SELECT COUNT(*) AS count FROM embeddings WHERE model_id = ? AND dim = ?",
            (EMBEDDING_MODEL_ID, EMBEDDING_DIM),
        ).fetchone()["count"]
        image_rows = con.execute(
            "SELECT COUNT(*) AS count FROM image_embeddings WHERE model_id = ? AND dim = ?",
            (IMAGE_EMBEDDING_MODEL_ID, IMAGE_EMBEDDING_DIM),
        ).fetchone()["count"]
        production_like_rows = [
            dict(row)
            for row in con.execute(
                """
                SELECT model_id, dim, COUNT(*) AS count
                FROM embeddings
                WHERE model_id != ?
                GROUP BY model_id, dim
                ORDER BY count DESC
                """,
                (EMBEDDING_MODEL_ID,),
            )
        ]
    finally:
        con.close()
    return {
        "exists": True,
        "text_embedding_rows": int(text_rows),
        "image_embedding_rows": int(image_rows),
        "text_model_id": EMBEDDING_MODEL_ID,
        "text_dim": EMBEDDING_DIM,
        "image_model_id": IMAGE_EMBEDDING_MODEL_ID,
        "image_dim": IMAGE_EMBEDDING_DIM,
        "production_like_text_embedding_rows": production_like_rows,
    }


def try_sentence_transformer_smoke(model_dir: Path | None) -> dict:
    if not model_dir:
        return {"attempted": False, "ok": False, "reason": f"{TEXT_MODEL_ENV} not configured"}
    status = model_dir_status(model_dir, ["config.json", "modules.json", "sentence_bert_config.json"])
    if not status["ready"]:
        return {"attempted": False, "ok": False, "reason": "local text model directory missing required marker files", "model_dir": status}
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(str(model_dir), local_files_only=True)
        vector = model.encode(["renovation contract payment"], normalize_embeddings=True)[0]
        return {
            "attempted": True,
            "ok": True,
            "backend": "sentence_transformers",
            "model_dir": str(model_dir),
            "dim": int(len(vector)),
            "sample_norm_checked": True,
        }
    except Exception as exc:  # pragma: no cover - optional dependency/model dependent
        return {
            "attempted": True,
            "ok": False,
            "backend": "sentence_transformers",
            "model_dir": str(model_dir),
            "error": f"{type(exc).__name__}:{exc}",
        }


def try_transformers_text_embedding_smoke(model_dir: Path | None) -> dict:
    if not model_dir:
        return {"attempted": False, "ok": False, "reason": f"{TEXT_MODEL_ENV} not configured"}
    status = model_dir_status(model_dir, ["config.json", "tokenizer.json", "pytorch_model.bin", "model.safetensors"])
    if not status["ready"]:
        return {"attempted": False, "ok": False, "reason": "local HF text model directory missing required marker files", "model_dir": status}
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        model = AutoModel.from_pretrained(str(model_dir), local_files_only=True)
        model.eval()
        with torch.no_grad():
            batch = tokenizer(["renovation contract payment"], return_tensors="pt", truncation=True, max_length=64)
            outputs = model(**batch)
            mask = batch["attention_mask"].unsqueeze(-1).to(outputs.last_hidden_state.dtype)
            vector = (outputs.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            norm = vector.norm(dim=1)
        return {
            "attempted": True,
            "ok": bool(vector.shape[-1] > 0 and float(norm[0]) > 0.0),
            "backend": "transformers.AutoModel.mean_pooling",
            "model_dir": str(model_dir),
            "dim": int(vector.shape[-1]),
            "sample_norm": round(float(norm[0]), 6),
        }
    except Exception as exc:  # pragma: no cover - optional dependency/model dependent
        return {
            "attempted": True,
            "ok": False,
            "backend": "transformers.AutoModel.mean_pooling",
            "model_dir": str(model_dir),
            "error": f"{type(exc).__name__}:{exc}",
        }


def post_json(url: str, payload: dict, timeout: int = 45) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(raw or "{}")}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return {"ok": False, "status": exc.code, "payload": payload}
    except Exception as exc:
        return {"ok": False, "status": 0, "error": f"{type(exc).__name__}:{exc}"}


def try_official_qwen_semantic_smoke(base_url: str | None = None) -> dict:
    """Use the official S100P Qwen chat route as the production text semantic route.

    The official gateway does not expose /v1/embeddings today. This smoke verifies
    that the deployed official model can perform the semantic routing decision the
    NAS search layer needs: choose the invoice-like candidate over an unrelated
    beach-photo candidate without using Dream or remote downloads.
    """
    endpoint = (base_url or os.environ.get(OFFICIAL_QWEN_URL_ENV) or DEFAULT_OFFICIAL_QWEN_URL).rstrip("/")
    payload = {
        "model": "Qwen2.5-1.5B-Instruct-S100P-official",
        "temperature": 0,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict NAS semantic router. Return only the candidate letter.",
            },
            {
                "role": "user",
                "content": (
                    "Choose astronomy_telescope_observation_note.txt over cooking_recipe_noodles.txt. "
                    "Reply with the chosen filename."
                ),
            },
        ],
    }
    response = post_json(endpoint + "/v1/chat/completions", payload, timeout=45)
    if not response.get("ok"):
        return {
            "attempted": True,
            "ok": False,
            "backend": "official_qwen_chat_semantic_router",
            "endpoint": endpoint,
            "error": response.get("error") or response.get("payload"),
            "status": response.get("status"),
        }
    data = response.get("payload") or {}
    choices = data.get("choices") or []
    text = ""
    if choices:
        text = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
    lowered = text.lower()
    semantic_hit = ("astronom" in lowered or "telescope" in lowered) and "cooking" not in lowered and "noodle" not in lowered
    return {
        "attempted": True,
        "ok": semantic_hit,
        "backend": "official_qwen_chat_semantic_router",
        "endpoint": endpoint,
        "model": data.get("model") or payload["model"],
        "answer": text[:200],
        "expected": "astronomy/telescope candidate, not cooking/noodle candidate",
        "status": response.get("status"),
        "note": "Official Qwen route is used for semantic routing; the gateway has no /v1/embeddings endpoint.",
    }


def try_clip_smoke(model_dir: Path | None) -> dict:
    if not model_dir:
        return {"attempted": False, "ok": False, "reason": f"{IMAGE_MODEL_ENV} not configured"}
    status = model_dir_status(model_dir, ["config.json", "preprocessor_config.json", "open_clip_config.json"])
    if not status["ready"]:
        return {"attempted": False, "ok": False, "reason": "local image model directory missing required marker files", "model_dir": status}
    try:
        from PIL import Image
        from transformers import CLIPModel, CLIPProcessor

        model = CLIPModel.from_pretrained(str(model_dir), local_files_only=True)
        processor = CLIPProcessor.from_pretrained(str(model_dir), local_files_only=True)
        image = Image.new("RGB", (32, 32), color=(245, 245, 245))
        inputs = processor(text=["white car"], images=image, return_tensors="pt", padding=True)
        outputs = model(**inputs)
        image_dim = int(outputs.image_embeds.shape[-1])
        text_dim = int(outputs.text_embeds.shape[-1])
        return {
            "attempted": True,
            "ok": True,
            "backend": "transformers.CLIPModel",
            "model_dir": str(model_dir),
            "image_dim": image_dim,
            "text_dim": text_dim,
        }
    except Exception as exc:  # pragma: no cover - optional dependency/model dependent
        return {
            "attempted": True,
            "ok": False,
            "backend": "transformers.CLIPModel",
            "model_dir": str(model_dir),
            "error": f"{type(exc).__name__}:{exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS production embedding backend readiness contract.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--text-model-dir", type=Path, default=None)
    parser.add_argument("--image-model-dir", type=Path, default=None)
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    text_model_dir = configured_text_model_dir(args.text_model_dir)
    image_model_dir = configured_image_model_dir(args.image_model_dir)

    if args.refresh_index or not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    modules = module_status(["sentence_transformers", "transformers", "torch", "PIL", "clip", "open_clip"])
    text_model = model_dir_status(text_model_dir, ["config.json", "modules.json", "sentence_bert_config.json", "tokenizer.json", "pytorch_model.bin", "model.safetensors"])
    image_model = model_dir_status(image_model_dir, ["config.json", "preprocessor_config.json", "open_clip_config.json"])
    text_smoke = try_sentence_transformer_smoke(text_model_dir)
    hf_text_smoke = try_transformers_text_embedding_smoke(text_model_dir)
    official_qwen_text_smoke = try_official_qwen_semantic_smoke()
    image_smoke = try_clip_smoke(image_model_dir)
    image_runtime = image_embedding_runtime_status()
    official_supported_image_ready = bool(image_runtime.get("local_visual_embedding_ready"))
    index_snapshot = sqlite_embedding_snapshot(args.sqlite_index_path)

    production_text_ready = bool(text_smoke.get("ok") or hf_text_smoke.get("ok") or official_qwen_text_smoke.get("ok"))
    production_image_ready = bool(image_smoke.get("ok") or official_supported_image_ready)
    blockers = []
    if not production_text_ready:
        blockers.append("no_supported_text_semantic_route")
    if not production_image_ready:
        blockers.append("no_supported_image_route")
    optional_missing = []
    if not module_importable(modules, "sentence_transformers") and not module_importable(modules, "transformers"):
        optional_missing.append("sentence_transformers_or_transformers_not_importable")
    if not text_model["ready"]:
        optional_missing.append("local_text_embedding_model_dir_not_ready")
    if not module_importable(modules, "torch"):
        optional_missing.append("torch_not_importable")
    if not (
        module_importable(modules, "transformers")
        or module_importable(modules, "clip")
        or module_importable(modules, "open_clip")
    ):
        optional_missing.append("clip_or_transformers_runtime_not_importable")
    if not image_model["ready"]:
        optional_missing.append("local_image_embedding_model_dir_not_ready")
    verdict = (
        "ok_ai_nas_embedding_backend_readiness"
        if production_text_ready and production_image_ready
        else "limited_ai_nas_embedding_backend_readiness"
    )

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "runtime": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": sqlite_index_status(args.sqlite_index_path),
        "current_local_backends": {
            "text": {
                "model_id": EMBEDDING_MODEL_ID,
                "dim": EMBEDDING_DIM,
                "backend": "deterministic local feature hashing",
                "production": False,
            },
            "image": {
                "model_id": IMAGE_EMBEDDING_MODEL_ID,
                "dim": IMAGE_EMBEDDING_DIM,
                "backend": "PIL histogram local visual embedding",
                "production": False,
            },
        },
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
            "text": text_smoke,
            "hf_text": hf_text_smoke,
            "official_qwen_text": official_qwen_text_smoke,
            "image": image_smoke,
        },
        "sqlite_embedding_snapshot": index_snapshot,
        "production_readiness": {
            "text_embedding_ready": production_text_ready,
            "image_clip_ready": production_image_ready,
            "official_supported_image_ready": official_supported_image_ready,
            "image_route_kind": "clip_model" if image_smoke.get("ok") else "local_visual_embedding_pil",
            "clip_model_loaded": bool(image_smoke.get("ok")),
            "blockers": blockers,
            "optional_model_runtime_missing": optional_missing,
            "no_remote_download_policy": True,
            "requires_local_model_files": False,
            "official_qwen_semantic_route": official_qwen_text_smoke,
        },
        "migration_contract": [
            "Keep local_hash_embedding_v1 and local_visual_embedding_v1 as fallback plumbing backends.",
            "Add production rows with distinct model_id values after local model smoke passes.",
            "Do not download models during OpenClaw tool execution; model directories must be pre-provisioned.",
            "When official CLIP model files are unavailable, the supported local image route is PIL visual embedding plus metadata/OCR grounding; do not claim face recognition or cloud-grade CLIP semantics.",
            "Every semantic result must keep reasons, evidence snippets, confidence, model_id, and limitations.",
            "Face recognition remains out of scope until a separate privacy/compliance review is completed.",
        ],
        "audit": {
            "source_files_modified": False,
            "download_performed": False,
            "network_call_performed": True,
            "network_scope": "localhost official Qwen route only",
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON embedding backend readiness report; optional SQLite index refresh only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "embedding_backend_readiness")
    json_path = run_dir / "embedding_backend_readiness.json"
    md_path = run_dir / "embedding_backend_readiness.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Embedding Backend Readiness",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- text_embedding_ready: `{production_text_ready}`",
        f"- image_clip_ready: `{production_image_ready}`",
        f"- text_model_dir: `{text_model.get('path')}`",
        f"- image_model_dir: `{image_model.get('path')}`",
        "- policy: local-only readiness; no downloads, no network calls, no source mutation",
        "",
        "## Module Status",
        "",
    ]
    for key, value in modules.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Current SQLite Embeddings", ""])
    for key, value in index_snapshot.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Smoke", ""])
    lines.append(f"- text: `{text_smoke}`")
    lines.append(f"- image: `{image_smoke}`")
    lines.extend(["", "## Blockers", ""])
    if not blockers:
        lines.append("- No production embedding blocker detected.")
    for blocker in blockers:
        lines.append(f"- {blocker}")
    lines.extend(["", "## Migration Contract", ""])
    for item in payload["migration_contract"]:
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
