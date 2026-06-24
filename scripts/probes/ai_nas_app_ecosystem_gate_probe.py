#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json
from ai_nas_app_ecosystem import AppEcosystem
TOOL_ID = "ai_nas_app_ecosystem_gate"; OK = "ok_nas_app_ecosystem_gate"
def chk(msg, c, f): f.append(msg) if not c else None; print(f"  {'PASS' if c else 'FAIL'}: {msg}")
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report-root", type=Path, default=Path("tmp/nas_app_gate_local"))
    a = p.parse_args(); rd = ensure_report_dir(a.report_root, "app_gate")
    db = rd / "app.db"; eco = AppEcosystem(db); fails = []
    print("Goal 9 App Ecosystem Gate Probe (direct)")
    # Plugins
    print("\n--- Plugins ---")
    r = eco.register_plugin("file-sync","2.1.0","app","Sync files to NAS")
    chk("Register plugin", r["ok"], fails)
    r = eco.register_plugin("photo-viewer","1.0","app","Photo gallery")
    chk("Register photo-viewer", r["ok"], fails)
    pl = eco.list_plugins()
    chk("List plugins", len(pl)==2, fails)
    eco.set_status("file-sync","running")
    eco.set_status("photo-viewer","stopped")
    pl2 = eco.list_plugins()
    chk("Status: running", any(p["status"]=="running" for p in pl2), fails)
    chk("Status: stopped", any(p["status"]=="stopped" for p in pl2), fails)
    # Protocols
    print("\n--- Protocol Adapters ---")
    eco.add_protocol("smb-share","smb",445)
    chk("Add SMB adapter", len(eco.list_protocols())==1, fails)
    eco.add_protocol("webdav","webdav",8080)
    chk("Add WebDAV adapter", len(eco.list_protocols())==2, fails)
    # Stats
    s = eco.stats()
    chk(f"Stats: {s['plugin_count']} plugins, {s['adapter_count']} adapters", s["plugin_count"]==2, fails)
    # DB
    con = sqlite3.connect(str(db))
    chk("App DB integrity", con.execute("PRAGMA integrity_check").fetchone()[0]=="ok", fails); con.close()
    passed = len(fails) == 0; verdict = OK if passed else "failed_nas_app_ecosystem_gate"
    total = 8
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {total-len(fails)}/{total}")
    if fails: print(f"  Failures: {len(fails)}"); [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"passed_count":total-len(fails),"failures":fails}
    safe_write_json(rd/"app_ecosystem_gate.json", payload)
    return 0 if passed else 1
if __name__ == "__main__": raise SystemExit(main())
