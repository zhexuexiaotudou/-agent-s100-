#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_snapshot import SnapshotStore

TOOL_ID = "ai_nas_snapshot_recovery_gate"
OK = "ok_nas_snapshot_recovery_gate"

def chk(msg, cond, fails): fails.append(msg) if not cond else None; print(f"  {'PASS' if cond else 'FAIL'}: {msg}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_snapshot_recovery_gate_local"))
    args = parser.parse_args()
    rd = ensure_report_dir(args.report_root, "snapshot_gate")
    pr = rd / "Personal"; pr.mkdir(parents=True, exist_ok=True)
    (pr/"Docs").mkdir(exist_ok=True); (pr/"Inbox").mkdir(exist_ok=True)
    db_path = rd / "snap.db"
    store = SnapshotStore(pr, db_path)
    fails = []
    print("Goal 3 Snapshot Recovery Gate Probe (direct)")

    # Setup
    (pr/"Docs/doc1.txt").write_text("original v1")
    (pr/"Docs/doc2.txt").write_text("doc2 original")

    # 1. Trash
    print("\n--- Trash ---")
    r = store.trash_file(pr/"Docs/doc1.txt", "admin")
    chk("Move to trash", r["ok"], fails)
    trash = store.list_trash()
    chk("Trash has 1 entry", len(trash) == 1, fails)
    chk("Original path preserved", trash[0]["original_path"] == "Docs/doc1.txt", fails)
    r = store.restore_from_trash(trash[0]["id"])
    chk("Restore from trash", r["ok"], fails)
    chk("File restored to disk", (pr/"Docs/doc1.txt").exists(), fails)
    chk("Restored content correct", (pr/"Docs/doc1.txt").read_text() == "original v1", fails)

    # 2. Versioning
    print("\n--- Versioning ---")
    store.save_version(pr/"Docs/doc1.txt")
    (pr/"Docs/doc1.txt").write_text("updated v2")
    store.save_version(pr/"Docs/doc1.txt")
    (pr/"Docs/doc1.txt").write_text("final v3")
    store.save_version(pr/"Docs/doc1.txt")
    vers = store.list_versions("Docs/doc1.txt")
    chk(f"Version history ({len(vers)} entries)", len(vers) >= 3, fails)
    r = store.restore_version(vers[2]["id"])
    chk("Restore oldest version", r["ok"], fails)
    chk("Content is v1", "v1" in (pr/"Docs/doc1.txt").read_text(), fails)

    # 3. Snapshots
    print("\n--- Snapshots ---")
    r = store.create_snapshot("snap1", "Docs", "admin")
    chk("Create snapshot", r["ok"], fails)
    snaps = store.list_snapshots()
    chk("List 1 snapshot", len(snaps) == 1, fails)
    r = store.browse_snapshot("snap1")
    chk("Browse snapshot", r["ok"], fails)

    (pr/"Docs/doc2.txt").unlink()
    r = store.restore_from_snapshot("snap1", "doc2.txt", "Docs/doc2.txt")
    chk("Restore doc2 from snapshot", r["ok"], fails)
    chk("Doc2 restored", (pr/"Docs/doc2.txt").exists(), fails)

    # 4. DB integrity
    print("\n--- DB Integrity ---")
    con = sqlite3.connect(str(db_path))
    chk("Snapshot DB integrity", con.execute("PRAGMA integrity_check").fetchone()[0]=="ok", fails); con.close()

    # 5. Stats
    stats = store.stats()
    chk("Stats available", stats["trash_count"] >= 0, fails)

    passed = len(fails) == 0; verdict = OK if passed else "failed_nas_snapshot_recovery_gate"
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {15-len(fails)}/15")
    if fails: print(f"  Failures: {len(fails)}"); [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"passed_count":15-len(fails),"failures":fails}
    safe_write_json(rd/"snapshot_recovery_gate.json", payload)
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
