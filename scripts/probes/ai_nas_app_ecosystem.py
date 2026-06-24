#!/usr/bin/env python3
"""AI-NAS App Ecosystem — plugin/app registry, container placeholder, protocol adapters."""
from __future__ import annotations
import json, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path

def _now_iso(): return datetime.now(timezone.utc).isoformat()
def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS plugins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE, version TEXT, type TEXT DEFAULT 'app',
            description TEXT, status TEXT DEFAULT 'stopped',
            install_path TEXT, config_json TEXT,
            installed_at TEXT NOT NULL, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS protocol_adapters(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE, protocol TEXT NOT NULL, port INTEGER,
            status TEXT DEFAULT 'disabled', config_json TEXT
        );
    """)
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
    con.commit(); con.close()

class AppEcosystem:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path; _init_db(db_path)
    def _conn(self):
        c = sqlite3.connect(str(self.db_path)); c.row_factory = sqlite3.Row; return c

    def register_plugin(self, name: str, version: str = "1.0.0", ptype: str = "app", desc: str = "", config: dict | None = None) -> dict:
        con = self._conn()
        try:
            con.execute("INSERT INTO plugins(name,version,type,description,config_json,installed_at) VALUES(?,?,?,?,?,?)",(name,version,ptype,desc,json.dumps(config or {}),_now_iso()))
            con.commit(); return {"ok":True,"id":con.execute("SELECT last_insert_rowid()").fetchone()[0]}
        except sqlite3.IntegrityError: return {"ok":False,"error":"plugin_exists"}
        finally: con.close()

    def list_plugins(self) -> list[dict]:
        con = self._conn()
        try: return [dict(r) for r in con.execute("SELECT * FROM plugins ORDER BY name").fetchall()]
        finally: con.close()

    def set_status(self, name: str, status: str) -> dict:
        if status not in ("running","stopped","error"): return {"ok":False,"error":"invalid_status"}
        con = self._conn()
        try:
            cur = con.execute("UPDATE plugins SET status=?,updated_at=? WHERE name=?",(status,_now_iso(),name)); con.commit()
            return {"ok":cur.rowcount>0}
        finally: con.close()

    def add_protocol(self, name: str, protocol: str, port: int = 0, config: dict | None = None) -> dict:
        con = self._conn()
        try:
            con.execute("INSERT INTO protocol_adapters(name,protocol,port,config_json) VALUES(?,?,?,?)",(name,protocol,port,json.dumps(config or {})))
            con.commit(); return {"ok":True,"id":con.execute("SELECT last_insert_rowid()").fetchone()[0]}
        except sqlite3.IntegrityError: return {"ok":False,"error":"adapter_exists"}
        finally: con.close()

    def list_protocols(self) -> list[dict]:
        con = self._conn()
        try: return [dict(r) for r in con.execute("SELECT * FROM protocol_adapters ORDER BY name").fetchall()]
        finally: con.close()

    def stats(self) -> dict:
        con = self._conn()
        try:
            pc = con.execute("SELECT COUNT(*) FROM plugins").fetchone()[0]
            ac = con.execute("SELECT COUNT(*) FROM protocol_adapters").fetchone()[0]
            return {"plugin_count":pc,"adapter_count":ac}
        finally: con.close()
