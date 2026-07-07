from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .image_embedding_adapter import LocalImageTextEmbeddingAdapter, normalize_vector
import base64
import urllib.request
import urllib.error
import json as _json
import time as _time

PRODUCTION_FAMILIES = {"clip", "siglip", "chinese_clip", "open_clip"}

@dataclass(frozen=True)
class AdapterIdentity:
    model_name: str
    model_family: str
    vector_dim: int
    backend: str
    device: str
    precision: str
    local_only: bool
    weights_committed_to_repo: bool
    production_semantic: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_family": self.model_family,
            "vector_dim": self.vector_dim,
            "backend": self.backend,
            "device": self.device,
            "precision": self.precision,
            "local_only": self.local_only,
            "weights_committed_to_repo": self.weights_committed_to_repo,
            "production_semantic": self.production_semantic,
        }

class UnavailableClipEmbeddingAdapter:
    def __init__(self, *, reason: str, backend: str, model_dir: str | None, require_production: bool) -> None:
        self.available = False
        self.reason = reason
        self.backend = backend
        self.model_dir = model_dir
        self.require_production = require_production

    def get_model_identity(self) -> dict[str, Any]:
        return AdapterIdentity(
            model_name=self.model_dir or "unconfigured",
            model_family="unavailable",
            vector_dim=0,
            backend=self.backend,
            device=os.environ.get("DIGUA_CLIP_DEVICE", "cpu"),
            precision="unknown",
            local_only=True,
            weights_committed_to_repo=False,
            production_semantic=False,
        ).to_dict() | {"available": False, "unavailable_reason": self.reason}

    def embed_image(self, image_path: str | Path) -> np.ndarray:
        raise RuntimeError(self.reason)

    def embed_text(self, query: str) -> np.ndarray:
        raise RuntimeError(self.reason)

class TransformersClipEmbeddingAdapter:
    def __init__(self, *, model_dir: str | Path, device: str = "cpu", backend: str = "transformers_clip") -> None:
        self.model_dir = Path(model_dir)
        self.device = device
        self.backend = backend
        self.available = False
        self._load_error: str | None = None
        self._model = None
        self._processor = None
        self._torch = None
        self._load()

    def _load(self) -> None:
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            self._torch = torch
            self._model = CLIPModel.from_pretrained(str(self.model_dir), local_files_only=True)
            self._processor = CLIPProcessor.from_pretrained(str(self.model_dir), local_files_only=True)
            self._model.eval()
            if self.device != "cpu":
                self._model.to(self.device)
            self.available = True
        except Exception as exc:  # pragma: no cover - depends on local runtime/model files
            self.available = False
            self._load_error = f"{type(exc).__name__}:{exc}"

    def get_model_identity(self) -> dict[str, Any]:
        vector_dim = 512
        model_name = self.model_dir.name
        if self._model is not None:
            projection_dim = getattr(getattr(self._model, "config", None), "projection_dim", None)
            if projection_dim:
                vector_dim = int(projection_dim)
        return AdapterIdentity(
            model_name=model_name,
            model_family="clip",
            vector_dim=vector_dim,
            backend=self.backend,
            device=self.device,
            precision="float32",
            local_only=True,
            weights_committed_to_repo=False,
            production_semantic=self.available and vector_dim >= 128,
        ).to_dict() | {"available": self.available, "unavailable_reason": self._load_error}

    def embed_image(self, image_path: str | Path) -> np.ndarray:
        if not self.available or self._model is None or self._processor is None or self._torch is None:
            raise RuntimeError(self._load_error or "clip_model_unavailable")
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt")
        if self.device != "cpu":
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self._torch.no_grad():
            features = self._model.get_image_features(**inputs)
        return normalize_vector(features[0].detach().cpu().numpy().astype(np.float32))

    def embed_text(self, query: str) -> np.ndarray:
        if not self.available or self._model is None or self._processor is None or self._torch is None:
            raise RuntimeError(self._load_error or "clip_model_unavailable")
        inputs = self._processor(text=[query], return_tensors="pt", padding=True, truncation=True)
        if self.device != "cpu":
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self._torch.no_grad():
            features = self._model.get_text_features(**inputs)
        return normalize_vector(features[0].detach().cpu().numpy().astype(np.float32))

