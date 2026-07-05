#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness_gate_common import check, gate_payload, load_latest_shadow_probe, load_registry_policy, write_gate_report


GATE_ID = "cloud_egress_privacy_gate"


def run_gate(report_root: str | Path | None = None) -> dict[str, Any]:
    _, policy = load_registry_policy()
    probe = load_latest_shadow_probe(report_root)
    terms = policy.get("cloud_redaction", {}).get("private_terms") or []
    replacement = policy.get("cloud_redaction", {}).get("replacement")
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    scenarios = probe.get("scenario_results") or []

    for item in scenarios:
        scenario_id = item.get("scenario_id")
        if scenario_id == "web_cloud_research_redacted":
            payload = item.get("cloud_payload") or {}
            preview = payload.get("egress_preview") or ""
            summary = payload.get("redaction_summary") or {}
            check(checks, failures, "web cloud scenario is explicitly cloud allowed", payload.get("allowed") is True, payload)
            check(checks, failures, "web cloud redaction applied", payload.get("redaction_applied") is True, payload)
            check(checks, failures, "web cloud egress hash exists", bool(payload.get("egress_payload_hash")), payload)
            check(checks, failures, "web cloud egress leak count is zero", summary.get("leak_count") == 0, summary)
            check(checks, failures, "web cloud egress uses configured replacement", "[REDACTED_NAS_CONTEXT]" in preview, preview)
        else:
            check(checks, failures, f"{scenario_id} cloud disabled", item.get("cloud_allowed") is False, item.get("cloud_allowed"))

    check(checks, failures, "probe reports no protected port modifications", probe.get("ports_modified") == [], probe.get("ports_modified"))
    check(checks, failures, "probe reports production path unmodified", probe.get("production_path_modified") is False, probe.get("production_path_modified"))

    return gate_payload(
        GATE_ID,
        checks,
        failures,
        {
            "private_terms": terms,
            "replacement": replacement,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 1 cloud egress redaction.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    payload = run_gate(args.report_root)
    paths = write_gate_report(payload, args.report_root)
    print(paths["json"])
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
