#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json
from ai_nas_ops import OpsManager

TOOL_ID = "ai_nas_ops_observability_gate"; OK = "ok_nas_ops_observability_gate"
def chk(msg, cnd, fls): fls.append(msg) if not cnd else None; print(f"  {'PASS' if cnd else 'FAIL'}: {msg}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_ops_gate_local"))
    args = parser.parse_args()
    rd = ensure_report_dir(args.report_root, "ops_gate")
    db = rd / "ops.db"; ops = OpsManager(db); fails = []
    print("Goal 8 Operations Gate Probe (direct)")

    # Health checks
    print("\n--- Health Checks ---")
    r = ops.check_health("storage_api", lambda: (True,"ok"))
    chk("Health check healthy", r["status"]=="healthy", fails)
    r = ops.check_health("failing_service", lambda: (False,"down"))
    chk("Health check unhealthy", r["status"]=="unhealthy", fails)
    checks = ops.list_checks()
    chk("List checks", len(checks)>=2, fails)

    # Disk
    print("\n--- Disk Monitoring ---")
    d = ops.disk_check(str(rd))
    chk("Disk check returns data", d["ok"] and d["free_gb"]>0, fails)

    # Alerts
    print("\n--- Alerts ---")
    r = ops.create_alert("warning","disk","storage 85% full")
    chk("Create alert", r["ok"], fails)
    alerts = ops.list_alerts()
    chk(f"Active alerts ({len(alerts)})", len(alerts)>=1, fails)
    r = ops.resolve_alert(alerts[0]["id"])
    chk("Resolve alert", r["ok"], fails)
    chk("Alert resolved", len(ops.list_alerts())==0, fails)

    # Export
    print("\n--- Diagnostics ---")
    exp = rd / "diag_export"
    r = ops.export_diagnostics(exp)
    chk("Export diagnostics", r["ok"] and (exp/"diagnostics.json").exists(), fails)

    # Stats
    s = ops.stats()
    chk(f"Stats: {s['health_check_count']} checks, {s['active_alert_count']} alerts", s["health_check_count"]>=2, fails)

    # DB
    con = sqlite3.connect(str(db))
    chk("Ops DB integrity", con.execute("PRAGMA integrity_check").fetchone()[0]=="ok", fails); con.close()

    passed = len(fails) == 0; verdict = OK if passed else "failed_nas_ops_observability_gate"
    total = 10
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {total-len(fails)}/{total}")
    if fails: print(f"  Failures: {len(fails)}"); [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"passed_count":total-len(fails),"failures":fails}
    safe_write_json(rd/"ops_observability_gate.json", payload)
    return 0 if passed else 1

if __name__ == "__main__": raise SystemExit(main())
