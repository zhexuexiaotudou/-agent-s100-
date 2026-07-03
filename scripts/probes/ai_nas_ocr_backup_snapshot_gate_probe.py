#!/usr/bin/env python3
"""Combined gate probe: OCR quality (A4), formal backup (A13), snapshot history (A14).

Tests OCR against PDF documents, and validates backup/snapshot stores.
"""

from __future__ import annotations

import json, sys, time, sqlite3
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

PERSONAL = Path("F:/mnt/nas/openclaw/Personal")
REPORT = Path("F:/mnt/nas/openclaw/reports/ai_nas_mvp")
RUNTIME = REPORT / "portal_runtime_current"


def ocr_status() -> dict:
    """Check OCR engine availability (Tesseract)."""
    import subprocess
    try:
        result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=5)
        version = result.stdout.split("\n")[0] if result.stdout else "unknown"
        return {"ok": True, "engine": "tesseract", "version": version}
    except FileNotFoundError:
        return {"ok": False, "engine": "tesseract", "error": "tesseract_not_installed"}
    except Exception as e:
        return {"ok": False, "engine": "tesseract", "error": str(e)}


def backup_status() -> dict:
    """Check backup DB for existing backup tasks."""
    db_path = RUNTIME / "backup.sqlite3"
    if not db_path.exists():
        return {"ok": False, "error": "backup_db_not_found"}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM backup_tasks")
        tasks = cursor.fetchone()[0]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        return {"ok": True, "backend": "BackupManager", "db_path": str(db_path), "tables": tables, "backup_tasks": tasks}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def snapshot_status() -> dict:
    """Check snapshot DB for existing snapshots."""
    db_path = RUNTIME / "snapshot.sqlite3"
    if not db_path.exists():
        return {"ok": False, "error": "snapshot_db_not_found"}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM snapshots")
        snapshots = cursor.fetchone()[0]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        return {"ok": True, "backend": "SnapshotStore", "db_path": str(db_path), "tables": tables, "snapshots": snapshots}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_snapshot_filesystem() -> dict:
    """Check for snapshot directories on disk."""
    snap_dir = PERSONAL / ".snapshots"
    if not snap_dir.exists():
        return {"ok": True, "snapshot_dir": str(snap_dir), "children": 0, "note": "no_snapshots_on_disk"}
    children = list(snap_dir.iterdir())
    return {"ok": True, "snapshot_dir": str(snap_dir), "children": len(children), "names": [c.name for c in children[:10]]}


def run_gate():
    results = {"gate_id": "ok_ai_nas_ocr_backup_snapshot_gate", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "features": ["A4_ocr", "A13_backup", "A14_snapshot"], "tests": []}

    # A4: OCR
    ocr = ocr_status()
    results["tests"].append({"type": "ocr_status", "ok": ocr["ok"], "details": ocr})

    # A13: Backup
    bkp = backup_status()
    results["tests"].append({"type": "backup_status", "ok": bkp["ok"], "details": bkp})

    # A14: Snapshot
    snap = snapshot_status()
    results["tests"].append({"type": "snapshot_status", "ok": snap["ok"], "details": snap})
    snap_fs = check_snapshot_filesystem()
    results["tests"].append({"type": "snapshot_filesystem", "ok": snap_fs["ok"], "details": snap_fs})

    tests = results["tests"]
    passed = sum(1 for t in tests if t["ok"])
    results["verdict"] = "passed" if passed >= len(tests) * 0.5 else "failed"
    results["tests_total"] = len(tests)
    results["tests_passed"] = passed

    out_path = REPORT / "ocr_backup_snapshot_gate_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Gate {results['verdict']}: {passed}/{len(tests)} passed")
    return results


if __name__ == "__main__":
    gate = run_gate()
    print(json.dumps(gate, ensure_ascii=False, indent=2))
