from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .asr_backend import LocalAsrBackend
from .schema import connect, migrate
from .segment_writer import write_srt, write_vtt


class SubtitleExtractionService:
    def __init__(self, *, db_path: str | Path, artifact_dir: str | Path, backend: LocalAsrBackend | None = None) -> None:
        self.db_path = Path(db_path)
        self.artifact_dir = Path(artifact_dir)
        self.backend = backend or LocalAsrBackend()

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        backend_status = self.backend.status()
        conn = connect(self.db_path)
        try:
            transcript_count = conn.execute("SELECT count(*) FROM media_transcripts").fetchone()[0]
            segment_count = conn.execute("SELECT count(*) FROM media_transcript_segments").fetchone()[0]
        finally:
            conn.close()
        degraded = backend_status.get("degraded") or transcript_count == 0 or segment_count == 0
        reason = backend_status.get("degraded_reason") if backend_status.get("degraded") else "transcripts_missing" if degraded else None
        return {
            "ok": True,
            "schema": "digua_subtitle_extraction_v1",
            "backend": backend_status,
            "transcript_count": transcript_count,
            "segment_count": segment_count,
            "cloud_used": False,
            "raw_path_returned": False,
            "fixture_only_for_ci": backend_status.get("backend") == "fixture",
            "degraded": bool(degraded),
            "degraded_reason": reason,
        }

    def extract(self, payload: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "manual_asset")
        media_path = payload.get("media_path")
        if not media_path:
            return {"ok": False, "error": "media_path_required", "raw_path_returned": False}
        result = self.backend.transcribe(media_path)
        if not result.get("ok"):
            return {**result, "raw_path_returned": False, "cloud_used": False}
        transcript_id = "tr_" + hashlib.sha256(f"{asset_id}:{time.time()}".encode("utf-8")).hexdigest()[:20]
        evidence_ref = "subtitle_ev_" + transcript_id[-12:]
        out_dir = self.artifact_dir / transcript_id
        out_dir.mkdir(parents=True, exist_ok=True)
        srt_path = out_dir / f"{transcript_id}.srt"
        vtt_path = out_dir / f"{transcript_id}.vtt"
        segments = result.get("segments") or []
        write_srt(srt_path, segments)
        write_vtt(vtt_path, segments)
        transcript_text = " ".join(str(seg.get("text_redacted") or "") for seg in segments)[:4000]
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO media_transcripts(
                  transcript_id,asset_id,modality,language,backend,model_name,duration_sec,transcript_redacted,
                  srt_path,vtt_path,evidence_ref,privacy_level,cloud_used,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,?)
                """,
                (
                    transcript_id,
                    asset_id,
                    str(payload.get("modality") or "video"),
                    result.get("language"),
                    result.get("backend"),
                    result.get("model_name"),
                    result.get("duration_sec"),
                    transcript_text,
                    str(srt_path),
                    str(vtt_path),
                    evidence_ref,
                    "private_local_only",
                    _now(),
                ),
            )
            conn.execute("DELETE FROM media_transcript_segments_fts WHERE asset_id=?", (asset_id,))
            for idx, seg in enumerate(segments):
                segment_id = f"{transcript_id}_s{idx}"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO media_transcript_segments(segment_id,transcript_id,asset_id,start_sec,end_sec,text_redacted,confidence,evidence_ref)
                    VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (segment_id, transcript_id, asset_id, seg["start_sec"], seg["end_sec"], seg["text_redacted"], seg.get("confidence"), evidence_ref),
                )
                conn.execute(
                    "INSERT INTO media_transcript_segments_fts(segment_id,asset_id,text_redacted) VALUES(?,?,?)",
                    (segment_id, asset_id, seg["text_redacted"]),
                )
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "schema": "digua_subtitle_extraction_v1",
            "transcript_id": transcript_id,
            "segment_count": len(segments),
            "srt_available": srt_path.exists(),
            "vtt_available": vtt_path.exists(),
            "evidence_ref": evidence_ref,
            "cloud_used": False,
            "raw_path_returned": False,
            "fixture_only_for_ci": bool(result.get("fixture_only_for_ci")),
        }

    def transcript(self, asset_id: str) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM media_transcripts WHERE asset_id=? ORDER BY created_at DESC LIMIT 1", (asset_id,)).fetchone()
            segments = [dict(seg) for seg in conn.execute("SELECT * FROM media_transcript_segments WHERE asset_id=? ORDER BY start_sec", (asset_id,))]
        finally:
            conn.close()
        if row is None:
            return {"ok": False, "error": "not_found", "raw_path_returned": False}
        data = dict(row)
        data.pop("srt_path", None)
        data.pop("vtt_path", None)
        return {"ok": True, "transcript": data, "segments": segments, "raw_path_returned": False, "cloud_used": False}

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query") or "").strip()
        if not query:
            return {"ok": False, "error": "query_required"}
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            try:
                rows = [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT s.* FROM media_transcript_segments_fts f
                        JOIN media_transcript_segments s ON s.segment_id=f.segment_id
                        WHERE media_transcript_segments_fts MATCH ?
                        LIMIT ?
                        """,
                        (query.replace('"', ""), int(payload.get("top_k") or 10)),
                    )
                ]
            except Exception:
                rows = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT * FROM media_transcript_segments WHERE text_redacted LIKE ? LIMIT ?",
                        (f"%{query}%", int(payload.get("top_k") or 10)),
                    )
                ]
        finally:
            conn.close()
        return {"ok": True, "schema": "digua_subtitle_extraction_v1", "query_redacted": query[:200], "results": rows, "raw_path_returned": False, "cloud_used": False}

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "")
        data = self.transcript(asset_id)
        if not data.get("ok"):
            return data
        text = data["transcript"].get("transcript_redacted") or ""
        return {"ok": True, "summary_redacted": text[:300], "evidence_ref": data["transcript"].get("evidence_ref"), "cloud_used": False, "raw_path_returned": False}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
