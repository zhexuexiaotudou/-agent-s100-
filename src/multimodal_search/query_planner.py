from __future__ import annotations

import re
from dataclasses import dataclass


ZH_VISUAL_TERMS = {
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
    "\u4eba": "person people portrait",
    "\u4eba\u7269": "person people portrait",
    "\u4eba\u50cf": "person portrait",
    "\u884c\u4eba": "person pedestrian",
    "\u6709\u4eba": "person people",
    "\u56fe\u7247": "image photo",
    "\u7167\u7247": "image photo",
    "\u56fe": "image",
    "\u89c6\u9891": "video",
    "\u97f3\u9891": "audio",
    "\u6587\u6863": "document",
    "\u4ee3\u7801": "code",
}

ZH_MODALITY_TERMS = {
    "\u56fe\u7247": "image",
    "\u7167\u7247": "image",
    "\u89c6\u9891": "video",
    "\u97f3\u9891": "audio",
    "\u6587\u6863": "document",
    "\u4ee3\u7801": "code",
}


@dataclass(frozen=True)
class QueryPlan:
    query_redacted: str
    query_type: str
    modality_filters: list[str]
    original_terms: list[str]
    visual_query_en: str
    retrieval_mode: str


def redact_query(query: str) -> str:
    text = query.strip()[:500]
    return re.sub(r"(?i)(password|token|credential|secret|api[_-]?key)\s*[:=]\s*\S+", r"\1=[redacted]", text)


def plan_query(query: str, *, modality: str | None = None) -> QueryPlan:
    redacted = redact_query(query)
    q_lower = redacted.lower()
    filters: list[str] = []
    if modality and modality != "all":
        filters.append(modality)
    else:
        for key, mod in [("image", "image"), ("photo", "image"), ("video", "video"), ("audio", "audio"), ("code", "code"), ("document", "document")]:
            if key in q_lower:
                filters.append(mod)
        for zh, mod in ZH_MODALITY_TERMS.items():
            if zh in redacted:
                filters.append(mod)
        filters = sorted(set(filters))
    visual_parts = [q_lower]
    for zh, en in ZH_VISUAL_TERMS.items():
        if zh in redacted:
            visual_parts.append(en)
    query_type = filters[0] if len(filters) == 1 else "all"
    return QueryPlan(
        query_redacted=redacted,
        query_type=query_type,
        modality_filters=filters,
        original_terms=[part for part in re.split(r"\s+", redacted) if part],
        visual_query_en=" ".join(visual_parts),
        retrieval_mode="fts_first_plus_image_embedding",
    )
