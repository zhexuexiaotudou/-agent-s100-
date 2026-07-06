from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from PIL import Image
except Exception:  # pragma: no cover - dependency-dependent fallback
    Image = None  # type: ignore[assignment]


COLOR_WORDS = {
    "white": np.array([1.0, 1.0, 1.0]),
    "black": np.array([0.0, 0.0, 0.0]),
    "red": np.array([1.0, 0.0, 0.0]),
    "green": np.array([0.0, 1.0, 0.0]),
    "blue": np.array([0.0, 0.0, 1.0]),
    "yellow": np.array([1.0, 1.0, 0.0]),
    "gray": np.array([0.5, 0.5, 0.5]),
    "grey": np.array([0.5, 0.5, 0.5]),
}

ZH_COLOR_MAP = {
    "\u767d": "white",
    "\u767d\u8272": "white",
    "\u9ed1": "black",
    "\u9ed1\u8272": "black",
    "\u7ea2": "red",
    "\u7ea2\u8272": "red",
    "\u7eff": "green",
    "\u7eff\u8272": "green",
    "\u84dd": "blue",
    "\u84dd\u8272": "blue",
    "\u9ec4": "yellow",
    "\u9ec4\u8272": "yellow",
    "\u7070": "gray",
    "\u7070\u8272": "gray",
}


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0:
        return arr
    return arr / norm


@dataclass(frozen=True)
class ModelIdentity:
    model_name: str
    model_family: str
    vector_dim: int
    backend: str
    device: str
    precision: str
    local_only: bool
    weights_committed_to_repo: bool
    production_semantic: bool = False

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


class LocalImageTextEmbeddingAdapter:
    """Small local image-text adapter for v1 appliance delivery.

    This is not a cloud vision model and does not identify people. It embeds
    color, brightness, aspect, and safe filename/text cues so image search can
    work locally when heavier OpenCLIP/SigLIP dependencies are absent.
    """

    vector_dim = 16

    def __init__(self) -> None:
        self.available = Image is not None

    def get_model_identity(self) -> dict[str, Any]:
        return ModelIdentity(
            model_name="digua-local-visual-text-embedding-v1",
            model_family="local_feature_embedding",
            vector_dim=self.vector_dim,
            backend="pillow_numpy",
            device="cpu",
            precision="float32",
            local_only=True,
            weights_committed_to_repo=False,
        ).to_dict()

    def embed_image(self, image_path: str | Path) -> np.ndarray:
        if Image is None:
            raise RuntimeError("pillow_unavailable")
        with Image.open(image_path) as image:
            rgb = image.convert("RGB").resize((32, 32))
            arr = np.asarray(rgb, dtype=np.float32) / 255.0
            width, height = image.size
        mean = arr.mean(axis=(0, 1))
        std = arr.std(axis=(0, 1))
        brightness = np.array([float(mean.mean())], dtype=np.float32)
        aspect = np.array([float(width / max(1, height))], dtype=np.float32)
        color_bins = np.array(
            [
                float(mean[0] > 0.65 and mean[0] >= mean[1] and mean[0] >= mean[2]),
                float(mean[1] > 0.65 and mean[1] >= mean[0] and mean[1] >= mean[2]),
                float(mean[2] > 0.65 and mean[2] >= mean[0] and mean[2] >= mean[1]),
                float(mean.mean() > 0.75),
                float(mean.mean() < 0.25),
            ],
            dtype=np.float32,
        )
        vector = np.concatenate([mean, std, brightness, aspect, color_bins, np.zeros(3, dtype=np.float32)])
        return normalize_vector(vector[: self.vector_dim])

    def embed_text(self, query: str) -> np.ndarray:
        text = query.lower()
        for zh, en in ZH_COLOR_MAP.items():
            if zh in query:
                text += " " + en
        rgb = np.array([0.25, 0.25, 0.25], dtype=np.float32)
        hits = 0
        color_flags = {word: False for word in COLOR_WORDS}
        for word, color in COLOR_WORDS.items():
            if word in text:
                rgb += color.astype(np.float32)
                hits += 1
                color_flags[word] = True
        if hits:
            rgb = rgb / float(hits + 1)
        std = np.array([0.1, 0.1, 0.1], dtype=np.float32)
        brightness = np.array([float(rgb.mean())], dtype=np.float32)
        aspect = np.array([1.0], dtype=np.float32)
        color_bins = np.array(
            [
                float(color_flags["red"]),
                float(color_flags["green"]),
                float(color_flags["blue"]),
                float(color_flags["white"]),
                float(color_flags["black"]),
            ],
            dtype=np.float32,
        )
        vector = np.concatenate([rgb, std, brightness, aspect, color_bins, np.zeros(3, dtype=np.float32)])
        return normalize_vector(vector[: self.vector_dim])


def load_image_text_model() -> LocalImageTextEmbeddingAdapter:
    return LocalImageTextEmbeddingAdapter()
