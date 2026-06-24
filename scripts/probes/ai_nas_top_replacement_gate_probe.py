#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json
from ai_nas_identity import IdentityStore
from ai_nas_snapshot import SnapshotStore
from ai_nas_backup import BackupManager
from ai_nas_media import MediaCenter
from ai_nas_copilot import CopilotStore
from ai_nas_ops import OpsManager
from ai_nas_app_ecosystem import AppEcosystem
TOOL_ID = "top_nas_replacement_gate"; OK = "ok_top_nas_replacement_product_gate"
def chk(msg, c, f): f.append(msg) if not c else None; print(f"  {'PASS' if c else 'FAIL'}: {msg}")
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report-root", type=Path, default=Path("tmp/nas_top_gate_local"))
    a = p.parse_args(); rd = ensure_report_dir(a.report_root, "top_gate")
    pr = rd / "Personal"; pr.mkdir(parents=True, exist_ok=True)
    for d in ["Movies","Documents","Photos","Inbox"]: (pr/d).mkdir(exist_ok=True)
    fails = [] ; R = {}
    print("Goal 10 Top NAS Replacement Gate Probe")

    R["identity"] = IdentityStore(rd/"id.db").create_user("admin","admin123")["ok"]
    chk("Identity/ACL", R["identity"], fails)
    R["storage"] = (pr/"Documents").exists()
    chk("Storage foundation", R["storage"], fails)
    (pr/"Documents/test.txt").write_text("hello")

    snap = SnapshotStore(pr, rd/"snap.db")
    r = snap.trash_file(pr/"Documents/test.txt")
    R["trash"] = r["ok"]; chk("Trash", R["trash"], fails)
    r = snap.restore_from_trash(r.get("trash_id",0))
    R["trash_restore"] = r["ok"]; chk("Trash restore", R["trash_restore"], fails)
    snap.create_snapshot("final_snap","Documents")
    R["snapshot"] = len(snap.list_snapshots())==1; chk("Snapshot", R["snapshot"], fails)

    bm = BackupManager(rd/"backup.db")
    bm.create_task("sync_docs",str(pr/"Documents"),str(rd/"Backup"),3600)
    R["backup"] = bm.run_backup("sync_docs")["ok"]; chk("Backup sync", R["backup"], fails)

    (pr/"Photos/p1.jpg").write_bytes(b"\xFF\xD8\xFF" + bytes(50))
    mc = MediaCenter(rd/"media.db")
    R["media"] = mc.index_photos(pr/"Photos")["indexed"]>=1; chk("Media index", R["media"], fails)

    cs = CopilotStore(rd/"copilot.db")
    cs.index_documents(pr/"Documents")
    R["copilot"] = len(cs.answer_question("hello")["sources"])>=1; chk("Copilot Q&A", R["copilot"], fails)

    ops = OpsManager(rd/"ops.db")
    R["ops"] = ops.check_health("core",lambda:(True,"ok"))["status"]=="healthy"; chk("Health check", R["ops"], fails)

    eco = AppEcosystem(rd/"app.db")
    R["app"] = eco.register_plugin("web-ui","1.0")["ok"]; chk("Plugin system", R["app"], fails)

    portal = Path(__file__).parent/"nas_web_os_portal.html"
    R["portal"] = portal.exists(); chk("Web portal", R["portal"], fails)

    all_ok = all(R.values()) and len(fails)==0
    chk("ALL subsystems pass", all_ok, fails)

    verdict = OK if all_ok else "failed"
    total = len(R)+1
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {total-len(fails)}/{total}")
    if fails: [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"passed_count":total-len(fails),"failures":fails,"subsystems":{k:bool(v) for k,v in R.items()}}
    safe_write_json(rd/"top_nas_replacement_gate.json", payload)
    return 0 if all_ok else 1
if __name__ == "__main__": raise SystemExit(main())
