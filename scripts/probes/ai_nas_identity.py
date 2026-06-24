#!/usr/bin/env python3
"""AI-NAS Identity Layer — users, groups, sessions, directory ACLs."""
from __future__ import annotations
import hashlib, json, secrets, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SID_BYTES = 32
DEFAULT_SESSION_TTL_SECONDS = 86400

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"pbkdf2:sha256:100000:{salt}:{dk.hex()}"

def _verify_password(password: str, stored: str) -> bool:
    parts = stored.split(":")
    if len(parts) != 5 or parts[0] != "pbkdf2" or parts[1] != "sha256":
        return False
    _, _, iterations, salt, expected = parts
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    return secrets.compare_digest(dk.hex(), expected)

def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS identity_meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS groups_ (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS group_members (group_id INTEGER NOT NULL REFERENCES groups_(id) ON DELETE CASCADE, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, PRIMARY KEY(group_id, user_id));
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS directory_acls (id INTEGER PRIMARY KEY AUTOINCREMENT, relative_path TEXT NOT NULL, principal_type TEXT NOT NULL CHECK(principal_type IN('user','group')), principal_name TEXT NOT NULL, permission TEXT NOT NULL CHECK(permission IN('read','write','admin')), created_at TEXT NOT NULL, UNIQUE(relative_path, principal_type, principal_name, permission));
        CREATE INDEX IF NOT EXISTS idx_directory_acls_path ON directory_acls(relative_path);
        CREATE INDEX IF NOT EXISTS idx_directory_acls_principal ON directory_acls(principal_type, principal_name);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """)
    con.execute("INSERT OR IGNORE INTO identity_meta(key,value) VALUES('schema_version','1')")
    con.commit(); con.close()


class IdentityStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        _init_db(db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.execute("PRAGMA foreign_keys=ON")
        con.row_factory = sqlite3.Row
        return con

    def create_user(self, username: str, password: str, role: str = "user") -> dict:
        if not username or not password:
            return {"ok": False, "error": "username_and_password_required"}
        con = self._connect()
        user_count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        con.close()
        if user_count == 0:
            role = "admin"
        if role not in ("user", "admin"):
            return {"ok": False, "error": "invalid_role"}
        now = _now_iso()
        pw_hash = _hash_password(password)
        con = self._connect()
        try:
            con.execute("INSERT INTO users(username,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)", (username, pw_hash, role, now, now))
            con.commit()
            uid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"ok": True, "user": {"id": uid, "username": username, "role": role, "created_at": now}}
        except sqlite3.IntegrityError:
            return {"ok": False, "error": "username_already_exists"}
        finally:
            con.close()

    def delete_user(self, username: str) -> dict:
        con = self._connect()
        try:
            cur = con.execute("DELETE FROM users WHERE username=?", (username,))
            con.commit()
            if cur.rowcount == 0:
                return {"ok": False, "error": "user_not_found"}
            return {"ok": True}
        finally:
            con.close()

    def list_users(self) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute("SELECT id,username,role,created_at FROM users ORDER BY username").fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()

    def login(self, username: str, password: str, ttl: int = DEFAULT_SESSION_TTL_SECONDS) -> dict:
        con = self._connect()
        try:
            row = con.execute("SELECT id,password_hash,role FROM users WHERE username=?", (username,)).fetchone()
            if not row or not _verify_password(password, row["password_hash"]):
                return {"ok": False, "error": "invalid_credentials"}
            token = secrets.token_hex(SID_BYTES)
            now = _now_iso(); exp = datetime.now(timezone.utc).timestamp() + ttl
            exp_iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
            con.execute("INSERT INTO sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)", (token, row["id"], now, exp_iso))
            con.commit()
            return {"ok": True, "token": token, "expires_at": exp_iso, "user": {"id": row["id"], "username": username, "role": row["role"]}}
        finally:
            con.close()

    def validate_token(self, token: str) -> dict | None:
        con = self._connect()
        try:
            row = con.execute("SELECT u.id,u.username,u.role,s.expires_at FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=?", (token,)).fetchone()
            if not row: return None
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
                con.execute("DELETE FROM sessions WHERE token=?", (token,)); con.commit()
                return None
            return {"id": row["id"], "username": row["username"], "role": row["role"]}
        finally:
            con.close()

    def logout(self, token: str) -> dict:
        con = self._connect()
        try:
            cur = con.execute("DELETE FROM sessions WHERE token=?", (token,)); con.commit()
            return {"ok": True, "sessions_removed": cur.rowcount}
        finally:
            con.close()

    def create_group(self, name: str) -> dict:
        if not name: return {"ok": False, "error": "group_name_required"}
        now = _now_iso(); con = self._connect()
        try:
            con.execute("INSERT INTO groups_(name,created_at) VALUES(?,?)", (name, now)); con.commit()
            gid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"ok": True, "group": {"id": gid, "name": name, "created_at": now}}
        except sqlite3.IntegrityError:
            return {"ok": False, "error": "group_already_exists"}
        finally:
            con.close()

    def delete_group(self, name: str) -> dict:
        con = self._connect()
        try:
            cur = con.execute("DELETE FROM groups_ WHERE name=?", (name,)); con.commit()
            if cur.rowcount == 0: return {"ok": False, "error": "group_not_found"}
            return {"ok": True}
        finally:
            con.close()

    def list_groups(self) -> list[dict]:
        con = self._connect()
        try:
            return [dict(row) for row in con.execute("SELECT id,name,created_at FROM groups_ ORDER BY name").fetchall()]
        finally:
            con.close()

    def add_group_member(self, group_name: str, username: str) -> dict:
        con = self._connect()
        try:
            gr = con.execute("SELECT id FROM groups_ WHERE name=?", (group_name,)).fetchone()
            if not gr: return {"ok": False, "error": "group_not_found"}
            ur = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if not ur: return {"ok": False, "error": "user_not_found"}
            con.execute("INSERT OR IGNORE INTO group_members(group_id,user_id) VALUES(?,?)", (gr["id"], ur["id"])); con.commit()
            return {"ok": True}
        finally:
            con.close()

    def remove_group_member(self, group_name: str, username: str) -> dict:
        con = self._connect()
        try:
            cur = con.execute("DELETE FROM group_members WHERE group_id=(SELECT id FROM groups_ WHERE name=?) AND user_id=(SELECT id FROM users WHERE username=?)", (group_name, username)); con.commit()
            if cur.rowcount == 0: return {"ok": False, "error": "membership_not_found"}
            return {"ok": True}
        finally:
            con.close()

    def get_user_groups(self, username: str) -> list[str]:
        con = self._connect()
        try:
            rows = con.execute("SELECT g.name FROM groups_ g JOIN group_members gm ON g.id=gm.group_id JOIN users u ON gm.user_id=u.id WHERE u.username=?", (username,)).fetchall()
            return [row["name"] for row in rows]
        finally:
            con.close()

    def set_acl(self, relative_path: str, principal_type: str, principal_name: str, permission: str) -> dict:
        if principal_type not in ("user","group"): return {"ok": False, "error": "invalid_principal_type"}
        if permission not in ("read","write","admin"): return {"ok": False, "error": "invalid_permission"}
        cleaned = relative_path.strip().strip("/") or ""
        now = _now_iso(); con = self._connect()
        try:
            con.execute("INSERT OR IGNORE INTO directory_acls(relative_path,principal_type,principal_name,permission,created_at) VALUES(?,?,?,?,?)", (cleaned, principal_type, principal_name, permission, now)); con.commit()
            return {"ok": True, "acl": {"relative_path": cleaned, "principal_type": principal_type, "principal_name": principal_name, "permission": permission}}
        finally:
            con.close()

    def remove_acl(self, relative_path: str, principal_type: str, principal_name: str, permission: str) -> dict:
        cleaned = relative_path.strip().strip("/") or ""
        con = self._connect()
        try:
            cur = con.execute("DELETE FROM directory_acls WHERE relative_path=? AND principal_type=? AND principal_name=? AND permission=?", (cleaned, principal_type, principal_name, permission)); con.commit()
            if cur.rowcount == 0: return {"ok": False, "error": "acl_not_found"}
            return {"ok": True}
        finally:
            con.close()

    def list_acls(self, relative_path: str | None = None) -> list[dict]:
        con = self._connect()
        try:
            if relative_path is not None:
                cleaned = relative_path.strip().strip("/") or ""
                rows = con.execute("SELECT id,relative_path,principal_type,principal_name,permission,created_at FROM directory_acls WHERE relative_path=? ORDER BY principal_type,principal_name,permission", (cleaned,)).fetchall()
            else:
                rows = con.execute("SELECT id,relative_path,principal_type,principal_name,permission,created_at FROM directory_acls ORDER BY relative_path,principal_type,principal_name,permission").fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()

    def check_acl(self, username: str, relative_path: str, required: str) -> bool:
        con = self._connect()
        try:
            ur = con.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
            if not ur: return False
            if ur["role"] == "admin": return True
            groups = self.get_user_groups(username)
            cleaned = relative_path.strip().strip("/") or ""
            parts = cleaned.split("/") if cleaned else [""]
            for depth in range(len(parts), -1, -1):
                ancestor = "/".join(parts[:depth]).strip("/") or ""
                up = con.execute("SELECT permission FROM directory_acls WHERE relative_path=? AND principal_type='user' AND principal_name=?", (ancestor, username)).fetchall()
                if _has_sufficient(up, required): return True
                for gn in groups:
                    gp = con.execute("SELECT permission FROM directory_acls WHERE relative_path=? AND principal_type='group' AND principal_name=?", (ancestor, gn)).fetchall()
                    if _has_sufficient(gp, required): return True
            return False
        finally:
            con.close()

    def get_visible_paths(self, username: str) -> list[str]:
        con = self._connect()
        try:
            ur = con.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
            if not ur: return []
            if ur["role"] == "admin": return ["*"]
            groups = self.get_user_groups(username)
            if not groups:
                rows = con.execute("SELECT DISTINCT relative_path FROM directory_acls WHERE permission IN ('read','write','admin') AND principal_type='user' AND principal_name=? ORDER BY relative_path", (username,)).fetchall()
            else:
                ph = ",".join(["?"] * len(groups))
                sql = "SELECT DISTINCT relative_path FROM directory_acls WHERE permission IN ('read','write','admin') AND ((principal_type='user' AND principal_name=?) OR (principal_type='group' AND principal_name IN (" + ph + "))) ORDER BY relative_path"
                rows = con.execute(sql, [username] + groups).fetchall()
            seen = {""}
            for row in rows:
                path = row["relative_path"]
                seen.add(path)
                parts = path.split("/")
                for i in range(1, len(parts)):
                    seen.add("/".join(parts[:i]))
            return sorted(seen)
        finally:
            con.close()


def _has_sufficient(rows: list[sqlite3.Row], required: str) -> bool:
    levels = {"read": 1, "write": 2, "admin": 3}
    req = levels.get(required, 0)
    for row in rows:
        if levels.get(row["permission"], 0) >= req:
            return True
    return False


def parse_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    parts = authorization_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None
