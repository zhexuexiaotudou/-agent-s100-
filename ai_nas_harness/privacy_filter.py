from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


REPLACEMENT = "[REDACTED_NAS_CONTEXT]"

SENSITIVE_TERMS = [
    "Personal",
    "Inbox",
    "Documents",
    "Photos",
    "Family",
    "Finance",
    "Medical",
    "Private",
    "invoice",
    "receipt",
    "contract",
    "payment",
    "family",
    "child",
    "face",
    "screenshot",
    "bank",
    "salary",
    "个人",
    "家庭",
    "财务",
    "医疗",
    "身份证",
    "合同",
    "照片",
    "相册",
    "私密",
    "隐私",
]

PATH_PATTERNS = [
    re.compile(r"(?i)(?:/mnt/(?:nas|data)|/home)/[^\s,;\"'<>]+"),
    re.compile(r"(?i)(?:[A-Za-z]:\\|\\\\)[^\s,;\"'<>]+"),
    re.compile(r"(?i)(?:^|[\s,;])(?:Personal|Inbox|Documents|Photos|Family|Finance|Medical|Private)(?:[/\\][^\s,;\"'<>]+)?"),
    re.compile(r"(?i)\.\.(?:/|\\)"),
    re.compile(r"(?i)raw[_ -]?nas[_ -]?snippet[:=][^\n]+"),
    re.compile(r"(?i)denied[_ -]?acl[_ -]?snippet[:=][^\n]+"),
]

FILENAME_PATTERN = re.compile(
    r"(?i)\b[^\s/\\]+(?:invoice|receipt|contract|idcard|passport|salary|medical|family|private|身份证|合同|照片|相册|财务|医疗)[^\s/\\]*"
)


@dataclass
class RedactionResult:
    raw_payload_hash: str
    redacted_text: str
    redacted_preview: str
    redaction_applied: bool
    redacted_terms: list[str]
    redacted_patterns: list[str]
    leak_count: int
    leak_markers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "egress_payload_hash": self.raw_payload_hash,
            "redacted_text": self.redacted_text,
            "redacted_preview": self.redacted_preview,
            "redaction_applied": self.redaction_applied,
            "redaction_summary": {
                "redacted_terms": self.redacted_terms,
                "redacted_patterns": self.redacted_patterns,
                "leak_count": self.leak_count,
                "leak_markers": self.leak_markers,
            },
        }


def payload_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_cloud_payload(text: str, *, max_preview_chars: int = 300) -> RedactionResult:
    redacted = text
    redacted_patterns: list[str] = []
    for pattern in PATH_PATTERNS:
        if pattern.search(redacted):
            redacted_patterns.append(pattern.pattern)
            redacted = pattern.sub(lambda match: match.group(0)[0] + REPLACEMENT if match.group(0)[0].isspace() else REPLACEMENT, redacted)
    if FILENAME_PATTERN.search(redacted):
        redacted_patterns.append(FILENAME_PATTERN.pattern)
        redacted = FILENAME_PATTERN.sub(REPLACEMENT, redacted)

    terms_hit: list[str] = []
    for term in SENSITIVE_TERMS:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(redacted):
            terms_hit.append(term)
            redacted = pattern.sub(REPLACEMENT, redacted)

    leaks = detect_private_leaks(redacted)
    return RedactionResult(
        raw_payload_hash=payload_hash(text),
        redacted_text=redacted,
        redacted_preview=redacted[:max_preview_chars],
        redaction_applied=redacted != text,
        redacted_terms=sorted(set(terms_hit)),
        redacted_patterns=sorted(set(redacted_patterns)),
        leak_count=len(leaks),
        leak_markers=leaks,
    )


def detect_private_leaks(text: str) -> list[str]:
    leaks: list[str] = []
    for pattern in PATH_PATTERNS:
        if pattern.search(text):
            leaks.append(f"pattern:{pattern.pattern}")
    if FILENAME_PATTERN.search(text):
        leaks.append("pattern:sensitive_filename")
    lowered = text.lower()
    for term in SENSITIVE_TERMS:
        if term.lower() in lowered:
            leaks.append(f"term:{term}")
    return sorted(set(leaks))
