from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.token_budget.cloud_route_decider import decide_route
from tools.token_budget.context_compressor import ContextCompressor
from tools.token_budget.privacy_redactor import PrivacyRedactor, find_private_leaks
from tools.token_budget.qwen_token_counter import QwenTokenCounter
from tools.token_budget.token_trace import append_trace, make_trace_record


DEFAULT_TRACE_PATH = REPO_ROOT / "reports" / "token_budget_traces_sample.jsonl"


def _compact(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _first_text(payload: Dict[str, Any]) -> str:
    for key in ("user_prompt", "prompt", "query", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and isinstance(item.get("content"), str):
                return item["content"]
    return ""


def _context_text(payload: Dict[str, Any]) -> str:
    value = payload.get("context_text", payload.get("context", ""))
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if isinstance(value, dict):
        return _compact(value)
    return ""


def _case_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = _first_text(payload)
    context = _context_text(payload)
    return {
        "case_id": payload.get("case_id") or f"api_{uuid.uuid4().hex[:12]}",
        "task_type": payload.get("task_type") or payload.get("category") or "public_research",
        "category": payload.get("category") or payload.get("task_type") or "api_request",
        "workspace": payload.get("workspace") or "openclaw",
        "user_prompt": prompt,
        "context_text": context,
        "context_items": context.splitlines(),
        "private_markers": payload.get("private_markers") if isinstance(payload.get("private_markers"), list) else [],
        "evidence_hashes": payload.get("evidence_hashes") if isinstance(payload.get("evidence_hashes"), list) else [],
        "acl_denied": bool(payload.get("acl_denied")),
        "prompt_injection": bool(payload.get("prompt_injection")),
        "sensitivity": payload.get("sensitivity") or "",
        "complexity": payload.get("complexity") or "",
    }


class TokenBudgetIntegration:
    def __init__(self, trace_path: str | Path | None = None, tokenizer_path: str | None = None) -> None:
        self.trace_path = Path(trace_path) if trace_path else DEFAULT_TRACE_PATH
        self.counter = QwenTokenCounter(tokenizer_path)
        self.redactor = PrivacyRedactor()
        self.compressor = ContextCompressor(self.counter)

    def estimate(self, payload: Dict[str, Any], *, record_trace: bool = True) -> Dict[str, Any]:
        case = _case_from_payload(payload)
        prompt_result = self.redactor.redact(case["user_prompt"])
        context_result = self.redactor.redact(case["context_text"])
        route = decide_route(case, prompt_result.redacted_text + "\n" + context_result.redacted_text).to_dict()

        naive_payload = {
            "task_type": case["task_type"],
            "user_prompt": case["user_prompt"],
            "context": case["context_text"],
            "evidence_hashes": case["evidence_hashes"],
        }
        redacted_payload = {
            "task_type": case["task_type"],
            "user_prompt": prompt_result.redacted_text,
            "context": context_result.redacted_text,
            "evidence_hashes": case["evidence_hashes"],
            "redaction_map_included": False,
        }
        compression = self.compressor.compress(case, prompt_result.redacted_text, context_result.redacted_text, route)

        raw_user_prompt_tokens = self.counter.count_text_tokens(case["user_prompt"])
        raw_context_tokens = self.counter.count_text_tokens(case["context_text"])
        naive_cloud_payload_tokens = self.counter.count_payload_tokens(naive_payload)
        redacted_payload_text = _compact(redacted_payload)
        redacted_payload_tokens = self.counter.count_text_tokens(redacted_payload_text)
        optimized_cloud_payload_tokens = compression.tokens
        saved_tokens = max(0, naive_cloud_payload_tokens - optimized_cloud_payload_tokens)
        reduction_ratio = saved_tokens / naive_cloud_payload_tokens if naive_cloud_payload_tokens else 0.0
        private_leaks = find_private_leaks(compression.payload_text, case.get("private_markers"))
        redacted_leaks = find_private_leaks(redacted_payload_text, case.get("private_markers"))

        token_counts = {
            "raw_user_prompt_tokens": raw_user_prompt_tokens,
            "raw_context_tokens": raw_context_tokens,
            "naive_cloud_payload_tokens": naive_cloud_payload_tokens,
            "redacted_payload_tokens": redacted_payload_tokens,
            "compressed_payload_tokens": compression.tokens,
            "optimized_cloud_payload_tokens": optimized_cloud_payload_tokens,
            "saved_tokens": saved_tokens,
            "reduction_ratio": round(reduction_ratio, 6),
        }
        quality = "pass" if not private_leaks and not redacted_leaks and compression.budget_compliant else "review"
        run_id = str(payload.get("run_id") or f"token-budget-{uuid.uuid4().hex[:12]}")
        trace = make_trace_record(
            run_id=run_id,
            case=case,
            route=route,
            token_counts=token_counts,
            redaction_count=prompt_result.redaction_count + context_result.redaction_count,
            private_leak_count=len(private_leaks) + len(redacted_leaks),
            tokenizer_identity_hash=self.counter.identity["tokenizer_identity_hash"],
            quality_check=quality,
        )
        if record_trace:
            append_trace(self.trace_path, trace)

        return {
            "ok": quality in {"pass", "review"},
            "run_id": run_id,
            "case_id": case["case_id"],
            "task_type": case["task_type"],
            "workspace": case["workspace"],
            "route": route["route"],
            "route_reason": route["reason"],
            "cloud_allowed": route["cloud_allowed"],
            "cloud_call_avoided": route["route"] in {"local_only", "cloud_blocked_private"},
            "token_counts": token_counts,
            "redaction_count": prompt_result.redaction_count + context_result.redaction_count,
            "private_leak_count": len(private_leaks) + len(redacted_leaks),
            "redaction_map_included": False,
            "optimized_payload_preview": compression.payload if route["cloud_allowed"] else None,
            "trace": trace,
            "tokenizer_identity": self.safe_identity(),
            "quality_check": quality,
        }

    def route(self, payload: Dict[str, Any], *, record_trace: bool = True) -> Dict[str, Any]:
        result = self.estimate(payload, record_trace=record_trace)
        return {
            "ok": result["ok"],
            "run_id": result["run_id"],
            "case_id": result["case_id"],
            "task_type": result["task_type"],
            "route": result["route"],
            "route_reason": result["route_reason"],
            "cloud_allowed": result["cloud_allowed"],
            "cloud_call_avoided": result["cloud_call_avoided"],
            "redaction_count": result["redaction_count"],
            "private_leak_count": result["private_leak_count"],
            "token_counts": result["token_counts"],
            "trace_hash": result["trace"]["trace_hash"],
        }

    def trace(self, run_id: str) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        if self.trace_path.exists():
            with self.trace_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if row.get("run_id") == run_id:
                        rows.append(row)
        return {"ok": bool(rows), "run_id": run_id, "traces": rows}

    def safe_identity(self) -> Dict[str, Any]:
        identity = dict(self.counter.identity)
        identity.pop("file_hashes", None)
        return identity

    def summary(self) -> Dict[str, Any]:
        analysis_path = REPO_ROOT / "reports" / "17080_token_cost_reduction_analysis.json"
        if not analysis_path.exists():
            analysis_path = REPO_ROOT / "reports" / "17060_token_cost_reduction_analysis.json"
        analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else {}
        return {
            "ok": True,
            "tokenizer_identity": self.safe_identity(),
            "trace_path": str(self.trace_path),
            "latest_analysis": analysis,
        }

    def benchmark_summary(self) -> Dict[str, Any]:
        path = REPO_ROOT / "reports" / "17070_token_budget_benchmark_results.json"
        if not path.exists():
            path = REPO_ROOT / "reports" / "17050_token_budget_benchmark_results.json"
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return {"ok": bool(payload), "benchmark_summary": payload}


def estimate_token_budget(payload: Dict[str, Any], *, record_trace: bool = True) -> Dict[str, Any]:
    return TokenBudgetIntegration().estimate(payload, record_trace=record_trace)


def route_token_budget(payload: Dict[str, Any], *, record_trace: bool = True) -> Dict[str, Any]:
    return TokenBudgetIntegration().route(payload, record_trace=record_trace)

