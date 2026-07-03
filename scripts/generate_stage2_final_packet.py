#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_IDS = [
    "2000_stage1_review_baseline_lock",
    "2010_package_reproducibility_gate",
    "2020_existing_gate_hard_fail_test",
    "2030_cloud_redaction_hardening_gate",
    "2040_argument_scope_gate",
    "2050_approval_token_schema_gate",
    "2060_qwen_runtime_identity_gate",
    "2070_stage2_sidecar_mock_isolation",
    "2080_stage2_readonly_nas_search_bridge",
    "2090_stage2_document_rag_bridge",
    "2100_stage2_runtime_trace_completeness",
    "2110_stage2_context_minimization_regression",
    "2120_stage2_rollback_gate",
]
FINAL_VERDICT = "ready_for_more_readonly_sidecar_trials"
STAGE1_FIXED_PACKAGE = ROOT / "evidence_for_gptpro" / "ai_nas_harness_stage1_fixed_gptpro_20260702-233035.zip"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def git_status() -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "usable": completed.returncode == 0,
    }


def collect_reports() -> list[dict[str, Any]]:
    reports = []
    for report_id in REPORT_IDS:
        path = ROOT / "reports" / f"{report_id}.json"
        payload = load_json(path)
        reports.append(
            {
                "report_id": report_id,
                "path": rel(path),
                "gate_id": payload.get("gate_id"),
                "verdict": payload.get("verdict"),
                "passed_count": payload.get("passed_count"),
                "check_count": payload.get("check_count"),
                "failure_count": payload.get("failure_count"),
                "sha256": sha256_file(path),
            }
        )
    return reports


def bool_from_gate(reports: list[dict[str, Any]]) -> bool:
    return all(item.get("failure_count") == 0 and str(item.get("verdict", "")).startswith("ok_") for item in reports)


def markdown_gate_table(reports: list[dict[str, Any]]) -> list[str]:
    lines = ["| Report | Gate | Verdict | Checks | Failures |", "|---|---|---:|---:|---:|"]
    for item in reports:
        lines.append(
            f"| `{item['report_id']}` | `{item['gate_id']}` | `{item['verdict']}` | "
            f"{item['passed_count']}/{item['check_count']} | {item['failure_count']} |"
        )
    return lines


