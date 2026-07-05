from __future__ import annotations

from .document_indexer import extract_text


def extract_code_text(path: str) -> str:
    return extract_text(path)
