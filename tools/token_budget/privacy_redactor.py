from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


PRIVATE_TERMS = (
    "身份证",
    "成绩单",
    "发票",
    "报销",
    "家庭",
    "合同",
    "病历",
    "聊天记录",
    "银行卡",
    "工资",
    "财务",
    "Personal",
    "Private",
    "ACL_DENIED",
    "Denied",
)


@dataclass
class RedactionResult:
    redacted_text: str
    counts: Dict[str, int]
    redaction_map: Dict[str, str] = field(default_factory=dict)

    @property
    def redaction_count(self) -> int:
        return sum(self.counts.values())


def short_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def placeholder(kind: str, raw: str) -> str:
    return f"<PRIVATE_{kind}_HASH:{short_hash(raw)}>"


class PrivacyRedactor:
    def __init__(self) -> None:
        path_chars = r"""[^\s\]\)'"`,;]+"""
        self.patterns: List[tuple[str, re.Pattern[str]]] = [
            ("SECRET", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[A-Za-z0-9_\-./+=]{8,}")),
            ("SECRET", re.compile(r"(?i)\b(?:sk|pk|ak)[-_][A-Za-z0-9_\-]{16,}\b")),
            ("PATH", re.compile(r"(?i)(?:\.\./|\.\.\\|%2e%2e|%252e%252e)[^\s\]\)'\"]*")),
            ("EMAIL", re.compile(r"(?<![\w.])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.])")),
            ("PHONE", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")),
            ("ID", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
            ("ID", re.compile(r"(?i)(?:id|student|学号|身份证号)[:：\s-]*\d{12,16}")),
            ("POLICY", re.compile(r"(?i)\bACL_DENIED\b|访问被拒绝|权限不足")),
            ("BLOB", re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{48,}={0,2}(?![A-Za-z0-9+/=])")),
            ("PATH", re.compile(rf"(?:/mnt/nas/openclaw|/OpenClawWorkspace|\\\\NAS\\OpenClawWorkspace){path_chars}", re.IGNORECASE)),
            ("PATH", re.compile(rf"[A-Za-z]:\\Users\\[^\\\s]+\\(?:Documents|Downloads|Desktop|Pictures)\\{path_chars}", re.IGNORECASE)),
            ("PATH", re.compile(rf"(?:Personal|Private|家庭|证件|发票|聊天记录|成绩|合同|财务|病历)[/\\]{path_chars}", re.IGNORECASE)),
            ("FILENAME", re.compile(r"[^\s/\\\]\)'\"]*(?:身份证|成绩单|发票|报销|家庭|合同|病历|聊天|工资|银行卡|secret|private|token)[^\s/\\\]\)'\"]*\.(?:pdf|docx|xlsx|jpg|jpeg|png|txt|md|zip|json|csv)", re.IGNORECASE)),
            ("FILENAME", re.compile(r"[A-Za-z0-9_-]{4,}_[\u4e00-\u9fff]{2,}_[^\s/\\\]\)'\"]+\.(?:pdf|docx|xlsx|jpg|jpeg|png)", re.IGNORECASE)),
        ]

    def redact(self, text: Any) -> RedactionResult:
        value = "" if text is None else str(text)
        redaction_map: Dict[str, str] = {}
        counts: Dict[str, int] = {}

        def replace(kind: str, match: re.Match[str]) -> str:
            raw = match.group(0)
            token = placeholder(kind, raw)
            redaction_map[token] = raw
            counts[kind] = counts.get(kind, 0) + 1
            return token

        redacted = value
        for kind, pattern in self.patterns:
            redacted = pattern.sub(lambda m, k=kind: replace(k, m), redacted)

        lines: List[str] = []
        for line in redacted.splitlines():
            term_hits = sum(line.count(term) for term in PRIVATE_TERMS if term in line)
            if (len(line) >= 160 and term_hits > 0) or term_hits >= 3:
                token = placeholder("SNIPPET", line)
                redaction_map[token] = line
                counts["SNIPPET"] = counts.get("SNIPPET", 0) + 1
                lines.append(token)
            else:
                lines.append(line)
        redacted = "\n".join(lines)
        return RedactionResult(redacted_text=redacted, counts=counts, redaction_map=redaction_map)


def redact_text(text: Any) -> RedactionResult:
    return PrivacyRedactor().redact(text)


def batch_redact_texts(texts: Iterable[Any]) -> List[RedactionResult]:
    redactor = PrivacyRedactor()
    return [redactor.redact(text) for text in texts]


def strip_placeholders(text: str) -> str:
    return re.sub(r"<PRIVATE_[A-Z_]+_HASH:[0-9a-f]{12,64}>", "", text)


def find_private_leaks(text: Any, markers: Optional[Iterable[str]] = None) -> List[str]:
    value = strip_placeholders("" if text is None else str(text))
    leaks: List[str] = []
    if markers:
        for marker in markers:
            if marker and marker in value:
                leaks.append(marker)
    redactor = PrivacyRedactor()
    for _, pattern in redactor.patterns:
        for match in pattern.finditer(value):
            leaks.append(match.group(0))
    return sorted(set(leaks))


def cloud_payload_has_raw_private(text: Any, markers: Optional[Iterable[str]] = None) -> bool:
    return bool(find_private_leaks(text, markers))
