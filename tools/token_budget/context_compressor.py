from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .privacy_redactor import find_private_leaks
from .qwen_token_counter import QwenTokenCounter


TASK_BUDGETS = {
    "nas_search": 512,
    "chinese_search": 512,
    "mixed_zh_en_search": 512,
    "document_qa": 1200,
    "folder_summary": 1500,
    "report_generation": 2000,
    "file_organization_suggestion": 1200,
    "public_research": 3000,
    "cloud_sensitive_mixed": 1200,
    "private_or_denied": 0,
}


@dataclass
class CompressionResult:
    payload: Dict[str, Any] | str
    payload_text: str
    tokens: int
    budget: int
    strategies: List[str]
    citation_hashes_preserved: int
    citation_hashes_expected: int
    private_leak_count: int

    @property
    def budget_compliant(self) -> bool:
        return self.tokens <= self.budget if self.budget > 0 else self.tokens == 0


def dedupe(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = re.sub(r"\s+", " ", value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def query_terms(prompt: str) -> List[str]:
    words = re.findall(r"[A-Za-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", prompt)
    return [w.lower() for w in words[:12]]


def top_k_snippets(prompt: str, context_items: List[str], k: int = 5) -> List[str]:
    terms = query_terms(prompt)
    scored = []
    for index, item in enumerate(context_items):
        low = item.lower()
        score = sum(1 for term in terms if term in low)
        scored.append((score, -index, item))
    scored.sort(reverse=True)
    return [item for score, _, item in scored[:k] if score > 0] or context_items[:k]


class ContextCompressor:
    def __init__(self, counter: Optional[QwenTokenCounter] = None) -> None:
        self.counter = counter or QwenTokenCounter()

    def compress(self, case: Dict[str, Any], redacted_prompt: str, redacted_context: str, route: Dict[str, Any]) -> CompressionResult:
        task_type = case.get("task_type", "unknown")
        if route.get("route") in {"local_only", "cloud_blocked_private"}:
            return CompressionResult("", "", 0, 0, ["local_route_no_cloud_payload"], 0, len(case.get("evidence_hashes", [])), 0)

        budget = TASK_BUDGETS.get(task_type, 1200)
        context_items = redacted_context.splitlines() if redacted_context else case.get("context_items", [])
        clean_items = dedupe(context_items)
        snippets = top_k_snippets(redacted_prompt, clean_items, k=5)
        evidence_hashes = list(dict.fromkeys(case.get("evidence_hashes", [])))
        metadata = case.get("metadata", {})
        summary = {
            "task_type": task_type,
            "query": redacted_prompt,
            "evidence_hashes": evidence_hashes,
            "context_summary": {
                "item_count": len(clean_items),
                "top_items": snippets,
                "metadata": metadata,
            },
            "policy": {
                "raw_private_content_removed": True,
                "redaction_map_included": False,
                "split_private_local": bool(route.get("split_private_local")),
            },
        }
        strategies = ["dedupe", "top_k_snippet", "schema_compression", "budget_cap"]
        if task_type in {"nas_search", "folder_summary", "file_organization_suggestion"}:
            strategies.append("metadata_only")
        if len(clean_items) > len(snippets):
            strategies.append("local_summary")

        payload_text = json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        tokens = self.counter.count_text_tokens(payload_text)
        while tokens > budget and len(summary["context_summary"]["top_items"]) > 1:
            summary["context_summary"]["top_items"].pop()
            payload_text = json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            tokens = self.counter.count_text_tokens(payload_text)
        if tokens > budget:
            summary["context_summary"]["top_items"] = []
            summary["context_summary"]["truncated"] = True
            payload_text = json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            tokens = self.counter.count_text_tokens(payload_text)

        leak_count = len(find_private_leaks(payload_text, case.get("private_markers")))
        preserved = sum(1 for h in evidence_hashes if h in payload_text)
        return CompressionResult(
            payload=summary,
            payload_text=payload_text,
            tokens=tokens,
            budget=budget,
            strategies=strategies,
            citation_hashes_preserved=preserved,
            citation_hashes_expected=len(evidence_hashes),
            private_leak_count=leak_count,
        )


def compress_context(case: Dict[str, Any], redacted_prompt: str, redacted_context: str, route: Dict[str, Any]) -> CompressionResult:
    return ContextCompressor().compress(case, redacted_prompt, redacted_context, route)
