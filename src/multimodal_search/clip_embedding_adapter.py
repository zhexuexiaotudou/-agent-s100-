from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .image_embedding_adapter import LocalImageTextEmbeddingAdapter, normalize_vector


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

    if backend == "local_feature":
        return LocalFallbackAdapter()

    if model_dir:
        adapter = TransformersClipEmbeddingAdapter(model_dir=model_dir, device=device)
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
        return UnavailableClipEmbeddingAdapter(
            reason="production_clip_model_dir_not_configured",
            backend=backend,
            model_dir=model_dir,
            require_production=True,
        )

    return LocalFallbackAdapter()
