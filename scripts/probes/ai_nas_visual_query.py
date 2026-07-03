#!/usr/bin/env python3
"""Visual query planning for OpenClaw AI-NAS search."""

from __future__ import annotations

import hashlib
import re


COLOR_ALIASES = {
    "white": ["white", "off white", "off_white", "light gray", "light_gray", "\u767d", "\u767d\u8272", "\u7c73\u767d", "\u6d45\u7070"],
    "black": ["black", "\u9ed1", "\u9ed1\u8272"],
    "red": ["red", "\u7ea2", "\u7ea2\u8272"],
    "blue": ["blue", "\u84dd", "\u84dd\u8272", "\u85cd\u8272"],
    "green": ["green", "\u7eff", "\u7eff\u8272", "\u7da0\u8272"],
    "yellow": ["yellow", "\u9ec4", "\u9ec4\u8272", "\u9ec3\u8272"],
    "gray": ["gray", "grey", "\u7070", "\u7070\u8272"],
}

CLOTHING_ALIASES = [
    "wearing",
    "wears",
    "shirt",
    "t-shirt",
    "tee",
    "top",
    "upper garment",
    "upper clothing",
    "clothing",
    "coat",
    "jacket",
    "\u7a7f",
    "\u7a7f\u7740",
    "\u4e0a\u8863",
    "\u4e0a\u88c5",
    "\u4e0a\u534a\u8eab",
    "\u8863\u670d",
    "\u670d\u88c5",
    "\u886c\u886b",
    "t\u6064",
    "\u5916\u5957",
]

PERSON_ALIASES = [
    "person",
    "people",
    "human",
    "player",
    "athlete",
    "man",
    "woman",
    "child",
    "kid",
    "\u4eba",
    "\u4eba\u7269",
    "\u4eba\u50cf",
    "\u5b69\u5b50",
    "\u5c0f\u5b69",
    "\u7537\u4eba",
    "\u5973\u4eba",
]

DOCUMENT_ALIASES = [
    "invoice",
    "receipt",
    "contract",
    "document",
    "screenshot",
    "screen",
    "\u53d1\u7968",
    "\u6536\u636e",
    "\u5408\u540c",
    "\u622a\u56fe",
    "\u5c4f\u5e55",
    "\u6587\u6863",
    "\u8bc1\u4ef6",
]

VEHICLE_ALIASES = ["car", "vehicle", "bike", "\u8f66", "\u6c7d\u8f66", "\u81ea\u884c\u8f66"]

SCENE_ALIASES = {
    "beach": ["beach", "sea", "coast", "\u6d77\u8fb9", "\u6d77\u6ee9"],
    "meal": ["meal", "dinner", "lunch", "restaurant", "\u805a\u9910", "\u5403\u996d", "\u9910\u5385"],
    "sunset": ["sunset", "\u5915\u9633", "\u65e5\u843d"],
}


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle and needle.lower() in text for needle in needles)


def _colors(text: str) -> list[str]:
    out = []
    for canonical, aliases in COLOR_ALIASES.items():
        if _contains_any(text, aliases):
            out.append(canonical)
    return out


def build_visual_query_plan(query: str) -> dict:
    raw = str(query or "").strip()
    lower = raw.lower()
    tokens = re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]", lower)
    colors = _colors(lower)
    clothing = _contains_any(lower, CLOTHING_ALIASES)
    person = clothing or _contains_any(lower, PERSON_ALIASES)
    document = _contains_any(lower, DOCUMENT_ALIASES)
    vehicle = _contains_any(lower, VEHICLE_ALIASES)
    scene_terms = [canonical for canonical, aliases in SCENE_ALIASES.items() if _contains_any(lower, aliases)]

    attributes = []
    if colors:
        target = "upper_clothing.color" if clothing else "dominant_color"
        attributes.append({"name": target, "values": colors})

    entities = []
    if person:
        entities.append("person")
    if vehicle:
        entities.append("vehicle")
    if document:
        entities.append("document_or_screen")

    regions = ["upper_clothing"] if clothing else []
    requires_region = bool(clothing)
    requires_ocr = bool(document)
    free_text_visual = bool(tokens) and not document
    requires_vector = bool(scene_terms or vehicle or person or colors or free_text_visual)
    strict_attributes = bool(clothing and colors)
    if document and not requires_region:
        search_kind = "ocr_document_visual"
    elif requires_region:
        search_kind = "region_attribute_visual"
    elif requires_vector:
        search_kind = "semantic_visual"
    else:
        search_kind = "visual_hybrid"
    return {
        "query": raw,
        "query_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
        "search_kind": search_kind,
        "entities": entities,
        "regions": regions,
        "attributes": attributes,
        "scene_terms": scene_terms,
        "requires_region": requires_region,
        "requires_ocr": requires_ocr,
        "requires_vector": requires_vector,
        "strict_attributes": strict_attributes,
        "tokens": tokens,
    }
