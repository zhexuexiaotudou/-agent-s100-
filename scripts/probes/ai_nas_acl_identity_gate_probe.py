#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, socket, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_identity import IdentityStore

TOOL_ID = "ai_nas_acl_identity_gate"
OK_VERDICT = "ok_nas_acl_identity_gate"

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    try: return int(s.getsockname()[1])
    finally: s.close()

def h(method, url, body=None, token=None, timeout=30):
    d = None; hdrs = {"Accept": "application/json"}
    if token: hdrs["Authorization"] = f"Bearer {token}"
    if body is not None: d = json.dumps(body).encode(); hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=d, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": 200 <= r.status < 300, "status": r.status, "payload": json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        try: payload = json.loads(e.read().decode())
        except: payload = {}
        return {"ok": False, "status": e.code, "payload": payload}

def multipart(url, fname, content, token=None):
    bnd = "gate-identity-boundary"
    body = b"--"+bnd.encode()+b"\r\nContent-Disposition: form-data; name=\"file\"; filename=\""+fname.encode()+b"\"\r\nContent-Type: application/octet-stream\r\n\r\n"+content+b"\r\n--"+bnd.encode()+b"--\r\n"
    hdrs = {"Content-Type": "multipart/form-data; boundary="+bnd}
    if token: hdrs["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"ok": 200 <= r.status < 300, "status": r.status, "payload": json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        try: payload = json.loads(e.read().decode())
        except: payload = {}
        return {"ok": False, "status": e.code, "payload": payload}

def chk(msg, cond, fails): fails.append(msg) if not cond else None; print(f"  {'PASS' if cond else 'FAIL'}: {msg}")

def wait_http_ready(base_url: str, proc: subprocess.Popen, timeout: float = 10.0) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{base_url}/api/storage/status", timeout=0.5) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            time.sleep(0.1)
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_acl_identity_gate_local"))
    args = parser.parse_args()
    rd = ensure_report_dir(args.report_root, "acl_identity_gate")
    port = free_port()
    pr = rd / "Personal"; pr.mkdir(parents=True, exist_ok=True)
    for d in ["Movies","Documents","Photos","Inbox"]: (pr/d).mkdir(exist_ok=True)
    ident_db = rd / "identity.sqlite3"
    idx_db = rd / "index.sqlite3"
    cmd = [sys.executable, str(Path(__file__).parent/"ai_nas_operator_portal_server.py"),
           "--bind","127.0.0.1","--port",str(port),"--report-root",str(rd),
           "--personal-root",str(pr),"--sqlite-index-path",str(idx_db),
           "--identity-db-path",str(ident_db),"--storage-max-files","200","--no-refresh"]
    BASE = f"http://127.0.0.1:{port}"; fails = []
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ready = wait_http_ready(BASE, proc)
    print("AI-NAS ACL Identity Gate Probe\n  server:", BASE)
    chk("Portal server ready", ready, fails)

    # Bootstrap admin and create users via HTTP for proper token handling
    print("\n--- Users & Authentication ---")
    r = h("POST", f"{BASE}/api/identity/create-user", {"username":"admin","password":"admin123"})
    chk("Bootstrap admin created", r["ok"] and r["payload"].get("ok"), fails)
    r = h("POST", f"{BASE}/api/identity/login", {"username":"admin","password":"admin123"})
    atok = r["payload"].get("token"); chk("Admin login", r["ok"] and bool(atok), fails)
    r = h("POST", f"{BASE}/api/identity/create-user", {"username":"alice","password":"alice123"}, atok)
    chk("Create user alice", r["ok"] and r["payload"].get("ok"), fails)
    r = h("POST", f"{BASE}/api/identity/create-user", {"username":"bob","password":"bob123"}, atok)
    chk("Create user bob", r["ok"] and r["payload"].get("ok"), fails)
    r = h("GET", f"{BASE}/api/identity/users", token=atok)
    chk("List users (3 users)", len(r["payload"].get("users",[])) == 3, fails)
    r = h("POST", f"{BASE}/api/identity/login", {"username":"alice","password":"alice123"})
    alice_tok = r["payload"].get("token"); chk("Alice login", r["ok"] and bool(alice_tok), fails)
    r = h("POST", f"{BASE}/api/identity/login", {"username":"bob","password":"bob123"})
    bob_tok = r["payload"].get("token"); chk("Bob login", r["ok"] and bool(bob_tok), fails)
    chk("Alice session valid", h("GET", f"{BASE}/api/identity/session", token=alice_tok)["ok"], fails)
    r = h("POST", f"{BASE}/api/identity/login", {"username":"alice","password":"wrong"})
    chk("Bad credentials rejected", r["status"] == 401, fails)
    r = h("POST", f"{BASE}/api/identity/logout", token=bob_tok)
    chk("Bob logout", r["ok"] and r["payload"].get("ok"), fails)
    r = h("POST", f"{BASE}/api/identity/login", {"username":"bob","password":"bob123"})
    bob_tok = r["payload"].get("token"); chk("Bob re-login for ACL checks", r["ok"] and bool(bob_tok), fails)

    print("\n--- Groups ---")
    for gn in ["editors","viewers"]:
        r = h("POST", f"{BASE}/api/identity/create-group", {"name":gn}, atok)
        chk(f"Create group {gn}", r["ok"] and r["payload"].get("ok"), fails)
    r = h("POST", f"{BASE}/api/identity/add-member", {"group":"editors","username":"alice"}, atok)
    chk("Add alice to editors", r["ok"] and r["payload"].get("ok"), fails)
    r = h("POST", f"{BASE}/api/identity/add-member", {"group":"viewers","username":"bob"}, atok)
    chk("Add bob to viewers", r["ok"] and r["payload"].get("ok"), fails)
    r = h("GET", f"{BASE}/api/identity/groups", token=atok)
    chk("List groups (2 groups)", len(r["payload"].get("groups",[])) == 2, fails)

    print("\n--- Directory ACLs ---")
    r = h("POST", f"{BASE}/api/identity/set-acl", {"path":"Inbox","principal_type":"user","principal_name":"alice","permission":"write"}, atok)
    chk("Set ACL: alice write Inbox", r["ok"] and r["payload"].get("ok"), fails)
    r = h("POST", f"{BASE}/api/identity/set-acl", {"path":"Documents","principal_type":"user","principal_name":"alice","permission":"read"}, atok)
    chk("Set ACL: alice read Documents", r["ok"] and r["payload"].get("ok"), fails)
    r = h("POST", f"{BASE}/api/identity/set-acl", {"path":"Photos","principal_type":"group","principal_name":"viewers","permission":"read"}, atok)
    chk("Set ACL: viewers group read Photos", r["ok"] and r["payload"].get("ok"), fails)
    r = h("GET", f"{BASE}/api/identity/acls", token=atok)
    chk("List ACLs (3 entries)", len(r["payload"].get("acls",[])) == 3, fails)

    print("\n--- Permission Enforcement: Visibility ---")
    r = h("GET", f"{BASE}/api/identity/visible-paths", token=alice_tok)
    ap = r["payload"].get("paths",[]); chk("Alice can see Inbox","Inbox" in ap, fails); chk("Alice can see Documents","Documents" in ap, fails); chk("Alice cannot see Movies","Movies" not in ap, fails)
    r = h("GET", f"{BASE}/api/identity/visible-paths", token=bob_tok)
    bp = r["payload"].get("paths",[]); chk("Bob can see Photos (group ACL)","Photos" in bp, fails); chk("Bob cannot see Inbox","Inbox" not in bp, fails)

    print("\n--- Storage ACL Enforcement: Write ---")
    alice_tok2 = h("POST", f"{BASE}/api/identity/login", {"username":"alice","password":"alice123"})["payload"].get("token")
    bob_tok2 = h("POST", f"{BASE}/api/identity/login", {"username":"bob","password":"bob123"})["payload"].get("token")
    r = multipart(f"{BASE}/api/storage/upload?path=Inbox","alice_f.txt",b"alice",alice_tok2)
    chk("Alice upload to Inbox (allowed)", r["ok"] and r["payload"].get("ok"), fails)
    r = multipart(f"{BASE}/api/storage/upload?path=Inbox","bob_f.txt",b"bob",bob_tok2)
    chk("Bob upload to Inbox (denied, no ACL)", not r["payload"].get("ok", False), fails)

    print("\n--- Storage ACL Enforcement: Read ---")
    r = h("GET", f"{BASE}/api/storage/acl-list?path=Inbox", token=alice_tok)
    chk("Alice list Inbox (allowed)", r["ok"] and r["payload"].get("ok",False), fails)
    r = h("GET", f"{BASE}/api/storage/acl-list?path=Documents", token=alice_tok)
    chk("Alice list Documents (allowed)", r["ok"] and r["payload"].get("ok",False), fails)
    r = h("GET", f"{BASE}/api/storage/acl-list?path=Photos", token=alice_tok)
    chk("Alice list Photos (denied)", not r["payload"].get("ok", True), fails)

    print("\n--- Backward Compatibility ---")
    r = h("GET", f"{BASE}/api/storage/list"); chk("No-auth root list works", r["ok"], fails)
    r = h("GET", f"{BASE}/api/storage/status"); chk("No-auth status works", r["ok"] and r["payload"].get("ok"), fails)
    r = h("GET", f"{BASE}/api/storage/list?path=..", token=atok)
    chk("Traversal blocked even for admin", r["status"]==400, fails)

    print("\n--- Admin Permissions ---")
    r = h("GET", f"{BASE}/api/identity/visible-paths", token=atok)
    chk("Admin wildcard", r["payload"].get("paths",[])==["*"], fails)
    r = h("GET", f"{BASE}/api/storage/acl-list?path=Documents", token=atok)
    chk("Admin lists Documents", r["ok"] and r["payload"].get("ok",False), fails)

    print("\n--- DB Integrity ---")
    import sqlite3; con = sqlite3.connect(str(ident_db))
    chk("Identity DB integrity", con.execute("PRAGMA integrity_check").fetchone()[0]=="ok", fails); con.close()

    proc.terminate(); proc.wait(timeout=5)
    passed = len(fails) == 0; verdict = OK_VERDICT if passed else "failed_nas_acl_identity_gate"
    total = 31
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {total-len(fails)}/{total}")
    if fails:
        print(f"  Failures: {len(fails)}"); [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"scope":"Goal 2 identity/ACL gate","passed_count":total-len(fails),"failures":fails}
    safe_write_json(rd/"nas_acl_identity_gate.json", payload)
    safe_write_text(rd/"nas_acl_identity_gate.md", f"# AI-NAS ACL Identity Gate\n\n- verdict: `{verdict}`\n- passed: {total-len(fails)}/{total}\n")
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
