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
    "\u82b1": "flowers blossoms",
    "\u82b1\u6735": "flowers blossoms",
    "\u9c9c\u82b1": "flowers blossoms",
    "\u5efa\u7b51": "building architecture cityscape",
    "\u697c\u623f": "building architecture",
    "\u57ce\u5e02": "city architecture cityscape",
    "\u56fe\u7247": "image photo",
    "\u7167\u7247": "image photo",
    "\u56fe": "image",
    "\u89c6\u9891": "video",
    "\u97f3\u9891": "audio",
    "\u6587\u6863": "document",
    "\u4ee3\u7801": "code",
}

ZH_VISUAL_CONCEPTS = (
    {
        "terms": ("\u82b1\u6735", "\u9c9c\u82b1", "\u82b1"),
        "query": "a close-up photo of flowers and blossoms",
        "keywords": ("flower", "flowers", "blossom", "blossoms"),
    },
    {
        "terms": ("\u5efa\u7b51", "\u697c\u623f", "\u57ce\u5e02"),
        "query": "a photo of a building, architecture, or cityscape",
        "keywords": ("building", "architecture", "cityscape"),
    },
    {
        "terms": ("\u52a8\u7269", "\u5ba0\u7269", "\u732b", "\u72d7", "\u9e1f"),
        "query": "a photo of an animal or pet",
        "keywords": ("animal", "pet", "cat", "dog", "bird"),
    },
    {
        "terms": ("\u6c7d\u8f66", "\u8f66\u8f86", "\u516c\u4ea4", "\u706b\u8f66", "\u98de\u673a", "\u8239"),
        "query": "a photo of a vehicle, car, bus, train, airplane, or boat",
        "keywords": ("vehicle", "car", "bus", "train", "airplane", "boat"),
    },
    {
        "terms": ("\u98df\u7269", "\u7f8e\u98df", "\u9910\u98df", "\u996e\u6599"),
        "query": "a photo of food, a meal, or a drink",
        "keywords": ("food", "meal", "drink"),
    },
    {
        "terms": ("\u98ce\u666f", "\u81ea\u7136", "\u5c71", "\u6d77", "\u68ee\u6797", "\u5929\u7a7a", "\u8349\u5730"),
        "query": "a landscape photo of nature, mountains, sea, forest, sky, or grassland",
        "keywords": ("landscape", "nature", "mountain", "sea", "forest", "sky", "grassland"),
    },
)

GENERIC_VISUAL_TRANSLATIONS = {"image photo", "image", "video", "audio", "document", "code"}

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
    visual_query_variants_en: list[str]
    visual_semantic_search_supported: bool
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
    translated_visual_terms: list[str] = []
    for zh, en in ZH_VISUAL_TERMS.items():
        if zh in redacted:
            visual_parts.append(en)
            if en not in GENERIC_VISUAL_TRANSLATIONS and en not in translated_visual_terms:
                translated_visual_terms.append(en)
    concept_queries: list[str] = []
    concept_keywords: list[str] = []
    for concept in ZH_VISUAL_CONCEPTS:
        if any(term in redacted for term in concept["terms"]):
            concept_queries.append(str(concept["query"]))
            concept_keywords.extend(str(term) for term in concept["keywords"])
    original_terms = [part for part in re.split(r"\s+", redacted) if part]
    for keyword in concept_keywords:
        if keyword not in original_terms:
            original_terms.append(keyword)
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", redacted))
    if concept_queries:
        visual_query_variants_en = concept_queries
    elif has_cjk and translated_visual_terms:
        visual_query_variants_en = ["a photo of " + " ".join(translated_visual_terms)]
    elif has_cjk:
        visual_query_variants_en = []
    else:
        visual_query_variants_en = [q_lower]
    visual_query_en = " OR ".join(visual_query_variants_en)
    query_type = filters[0] if len(filters) == 1 else "all"
    return QueryPlan(
        query_redacted=redacted,
        query_type=query_type,
        modality_filters=filters,
        original_terms=original_terms,
        visual_query_en=visual_query_en,
        visual_query_variants_en=visual_query_variants_en,
        visual_semantic_search_supported=bool(visual_query_variants_en),
        retrieval_mode="fts_first_plus_image_embedding",
    )
