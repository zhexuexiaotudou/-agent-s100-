#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


UPSTREAM = "http://127.0.0.1:18080"
MODEL = "Qwen2.5-1.5B-Instruct-S100P-official"


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenClaw / AI-NAS Qwen2.5 Chat</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:#f4f6f8;color:#182230}.app{max-width:980px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column;padding:20px}.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:14px}.top h1{font-size:22px;margin:0 0 4px}.muted{color:#667085;font-size:13px}.pill{display:inline-flex;align-items:center;border-radius:999px;padding:4px 10px;background:#dcfae6;color:#067647;font-size:12px;border:1px solid #abefc6}.chat{flex:1;background:#fff;border:1px solid #e1e6ec;border-radius:8px;overflow:auto;padding:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.msg{padding:10px 12px;border-radius:8px;margin:0 0 10px;white-space:pre-wrap;line-height:1.48}.user{background:#eef4ff;margin-left:9%}.assistant{background:#f8fafc;margin-right:9%;border:1px solid #edf0f3}.meta{font-size:12px;color:#667085;margin-bottom:6px}.composer{display:flex;gap:10px;margin-top:12px}.composer textarea{flex:1;min-height:72px;resize:vertical;border:1px solid #ccd3dd;border-radius:8px;padding:10px 12px;font:inherit}.composer button{width:108px;border:0;border-radius:8px;background:#155eef;color:white;font-weight:650;cursor:pointer}.composer button:disabled{background:#98a2b3;cursor:not-allowed}.links{font-size:12px;margin-top:8px;color:#475467}.links code{font-family:ui-monospace,Consolas,monospace}.err{color:#b42318}
</style>
</head>
<body>
<main class="app">
  <div class="top">
    <div>
      <h1>OpenClaw / AI-NAS Qwen2.5 Chat</h1>
      <div class="muted">后端：S100P official Qwen2.5 gateway + AI-NAS allowlisted tools</div>
    </div>
    <div><span id="health" class="pill">checking...</span></div>
  </div>
  <section id="chat" class="chat"></section>
  <div class="links">OpenClaw gateway: <code>http://127.0.0.1:18789/health</code> | Qwen gateway: <code>http://127.0.0.1:18080/health</code></div>
  <form id="form" class="composer">
    <textarea id="input" placeholder="输入你的 NAS 需求，例如：帮我找 2024 装修付款相关的合同、发票、收据和聊天截图，并生成证据报告。"></textarea>
    <button id="send" type="submit">发送</button>
  </form>
</main>
<script>
const chat=document.getElementById('chat'), form=document.getElementById('form'), input=document.getElementById('input'), send=document.getElementById('send'), health=document.getElementById('health');
let messages=[];
function add(role,text,meta=''){const box=document.createElement('div');box.className='msg '+role;box.innerHTML='<div class="meta">'+(role==='user'?'你':'AI-NAS')+(meta?' · '+meta:'')+'</div>'+escapeHtml(text);chat.appendChild(box);chat.scrollTop=chat.scrollHeight}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function check(){try{const r=await fetch('/health');const j=await r.json();health.textContent=j.ok?j.model:'offline';if(!j.ok)health.className='pill err'}catch(e){health.textContent='offline';health.className='pill err'}}
form.addEventListener('submit',async e=>{e.preventDefault();const text=input.value.trim();if(!text)return;input.value='';add('user',text);messages.push({role:'user',content:text});send.disabled=true;send.textContent='等待';try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages})});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||r.statusText);const content=j.content||'';messages.push({role:'assistant',content});add('assistant',content,j.model||'');}catch(err){add('assistant','请求失败：'+err.message,'error')}finally{send.disabled=false;send.textContent='发送'}});
check();
</script>
</body>
</html>
"""


def upstream_json(method: str, path: str, payload: dict | None = None, timeout: int = 120) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{UPSTREAM}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"error": raw}
    except Exception as exc:
        return 599, {"error": f"{type(exc).__name__}: {exc}"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            raw = HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if self.path == "/health":
            status, payload = upstream_json("GET", "/health", timeout=10)
            self.send_json({"ok": status == 200 and payload.get("ok") is True, **payload}, HTTPStatus.OK if status == 200 else HTTPStatus.BAD_GATEWAY)
            return
        self.send_json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/chat":
            self.send_json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            self.send_json({"ok": False, "error": f"invalid_json:{exc}"}, HTTPStatus.BAD_REQUEST)
            return
        messages = body.get("messages") if isinstance(body.get("messages"), list) else []
        payload = {"model": MODEL, "messages": messages, "temperature": 0, "max_tokens": 512}
        status, upstream = upstream_json("POST", "/v1/chat/completions", payload, timeout=180)
        if status != 200:
            self.send_json({"ok": False, "error": upstream.get("error") or upstream, "status": status}, HTTPStatus.BAD_GATEWAY)
            return
        choice = ((upstream.get("choices") or [{}])[0] or {})
        message = choice.get("message") or {}
        self.send_json({"ok": True, "model": upstream.get("model") or MODEL, "content": message.get("content") or "", "metadata": message.get("metadata") or {}})


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 18180), Handler)
    print("http://127.0.0.1:18180/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
