#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys, time
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_backup import BackupManager

TOOL_ID = "ai_nas_backup_sync_gate"
OK = "ok_nas_backup_sync_gate"

def chk(msg, cond, fails): fails.append(msg) if not cond else None; print(f"  {'PASS' if cond else 'FAIL'}: {msg}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_backup_sync_gate_local"))
    args = parser.parse_args()
    rd = ensure_report_dir(args.report_root, "backup_gate")
    src = rd / "Source"; src.mkdir(parents=True, exist_ok=True)
    dest = rd / "Backup"; dest.mkdir(parents=True, exist_ok=True)
    db = rd / "backup.db"
    bm = BackupManager(db)
    fails = []
    print("Goal 4 Backup & Sync Gate Probe (direct)")

    # Create test files
    (src/"file1.txt").write_text("hello backup")
    (src/"file2.txt").write_text("second file")
    (src/"sub").mkdir(exist_ok=True)
    (src/"sub/file3.txt").write_text("nested file")

    # 1. Task management
    print("\n--- Task Management ---")
    r = bm.create_task("sync_docs", str(src), str(dest), 3600)
    chk("Create backup task", r["ok"], fails)
    tasks = bm.list_tasks()
    chk("List tasks (1)", len(tasks) == 1, fails)
    chk("Task name correct", tasks[0]["name"] == "sync_docs", fails)

    # 2. Run backup
    print("\n--- Backup Execution ---")
    r = bm.run_backup("sync_docs")
    chk("Backup completes", r["ok"], fails)
    chk("Copied 3 files", r["copied"] == 3, fails)
    chk("Scanned 3 files", r["scanned"] == 3, fails)

    # Verify files exist in destination
    chk("file1.txt backed up", (dest/"file1.txt").exists(), fails)
    chk("file2.txt backed up", (dest/"file2.txt").exists(), fails)
    chk("sub/file3.txt backed up", (dest/"sub/file3.txt").exists(), fails)
    chk("Content preserved", (dest/"file1.txt").read_text() == "hello backup", fails)

    # 3. Incremental: re-run, should skip unchanged
    print("\n--- Incremental Backup ---")
    r = bm.run_backup("sync_docs")
    chk("Second run completes", r["ok"], fails)
    chk("All files skipped (no changes)", r["skipped"] >= 3, fails)

    # Modify a file, re-run
    (src/"file1.txt").write_text("modified content")
    r = bm.run_backup("sync_docs")
    chk("Modified file re-copied", r["copied"] == 1, fails)
    chk("Updated content backed up", "modified" in (dest/"file1.txt").read_text(), fails)

    # 4. Restore from backup run
    print("\n--- Restore ---")
    restore_target = rd / "Restored"
    runs = bm.list_runs("sync_docs", 1)
    chk("Has run history", len(runs) >= 1, fails)
    r = bm.restore_from_run(runs[0]["id"], str(restore_target))
    chk("Restore from backup", r["ok"], fails)
    chk("Restored file exists", (restore_target/"file1.txt").exists(), fails)

    # 5. Scheduled task detection
    print("\n--- Scheduling ---")
    tasks = bm.list_tasks()
    chk("Task has schedule", tasks[0]["schedule_interval_seconds"] == 3600, fails)

    # 6. DB integrity
    print("\n--- DB Integrity ---")
    con = sqlite3.connect(str(db))
    chk("Backup DB integrity", con.execute("PRAGMA integrity_check").fetchone()[0]=="ok", fails); con.close()

    # 7. Stats
    stats = bm.stats()
    chk("Stats available", stats["task_count"] == 1 and stats["run_count"] >= 3, fails)

    passed = len(fails) == 0; verdict = OK if passed else "failed_nas_backup_sync_gate"
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {18-len(fails)}/18")
    if fails: print(f"  Failures: {len(fails)}"); [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"passed_count":18-len(fails),"failures":fails}
    safe_write_json(rd/"backup_sync_gate.json", payload)
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
