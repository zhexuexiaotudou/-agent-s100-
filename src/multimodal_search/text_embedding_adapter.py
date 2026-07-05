from __future__ import annotations


def text_embedding_status() -> dict:
    return {"enabled": False, "available": False, "reason": "document_embedding_feature_flag_disabled"}
