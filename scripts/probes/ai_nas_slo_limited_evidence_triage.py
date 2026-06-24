#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "ai_nas_slo_limited_evidence_triage"
DEFAULT_SNAPSHOT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_OUT_JSON = DEFAULT_SNAPSHOT_ROOT / "ai_nas_slo_limited_evidence_triage_latest.json"
DEFAULT_OUT_MD = DEFAULT_SNAPSHOT_ROOT / "ai_nas_slo_limited_evidence_triage_latest.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_json(root: Path, pattern: str) -> Path:
    paths = sorted(root.rglob(pattern), key=lambda path: path.stat().st_mtime)
    if not paths:
        raise FileNotFoundError(f"no report matched {pattern} under {root}")
    return paths[-1]


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    slo_path = args.slo_json or latest_json(
        args.snapshot_root,
        "operational_slo_rollup_contract_*/operational_slo_rollup_contract.json",
    )
    product_path = args.product_json or latest_json(
        args.snapshot_root,
        "dream7b_product_decision_packet_*/dream7b_product_decision_packet.json",
    )
    freshness_path = (
        args.freshness_json
        or args.snapshot_root / "dream7b_default_service_freshness_gate_latest.json"
    )

    slo = read_json(slo_path)
    contracts = {contract.get("key"): contract for contract in slo.get("contracts") or []}
    concurrency_contract = contracts.get("concurrency_stability") or {}
    concurrency_report_path = args.concurrency_json or Path(
        (concurrency_contract.get("report") or {}).get("path") or ""
    )
    concurrency = read_json(concurrency_report_path)
    product = read_json(product_path)
    freshness = read_json(freshness_path)

    slo_summary = slo.get("summary") or {}
    concurrency_summary = concurrency.get("summary") or {}
    dialog_health = concurrency_summary.get("dialog_health") or {}
    error_taxonomy = concurrency_summary.get("error_taxonomy") or {}
    product_decision = product.get("decision") or {}
    product_evidence = product.get("product_evidence") or {}
    freshness_decision = freshness.get("decision") or {}
    freshness_checks = freshness.get("checks") or {}
    warnings = slo_summary.get("warnings") or []

    checks = {
        "slo_rollup_ok": slo.get("verdict") == "ok_ai_nas_operational_slo_rollup_contract",
        "all_required_slo_contracts_accepted": as_int(
            slo_summary.get("required_accepted_count")
        )
        == as_int(slo_summary.get("required_contract_count"))
        and as_int(slo_summary.get("required_contract_count")) > 0,
        "no_required_slo_blockers": as_int(slo_summary.get("blocker_count")) == 0,
        "only_limited_warning_is_concurrency_stability": warnings
        == ["concurrency_stability:limited_production_evidence"],
        "concurrency_contract_observational_limited_accepted": concurrency_contract.get(
            "required"
        )
        is False
        and concurrency_contract.get("accepted") is True
        and concurrency_contract.get("limited") is True
        and concurrency_contract.get("warnings")
        == ["concurrency_stability:limited_production_evidence"],
        "concurrency_report_has_no_failed_jobs": concurrency.get("verdict")
        == "limited_ai_nas_concurrency_stability"
        and as_int(concurrency_summary.get("failure_count")) == 0,
        "limited_reason_is_dialog_health_fixture": as_int(dialog_health.get("error_count"))
        > 0
        and as_int(dialog_health.get("ok_count")) == 0
        and as_int(error_taxonomy.get("dialog_health_URLError")) > 0,
        "product_packet_ok": product.get("verdict") == "ok_dream7b_product_decision_packet",
        "freshness_gate_ok": freshness.get("verdict")
        == "ok_dream7b_default_service_freshness_gate"
        and not (freshness.get("failed_checks") or []),
        "queue_batch_default_preserved": product_decision.get("production_default")
        == "queue_batch"
        and product_decision.get("queue_should_remain_default") is True
        and freshness_decision.get("queue_batch_service_remains_default") is True,
        "true_batch_not_promoted": product_decision.get("true_batch_b4_status")
        == "research_artifact_not_promoted"
        and freshness_decision.get("do_not_promote_true_batch") is True,
        "service_runtime_compile_not_started": product_evidence.get(
            "first_response_warning_backend_not_true_batch_work"
        )
        is True
        and freshness_checks.get("runtime_command_guard_starts_no_runtime") is True
        and freshness_checks.get("compile_command_guard_starts_no_compile") is True,
    }
    failed_checks = [key for key, value in checks.items() if not value]
    verdict = (
        "ok_ai_nas_slo_limited_evidence_triage"
        if not failed_checks
        else "warning_ai_nas_slo_limited_evidence_triage"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_paths": {
            "operational_slo_rollup": str(slo_path),
            "concurrency_stability": str(concurrency_report_path),
            "product_decision_packet": str(product_path),
            "default_service_freshness_gate": str(freshness_path),
        },
        "summary": {
            "slo_warning_count": slo_summary.get("warning_count"),
            "slo_limited_evidence_count": slo_summary.get("limited_evidence_count"),
            "slo_required_accepted_count": slo_summary.get("required_accepted_count"),
            "slo_required_contract_count": slo_summary.get("required_contract_count"),
            "slo_warnings": warnings,
            "concurrency_required": concurrency_contract.get("required"),
            "concurrency_accepted": concurrency_contract.get("accepted"),
            "concurrency_limited": concurrency_contract.get("limited"),
            "concurrency_verdict": concurrency.get("verdict"),
            "concurrency_failure_count": concurrency_summary.get("failure_count"),
            "concurrency_throughput_jobs_per_s": concurrency_summary.get(
                "throughput_jobs_per_s"
            ),
            "concurrency_all_task_p95_ms": (
                concurrency_summary.get("all_task_latency") or {}
            ).get("p95_ms"),
            "dialog_health_ok_count": dialog_health.get("ok_count"),
            "dialog_health_error_count": dialog_health.get("error_count"),
            "dialog_health_error_taxonomy": error_taxonomy,
            "product_verdict": product.get("verdict"),
            "freshness_verdict": freshness.get("verdict"),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "decision": {
            "limited_evidence_triaged": not failed_checks,
            "release_blocker": False if not failed_checks else True,
            "queue_batch_service_remains_default": freshness_decision.get(
                "queue_batch_service_remains_default"
            )
            is True,
            "do_not_promote_true_batch": freshness_decision.get(
                "do_not_promote_true_batch"
            )
            is True,
            "continue_collecting_production_mixed_concurrency": True,
            "recommended_next": (
                "keep queue-batch default; collect a fresh production mixed-concurrency "
                "run for the observational concurrency_stability contract"
            ),
        },
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "remote_write_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown SLO limited-evidence triage only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# AI-NAS SLO Limited-Evidence Triage",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- failed_checks: `{payload['failed_checks']}`",
        f"- slo_warning_count: `{summary['slo_warning_count']}`",
        f"- slo_limited_evidence_count: `{summary['slo_limited_evidence_count']}`",
        f"- slo_warnings: `{summary['slo_warnings']}`",
        f"- concurrency_required: `{summary['concurrency_required']}`",
        f"- concurrency_accepted: `{summary['concurrency_accepted']}`",
        f"- concurrency_limited: `{summary['concurrency_limited']}`",
        f"- concurrency_verdict: `{summary['concurrency_verdict']}`",
        f"- concurrency_failure_count: `{summary['concurrency_failure_count']}`",
        f"- dialog_health_ok_count: `{summary['dialog_health_ok_count']}`",
        f"- dialog_health_error_count: `{summary['dialog_health_error_count']}`",
        f"- limited_evidence_triaged: `{decision['limited_evidence_triaged']}`",
        f"- release_blocker: `{decision['release_blocker']}`",
        f"- queue_batch_service_remains_default: `{decision['queue_batch_service_remains_default']}`",
        f"- do_not_promote_true_batch: `{decision['do_not_promote_true_batch']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Triage limited/observational SLO evidence without starting services."
    )
    parser.add_argument("--snapshot-root", type=Path, default=DEFAULT_SNAPSHOT_ROOT)
    parser.add_argument("--slo-json", type=Path)
    parser.add_argument("--concurrency-json", type=Path)
    parser.add_argument("--product-json", type=Path)
    parser.add_argument("--freshness-json", type=Path)
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
