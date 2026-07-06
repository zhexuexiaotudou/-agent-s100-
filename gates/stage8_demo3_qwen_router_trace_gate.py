from __future__ import annotations

import argparse
import json

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload, has_raw_path, http_post_json


NAME = "stage8_demo3_qwen_router_trace_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate demo 3 Qwen router, privacy tokenizer, token budget, and trace endpoints.")
    add_common_args(parser)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    private_query = "Check invoice and contract files in Personal/Documents without sending raw private data to cloud"
    router = http_post_json(args.base_url, "/api/router/explain", {"query": private_query, "session_id": "stage8_demo3"}, timeout=args.timeout)
    token = http_post_json(args.base_url, "/api/token-budget/explain", {"query": private_query, "task_type": "document_qa", "private_markers": ["invoice", "contract"], "session_id": "stage8_demo3"}, timeout=args.timeout)
    privacy = http_post_json(args.base_url, "/api/privacy-tokenizer/debug", {"text": private_query, "session_id": "stage8_demo3"}, timeout=args.timeout)
    assistant = http_post_json(args.base_url, "/api/assistant/chat", {"query": private_query, "entrypoint": "assistant_chat", "session_id": "stage8_demo3"}, timeout=args.timeout)
    router_payload = router.get("payload") or {}
    route_decision = router_payload.get("route_decision") if isinstance(router_payload.get("route_decision"), dict) else {}
    encoded_payloads = json.dumps({"router": router, "token": token, "privacy": privacy, "assistant": assistant}, ensure_ascii=False)
    checks = [
        check("router explain ok", router.get("ok") is True and router_payload.get("ok") is True, router),
        check("router touched Qwen", router_payload.get("qwen_touched") is True, router_payload),
        check("router did not fail Qwen", route_decision.get("qwen_router_failed") is not True, route_decision),
        check("private route not cloud", route_decision.get("route") != "cloud" or route_decision.get("guardrail_applied") is True, route_decision),
        check("router trace id present", bool(router_payload.get("trace_id")), router_payload.get("trace_id")),
        check("token budget explain ok", token.get("ok") is True and (token.get("payload") or {}).get("ok") is True, token),
        check("token budget avoids private cloud call", (token.get("payload") or {}).get("cloud_call_avoided") is True, token.get("payload")),
        check("privacy tokenizer ok", privacy.get("ok") is True and (privacy.get("payload") or {}).get("ok") is True, privacy),
        check("privacy tokenizer found spans", int((privacy.get("payload") or {}).get("redaction_count") or 0) >= 1, privacy.get("payload")),
        check("assistant chat trace ok", assistant.get("ok") is True and (assistant.get("payload") or {}).get("ok") is True, assistant),
        check("assistant trace id present", bool((assistant.get("payload") or {}).get("trace_id")), assistant.get("payload")),
        check("router does not expose raw qwen content preview", "raw_content_preview" not in route_decision, route_decision),
        check("relative private path redacted", "Personal/Documents" not in encoded_payloads, "redacted"),
        check("no raw absolute path in demo3 payloads", not has_raw_path({"router": router, "token": token, "privacy": privacy, "assistant": assistant}), "redacted"),
    ]
    payload = gate_payload("ok_stage8_demo3_qwen_router_trace_gate", "blocked_stage8_demo3_qwen_router_trace_gate", checks, {"router": router, "token_budget": token, "privacy": privacy, "assistant": assistant})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
