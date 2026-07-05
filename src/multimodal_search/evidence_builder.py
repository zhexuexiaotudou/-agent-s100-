from __future__ import annotations

import hashlib
from typing import Any


def evidence_ref(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return "mm_ev_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:18]


def build_result(row: dict[str, Any], *, rank: int, score: float, matched_by: list[str], components: dict[str, float | None]) -> dict[str, Any]:
    return {
        "rank": rank,
        "asset_id": row["asset_id"],
        "modality": row["modality"],
        "title_redacted": row.get("title_redacted") or "",
        "thumbnail_url": row.get("thumbnail_url"),
        "evidence_ref": evidence_ref(row["asset_id"], rank, matched_by),
        "snippet_redacted": row.get("snippet_redacted") or "",
        "timestamp_sec": row.get("timestamp_sec"),
        "score": round(float(score), 6),
        "score_components": components,
        "matched_by": matched_by,
        "privacy_level": row.get("privacy_level") or "private_local_only",
        "path_hash": row.get("path_hash"),
    }
