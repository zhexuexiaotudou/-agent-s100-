#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.memory_store import MemoryStore
from harness_gate_common import check, gate_payload, load_latest_shadow_probe, write_gate_report


GATE_ID = "memory_boundary_gate"


def run_gate(report_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(report_root or ROOT / "reports")
    db_path = root / "harness_stage1_memory_boundary_gate.sqlite3"
    if db_path.exists():
        db_path.unlink()
    store = MemoryStore(db_path)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    skipped = store.write_memory("case", "nas_search", "should not persist by default", privacy_level="high")
    check(checks, failures, "long-term write skipped by default", skipped.get("status") == "skipped", skipped)
    written = store.write_memory(
        "experience",
        "ops_recovery",
        "fixture write with explicit policy approval",
        privacy_level="medium",
        allow_long_term=True,
        policy_decision="gate_fixture_policy",
    )
    check(checks, failures, "policy-approved fixture write succeeds", written.get("status") == "written", written)
    store.seed_memory("person", "global", "low privacy user preference fixture", privacy_level="low")
    store.seed_memory("case", "nas_search", "high privacy NAS fixture", privacy_level="high")

    cloud_records = store.read_memory(scope="web_cloud_research", max_privacy_level="none", limit=10)
    check(checks, failures, "cloud research reads no private memory at privacy none", all(item["privacy_level"] == "none" for item in cloud_records), cloud_records)
    search_records = store.read_memory(scope="nas_search", max_privacy_level="high", limit=10)
    check(checks, failures, "NAS search can read scoped high privacy memory", any(item["scope"] == "nas_search" and item["privacy_level"] == "high" for item in search_records), search_records)

    probe = load_latest_shadow_probe(root)
    scenarios = probe.get("scenario_results") or []
    for item in scenarios:
        scope = ((item.get("memory_scope") or {}).get("requested_scope"))
        records = (item.get("memory_scope") or {}).get("records") or []
        bad_scope = [
            record for record in records
            if record.get("scope") not in {scope, "global"}
        ]
        check(checks, failures, f"{item.get('scenario_id')} memory scoped to selected request", not bad_scope, bad_scope)
    web = next((item for item in scenarios if item.get("scenario_id") == "web_cloud_research_redacted"), {})
    web_records = (web.get("memory_scope") or {}).get("records") or []
    check(checks, failures, "web cloud scenario has no high privacy memory", all(record.get("privacy_level") == "none" for record in web_records), web_records)

    return gate_payload(
        GATE_ID,
        checks,
        failures,
        {
            "memory_db": str(db_path),
            "shadow_memory_db": probe.get("memory_db"),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 1 memory boundaries.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    payload = run_gate(args.report_root)
    paths = write_gate_report(payload, args.report_root)
    print(paths["json"])
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
