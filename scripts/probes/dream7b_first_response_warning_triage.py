#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_first_response_warning_triage"
DEFAULT_SNAPSHOT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_OUT_JSON = DEFAULT_SNAPSHOT_ROOT / "dream7b_first_response_warning_triage_latest.json"
DEFAULT_OUT_MD = DEFAULT_SNAPSHOT_ROOT / "dream7b_first_response_warning_triage_latest.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_json(root: Path, pattern: str) -> Path:
    paths = sorted(root.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not paths:
        raise FileNotFoundError(f"no report matched {pattern} under {root}")
    return paths[-1]


def get(payload: dict[str, Any], path: list[str], default: Any = None) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    return default if value is None else value


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def case_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case.get("id")): case for case in payload.get("cases") or []}


def candidate_meta(case: dict[str, Any]) -> dict[str, Any]:
    return case.get("dream7b_candidate") or (case.get("response") or {}).get(
        "dream7b_candidate"
    ) or {}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    first_response_path = args.first_response_json or latest_json(
        args.snapshot_root,
        "dream7b_first_response_packet_*/dream7b_first_response_packet.json",
    )
    routing_path = args.routing_json or latest_json(
        args.snapshot_root,
        "dream7b_first_response_routing_packet_*/dream7b_first_response_routing_packet.json",
    )
    fast_status_path = args.fast_status_json or latest_json(
        args.snapshot_root,
        "dream7b_first_response_fast_status_packet_*/dream7b_first_response_fast_status_packet.json",
    )
    fast_path_regression_path = args.fast_path_regression_json or latest_json(
        args.snapshot_root,
        "dream7b_fast_path_regression_*/dream7b_fast_path_regression.json",
    )
    slo_tier_guard_path = (
        args.slo_tier_guard_json
        or args.snapshot_root / "dream7b_first_response_slo_tier_guard_latest.json"
    )

    first_response = read_json(first_response_path)
    routing = read_json(routing_path)
    fast_status = read_json(fast_status_path)
    fast_path_regression = read_json(fast_path_regression_path)
    slo_tier_guard = read_json(slo_tier_guard_path)

    first_summary = first_response.get("summary") or {}
    first_decision = first_response.get("decision") or {}
    routing_summary = routing.get("summary") or {}
    routing_decision = routing.get("decision") or {}
    fast_decision = fast_status.get("decision") or {}
    slo_decision = slo_tier_guard.get("decision") or {}
    slo_tiers = slo_tier_guard.get("tiers") or {}
    slo_audit = slo_tier_guard.get("audit") or {}
    regression_cases = case_map(fast_path_regression)

    quick_ready = regression_cases.get("quick_ready") or {}
    identity_short = regression_cases.get("identity_short") or {}
    chinese_short = regression_cases.get("chinese_short") or {}
    fast_case_rows = []
    for case_id, case in [
        ("quick_ready", quick_ready),
        ("identity_short", identity_short),
        ("chinese_short", chinese_short),
    ]:
        meta = candidate_meta(case)
        fast_case_rows.append(
            {
                "id": case_id,
                "ok": case.get("ok"),
                "first_content_ms": case.get("first_content_ms"),
                "ttft_ms": case.get("ttft_ms"),
                "execution_path": meta.get("execution_path"),
                "backend_invoked": meta.get("backend_invoked"),
            }
        )

    first_content_p50_ms = as_float(first_summary.get("first_content_p50_ms"))
    first_content_p95_ms = as_float(first_summary.get("first_content_p95_ms"))
    first_progress_p50_ms = as_float(first_summary.get("first_progress_p50_ms"))
    quickpath_p50_ms = as_float(routing_summary.get("quickpath_first_content_p50_ms"))
    explicit_p50_ms = as_float(routing_summary.get("explicit_first_content_p50_ms"))
    quickpath_delta_ms = (
        round(quickpath_p50_ms - explicit_p50_ms, 3)
        if quickpath_p50_ms is not None and explicit_p50_ms is not None
        else None
    )

    checks = {
        "source_warning_is_expected_content_latency": first_response.get("verdict")
        == "warning_dream7b_first_response_packet_content_latency"
        and first_decision.get("first_content_latency_needs_work") is True
        and "interactive_first_content_p50_above_5000ms"
        in (first_summary.get("warnings") or []),
        "slo_tier_guard_ok": slo_tier_guard.get("verdict")
        == "ok_dream7b_first_response_slo_tier_guard"
        and not (slo_tier_guard.get("failed_checks") or []),
        "fast_path_first_content_ready": slo_decision.get(
            "fast_paths_satisfy_interactive_first_content_slo"
        )
        is True
        and all(row["backend_invoked"] is False for row in fast_case_rows)
        and get(slo_tiers, ["fast_path_first_content", "ready"]) is True,
        "sse_progress_ready": slo_decision.get(
            "sse_progress_satisfies_interactive_progress_slo"
        )
        is True
        and first_progress_p50_ms is not None
        and first_progress_p50_ms <= args.progress_slo_ms,
        "backend_content_tracked_separately": slo_decision.get(
            "backend_first_content_latency_is_not_true_batch_work"
        )
        is True
        and get(slo_tiers, ["backend_first_content", "tracked_separately"]) is True,
        "routing_fast_path_covers_warning_cases": routing.get("verdict")
        == "ok_dream7b_first_response_routing_packet"
        and routing_decision.get("quick_ready_improved_when_quickpath_enabled") is True
        and quickpath_p50_ms is not None
        and quickpath_p50_ms <= args.fast_content_slo_ms,
        "fast_status_ready": fast_status.get("verdict")
        == "ok_dream7b_first_response_fast_status_packet"
        and fast_decision.get("localized_status_fast_path_ready") is True
        and fast_decision.get("identity_fast_path_still_ready") is True,
        "no_runtime_or_compile_started": slo_audit.get("runtime_started") is False
        and slo_audit.get("compile_started") is False,
    }
    failed_checks = [key for key, value in checks.items() if not value]
    verdict = (
        "ok_dream7b_first_response_warning_triage"
        if not failed_checks
        else "warning_dream7b_first_response_warning_triage"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_paths": {
            "first_response_packet": str(first_response_path),
            "first_response_routing_packet": str(routing_path),
            "first_response_fast_status_packet": str(fast_status_path),
            "fast_path_regression": str(fast_path_regression_path),
            "first_response_slo_tier_guard": str(slo_tier_guard_path),
        },
        "thresholds": {
            "fast_content_slo_ms": args.fast_content_slo_ms,
            "progress_slo_ms": args.progress_slo_ms,
            "backend_content_warning_ms": args.backend_content_warning_ms,
        },
        "summary": {
            "source_warning_verdict": first_response.get("verdict"),
            "source_warning_count": len(first_summary.get("warnings") or []),
            "first_content_p50_ms": first_content_p50_ms,
            "first_content_p95_ms": first_content_p95_ms,
            "first_progress_p50_ms": first_progress_p50_ms,
            "explicit_first_content_p50_ms": explicit_p50_ms,
            "quickpath_first_content_p50_ms": quickpath_p50_ms,
            "quickpath_delta_ms": quickpath_delta_ms,
            "fast_path_max_first_content_ms": get(
                slo_tiers, ["fast_path_first_content", "max_first_content_ms"]
            ),
            "backend_first_content_tracked_separately": get(
                slo_tiers, ["backend_first_content", "tracked_separately"]
            ),
            "backend_first_content_latency_is_not_true_batch_work": slo_decision.get(
                "backend_first_content_latency_is_not_true_batch_work"
            ),
            "fast_case_rows": fast_case_rows,
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "decision": {
            "warning_is_product_triaged": not failed_checks,
            "queue_batch_service_remains_default": slo_decision.get(
                "queue_batch_service_remains_default"
            )
            is True,
            "do_not_promote_true_batch_for_first_response": slo_decision.get(
                "do_not_promote_true_batch_for_first_response"
            )
            is True,
            "continue_tracking_backend_content_latency": True,
            "recommended_next": (
                "keep fast-path and SSE-progress guardrails; treat backend first-content "
                "latency as a separate product latency backlog, not a B=4 true-batch promotion gate"
            ),
        },
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "remote_write_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown first-response warning triage only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B First-Response Warning Triage",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- failed_checks: `{payload['failed_checks']}`",
        f"- source_warning_verdict: `{summary['source_warning_verdict']}`",
        f"- source_warning_count: `{summary['source_warning_count']}`",
        f"- first_content_p50_ms: `{summary['first_content_p50_ms']}`",
        f"- first_content_p95_ms: `{summary['first_content_p95_ms']}`",
        f"- first_progress_p50_ms: `{summary['first_progress_p50_ms']}`",
        f"- explicit_first_content_p50_ms: `{summary['explicit_first_content_p50_ms']}`",
        f"- quickpath_first_content_p50_ms: `{summary['quickpath_first_content_p50_ms']}`",
        f"- quickpath_delta_ms: `{summary['quickpath_delta_ms']}`",
        f"- fast_path_max_first_content_ms: `{summary['fast_path_max_first_content_ms']}`",
        f"- backend_first_content_tracked_separately: `{summary['backend_first_content_tracked_separately']}`",
        f"- backend_first_content_latency_is_not_true_batch_work: `{summary['backend_first_content_latency_is_not_true_batch_work']}`",
        f"- warning_is_product_triaged: `{decision['warning_is_product_triaged']}`",
        f"- queue_batch_service_remains_default: `{decision['queue_batch_service_remains_default']}`",
        f"- do_not_promote_true_batch_for_first_response: `{decision['do_not_promote_true_batch_for_first_response']}`",
        "",
        "## Fast Path Cases",
        "",
        "| id | execution_path | backend_invoked | first_content_ms |",
        "| --- | --- | --- | ---: |",
    ]
    for row in summary["fast_case_rows"]:
        lines.append(
            f"| {row['id']} | {row['execution_path']} | {row['backend_invoked']} | {row['first_content_ms']} |"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Triage the legacy Dream7B first-response content-latency warning."
    )
    parser.add_argument("--snapshot-root", type=Path, default=DEFAULT_SNAPSHOT_ROOT)
    parser.add_argument("--first-response-json", type=Path)
    parser.add_argument("--routing-json", type=Path)
    parser.add_argument("--fast-status-json", type=Path)
    parser.add_argument("--fast-path-regression-json", type=Path)
    parser.add_argument("--slo-tier-guard-json", type=Path)
    parser.add_argument("--fast-content-slo-ms", type=float, default=100.0)
    parser.add_argument("--progress-slo-ms", type=float, default=500.0)
    parser.add_argument("--backend-content-warning-ms", type=float, default=5000.0)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
