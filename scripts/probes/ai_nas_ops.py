#!/usr/bin/env python3
"""AI-NAS Operations — service monitoring, disk alerts, health checks, diagnostic export."""
from __future__ import annotations
import hashlib, json, os, shutil, sqlite3, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

def _now_iso(): return datetime.now(timezone.utc).isoformat()

def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS health_checks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL, status TEXT NOT NULL,
            message TEXT, latency_ms REAL, checked_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alerts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            severity TEXT NOT NULL CHECK(severity IN('info','warning','critical')),
            source TEXT NOT NULL, message TEXT NOT NULL,
            created_at TEXT NOT NULL, resolved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_health_service ON health_checks(service_name, checked_at);
        CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity, resolved_at);
    """)
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
    con.commit(); con.close()

class OpsManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path; _init_db(db_path)
    def _connect(self):
        c = sqlite3.connect(str(self.db_path)); c.execute("PRAGMA foreign_keys=ON"); c.row_factory = sqlite3.Row; return c

    def check_health(self, service_name: str, check_fn=None) -> dict:
        started = time.perf_counter()
        ok, msg = True, ""
        try:
            if check_fn: ok, msg = check_fn()
        except Exception as e: ok, msg = False, str(e)
        lat = (time.perf_counter() - started) * 1000
        status = "healthy" if ok else "unhealthy"
        con = self._connect()
        try:
            con.execute("INSERT INTO health_checks(service_name,status,message,latency_ms,checked_at) VALUES(?,?,?,?,?)",(service_name,status,str(msg)[:500],round(lat,2),_now_iso()))
            con.commit()
        finally: con.close()
        return {"service":service_name,"status":status,"latency_ms":round(lat,2),"message":msg}

    def list_checks(self, limit=50) -> list[dict]:
        con = self._connect()
        try:
            return [dict(r) for r in con.execute("SELECT * FROM health_checks ORDER BY checked_at DESC LIMIT ?",(limit,)).fetchall()]
        finally: con.close()

    def disk_check(self, path: str) -> dict:
        p = Path(path)
        if not p.exists(): return {"ok":False,"error":"path_not_found"}
        try:
            usage = shutil.disk_usage(p)
            pct = (usage.used / usage.total) * 100
            alert = pct > 90
            return {"ok":True,"total_gb":round(usage.total/1e9,2),"used_gb":round(usage.used/1e9,2),"free_gb":round(usage.free/1e9,2),"used_pct":round(pct,1),"alert":alert}
        except: return {"ok":False,"error":"disk_check_failed"}

    def create_alert(self, severity: str, source: str, message: str) -> dict:
        if severity not in ("info","warning","critical"): return {"ok":False,"error":"invalid_severity"}
        con = self._connect()
        try:
            con.execute("INSERT INTO alerts(severity,source,message,created_at) VALUES(?,?,?,?)",(severity,source,message,_now_iso()))
            con.commit()
            return {"ok":True,"id":con.execute("SELECT last_insert_rowid()").fetchone()[0]}
        finally: con.close()

    def list_alerts(self, include_resolved=False) -> list[dict]:
        con = self._connect()
        try:
            if include_resolved:
                return [dict(r) for r in con.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 100").fetchall()]
            return [dict(r) for r in con.execute("SELECT * FROM alerts WHERE resolved_at IS NULL ORDER BY severity, created_at DESC LIMIT 100").fetchall()]
        finally: con.close()

    def resolve_alert(self, alert_id: int) -> dict:
        con = self._connect()
        try:
            cur = con.execute("UPDATE alerts SET resolved_at=? WHERE id=?",(_now_iso(),alert_id))
            con.commit()
            return {"ok":cur.rowcount>0}
        finally: con.close()

    def export_diagnostics(self, output_path: Path) -> dict:
        output_path.mkdir(parents=True, exist_ok=True)
        con = self._connect()
        try:
            checks = self.list_checks(50)
            alerts = self.list_alerts(True)
            diag = {"generated_at":_now_iso(),"health_checks":checks,"alerts":alerts}
            (output_path/"diagnostics.json").write_text(json.dumps(diag,indent=2,default=str))
            return {"ok":True,"path":str(output_path)}
        finally: con.close()

    def stats(self) -> dict:
        con = self._connect()
        try:
            hc = con.execute("SELECT COUNT(*) FROM health_checks").fetchone()[0]
            ac = con.execute("SELECT COUNT(*) FROM alerts WHERE resolved_at IS NULL").fetchone()[0]
            return {"health_check_count":hc,"active_alert_count":ac}
        finally: con.close()
