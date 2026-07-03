#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness_gate_common import check, gate_payload, load_latest_shadow_probe, sqlite_table_counts, write_gate_report


GATE_ID = "runtime_trace_completeness_gate"
REQUIRED_PER_RUN = [
    "harness_steps",
    "workspace_decisions",
    "tool_calls",
    "memory_reads",
    "gate_results",
]


def _count_for_run(con: sqlite3.Connection, table: str, run_id: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id = ?", (run_id,)).fetchone()[0])


def run_gate(report_root: str | Path | None = None) -> dict[str, Any]:
    probe = load_latest_shadow_probe(report_root)
    trace_db = Path(probe.get("trace_db") or "")
    root = Path(report_root or ROOT / "reports")
    if not trace_db.exists():
        fallback = root / "latest_shadow_run" / "harness_runtime_trace.sqlite3"
        if fallback.exists():
            trace_db = fallback
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    check(checks, failures, "trace DB exists", trace_db.exists(), str(trace_db))
    if not trace_db.exists():
        return gate_payload(GATE_ID, checks, failures, {"trace_db": str(trace_db)})

    counts = sqlite_table_counts(trace_db)
    for table, count in counts.items():
        check(checks, failures, f"{table} has rows", count > 0, count)

    run_details: list[dict[str, Any]] = []
    with sqlite3.connect(trace_db) as con:
        con.row_factory = sqlite3.Row
        runs = [dict(row) for row in con.execute("SELECT run_id, scenario_id, status FROM harness_runs ORDER BY started_at")]
        check(checks, failures, "six trace runs recorded", len(runs) == 6, len(runs))
        for run in runs:
            per_run = {table: _count_for_run(con, table, run["run_id"]) for table in REQUIRED_PER_RUN}
            run_details.append({"run_id": run["run_id"], "scenario_id": run["scenario_id"], "counts": per_run})
            check(checks, failures, f"{run['scenario_id']} trace complete", all(value > 0 for value in per_run.values()), per_run)
        denied_count = int(con.execute("SELECT COUNT(*) FROM tool_calls WHERE status = 'denied'").fetchone()[0])
        policy_denial_count = int(con.execute("SELECT COUNT(*) FROM policy_denials").fetchone()[0])
        non_dispatcher_calls = int(con.execute("SELECT COUNT(*) FROM tool_calls WHERE dispatcher_used != 1").fetchone()[0])
    check(checks, failures, "denied calls recorded", denied_count > 0, denied_count)
    check(checks, failures, "policy_denials recorded", policy_denial_count > 0, policy_denial_count)
    check(checks, failures, "all tool call records preserve dispatcher boundary", non_dispatcher_calls == 0, non_dispatcher_calls)
    check(checks, failures, "shadow probe verdict ok", str(probe.get("verdict", "")).startswith("ok_"), probe.get("verdict"))

    return gate_payload(
        GATE_ID,
        checks,
        failures,
        {
            "trace_db": str(trace_db),
            "table_counts": counts,
            "run_details": run_details,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 1 runtime trace completeness.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    payload = run_gate(args.report_root)
    paths = write_gate_report(payload, args.report_root)
    print(paths["json"])
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