class HttpClipEmbeddingAdapter:
    """CLIP adapter that delegates to a local HTTP CLIP embedding gateway.

    Reads AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT (required) and
    AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL (optional) from environment.
    """

    vector_dim = 512

    def __init__(self) -> None:
        self.endpoint = (os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT") or "").strip().rstrip("/")
        self.model = (os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL") or "s100p-clip-vit-base-patch32").strip()
        self.timeout_sec = float(os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_TIMEOUT_SECONDS") or 120)
        self._available: bool | None = None
        self._load_error: str | None = None
        self._dim: int | None = None
        self.available = bool(self.endpoint)
        if not self.endpoint:
            self._load_error = "AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT_not_set"
            self.available = False

    def _check_health(self) -> None:
        if self._available is not None:
            if not self._available:
                raise RuntimeError(self._load_error or "http_clip_model_unavailable")
            return
        try:
            req = urllib.request.Request(
                f"{self.endpoint}/health",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = _json.loads(resp.read(4096).decode("utf-8"))
            self._available = bool(data.get("ok") and data.get("ready"))
            if not self._available:
                self._load_error = data.get("load_error") or "http_clip_not_ready"
                self.available = False
        except Exception as exc:
            self._available = False
            self._load_error = f"{type(exc).__name__}:{exc}"
            self.available = False

    def get_model_identity(self) -> dict[str, Any]:
        self._check_health()
        return AdapterIdentity(
            model_name=self.model,
            model_family="clip",
            vector_dim=self.vector_dim,
            backend="http_clip_embedding_gateway",
            device=os.environ.get("DIGUA_CLIP_DEVICE", "cpu"),
            precision="float32",
            local_only=True,
            weights_committed_to_repo=False,
            production_semantic=self._available if self._available is not None else False,
        ).to_dict() | {"available": self.available, "unavailable_reason": self._load_error}

    def embed_image(self, image_path: str | Path) -> np.ndarray:
        self._check_health()
        path = Path(image_path)
        with open(path, "rb") as fh:
            raw = fh.read()
        ext = path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".bmp": "image/bmp", ".gif": "image/gif"}
        mime = mime_map.get(ext, "image/jpeg")
        b64 = base64.b64encode(raw).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        payload = _json.dumps({"input_type": "image", "model": self.model, "image_url": {"url": data_url}}).encode("utf-8")
        return self._post_embed(payload)

    def embed_text(self, query: str) -> np.ndarray:
        self._check_health()
        payload = _json.dumps({"input_type": "text", "model": self.model, "text": query}).encode("utf-8")
        return self._post_embed(payload)

    def _post_embed(self, payload: bytes) -> np.ndarray:
        started = _time.time()
        deadline = started + self.timeout_sec
        retries = 0
        max_retries = 2
        last_error = None
        while _time.time() < deadline:
            try:
                req = urllib.request.Request(
                    f"{self.endpoint}/embed",
                    data=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=min(30, deadline - _time.time())) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    embedding = data.get("embedding", [])
                    self._dim = len(embedding)
                    vec = np.array(embedding, dtype=np.float32)
                    return normalize_vector(vec)
                last_error = data.get("error") or "http_clip_embed_failed"
                retries += 1
                if retries >= max_retries:
                    break
                _time.sleep(1.0)
            except (urllib.error.URLError, OSError, _json.JSONDecodeError) as exc:
                last_error = f"{type(exc).__name__}:{exc}"
                retries += 1
                if retries >= max_retries:
                    break
                _time.sleep(1.0)
        raise RuntimeError(last_error or "http_clip_embed_timeout")

class LocalFallbackAdapter(LocalImageTextEmbeddingAdapter):
    def get_model_identity(self) -> dict[str, Any]:
        identity = super().get_model_identity()
        identity["production_semantic"] = False
        identity["available"] = self.available
        return identity

def load_image_text_model():
    backend = os.environ.get("DIGUA_CLIP_BACKEND", "auto").strip().lower() or "auto"
    model_dir = os.environ.get("DIGUA_CLIP_MODEL_DIR")
    device = os.environ.get("DIGUA_CLIP_DEVICE", "cpu")
    require_production = os.environ.get("DIGUA_CLIP_REQUIRE_PRODUCTION", "0").lower() in {"1", "true", "yes"}
    http_endpoint = os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT", "").strip()

    # Prefer HTTP CLIP gateway if configured
    if http_endpoint and backend != "local_feature":
        adapter = HttpClipEmbeddingAdapter()
        if adapter.available:
            return adapter

    if backend == "local_feature":
        return LocalFallbackAdapter()

    if model_dir:
        adapter = TransformersClipEmbeddingAdapter(model_dir=model_dir, device=device)
        if adapter.available:
            return adapter
        if require_production:
            if http_endpoint:
                http_adapter = HttpClipEmbeddingAdapter()
                if http_adapter.available:
                    return http_adapter
            return UnavailableClipEmbeddingAdapter(
                reason=adapter.get_model_identity().get("unavailable_reason") or "production_clip_model_unavailable",
                backend=backend,
                model_dir=model_dir,
                require_production=True,
            )

    if http_endpoint:
        adapter = HttpClipEmbeddingAdapter()
        if adapter.available:
            return adapter
        if require_production:
            return UnavailableClipEmbeddingAdapter(
                reason=adapter.get_model_identity().get("unavailable_reason") or "production_clip_model_unavailable",
                backend=backend,
                model_dir=model_dir,
                require_production=True,
            )

    if require_production:
        if http_endpoint:
            http_adapter = HttpClipEmbeddingAdapter()
            if http_adapter.available:
                return http_adapter
        return UnavailableClipEmbeddingAdapter(
            reason="production_clip_model_dir_not_configured",
            backend=backend,
            model_dir=model_dir,
            require_production=True,
        )

    return LocalFallbackAdapter()
