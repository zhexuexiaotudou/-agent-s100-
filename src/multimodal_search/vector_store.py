from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


class NumpyVectorStore:
    def __init__(self, store_dir: str | Path) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.matrix_path = self.store_dir / "vectors.npy"
        self.meta_path = self.store_dir / "vectors.json"
        self.records: list[dict[str, Any]] = []
        self.matrix = np.zeros((0, 0), dtype=np.float32)
        self._load()

    def _load(self) -> None:
        if self.matrix_path.exists() and self.meta_path.exists():
            self.matrix = np.load(self.matrix_path)
            self.records = json.loads(self.meta_path.read_text(encoding="utf-8"))

    def save(self) -> None:
        np.save(self.matrix_path, self.matrix)
        self.meta_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def add(self, *, embedding_id: str, asset_id: str, modality: str, model_id: str, vector: np.ndarray, privacy_level: str) -> str:
        arr = np.asarray(vector, dtype=np.float32)
        if self.matrix.size and self.matrix.shape[1] != arr.shape[0]:
            raise ValueError(f"vector_dim_mismatch:{self.matrix.shape[1]}!={arr.shape[0]}")
        if not self.matrix.size:
            self.matrix = arr.reshape(1, -1)
        else:
            self.matrix = np.vstack([self.matrix, arr.reshape(1, -1)])
        ref = f"numpy://{len(self.records)}"
        self.records.append(
            {
                "embedding_id": embedding_id,
                "asset_id": asset_id,
                "modality": modality,
                "model_id": model_id,
                "privacy_level": privacy_level,
                "vector_store_ref": ref,
            }
        )
        self.save()
        return ref

    def search(
        self,
        query_vector: np.ndarray,
        *,
        top_k: int = 10,
        modality: str | None = None,
        model_id: str | None = None,
        privacy_level: str = "private_local_only",
    ) -> list[dict[str, Any]]:
        if self.matrix.size == 0:
            return []
        q = np.asarray(query_vector, dtype=np.float32)
        if q.shape[0] != self.matrix.shape[1]:
            raise ValueError(f"vector_dim_mismatch:{self.matrix.shape[1]}!={q.shape[0]}")
        scores = self.matrix @ q
        rows: list[dict[str, Any]] = []
        for idx in np.argsort(scores)[::-1]:
            record = self.records[int(idx)]
            if modality and record.get("modality") != modality:
                continue
            if model_id and record.get("model_id") != model_id:
                continue
            if record.get("privacy_level") != privacy_level:
                continue
            rows.append({**record, "score": float(scores[int(idx)])})
            if len(rows) >= top_k:
                break
        return rows


def vector_store_status(store_dir: str | Path) -> dict[str, Any]:
    store = NumpyVectorStore(store_dir)
    return {
        "ok": True,
        "backend": "numpy",
        "vector_count": len(store.records),
        "vector_dim": int(store.matrix.shape[1]) if store.matrix.size else 0,
        "degraded": False,
    }
