from __future__ import annotations

from dataclasses import dataclass


IDENTITY_TERMS = (
    "\u8fd9\u4e2a\u4eba\u662f\u8c01",
    "\u8bc6\u522b\u7167\u7247\u91cc\u7684\u7238\u7238",
    "\u8fd9\u4e2a\u4eba\u53eb\u4ec0\u4e48\u540d\u5b57",
    "\u8fd9\u662f\u4e0d\u662f",
    "who is this",
    "identify this person",
    "family member",
)

COLOR_TERMS = {
    "white": ("white", "\u767d", "\u767d\u8272", "\u767d\u8863"),
    "black": ("black", "\u9ed1", "\u9ed1\u8272"),
    "red": ("red", "\u7ea2", "\u7ea2\u8272"),
    "blue": ("blue", "\u84dd", "\u84dd\u8272"),
    "green": ("green", "\u7eff", "\u7eff\u8272"),
    "yellow": ("yellow", "\u9ec4", "\u9ec4\u8272"),
    "gray": ("gray", "grey", "\u7070", "\u7070\u8272"),
}

OBJECT_TERMS = {
    "laptop": ("laptop", "computer", "\u7535\u8111"),
    "book": ("book", "\u4e66", "\u4e66\u672c"),
    "car": ("car", "\u8f66", "\u6c7d\u8f66"),
    "cup": ("cup", "\u676f"),
    "bag": ("bag", "\u5305"),
}


@dataclass(frozen=True)
class PersonAttributeQuery:
    query_redacted: str
    blocked: bool
    blocked_reason: str | None
    require_person: bool
    upper_color: str | None
    co_occurs_with: str | None
    modality: str | None

    def to_dict(self) -> dict:
        return {
            "query_redacted": self.query_redacted,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "require_person": self.require_person,
            "upper_color": self.upper_color,
            "co_occurs_with": self.co_occurs_with,
            "modality": self.modality,
        }


def parse_person_attribute_query(query: str) -> PersonAttributeQuery:
    text = query.strip()[:240]
    lower = text.lower()
    if any(term in lower or term in text for term in IDENTITY_TERMS):
        return PersonAttributeQuery(
            query_redacted=text,
            blocked=True,
            blocked_reason="face_identification_disabled",
            require_person=False,
            upper_color=None,
            co_occurs_with=None,
            modality=None,
        )
    upper_color = None
    for color, terms in COLOR_TERMS.items():
        if any(term in lower or term in text for term in terms):
            upper_color = color
            break
    co_occurs = None
    for label, terms in OBJECT_TERMS.items():
        if any(term in lower or term in text for term in terms):
            co_occurs = label
            break
    modality = "video" if "video" in lower or "\u89c6\u9891" in text else None
    person_terms = ("person", "people", "\u6709\u4eba", "\u4eba\u7269", "\u4eba")
    require_person = bool(upper_color or co_occurs or any(term in lower or term in text for term in person_terms))
    return PersonAttributeQuery(
        query_redacted=text,
        blocked=False,
        blocked_reason=None,
        require_person=require_person,
        upper_color=upper_color,
        co_occurs_with=co_occurs,
        modality=modality,
    )
