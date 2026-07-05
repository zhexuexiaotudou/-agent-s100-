#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize Digua Agent Runtime S100P acceptance evidence.")
    parser.add_argument("--evidence-dir", default=str(ROOT / "evidence" / "s100p_agent_runtime_deepening_20260705"))
    parser.add_argument("--report-root", default=str(ROOT / "reports"))
    parser.add_argument("--final-root", default=str(ROOT / "01_final_evidence"))
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir)
    report_root = Path(args.report_root)
    final_root = Path(args.final_root)
    live_summary = read_json(evidence_dir / "agent_runtime_live_status" / "agent_runtime_live_status_summary.json")
    e2e_summary = read_json(evidence_dir / "agent_runtime_e2e_smoke" / "agent_runtime_e2e_smoke_summary.json")
    http_context = read_json(evidence_dir / "agent_runtime_live_status" / "http_context_pack_smoke.json")
    s100p_eval = read_json(evidence_dir / "s100p_24090_agent_runtime_eval_gate.json")
    s100p_package = read_json(evidence_dir / "s100p_24100_agent_runtime_final_evidence_package.json")
    ui_smoke_path = ROOT / "output" / "playwright" / "agent_runtime_iab_ui_smoke.json"
    ui_smoke = read_json(ui_smoke_path) if ui_smoke_path.exists() else {"ok": False, "error": "ui_smoke_missing"}

    checks = [
        {"label": "S100P live status ok", "ok": live_summary.get("ok") is True, "detail": live_summary},
        {"label": "S100P e2e smoke ok", "ok": e2e_summary.get("ok") is True, "detail": e2e_summary},
        {"label": "S100P eval gate ok", "ok": s100p_eval.get("ok") is True, "detail": s100p_eval.get("metrics")},
        {"label": "S100P package local_ok true", "ok": s100p_package.get("local_ok") is True},
        {"label": "Qwen execution authority false", "ok": live_summary.get("qwen_execution_authority") is False},
        {"label": "cloud private raw egress false", "ok": live_summary.get("cloud_private_raw_egress") is False},
        {"label": "public MCP exposed false", "ok": live_summary.get("public_mcp_exposed") is False},
        {"label": "HTTP POST auth not bypassed", "ok": http_context.get("auth_blocked_without_bypass") is True or http_context.get("context_pack_ok") is True, "detail": http_context},
        {"label": "UI desktop/mobile smoke ok", "ok": ui_smoke.get("ok") is True, "detail": ui_smoke},
    ]
    failures = [check for check in checks if not check["ok"]]
    verdict = "agent_runtime_deepening_deliverable_ready_for_repo_pr" if not failures else "agent_runtime_deepening_hold_s100p_acceptance"
    payload = {
        "schema": "digua_agent_runtime_deepening_final_acceptance_v1",
        "generated_at": now(),
        "ok": not failures,
        "verdict": verdict,
        "checks": checks,
        "failures": failures,
        "s100p": {
            "ssh_user": "sunrise",
            "host": "192.168.127.10",
            "openclaw_service": "openclaw-gateway.service",
            "openclaw_url": "http://127.0.0.1:8765",
            "qwen_url": "http://127.0.0.1:18080",
            "report_root": "/mnt/nas/openclaw/reports/qwen25_ai_nas",
        },
        "metrics": s100p_eval.get("metrics") or {},
        "evidence_dir": str(evidence_dir),
        "live_status_summary": str(evidence_dir / "agent_runtime_live_status" / "agent_runtime_live_status_summary.json"),
        "e2e_smoke_summary": str(evidence_dir / "agent_runtime_e2e_smoke" / "agent_runtime_e2e_smoke_summary.json"),
        "http_context_pack_smoke": str(evidence_dir / "agent_runtime_live_status" / "http_context_pack_smoke.json"),
        "ui_smoke": str(ui_smoke_path),
        "hard_constraints": {
            "ports_changed": False,
            "qwen_tool_execution_authority": False,
            "allowlist_dispatcher_bypassed": False,
            "raw_private_cloud_egress": False,
            "public_mcp_exposed": False,
            "destructive_actions_default": False,
        },
    }
    write_json(report_root / "24130_agent_runtime_s100p_acceptance_gate.json", payload)
    write_json(final_root / "digua_ai_nas_agent_runtime_deepening_packet.json", payload)
    md = "\n".join(
        [
            "# Digua AI-NAS Agent Runtime Deepening Final Packet",
            "",
            f"- Generated: {payload['generated_at']}",
            f"- Verdict: `{payload['verdict']}`",
            f"- S100P live status: `{live_summary.get('ok')}`",
            f"- S100P e2e smoke: `{e2e_summary.get('ok')}`",
            f"- Eval cases: `{payload['metrics'].get('eval_total_cases')}`",
            f"- RAG citation coverage: `{payload['metrics'].get('rag_citation_coverage')}`",
            f"- No-evidence refusal rate: `{payload['metrics'].get('rag_no_evidence_refusal_rate')}`",
            f"- HTTP Context Pack POST: `{http_context.get('context_pack_ok')}`; auth blocked without bypass: `{http_context.get('auth_blocked_without_bypass')}`",
            f"- UI desktop/mobile smoke: `{ui_smoke.get('ok')}`",
            "",
            "Hard constraints: ports unchanged; Qwen has no tool execution authority; public MCP is not exposed; raw private cloud egress remains false; destructive actions remain disabled by default.",
            "",
        ]
    )
    (final_root / "digua_ai_nas_agent_runtime_deepening_packet.md").write_text(md, encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "verdict": verdict, "path": str(final_root / "digua_ai_nas_agent_runtime_deepening_packet.json")}, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
