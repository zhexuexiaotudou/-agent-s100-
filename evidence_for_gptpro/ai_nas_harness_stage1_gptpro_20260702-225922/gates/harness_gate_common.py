from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.config_io import load_json_yaml, safe_write_json, safe_write_text, utc_stamp


REQUIRED_WORKSPACES = [
    "main_router",
    "nas_search",
    "nas_action",
    "media_photo",
    "document_rag",
    "ops_recovery",
    "web_cloud_research",
    "admin_audit",
]


def dispatcher_tool_ids(root: Path = ROOT) -> list[str]:
    dispatcher = root / "scripts" / "probes" / "ai_nas_allowlisted_tool.sh"
    text = dispatcher.read_text(encoding="utf-8", errors="replace")
    from_usage = set(re.findall(r"ai_nas_allowlisted_tool\.sh ([A-Za-z0-9_]+)", text))
    from_case = set(re.findall(r"^\s{2}([A-Za-z0-9_]+)\)\s*$", text, flags=re.M))
    return sorted(from_usage | from_case)


def load_latest_shadow_probe(report_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(report_root or ROOT / "reports")
    latest = root / "harness_shadow_probe_latest.json"
    if latest.exists():
        return json.loads(latest.read_text(encoding="utf-8"))
    candidates = sorted(root.glob("harness_shadow_probe_*/harness_shadow_probe.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"no harness shadow probe report found under {root}")
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def sqlite_table_counts(db_path: str | Path) -> dict[str, int]:
    tables = [
        "harness_runs",
        "harness_steps",
        "workspace_decisions",
        "tool_calls",
        "policy_denials",
        "memory_reads",
        "gate_results",
    ]
    with sqlite3.connect(db_path) as con:
        return {table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}


def check(checks: list[dict[str, Any]], failures: list[str], label: str, passed: bool, detail: Any = None) -> None:
    item = {"label": label, "ok": bool(passed)}
    if detail is not None:
        item["detail"] = detail
    checks.append(item)
    if not passed:
        failures.append(label)


def gate_payload(gate_id: str, checks: list[dict[str, Any]], failures: list[str], detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "generated_at": utc_stamp(),
        "gate_id": gate_id,
        "verdict": f"ok_{gate_id}" if not failures else f"failed_{gate_id}",
        "passed_count": sum(1 for item in checks if item.get("ok")),
        "check_count": len(checks),
        "failure_count": len(failures),
        "failures": failures,
        "checks": checks,
        "detail": detail or {},
    }


def write_gate_report(payload: dict[str, Any], report_root: str | Path | None = None) -> dict[str, str]:
    root = Path(report_root or ROOT / "reports")
    gate_id = payload["gate_id"]
    json_path = root / f"{gate_id}.json"
    md_path = root / f"{gate_id}.md"
    safe_write_json(json_path, payload)
    lines = [
        f"# {gate_id}",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- passed: `{payload['passed_count']}/{payload['check_count']}`",
        "",
        "## Checks",
        "",
    ]
    for item in payload["checks"]:
        status = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"- `{status}` {item['label']}")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{item}`" for item in payload["failures"]] or ["- none"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    return {"json": str(json_path), "md": str(md_path)}


def load_registry_policy() -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_json_yaml(ROOT / "config" / "workspace_registry.yaml")
    policy = load_json_yaml(ROOT / "config" / "workspace_tool_policy.yaml")
    return registry, policy
