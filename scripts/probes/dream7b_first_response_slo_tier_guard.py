#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_first_response_slo_tier_guard"
DEFAULT_OUT_JSON = Path(
    "tmp/product_guardrail_snapshots/dream7b_first_response_slo_tier_guard_latest.json"
)
DEFAULT_OUT_MD = Path(
    "tmp/product_guardrail_snapshots/dream7b_first_response_slo_tier_guard_latest.md"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_json(root: Path, pattern: str) -> Path:
    paths = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime)
    if not paths:
        raise FileNotFoundError(f"no report matched {pattern} under {root}")
    return paths[-1]


def case_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case.get("id")): case for case in payload.get("cases") or []}


def candidate_meta(case: dict[str, Any]) -> dict[str, Any]:
    return case.get("dream7b_candidate") or (case.get("response") or {}).get("dream7b_candidate") or {}


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def max_case_metric(cases: dict[str, dict[str, Any]], metric: str) -> float | None:
    values = [as_float(case.get(metric)) for case in cases.values()]
    numbers = [value for value in values if value is not None]
    return max(numbers) if numbers else None


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    first_response_path = args.first_response_json or latest_json(
        args.snapshot_root, "dream7b_first_response_packet_*/dream7b_first_response_packet.json"
    )
    routing_path = args.routing_json or latest_json(
        args.snapshot_root, "dream7b_first_response_routing_packet_*/dream7b_first_response_routing_packet.json"
    )
    fast_status_path = args.fast_status_json or latest_json(
        args.snapshot_root, "dream7b_first_response_fast_status_packet_*/dream7b_first_response_fast_status_packet.json"
    )
    regression_path = args.fast_path_regression_json or latest_json(
        args.snapshot_root, "dream7b_fast_path_regression_*/dream7b_fast_path_regression.json"
    )

    first_response = read_json(first_response_path)
    routing = read_json(routing_path)
    fast_status = read_json(fast_status_path)
    regression = read_json(regression_path)
    first_summary = first_response.get("summary") or {}
    first_decision = first_response.get("decision") or {}
    routing_summary = routing.get("summary") or {}
    routing_decision = routing.get("decision") or {}
    fast_decision = fast_status.get("decision") or {}
    regression_cases = case_map(regression)

    expected_paths = {
        "quick_ready": "gateway_fast_ready",
        "identity_short": "gateway_fast_identity",
        "chinese_short": "gateway_fast_local_status",
    }
    fast_rows = []
    for case_id, expected_path in expected_paths.items():
        case = regression_cases.get(case_id) or {}
        meta = candidate_meta(case)
        fast_rows.append(
            {
                "id": case_id,
                "ok": case.get("ok"),
                "first_content_ms": case.get("first_content_ms"),
                "ttft_ms": case.get("ttft_ms"),
                "execution_path": meta.get("execution_path"),
                "backend_invoked": meta.get("backend_invoked"),
                "expected_execution_path": expected_path,
                "within_fast_content_slo": (
                    as_float(case.get("first_content_ms")) is not None
                    and float(case.get("first_content_ms")) <= args.fast_content_slo_ms
                ),
            }
        )

    fast_path_ready = (
        regression.get("verdict") == "ok_dream7b_fast_path_regression"
        and all(row["ok"] is True for row in fast_rows)
        and all(row["execution_path"] == row["expected_execution_path"] for row in fast_rows)
        and all(row["backend_invoked"] is False for row in fast_rows)
        and all(row["within_fast_content_slo"] is True for row in fast_rows)
    )
    progress_ready = (
        first_decision.get("first_response_events_ready") is True
        and first_decision.get("sse_progress_ready") is True
        and as_float(first_summary.get("first_progress_p50_ms")) is not None
        and float(first_summary.get("first_progress_p50_ms")) <= args.progress_slo_ms
    )
    backend_content_tracked_separately = (
        first_decision.get("first_content_latency_needs_work") is True
        and routing.get("verdict") == "ok_dream7b_first_response_routing_packet"
        and routing_decision.get("recommended_next")
        == "fast-ready, identity, and local-status prompts are now covered by gateway fast paths; keep SSE progress for general backend generation and continue tracking first-content latency separately"
    )
    queue_default_preserved = (
        fast_decision.get("queue_batch_service_remains_default") is True
        and (regression.get("service") or {}).get("queue_service_active_enabled") is True
        and (regression.get("service") or {}).get("gateway_service_active_enabled") is True
    )
    checks = {
        "fast_path_ready": fast_path_ready,
        "progress_ready": progress_ready,
        "backend_content_tracked_separately": backend_content_tracked_separately,
        "queue_default_preserved": queue_default_preserved,
        "localized_status_fast_path_ready": fast_decision.get(
            "localized_status_fast_path_ready"
        )
        is True,
        "identity_fast_path_ready": fast_decision.get("identity_fast_path_still_ready")
        is True,
        "quickpath_improves_explicit_requests": routing_decision.get(
            "quick_ready_improved_when_quickpath_enabled"
        )
        is True,
    }
    failed_checks = [key for key, value in checks.items() if not value]
    verdict = (
        "ok_dream7b_first_response_slo_tier_guard"
        if not failed_checks
        else "warning_dream7b_first_response_slo_tier_guard"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_paths": {
            "first_response_packet": str(first_response_path),
            "first_response_routing_packet": str(routing_path),
            "first_response_fast_status_packet": str(fast_status_path),
            "fast_path_regression": str(regression_path),
        },
        "thresholds": {
            "fast_content_slo_ms": args.fast_content_slo_ms,
            "progress_slo_ms": args.progress_slo_ms,
            "backend_content_warning_ms": args.backend_content_warning_ms,
        },
        "tiers": {
            "health": {
                "ready": (regression.get("preflight") or {}).get("model_id_confirmed")
                is True
                and (regression.get("service") or {}).get("queue_service_active_enabled")
                is True
                and (regression.get("service") or {}).get("gateway_service_active_enabled")
                is True,
                "health_latency_ms": (regression.get("preflight") or {}).get(
                    "health_latency_ms"
                ),
                "models_latency_ms": (regression.get("preflight") or {}).get(
                    "models_latency_ms"
                ),
            },
            "fast_path_first_content": {
                "ready": fast_path_ready,
                "max_first_content_ms": max_case_metric(regression_cases, "first_content_ms"),
                "case_count": len(fast_rows),
                "cases": fast_rows,
            },
            "sse_progress": {
                "ready": progress_ready,
                "first_progress_p50_ms": first_summary.get("first_progress_p50_ms"),
                "first_progress_p95_ms": first_summary.get("first_progress_p95_ms"),
                "progress_event_total_count": first_summary.get(
                    "progress_event_total_count"
                ),
            },
            "backend_first_content": {
                "tracked_separately": backend_content_tracked_separately,
                "first_content_latency_needs_work": first_decision.get(
                    "first_content_latency_needs_work"
                ),
                "explicit_first_content_p50_ms": routing_summary.get(
                    "explicit_first_content_p50_ms"
                ),
                "quickpath_first_content_p50_ms": routing_summary.get(
                    "quickpath_first_content_p50_ms"
                ),
                "recommended_next": routing_decision.get("recommended_next"),
            },
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "decision": {
            "queue_batch_service_remains_default": queue_default_preserved,
            "fast_paths_satisfy_interactive_first_content_slo": fast_path_ready,
            "sse_progress_satisfies_interactive_progress_slo": progress_ready,
            "backend_first_content_latency_is_not_true_batch_work": True,
            "do_not_promote_true_batch_for_first_response": True,
            "recommended_next": "keep fast-path and SSE progress guardrails; track backend first-content latency separately from B=4 true-batch research",
        },
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "remote_write_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown first-response SLO tier guard only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    tiers = payload["tiers"]
    lines = [
        "# Dream7B First-Response SLO Tier Guard",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- failed_checks: `{payload['failed_checks']}`",
        f"- queue_batch_service_remains_default: `{payload['decision']['queue_batch_service_remains_default']}`",
        f"- fast_paths_satisfy_interactive_first_content_slo: `{payload['decision']['fast_paths_satisfy_interactive_first_content_slo']}`",
        f"- sse_progress_satisfies_interactive_progress_slo: `{payload['decision']['sse_progress_satisfies_interactive_progress_slo']}`",
        f"- backend_first_content_latency_is_not_true_batch_work: `{payload['decision']['backend_first_content_latency_is_not_true_batch_work']}`",
        "",
        "## Tiers",
        "",
        f"- health_ready: `{tiers['health']['ready']}`",
        f"- fast_path_ready: `{tiers['fast_path_first_content']['ready']}`",
        f"- fast_path_max_first_content_ms: `{tiers['fast_path_first_content']['max_first_content_ms']}`",
        f"- sse_progress_ready: `{tiers['sse_progress']['ready']}`",
        f"- sse_first_progress_p50_ms: `{tiers['sse_progress']['first_progress_p50_ms']}`",
        f"- backend_first_content_tracked_separately: `{tiers['backend_first_content']['tracked_separately']}`",
        f"- explicit_first_content_p50_ms: `{tiers['backend_first_content']['explicit_first_content_p50_ms']}`",
        f"- quickpath_first_content_p50_ms: `{tiers['backend_first_content']['quickpath_first_content_p50_ms']}`",
        "",
        "## Fast Path Cases",
        "",
        "| id | path | backend | first_content_ms | within_slo |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in tiers["fast_path_first_content"]["cases"]:
        lines.append(
            f"| {row['id']} | {row['execution_path']} | {row['backend_invoked']} | "
            f"{row['first_content_ms']} | {row['within_fast_content_slo']} |"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Separate Dream7B fast first-response SLOs from backend first-content latency."
    )
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--first-response-json", type=Path)
    parser.add_argument("--routing-json", type=Path)
    parser.add_argument("--fast-status-json", type=Path)
    parser.add_argument("--fast-path-regression-json", type=Path)
    parser.add_argument("--fast-content-slo-ms", type=float, default=100.0)
    parser.add_argument("--progress-slo-ms", type=float, default=500.0)
    parser.add_argument("--backend-content-warning-ms", type=float, default=5000.0)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
