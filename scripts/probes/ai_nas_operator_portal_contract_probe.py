#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_nas_appliance_experience_acceptance_probe import (
    DEFAULT_COLLECTION,
    QUERY,
    build_case_packet,
    build_manifest,
    prepare_fixture,
    user_facing_results,
)
from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_operator_approval_inbox_probe import make_manifest, summarize_manifest


TOOL_ID = "ai_nas_operator_portal_contract"


def h(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def parse_report_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path) or {}
    generated_at = parse_report_time(payload.get("generated_at"))
    generated_ts = generated_at.timestamp() if generated_at else 0.0
    try:
        mtime_ts = path.stat().st_mtime
    except OSError:
        mtime_ts = 0.0
    return generated_ts, mtime_ts, str(path)


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [report_root]
    tmp_root = Path("tmp")
    if tmp_root.exists():
        roots.append(tmp_root)
    return roots


def latest_report(evidence_roots: list[Path], filename: str) -> dict:
    candidates = []
    for root in evidence_roots:
        if not root.exists():
            continue
        try:
            candidates.extend(path for path in root.rglob(filename) if path.is_file())
        except OSError:
            continue
    if not candidates:
        return {
            "found": False,
            "filename": filename,
            "path": None,
            "verdict": None,
            "generated_at": None,
            "selection_policy": "generated_at_then_mtime",
            "payload": None,
        }
    selected = max(candidates, key=report_sort_key)
    payload = read_json(selected)
    return {
        "found": payload is not None,
        "filename": filename,
        "path": str(selected),
        "verdict": payload.get("verdict") if payload else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "selection_policy": "generated_at_then_mtime",
        "payload": payload,
    }


def build_inbox_rows(run_dir: Path, case_manifest: dict) -> list[dict]:
    manifests = [
        case_manifest,
        make_manifest("apm-portal-needsreview", "awaiting_human_confirmation", 1, complete=False),
        make_manifest("apm-portal-approved", "approved_for_execution", 1, complete=True),
    ]
    rows = []
    inbox_dir = run_dir / "portal_inbox_manifests"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    for payload in manifests:
        path = inbox_dir / f"{payload['manifest_id']}.json"
        safe_write_json(path, payload)
        row, _issues = summarize_manifest(path, payload)
        rows.append(row)
    return rows


