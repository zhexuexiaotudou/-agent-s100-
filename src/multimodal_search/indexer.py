from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .archive_indexer import archive_metadata
from .audio_indexer import audio_metadata
from .document_indexer import chunk_text, extract_text
from .feature_flags import MultimodalFeatureFlags
from .image_embedding_adapter import load_image_text_model
from .image_indexer import image_metadata
from .scanner import ScannedAsset, scan_nas_sources
from .schema import connect, migrate
from .vector_store import NumpyVectorStore
from .video_indexer import video_metadata


class MultimodalIndexer:
    def __init__(
        self,
        db_path: str | Path,
        *,
        vector_dir: str | Path,
        flags: MultimodalFeatureFlags | None = None,
        max_files: int = 5000,
    ) -> None:
        self.db_path = Path(db_path)
        self.vector_dir = Path(vector_dir)
        self.flags = flags or MultimodalFeatureFlags()
        self.max_files = max_files
        self.image_model = load_image_text_model()
        self.vector_store = NumpyVectorStore(self.vector_dir)

    def migrate(self) -> None:
        migrate(self.db_path)

    def rebuild(self, roots: list[str | Path]) -> dict[str, Any]:
        self.migrate()
        assets = scan_nas_sources(roots, max_files=self.max_files)
        started = time.time()
        counts: dict[str, int] = {}
        chunks = 0
        image_embeddings = 0
        conn = connect(self.db_path)
        try:
            conn.execute("DELETE FROM mm_search_results")
            conn.execute("DELETE FROM mm_search_runs")
            conn.execute("DELETE FROM mm_embeddings")
            conn.execute("DELETE FROM mm_video_keyframes")
            conn.execute("DELETE FROM mm_thumbnails")
            conn.execute("DELETE FROM mm_media_metadata")
            conn.execute("DELETE FROM mm_text_chunks_fts")
            conn.execute("DELETE FROM mm_text_chunks")
            conn.execute("DELETE FROM mm_assets")
            for asset in assets:
                self._upsert_asset(conn, asset)
                counts[asset.modality] = counts.get(asset.modality, 0) + 1
                chunks += self._index_text(conn, asset)
                self._index_media_metadata(conn, asset)
                if asset.modality == "image" and self.flags.image_embedding_enabled and self.image_model.available:
                    vector = self.image_model.embed_image(asset.path)
                    embedding_id = "emb_" + hashlib.sha256((asset.asset_id + asset.sha256).encode("utf-8")).hexdigest()[:24]
                    vector_ref = self.vector_store.add(
                        embedding_id=embedding_id,
                        asset_id=asset.asset_id,
                        modality="image",
                        model_id=self.image_model.get_model_identity()["model_name"],
                        vector=vector,
                        privacy_level="private_local_only",
                    )
                    vector_sha = hashlib.sha256(vector.tobytes()).hexdigest()
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO mm_embeddings(
                          embedding_id,asset_id,chunk_id,modality,model_id,vector_dim,vector_store_ref,vector_sha256,normalized,created_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            embedding_id,
                            asset.asset_id,
                            None,
                            "image",
                            self.image_model.get_model_identity()["model_name"],
                            int(vector.shape[0]),
                            vector_ref,
                            vector_sha,
                            1,
                            _now(),
                        ),
                    )
                    image_embeddings += 1
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "indexed_assets": len(assets),
            "counts": counts,
            "text_chunks": chunks,
            "image_embeddings": image_embeddings,
            "image_embedding_model": self.image_model.get_model_identity(),
            "image_embedding_available": self.image_model.available,
            "duration_sec": round(time.time() - started, 3),
            "privacy": {"raw_path_rows": 0, "private_leak_count": 0, "cloud_used": False},
        }

    def _upsert_asset(self, conn, asset: ScannedAsset) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO mm_assets(
              asset_id,source_id,modality,file_type,title_redacted,path_hash,parent_hash,size_bytes,mtime,sha256,
              privacy_level,index_status,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                asset.asset_id,
                "allowlisted_nas_root",
                asset.modality,
                asset.file_type,
                asset.title_redacted,
                asset.path_hash,
                asset.parent_hash,
                asset.size_bytes,
                asset.mtime,
                asset.sha256,
                "private_local_only",
                "indexed",
                _now(),
                _now(),
            ),
        )

    def _index_text(self, conn, asset: ScannedAsset) -> int:
        if asset.modality not in {"document", "code"}:
            return 0
        chunks = chunk_text(extract_text(asset.path))
        for index, text in enumerate(chunks):
            chunk_id = f"{asset.asset_id}_c{index}"
            conn.execute(
                """
                INSERT OR REPLACE INTO mm_text_chunks(
                  chunk_id,asset_id,chunk_index,text_redacted,page_no,timestamp_start,timestamp_end,source_type,token_count,privacy_level
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (chunk_id, asset.asset_id, index, text, None, None, None, asset.modality, len(text.split()), "private_local_only"),
            )
            conn.execute(
                "INSERT INTO mm_text_chunks_fts(chunk_id, asset_id, text_redacted) VALUES(?,?,?)",
                (chunk_id, asset.asset_id, text),
            )
        return len(chunks)

    def _index_media_metadata(self, conn, asset: ScannedAsset) -> None:
        meta: dict[str, Any] = {}
        if asset.modality == "image":
            meta = image_metadata(asset.path)
        elif asset.modality == "video":
            meta = video_metadata(asset.path)
        elif asset.modality == "audio":
            meta = audio_metadata(asset.path)
        elif asset.modality == "archive":
            meta = archive_metadata(asset.path)
        if not meta:
            return
        conn.execute(
            """
            INSERT OR REPLACE INTO mm_media_metadata(
              asset_id,width,height,duration_sec,codec,exif_json_redacted,dominant_time,gps_redacted,thumbnail_id
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                asset.asset_id,
                meta.get("width"),
                meta.get("height"),
                meta.get("duration_sec"),
                meta.get("codec"),
                json.dumps({"metadata_mode": meta.get("metadata_mode", "metadata_only")}, ensure_ascii=False),
                None,
                "[redacted]",
                None,
            ),
        )


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