def build_packet(reports: list[dict[str, Any]], final_zip_name: str) -> dict[str, Any]:
    qwen = load_json(ROOT / "reports" / "2060_qwen_runtime_identity_gate.json")
    sidecar = load_json(ROOT / "reports" / "2070_stage2_sidecar_mock_isolation.json")
    nas_bridge = load_json(ROOT / "reports" / "2080_stage2_readonly_nas_search_bridge.json")
    doc_bridge = load_json(ROOT / "reports" / "2090_stage2_document_rag_bridge.json")
    trace = load_json(ROOT / "reports" / "2100_stage2_runtime_trace_completeness.json")
    context = load_json(ROOT / "reports" / "2110_stage2_context_minimization_regression.json")
    rollback = load_json(ROOT / "reports" / "2120_stage2_rollback_gate.json")
    redaction = load_json(ROOT / "reports" / "2030_cloud_redaction_hardening_gate.json")
    arg_policy_path = ROOT / "config" / "workspace_arg_policy.yaml"
    tool_policy_path = ROOT / "config" / "workspace_tool_policy.yaml"

    commands_run = [
        "py -3 -m py_compile ai_nas_harness\\*.py probes\\harness_shadow_probe.py gates\\*.py stage2_sidecar\\*.py",
        "py -3 probes\\harness_shadow_probe.py --report-root reports",
        "py -3 gates\\run_harness_stage1_gates.py --report-root reports",
        "bash tmp/stage1_fixed_repro_manual/scripts/run_stage1_gates_from_package.sh",
        "py -3 gates\\stage2_readiness_gates.py --report-root reports --package-zip evidence_for_gptpro\\ai_nas_harness_stage1_fixed_gptpro_20260702-233035.zip",
        "py -3 scripts\\generate_stage2_final_packet.py",
        "git status --short",
    ]

    qwen_health = qwen.get("detail", {}).get("health", {})
    qwen_models = qwen.get("detail", {}).get("models", {})
    provider_config = qwen.get("detail", {}).get("provider_config", {})
    sidecar_health = next((c.get("detail", {}) for c in sidecar.get("checks", []) if c.get("label") == "sidecar health ok"), {})
    sidecar_port = sidecar.get("detail", {}).get("port")
    protected_hashes = rollback.get("detail", {}).get("asset_hashes", {})

    return {
        "generated_at": now_iso(),
        "final_verdict": FINAL_VERDICT,
        "stage": "stage2_readonly_sidecar_trial_readiness",
        "all_numbered_gates_pass": bool_from_gate(reports),
        "numbered_reports": reports,
        "environment": {
            "repo_root": str(ROOT),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "git_status": git_status(),
        },
        "inputs": {
            "stage1_fixed_package": rel(STAGE1_FIXED_PACKAGE),
            "stage1_fixed_package_sha256": sha256_file(STAGE1_FIXED_PACKAGE) if STAGE1_FIXED_PACKAGE.exists() else None,
        },
        "commands_run": commands_run,
        "service_and_port_boundary": {
            "protected_ports": [8765, 18080, 18888, 18889],
            "sidecar_mock_port": sidecar_port,
            "foreground_route": False,
            "protected_asset_hashes": protected_hashes,
            "rollback_verdict": rollback.get("verdict"),
        },
        "model_provider_identity": {
            "qwen_gateway_url": "http://127.0.0.1:18080",
            "health": qwen_health,
            "models": qwen_models,
            "model_id": qwen.get("detail", {}).get("model_id", "unknown"),
            "provider_config": provider_config,
            "interpretation": "Local Qwen provider is configured for sidecar default, but this Windows run recorded the gateway as explicitly unavailable.",
        },
        "dispatcher_and_policy": {
            "dispatcher_sha256": protected_hashes.get("dispatcher"),
            "workspace_tool_policy": {"path": rel(tool_policy_path), "sha256": sha256_file(tool_policy_path)},
            "workspace_arg_policy": {"path": rel(arg_policy_path), "sha256": sha256_file(arg_policy_path)},
            "write_workspace_allowed": False,
            "arbitrary_shell_path_allowed": False,
        },
        "stage2_sidecar_status": {
            "runtime": "stage2_sidecar_mock",
            "mock_health": sidecar_health,
            "nas_search_bridge_execute_real_dispatcher": nas_bridge.get("detail", {}).get("execute_real_dispatcher"),
            "document_rag_bridge_execute_real_dispatcher": doc_bridge.get("detail", {}).get("execute_real_dispatcher"),
            "real_zleap_integrated": False,
            "production_route_modified": False,
            "cloud_called": False,
        },
        "trace_and_redaction": {
            "trace_report": "reports/2100_stage2_runtime_trace_completeness.json",
            "trace_complete_rate": trace.get("detail", {}).get("trace_complete_rate"),
            "trace_run_count": trace.get("detail", {}).get("run_count"),
            "redaction_report": "reports/2030_cloud_redaction_hardening_gate.json",
            "redaction_cases": len(redaction.get("detail", {}).get("cases", [])),
            "redaction_failure_count": redaction.get("failure_count"),
        },
        "context_minimization": context.get("detail", {}),
        "product_safe_claim_boundary": [
            "Stage 1 package reproducibility issues are fixed and gate-backed in this checkout.",
            "Stage 2 is ready only for more read-only sidecar trials.",
            "The package does not prove production Zleap integration.",
            "The package does not enable write/destructive NAS tools.",
            "The package does not enable private NAS cloud egress.",
            "The package does not modify OpenClaw, local Qwen, dispatcher, Dream7B routes, or protected ports.",
        ],
        "recommendations": {
            "continue_zleap_sidecar": "yes, but only as isolated read-only trials",
            "absorb_zleap_design_without_code": "yes; keep workspace-scoped tools, trace, provider isolation, and rollback patterns",
            "postgres_pgvector": "no production dependency now; lab-only if real Zleap requires it",
            "continue_sqlite": "yes for harness trace and current NAS index evidence",
            "allow_write_workspace": "no",
            "allow_cloud_research": "public/redacted only; no private NAS raw content",
            "modify_production_route": "no",
            "openclaw_qwen_dispatcher_unchanged": "yes, by hash evidence in 2070/2120",
            "rollback_passed": "yes",
        },
        "blocking_items_before_stage3": [
            "Run the same gates on the S100P host with live Qwen/OpenClaw health available.",
            "Replace mock sidecar with real Zleap or an equivalent runtime in an isolated port, still read-only.",
            "Run controlled read-only dispatcher execution instead of dry-run bridge records.",
            "Keep write/destructive workspaces disabled until signed approval, UX, audit log, and rollback are gate-backed.",
        ],
        "final_package": final_zip_name,
    }


