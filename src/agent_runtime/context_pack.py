from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .privacy import estimate_tokens, private_leak_count, redact_text, stable_hash
from .trace_schema import TraceRecorder


DEFAULT_ALLOWED_TOOLS = [
    "agent_runtime.context_pack.compile",
    "agent_runtime.memory.lookup",
    "agent_runtime.multimodal_index.search",
    "agent_runtime.rag.query",
    "harness.copy.preview",
    "harness.copy.dry_run",
]


@dataclass(frozen=True)
class ContextCandidate:
    source: str
    title: str
    text: str
    evidence_ref: str | None = None
    acl_allowed: bool = True
    media_type: str = "text"


class ContextPackCompiler:
    def __init__(self, *, token_budget: int = 4096, allowed_tools: Iterable[str] | None = None) -> None:
        self.token_budget = token_budget
        self.allowed_tools = list(allowed_tools or DEFAULT_ALLOWED_TOOLS)

    def compile(
        self,
        *,
        query: str,
        workspace: str,
        user_id: str,
        candidates: Iterable[ContextCandidate | dict[str, Any]],
        request_id: str | None = None,
        tool_intent: str = "answer_with_evidence",
    ) -> dict[str, Any]:
        request_id = request_id or "ctx_" + stable_hash({"query": query, "workspace": workspace, "user_id": user_id}, 16)
        safe_query, query_redactions = redact_text(query)
        items: list[dict[str, Any]] = []
        denied_count = 0
        redaction_count = query_redactions
        token_total = estimate_tokens(safe_query)

        for index, raw in enumerate(candidates, start=1):
            candidate = raw if isinstance(raw, ContextCandidate) else ContextCandidate(**raw)
            if not candidate.acl_allowed:
                denied_count += 1
                continue
            safe_text, count = redact_text(candidate.text)
            safe_title, title_count = redact_text(candidate.title)
            safe_source, source_count = redact_text(candidate.source)
            redaction_count += count + title_count + source_count
            snippet = safe_text[:500]
            token_total += estimate_tokens(snippet)
            items.append(
                {
                    "rank": len(items) + 1,
                    "source": safe_source[:220],
                    "title": safe_title[:160],
                    "media_type": candidate.media_type,
                    "evidence_ref": candidate.evidence_ref or f"ctx_ev_{index}_{stable_hash(candidate.source, 8)}",
                    "source_hash": stable_hash(candidate.source, 24),
                    "snippet": snippet,
                    "snippet_token_estimate": estimate_tokens(snippet),
                    "raw_content_stored": False,
                }
            )

        pack = {
            "schema": "digua_agent_runtime_context_pack_v1",
            "pack_id": "ctxpack_" + stable_hash({"request_id": request_id, "items": items}, 24),
            "request_id": request_id,
            "workspace": workspace,
            "user_id_hash": stable_hash(user_id, 16),
            "query": safe_query,
            "tool_intent": tool_intent,
            "context_items": items,
            "evidence_refs": [item["evidence_ref"] for item in items],
            "acl_denied_count": denied_count,
            "redaction_count": redaction_count,
            "token_budget": self.token_budget,
            "token_estimate": token_total,
            "budget_ok": token_total <= self.token_budget,
            "allowed_tool_ids": list(self.allowed_tools),
            "qwen_execution_authority": False,
            "cloud_private_raw_egress": False,
            "redaction_map_exported": False,
        }
        trace = TraceRecorder()
        trace.record_required_skeleton()
        pack["trace"] = trace.to_record(
            request_id=request_id,
            attributes={
                "context_item_count": len(items),
                "acl_denied_count": denied_count,
                "token_estimate": token_total,
            },
        )
        pack["private_leak_count"] = private_leak_count(pack)
        pack["ok"] = pack["private_leak_count"] == 0 and pack["budget_ok"] and bool(items)
        return pack

    @staticmethod
    def write_json(path: str | Path, pack: dict[str, Any]) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sample_context_candidates(case_index: int) -> list[ContextCandidate]:
    return [
        ContextCandidate(
            source=f"document_policy_{case_index}.md",
            title=f"AI-NAS policy note {case_index}",
            text=(
                f"Case {case_index}: OpenClaw remains the gateway, Qwen is advisory only, "
                "and copy execution must pass the Harness allowlist dispatcher."
            ),
            evidence_ref=f"policy_{case_index}",
        ),
        ContextCandidate(
            source=f"/mnt/nas/openclaw/Personal/private/customer_{case_index}.txt",
            title="private raw path should be redacted",
            text="Private source /mnt/nas/openclaw/Personal/family/photo.jpg with password marker.",
            evidence_ref=f"private_{case_index}",
        ),
        ContextCandidate(
            source=f"denied_{case_index}.md",
            title="denied evidence",
            text="This denied item must not enter the pack.",
            evidence_ref=f"denied_{case_index}",
            acl_allowed=False,
        ),
    ]
