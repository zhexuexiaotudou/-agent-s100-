from __future__ import annotations

from typing import Any


def match_rule(asset: dict[str, Any], rule: dict[str, Any]) -> tuple[bool, float, list[str]]:
    matched: list[str] = []
    score = 0.0
    if rule.get("modalities") and asset.get("modality") in set(rule["modalities"]):
        matched.append("modality")
        score += 0.25
    labels = set(asset.get("object_labels") or [])
    if labels.intersection(rule.get("object_labels_any") or []):
        matched.append("object_labels_any")
        score += 0.35
    attrs = set(asset.get("person_attrs") or [])
    person_attrs = rule.get("person_attrs") or {}
    if person_attrs.get("person_present") and "person_present" in attrs:
        matched.append("person_present")
        score += 0.25
    if person_attrs.get("upper_color") and f"upper_{person_attrs['upper_color']}" in attrs:
        matched.append("upper_color")
        score += 0.4
    if person_attrs.get("lower_color") and f"lower_{person_attrs['lower_color']}" in attrs:
        matched.append("lower_color")
        score += 0.2
    haystack = " ".join(
        [
            str(asset.get("title_redacted") or ""),
            str(asset.get("summary_redacted") or ""),
            str(asset.get("modality") or ""),
            " ".join(asset.get("object_labels") or []),
            " ".join(asset.get("person_attrs") or []),
            " ".join(asset.get("category_names") or []),
        ]
    ).lower()
    for key, marker in (("ocr_terms_any", "ocr_terms_any"), ("transcript_terms_any", "transcript_terms_any"), ("title_terms_any", "title_terms_any")):
        terms = [str(term).lower() for term in rule.get(key) or []]
        if any(term in haystack for term in terms):
            matched.append(marker)
            score += 0.3
    semantic_query = str(rule.get("semantic_query") or "").lower()
    if semantic_query and any(part and part in haystack for part in semantic_query.split()):
        matched.append("semantic_query")
        score += 0.2
    return bool(matched), min(score, 1.0), matched
