from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ProductAccessStore:
    """Non-secret product access state.

    One-time claims are stored only as hashes. Tunnel credentials and private
    keys are deliberately excluded from this database.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _init(self) -> None:
        con = self.connect()
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS product_meta(
                  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS setup_claims(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  token_hash TEXT UNIQUE NOT NULL,
                  expires_at TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  max_attempts INTEGER NOT NULL DEFAULT 8,
                  consumed_at TEXT,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS endpoints(
                  channel TEXT PRIMARY KEY,
                  url TEXT NOT NULL,
                  enabled INTEGER NOT NULL DEFAULT 0,
                  verified INTEGER NOT NULL DEFAULT 0,
                  details_json TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS identity_mappings(
                  provider TEXT NOT NULL,
                  external_subject TEXT NOT NULL,
                  local_username TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY(provider, external_subject)
                );
                CREATE TABLE IF NOT EXISTS audit_events(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  happened_at TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  action TEXT NOT NULL,
                  channel TEXT NOT NULL,
                  outcome TEXT NOT NULL,
                  details_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS network_snapshots(
                  id TEXT PRIMARY KEY,
                  state_json TEXT NOT NULL,
                  plan_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  confirmed_at TEXT,
                  rolled_back_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(happened_at);
                """
            )
            now = utc_now()
            con.execute(
                "INSERT OR IGNORE INTO product_meta(key,value,updated_at) VALUES('schema_version','1',?)",
                (now,),
            )
            con.execute(
                "INSERT OR IGNORE INTO product_meta(key,value,updated_at) VALUES('device_id',?,?)",
                (str(uuid.uuid4()), now),
            )
            con.execute(
                "INSERT OR IGNORE INTO product_meta(key,value,updated_at) VALUES('installation_id',?,?)",
                (str(uuid.uuid4()), now),
            )
            con.execute(
                "INSERT OR IGNORE INTO product_meta(key,value,updated_at) VALUES('created_at',?,?)",
                (now, now),
            )
            con.execute(
                "INSERT OR IGNORE INTO product_meta(key,value,updated_at) VALUES('device_name','Digua AI-NAS',?)",
                (now,),
            )
            con.commit()
        finally:
            con.close()

    def meta(self, key: str) -> str | None:
        con = self.connect()
        try:
            row = con.execute("SELECT value FROM product_meta WHERE key=?", (key,)).fetchone()
            return str(row[0]) if row else None
        finally:
            con.close()

    def set_meta(self, key: str, value: str) -> None:
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO product_meta(key,value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                (key, value, utc_now()),
            )
            con.commit()
        finally:
            con.close()

    def device(self) -> dict:
        device_id = self.meta("device_id") or ""
        return {
            "id": device_id,
            "device_id": device_id,
            "short_device_id": device_id.replace("-", "")[:8],
            "name": self.meta("device_name") or "Digua AI-NAS",
            "device_name": self.meta("device_name") or "Digua AI-NAS",
            "hostname": self.meta("hostname") or "digua",
            "model": "S100P",
            "product_name": "地瓜 AI-NAS",
            "installation_id": self.meta("installation_id"),
            "created_at": self.meta("created_at"),
        }

    def create_claim(self, ttl_minutes: int = 30) -> str:
        token = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE setup_claims SET consumed_at=? WHERE consumed_at IS NULL", (now.isoformat(),))
            con.execute(
                "INSERT INTO setup_claims(token_hash,expires_at,created_at) VALUES(?,?,?)",
                (token_hash(token), (now + timedelta(minutes=max(5, min(ttl_minutes, 1440)))).isoformat(), now.isoformat()),
            )
            con.commit()
            return token
        finally:
            con.close()

    def claim_status(self) -> dict:
        con = self.connect()
        try:
            row = con.execute(
                "SELECT expires_at,attempts,max_attempts,consumed_at FROM setup_claims ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return {"available": False, "reason": "claim_not_generated"}
            active = (
                row["consumed_at"] is None
                and row["attempts"] < row["max_attempts"]
                and datetime.fromisoformat(row["expires_at"]) > datetime.now(timezone.utc)
            )
            return {
                "available": active,
                "expires_at": row["expires_at"],
                "attempts_remaining": max(0, row["max_attempts"] - row["attempts"]),
                "consumed": row["consumed_at"] is not None,
            }
        finally:
            con.close()

    def verify_claim(self, token: str) -> bool:
        digest = token_hash(token)
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT id,token_hash,expires_at,attempts,max_attempts,consumed_at "
                "FROM setup_claims ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                con.commit()
                return False
            active = (
                row["consumed_at"] is None
                and row["attempts"] < row["max_attempts"]
                and datetime.fromisoformat(row["expires_at"]) > datetime.now(timezone.utc)
            )
            valid = active and secrets.compare_digest(str(row["token_hash"]), digest)
            if not valid:
                con.execute("UPDATE setup_claims SET attempts=attempts+1 WHERE id=?", (row["id"],))
            con.commit()
            return bool(valid)
        finally:
            con.close()

    def consume_claim(self, token: str) -> bool:
        digest = token_hash(token)
        con = self.connect()
        try:
            cur = con.execute(
                "UPDATE setup_claims SET consumed_at=? WHERE token_hash=? AND consumed_at IS NULL",
                (utc_now(), digest),
            )
            con.commit()
            return cur.rowcount == 1
        finally:
            con.close()

    def redeem_claim(self, token: str) -> bool:
        """Atomically validate and consume the latest claim across processes."""
        digest = token_hash(token)
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT id,token_hash,expires_at,attempts,max_attempts,consumed_at FROM setup_claims ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                con.commit()
                return False
            active = (
                row["consumed_at"] is None
                and row["attempts"] < row["max_attempts"]
                and datetime.fromisoformat(row["expires_at"]) > datetime.now(timezone.utc)
            )
            valid = active and secrets.compare_digest(str(row["token_hash"]), digest)
            if valid:
                con.execute("UPDATE setup_claims SET consumed_at=? WHERE id=?", (utc_now(), row["id"]))
            else:
                con.execute("UPDATE setup_claims SET attempts=attempts+1 WHERE id=?", (row["id"],))
            con.commit()
            return bool(valid)
        finally:
            con.close()

    def set_endpoint(self, channel: str, url: str, *, enabled: bool, verified: bool = False, details: dict | None = None) -> None:
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO endpoints(channel,url,enabled,verified,details_json,updated_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(channel) DO UPDATE SET url=excluded.url,enabled=excluded.enabled,"
                "verified=excluded.verified,details_json=excluded.details_json,updated_at=excluded.updated_at",
                (channel, url, int(enabled), int(verified), json.dumps(details or {}, ensure_ascii=False), utc_now()),
            )
            con.commit()
        finally:
            con.close()

    def endpoints(self) -> list[dict]:
        con = self.connect()
        try:
            rows = con.execute("SELECT * FROM endpoints ORDER BY channel").fetchall()
            return [
                {
                    "channel": row["channel"], "url": row["url"],
                    "enabled": bool(row["enabled"]), "verified": bool(row["verified"]),
                    "details": json.loads(row["details_json"]), "updated_at": row["updated_at"],
                }
                for row in rows
            ]
        finally:
            con.close()

    def map_identity(self, provider: str, subject: str, username: str) -> None:
        if provider not in {"tailscale", "cloudflare"}:
            raise ValueError("unsupported_identity_provider")
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO identity_mappings(provider,external_subject,local_username,created_at) VALUES(?,?,?,?) "
                "ON CONFLICT(provider,external_subject) DO UPDATE SET local_username=excluded.local_username",
                (provider, subject.strip().lower(), username, utc_now()),
            )
            con.commit()
        finally:
            con.close()

    def mapped_user(self, provider: str, subject: str) -> str | None:
        con = self.connect()
        try:
            row = con.execute(
                "SELECT local_username FROM identity_mappings WHERE provider=? AND external_subject=?",
                (provider, subject.strip().lower()),
            ).fetchone()
            return str(row[0]) if row else None
        finally:
            con.close()

    def mappings(self) -> list[dict]:
        con = self.connect()
        try:
            return [dict(row) for row in con.execute(
                "SELECT provider,external_subject,local_username,created_at FROM identity_mappings ORDER BY provider,external_subject"
            ).fetchall()]
        finally:
            con.close()

    def audit(self, actor: str, action: str, channel: str, outcome: str, details: dict | None = None) -> None:
        safe = {k: v for k, v in (details or {}).items() if "token" not in k.lower() and "password" not in k.lower() and "secret" not in k.lower()}
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO audit_events(happened_at,actor,action,channel,outcome,details_json) VALUES(?,?,?,?,?,?)",
                (utc_now(), actor or "anonymous", action, channel, outcome, json.dumps(safe, ensure_ascii=False)),
            )
            con.commit()
        finally:
            con.close()

    def recent_audit(self, limit: int = 100) -> list[dict]:
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT happened_at,actor,action,channel,outcome,details_json FROM audit_events ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
            return [{**dict(row), "details": json.loads(row["details_json"])} for row in rows]
        finally:
            con.close()

    def add_network_snapshot(self, state: dict, plan: dict) -> str:
        snapshot_id = uuid.uuid4().hex
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO network_snapshots(id,state_json,plan_json,status,created_at) VALUES(?,?,?,?,?)",
                (snapshot_id, json.dumps(state, ensure_ascii=False), json.dumps(plan, ensure_ascii=False), "pending", utc_now()),
            )
            con.commit()
            return snapshot_id
        finally:
            con.close()

    def update_network_snapshot(self, snapshot_id: str, status: str) -> bool:
        if status not in {"confirmed", "rolled_back", "failed"}:
            raise ValueError("invalid_snapshot_status")
        column = "confirmed_at" if status == "confirmed" else "rolled_back_at" if status == "rolled_back" else None
        con = self.connect()
        try:
            if column:
                cur = con.execute(f"UPDATE network_snapshots SET status=?,{column}=? WHERE id=?", (status, utc_now(), snapshot_id))
            else:
                cur = con.execute("UPDATE network_snapshots SET status=? WHERE id=?", (status, snapshot_id))
            con.commit()
            return cur.rowcount == 1
        finally:
            con.close()

    def network_snapshot(self, snapshot_id: str) -> dict | None:
        con = self.connect()
        try:
            row = con.execute("SELECT * FROM network_snapshots WHERE id=?", (snapshot_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["state"] = json.loads(result.pop("state_json"))
            result["plan"] = json.loads(result.pop("plan_json"))
            return result
        finally:
            con.close()