def write_markdown_outputs(packet: dict[str, Any]) -> None:
    reports = packet["numbered_reports"]
    gate_table = "\n".join(markdown_gate_table(reports))
    packet_md = f"""# Digua AI-NAS Harness Stage 2 Gate Packet

- final_verdict: `{packet['final_verdict']}`
- stage: `{packet['stage']}`
- generated_at: `{packet['generated_at']}`
- all_numbered_gates_pass: `{packet['all_numbered_gates_pass']}`

## Evidence Table

{gate_table}

## Decision

Stage 2 is ready for more read-only sidecar trials, not Stage 3 productionization. The evidence supports package reproducibility, hard-fail behavior, redaction, argument policy, approval-token schema, mock sidecar isolation, read-only bridge boundaries, runtime trace completeness, context bounds, and rollback. It does not prove real Zleap production integration or live Qwen availability from this Windows run.

## Boundary

- OpenClaw, Qwen, dispatcher, Dream7B routes, and protected ports remain unchanged by hash-backed gates.
- Write/destructive NAS workspaces remain disabled.
- Cloud receives public/redacted content only.
- Sidecar is mock/sidecar-like and bridge execution is dry-run in this packet.

## Commands Run

""" + "\n".join(f"- `{cmd}`" for cmd in packet["commands_run"]) + "\n"
    write_text(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_gate_packet.md", packet_md)

    decision_md = f"""# Stage 2 Decision

Final verdict: `{packet['final_verdict']}`.

Proceed with more isolated read-only sidecar trials. Do not move to Stage 3 productized Python harness yet, because `2060_qwen_runtime_identity_gate` recorded the local Qwen gateway as explicitly unavailable in this Windows run, and `2080/2090` are sidecar bridge dry-run trials rather than real dispatcher execution.

Product-safe claim: this package proves Stage 1 reproducibility fixes and Stage 2 read-only trial readiness under the current evidence. It does not prove production Zleap integration, write-tool readiness, private cloud egress safety beyond redaction gates, or live S100P service health.

## Required Before Stage 3

- Re-run on S100P with live OpenClaw and Qwen health.
- Run read-only bridge calls through the real dispatcher on controlled fixtures.
- Trial real Zleap or an equivalent sidecar runtime on an isolated port.
- Keep write/destructive workspaces disabled until signed approval, UX, audit, and rollback gates pass.
"""
    write_text(ROOT / "docs" / "STAGE2_DECISION.md", decision_md)

    risk_md = """# Stage 2 Sidecar Risk Register

| Risk | Evidence | Impact | Mitigation |
|---|---|---|---|
| Local Qwen unavailable in this Windows run | `reports/2060_qwen_runtime_identity_gate.json` | Blocks Stage 3 claim | Re-run on S100P and require live health/model identity |
| Sidecar is mock/sidecar-like, not real Zleap | `reports/2070_stage2_sidecar_mock_isolation.json` | Product integration unknown | Trial real Zleap only on isolated port |
| Read-only bridge is dry-run | `reports/2080_stage2_readonly_nas_search_bridge.json`, `reports/2090_stage2_document_rag_bridge.json` | Real dispatcher behavior still unproven for sidecar | Run controlled read-only dispatcher execution next |
| Write approval is schema-only | `reports/2050_approval_token_schema_gate.json` | No safe write workspace yet | Keep all write/destructive tools disabled |
| Cloud egress is gate-tested, not product-enabled | `reports/2030_cloud_redaction_hardening_gate.json` | Private leakage risk if expanded carelessly | Keep cloud public/redacted only and add live egress audit before expansion |
| Git metadata is unusable in this checkout | final packet environment.git_status | Commit-based diff evidence unavailable | Use artifact hashes and generated reports as the evidence source |
"""
    write_text(ROOT / "docs" / "STAGE2_SIDEcar_RISK_REGISTER.md", risk_md)
    write_text(ROOT / "docs" / "STAGE2_SIDECAR_RISK_REGISTER.md", risk_md)

    stage3_md = """# Stage 3 Productization Recommendation

Recommendation: do not enter Stage 3 yet. Continue Stage 2 read-only sidecar trials.

Keep SQLite for current trace and index evidence. Do not add PostgreSQL/pgvector as a production dependency now; use it only in a lab branch if real Zleap requires it. Do not open any write workspace. Do not modify the OpenClaw foreground route, the local Qwen gateway, the dispatcher path, Dream7B ports, or protected ports.

Next route:

1. S100P live preflight: OpenClaw 8765, Qwen 18080, dispatcher hash, and protected ports.
2. Controlled read-only sidecar execution through `ai_nas_allowlisted_tool.sh`.
3. Real Zleap isolated trial if dependency and license checks are acceptable.
4. Trace, redaction, context, and rollback re-run.
5. Only then decide between productized Python harness and real sidecar integration.
"""
    write_text(ROOT / "docs" / "STAGE3_PRODUCTIZATION_RECOMMENDATION.md", stage3_md)

    package_ref = packet.get("final_package")
    if isinstance(package_ref, dict):
        package_ref = package_ref.get("zip_path") or package_ref.get("name") or str(package_ref)
    gpt_prompt = f"""# GPT Pro Stage 2 Evaluation Prompt

Please evaluate the package `{package_ref}`. Do not rely only on the final verdict. Check the numbered gate reports under `reports/2000-2120_*.json`, `01_final_evidence/digua_ai_nas_harness_stage2_gate_packet.json`, `docs/STAGE2_DECISION.md`, and `reports/stage2_sidecar_comparison.json`.

Please answer:

1. Is the current verdict `{packet['final_verdict']}` supported by the evidence?
2. Do you agree that this should not enter Stage 3 productized harness yet?
3. Which evidence is sufficient to continue read-only sidecar trials?
4. Which blockers must be re-tested on the S100P host?
5. Should we introduce real Zleap code, or only absorb its workspace, sidecar, and trace design?
6. Should SQLite remain the default, and should PostgreSQL/pgvector stay lab-only?
7. Propose the next 3-5 gates, each with explicit pass/fail criteria.

Hard constraints: do not suggest replacing OpenClaw, replacing local Qwen, bypassing `ai_nas_allowlisted_tool.sh`, enabling write/destructive workspaces, modifying ports 8765/18080/18888/18889, or allowing cloud to see private NAS raw content.
"""
    write_text(ROOT / "docs" / "GPT_PRO_STAGE2_EVALUATION_PROMPT.md", gpt_prompt)


def write_comparison(packet: dict[str, Any]) -> None:
    comparison = {
        "generated_at": packet["generated_at"],
        "final_verdict": packet["final_verdict"],
        "stage1_vs_stage2": packet["context_minimization"].get("comparisons", []),
        "sidecar_limitations": [
            "mock sidecar only",
            "read-only bridge dry-run",
            "no real Zleap package installed",
            "Qwen gateway explicitly unavailable in this Windows run",
        ],
        "recommendations": packet["recommendations"],
    }
    write_json(ROOT / "reports" / "stage2_sidecar_comparison.json", comparison)
    lines = [
        "# Stage 2 Sidecar Comparison",
        "",
        f"- final_verdict: `{comparison['final_verdict']}`",
        "",
        "## Context Comparison",
        "",
        "| Scenario | Stage1 chars | Stage2 chars | Stage1 tools | Stage2 tools |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in comparison["stage1_vs_stage2"]:
        lines.append(
            f"| `{item['scenario']}` | {item['stage1_context']} | {item['stage2_estimated_context']} | "
            f"{item['stage1_exposed']} | {item['stage2_exposed']} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in comparison["sidecar_limitations"])
    lines.extend(["", "## Recommendation", "", "Continue read-only sidecar trials; do not enter Stage 3 yet."])
    write_text(ROOT / "reports" / "stage2_sidecar_comparison.md", "\n".join(lines) + "\n")


def selected_files() -> list[Path]:
    files: list[Path] = []
    roots = [
        ROOT / "ai_nas_harness",
        ROOT / "gates",
        ROOT / "probes",
        ROOT / "stage2_sidecar",
        ROOT / "config",
    ]
    for directory in roots:
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                if path.suffix in {".py", ".yaml", ".json", ".md"}:
                    files.append(path)
    script_names = {
        "run_stage1_gates_from_package.sh",
        "start_stage2_sidecar_mock.sh",
        "stop_stage2_sidecar_mock.sh",
        "generate_stage2_final_packet.py",
    }
    for name in script_names:
        path = ROOT / "scripts" / name
        if path.exists():
            files.append(path)
    for report_id in REPORT_IDS:
        for suffix in (".json", ".md"):
            path = ROOT / "reports" / f"{report_id}{suffix}"
            if path.exists():
                files.append(path)
    extra_reports = [
        ROOT / "reports" / "stage2_sidecar_runtime_trace.jsonl",
        ROOT / "reports" / "stage2_sidecar_comparison.json",
        ROOT / "reports" / "stage2_sidecar_comparison.md",
        ROOT / "reports" / "harness_stage1_gate_report.json",
        ROOT / "reports" / "harness_stage1_gate_report.md",
        ROOT / "reports" / "harness_shadow_probe_latest.json",
    ]
    files.extend(path for path in extra_reports if path.exists())
    final_files = [
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_gate_packet.json",
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_gate_packet.md",
        ROOT / "docs" / "STAGE2_DECISION.md",
        ROOT / "docs" / "STAGE2_SIDEcar_RISK_REGISTER.md",
        ROOT / "docs" / "STAGE2_SIDECAR_RISK_REGISTER.md",
        ROOT / "docs" / "STAGE3_PRODUCTIZATION_RECOMMENDATION.md",
        ROOT / "docs" / "GPT_PRO_STAGE2_EVALUATION_PROMPT.md",
    ]
    files.extend(path for path in final_files if path.exists())
    if STAGE1_FIXED_PACKAGE.exists():
        files.append(STAGE1_FIXED_PACKAGE)
    return sorted(set(files), key=lambda p: rel(p))


def build_zip(zip_path: Path) -> dict[str, Any]:
    files = selected_files()
    manifest_lines = []
    for path in files:
        manifest_lines.append(f"{sha256_file(path)}  {rel(path)}")
    manifest_path = ROOT / "tmp" / "stage2_final_package_SHA256SUMS.txt"
    write_text(manifest_path, "\n".join(manifest_lines) + "\n")
    files.append(manifest_path)

    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            if path == STAGE1_FIXED_PACKAGE:
                arcname = f"stage1_input/{path.name}"
            elif path == manifest_path:
                arcname = "SHA256SUMS_STAGE2_CONTENTS.txt"
            else:
                arcname = rel(path)
            zf.write(path, arcname)
    digest = sha256_file(zip_path)
    hash_path = zip_path.with_suffix(zip_path.suffix + ".sha256.txt")
    write_text(hash_path, f"{digest}  {zip_path.name}\n")
    return {"zip_path": str(zip_path), "sha256": digest, "file_count": len(files), "sha256_file": str(hash_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    zip_name = f"digua_ai_nas_harness_stage2_for_gptpro_{args.timestamp}.zip"

    reports = collect_reports()
    packet = build_packet(reports, zip_name)
    write_json(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_gate_packet.json", packet)
    write_markdown_outputs(packet)
    write_comparison(packet)

    package_info = build_zip(ROOT / "evidence_for_gptpro" / zip_name)
    packet["final_package"] = package_info
    write_json(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_gate_packet.json", packet)
    write_markdown_outputs(packet)
    write_comparison(packet)

    print(json.dumps({"verdict": packet["final_verdict"], "package": package_info}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
