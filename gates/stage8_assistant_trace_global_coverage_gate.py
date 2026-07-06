from __future__ import annotations

import argparse

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload, has_raw_path

from src.assistant_trace.recorder import STANDARD_STEPS
from src.assistant_trace.routes import assistant_trace_route_response


NAME = "stage8_assistant_trace_global_coverage_gate"
ENTRYPOINTS = [
    "assistant_chat",
    "copilot_chat",
    "router_explain",
    "token_budget_explain",
    "privacy_tokenizer_debug",
    "auto_organizer_plan",
    "auto_organizer_execute",
    "product_status",
    "ai_space_search",
    "subtitle_extract",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate assistant trace records all product entrypoints.")
    add_common_args(parser)
    args = parser.parse_args()
    traces = {}
    checks = []
    for entrypoint in ENTRYPOINTS:
        _code, trace = assistant_trace_route_response(
            "/api/assistant/trace/record-entrypoint",
            method="POST",
            payload={"entrypoint": entrypoint, "query": f"stage8 trace coverage {entrypoint}", "session_id": "stage8_trace_gate"},
            report_root=args.report_root,
            personal_root=args.personal_root,
        )
        traces[entrypoint] = trace
        step_names = [step.get("step_name") for step in trace.get("steps") or []]
        checks.extend(
            [
                check(f"{entrypoint} trace ok", trace.get("ok") is True, trace.get("error")),
                check(f"{entrypoint} all standard steps", set(STANDARD_STEPS).issubset(set(step_names)), step_names),
                check(f"{entrypoint} no hidden CoT saved", trace.get("hidden_chain_of_thought_saved") is False, trace.get("hidden_chain_of_thought_saved")),
                check(f"{entrypoint} no raw path returned", trace.get("raw_path_returned") is False and not has_raw_path(trace), "redacted"),
            ]
        )
    _code, status = assistant_trace_route_response("/api/assistant/trace/status", report_root=args.report_root, personal_root=args.personal_root)
    checks.append(check("trace status ok", status.get("ok") is True, status))
    checks.append(check("status exposes required steps", set(STANDARD_STEPS).issubset(set(status.get("required_steps") or [])), status.get("required_steps")))
    payload = gate_payload("ok_stage8_assistant_trace_global_coverage_gate", "blocked_stage8_assistant_trace_global_coverage_gate", checks, {"trace_status": status, "traces": traces})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
