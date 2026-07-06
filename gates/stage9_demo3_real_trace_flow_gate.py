from __future__ import annotations

import argparse
import os

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload, has_raw_path, http_get_json, http_post_json

from src.assistant_trace.recorder import STANDARD_STEPS


NAME = "stage9_demo3_real_trace_flow_gate"
QUERIES = {
    "local_media": "列出最近上传的照片",
    "private_docs": "总结我的家庭发票和合同里涉及金额的内容",
    "public_complex": "不要引用本地文件，只根据公开信息比较高端 AI NAS 的发展趋势",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Demo3 real Qwen router/privacy/token/tool trace flow.")
    add_common_args(parser)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    session_id = "stage9_demo3_real_trace"
    runs = {}
    checks = []
    for key, query in QUERIES.items():
        response = http_post_json(args.base_url, "/api/assistant/chat", {"query": query, "session_id": session_id}, timeout=args.timeout)
        payload = response.get("payload") or {}
        trace_id = payload.get("trace_id")
        trace = http_get_json(args.base_url, f"/api/assistant/trace/{trace_id}", timeout=args.timeout) if trace_id else {"ok": False, "payload": {}}
        trace_payload = trace.get("payload") or {}
        step_names = [step.get("step_name") for step in trace_payload.get("steps") or []]
        step_payloads = {step.get("step_name"): step.get("payload") or {} for step in trace_payload.get("steps") or []}
        runs[key] = {"query": query, "assistant": response, "trace": trace}
        checks.extend(
            [
                check(f"{key} assistant ok", response.get("ok") is True and payload.get("ok") is True, payload.get("error")),
                check(f"{key} trace id present", bool(trace_id), trace_id),
                check(f"{key} trace fetch ok", trace.get("ok") is True and trace_payload.get("ok") is True, trace_payload.get("error")),
                check(f"{key} all required steps", set(STANDARD_STEPS).issubset(set(step_names)), step_names),
                check(f"{key} trace uses real execution context", all((step_payloads.get(step) or {}).get("payload_source") == "real_execution_context" for step in STANDARD_STEPS if step != "received"), step_payloads),
                check(f"{key} no hidden CoT", trace_payload.get("hidden_chain_of_thought_saved") is False and payload.get("hidden_chain_of_thought_saved") is False, payload),
                check(f"{key} no raw path", not has_raw_path({"assistant": payload, "trace": trace_payload}), "redacted"),
            ]
        )
    a = (runs["local_media"]["assistant"].get("payload") or {})
    b = (runs["private_docs"]["assistant"].get("payload") or {})
    c = (runs["public_complex"]["assistant"].get("payload") or {})
    checks.extend(
        [
            check("query A touched qwen", a.get("qwen_touched") is True, a),
            check("query A task type media_search", a.get("task_type") == "media_search", a.get("task_type")),
            check("query A simple local route", a.get("task_complexity") == "simple" and a.get("route") in {"local_only", "private_local_only"}, a),
            check("query A no cloud", a.get("cloud_used") is False, a.get("cloud_used")),
            check("query A local media tool", a.get("tool_execution") == "local_media_search", a.get("tool_execution")),
            check("query B privacy spans", {"invoice", "contract", "amount", "private_nas_context"}.issubset(set(b.get("privacy_spans") or [])), b.get("privacy_spans")),
            check("query B high privacy", b.get("privacy_level") == "high", b.get("privacy_level")),
            check("query B private local only", b.get("route") == "private_local_only", b.get("route")),
            check("query B cloud disallowed", b.get("cloud_allowed") is False and b.get("cloud_used") is False, b),
            check("query B no private cloud egress", b.get("raw_private_cloud_egress") is False, b.get("raw_private_cloud_egress")),
            check("query C no privacy", c.get("privacy_level") == "none" and not c.get("privacy_spans"), c),
            check("query C complex", c.get("task_complexity") == "complex", c.get("task_complexity")),
            check("query C cloud allowed redacted", c.get("route") == "cloud_allowed_redacted", c.get("route")),
            check("query C redaction applied", c.get("redaction_applied") is True, c.get("redaction_applied")),
            check("query C token fields present", isinstance(c.get("before_tokens"), int) and isinstance(c.get("after_tokens"), int) and isinstance(c.get("reduction_ratio"), (float, int)), c),
            check("query C no private cloud payload", c.get("cloud_payload_contains_private_context") is False, c.get("cloud_payload_contains_private_context")),
            check("query C cloud stub declared when no real cloud", (c.get("real_cloud_call") is True) or (c.get("cloud_stub") is True), {"cloud_stub": c.get("cloud_stub"), "real_cloud_call": c.get("real_cloud_call")}),
        ]
    )
    payload = gate_payload(
        "ok_stage9_demo3_real_trace_flow_gate",
        "blocked_stage9_demo3_real_trace_flow_gate",
        checks,
        {
            "base_url": args.base_url,
            "session_id": session_id,
            "cloud_stub_expected_without_AI_NAS_CLOUD_CHAT_URL": not bool(os.environ.get("AI_NAS_CLOUD_CHAT_URL")),
            "runs": runs,
        },
    )
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
