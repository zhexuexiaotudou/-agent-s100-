#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(GATE_DIR) not in sys.path:
    sys.path.insert(0, str(GATE_DIR))

from ai_nas_harness.config_io import safe_write_json, safe_write_text, utc_stamp
from harness_gate_common import write_gate_report


GATE_MODULES = [
    "workspace_isolation_gate",
    "tool_exposure_minimization_gate",
    "memory_boundary_gate",
    "runtime_trace_completeness_gate",
    "cloud_egress_privacy_gate",
]


def run_all(report_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(report_root or ROOT / "reports")
    gate_results = []
    for module_name in GATE_MODULES:
        module = importlib.import_module(module_name)
        payload = module.run_gate(root)
        paths = write_gate_report(payload, root)
        payload["report_paths"] = paths
        gate_results.append(payload)
    failures = [
        {"gate_id": result["gate_id"], "failures": result["failures"]}
        for result in gate_results
        if not str(result.get("verdict", "")).startswith("ok_")
    ]
    payload = {
        "generated_at": utc_stamp(),
        "gate_id": "harness_stage1_gate_report",
        "verdict": "ok_harness_stage1_gates" if not failures else "failed_harness_stage1_gates",
        "gate_count": len(gate_results),
        "passed_gate_count": sum(1 for item in gate_results if str(item.get("verdict", "")).startswith("ok_")),
        "failure_count": len(failures),
        "failures": failures,
        "gate_results": gate_results,
        "stage1_boundaries": {
            "production_mainline_replaced": False,
            "dispatcher_bypassed": False,
            "arbitrary_script_path_enabled": False,
            "dream7b_foreground_attached": False,
            "protected_ports_modified": [],
        },
    }
    return payload


def write_combined(payload: dict[str, Any], report_root: str | Path | None = None) -> dict[str, str]:
    root = Path(report_root or ROOT / "reports")
    json_path = root / "harness_stage1_gate_report.json"
    md_path = root / "harness_stage1_gate_report.md"
    safe_write_json(json_path, payload)
    lines = [
        "# Harness Stage 1 Gate Report",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- passed_gate_count: `{payload['passed_gate_count']}/{payload['gate_count']}`",
        "",
        "## Gates",
        "",
    ]
    for result in payload["gate_results"]:
        lines.append(
            f"- `{result['gate_id']}` verdict `{result['verdict']}` "
            f"passed `{result['passed_count']}/{result['check_count']}`"
        )
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        for item in payload["failures"]:
            lines.append(f"- `{item['gate_id']}`: `{item['failures']}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Boundaries", ""])
    for key, value in payload["stage1_boundaries"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    return {"json": str(json_path), "md": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all Stage 1 Workspace Harness gates.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    payload = run_all(args.report_root)
    paths = write_combined(payload, args.report_root)
    print(paths["json"])
    print(paths["md"])
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