def render_portal(
    query: str,
    result_rows: list[dict],
    payment_nodes: list[dict],
    suggestions: list[dict],
    approval_manifest: dict,
    inbox_rows: list[dict],
    audit: dict,
    report_json_path: Path,
    readiness_report: dict,
    slo_report: dict,
    traceability_report: dict,
    dependency_report: dict,
    runbook_report: dict,
    soak_watcher_report: dict,
    dream7b_report: dict,
    dream7b_product_report: dict,
    dream7b_fast_path_report: dict,
    dream7b_guardrail_report: dict,
    dream7b_freshness_report: dict,
) -> str:
    ready_count = sum(1 for row in inbox_rows if row.get("risk_level") == "ready_for_operator_review")
    needs_repair_count = sum(1 for row in inbox_rows if row.get("risk_level") == "needs_manifest_repair")
    rows_html = []
    for row in result_rows:
        evidence = "".join(f"<li>{h(item)}</li>" for item in row.get("evidence_snippets", [])[:3])
        reasons = "".join(f"<li>{h(item)}</li>" for item in row.get("why_matched", [])[:6])
        amounts = ", ".join(row.get("amounts") or [])
        dates = ", ".join(row.get("dates") or [])
        rows_html.append(
            f"""
            <article class="result-card" data-testid="result-card">
              <header>
                <h3>{h(row.get('relative_path'))}</h3>
                <span class="confidence">confidence {h(row.get('confidence'))}</span>
              </header>
              <p class="path">{h(row.get('original_path'))}</p>
              <p>{h(row.get('summary'))}</p>
              <dl>
                <dt>Amounts</dt><dd>{h(amounts)}</dd>
                <dt>Dates</dt><dd>{h(dates)}</dd>
              </dl>
              <section><h4>Evidence</h4><ul>{evidence}</ul></section>
              <section><h4>Why Matched</h4><ul>{reasons}</ul></section>
            </article>
            """
        )
    payments_html = "".join(
        f"<tr><td>{h(node.get('date'))}</td><td>{h(node.get('amount'))}</td><td>{h(node.get('relative_path'))}</td></tr>"
        for node in payment_nodes
    )
    suggestions_html = "".join(
        f"<li><code>{h(item.get('source_relative_path'))}</code> -> <code>{h(item.get('suggested_target_relative_path'))}</code></li>"
        for item in suggestions
    )
    inbox_html = "".join(
        f"""
        <tr data-testid="approval-row">
          <td>{h(row.get('manifest_id'))}</td>
          <td>{h(row.get('status'))}</td>
          <td>{h(row.get('risk_level'))}</td>
          <td>{h(row.get('action_count'))}</td>
          <td>
            <code>{h(row.get('approval_phrase'))}</code>
            <div class="row-actions">
              <button type="button" data-manifest="{h(row.get('manifest_id'))}" data-decision="approve" data-phrase="{h(row.get('approval_phrase'))}">Approve</button>
              <button type="button" data-manifest="{h(row.get('manifest_id'))}" data-decision="rollback_draft" data-phrase="ROLLBACK {h(row.get('manifest_id'))}">Rollback draft</button>
              <button type="button" data-manifest="{h(row.get('manifest_id'))}" data-decision="reject" data-phrase="REJECT {h(row.get('manifest_id'))}">Reject</button>
              <button type="button" data-manifest="{h(row.get('manifest_id'))}" data-decision="needs_review" data-phrase="NEEDS_REVIEW {h(row.get('manifest_id'))}">Needs review</button>
            </div>
          </td>
        </tr>
        """
        for row in inbox_rows
    )
    blocked_actions = ", ".join(sorted({kind for item in approval_manifest.get("blocked_destructive_actions", []) for kind in [item.get("action_type")] if kind}))
    readiness_payload = readiness_report.get("payload") or {}
    readiness_summary = readiness_payload.get("summary") or {}
    readiness_blockers = readiness_payload.get("blockers") or []
    readiness_warnings = readiness_payload.get("warnings") or []
    slo_payload = slo_report.get("payload") or {}
    slo_summary = slo_payload.get("summary") or {}
    slo_scorecard = slo_payload.get("scorecard") or {}
    traceability_payload = traceability_report.get("payload") or {}
    traceability_summary = traceability_payload.get("summary") or {}
    traceability_matrix = traceability_payload.get("traceability_matrix") or []
    limited_rows = [row for row in traceability_matrix if row.get("status") == "limited_evidence"]
    missing_rows = [row for row in traceability_matrix if row.get("status") == "missing_or_failed_evidence"]
    other_nonready_rows = [
        row
        for row in traceability_matrix
        if row.get("status") not in {"satisfied", "limited_evidence", "missing_or_failed_evidence"}
    ]
    satisfied_rows = [row for row in traceability_matrix if row.get("status") == "satisfied"]
    visible_traceability_rows = limited_rows + missing_rows + other_nonready_rows
    if not visible_traceability_rows:
        visible_traceability_rows = satisfied_rows
    pinned_traceability_ids = {"document_rag_ocr", "production_blockers_explicit"}
    pinned_traceability_rows = [row for row in traceability_matrix if row.get("id") in pinned_traceability_ids]
    visible_traceability_rows = pinned_traceability_rows + [
        row for row in visible_traceability_rows if row.get("id") not in pinned_traceability_ids
    ]
    traceability_rows_html = "".join(
        f"<tr><td>{h(row.get('id'))}</td><td>{h(row.get('area'))}</td><td>{h(row.get('status'))}</td><td>{h(', '.join(row.get('limited_reports') or row.get('missing_reports') or []))}</td></tr>"
        for row in visible_traceability_rows[:12]
    )
    dependency_payload = dependency_report.get("payload") or {}
    dependency_summary = dependency_payload.get("summary") or {}
    dependencies = dependency_payload.get("dependencies") or []
    dependency_rows_html = "".join(
        f"<tr><td>{h(item.get('id'))}</td><td>{h(item.get('ready'))}</td><td>{h(', '.join(item.get('blockers') or []))}</td></tr>"
        for item in dependencies[:8]
    )
    runbook_payload = runbook_report.get("payload") or {}
    runbook_summary = runbook_payload.get("summary") or {}
    runbook_items = runbook_payload.get("runbook_items") or []
    runbook_rows_html = "".join(
        f"""
        <tr data-testid="runbook-row">
          <td>{h(item.get('id'))}</td>
          <td>{h(item.get('owner_category'))}</td>
          <td>{h(', '.join(item.get('covers_blockers') or []))}</td>
          <td>{h(', '.join(item.get('verification_commands') or []))}</td>
        </tr>
        """
        for item in runbook_items[:8]
    )
    soak_watcher_payload = soak_watcher_report.get("payload") or {}
    soak_latest = soak_watcher_payload.get("latest_soak") or {}
    soak_summary = soak_latest.get("summary") or {}
    soak_status = soak_watcher_payload.get("status") or soak_watcher_report.get("verdict") or "missing"
    soak_process = soak_watcher_payload.get("soak_process") or (soak_watcher_payload.get("summary") or {}).get("final_soak_process") or {}
    soak_fresh_after_min_mtime = soak_latest.get("fresh_after_min_mtime")
    dream7b_payload = dream7b_report.get("payload") or {}
    dream7b_summary = dream7b_payload.get("summary") or {}
    dream7b_cases = dream7b_payload.get("cases") or []
    dream7b_case = dream7b_cases[0] if dream7b_cases else {}
    dream7b_meta = (dream7b_case.get("response") or {}).get("dream7b_candidate") or {}
    dream7b_product_payload = dream7b_product_report.get("payload") or {}
    dream7b_product_decision = dream7b_product_payload.get("decision") or {}
    dream7b_first_response = dream7b_product_payload.get("first_response") or {}
    dream7b_first_response_slo = (
        dream7b_product_payload.get("first_response_slo_tier_guard") or {}
    )
    dream7b_first_response_warning_triage = (
        dream7b_product_payload.get("first_response_warning_triage") or {}
    )
    dream7b_slo_limited_evidence_triage = (
        dream7b_product_payload.get("slo_limited_evidence_triage") or {}
    )
    dream7b_product_evidence = dream7b_product_payload.get("product_evidence") or {}
    dream7b_runtime_gate = dream7b_product_payload.get("runtime_experiment_gate") or {}
    dream7b_runtime_command_guard = dream7b_product_payload.get("runtime_command_guard") or {}
    dream7b_compile_command_guard = dream7b_product_payload.get("compile_command_guard") or {}
    dream7b_next_action_pack = dream7b_product_payload.get("next_action_admission_pack") or {}
    dream7b_segment_drag = dream7b_product_payload.get("segment_drag_breakdown") or {}
    dream7b_segment_stability = dream7b_product_payload.get("segment_stability_audit") or {}
    dream7b_group_order = dream7b_product_payload.get("group_order_candidates") or {}
    dream7b_group_partition = dream7b_product_payload.get("group_partition_planner") or {}
    dream7b_group_inner_order_value = (
        dream7b_product_payload.get("group_inner_order_value_audit") or {}
    )
    dream7b_segment_group_schedule = (
        dream7b_product_payload.get("segment_group_schedule_scorecard") or {}
    )
    dream7b_group_switch = dream7b_product_payload.get("group_switch_accounting") or {}
    dream7b_scheduler = dream7b_product_payload.get("scheduler_overhead_budget") or {}
    dream7b_instrumentation = dream7b_product_payload.get("runtime_instrumentation") or {}
    dream7b_hbm_accounting = (
        dream7b_product_payload.get("hbm_load_accounting_contract") or {}
    )
    dream7b_bottleneck_closure = (
        dream7b_product_payload.get("bottleneck_closure_model") or {}
    )
    dream7b_post_instrumentation = (
        dream7b_product_payload.get("post_instrumentation_telemetry_gate") or {}
    )
    dream7b_post_overhead = (
        dream7b_product_payload.get("post_instrumentation_overhead_analysis") or {}
    )
    dream7b_post_segment = (
        dream7b_product_payload.get("post_instrumentation_segment_attribution") or {}
    )
    dream7b_hidden_buffer = (
        dream7b_product_payload.get("hidden_buffer_reuse_decision") or {}
    )
    dream7b_queue_health = dream7b_product_payload.get("queue_health_snapshot") or {}
    dream7b_workstream_overlap = dream7b_product_payload.get("workstream_overlap_audit") or {}
    dream7b_tuning_matrix = dream7b_product_payload.get("tuning_decision_matrix") or {}
    dream7b_final_logits_leverage = (
        dream7b_product_payload.get("final_logits_leverage_model") or {}
    )
    dream7b_last_token = dream7b_product_payload.get("last_token_candidate") or {}
    dream7b_last_token_gate = dream7b_product_payload.get("last_token_experiment_gate") or {}
    dream7b_last_token_validation_plan = (
        dream7b_product_payload.get("last_token_runtime_validation_plan") or {}
    )
    dream7b_last_token_validation_compare = (
        dream7b_product_payload.get("last_token_validation_compare") or {}
    )
    dream7b_compile_capacity = dream7b_product_payload.get("compile_capacity") or {}
    dream7b_nas_inventory = dream7b_product_payload.get("true_batch_nas_inventory") or {}
    dream7b_refactor_backlog = dream7b_product_payload.get("runtime_refactor_backlog") or {}
    dream7b_refactor_source = dream7b_product_payload.get("runtime_refactor_source_contract") or {}
    dream7b_refactor_admission = (
        dream7b_product_payload.get("runtime_refactor_admission_contract") or {}
    )
    dream7b_runtime_source_map = (
        dream7b_product_payload.get("runtime_source_implementation_map") or {}
    )
    dream7b_checks = dream7b_product_payload.get("checks") or {}
    dream7b_fast_payload = dream7b_fast_path_report.get("payload") or {}
    dream7b_fast_cases = {str(case.get("id")): case for case in dream7b_fast_payload.get("cases") or []}
    quick_ready_case = dream7b_fast_cases.get("quick_ready") or {}
    localized_status_case = dream7b_fast_cases.get("chinese_short") or {}
    quick_ready_meta = quick_ready_case.get("dream7b_candidate") or {}
    localized_status_meta = localized_status_case.get("dream7b_candidate") or {}
    dream7b_guardrail_payload = dream7b_guardrail_report.get("payload") or {}
    dream7b_guardrail = dream7b_guardrail_payload.get("guardrail") or {}
    dream7b_status_contract = dream7b_guardrail_payload.get("default_status_contract") or {}
    dream7b_rollback_contract = dream7b_guardrail_payload.get("default_rollback_contract") or {}
    dream7b_freshness_payload = dream7b_freshness_report.get("payload") or {}
    dream7b_freshness_decision = dream7b_freshness_payload.get("decision") or {}
    dream7b_freshness_checks = dream7b_freshness_payload.get("checks") or {}
    dream7b_freshness_summary = dream7b_freshness_payload.get("packet_summary") or {}
    dream7b_freshness = dream7b_freshness_payload.get("freshness") or {}
    partial_batch_flush_ready = dream7b_product_evidence.get(
        "queue_partial_batch_flush_ready"
    )
    if partial_batch_flush_ready is None:
        partial_batch_flush_ready = dream7b_freshness_checks.get(
            "queue_partial_batch_flush_ready"
        )
    partial_batch_flush_live_summary_ready = dream7b_product_evidence.get(
        "queue_partial_batch_flush_live_summary_ready"
    )
    if partial_batch_flush_live_summary_ready is None:
        partial_batch_flush_live_summary_ready = dream7b_freshness_summary.get(
            "queue_partial_batch_flush_live_summary_ready"
        )
    partial_batch_flush_probe_ready = dream7b_product_evidence.get(
        "queue_partial_batch_flush_probe_ready"
    )
    if partial_batch_flush_probe_ready is None:
        partial_batch_flush_probe_ready = dream7b_freshness_checks.get(
            "queue_partial_batch_flush_probe_ready"
        )
    partial_batch_flush_health_ready = dream7b_product_evidence.get(
        "queue_partial_batch_flush_health_snapshot_ready"
    )
    if partial_batch_flush_health_ready is None:
        partial_batch_flush_health_ready = dream7b_freshness_checks.get(
            "queue_partial_batch_flush_health_snapshot_ready"
        )
    partial_batch_flush_probe_or_health_ready = (
        partial_batch_flush_probe_ready is True or partial_batch_flush_health_ready is True
    )
    partial_batch_flush_source = dream7b_product_evidence.get(
        "queue_partial_batch_flush_readiness_source"
    ) or dream7b_freshness_summary.get("queue_partial_batch_flush_readiness_source")
    partial_batch_probe_run_dir = dream7b_product_evidence.get(
        "queue_partial_batch_probe_run_dir"
    ) or dream7b_freshness_summary.get("queue_partial_batch_probe_run_dir")
    partial_batch_probe_ms_per_request = dream7b_product_evidence.get(
        "queue_partial_batch_probe_ms_per_request"
    ) or dream7b_freshness_summary.get("queue_partial_batch_probe_ms_per_request")
    per_run_evidence_matrix_verdict = dream7b_product_evidence.get(
        "per_run_evidence_matrix_verdict"
    ) or dream7b_freshness_summary.get("per_run_evidence_matrix_verdict")
    per_run_evidence_matrix_run_count = dream7b_product_evidence.get(
        "per_run_evidence_matrix_run_count"
    ) or dream7b_freshness_summary.get("per_run_evidence_matrix_run_count")
    per_run_evidence_matrix_successful_run_count = dream7b_product_evidence.get(
        "per_run_evidence_matrix_successful_run_count"
    ) or dream7b_freshness_summary.get("per_run_evidence_matrix_successful_run_count")
    per_run_evidence_matrix_failed_run_count = dream7b_product_evidence.get(
        "per_run_evidence_matrix_failed_run_count"
    ) or dream7b_freshness_summary.get("per_run_evidence_matrix_failed_run_count")
    per_run_evidence_matrix_top_segment = dream7b_product_evidence.get(
        "per_run_evidence_matrix_top_segment"
    ) or dream7b_freshness_summary.get("per_run_evidence_matrix_top_segment")
    per_run_evidence_matrix_top_segment_rate = dream7b_product_evidence.get(
        "per_run_evidence_matrix_top_segment_rate"
    ) or dream7b_freshness_summary.get("per_run_evidence_matrix_top_segment_rate")
    per_run_evidence_matrix_standard_sweep_status = dream7b_product_evidence.get(
        "per_run_evidence_matrix_standard_sweep_status"
    ) or dream7b_freshness_summary.get("per_run_evidence_matrix_standard_sweep_status")
    status_script = dream7b_status_contract.get("script") or {}
    rollback_script = dream7b_rollback_contract.get("script") or {}
    command_rows_html = "".join(
        f"<tr><td>{h(label)}</td><td><code>{h(command)}</code></td></tr>"
        for label, command in [
            ("Seed controlled Personal corpus", "ai_nas_controlled_personal_seed --execute"),
            ("Run NAS-backed long soak", "ai_nas_nas_backed_long_soak --duration-seconds 21600 --min-duration-seconds 21600"),
            ("Refresh production gate", "ai_nas_production_readiness_gate"),
            ("Check Dream7B identity", "dream7b_perf_identity --max-tokens 16"),
        ]
    )
    readiness_status = "ready" if readiness_payload.get("production_ready") else "limited"
    approval_phrase = approval_manifest.get("approval", {}).get("approval_phrase")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI-NAS Operator Portal Contract</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; background: #f4f6f4; color: #18212a; scroll-behavior: smooth; }}
    body {{ margin: 0; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px; }}
    header.portal-header {{ display: grid; gap: 14px; margin-bottom: 20px; }}
    h1 {{ font-size: 30px; margin: 0; letter-spacing: 0; }}
    h2 {{ font-size: 19px; margin: 0 0 12px; }}
    h3 {{ font-size: 16px; margin: 0; }}
    h4 {{ font-size: 13px; margin: 14px 0 6px; }}
    .topline {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; align-items: end; }}
    .query {{ padding: 13px 15px; border: 1px solid #c6ccc4; background: #fff; }}
    nav.quick-actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    nav.quick-actions a, .copy-token {{ border: 1px solid #aab4ac; background: #ffffff; color: #17251f; padding: 8px 10px; text-decoration: none; font-size: 13px; border-radius: 6px; transition: background 180ms ease, transform 180ms ease; }}
    nav.quick-actions a:hover {{ background: #edf3ee; transform: translateY(-1px); }}
    nav.quick-actions a:focus-visible {{ outline: 3px solid #7ba588; outline-offset: 2px; }}
    button {{ border: 1px solid #9da8a1; background: #fff; color: #18212a; border-radius: 6px; padding: 7px 9px; cursor: pointer; }}
    button:hover {{ background: #eef4ef; }}
    .row-actions {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }}
    .metric {{ background: #fff; border: 1px solid #d5ddd6; padding: 12px; border-radius: 6px; }}
    .metric b {{ display: block; font-size: 20px; font-variant-numeric: tabular-nums; }}
    .metric span {{ display: block; color: #5f6f67; font-size: 12px; margin-top: 4px; }}
    .status {{ display: inline-block; padding: 3px 7px; border-radius: 4px; background: #e9efe9; color: #244c35; font-weight: 700; font-size: 12px; }}
    .status.limited {{ background: #f4e9d5; color: #714c12; }}
    .section {{ background: #fff; border: 1px solid #d5ddd6; border-radius: 6px; padding: 16px; margin: 14px 0; }}
    .command-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }}
    .results {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    .result-card {{ border: 1px solid #d1d8d2; padding: 12px; border-radius: 6px; }}
    .result-card header {{ display: flex; justify-content: space-between; gap: 10px; align-items: start; }}
    .confidence {{ white-space: nowrap; font-size: 12px; color: #315f49; }}
    .path {{ color: #59636e; font-size: 12px; overflow-wrap: anywhere; }}
    dl {{ display: grid; grid-template-columns: 72px 1fr; gap: 6px; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ text-align: left; border-bottom: 1px solid #e5e7eb; padding: 8px; vertical-align: top; }}
    code {{ overflow-wrap: anywhere; }}
    .audit-ok {{ color: #315f49; font-weight: 700; }}
    @media (max-width: 860px) {{ main {{ padding: 16px; }} .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .command-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<main>
  <header class="portal-header">
    <div class="topline">
      <h1>AI-NAS Operator Portal</h1>
      <nav class="quick-actions" aria-label="Operator actions">
        <a href="#results">Related Files</a>
        <a href="#approval">Approval Queue</a>
        <a href="#production-readiness">Production Readiness</a>
        <a href="#soak-watcher">Soak Watcher</a>
        <a href="#dream7b-interaction">Dream7B</a>
        <a href="#commands">Run Commands</a>
        <a href="#report">One-Click Report</a>
      </nav>
    </div>
    <div class="query" data-testid="query">Query: {h(query)}</div>
  </header>
  <section class="metrics" aria-label="Portal metrics">
    <div class="metric"><b>{len(result_rows)}</b><span>Related files</span></div>
    <div class="metric"><b>{len(payment_nodes)}</b><span>Payment nodes</span></div>
    <div class="metric"><b>{len(suggestions)}</b><span>Copy suggestions</span></div>
    <div class="metric"><b>{ready_count}/{needs_repair_count}</b><span>Ready / repair approvals</span></div>
    <div class="metric"><b><span class="status {h(readiness_status)}">{h(readiness_status)}</span></b><span>Production gate</span></div>
  </section>
  <section class="section" data-testid="commands" id="commands"><h2>Run Commands</h2>
    <div class="command-grid">
      <table><thead><tr><th>Action</th><th>Allowlisted command</th></tr></thead><tbody>{command_rows_html}</tbody></table>
      <div>
        <p>Approval phrase</p>
        <p><code class="copy-token">{h(approval_phrase)}</code></p>
        <p>Report JSON <code>{h(report_json_path)}</code></p>
      </div>
    </div>
  </section>
  <section class="section" data-testid="results" id="results"><h2>Related Files</h2><div class="results">{''.join(rows_html)}</div></section>
  <section class="section" data-testid="production-readiness" id="production-readiness"><h2>Production Readiness</h2>
    <table><tbody>
      <tr><th>Report</th><td><code>{h(readiness_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Verdict</th><td>{h(readiness_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>Production ready</th><td>{h(readiness_summary.get('production_ready'))}</td></tr>
      <tr><th>Categories</th><td>{h(readiness_summary.get('ready_category_count'))}/{h(readiness_summary.get('category_count'))} ready</td></tr>
      <tr><th>Blockers</th><td>{h(readiness_summary.get('blocker_count'))}</td></tr>
      <tr><th>Warnings</th><td>{h(readiness_summary.get('warning_count'))}</td></tr>
    </tbody></table>
    <ul>{''.join(f'<li>{h(item)}</li>' for item in readiness_blockers[:12])}</ul>
  </section>
  <section class="section" data-testid="soak-watcher" id="soak-watcher"><h2>Long Soak / Gate Watcher</h2>
    <table><tbody>
      <tr><th>Status report</th><td><code>{h(soak_watcher_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Status</th><td>{h(soak_status)}</td></tr>
      <tr><th>PID</th><td>{h(soak_watcher_payload.get('pid'))}</td></tr>
      <tr><th>PID running</th><td>{h(soak_watcher_payload.get('pid_running'))}</td></tr>
      <tr><th>Soak elapsed</th><td>{h(soak_process.get('elapsed_seconds'))} s / {h(soak_process.get('target_seconds'))} s</td></tr>
      <tr><th>Soak progress</th><td>{h(soak_process.get('progress_percent'))}%</td></tr>
      <tr><th>Estimated remaining</th><td>{h(soak_process.get('remaining_seconds'))} s</td></tr>
      <tr><th>Estimated completion</th><td>{h(soak_process.get('estimated_completion_at'))}</td></tr>
      <tr><th>Wait elapsed seconds</th><td>{h(soak_watcher_payload.get('elapsed_wait_seconds') or (soak_watcher_payload.get('summary') or {}).get('wait_elapsed_seconds'))}</td></tr>
      <tr><th>Latest soak report</th><td><code>{h(soak_watcher_payload.get('latest_soak_report') or soak_latest.get('path') or 'not found')}</code></td></tr>
      <tr><th>Latest soak precheck</th><td>{h(soak_watcher_payload.get('latest_soak_meets_precheck') if 'latest_soak_meets_precheck' in soak_watcher_payload else soak_latest.get('meets_precheck'))}</td></tr>
      <tr><th>Fresh report</th><td>{h(soak_fresh_after_min_mtime)}</td></tr>
      <tr><th>NAS backed</th><td>{h(soak_summary.get('nas_backed'))}</td></tr>
      <tr><th>Final file count</th><td>{h(soak_summary.get('final_file_count'))}</td></tr>
      <tr><th>Gate report</th><td><code>{h(soak_watcher_payload.get('gate_report') or (soak_watcher_payload.get('summary') or {}).get('latest_gate_report') or 'pending')}</code></td></tr>
      <tr><th>Runbook report</th><td><code>{h(soak_watcher_payload.get('runbook_report') or (soak_watcher_payload.get('summary') or {}).get('latest_runbook_report') or 'pending')}</code></td></tr>
    </tbody></table>
  </section>
  <section class="section" data-testid="dream7b-interaction" id="dream7b-interaction"><h2>Dream7B Interaction</h2>
    <table><tbody>
      <tr><th>Report</th><td><code>{h(dream7b_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Verdict</th><td>{h(dream7b_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>Content</th><td>{h(dream7b_case.get('content'))}</td></tr>
      <tr><th>TTFT p50 ms</th><td>{h((dream7b_summary.get('ttft_ms') or {}).get('p50_ms'))}</td></tr>
      <tr><th>First progress p50 ms</th><td>{h((dream7b_summary.get('first_progress_ms') or {}).get('p50_ms'))}</td></tr>
      <tr><th>Progress interval sec</th><td>{h((dream7b_summary.get('progress_interval_sec') or {}).get('p50'))}</td></tr>
      <tr><th>First content p50 ms</th><td>{h((dream7b_summary.get('first_content_ms') or {}).get('p50_ms'))}</td></tr>
      <tr><th>Stream-supported cases</th><td>{h(dream7b_summary.get('stream_supported_case_count'))}</td></tr>
      <tr><th>Progress-event cases</th><td>{h(dream7b_summary.get('progress_event_case_count'))}</td></tr>
      <tr><th>Total progress events</th><td>{h(dream7b_summary.get('progress_event_total_count'))}</td></tr>
      <tr><th>Streaming mode</th><td>{h(dream7b_meta.get('streaming_mode'))}</td></tr>
      <tr><th>Progress events</th><td>{h(dream7b_meta.get('streaming_progress_event_count'))}</td></tr>
      <tr><th>Backend invoked</th><td>{h(dream7b_meta.get('backend_invoked'))}</td></tr>
      <tr><th>Interaction gaps</th><td><code>{h(dream7b_summary.get('interaction_gaps'))}</code></td></tr>
    </tbody></table>
  </section>
  <section class="section" data-testid="dream7b-service-guardrails" id="dream7b-service-guardrails"><h2>Dream7B Service Guardrails</h2>
    <table><tbody>
      <tr><th>Product packet</th><td><code>{h(dream7b_product_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Product verdict</th><td>{h(dream7b_product_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>Production default</th><td>{h(dream7b_product_decision.get('production_default'))}</td></tr>
      <tr><th>Queue remains default</th><td>{h(dream7b_product_decision.get('queue_should_remain_default'))}</td></tr>
      <tr><th>runtime_experiment_gate</th><td>{h(dream7b_runtime_gate.get('verdict') or 'missing')}</td></tr>
      <tr><th>s100p_runtime_experiment_now</th><td>{h(dream7b_product_decision.get('s100p_runtime_experiment_now'))}</td></tr>
      <tr><th>allowed_s100p_runtime_experiments</th><td><code>{h(dream7b_product_decision.get('allowed_s100p_runtime_experiments') or [])}</code></td></tr>
      <tr><th>runtime_gate_blockers</th><td><code>{h(dream7b_runtime_gate.get('blockers') or [])}</code></td></tr>
      <tr><th>next_nonduplicate_runtime_candidate</th><td>{h(dream7b_runtime_gate.get('next_nonduplicate_runtime_candidate') or dream7b_product_decision.get('next_runtime_candidate'))}</td></tr>
      <tr><th>runtime_gate_admission_evidence_ready</th><td>{h(dream7b_runtime_gate.get('admission_evidence_ready'))}</td></tr>
      <tr><th>runtime_gate_final_logits_leverage_gate_ready</th><td>{h(dream7b_runtime_gate.get('final_logits_leverage_gate_ready'))}</td></tr>
      <tr><th>runtime_gate_runtime_refactor_gate_ready</th><td>{h(dream7b_runtime_gate.get('runtime_refactor_gate_ready'))}</td></tr>
      <tr><th>runtime_gate_tuning_matrix_gate_ready</th><td>{h(dream7b_runtime_gate.get('tuning_matrix_gate_ready'))}</td></tr>
      <tr><th>runtime_gate_admission_projected_saved_ms_per_request</th><td>{h(dream7b_runtime_gate.get('admission_projected_saved_ms_per_request'))}</td></tr>
      <tr><th>runtime_gate_admission_standard_sweeps_blocked</th><td>{h(dream7b_runtime_gate.get('admission_standard_sweeps_blocked'))}</td></tr>
      <tr><th>runtime_command_guard</th><td>{h(dream7b_runtime_command_guard.get('verdict') or 'missing')}</td></tr>
      <tr><th>runtime_command_guard_active</th><td>{h(dream7b_runtime_command_guard.get('command_guard_active'))}</td></tr>
      <tr><th>runtime_command_guard_standard_sweeps_blocked</th><td>{h(dream7b_runtime_command_guard.get('standard_sweep_commands_blocked'))}</td></tr>
      <tr><th>runtime_command_guard_command_admitted</th><td>{h(dream7b_runtime_command_guard.get('command_admitted'))}</td></tr>
      <tr><th>runtime_command_guard_would_start_runtime</th><td>{h(dream7b_runtime_command_guard.get('would_start_runtime'))}</td></tr>
      <tr><th>runtime_gate_post_segment_blocks_standard_group_sweeps</th><td>{h(dream7b_runtime_gate.get('post_segment_blocks_standard_group_sweeps'))}</td></tr>
      <tr><th>runtime_gate_post_segment_group_size_tuning_implication</th><td>{h(dream7b_runtime_gate.get('post_segment_group_size_tuning_implication'))}</td></tr>
      <tr><th>runtime_gate_post_segment_inner_order_tuning_implication</th><td>{h(dream7b_runtime_gate.get('post_segment_inner_order_tuning_implication'))}</td></tr>
      <tr><th>segment_stability_audit</th><td>{h(dream7b_segment_stability.get('verdict') or 'missing')}</td></tr>
      <tr><th>stable_primary_bottleneck</th><td>{h(dream7b_segment_stability.get('stable_primary_bottleneck'))}</td></tr>
      <tr><th>final_logits_rank1_rate</th><td>{h(dream7b_segment_stability.get('final_logits_rank1_rate'))}</td></tr>
      <tr><th>final_logits_cv_positive_excess</th><td>{h(dream7b_segment_stability.get('final_logits_cv_positive_excess'))}</td></tr>
      <tr><th>final_to_token_excess_ratio</th><td>{h(dream7b_segment_stability.get('final_to_token_excess_ratio'))}</td></tr>
      <tr><th>final_to_max_hidden_excess_ratio</th><td>{h(dream7b_segment_stability.get('final_to_max_hidden_excess_ratio'))}</td></tr>
      <tr><th>do_not_run_hidden_order_sweeps_now</th><td>{h(dream7b_segment_stability.get('do_not_run_hidden_order_sweeps_now'))}</td></tr>
      <tr><th>segment_drag_breakdown</th><td>{h(dream7b_segment_drag.get('verdict') or 'missing')}</td></tr>
      <tr><th>segment_drag_final_vs_hidden_mean_ratio</th><td>{h(dream7b_segment_drag.get('final_vs_hidden_mean_ratio'))}</td></tr>
      <tr><th>segment_drag_final_excess_ms_per_request</th><td>{h(dream7b_segment_drag.get('final_excess_ms_per_request_if_hidden_speed'))}</td></tr>
      <tr><th>segment_drag_token_excess_ms_per_request</th><td>{h(dream7b_segment_drag.get('token_excess_ms_per_request_if_hidden_speed'))}</td></tr>
      <tr><th>segment_drag_top_group_by_accounted_ms</th><td>{h(dream7b_segment_drag.get('top_group_by_accounted_ms'))}</td></tr>
      <tr><th>segment_drag_top_group_contains_final_logits</th><td>{h(dream7b_segment_drag.get('top_group_contains_final_logits'))}</td></tr>
      <tr><th>segment_drag_top_segments</th><td><code>{h(dream7b_segment_drag.get('top_segments_by_avg_run_ms') or [])}</code></td></tr>
      <tr><th>segment_group_schedule_scorecard</th><td>{h(dream7b_segment_group_schedule.get('verdict') or 'missing')}</td></tr>
      <tr><th>segment_group_primary_schedule_bottleneck</th><td>{h(dream7b_segment_group_schedule.get('primary_schedule_bottleneck'))}</td></tr>
      <tr><th>segment_group_primary_code_target</th><td>{h(dream7b_segment_group_schedule.get('primary_code_target'))}</td></tr>
      <tr><th>segment_group_preferred_group_policy</th><td>{h(dream7b_segment_group_schedule.get('preferred_group_policy'))}</td></tr>
      <tr><th>segment_group_preferred_inner_order</th><td>{h(dream7b_segment_group_schedule.get('preferred_inner_order'))}</td></tr>
      <tr><th>segment_group_run_more_standard_sweeps_now</th><td>{h(dream7b_segment_group_schedule.get('run_more_standard_b4_group_or_inner_order_sweeps_now'))}</td></tr>
      <tr><th>segment_group_run_s100p_runtime_now</th><td>{h(dream7b_segment_group_schedule.get('run_s100p_runtime_now'))}</td></tr>
      <tr><th>segment_group_start_compile_now</th><td>{h(dream7b_segment_group_schedule.get('start_compile_now'))}</td></tr>
      <tr><th>segment_group_compile_preflight_only_now</th><td>{h(dream7b_segment_group_schedule.get('compile_preflight_only_now'))}</td></tr>
      <tr><th>segment_group_final_excess_to_group_switch_gap_ratio</th><td>{h(dream7b_segment_group_schedule.get('final_excess_to_group_switch_gap_ratio'))}</td></tr>
      <tr><th>group_order_candidates</th><td>{h(dream7b_group_order.get('verdict') or 'missing')}</td></tr>
      <tr><th>group_order_baseline</th><td>{h(dream7b_group_order.get('baseline'))}</td></tr>
      <tr><th>group_order_segment_major_preferred</th><td>{h(dream7b_group_order.get('segment_major_preferred_over_microbatch_major'))}</td></tr>
      <tr><th>group_order_best_nonbaseline_variant</th><td>{h(dream7b_group_order.get('best_nonbaseline_observed_variant'))}</td></tr>
      <tr><th>group_order_best_nonbaseline_delta_ms_per_request</th><td>{h(dream7b_group_order.get('best_nonbaseline_observed_variant_delta_ms_per_request'))}</td></tr>
      <tr><th>group_order_no_variant_beats_baseline</th><td>{h(dream7b_group_order.get('no_observed_variant_beats_baseline'))}</td></tr>
      <tr><th>group_order_more_mb512_sweeps_deprioritized</th><td>{h(dream7b_group_order.get('more_mb512_group_boundary_sweeps_deprioritized'))}</td></tr>
      <tr><th>group_order_only_capacity_probe_if_needed</th><td>{h(dream7b_group_order.get('only_capacity_probe_if_needed'))}</td></tr>
      <tr><th>group_partition_planner</th><td>{h(dream7b_group_partition.get('verdict') or 'missing')}</td></tr>
      <tr><th>group_partition_candidate_count</th><td>{h(dream7b_group_partition.get('candidate_count'))}</td></tr>
      <tr><th>group_partition_run_new_partition_now</th><td>{h(dream7b_group_partition.get('run_new_partition_now'))}</td></tr>
      <tr><th>group_partition_only_probe_if_memory_plan_changes</th><td>{h(dream7b_group_partition.get('only_probe_if_memory_plan_changes'))}</td></tr>
      <tr><th>group_partition_top_capacity_probe_groups</th><td><code>{h(dream7b_group_partition.get('top_capacity_probe_groups') or [])}</code></td></tr>
      <tr><th>group_partition_top_capacity_probe_max_group_hbm_mib</th><td>{h(dream7b_group_partition.get('top_capacity_probe_max_group_hbm_mib'))}</td></tr>
      <tr><th>group_partition_top_capacity_probe_peak_delta_pct</th><td>{h(dream7b_group_partition.get('top_capacity_probe_peak_delta_pct'))}</td></tr>
      <tr><th>group_partition_best_observed_nonbaseline_delta_ms_per_request</th><td>{h(dream7b_group_partition.get('best_observed_nonbaseline_delta_ms_per_request'))}</td></tr>
      <tr><th>group_inner_order_value_audit</th><td>{h(dream7b_group_inner_order_value.get('verdict') or 'missing')}</td></tr>
      <tr><th>group_inner_order_run_more_sweeps_now</th><td>{h(dream7b_group_inner_order_value.get('run_more_group_size_or_inner_order_sweeps_now'))}</td></tr>
      <tr><th>group_inner_order_best_nonbaseline_delta_ms_per_request</th><td>{h(dream7b_group_inner_order_value.get('best_nonbaseline_delta_ms_per_request'))}</td></tr>
      <tr><th>group_inner_order_slower_or_equal_nonbaseline_count</th><td>{h(dream7b_group_inner_order_value.get('slower_or_equal_nonbaseline_count'))}</td></tr>
      <tr><th>group_inner_order_capacity_probe_only_candidate_count</th><td>{h(dream7b_group_inner_order_value.get('capacity_probe_only_candidate_count'))}</td></tr>
      <tr><th>group_inner_order_top_value_lever</th><td>{h(dream7b_group_inner_order_value.get('top_value_lever'))}</td></tr>
      <tr><th>group_switch_accounting</th><td>{h(dream7b_group_switch.get('verdict') or 'missing')}</td></tr>
      <tr><th>group_switch_gap_ms_per_request</th><td>{h(dream7b_group_switch.get('group_switch_gap_ms_per_request'))}</td></tr>
      <tr><th>group_release_ms_per_request</th><td>{h(dream7b_group_switch.get('group_release_ms_per_request'))}</td></tr>
      <tr><th>unaccounted_gap_ms_per_request</th><td>{h(dream7b_group_switch.get('unaccounted_gap_ms_per_request'))}</td></tr>
      <tr><th>latest_gap_intra_segment_run_gap_ms_per_request</th><td>{h(dream7b_group_switch.get('latest_gap_intra_segment_run_gap_ms_per_request'))}</td></tr>
      <tr><th>final_excess_to_switch_gap_ratio</th><td>{h(dream7b_group_switch.get('final_excess_to_switch_gap_ratio'))}</td></tr>
      <tr><th>group_release_and_unaccounted_gap_not_primary</th><td>{h(dream7b_group_switch.get('group_release_and_unaccounted_gap_not_primary'))}</td></tr>
      <tr><th>scheduler_overhead_budget</th><td>{h(dream7b_scheduler.get('verdict') or 'missing')}</td></tr>
      <tr><th>scheduler_primary_code_target</th><td>{h(dream7b_scheduler.get('primary_code_target'))}</td></tr>
      <tr><th>scheduler_final_excess_to_group_switch_gap</th><td>{h(dream7b_scheduler.get('final_excess_to_group_switch_gap'))}</td></tr>
      <tr><th>scheduler_final_excess_to_intra_segment_gap</th><td>{h(dream7b_scheduler.get('final_excess_to_intra_segment_gap'))}</td></tr>
      <tr><th>deprioritize_python_inter_segment_gap_tuning</th><td>{h(dream7b_scheduler.get('deprioritize_python_inter_segment_gap_tuning'))}</td></tr>
      <tr><th>runtime_instrumentation_contract</th><td>{h(dream7b_instrumentation.get('contract_verdict') or 'missing')}</td></tr>
      <tr><th>runtime_instrumentation_deployment</th><td>{h(dream7b_instrumentation.get('deployment_verdict') or 'missing')}</td></tr>
      <tr><th>runtime_instrumentation_new_fields</th><td><code>{h(dream7b_instrumentation.get('new_telemetry_fields') or [])}</code></td></tr>
      <tr><th>runtime_instrumentation_default_cli_changed</th><td>{h(dream7b_instrumentation.get('default_cli_changed'))}</td></tr>
      <tr><th>runtime_instrumentation_runtime_order_changed</th><td>{h(dream7b_instrumentation.get('runtime_order_changed'))}</td></tr>
      <tr><th>runtime_instrumentation_remote_probe_sha256</th><td><code>{h(dream7b_instrumentation.get('remote_probe_sha256'))}</code></td></tr>
      <tr><th>runtime_instrumentation_remote_backup</th><td><code>{h(dream7b_instrumentation.get('remote_backup'))}</code></td></tr>
      <tr><th>runtime_instrumentation_active_true_batch_python</th><td>{h(dream7b_instrumentation.get('active_true_batch_python'))}</td></tr>
      <tr><th>runtime_instrumentation_active_compile_true_batch</th><td>{h(dream7b_instrumentation.get('active_compile_true_batch'))}</td></tr>
      <tr><th>hbm_load_accounting_contract</th><td>{h(dream7b_hbm_accounting.get('verdict') or 'missing')}</td></tr>
      <tr><th>hbm_per_segment_load_accounting_ready</th><td>{h(dream7b_hbm_accounting.get('per_segment_load_accounting_ready'))}</td></tr>
      <tr><th>hbm_group_load_accounting_ready</th><td>{h(dream7b_hbm_accounting.get('group_load_accounting_ready'))}</td></tr>
      <tr><th>hbm_prewarm_accounting_ready</th><td>{h(dream7b_hbm_accounting.get('prewarm_accounting_ready'))}</td></tr>
      <tr><th>hbm_timing_summary_accounts_load_and_prewarm</th><td>{h(dream7b_hbm_accounting.get('timing_summary_accounts_load_and_prewarm'))}</td></tr>
      <tr><th>hbm_prewarm_hbm_default_changed</th><td>{h(dream7b_hbm_accounting.get('prewarm_hbm_default_changed'))}</td></tr>
      <tr><th>hbm_accounting_runtime_started</th><td>{h(dream7b_hbm_accounting.get('runtime_started'))}</td></tr>
      <tr><th>hbm_accounting_compile_started</th><td>{h(dream7b_hbm_accounting.get('compile_started'))}</td></tr>
      <tr><th>bottleneck_closure_model</th><td>{h(dream7b_bottleneck_closure.get('verdict') or 'missing')}</td></tr>
      <tr><th>bottleneck_closure_latest_avg_bpu_gap_to_queue_points</th><td>{h(dream7b_bottleneck_closure.get('latest_avg_bpu_gap_to_queue_points'))}</td></tr>
      <tr><th>bottleneck_closure_latest_nonzero_shortfall_points_for_93_avg</th><td>{h(dream7b_bottleneck_closure.get('latest_nonzero_shortfall_points_for_93_avg'))}</td></tr>
      <tr><th>bottleneck_closure_primary_next_code_target</th><td>{h(dream7b_bottleneck_closure.get('primary_next_code_target'))}</td></tr>
      <tr><th>bottleneck_closure_final_logits_projection_saved_ms_per_request</th><td>{h(dream7b_bottleneck_closure.get('final_logits_projection_saved_ms_per_request'))}</td></tr>
      <tr><th>bottleneck_closure_hbm_group_load_ms_per_request</th><td>{h(dream7b_bottleneck_closure.get('hbm_group_load_ms_per_request'))}</td></tr>
      <tr><th>bottleneck_closure_release_plus_unaccounted_gap_ms_per_request</th><td>{h(dream7b_bottleneck_closure.get('release_plus_unaccounted_group_gap_ms_per_request'))}</td></tr>
      <tr><th>bottleneck_closure_small_python_and_gap_optimizations_combined_ms_per_request</th><td>{h(dream7b_bottleneck_closure.get('small_python_and_gap_optimizations_combined_ms_per_request'))}</td></tr>
      <tr><th>bottleneck_closure_group_size_or_inner_order_current_primary_lever</th><td>{h(dream7b_bottleneck_closure.get('group_size_or_inner_order_current_primary_lever'))}</td></tr>
      <tr><th>bottleneck_closure_projection_is_not_bpu_promotion_proof</th><td>{h(dream7b_bottleneck_closure.get('projection_is_not_bpu_promotion_proof'))}</td></tr>
      <tr><th>bottleneck_closure_requires_real_runtime_result_before_promotion</th><td>{h(dream7b_bottleneck_closure.get('requires_real_runtime_result_before_promotion'))}</td></tr>
      <tr><th>post_instrumentation_telemetry_gate</th><td>{h(dream7b_post_instrumentation.get('verdict') or 'missing')}</td></tr>
      <tr><th>post_instrumentation_success_count</th><td>{h(dream7b_post_instrumentation.get('post_instrumentation_success_count'))}</td></tr>
      <tr><th>post_instrumentation_telemetry_ready</th><td>{h(dream7b_post_instrumentation.get('post_instrumentation_telemetry_ready'))}</td></tr>
      <tr><th>input_output_overhead_quantified</th><td>{h(dream7b_post_instrumentation.get('input_output_overhead_quantified'))}</td></tr>
      <tr><th>do_not_claim_input_output_overhead_yet</th><td>{h(dream7b_post_instrumentation.get('do_not_claim_input_output_overhead_yet'))}</td></tr>
      <tr><th>allow_one_post_instrumentation_baseline_measurement</th><td>{h(dream7b_post_instrumentation.get('allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available'))}</td></tr>
      <tr><th>post_instrumentation_next_measurement</th><td>{h(dream7b_post_instrumentation.get('next_measurement_purpose'))}</td></tr>
      <tr><th>post_instrumentation_overhead_analysis</th><td>{h(dream7b_post_overhead.get('verdict') or 'missing')}</td></tr>
      <tr><th>input_prepare_ms_per_request</th><td>{h(dream7b_post_overhead.get('input_prepare_ms_per_request'))}</td></tr>
      <tr><th>output_postprocess_ms_per_request</th><td>{h(dream7b_post_overhead.get('output_postprocess_ms_per_request'))}</td></tr>
      <tr><th>hidden_materialize_ms_per_request</th><td>{h(dream7b_post_overhead.get('hidden_materialize_ms_per_request'))}</td></tr>
      <tr><th>final_output_postprocess_ms_per_request</th><td>{h(dream7b_post_overhead.get('final_output_postprocess_ms_per_request'))}</td></tr>
      <tr><th>final_logits_compute_still_primary</th><td>{h(dream7b_post_overhead.get('final_logits_compute_still_primary'))}</td></tr>
      <tr><th>secondary_local_runtime_code_target</th><td>{h(dream7b_post_overhead.get('secondary_local_runtime_code_target'))}</td></tr>
      <tr><th>post_instrumentation_segment_attribution</th><td>{h(dream7b_post_segment.get('verdict') or 'missing')}</td></tr>
      <tr><th>post_segment_primary_single_segment_bottleneck</th><td>{h(dream7b_post_segment.get('primary_single_segment_bottleneck'))}</td></tr>
      <tr><th>post_segment_final_compute_excess_ms_per_request</th><td>{h(dream7b_post_segment.get('final_compute_excess_ms_per_request'))}</td></tr>
      <tr><th>post_segment_top_group_by_segment_total</th><td>{h(dream7b_post_segment.get('top_group_by_segment_total'))}</td></tr>
      <tr><th>post_segment_top_group_contains_final_logits</th><td>{h(dream7b_post_segment.get('top_group_contains_final_logits'))}</td></tr>
      <tr><th>post_segment_group_size_tuning_implication</th><td>{h(dream7b_post_segment.get('group_size_tuning_implication'))}</td></tr>
      <tr><th>post_segment_inner_order_tuning_implication</th><td>{h(dream7b_post_segment.get('inner_order_tuning_implication'))}</td></tr>
      <tr><th>hidden_buffer_reuse_decision</th><td>{h(dream7b_hidden_buffer.get('verdict') or 'missing')}</td></tr>
      <tr><th>hidden_buffer_reuse_default</th><td>{h(dream7b_hidden_buffer.get('hidden_buffer_reuse_default'))}</td></tr>
      <tr><th>preallocate_hidden_experimental_flag_only</th><td>{h(dream7b_hidden_buffer.get('preallocate_hidden_experimental_flag_only'))}</td></tr>
      <tr><th>prealloc_ms_per_request_delta</th><td>{h(dream7b_hidden_buffer.get('prealloc_ms_per_request_delta'))}</td></tr>
      <tr><th>prealloc_hidden_materialize_ms_per_request_delta</th><td>{h(dream7b_hidden_buffer.get('prealloc_hidden_materialize_ms_per_request_delta'))}</td></tr>
      <tr><th>prealloc_reused_hidden_buffer_count</th><td>{h(dream7b_hidden_buffer.get('prealloc_reused_hidden_buffer_count'))}</td></tr>
      <tr><th>reuse_buffer_implementation_measured_slower</th><td>{h(dream7b_hidden_buffer.get('reuse_buffer_implementation_measured_slower'))}</td></tr>
      <tr><th>last_token_candidate</th><td>{h(dream7b_last_token.get('compile_candidate'))}</td></tr>
      <tr><th>last_token_readiness_verdict</th><td>{h(dream7b_last_token.get('readiness_verdict'))}</td></tr>
      <tr><th>last_token_compile_ready</th><td>{h(dream7b_last_token.get('compile_ready'))}</td></tr>
      <tr><th>last_token_runtime_validation_ready</th><td>{h(dream7b_last_token.get('runtime_validation_ready'))}</td></tr>
      <tr><th>last_token_readiness_blockers</th><td><code>{h(dream7b_last_token.get('readiness_blockers') or [])}</code></td></tr>
      <tr><th>last_token_target_shape</th><td><code>{h(dream7b_last_token.get('candidate_target_shape'))}</code></td></tr>
      <tr><th>last_token_saved_ms_projection</th><td>{h(dream7b_last_token.get('projection_only_hypothesis_saved_ms_per_request'))}</td></tr>
      <tr><th>last_token_remote_manifest_verified</th><td>{h(dream7b_last_token.get('remote_last_token_manifest_verified'))}</td></tr>
      <tr><th>last_token_remote_hbm_exists</th><td>{h(dream7b_last_token.get('remote_last_token_hbm_exists'))}</td></tr>
      <tr><th>last_token_experiment_gate</th><td>{h(dream7b_last_token_gate.get('verdict') or 'missing')}</td></tr>
      <tr><th>last_token_gate_blockers</th><td><code>{h(dream7b_last_token_gate.get('gate_blockers') or [])}</code></td></tr>
      <tr><th>last_token_validation_plan</th><td>{h(dream7b_last_token_validation_plan.get('verdict') or 'missing')}</td></tr>
      <tr><th>last_token_validation_plan_generated_at</th><td>{h(dream7b_last_token_validation_plan.get('plan_generated_at'))}</td></tr>
      <tr><th>last_token_validation_ready</th><td>{h(dream7b_last_token_validation_plan.get('validation_ready'))}</td></tr>
      <tr><th>last_token_validation_blockers</th><td><code>{h(dream7b_last_token_validation_plan.get('blockers') or [])}</code></td></tr>
      <tr><th>last_token_validation_final_hbm_root_exists</th><td>{h(dream7b_last_token_validation_plan.get('final_hbm_root_exists'))}</td></tr>
      <tr><th>last_token_validation_hbm_exists</th><td>{h(dream7b_last_token_validation_plan.get('last_token_hbm_exists'))}</td></tr>
      <tr><th>last_token_validation_manifest_exists</th><td>{h(dream7b_last_token_validation_plan.get('manifest_exists'))}</td></tr>
      <tr><th>last_token_validation_manifest_verified</th><td>{h(dream7b_last_token_validation_plan.get('manifest_verified'))}</td></tr>
      <tr><th>last_token_validation_hbm_path</th><td><code>{h(dream7b_last_token_validation_plan.get('hbm_path'))}</code></td></tr>
      <tr><th>last_token_validation_compare</th><td>{h(dream7b_last_token_validation_compare.get('verdict') or 'missing')}</td></tr>
      <tr><th>last_token_compare_decision</th><td>{h(dream7b_last_token_validation_compare.get('decision'))}</td></tr>
      <tr><th>last_token_candidate_result_exists</th><td>{h(dream7b_last_token_validation_compare.get('candidate_exists'))}</td></tr>
      <tr><th>compile_capacity_plan</th><td>{h(dream7b_compile_capacity.get('verdict') or 'missing')}</td></tr>
      <tr><th>compile_command_guard</th><td>{h(dream7b_compile_command_guard.get('verdict') or 'missing')}</td></tr>
      <tr><th>compile_command_guard_active</th><td>{h(dream7b_compile_command_guard.get('compile_guard_active'))}</td></tr>
      <tr><th>compile_command_guard_b8_full_compile_blocked</th><td>{h(dream7b_compile_command_guard.get('b8_full_compile_blocked'))}</td></tr>
      <tr><th>compile_command_guard_only_single_segment_last_token_compile_allowed</th><td>{h(dream7b_compile_command_guard.get('only_single_segment_last_token_compile_allowed'))}</td></tr>
      <tr><th>compile_command_guard_would_start_compile</th><td>{h(dream7b_compile_command_guard.get('would_start_compile'))}</td></tr>
      <tr><th>next_action_admission_pack</th><td>{h(dream7b_next_action_pack.get('verdict') or 'missing')}</td></tr>
      <tr><th>next_action_allowed_now_count</th><td>{h(dream7b_next_action_pack.get('allowed_now_count'))}</td></tr>
      <tr><th>next_action_preflight_only_count</th><td>{h(dream7b_next_action_pack.get('preflight_only_count'))}</td></tr>
      <tr><th>next_action_blocked_action_count</th><td>{h(dream7b_next_action_pack.get('blocked_action_count'))}</td></tr>
      <tr><th>next_action_would_start_runtime</th><td>{h(dream7b_next_action_pack.get('would_start_runtime'))}</td></tr>
      <tr><th>next_action_would_start_compile</th><td>{h(dream7b_next_action_pack.get('would_start_compile'))}</td></tr>
      <tr><th>next_action_only_future_runtime_candidate</th><td>{h(dream7b_next_action_pack.get('only_future_runtime_candidate'))}</td></tr>
      <tr><th>compile_commit_headroom_gb</th><td>{h(dream7b_compile_capacity.get('commit_headroom_gb'))}</td></tr>
      <tr><th>compile_commit_headroom_deficit_gb</th><td>{h(dream7b_compile_capacity.get('commit_headroom_deficit_gb'))}</td></tr>
      <tr><th>compile_projected_headroom_after_reclaim_gb</th><td>{h(dream7b_compile_capacity.get('projected_commit_headroom_after_reclaim_gb'))}</td></tr>
      <tr><th>compile_remaining_deficit_after_reclaim_gb</th><td>{h(dream7b_compile_capacity.get('remaining_headroom_deficit_after_reclaim_gb'))}</td></tr>
      <tr><th>compile_recommended_additional_commit_limit_with_safety_gb</th><td>{h(dream7b_compile_capacity.get('recommended_additional_commit_limit_with_safety_gb'))}</td></tr>
      <tr><th>compile_do_not_start_compile_now</th><td>{h(dream7b_compile_capacity.get('do_not_start_compile_now'))}</td></tr>
      <tr><th>compile_largest_private_process</th><td>{h(dream7b_last_token.get('largest_private_process'))}</td></tr>
      <tr><th>true_batch_nas_inventory</th><td>{h(dream7b_nas_inventory.get('verdict') or 'missing')}</td></tr>
      <tr><th>nas_remote_group_major_report_count</th><td>{h(dream7b_nas_inventory.get('remote_group_major_report_count'))}</td></tr>
      <tr><th>nas_remote_group_major_report_json_count</th><td>{h(dream7b_nas_inventory.get('remote_group_major_report_json_count'))}</td></tr>
      <tr><th>nas_remote_b4_group_major_report_count</th><td>{h(dream7b_nas_inventory.get('remote_b4_group_major_report_count'))}</td></tr>
      <tr><th>nas_remote_b4_group_major_report_json_count</th><td>{h(dream7b_nas_inventory.get('remote_b4_group_major_report_json_count'))}</td></tr>
      <tr><th>nas_local_b4_json_count</th><td>{h(dream7b_nas_inventory.get('local_b4_json_count'))}</td></tr>
      <tr><th>nas_missing_report_json_dirs</th><td><code>{h(dream7b_nas_inventory.get('missing_report_json_dirs') or [])}</code></td></tr>
      <tr><th>nas_b4_remote_json_local_count_match</th><td>{h(dream7b_nas_inventory.get('b4_remote_json_local_count_match'))}</td></tr>
      <tr><th>nas_b4_hbm_count</th><td>{h(dream7b_nas_inventory.get('b4_hbm_count'))}</td></tr>
      <tr><th>nas_b4_manifest_count</th><td>{h(dream7b_nas_inventory.get('b4_manifest_count'))}</td></tr>
      <tr><th>nas_run_more_standard_b4_runtime_sweeps_now</th><td>{h(dream7b_nas_inventory.get('run_more_standard_b4_runtime_sweeps_now'))}</td></tr>
      <tr><th>nas_last_token_candidate_already_ran</th><td>{h(dream7b_nas_inventory.get('last_token_candidate_already_ran'))}</td></tr>
      <tr><th>nas_duplicate_stop_rules</th><td><code>{h(dream7b_nas_inventory.get('duplicate_stop_rules') or [])}</code></td></tr>
      <tr><th>nas_remaining_nonduplicate_work</th><td><code>{h(dream7b_nas_inventory.get('remaining_nonduplicate_work') or [])}</code></td></tr>
      <tr><th>runtime_refactor_backlog</th><td>{h(dream7b_refactor_backlog.get('verdict') or 'missing')}</td></tr>
      <tr><th>runtime_refactor_primary_target</th><td>{h(dream7b_refactor_backlog.get('primary_runtime_refactor_target'))}</td></tr>
      <tr><th>runtime_refactor_secondary_target</th><td>{h(dream7b_refactor_backlog.get('secondary_research_target'))}</td></tr>
      <tr><th>runtime_refactor_preallocate_hidden_rejected</th><td>{h(dream7b_refactor_backlog.get('current_preallocate_hidden_rejected_by_evidence'))}</td></tr>
      <tr><th>runtime_refactor_rank1_projected_saved_ms_per_request</th><td>{h(dream7b_refactor_backlog.get('rank1_projected_saved_ms_per_request'))}</td></tr>
      <tr><th>runtime_refactor_rank1_not_bpu_promotion_proof</th><td>{h(dream7b_refactor_backlog.get('rank1_projection_is_not_bpu_promotion_proof'))}</td></tr>
      <tr><th>runtime_refactor_rank1_blocks_standard_sweeps</th><td>{h(dream7b_refactor_backlog.get('rank1_blocks_standard_group_or_inner_order_sweeps'))}</td></tr>
      <tr><th>runtime_refactor_ready_local_count</th><td>{h(dream7b_refactor_backlog.get('ready_local_refactor_count'))}</td></tr>
      <tr><th>runtime_refactor_do_not_change_defaults_now</th><td>{h(dream7b_refactor_backlog.get('do_not_change_runtime_defaults_now'))}</td></tr>
      <tr><th>runtime_refactor_do_not_start_s100p_now</th><td>{h(dream7b_refactor_backlog.get('do_not_start_s100p_runtime_now'))}</td></tr>
      <tr><th>runtime_refactor_top_items</th><td><code>{h(dream7b_refactor_backlog.get('top_backlog_items') or [])}</code></td></tr>
      <tr><th>runtime_refactor_source_contract</th><td>{h(dream7b_refactor_source.get('verdict') or 'missing')}</td></tr>
      <tr><th>runtime_refactor_source_cli_defaults_preserved</th><td>{h(dream7b_refactor_source.get('cli_defaults_preserved'))}</td></tr>
      <tr><th>runtime_refactor_source_last_token_path_supported</th><td>{h(dream7b_refactor_source.get('last_token_path_supported'))}</td></tr>
      <tr><th>runtime_refactor_source_telemetry_contract_ready</th><td>{h(dream7b_refactor_source.get('telemetry_contract_ready'))}</td></tr>
      <tr><th>runtime_refactor_source_protected_telemetry_field_count</th><td>{h(dream7b_refactor_source.get('protected_telemetry_field_count'))}</td></tr>
      <tr><th>runtime_refactor_source_protected_telemetry_missing_count</th><td>{h(dream7b_refactor_source.get('protected_telemetry_missing_count'))}</td></tr>
      <tr><th>runtime_refactor_source_runtime_order_changed</th><td>{h(dream7b_refactor_source.get('runtime_order_changed'))}</td></tr>
      <tr><th>runtime_refactor_source_default_promotes_experimental_flags</th><td>{h(dream7b_refactor_source.get('default_promotes_experimental_flags'))}</td></tr>
      <tr><th>runtime_source_implementation_map</th><td>{h(dream7b_runtime_source_map.get('verdict') or 'missing')}</td></tr>
      <tr><th>runtime_source_implementation_area_count</th><td>{h(dream7b_runtime_source_map.get('implementation_area_count'))}</td></tr>
      <tr><th>runtime_source_pattern_count</th><td>{h(dream7b_runtime_source_map.get('source_pattern_count'))}</td></tr>
      <tr><th>runtime_source_missing_source_pattern_count</th><td>{h(dream7b_runtime_source_map.get('missing_source_pattern_count'))}</td></tr>
      <tr><th>runtime_source_primary_runtime_refactor_target</th><td>{h(dream7b_runtime_source_map.get('primary_runtime_refactor_target'))}</td></tr>
      <tr><th>runtime_source_primary_schedule_bottleneck</th><td>{h(dream7b_runtime_source_map.get('primary_schedule_bottleneck'))}</td></tr>
      <tr><th>runtime_source_allowed_now</th><td><code>{h(dream7b_runtime_source_map.get('allowed_now') or [])}</code></td></tr>
      <tr><th>runtime_source_duplicate_or_blocked_area_count</th><td>{h(dream7b_runtime_source_map.get('duplicate_or_blocked_area_count'))}</td></tr>
      <tr><th>runtime_source_s100p_runtime_allowed_now</th><td>{h(dream7b_runtime_source_map.get('s100p_runtime_experiment_allowed_now'))}</td></tr>
      <tr><th>runtime_source_compile_start_allowed_now</th><td>{h(dream7b_runtime_source_map.get('compile_start_allowed_now'))}</td></tr>
      <tr><th>runtime_source_runtime_default_change_allowed_now</th><td>{h(dream7b_runtime_source_map.get('runtime_default_change_allowed_now'))}</td></tr>
      <tr><th>runtime_source_standard_sweeps_blocked</th><td>{h(dream7b_runtime_source_map.get('standard_group_inner_order_sweeps_blocked'))}</td></tr>
      <tr><th>runtime_source_runtime_compile_not_started</th><td>{h(dream7b_runtime_source_map.get('runtime_compile_not_started'))}</td></tr>
      <tr><th>runtime_source_remote_access_not_performed</th><td>{h(dream7b_runtime_source_map.get('remote_access_not_performed'))}</td></tr>
      <tr><th>runtime_source_failed_checks</th><td><code>{h(dream7b_runtime_source_map.get('failed_checks') or [])}</code></td></tr>
      <tr><th>runtime_refactor_admission_contract</th><td>{h(dream7b_refactor_admission.get('verdict') or 'missing')}</td></tr>
      <tr><th>runtime_refactor_admission_local_report_only_allowed_now</th><td>{h(dream7b_refactor_admission.get('local_report_only_refactor_allowed_now'))}</td></tr>
      <tr><th>runtime_refactor_admission_default_runtime_change_allowed_now</th><td>{h(dream7b_refactor_admission.get('default_runtime_code_change_allowed_now'))}</td></tr>
      <tr><th>runtime_refactor_admission_s100p_runtime_allowed_now</th><td>{h(dream7b_refactor_admission.get('s100p_runtime_experiment_allowed_now'))}</td></tr>
      <tr><th>runtime_refactor_admission_compile_start_allowed_now</th><td>{h(dream7b_refactor_admission.get('compile_start_allowed_now'))}</td></tr>
      <tr><th>runtime_refactor_admission_compile_preflight_only_allowed_now</th><td>{h(dream7b_refactor_admission.get('compile_preflight_only_allowed_now'))}</td></tr>
      <tr><th>runtime_refactor_admission_block_standard_sweeps</th><td>{h(dream7b_refactor_admission.get('block_standard_group_or_inner_order_sweeps'))}</td></tr>
      <tr><th>runtime_refactor_admission_block_prewarm_or_cache_default</th><td>{h(dream7b_refactor_admission.get('block_prewarm_or_cache_default'))}</td></tr>
      <tr><th>Routing verdict</th><td>{h(dream7b_first_response.get('routing_verdict'))}</td></tr>
      <tr><th>Fast status verdict</th><td>{h(dream7b_first_response.get('fast_status_verdict'))}</td></tr>
      <tr><th>Fast regression verdict</th><td>{h(dream7b_first_response.get('fast_path_regression_verdict') or dream7b_fast_path_report.get('verdict'))}</td></tr>
      <tr><th>first_response_slo_tier_guard</th><td>{h(dream7b_first_response_slo.get('verdict') or 'missing')}</td></tr>
      <tr><th>fast_paths_satisfy_interactive_first_content_slo</th><td>{h(dream7b_first_response_slo.get('fast_paths_satisfy_interactive_first_content_slo'))}</td></tr>
      <tr><th>sse_progress_satisfies_interactive_progress_slo</th><td>{h(dream7b_first_response_slo.get('sse_progress_satisfies_interactive_progress_slo'))}</td></tr>
      <tr><th>backend_first_content_latency_is_not_true_batch_work</th><td>{h(dream7b_first_response_slo.get('backend_first_content_latency_is_not_true_batch_work'))}</td></tr>
      <tr><th>slo_fast_path_max_first_content_ms</th><td>{h(dream7b_first_response_slo.get('fast_path_max_first_content_ms'))}</td></tr>
      <tr><th>slo_first_progress_p50_ms</th><td>{h(dream7b_first_response_slo.get('sse_first_progress_p50_ms'))}</td></tr>
      <tr><th>slo_backend_explicit_first_content_p50_ms</th><td>{h(dream7b_first_response_slo.get('explicit_first_content_p50_ms'))}</td></tr>
      <tr><th>first_response_warning_triage</th><td>{h(dream7b_first_response_warning_triage.get('verdict') or 'missing')}</td></tr>
      <tr><th>first_response_warning_triaged</th><td>{h(dream7b_first_response_warning_triage.get('warning_is_product_triaged'))}</td></tr>
      <tr><th>first_response_warning_source_verdict</th><td>{h(dream7b_first_response_warning_triage.get('source_warning_verdict'))}</td></tr>
      <tr><th>first_response_warning_quickpath_delta_ms</th><td>{h(dream7b_first_response_warning_triage.get('quickpath_delta_ms'))}</td></tr>
      <tr><th>first_response_warning_backend_not_true_batch_work</th><td>{h(dream7b_first_response_warning_triage.get('backend_first_content_latency_is_not_true_batch_work'))}</td></tr>
      <tr><th>dream7b_default_service_freshness_gate</th><td><code>{h(dream7b_freshness_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Default freshness verdict</th><td>{h(dream7b_freshness_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>freshness_failed_checks</th><td><code>{h(dream7b_freshness_payload.get('failed_checks') or [])}</code></td></tr>
      <tr><th>packet_age_minutes</th><td>{h(dream7b_freshness.get('packet_age_minutes'))}</td></tr>
      <tr><th>queue_batch_service_remains_default</th><td>{h(dream7b_freshness_decision.get('queue_batch_service_remains_default'))}</td></tr>
      <tr><th>do_not_promote_true_batch</th><td>{h(dream7b_freshness_decision.get('do_not_promote_true_batch'))}</td></tr>
      <tr><th>partial_batch_flush_ready</th><td>{h(partial_batch_flush_ready)}</td></tr>
      <tr><th>partial_batch_flush_live_summary_ready</th><td>{h(partial_batch_flush_live_summary_ready)}</td></tr>
      <tr><th>partial_batch_flush_probe_ready</th><td>{h(partial_batch_flush_probe_ready)}</td></tr>
      <tr><th>partial_batch_flush_health_snapshot_ready</th><td>{h(partial_batch_flush_health_ready)}</td></tr>
      <tr><th>partial_batch_flush_probe_or_health_ready</th><td>{h(partial_batch_flush_probe_or_health_ready)}</td></tr>
      <tr><th>partial_batch_flush_readiness_source</th><td>{h(partial_batch_flush_source)}</td></tr>
      <tr><th>partial_batch_probe_run_dir</th><td><code>{h(partial_batch_probe_run_dir)}</code></td></tr>
      <tr><th>partial_batch_probe_ms_per_request</th><td>{h(partial_batch_probe_ms_per_request)}</td></tr>
      <tr><th>per_run_evidence_matrix</th><td>{h(per_run_evidence_matrix_verdict)}</td></tr>
      <tr><th>per_run_matrix_runs</th><td>{h(per_run_evidence_matrix_run_count)} total, {h(per_run_evidence_matrix_successful_run_count)} ok, {h(per_run_evidence_matrix_failed_run_count)} failed</td></tr>
      <tr><th>per_run_matrix_top_segment</th><td>{h(per_run_evidence_matrix_top_segment)} @ {h(per_run_evidence_matrix_top_segment_rate)}</td></tr>
      <tr><th>per_run_matrix_standard_sweep_status</th><td>{h(per_run_evidence_matrix_standard_sweep_status)}</td></tr>
      <tr><th>queue_health_snapshot</th><td>{h(dream7b_queue_health.get('verdict') or 'missing')}</td></tr>
      <tr><th>queue_health_queue_idle</th><td>{h(dream7b_queue_health.get('queue_idle_at_probe'))}</td></tr>
      <tr><th>queue_health_no_true_batch_or_compile_process</th><td>{h(dream7b_queue_health.get('no_true_batch_or_compile_process'))}</td></tr>
      <tr><th>queue_health_quick_ready_first_content_ms</th><td>{h(dream7b_queue_health.get('quick_ready_first_content_ms'))}</td></tr>
      <tr><th>queue_health_latest_text_queue_ms_per_request</th><td>{h(dream7b_queue_health.get('latest_text_queue_ms_per_request'))}</td></tr>
      <tr><th>workstream_overlap_audit</th><td>{h(dream7b_workstream_overlap.get('verdict') or 'missing')}</td></tr>
      <tr><th>workstream_current_workstream</th><td>{h(dream7b_workstream_overlap.get('current_workstream'))}</td></tr>
      <tr><th>workstream_queue_work_duplicates_true_batch_rental</th><td>{h(dream7b_workstream_overlap.get('queue_batch_work_duplicates_prior_true_batch_rental'))}</td></tr>
      <tr><th>workstream_b4_records</th><td>{h(dream7b_workstream_overlap.get('remote_b4_group_major_report_count'))}/{h(dream7b_workstream_overlap.get('local_b4_json_count'))}</td></tr>
      <tr><th>workstream_b4_json_records</th><td>{h(dream7b_workstream_overlap.get('remote_b4_group_major_report_json_count'))}/{h(dream7b_workstream_overlap.get('local_b4_json_count'))}</td></tr>
      <tr><th>tuning_decision_matrix</th><td>{h(dream7b_tuning_matrix.get('verdict') or 'missing')}</td></tr>
      <tr><th>tuning_preferred_group_policy</th><td>{h(dream7b_tuning_matrix.get('preferred_group_policy'))}</td></tr>
      <tr><th>tuning_preferred_inner_order</th><td>{h(dream7b_tuning_matrix.get('preferred_inner_order'))}</td></tr>
      <tr><th>tuning_primary_code_target</th><td>{h(dream7b_tuning_matrix.get('primary_code_target'))}</td></tr>
      <tr><th>tuning_primary_code_target_projected_saved_ms_per_request</th><td>{h(dream7b_tuning_matrix.get('primary_code_target_projected_saved_ms_per_request'))}</td></tr>
      <tr><th>tuning_primary_code_target_not_bpu_promotion_proof</th><td>{h(dream7b_tuning_matrix.get('primary_code_target_not_bpu_promotion_proof'))}</td></tr>
      <tr><th>tuning_standard_sweeps_blocked_by_final_logits_leverage</th><td>{h(dream7b_tuning_matrix.get('standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage'))}</td></tr>
      <tr><th>tuning_next_s100p_runtime_experiment_allowed</th><td>{h(dream7b_tuning_matrix.get('next_s100p_runtime_experiment_allowed'))}</td></tr>
      <tr><th>tuning_next_compile_allowed</th><td>{h(dream7b_tuning_matrix.get('next_compile_allowed'))}</td></tr>
      <tr><th>final_logits_leverage_model</th><td>{h(dream7b_final_logits_leverage.get('verdict') or 'missing')}</td></tr>
      <tr><th>final_logits_leverage_projection_saved_ms_per_request</th><td>{h(dream7b_final_logits_leverage.get('projection_saved_ms_per_request'))}</td></tr>
      <tr><th>final_logits_leverage_projection_capture_pct</th><td>{h(dream7b_final_logits_leverage.get('projection_capture_of_final_excess_pct'))}</td></tr>
      <tr><th>final_logits_leverage_latest_projected_latency_reduction_pct</th><td>{h(dream7b_final_logits_leverage.get('latest_projected_latency_reduction_pct'))}</td></tr>
      <tr><th>final_logits_leverage_latest_nonzero_shortfall_points</th><td>{h(dream7b_final_logits_leverage.get('latest_nonzero_shortfall_points'))}</td></tr>
      <tr><th>final_logits_leverage_not_bpu_promotion_proof</th><td>{h(dream7b_final_logits_leverage.get('projection_is_not_bpu_promotion_proof'))}</td></tr>
      <tr><th>nas_inventory_prevents_duplicate_sweeps</th><td>{h(dream7b_freshness_checks.get('nas_inventory_prevents_duplicate_sweeps'))}</td></tr>
      <tr><th>group_order_partition_prevents_duplicate_sweeps</th><td>{h(dream7b_freshness_checks.get('group_order_partition_prevents_duplicate_sweeps'))}</td></tr>
      <tr><th>scheduler_overhead_deprioritizes_python_gap_tuning</th><td>{h(dream7b_freshness_checks.get('scheduler_overhead_deprioritizes_python_gap_tuning'))}</td></tr>
      <tr><th>freshness_next_runtime_candidate</th><td>{h(dream7b_freshness_summary.get('next_runtime_candidate'))}</td></tr>
      <tr><th>Quick ready</th><td>{h(quick_ready_case.get('first_content_ms') or dream7b_first_response.get('regression_quick_ready_first_content_ms'))} ms via <code>{h(quick_ready_meta.get('execution_path'))}</code>; backend_invoked={h(quick_ready_meta.get('backend_invoked'))}</td></tr>
      <tr><th>Localized status</th><td>{h(localized_status_case.get('first_content_ms') or dream7b_first_response.get('regression_localized_status_first_content_ms'))} ms via <code>{h(localized_status_meta.get('execution_path'))}</code>; backend_invoked={h(localized_status_meta.get('backend_invoked'))}</td></tr>
      <tr><th>Guardrail report</th><td><code>{h(dream7b_guardrail_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>default_status_contract_ready</th><td>{h(dream7b_guardrail.get('default_status_contract_ready') or dream7b_product_evidence.get('guardrail_default_status_contract_ready'))}</td></tr>
      <tr><th>default_rollback_dry_run_ready</th><td>{h(dream7b_guardrail.get('default_rollback_dry_run_ready') or dream7b_product_evidence.get('guardrail_default_rollback_dry_run_ready'))}</td></tr>
      <tr><th>Status script sha256</th><td><code>{h(status_script.get('sha256') or dream7b_product_evidence.get('guardrail_status_script_sha256'))}</code></td></tr>
      <tr><th>Rollback script sha256</th><td><code>{h(rollback_script.get('sha256') or dream7b_product_evidence.get('guardrail_rollback_script_sha256'))}</code></td></tr>
      <tr><th>gateway_listener_ownership</th><td>{h(dream7b_product_evidence.get('gateway_listener_ownership_verdict'))}</td></tr>
      <tr><th>gateway_listener_pid</th><td>{h(dream7b_product_evidence.get('gateway_listener_pid'))}</td></tr>
      <tr><th>gateway_main_pid</th><td>{h(dream7b_product_evidence.get('gateway_main_pid'))}</td></tr>
      <tr><th>gateway_listener_matches_systemd_main_pid</th><td>{h(dream7b_product_evidence.get('gateway_listener_matches_systemd_main_pid'))}</td></tr>
      <tr><th>gateway_orphan_listener_detected</th><td>{h(dream7b_product_evidence.get('gateway_orphan_listener_detected'))}</td></tr>
      <tr><th>gateway_listener_health_ok</th><td>{h(dream7b_product_evidence.get('gateway_listener_health_ok'))}</td></tr>
      <tr><th>gateway_listener_drift_gate</th><td>{h(dream7b_product_evidence.get('gateway_listener_drift_gate_verdict'))}</td></tr>
      <tr><th>gateway_listener_drift_live_matches_systemd_main_pid</th><td>{h(dream7b_product_evidence.get('gateway_listener_drift_live_matches_systemd_main_pid'))}</td></tr>
      <tr><th>gateway_listener_drift_live_orphan_detected</th><td>{h(dream7b_product_evidence.get('gateway_listener_drift_live_orphan_detected'))}</td></tr>
      <tr><th>Checks</th><td><code>{h(dream7b_checks)}</code></td></tr>
    </tbody></table>
  </section>
  <section class="section" data-testid="operational-slo"><h2>Operational SLO</h2>
    <table><tbody>
      <tr><th>Report</th><td><code>{h(slo_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Verdict</th><td>{h(slo_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>Required contracts</th><td>{h(slo_summary.get('required_accepted_count'))}/{h(slo_summary.get('required_contract_count'))}</td></tr>
      <tr><th>Limited evidence</th><td>{h(slo_summary.get('limited_evidence_count'))}</td></tr>
      <tr><th>Rollup blockers</th><td>{h(slo_summary.get('blocker_count'))}</td></tr>
      <tr><th>Rollup warnings</th><td>{h(slo_summary.get('warning_count'))}</td></tr>
      <tr><th>slo_limited_evidence_triage</th><td>{h(dream7b_slo_limited_evidence_triage.get('verdict') or 'missing')}</td></tr>
      <tr><th>slo_limited_evidence_triaged</th><td>{h(dream7b_slo_limited_evidence_triage.get('limited_evidence_triaged'))}</td></tr>
      <tr><th>slo_limited_evidence_release_blocker</th><td>{h(dream7b_slo_limited_evidence_triage.get('release_blocker'))}</td></tr>
      <tr><th>slo_limited_warnings</th><td><code>{h(dream7b_slo_limited_evidence_triage.get('slo_warnings') or [])}</code></td></tr>
    </tbody></table>
    <p><b>Tail latency:</b> <code>{h((slo_scorecard.get('tail_latency') or {}))}</code></p>
    <p><b>Queue:</b> <code>{h((slo_scorecard.get('queue_backpressure') or {}))}</code></p>
    <p><b>BPU headroom:</b> <code>{h((slo_scorecard.get('bpu_headroom') or {}))}</code></p>
  </section>
  <section class="section" data-testid="objective-traceability"><h2>Objective Traceability</h2>
    <table><tbody>
      <tr><th>Report</th><td><code>{h(traceability_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Verdict</th><td>{h(traceability_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>Rows</th><td>{h(traceability_summary.get('satisfied_row_count'))}/{h(traceability_summary.get('objective_row_count'))} satisfied</td></tr>
      <tr><th>Limited rows</th><td>{h(traceability_summary.get('limited_row_count'))}</td></tr>
      <tr><th>Missing/failed rows</th><td>{h(traceability_summary.get('missing_or_failed_row_count'))}</td></tr>
      <tr><th>Active blockers</th><td>{h(traceability_summary.get('active_production_blocker_count'))}</td></tr>
    </tbody></table>
    <table><thead><tr><th>Objective row</th><th>Area</th><th>Status</th><th>Evidence gap</th></tr></thead><tbody>{traceability_rows_html}</tbody></table>
  </section>
  <section class="section" data-testid="dependency-bundle"><h2>Dependency Bundle</h2>
    <table><tbody>
      <tr><th>Report</th><td><code>{h(dependency_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Verdict</th><td>{h(dependency_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>Dependencies</th><td>{h(dependency_summary.get('ready_count'))}/{h(dependency_summary.get('dependency_count'))} ready</td></tr>
      <tr><th>Blocked</th><td>{h(dependency_summary.get('blocked_count'))}</td></tr>
    </tbody></table>
    <table><thead><tr><th>Dependency</th><th>Ready</th><th>Blockers</th></tr></thead><tbody>{dependency_rows_html}</tbody></table>
  </section>
  <section class="section" data-testid="production-runbook"><h2>Production Runbook</h2>
    <table><tbody>
      <tr><th>Report</th><td><code>{h(runbook_report.get('path') or 'not found')}</code></td></tr>
      <tr><th>Verdict</th><td>{h(runbook_report.get('verdict') or 'missing')}</td></tr>
      <tr><th>Items</th><td>{h(runbook_summary.get('runbook_item_count'))}</td></tr>
      <tr><th>Covered blockers</th><td>{h(runbook_summary.get('covered_required_blocker_count'))}/{h(runbook_summary.get('required_blocker_count'))}</td></tr>
      <tr><th>Verification commands</th><td>{h(runbook_summary.get('verification_command_count'))}</td></tr>
    </tbody></table>
    <table><thead><tr><th>Runbook</th><th>Owner</th><th>Covers</th><th>Verify with</th></tr></thead><tbody>{runbook_rows_html}</tbody></table>
  </section>
  <section class="section" data-testid="payment-nodes"><h2>Payment Nodes</h2><table><thead><tr><th>Date</th><th>Amount</th><th>Evidence path</th></tr></thead><tbody>{payments_html}</tbody></table></section>
  <section class="section" data-testid="copy-suggestions"><h2>Copy Suggestions</h2><ul>{suggestions_html}</ul></section>
  <section class="section" data-testid="approval" id="approval"><h2>Approval Queue</h2><p>Exact phrase for active manifest: <code>{h(approval_phrase)}</code></p><p>Blocked destructive actions: {h(blocked_actions)}</p><table><thead><tr><th>Manifest</th><th>Status</th><th>Risk</th><th>Actions</th><th>Phrase</th></tr></thead><tbody>{inbox_html}</tbody></table><p id="operator-decision-status"><code>idle</code></p></section>
  <section class="section" data-testid="report" id="report"><h2>One-Click Report</h2><p>JSON report: <code>{h(report_json_path)}</code></p><p>Manifest SHA256: <code>{h(approval_manifest.get('manifest_sha256'))}</code></p></section>
  <section class="section" data-testid="audit"><h2>Audit Status</h2><p class="audit-ok">Source modified: {h(audit.get('source_files_modified'))}; delete: {h(audit.get('delete_performed'))}; move: {h(audit.get('move_performed'))}; overwrite: {h(audit.get('overwrite_performed'))}; execution: {h(audit.get('execution_performed'))}</p></section>
  <script>
    async function recordOperatorDecision(event) {{
      const button = event.target.closest('button[data-decision]');
      if (!button) return;
      const status = document.getElementById('operator-decision-status');
      status.innerHTML = '<code>recording</code>';
      try {{
        const response = await fetch('/api/operator-decision', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            manifest_id: button.dataset.manifest,
            decision: button.dataset.decision,
            phrase: button.dataset.phrase
          }})
        }});
        const payload = await response.json();
        const record = payload.operator_decision || {{}};
        status.innerHTML = '<code>' + (payload.ok ? 'recorded ' : 'failed ') + (record.path || payload.error || '') + '</code>';
      }} catch (error) {{
        status.innerHTML = '<code>failed ' + String(error).slice(0, 160) + '</code>';
      }}
    }}
    document.getElementById('approval').addEventListener('click', recordOperatorDecision);
  </script>
</main>
</body>
</html>
"""


def evaluate_portal(
    html_text: str,
    result_rows: list[dict],
    payment_nodes: list[dict],
    suggestions: list[dict],
    inbox_rows: list[dict],
    audit: dict,
    readiness_report: dict,
    slo_report: dict,
    traceability_report: dict,
    dependency_report: dict,
    runbook_report: dict,
    soak_watcher_report: dict,
    dream7b_report: dict,
    dream7b_product_report: dict,
    dream7b_fast_path_report: dict,
    dream7b_guardrail_report: dict,
    dream7b_freshness_report: dict,
) -> list[str]:
    failures = []
    required_tokens = [
        "AI-NAS Operator Portal",
        "Run Commands",
        "ai_nas_controlled_personal_seed",
        "ai_nas_nas_backed_long_soak",
        "dream7b_perf_identity",
        "Related Files",
        "Payment Nodes",
        "Copy Suggestions",
        "Approval Queue",
        "One-Click Report",
        "Audit Status",
        "Production Readiness",
        "Long Soak / Gate Watcher",
        "Dream7B Interaction",
        "Dream7B Service Guardrails",
        "dream7b_product_decision_packet",
        "runtime_experiment_gate",
        "s100p_runtime_experiment_now",
        "allowed_s100p_runtime_experiments",
        "runtime_gate_blockers",
        "next_nonduplicate_runtime_candidate",
        "segment_stability_audit",
        "stable_primary_bottleneck",
        "final_logits_rank1_rate",
        "final_logits_cv_positive_excess",
        "final_to_token_excess_ratio",
        "final_to_max_hidden_excess_ratio",
        "do_not_run_hidden_order_sweeps_now",
        "segment_drag_breakdown",
        "segment_drag_final_vs_hidden_mean_ratio",
        "segment_drag_final_excess_ms_per_request",
        "segment_drag_top_group_by_accounted_ms",
        "group_order_candidates",
        "group_order_baseline",
        "group_order_best_nonbaseline_delta_ms_per_request",
        "group_order_no_variant_beats_baseline",
        "group_partition_planner",
        "group_partition_candidate_count",
        "group_partition_run_new_partition_now",
        "group_partition_top_capacity_probe_groups",
        "group_inner_order_value_audit",
        "group_inner_order_run_more_sweeps_now",
        "group_inner_order_best_nonbaseline_delta_ms_per_request",
        "group_inner_order_top_value_lever",
        "group_switch_accounting",
        "group_switch_gap_ms_per_request",
        "final_excess_to_switch_gap_ratio",
        "scheduler_overhead_budget",
        "scheduler_primary_code_target",
        "deprioritize_python_inter_segment_gap_tuning",
        "runtime_instrumentation_contract",
        "runtime_instrumentation_deployment",
        "runtime_instrumentation_remote_probe_sha256",
        "hbm_load_accounting_contract",
        "hbm_per_segment_load_accounting_ready",
        "hbm_group_load_accounting_ready",
        "hbm_prewarm_accounting_ready",
        "hbm_timing_summary_accounts_load_and_prewarm",
        "hbm_prewarm_hbm_default_changed",
        "bottleneck_closure_model",
        "bottleneck_closure_latest_avg_bpu_gap_to_queue_points",
        "bottleneck_closure_primary_next_code_target",
        "bottleneck_closure_final_logits_projection_saved_ms_per_request",
        "bottleneck_closure_projection_is_not_bpu_promotion_proof",
        "bottleneck_closure_requires_real_runtime_result_before_promotion",
        "post_instrumentation_telemetry_gate",
        "post_instrumentation_telemetry_ready",
        "input_output_overhead_quantified",
        "do_not_claim_input_output_overhead_yet",
        "allow_one_post_instrumentation_baseline_measurement",
        "post_instrumentation_overhead_analysis",
        "input_prepare_ms_per_request",
        "output_postprocess_ms_per_request",
        "hidden_materialize_ms_per_request",
        "final_logits_compute_still_primary",
        "post_instrumentation_segment_attribution",
        "post_segment_primary_single_segment_bottleneck",
        "post_segment_group_size_tuning_implication",
        "post_segment_inner_order_tuning_implication",
        "hidden_buffer_reuse_decision",
        "hidden_buffer_reuse_default",
        "preallocate_hidden_experimental_flag_only",
        "prealloc_hidden_materialize_ms_per_request_delta",
        "reuse_buffer_implementation_measured_slower",
        "last_token_compile_ready",
        "last_token_readiness_blockers",
        "compile_capacity_plan",
        "compile_commit_headroom_gb",
        "compile_commit_headroom_deficit_gb",
        "compile_projected_headroom_after_reclaim_gb",
        "compile_remaining_deficit_after_reclaim_gb",
        "compile_recommended_additional_commit_limit_with_safety_gb",
        "compile_do_not_start_compile_now",
        "compile_largest_private_process",
        "true_batch_nas_inventory",
        "nas_remote_b4_group_major_report_count",
        "nas_local_b4_json_count",
        "nas_b4_hbm_count",
        "nas_b4_manifest_count",
        "nas_run_more_standard_b4_runtime_sweeps_now",
        "nas_duplicate_stop_rules",
        "runtime_refactor_backlog",
        "runtime_refactor_primary_target",
        "runtime_refactor_do_not_change_defaults_now",
        "runtime_refactor_do_not_start_s100p_now",
        "runtime_source_implementation_map",
        "runtime_source_pattern_count",
        "runtime_source_missing_source_pattern_count",
        "runtime_source_primary_runtime_refactor_target",
        "runtime_source_s100p_runtime_allowed_now",
        "runtime_source_compile_start_allowed_now",
        "runtime_source_runtime_default_change_allowed_now",
        "runtime_source_standard_sweeps_blocked",
        "dream7b_default_service_freshness_gate",
        "Default freshness verdict",
        "queue_batch_service_remains_default",
        "do_not_promote_true_batch",
        "first_response_slo_tier_guard",
        "fast_paths_satisfy_interactive_first_content_slo",
        "sse_progress_satisfies_interactive_progress_slo",
        "backend_first_content_latency_is_not_true_batch_work",
        "slo_fast_path_max_first_content_ms",
        "slo_backend_explicit_first_content_p50_ms",
        "nas_inventory_prevents_duplicate_sweeps",
        "group_order_partition_prevents_duplicate_sweeps",
        "scheduler_overhead_deprioritizes_python_gap_tuning",
        "gateway_fast_ready",
        "default_rollback_dry_run_ready",
        "gateway_listener_matches_systemd_main_pid",
        "gateway_orphan_listener_detected",
        "gateway_listener_drift_gate",
        "gateway_listener_drift_live_matches_systemd_main_pid",
        "Operational SLO",
        "Objective Traceability",
        "Dependency Bundle",
        "Production Runbook",
        "2024 renovation payment contract invoice receipt chat screenshot",
        "APPROVE ",
        "delete",
        "move",
        "overwrite",
        "rename",
    ]
    for token in required_tokens:
        if token not in html_text:
            failures.append(f"portal_missing_token:{token}")
    if html_text.count('data-testid="result-card"') < 3:
        failures.append("portal_result_card_count_lt_3")
    if len(payment_nodes) < 2:
        failures.append("payment_nodes_lt_2")
    if not suggestions:
        failures.append("copy_suggestions_missing")
    if not any(row.get("risk_level") == "ready_for_operator_review" for row in inbox_rows):
        failures.append("approval_queue_missing_ready_for_review")
    if not any(row.get("risk_level") == "needs_manifest_repair" for row in inbox_rows):
        failures.append("approval_queue_missing_needs_repair")
    for token in ['data-decision="approve"', "Rollback draft", "operator-decision-status"]:
        if token not in html_text:
            failures.append(f"operator_decision_control_missing:{token}")
    for row in result_rows:
        if not row.get("why_matched") or not row.get("evidence_snippets") or row.get("confidence") is None:
            failures.append(f"result_missing_grounding:{row.get('relative_path')}")
        if row.get("relative_path") not in html_text:
            failures.append(f"portal_missing_result_path:{row.get('relative_path')}")
    if any(audit.get(key) for key in ["source_files_modified", "delete_performed", "move_performed", "overwrite_performed", "execution_performed"]):
        failures.append("audit_mutation_flagged")
    if readiness_report.get("found") and readiness_report.get("verdict") not in (
        "ready_ai_nas_production_readiness_gate",
        "limited_ai_nas_production_readiness_gate",
    ):
        failures.append(f"readiness_verdict_unexpected:{readiness_report.get('verdict')}")
    if slo_report.get("found") and slo_report.get("verdict") not in (
        "ok_ai_nas_operational_slo_rollup_contract",
        "failed_ai_nas_operational_slo_rollup_contract",
    ):
        failures.append(f"slo_rollup_verdict_unexpected:{slo_report.get('verdict')}")
    if traceability_report.get("found") and traceability_report.get("verdict") not in (
        "ok_ai_nas_objective_traceability_contract",
        "failed_ai_nas_objective_traceability_contract",
    ):
        failures.append(f"traceability_verdict_unexpected:{traceability_report.get('verdict')}")
    if dependency_report.get("found") and dependency_report.get("verdict") not in (
        "ok_ai_nas_production_dependency_bundle",
        "limited_ai_nas_production_dependency_bundle",
    ):
        failures.append(f"dependency_bundle_verdict_unexpected:{dependency_report.get('verdict')}")
    if runbook_report.get("found") and runbook_report.get("verdict") not in (
        "ok_ai_nas_production_blocker_runbook_contract",
        "failed_ai_nas_production_blocker_runbook_contract",
    ):
        failures.append(f"runbook_verdict_unexpected:{runbook_report.get('verdict')}")
    if soak_watcher_report.get("found") and "Soak Watcher" not in html_text:
        failures.append("soak_watcher_not_visible")
    if dream7b_report.get("found") and "Dream7B Interaction" not in html_text:
        failures.append("dream7b_interaction_not_visible")
    if dream7b_product_report.get("found") and dream7b_product_report.get("verdict") not in (
        "ok_dream7b_product_decision_packet",
        "warning_dream7b_product_decision_packet",
    ):
        failures.append(f"dream7b_product_packet_verdict_unexpected:{dream7b_product_report.get('verdict')}")
    if dream7b_fast_path_report.get("found") and dream7b_fast_path_report.get("verdict") != "ok_dream7b_fast_path_regression":
        failures.append(f"dream7b_fast_path_regression_verdict_unexpected:{dream7b_fast_path_report.get('verdict')}")
    if dream7b_guardrail_report.get("found") and dream7b_guardrail_report.get("verdict") != "ok_dream7b_product_guardrail_snapshot":
        failures.append(f"dream7b_guardrail_verdict_unexpected:{dream7b_guardrail_report.get('verdict')}")
    if dream7b_freshness_report.get("found") and dream7b_freshness_report.get("verdict") not in (
        "ok_dream7b_default_service_freshness_gate",
        "warning_dream7b_default_service_freshness_gate",
    ):
        failures.append(
            f"dream7b_default_service_freshness_gate_verdict_unexpected:{dream7b_freshness_report.get('verdict')}"
        )
    product_payload = dream7b_product_report.get("payload") or {}
    first_response = product_payload.get("first_response") or {}
    first_response_slo = product_payload.get("first_response_slo_tier_guard") or {}
    first_response_warning_triage = (
        product_payload.get("first_response_warning_triage") or {}
    )
    slo_limited_evidence_triage = (
        product_payload.get("slo_limited_evidence_triage") or {}
    )
    product_evidence = product_payload.get("product_evidence") or {}
    freshness_payload_for_partial = dream7b_freshness_report.get("payload") or {}
    freshness_checks_for_partial = freshness_payload_for_partial.get("checks") or {}
    freshness_summary_for_partial = freshness_payload_for_partial.get("packet_summary") or {}
    partial_batch_flush_ready = product_evidence.get("queue_partial_batch_flush_ready")
    if partial_batch_flush_ready is None:
        partial_batch_flush_ready = freshness_checks_for_partial.get(
            "queue_partial_batch_flush_ready"
        )
    partial_batch_flush_probe_ready = product_evidence.get(
        "queue_partial_batch_flush_probe_ready"
    )
    if partial_batch_flush_probe_ready is None:
        partial_batch_flush_probe_ready = freshness_checks_for_partial.get(
            "queue_partial_batch_flush_probe_ready"
        )
    partial_batch_flush_health_ready = product_evidence.get(
        "queue_partial_batch_flush_health_snapshot_ready"
    )
    if partial_batch_flush_health_ready is None:
        partial_batch_flush_health_ready = freshness_checks_for_partial.get(
            "queue_partial_batch_flush_health_snapshot_ready"
        )
    partial_batch_flush_probe_or_health_ready = (
        partial_batch_flush_probe_ready is True or partial_batch_flush_health_ready is True
    )
    partial_batch_flush_source = product_evidence.get(
        "queue_partial_batch_flush_readiness_source"
    ) or freshness_summary_for_partial.get("queue_partial_batch_flush_readiness_source")
    per_run_evidence_matrix_verdict = product_evidence.get(
        "per_run_evidence_matrix_verdict"
    ) or freshness_summary_for_partial.get("per_run_evidence_matrix_verdict")
    per_run_evidence_matrix_top_segment = product_evidence.get(
        "per_run_evidence_matrix_top_segment"
    ) or freshness_summary_for_partial.get("per_run_evidence_matrix_top_segment")
    per_run_evidence_matrix_top_segment_rate = product_evidence.get(
        "per_run_evidence_matrix_top_segment_rate"
    ) or freshness_summary_for_partial.get("per_run_evidence_matrix_top_segment_rate")
    per_run_evidence_matrix_standard_sweep_status = product_evidence.get(
        "per_run_evidence_matrix_standard_sweep_status"
    ) or freshness_summary_for_partial.get("per_run_evidence_matrix_standard_sweep_status")
    runtime_gate = product_payload.get("runtime_experiment_gate") or {}
    segment_drag = product_payload.get("segment_drag_breakdown") or {}
    segment_stability = product_payload.get("segment_stability_audit") or {}
    group_order = product_payload.get("group_order_candidates") or {}
    group_partition = product_payload.get("group_partition_planner") or {}
    group_inner_order_value = product_payload.get("group_inner_order_value_audit") or {}
    segment_group_schedule = product_payload.get("segment_group_schedule_scorecard") or {}
    group_switch = product_payload.get("group_switch_accounting") or {}
    scheduler = product_payload.get("scheduler_overhead_budget") or {}
    instrumentation = product_payload.get("runtime_instrumentation") or {}
    hbm_accounting = product_payload.get("hbm_load_accounting_contract") or {}
    bottleneck_closure = product_payload.get("bottleneck_closure_model") or {}
    post_instrumentation = product_payload.get("post_instrumentation_telemetry_gate") or {}
    post_overhead = product_payload.get("post_instrumentation_overhead_analysis") or {}
    post_segment = product_payload.get("post_instrumentation_segment_attribution") or {}
    hidden_buffer = product_payload.get("hidden_buffer_reuse_decision") or {}
    queue_health = product_payload.get("queue_health_snapshot") or {}
    workstream_overlap = product_payload.get("workstream_overlap_audit") or {}
    tuning_matrix = product_payload.get("tuning_decision_matrix") or {}
    last_token = product_payload.get("last_token_candidate") or {}
    last_token_validation_plan = (
        product_payload.get("last_token_runtime_validation_plan") or {}
    )
    last_token_validation_compare = product_payload.get("last_token_validation_compare") or {}
    compile_capacity = product_payload.get("compile_capacity") or {}
    compile_command_guard = product_payload.get("compile_command_guard") or {}
    next_action_pack = product_payload.get("next_action_admission_pack") or {}
    nas_inventory = product_payload.get("true_batch_nas_inventory") or {}
    refactor_backlog = product_payload.get("runtime_refactor_backlog") or {}
    refactor_source = product_payload.get("runtime_refactor_source_contract") or {}
    refactor_admission = product_payload.get("runtime_refactor_admission_contract") or {}
    runtime_source_map = product_payload.get("runtime_source_implementation_map") or {}
    product_decision = product_payload.get("decision") or {}
    if dream7b_product_report.get("found"):
        for key in [
            "routing_verdict",
            "fast_status_verdict",
            "fast_path_regression_verdict",
            "regression_quick_ready_first_content_ms",
            "regression_localized_status_first_content_ms",
        ]:
            if first_response.get(key) is None:
                failures.append(f"dream7b_product_first_response_missing:{key}")
        for key in [
            "verdict",
            "fast_paths_satisfy_interactive_first_content_slo",
            "sse_progress_satisfies_interactive_progress_slo",
            "backend_first_content_latency_is_not_true_batch_work",
            "fast_path_max_first_content_ms",
            "sse_first_progress_p50_ms",
            "explicit_first_content_p50_ms",
            "runtime_started",
            "compile_started",
        ]:
            if first_response_slo.get(key) is None:
                failures.append(f"dream7b_product_first_response_slo_missing:{key}")
        if first_response_slo.get("verdict") != "ok_dream7b_first_response_slo_tier_guard":
            failures.append("dream7b_product_first_response_slo_not_ok")
        if first_response_slo.get("fast_paths_satisfy_interactive_first_content_slo") is not True:
            failures.append("dream7b_product_first_response_slo_fast_path_not_ready")
        if first_response_slo.get("sse_progress_satisfies_interactive_progress_slo") is not True:
            failures.append("dream7b_product_first_response_slo_progress_not_ready")
        if first_response_slo.get("backend_first_content_latency_is_not_true_batch_work") is not True:
            failures.append("dream7b_product_first_response_slo_backend_misclassified")
        if first_response_slo.get("runtime_started") is not False:
            failures.append("dream7b_product_first_response_slo_started_runtime")
        if first_response_slo.get("compile_started") is not False:
            failures.append("dream7b_product_first_response_slo_started_compile")
        for key in [
            "verdict",
            "warning_is_product_triaged",
            "source_warning_verdict",
            "quickpath_delta_ms",
            "backend_first_content_latency_is_not_true_batch_work",
            "runtime_started",
            "compile_started",
        ]:
            if first_response_warning_triage.get(key) is None:
                failures.append(f"dream7b_product_first_response_warning_triage_missing:{key}")
        if (
            first_response_warning_triage.get("verdict")
            != "ok_dream7b_first_response_warning_triage"
        ):
            failures.append("dream7b_product_first_response_warning_triage_not_ok")
        if first_response_warning_triage.get("warning_is_product_triaged") is not True:
            failures.append("dream7b_product_first_response_warning_not_triaged")
        if (
            first_response_warning_triage.get(
                "backend_first_content_latency_is_not_true_batch_work"
            )
            is not True
        ):
            failures.append("dream7b_product_first_response_warning_backend_misclassified")
        if first_response_warning_triage.get("runtime_started") is not False:
            failures.append("dream7b_product_first_response_warning_started_runtime")
        if first_response_warning_triage.get("compile_started") is not False:
            failures.append("dream7b_product_first_response_warning_started_compile")
        for key in [
            "verdict",
            "limited_evidence_triaged",
            "release_blocker",
            "slo_warnings",
            "concurrency_verdict",
            "runtime_started",
            "compile_started",
        ]:
            if slo_limited_evidence_triage.get(key) is None:
                failures.append(f"dream7b_product_slo_limited_triage_missing:{key}")
        if (
            slo_limited_evidence_triage.get("verdict")
            != "ok_ai_nas_slo_limited_evidence_triage"
        ):
            failures.append("dream7b_product_slo_limited_triage_not_ok")
        if slo_limited_evidence_triage.get("limited_evidence_triaged") is not True:
            failures.append("dream7b_product_slo_limited_not_triaged")
        if slo_limited_evidence_triage.get("release_blocker") is not False:
            failures.append("dream7b_product_slo_limited_marked_blocker")
        if slo_limited_evidence_triage.get("runtime_started") is not False:
            failures.append("dream7b_product_slo_limited_started_runtime")
        if slo_limited_evidence_triage.get("compile_started") is not False:
            failures.append("dream7b_product_slo_limited_started_compile")
        for key in [
            "s100p_runtime_experiment_now",
            "allowed_s100p_runtime_experiments",
        ]:
            if key not in product_decision:
                failures.append(f"dream7b_product_runtime_gate_decision_missing:{key}")
        for key in [
            "verdict",
            "blockers",
            "next_nonduplicate_runtime_candidate",
        ]:
            if runtime_gate.get(key) is None:
                failures.append(f"dream7b_product_runtime_gate_missing:{key}")
        for key in [
            "verdict",
            "stable_primary_bottleneck",
            "final_logits_rank1_rate",
            "final_logits_cv_positive_excess",
            "final_to_token_excess_ratio",
            "final_to_max_hidden_excess_ratio",
            "do_not_run_hidden_order_sweeps_now",
        ]:
            if segment_stability.get(key) is None:
                failures.append(f"dream7b_product_segment_stability_missing:{key}")
        if segment_stability.get("stable_primary_bottleneck") != "seg27_28_final_logits":
            failures.append("dream7b_product_segment_stability_unexpected_primary")
        if segment_stability.get("do_not_run_hidden_order_sweeps_now") is not True:
            failures.append("dream7b_product_segment_stability_hidden_order_not_blocked")
        for key in [
            "verdict",
            "analyzed_run_count",
            "latest_microbatch_count",
            "final_avg_run_ms",
            "hidden_mean_avg_run_ms",
            "final_vs_hidden_mean_ratio",
            "final_excess_ms_per_request_if_hidden_speed",
            "token_excess_ms_per_request_if_hidden_speed",
            "top_group_by_accounted_ms",
            "top_group_contains_final_logits",
            "top_segments_by_avg_run_ms",
        ]:
            if segment_drag.get(key) is None:
                failures.append(f"dream7b_product_segment_drag_missing:{key}")
        top_segments = segment_drag.get("top_segments_by_avg_run_ms") or []
        if not top_segments or top_segments[0].get("index") != 27:
            failures.append("dream7b_product_segment_drag_final_not_rank1")
        if segment_drag.get("top_group_contains_final_logits") is not False:
            failures.append("dream7b_product_segment_drag_top_group_unexpected_final")
        for key in [
            "verdict",
            "primary_schedule_bottleneck",
            "primary_code_target",
            "preferred_group_policy",
            "preferred_inner_order",
            "run_more_standard_b4_group_or_inner_order_sweeps_now",
            "run_new_group_partition_now",
            "run_s100p_runtime_now",
            "start_compile_now",
            "compile_preflight_only_now",
            "final_excess_to_group_switch_gap_ratio",
        ]:
            if segment_group_schedule.get(key) is None:
                failures.append(f"dream7b_segment_group_schedule_missing:{key}")
        if (
            segment_group_schedule.get("verdict")
            != "ok_dream7b_b4_segment_group_schedule_scorecard"
        ):
            failures.append("dream7b_segment_group_schedule_not_ok")
        if segment_group_schedule.get("primary_schedule_bottleneck") != "seg27_28_final_logits":
            failures.append("dream7b_segment_group_schedule_unexpected_primary")
        if (
            segment_group_schedule.get("preferred_group_policy")
            != "keep_existing_5_group_segment_major_default"
        ):
            failures.append("dream7b_segment_group_schedule_group_policy_changed")
        if segment_group_schedule.get("preferred_inner_order") != "segment-major":
            failures.append("dream7b_segment_group_schedule_inner_order_changed")
        if (
            segment_group_schedule.get("run_more_standard_b4_group_or_inner_order_sweeps_now")
            is not False
        ):
            failures.append("dream7b_segment_group_schedule_standard_sweeps_allowed")
        if segment_group_schedule.get("run_new_group_partition_now") is not False:
            failures.append("dream7b_segment_group_schedule_partition_allowed")
        if segment_group_schedule.get("run_s100p_runtime_now") is not False:
            failures.append("dream7b_segment_group_schedule_runtime_allowed")
        if segment_group_schedule.get("start_compile_now") is not False:
            failures.append("dream7b_segment_group_schedule_compile_allowed")
        if segment_group_schedule.get("compile_preflight_only_now") is not True:
            failures.append("dream7b_segment_group_schedule_preflight_not_allowed")
        if segment_group_schedule.get("failed_checks"):
            failures.append("dream7b_segment_group_schedule_failed_checks")
        for key in [
            "verdict",
            "baseline",
            "segment_major_preferred_over_microbatch_major",
            "best_nonbaseline_observed_variant",
            "best_nonbaseline_observed_variant_delta_ms_per_request",
            "no_observed_variant_beats_baseline",
            "more_mb512_group_boundary_sweeps_deprioritized",
            "only_capacity_probe_if_needed",
        ]:
            if group_order.get(key) is None:
                failures.append(f"dream7b_product_group_order_missing:{key}")
        if group_order.get("segment_major_preferred_over_microbatch_major") is not True:
            failures.append("dream7b_product_group_order_segment_major_not_preferred")
        if group_order.get("no_observed_variant_beats_baseline") is not True:
            failures.append("dream7b_product_group_order_variant_beats_baseline")
        if group_order.get("more_mb512_group_boundary_sweeps_deprioritized") is not True:
            failures.append("dream7b_product_group_order_mb512_sweeps_not_blocked")
        if (group_order.get("best_nonbaseline_observed_variant_delta_ms_per_request") or 0) <= 0:
            failures.append("dream7b_product_group_order_best_delta_not_positive")
        for key in [
            "verdict",
            "candidate_count",
            "run_new_partition_now",
            "only_probe_if_memory_plan_changes",
            "top_capacity_probe_groups",
            "top_capacity_probe_max_group_hbm_mib",
            "top_capacity_probe_peak_delta_pct",
            "best_observed_nonbaseline_delta_ms_per_request",
        ]:
            if group_partition.get(key) is None:
                failures.append(f"dream7b_product_group_partition_missing:{key}")
        if group_partition.get("run_new_partition_now") is not False:
            failures.append("dream7b_product_group_partition_run_new_not_blocked")
        if (group_partition.get("candidate_count") or 0) <= 100000:
            failures.append("dream7b_product_group_partition_candidate_count_low")
        for key in [
            "verdict",
            "best_nonbaseline_delta_ms_per_request",
            "slower_or_equal_nonbaseline_count",
            "capacity_probe_only_candidate_count",
            "run_more_group_size_or_inner_order_sweeps_now",
            "group_size_and_inner_order_are_current_primary_levers",
            "next_s100p_runtime_experiment_allowed_now",
            "next_compile_allowed_now",
            "top_value_lever",
        ]:
            if group_inner_order_value.get(key) is None:
                failures.append(f"dream7b_product_group_inner_order_value_missing:{key}")
        if (
            group_inner_order_value.get("verdict")
            != "ok_dream7b_b4_group_inner_order_value_audit"
        ):
            failures.append("dream7b_product_group_inner_order_value_not_ok")
        if group_inner_order_value.get("run_more_group_size_or_inner_order_sweeps_now") is not False:
            failures.append("dream7b_product_group_inner_order_value_sweeps_not_blocked")
        if group_inner_order_value.get("group_size_and_inner_order_are_current_primary_levers") is not False:
            failures.append("dream7b_product_group_inner_order_value_marked_primary")
        if group_inner_order_value.get("next_s100p_runtime_experiment_allowed_now") is not False:
            failures.append("dream7b_product_group_inner_order_value_runtime_allowed")
        if group_inner_order_value.get("next_compile_allowed_now") is not False:
            failures.append("dream7b_product_group_inner_order_value_compile_allowed")
        for key in [
            "verdict",
            "group_switch_gap_ms_per_request",
            "group_release_ms_per_request",
            "unaccounted_gap_ms_per_request",
            "latest_gap_intra_segment_run_gap_ms_per_request",
            "final_excess_to_switch_gap_ratio",
            "group_release_and_unaccounted_gap_not_primary",
        ]:
            if group_switch.get(key) is None:
                failures.append(f"dream7b_product_group_switch_missing:{key}")
        if group_switch.get("group_release_and_unaccounted_gap_not_primary") is not True:
            failures.append("dream7b_product_group_switch_gap_primary")
        if (group_switch.get("final_excess_to_switch_gap_ratio") or 0) <= 50:
            failures.append("dream7b_product_group_switch_final_ratio_low")
        for key in [
            "verdict",
            "primary_code_target",
            "deprioritize_python_inter_segment_gap_tuning",
            "deprioritize_more_group_boundary_sweeps",
            "final_excess_to_group_switch_gap",
            "final_excess_to_intra_segment_gap",
            "final_excess_exceeds_group_switch_gap_50x",
        ]:
            if scheduler.get(key) is None:
                failures.append(f"dream7b_product_scheduler_overhead_missing:{key}")
        if scheduler.get("deprioritize_python_inter_segment_gap_tuning") is not True:
            failures.append("dream7b_product_scheduler_python_gap_not_deprioritized")
        if scheduler.get("final_excess_exceeds_group_switch_gap_50x") is not True:
            failures.append("dream7b_product_scheduler_final_ratio_guard_missing")
        for key in [
            "contract_verdict",
            "deployment_verdict",
            "new_telemetry_fields",
            "default_cli_changed",
            "runtime_order_changed",
            "requires_s100p_runtime",
            "remote_probe_sha256",
            "remote_backup",
            "active_true_batch_python",
            "active_compile_true_batch",
        ]:
            if instrumentation.get(key) is None:
                failures.append(f"dream7b_product_runtime_instrumentation_missing:{key}")
        if instrumentation.get("contract_verdict") != "ok_dream7b_true_batch_runtime_instrumentation_contract":
            failures.append("dream7b_product_runtime_instrumentation_contract_not_ok")
        if instrumentation.get("deployment_verdict") != "ok_dream7b_true_batch_runtime_instrumentation_deployment_contract":
            failures.append("dream7b_product_runtime_instrumentation_deployment_not_ok")
        if instrumentation.get("default_cli_changed") is not False:
            failures.append("dream7b_product_runtime_instrumentation_default_cli_changed")
        if instrumentation.get("runtime_order_changed") is not False:
            failures.append("dream7b_product_runtime_instrumentation_order_changed")
        if instrumentation.get("active_true_batch_python") != 0.0:
            failures.append("dream7b_product_runtime_instrumentation_runtime_started")
        if instrumentation.get("active_compile_true_batch") != 0.0:
            failures.append("dream7b_product_runtime_instrumentation_compile_started")
        for key in [
            "verdict",
            "per_segment_load_accounting_ready",
            "group_load_accounting_ready",
            "prewarm_accounting_ready",
            "timing_summary_accounts_load_and_prewarm",
            "prewarm_hbm_default_changed",
            "runtime_started",
            "compile_started",
        ]:
            if hbm_accounting.get(key) is None:
                failures.append(f"dream7b_hbm_load_accounting_missing:{key}")
        if hbm_accounting.get("verdict") != "ok_dream7b_true_batch_hbm_load_accounting_contract":
            failures.append("dream7b_hbm_load_accounting_contract_not_ok")
        if hbm_accounting.get("per_segment_load_accounting_ready") is not True:
            failures.append("dream7b_hbm_per_segment_load_accounting_not_ready")
        if hbm_accounting.get("group_load_accounting_ready") is not True:
            failures.append("dream7b_hbm_group_load_accounting_not_ready")
        if hbm_accounting.get("prewarm_accounting_ready") is not True:
            failures.append("dream7b_hbm_prewarm_accounting_not_ready")
        if hbm_accounting.get("timing_summary_accounts_load_and_prewarm") is not True:
            failures.append("dream7b_hbm_timing_summary_accounting_not_ready")
        if hbm_accounting.get("prewarm_hbm_default_changed") is not False:
            failures.append("dream7b_hbm_prewarm_default_changed")
        if hbm_accounting.get("runtime_started") is not False:
            failures.append("dream7b_hbm_accounting_started_runtime")
        if hbm_accounting.get("compile_started") is not False:
            failures.append("dream7b_hbm_accounting_started_compile")
        for key in [
            "verdict",
            "primary_next_code_target",
            "final_logits_projection_saved_ms_per_request",
            "hbm_group_load_ms_per_request",
            "release_plus_unaccounted_group_gap_ms_per_request",
            "group_size_or_inner_order_current_primary_lever",
            "run_more_group_size_or_inner_order_sweeps_now",
            "projection_is_not_bpu_promotion_proof",
            "requires_real_runtime_result_before_promotion",
        ]:
            if bottleneck_closure.get(key) is None:
                failures.append(f"dream7b_bottleneck_closure_missing:{key}")
        if (
            bottleneck_closure.get("verdict")
            != "ok_dream7b_b4_bottleneck_closure_model"
        ):
            failures.append("dream7b_bottleneck_closure_model_not_ok")
        if (
            bottleneck_closure.get("primary_next_code_target")
            != "seg27_28_last_token_logits"
        ):
            failures.append("dream7b_bottleneck_closure_primary_target_unexpected")
        if (
            bottleneck_closure.get("group_size_or_inner_order_current_primary_lever")
            is not False
        ):
            failures.append("dream7b_bottleneck_closure_group_order_marked_primary")
        if (
            bottleneck_closure.get("run_more_group_size_or_inner_order_sweeps_now")
            is not False
        ):
            failures.append("dream7b_bottleneck_closure_more_group_sweeps_allowed")
        if bottleneck_closure.get("projection_is_not_bpu_promotion_proof") is not True:
            failures.append("dream7b_bottleneck_closure_projection_marked_proof")
        if (
            bottleneck_closure.get("requires_real_runtime_result_before_promotion")
            is not True
        ):
            failures.append("dream7b_bottleneck_closure_missing_runtime_gate")
        for key in [
            "verdict",
            "post_instrumentation_success_count",
            "post_instrumentation_telemetry_ready",
            "input_output_overhead_quantified",
            "do_not_claim_input_output_overhead_yet",
            "run_more_standard_b4_runtime_sweeps_now",
            "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available",
        ]:
            if post_instrumentation.get(key) is None:
                failures.append(f"dream7b_product_post_instrumentation_missing:{key}")
        if (
            post_instrumentation.get("post_instrumentation_telemetry_ready") is False
            and post_instrumentation.get("next_measurement_purpose") is None
        ):
            failures.append("dream7b_product_post_instrumentation_missing:next_measurement_purpose")
        if (
            post_instrumentation.get("post_instrumentation_telemetry_ready") is False
            and post_instrumentation.get("do_not_claim_input_output_overhead_yet") is not True
        ):
            failures.append("dream7b_product_post_instrumentation_overclaim_guard_missing")
        if post_instrumentation.get("run_more_standard_b4_runtime_sweeps_now") is not False:
            failures.append("dream7b_product_post_instrumentation_standard_sweep_allowed")
        for key in [
            "verdict",
            "input_prepare_ms_per_request",
            "output_postprocess_ms_per_request",
            "hidden_materialize_ms_per_request",
            "final_output_postprocess_ms_per_request",
            "final_excess_ms_per_request_vs_hidden",
            "input_prepare_primary_bottleneck",
            "output_postprocess_primary_bottleneck",
            "hidden_materialize_buffer_reuse_has_measured_ceiling",
            "final_logits_compute_still_primary",
            "final_logits_output_postprocess_not_primary",
            "next_local_runtime_code_target",
        ]:
            if post_overhead.get(key) is None:
                failures.append(f"dream7b_product_post_overhead_missing:{key}")
        if post_overhead.get("verdict") != "ok_dream7b_b4_post_instrumentation_overhead_analysis":
            failures.append("dream7b_product_post_overhead_verdict_not_ok")
        if post_overhead.get("input_prepare_primary_bottleneck") is not False:
            failures.append("dream7b_product_post_overhead_input_prepare_overstated")
        if post_overhead.get("final_logits_compute_still_primary") is not True:
            failures.append("dream7b_product_post_overhead_final_compute_not_primary")
        for key in [
            "verdict",
            "primary_single_segment_bottleneck",
            "final_compute_excess_ms_per_request",
            "top_group_by_segment_total",
            "top_group_contains_final_logits",
            "group_size_tuning_implication",
            "inner_order_tuning_implication",
            "next_code_target",
        ]:
            if post_segment.get(key) is None:
                failures.append(f"dream7b_product_post_segment_missing:{key}")
        if post_segment.get("verdict") != "ok_dream7b_b4_post_instrumentation_segment_attribution":
            failures.append("dream7b_product_post_segment_verdict_not_ok")
        if post_segment.get("primary_single_segment_bottleneck") != "seg27_28_final_logits":
            failures.append("dream7b_product_post_segment_unexpected_primary")
        if post_segment.get("group_size_tuning_implication") != "keep_existing_5_group_segment_major_default":
            failures.append("dream7b_product_post_segment_group_tuning_not_blocked")
        for key in [
            "verdict",
            "prealloc_ms_per_request_delta",
            "prealloc_hidden_materialize_ms_per_request_delta",
            "prealloc_reused_hidden_buffer_count",
            "hidden_buffer_reuse_default",
            "preallocate_hidden_experimental_flag_only",
            "do_not_start_new_preallocate_hidden_runtime_now",
            "reuse_buffer_implementation_measured_slower",
            "primary_target_remains_final_logits",
        ]:
            if hidden_buffer.get(key) is None:
                failures.append(f"dream7b_product_hidden_buffer_missing:{key}")
        if hidden_buffer.get("verdict") != "ok_dream7b_b4_hidden_buffer_reuse_decision":
            failures.append("dream7b_product_hidden_buffer_verdict_not_ok")
        if hidden_buffer.get("hidden_buffer_reuse_default") is not False:
            failures.append("dream7b_product_hidden_buffer_default_enabled")
        if hidden_buffer.get("reuse_buffer_implementation_measured_slower") is not True:
            failures.append("dream7b_product_hidden_buffer_not_marked_slower")
        for key in [
            "verdict",
            "queue_idle_at_probe",
            "no_true_batch_or_compile_process",
            "quick_ready_first_content_ms",
            "latest_text_queue_ms_per_request",
        ]:
            if queue_health.get(key) is None:
                failures.append(f"dream7b_product_queue_health_missing:{key}")
        if queue_health.get("verdict") != "ok_dream7b_queue_health_snapshot":
            failures.append("dream7b_product_queue_health_verdict_not_ok")
        if queue_health.get("queue_idle_at_probe") is not True:
            failures.append("dream7b_product_queue_health_not_idle")
        if queue_health.get("no_true_batch_or_compile_process") is not True:
            failures.append("dream7b_product_queue_health_true_batch_running")
        for key in [
            "verdict",
            "current_workstream",
            "queue_batch_work_duplicates_prior_true_batch_rental",
            "remote_b4_group_major_report_count",
            "local_b4_json_count",
            "do_not_start_standard_true_batch_runtime_now",
            "do_not_start_true_batch_compile_now",
        ]:
            if workstream_overlap.get(key) is None:
                failures.append(f"dream7b_product_workstream_overlap_missing:{key}")
        if workstream_overlap.get("verdict") != "ok_dream7b_workstream_overlap_audit":
            failures.append("dream7b_product_workstream_overlap_verdict_not_ok")
        if workstream_overlap.get("queue_batch_work_duplicates_prior_true_batch_rental") is not False:
            failures.append("dream7b_product_workstream_overlap_duplicate_not_rejected")
        if workstream_overlap.get("do_not_start_standard_true_batch_runtime_now") is not True:
            failures.append("dream7b_product_workstream_overlap_standard_runtime_not_blocked")
        for key in [
            "verdict",
            "preferred_group_policy",
            "preferred_inner_order",
            "primary_code_target",
            "next_s100p_runtime_experiment_allowed",
            "next_compile_allowed",
            "inner_order_decision",
            "group_count_decision",
            "final_logits_decision",
        ]:
            if tuning_matrix.get(key) is None:
                failures.append(f"dream7b_product_tuning_matrix_missing:{key}")
        if tuning_matrix.get("verdict") != "ok_dream7b_b4_tuning_decision_matrix":
            failures.append("dream7b_product_tuning_matrix_verdict_not_ok")
        if tuning_matrix.get("preferred_group_policy") != "keep_existing_5_group_segment_major_default":
            failures.append("dream7b_product_tuning_matrix_unexpected_group_policy")
        if tuning_matrix.get("preferred_inner_order") != "segment-major":
            failures.append("dream7b_product_tuning_matrix_unexpected_inner_order")
        if tuning_matrix.get("next_s100p_runtime_experiment_allowed") is not False:
            failures.append("dream7b_product_tuning_matrix_runtime_allowed")
        if tuning_matrix.get("next_compile_allowed") is not False:
            failures.append("dream7b_product_tuning_matrix_compile_allowed")
        for key in [
            "compile_ready",
            "readiness_blockers",
            "preflight_commit_headroom_gb",
            "latest_preflight_commit_headroom_deficit_gb",
            "largest_private_process",
        ]:
            if last_token.get(key) is None:
                failures.append(f"dream7b_product_last_token_compile_missing:{key}")
        for key in [
            "verdict",
            "commit_headroom_gb",
            "commit_headroom_deficit_gb",
            "projected_commit_headroom_after_reclaim_gb",
            "remaining_headroom_deficit_after_reclaim_gb",
            "recommended_additional_commit_limit_with_safety_gb",
            "do_not_start_compile_now",
        ]:
            if compile_capacity.get(key) is None:
                failures.append(f"dream7b_product_compile_capacity_missing:{key}")
        if last_token.get("compile_ready") is not False:
            failures.append("dream7b_product_last_token_compile_unexpected_ready")
        for key in [
            "verdict",
            "plan_generated_at",
            "validation_ready",
            "blockers",
            "manifest_ready",
            "queue_idle",
            "services_ready",
            "runtime_tools_ready",
            "lock_busy",
            "final_hbm_root_exists",
            "last_token_hbm_exists",
            "manifest_exists",
            "manifest_verified",
            "hbm_path",
        ]:
            if last_token_validation_plan.get(key) is None:
                failures.append(f"dream7b_last_token_validation_plan_missing:{key}")
        if (
            last_token_validation_plan.get("verdict")
            != "blocked_dream7b_b4_last_token_runtime_validation_plan"
        ):
            failures.append("dream7b_last_token_validation_plan_unexpected_verdict")
        if last_token_validation_plan.get("validation_ready") is not False:
            failures.append("dream7b_last_token_validation_unexpected_ready")
        if last_token_validation_plan.get("manifest_ready") is not False:
            failures.append("dream7b_last_token_validation_manifest_ready")
        if last_token_validation_plan.get("blockers") != ["last_token_manifest_not_ready"]:
            failures.append("dream7b_last_token_validation_unexpected_blockers")
        if last_token_validation_plan.get("queue_idle") is not True:
            failures.append("dream7b_last_token_validation_queue_not_idle")
        if last_token_validation_plan.get("services_ready") is not True:
            failures.append("dream7b_last_token_validation_services_not_ready")
        if last_token_validation_plan.get("runtime_tools_ready") is not True:
            failures.append("dream7b_last_token_validation_tools_not_ready")
        if last_token_validation_plan.get("lock_busy") is not False:
            failures.append("dream7b_last_token_validation_lock_busy")
        if last_token_validation_plan.get("final_hbm_root_exists") is not False:
            failures.append("dream7b_last_token_validation_final_hbm_root_exists")
        if last_token_validation_plan.get("last_token_hbm_exists") is not False:
            failures.append("dream7b_last_token_validation_hbm_exists")
        if last_token_validation_plan.get("manifest_exists") is not False:
            failures.append("dream7b_last_token_validation_manifest_exists")
        if last_token_validation_plan.get("manifest_verified") is not False:
            failures.append("dream7b_last_token_validation_manifest_verified")
        if (
            "true-batch-seq16-b4-last-token-final"
            not in str(last_token_validation_plan.get("hbm_path") or "")
        ):
            failures.append("dream7b_last_token_validation_hbm_path_unexpected")
        if (
            last_token_validation_compare.get("verdict")
            != "blocked_dream7b_b4_last_token_validation_compare_missing_result"
        ):
            failures.append("dream7b_last_token_compare_unexpected_verdict")
        if last_token_validation_compare.get("candidate_exists") is not False:
            failures.append("dream7b_last_token_compare_candidate_exists")
        if compile_capacity.get("do_not_start_compile_now") is not True:
            failures.append("dream7b_product_compile_capacity_start_not_blocked")
        if compile_command_guard.get("verdict") != "ok_dream7b_b4_compile_command_guard":
            failures.append("dream7b_compile_command_guard_not_ok")
        if compile_command_guard.get("compile_guard_active") is not True:
            failures.append("dream7b_compile_command_guard_inactive")
        if compile_command_guard.get("only_single_segment_last_token_compile_allowed") is not True:
            failures.append("dream7b_compile_command_guard_single_segment_not_enforced")
        if compile_command_guard.get("b8_full_compile_blocked") is not True:
            failures.append("dream7b_compile_command_guard_b8_full_not_blocked")
        if compile_command_guard.get("command_admitted") is not False:
            failures.append("dream7b_compile_command_guard_unexpected_admission")
        if compile_command_guard.get("would_start_compile") is not False:
            failures.append("dream7b_compile_command_guard_would_start_compile")
        if next_action_pack.get("verdict") != "ok_dream7b_b4_next_action_admission_pack":
            failures.append("dream7b_next_action_pack_not_ok")
        if next_action_pack.get("would_start_runtime") is not False:
            failures.append("dream7b_next_action_pack_would_start_runtime")
        if next_action_pack.get("would_start_compile") is not False:
            failures.append("dream7b_next_action_pack_would_start_compile")
        if next_action_pack.get("compile_preflight_only_allowed_now") is not True:
            failures.append("dream7b_next_action_pack_preflight_not_visible")
        if next_action_pack.get("queue_batch_product_work_allowed_now") is not True:
            failures.append("dream7b_next_action_pack_queue_work_not_allowed")
        for key in [
            "verdict",
            "remote_group_major_report_count",
            "remote_group_major_report_json_count",
            "remote_b4_group_major_report_count",
            "remote_b4_group_major_report_json_count",
            "local_b4_json_count",
            "b4_hbm_count",
            "b4_manifest_count",
            "b4_remote_json_local_count_match",
            "run_more_standard_b4_runtime_sweeps_now",
            "duplicate_stop_rules",
            "remaining_nonduplicate_work",
        ]:
            if nas_inventory.get(key) is None:
                failures.append(f"dream7b_product_nas_inventory_missing:{key}")
        if nas_inventory.get("remote_b4_group_major_report_count") != nas_inventory.get("local_b4_json_count"):
            failures.append("dream7b_product_nas_inventory_b4_mirror_mismatch")
        if nas_inventory.get("remote_b4_group_major_report_json_count") != nas_inventory.get("local_b4_json_count"):
            failures.append("dream7b_product_nas_inventory_b4_json_mirror_mismatch")
        if nas_inventory.get("b4_remote_json_local_count_match") is not True:
            failures.append("dream7b_product_nas_inventory_b4_json_match_not_true")
        if nas_inventory.get("b4_hbm_count") != 28 or nas_inventory.get("b4_manifest_count") != 28:
            failures.append("dream7b_product_nas_inventory_b4_hbm_incomplete")
        if nas_inventory.get("run_more_standard_b4_runtime_sweeps_now") is not False:
            failures.append("dream7b_product_nas_inventory_standard_sweeps_not_blocked")
        for key in [
            "verdict",
            "primary_runtime_refactor_target",
            "secondary_research_target",
            "current_preallocate_hidden_rejected_by_evidence",
            "preallocate_hidden_experimental_flag_only",
            "ready_local_refactor_count",
            "do_not_change_runtime_defaults_now",
            "do_not_start_s100p_runtime_now",
            "backlog_count",
            "top_backlog_items",
        ]:
            if refactor_backlog.get(key) is None:
                failures.append(f"dream7b_product_runtime_refactor_backlog_missing:{key}")
        if refactor_backlog.get("primary_runtime_refactor_target") != "final_logits_last_token_path":
            failures.append("dream7b_product_runtime_refactor_unexpected_primary")
        if refactor_backlog.get("do_not_change_runtime_defaults_now") is not True:
            failures.append("dream7b_product_runtime_refactor_defaults_not_blocked")
        if refactor_backlog.get("do_not_start_s100p_runtime_now") is not True:
            failures.append("dream7b_product_runtime_refactor_s100p_not_blocked")
        if refactor_source.get("verdict") != "ok_dream7b_b4_runtime_refactor_source_contract":
            failures.append("dream7b_runtime_refactor_source_contract_not_ok")
        if refactor_source.get("cli_defaults_preserved") is not True:
            failures.append("dream7b_runtime_refactor_source_defaults_not_preserved")
        if refactor_source.get("last_token_path_supported") is not True:
            failures.append("dream7b_runtime_refactor_source_last_token_missing")
        if refactor_source.get("telemetry_contract_ready") is not True:
            failures.append("dream7b_runtime_refactor_source_telemetry_missing")
        if refactor_source.get("protected_telemetry_fields_ready") is not True:
            failures.append("dream7b_runtime_refactor_source_protected_telemetry_not_ready")
        if int(refactor_source.get("protected_telemetry_field_count") or 0) < 22:
            failures.append("dream7b_runtime_refactor_source_protected_telemetry_field_count_low")
        if int(refactor_source.get("protected_telemetry_missing_count") or 0) != 0:
            failures.append("dream7b_runtime_refactor_source_protected_telemetry_missing")
        if refactor_source.get("runtime_order_changed") is not False:
            failures.append("dream7b_runtime_refactor_source_runtime_order_changed")
        if refactor_source.get("default_promotes_experimental_flags") is not False:
            failures.append("dream7b_runtime_refactor_source_experimental_defaulted")
        if runtime_source_map.get("verdict") != "ok_dream7b_b4_runtime_source_implementation_map":
            failures.append("dream7b_runtime_source_implementation_map_not_ok")
        if int(runtime_source_map.get("implementation_area_count") or 0) < 6:
            failures.append("dream7b_runtime_source_implementation_area_count_low")
        if int(runtime_source_map.get("source_pattern_count") or 0) < 40:
            failures.append("dream7b_runtime_source_pattern_count_low")
        if int(runtime_source_map.get("missing_source_pattern_count") or 0) != 0:
            failures.append("dream7b_runtime_source_patterns_missing")
        if runtime_source_map.get("primary_runtime_refactor_target") != "seg27_28_last_token_logits_or_output_avoidance":
            failures.append("dream7b_runtime_source_primary_target_unexpected")
        if runtime_source_map.get("primary_schedule_bottleneck") != "seg27_28_final_logits":
            failures.append("dream7b_runtime_source_primary_bottleneck_unexpected")
        if runtime_source_map.get("s100p_runtime_experiment_allowed_now") is not False:
            failures.append("dream7b_runtime_source_s100p_allowed")
        if runtime_source_map.get("compile_start_allowed_now") is not False:
            failures.append("dream7b_runtime_source_compile_start_allowed")
        if runtime_source_map.get("runtime_default_change_allowed_now") is not False:
            failures.append("dream7b_runtime_source_default_change_allowed")
        if runtime_source_map.get("standard_group_inner_order_sweeps_blocked") is not True:
            failures.append("dream7b_runtime_source_standard_sweeps_not_blocked")
        if runtime_source_map.get("runtime_compile_not_started") is not True:
            failures.append("dream7b_runtime_source_runtime_compile_started")
        if runtime_source_map.get("remote_access_not_performed") is not True:
            failures.append("dream7b_runtime_source_remote_access_performed")
        if runtime_source_map.get("failed_checks"):
            failures.append("dream7b_runtime_source_failed_checks")
        if refactor_admission.get("verdict") != "ok_dream7b_b4_runtime_refactor_admission_contract":
            failures.append("dream7b_runtime_refactor_admission_contract_not_ok")
        if refactor_admission.get("local_report_only_refactor_allowed_now") is not True:
            failures.append("dream7b_runtime_refactor_admission_report_only_not_allowed")
        if refactor_admission.get("default_runtime_code_change_allowed_now") is not False:
            failures.append("dream7b_runtime_refactor_admission_default_change_allowed")
        if refactor_admission.get("s100p_runtime_experiment_allowed_now") is not False:
            failures.append("dream7b_runtime_refactor_admission_s100p_allowed")
        if refactor_admission.get("compile_start_allowed_now") is not False:
            failures.append("dream7b_runtime_refactor_admission_compile_start_allowed")
        if refactor_admission.get("compile_preflight_only_allowed_now") is not True:
            failures.append("dream7b_runtime_refactor_admission_preflight_not_allowed")
        if refactor_admission.get("block_standard_group_or_inner_order_sweeps") is not True:
            failures.append("dream7b_runtime_refactor_admission_standard_sweeps_not_blocked")
        if refactor_admission.get("block_prewarm_or_cache_default") is not True:
            failures.append("dream7b_runtime_refactor_admission_cache_default_not_blocked")
        if refactor_admission.get("failed_checks"):
            failures.append("dream7b_runtime_refactor_admission_failed_checks")
        for key in [
            "guardrail_default_status_contract_ready",
            "guardrail_default_rollback_dry_run_ready",
            "gateway_listener_matches_systemd_main_pid",
            "gateway_listener_health_ok",
            "gateway_listener_drift_snapshot_ok",
            "gateway_listener_drift_live_matches_systemd_main_pid",
            "gateway_listener_drift_live_health_ok",
        ]:
            if product_evidence.get(key) is not True:
                failures.append(f"dream7b_product_guardrail_not_ready:{key}")
        if product_evidence.get("gateway_listener_ownership_verdict") != "ok_dream7b_gateway_listener_ownership":
            failures.append("dream7b_product_guardrail_not_ready:gateway_listener_ownership_verdict")
        if product_evidence.get("gateway_listener_drift_gate_verdict") != "ok_dream7b_gateway_listener_drift_gate":
            failures.append("dream7b_product_guardrail_not_ready:gateway_listener_drift_gate_verdict")
        if product_evidence.get("gateway_orphan_listener_detected") is not False:
            failures.append("dream7b_product_guardrail_not_ready:gateway_orphan_listener_detected")
        if product_evidence.get("gateway_listener_drift_live_orphan_detected") is not False:
            failures.append("dream7b_product_guardrail_not_ready:gateway_listener_drift_live_orphan_detected")
        if partial_batch_flush_ready is not True:
            failures.append("dream7b_partial_batch_flush_not_ready")
        if partial_batch_flush_probe_or_health_ready is not True:
            failures.append("dream7b_partial_batch_flush_probe_or_health_not_ready")
        if not partial_batch_flush_source:
            failures.append("dream7b_partial_batch_flush_readiness_source_missing")
        if per_run_evidence_matrix_verdict != "ok_dream7b_b4_per_run_evidence_matrix":
            failures.append("dream7b_per_run_evidence_matrix_not_ok")
        if per_run_evidence_matrix_top_segment != "seg27_final_logits":
            failures.append("dream7b_per_run_evidence_matrix_top_segment_unexpected")
        if float(per_run_evidence_matrix_top_segment_rate or 0.0) != 1.0:
            failures.append("dream7b_per_run_evidence_matrix_top_segment_rate_unexpected")
        if per_run_evidence_matrix_standard_sweep_status != "blocked_duplicate":
            failures.append("dream7b_per_run_evidence_matrix_standard_sweep_not_blocked")
    if dream7b_fast_path_report.get("found"):
        fast_cases = {str(case.get("id")): case for case in (dream7b_fast_path_report.get("payload") or {}).get("cases") or []}
        quick_ready = fast_cases.get("quick_ready") or {}
        quick_meta = quick_ready.get("dream7b_candidate") or {}
        if quick_meta.get("execution_path") != "gateway_fast_ready":
            failures.append("dream7b_quick_ready_path_not_visible")
        if quick_meta.get("backend_invoked") is not False:
            failures.append("dream7b_quick_ready_backend_invoked_not_false")
    if dream7b_guardrail_report.get("found"):
        guardrail = (dream7b_guardrail_report.get("payload") or {}).get("guardrail") or {}
        if guardrail.get("default_status_contract_ready") is not True:
            failures.append("dream7b_status_contract_not_ready")
        if guardrail.get("default_rollback_dry_run_ready") is not True:
            failures.append("dream7b_rollback_dry_run_not_ready")
    if dream7b_freshness_report.get("found"):
        freshness_payload = dream7b_freshness_report.get("payload") or {}
        freshness_decision = freshness_payload.get("decision") or {}
        freshness_checks = freshness_payload.get("checks") or {}
        if freshness_payload.get("failed_checks"):
            failures.append("dream7b_default_service_freshness_gate_failed_checks")
        if freshness_decision.get("queue_batch_service_remains_default") is not True:
            failures.append("dream7b_default_service_not_queue_batch")
        if freshness_decision.get("do_not_promote_true_batch") is not True:
            failures.append("dream7b_true_batch_promotion_not_blocked")
        if freshness_checks.get("nas_inventory_prevents_duplicate_sweeps") is not True:
            failures.append("dream7b_nas_inventory_duplicate_sweep_guard_missing")
        if freshness_checks.get("group_order_partition_prevents_duplicate_sweeps") is not True:
            failures.append("dream7b_group_order_partition_duplicate_sweep_guard_missing")
        if freshness_checks.get("scheduler_overhead_deprioritizes_python_gap_tuning") is not True:
            failures.append("dream7b_scheduler_overhead_gap_guard_missing")
        if freshness_checks.get("runtime_source_implementation_map_ok") is not True:
            failures.append("dream7b_runtime_source_map_freshness_guard_missing")
        if (
            freshness_checks.get(
                "runtime_source_implementation_map_blocks_runtime_compile_defaults"
            )
            is not True
        ):
            failures.append("dream7b_runtime_source_map_freshness_block_guard_missing")
    traceability_payload = traceability_report.get("payload") or {}
    traceability_summary = traceability_payload.get("summary") or {}
    if traceability_report.get("found") and not traceability_summary.get("objective_row_count"):
        failures.append("traceability_summary_missing_objective_rows")
    dependency_payload = dependency_report.get("payload") or {}
    dependency_summary = dependency_payload.get("summary") or {}
    if dependency_report.get("found") and not dependency_summary.get("dependency_count"):
        failures.append("dependency_summary_missing_dependency_count")
    runbook_payload = runbook_report.get("payload") or {}
    runbook_summary = runbook_payload.get("summary") or {}
    if runbook_report.get("found") and not runbook_summary.get("runbook_item_count"):
        failures.append("runbook_summary_missing_item_count")
    if runbook_report.get("found") and html_text.count('data-testid="runbook-row"') < 3:
        failures.append("runbook_rows_lt_3")
    for token in ["ai_nas_production_readiness_gate", "ai_nas_embedding_backend_readiness", "ai_nas_ocr_runtime_contract"]:
        if runbook_report.get("found") and token not in html_text:
            failures.append(f"runbook_verification_command_not_visible:{token}")
    for token in ["document_rag_ocr", "production_blockers_explicit"]:
        if traceability_report.get("found") and traceability_report.get("verdict") == "ok_ai_nas_objective_traceability_contract" and token not in html_text:
            failures.append(f"traceability_limited_row_not_visible:{token}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and validate a static AI-NAS operator portal contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "operator_portal_contract")
    if importlib.util.find_spec("PIL") is None:
        payload = {
            "generated_at": iso_now(),
            "tool_id": TOOL_ID,
            "verdict": "blocked_ai_nas_operator_portal_contract",
            "failures": ["missing_PIL_for_fixture_chat_screenshot"],
        }
        json_path = run_dir / "operator_portal_contract.json"
        md_path = run_dir / "operator_portal_contract.md"
        safe_write_json(json_path, payload)
        safe_write_text(md_path, "# AI-NAS Operator Portal Contract\n\n- verdict: `blocked_ai_nas_operator_portal_contract`\n")
        print(md_path)
        print(json_path)
        return 1

    personal_root = prepare_fixture(run_dir)
    sqlite_index_path = run_dir / "operator_portal_contract.sqlite3"
    case_packet = build_case_packet(personal_root, sqlite_index_path, 20)
    result_rows = user_facing_results(case_packet["matches"])
    approval_manifest = build_manifest(case_packet, personal_root, DEFAULT_COLLECTION)
    inbox_rows = build_inbox_rows(run_dir, approval_manifest)
    report_json_path = run_dir / "operator_portal_report.json"
    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    readiness_report = latest_report(evidence_roots, "production_readiness_gate.json")
    slo_report = latest_report(evidence_roots, "operational_slo_rollup_contract.json")
    traceability_report = latest_report(evidence_roots, "objective_traceability_contract.json")
    dependency_report = latest_report(evidence_roots, "production_dependency_bundle.json")
    runbook_report = latest_report(evidence_roots, "production_blocker_runbook_contract.json")
    soak_watcher_report = latest_report(evidence_roots, "soak_completion_gate_watcher_latest.json")
    dream7b_report = latest_report(evidence_roots, "dream7b_perf_identity.json")
    dream7b_product_report = latest_report(evidence_roots, "dream7b_product_decision_packet.json")
    dream7b_fast_path_report = latest_report(evidence_roots, "dream7b_fast_path_regression.json")
    dream7b_guardrail_report = latest_report(evidence_roots, "dream7b_product_guardrail_snapshot.json")
    dream7b_freshness_report = latest_report(evidence_roots, "dream7b_default_service_freshness_gate_latest.json")
    qwen25_report = latest_report(evidence_roots, "qwen25_ai_nas_acceptance.json")
    official_vision_report = latest_report(evidence_roots, "official_vision_route_packet.json")
    audit = {
        "source_files_modified": False,
        "real_personal_source_modified": False,
        "delete_performed": False,
        "move_performed": False,
        "overwrite_performed": False,
        "execution_performed": False,
        "all_operations_auditable": True,
    }
    report_payload = {
        "query": QUERY,
        "results": result_rows,
        "payment_nodes": case_packet["payment_nodes"],
        "copyable_organizing_suggestions": case_packet["copyable_organizing_suggestions"],
        "approval_manifest": approval_manifest,
        "approval_inbox": inbox_rows,
        "production_readiness": {key: value for key, value in readiness_report.items() if key != "payload"},
        "operational_slo": {key: value for key, value in slo_report.items() if key != "payload"},
        "objective_traceability": {key: value for key, value in traceability_report.items() if key != "payload"},
        "production_dependency_bundle": {key: value for key, value in dependency_report.items() if key != "payload"},
        "production_blocker_runbook": {key: value for key, value in runbook_report.items() if key != "payload"},
        "soak_completion_gate_watcher": {key: value for key, value in soak_watcher_report.items() if key != "payload"},
        "dream7b_interaction": {key: value for key, value in dream7b_report.items() if key != "payload"},
        "dream7b_product_decision_packet": {key: value for key, value in dream7b_product_report.items() if key != "payload"},
        "dream7b_fast_path_regression": {key: value for key, value in dream7b_fast_path_report.items() if key != "payload"},
        "dream7b_product_guardrail_snapshot": {key: value for key, value in dream7b_guardrail_report.items() if key != "payload"},
        "dream7b_default_service_freshness_gate": {key: value for key, value in dream7b_freshness_report.items() if key != "payload"},
        "official_qwen25_text_route": {key: value for key, value in qwen25_report.items() if key != "payload"},
        "official_s100_vision_route": {key: value for key, value in official_vision_report.items() if key != "payload"},
        "audit": audit,
    }
    safe_write_json(report_json_path, report_payload)
    html_text = render_portal(
        QUERY,
        result_rows,
        case_packet["payment_nodes"],
        case_packet["copyable_organizing_suggestions"],
        approval_manifest,
        inbox_rows,
        audit,
        report_json_path,
        readiness_report,
        slo_report,
        traceability_report,
        dependency_report,
        runbook_report,
        soak_watcher_report,
        dream7b_report,
        dream7b_product_report,
        dream7b_fast_path_report,
        dream7b_guardrail_report,
        dream7b_freshness_report,
    )
    official_route_html = f"""
    <section class="panel" id="official-route">
      <h2>Official Route</h2>
      <table>
        <tr><th>Qwen2.5 text route</th><td>{h(qwen25_report.get('verdict'))}</td></tr>
        <tr><th>Qwen2.5 evidence</th><td><code>{h(qwen25_report.get('path'))}</code></td></tr>
        <tr><th>Official S100 vision route</th><td>{h(official_vision_report.get('verdict'))}</td></tr>
        <tr><th>Official S100 vision evidence</th><td><code>{h(official_vision_report.get('path'))}</code></td></tr>
      </table>
      <p>Current product route: Qwen2.5 official text entry plus official S100 vision/Yolo evidence, with Dream7B retained only as historical runtime evidence.</p>
    </section>
    """
    html_text = html_text.replace("</main>", official_route_html + "\n</main>")
    html_path = run_dir / "operator_portal.html"
    safe_write_text(html_path, html_text)
    failures = evaluate_portal(
        html_text,
        result_rows,
        case_packet["payment_nodes"],
        case_packet["copyable_organizing_suggestions"],
        inbox_rows,
        audit,
        readiness_report,
        slo_report,
        traceability_report,
        dependency_report,
        runbook_report,
        soak_watcher_report,
        dream7b_report,
        dream7b_product_report,
        dream7b_fast_path_report,
        dream7b_guardrail_report,
        dream7b_freshness_report,
    )
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_operator_portal_contract" if not failures else "failed_ai_nas_operator_portal_contract",
        "scope": "static operator portal contract for search, evidence, report, approval, and audit entry",
        "portal_html": str(html_path),
        "portal_report_json": str(report_json_path),
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "summary": {
            "result_count": len(result_rows),
            "payment_node_count": len(case_packet["payment_nodes"]),
            "copy_suggestion_count": len(case_packet["copyable_organizing_suggestions"]),
            "approval_row_count": len(inbox_rows),
            "ready_approval_count": sum(1 for row in inbox_rows if row.get("risk_level") == "ready_for_operator_review"),
            "needs_repair_count": sum(1 for row in inbox_rows if row.get("risk_level") == "needs_manifest_repair"),
            "failure_count": len(failures),
            "execution_performed": False,
            "production_readiness_found": readiness_report.get("found"),
            "operational_slo_found": slo_report.get("found"),
            "objective_traceability_found": traceability_report.get("found"),
            "production_dependency_bundle_found": dependency_report.get("found"),
            "production_blocker_runbook_found": runbook_report.get("found"),
            "soak_completion_gate_watcher_found": soak_watcher_report.get("found"),
            "dream7b_interaction_found": dream7b_report.get("found"),
            "dream7b_product_decision_packet_found": dream7b_product_report.get("found"),
            "dream7b_fast_path_regression_found": dream7b_fast_path_report.get("found"),
            "dream7b_product_guardrail_snapshot_found": dream7b_guardrail_report.get("found"),
            "dream7b_default_service_freshness_gate_found": dream7b_freshness_report.get("found"),
            "official_qwen25_text_route_found": qwen25_report.get("found"),
            "official_s100_vision_route_found": official_vision_report.get("found"),
        },
        "requirements": {
            "single_entry_portal_html": html_path.exists(),
            "official_qwen25_text_route_visible": "Qwen2.5 text route" in html_text
            and "qwen25_ai_nas_acceptance.json" in html_text,
            "official_s100_vision_route_visible": "Official S100 vision route" in html_text
            and "official_vision_route_packet.json" in html_text,
            "query_visible": QUERY in html_text,
            "related_files_visible": html_text.count('data-testid="result-card"') >= 3,
            "evidence_visible": "Evidence" in html_text,
            "amount_date_payment_nodes_visible": "Payment Nodes" in html_text and len(case_packet["payment_nodes"]) >= 2,
            "copy_suggestions_visible": "Copy Suggestions" in html_text and bool(case_packet["copyable_organizing_suggestions"]),
            "approval_queue_visible": "Approval Queue" in html_text and len(inbox_rows) >= 2,
            "operator_decision_controls_visible": all(token in html_text for token in ['data-decision="approve"', "Rollback draft", "operator-decision-status"]),
            "one_click_report_visible": str(report_json_path) in html_text,
            "audit_visible": "Audit Status" in html_text,
            "production_readiness_visible": "Production Readiness" in html_text,
            "soak_completion_gate_watcher_visible": "Long Soak / Gate Watcher" in html_text,
            "dream7b_interaction_visible": "Dream7B Interaction" in html_text,
            "dream7b_first_response_warning_triage_visible": "first_response_warning_triage" in html_text
            and "first_response_warning_triaged" in html_text,
            "dream7b_service_guardrails_visible": "Dream7B Service Guardrails" in html_text,
            "dream7b_product_packet_visible": "dream7b_product_decision_packet" in html_text,
            "dream7b_runtime_experiment_gate_visible": "runtime_experiment_gate" in html_text
            and "s100p_runtime_experiment_now" in html_text
            and "runtime_gate_post_segment_blocks_standard_group_sweeps" in html_text
            and "runtime_gate_admission_evidence_ready" in html_text
            and "runtime_gate_admission_projected_saved_ms_per_request" in html_text
            and "runtime_gate_admission_standard_sweeps_blocked" in html_text
            and "runtime_command_guard" in html_text
            and "runtime_command_guard_standard_sweeps_blocked" in html_text
            and "runtime_command_guard_would_start_runtime" in html_text,
            "dream7b_segment_stability_audit_visible": "segment_stability_audit" in html_text
            and "stable_primary_bottleneck" in html_text
            and "do_not_run_hidden_order_sweeps_now" in html_text,
            "dream7b_segment_drag_breakdown_visible": "segment_drag_breakdown" in html_text
            and "segment_drag_final_vs_hidden_mean_ratio" in html_text
            and "segment_drag_top_group_by_accounted_ms" in html_text,
            "dream7b_group_order_partition_visible": "group_order_candidates" in html_text
            and "group_order_best_nonbaseline_delta_ms_per_request" in html_text
            and "group_partition_planner" in html_text
            and "group_partition_run_new_partition_now" in html_text
            and "group_inner_order_value_audit" in html_text
            and "group_inner_order_run_more_sweeps_now" in html_text
            and "group_inner_order_top_value_lever" in html_text,
            "dream7b_scheduler_overhead_visible": "group_switch_accounting" in html_text
            and "group_switch_gap_ms_per_request" in html_text
            and "scheduler_overhead_budget" in html_text
            and "deprioritize_python_inter_segment_gap_tuning" in html_text,
            "dream7b_runtime_instrumentation_visible": "runtime_instrumentation_contract" in html_text
            and "runtime_instrumentation_deployment" in html_text
            and "runtime_instrumentation_remote_probe_sha256" in html_text,
            "dream7b_hbm_load_accounting_visible": "hbm_load_accounting_contract" in html_text
            and "hbm_per_segment_load_accounting_ready" in html_text
            and "hbm_group_load_accounting_ready" in html_text
            and "hbm_prewarm_accounting_ready" in html_text
            and "hbm_timing_summary_accounts_load_and_prewarm" in html_text,
            "dream7b_bottleneck_closure_visible": "bottleneck_closure_model" in html_text
            and "bottleneck_closure_primary_next_code_target" in html_text
            and "bottleneck_closure_final_logits_projection_saved_ms_per_request"
            in html_text
            and "bottleneck_closure_projection_is_not_bpu_promotion_proof"
            in html_text,
            "dream7b_post_instrumentation_telemetry_gate_visible": "post_instrumentation_telemetry_gate" in html_text
            and "do_not_claim_input_output_overhead_yet" in html_text
            and "allow_one_post_instrumentation_baseline_measurement" in html_text,
            "dream7b_post_instrumentation_overhead_analysis_visible": "post_instrumentation_overhead_analysis" in html_text
            and "input_prepare_ms_per_request" in html_text
            and "hidden_materialize_ms_per_request" in html_text
            and "final_logits_compute_still_primary" in html_text,
            "dream7b_post_instrumentation_segment_attribution_visible": "post_instrumentation_segment_attribution" in html_text
            and "post_segment_primary_single_segment_bottleneck" in html_text
            and "post_segment_group_size_tuning_implication" in html_text
            and "post_segment_inner_order_tuning_implication" in html_text,
            "dream7b_segment_group_schedule_scorecard_visible": "segment_group_schedule_scorecard" in html_text
            and "segment_group_primary_schedule_bottleneck" in html_text
            and "segment_group_preferred_group_policy" in html_text
            and "segment_group_run_more_standard_sweeps_now" in html_text
            and "segment_group_run_s100p_runtime_now" in html_text
            and "segment_group_start_compile_now" in html_text,
            "dream7b_hidden_buffer_reuse_decision_visible": "hidden_buffer_reuse_decision" in html_text
            and "hidden_buffer_reuse_default" in html_text
            and "reuse_buffer_implementation_measured_slower" in html_text,
            "dream7b_last_token_compile_gate_visible": "last_token_compile_ready" in html_text
            and "compile_commit_headroom_gb" in html_text
            and "compile_do_not_start_compile_now" in html_text
            and "compile_command_guard" in html_text
            and "compile_command_guard_b8_full_compile_blocked" in html_text
            and "compile_command_guard_would_start_compile" in html_text
            and "next_action_admission_pack" in html_text
            and "next_action_would_start_runtime" in html_text
            and "next_action_would_start_compile" in html_text,
            "dream7b_last_token_candidate_visible": "last_token_candidate" in html_text
            and "last_token_readiness_verdict" in html_text
            and "last_token_remote_manifest_verified" in html_text,
            "dream7b_last_token_runtime_validation_visible": "last_token_validation_plan" in html_text
            and "last_token_validation_ready" in html_text
            and "last_token_validation_final_hbm_root_exists" in html_text
            and "last_token_validation_hbm_exists" in html_text
            and "last_token_validation_manifest_exists" in html_text
            and "last_token_validation_manifest_verified" in html_text
            and "last_token_validation_hbm_path" in html_text
            and "last_token_validation_compare" in html_text
            and "last_token_compare_decision" in html_text,
            "dream7b_true_batch_nas_inventory_visible": "true_batch_nas_inventory" in html_text
            and "nas_remote_b4_group_major_report_count" in html_text
            and "nas_remote_b4_group_major_report_json_count" in html_text
            and "nas_b4_remote_json_local_count_match" in html_text
            and "nas_run_more_standard_b4_runtime_sweeps_now" in html_text
            and "nas_duplicate_stop_rules" in html_text,
            "dream7b_runtime_refactor_backlog_visible": "runtime_refactor_backlog" in html_text
            and "runtime_refactor_primary_target" in html_text
            and "runtime_refactor_rank1_projected_saved_ms_per_request" in html_text
            and "runtime_refactor_rank1_not_bpu_promotion_proof" in html_text
            and "runtime_refactor_rank1_blocks_standard_sweeps" in html_text
            and "runtime_refactor_do_not_change_defaults_now" in html_text
            and "runtime_refactor_do_not_start_s100p_now" in html_text
            and "runtime_refactor_source_contract" in html_text
            and "runtime_refactor_source_cli_defaults_preserved" in html_text
            and "runtime_refactor_source_last_token_path_supported" in html_text
            and "runtime_refactor_source_telemetry_contract_ready" in html_text
            and "runtime_refactor_admission_contract" in html_text
            and "runtime_refactor_admission_local_report_only_allowed_now" in html_text
            and "runtime_refactor_admission_default_runtime_change_allowed_now" in html_text
            and "runtime_refactor_admission_s100p_runtime_allowed_now" in html_text,
            "dream7b_default_service_freshness_gate_visible": "dream7b_default_service_freshness_gate" in html_text,
            "dream7b_default_service_decision_visible": "queue_batch_service_remains_default" in html_text
            and "do_not_promote_true_batch" in html_text
            and "group_order_partition_prevents_duplicate_sweeps" in html_text
            and "scheduler_overhead_deprioritizes_python_gap_tuning" in html_text,
            "dream7b_queue_health_snapshot_visible": "queue_health_snapshot" in html_text
            and "queue_health_no_true_batch_or_compile_process" in html_text
            and "queue_health_latest_text_queue_ms_per_request" in html_text,
            "dream7b_workstream_overlap_audit_visible": "workstream_overlap_audit" in html_text
            and "workstream_queue_work_duplicates_true_batch_rental" in html_text
            and "workstream_b4_records" in html_text,
            "dream7b_tuning_decision_matrix_visible": "tuning_decision_matrix" in html_text
            and "tuning_preferred_group_policy" in html_text
            and "tuning_preferred_inner_order" in html_text
            and "tuning_primary_code_target_projected_saved_ms_per_request" in html_text
            and "tuning_standard_sweeps_blocked_by_final_logits_leverage" in html_text,
            "dream7b_final_logits_leverage_visible": "final_logits_leverage_model" in html_text
            and "final_logits_leverage_projection_saved_ms_per_request" in html_text
            and "final_logits_leverage_not_bpu_promotion_proof" in html_text,
            "dream7b_fast_ready_visible": "gateway_fast_ready" in html_text,
            "dream7b_rollback_contract_visible": "default_rollback_dry_run_ready" in html_text,
            "dream7b_gateway_listener_match_visible": "gateway_listener_matches_systemd_main_pid" in html_text,
            "dream7b_gateway_orphan_listener_visible": "gateway_orphan_listener_detected" in html_text,
            "dream7b_gateway_listener_drift_gate_visible": "gateway_listener_drift_gate" in html_text,
            "dream7b_gateway_listener_drift_match_visible": "gateway_listener_drift_live_matches_systemd_main_pid"
            in html_text,
            "operational_slo_visible": "Operational SLO" in html_text,
            "slo_limited_evidence_triage_visible": "slo_limited_evidence_triage" in html_text
            and "slo_limited_evidence_release_blocker" in html_text,
            "objective_traceability_visible": "Objective Traceability" in html_text,
            "production_dependency_bundle_visible": "Dependency Bundle" in html_text,
            "production_blocker_runbook_visible": "Production Runbook" in html_text,
            "no_execution": not audit["execution_performed"],
        },
        "production_readiness": {key: value for key, value in readiness_report.items() if key != "payload"},
        "operational_slo": {key: value for key, value in slo_report.items() if key != "payload"},
        "objective_traceability": {key: value for key, value in traceability_report.items() if key != "payload"},
        "production_dependency_bundle": {key: value for key, value in dependency_report.items() if key != "payload"},
        "production_blocker_runbook": {key: value for key, value in runbook_report.items() if key != "payload"},
        "soak_completion_gate_watcher": {key: value for key, value in soak_watcher_report.items() if key != "payload"},
        "dream7b_interaction": {key: value for key, value in dream7b_report.items() if key != "payload"},
        "dream7b_product_decision_packet": {key: value for key, value in dream7b_product_report.items() if key != "payload"},
        "dream7b_fast_path_regression": {key: value for key, value in dream7b_fast_path_report.items() if key != "payload"},
        "dream7b_product_guardrail_snapshot": {key: value for key, value in dream7b_guardrail_report.items() if key != "payload"},
        "dream7b_default_service_freshness_gate": {key: value for key, value in dream7b_freshness_report.items() if key != "payload"},
        "official_qwen25_text_route": {key: value for key, value in qwen25_report.items() if key != "payload"},
        "official_s100_vision_route": {key: value for key, value in official_vision_report.items() if key != "payload"},
        "failures": failures,
        "audit": {
            **audit,
            "network_call_performed": False,
            "service_started": False,
            "writes": "bounded fixture files, SQLite index/image_embeddings rows, static HTML portal, Markdown/JSON portal reports",
        },
        "production_gap": "Production still needs a live web/chat surface backed by the mounted NAS and OpenClaw session auth; this contract verifies the required user-facing information model.",
    }
    json_path = run_dir / "operator_portal_contract.json"
    md_path = run_dir / "operator_portal_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Operator Portal Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- portal_html: `{html_path}`",
        f"- result_count: `{payload['summary']['result_count']}`",
        f"- payment_node_count: `{payload['summary']['payment_node_count']}`",
        f"- copy_suggestion_count: `{payload['summary']['copy_suggestion_count']}`",
        f"- approval_row_count: `{payload['summary']['approval_row_count']}`",
        f"- failures: `{failures}`",
        "- policy: static bounded portal only; no execution, network call, service start, delete, move, or overwrite",
        "",
        "## Requirement Checks",
        "",
    ]
    for key, value in payload["requirements"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
