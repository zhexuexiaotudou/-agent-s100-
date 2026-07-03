import http.server, socketserver, json, urllib.request, os, time, threading, subprocess, sys

PORT = 53306
PROXY = 'http://127.0.0.1:18080'
PORTAL = r'F:\Project\Digua\scripts\probes\nas_web_os_portal.html'
ASSETS = r'F:\Project\Digua\scripts\probes\portal_assets'
GATEWAY_PORT = 153306

def start_portal():
    subprocess.Popen([sys.executable,
        r'F:\Project\Digua\scripts\probes\ai_nas_operator_portal_server.py',
        '--port', str(GATEWAY_PORT),
        '--report-root', r'F:\Project\Digua\reports',
        '--no-refresh'],
        cwd=r'F:\Project\Digua\scripts\probes')

threading.Thread(target=start_portal, daemon=True).start()
time.sleep(3)

class H(http.server.SimpleHTTPRequestHandler):
    def _proxy(self, method='GET', body=None, ct='application/json'):
        try:
            url = PROXY + self.path
            req = urllib.request.Request(url, data=body, method=method)
            if ct and body:
                req.add_header('Content-Type', ct)
            resp = urllib.request.urlopen(req, timeout=120)
            data = resp.read()
            self.send_response(resp.status)
            self.send_header('Access-Control-Allow-Origin', '*')
            for k, v in resp.getheaders():
                if k.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(502, str(e))

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(PORTAL, 'r', encoding='utf-8') as f:
                self.wfile.write(f.read().encode('utf-8'))
            return
        if self.path.startswith('/v1/') or self.path in ('/health', '/v1/models'):
            self._proxy()
            return
        if self.path.startswith('/assets/'):
            fp = ASSETS + self.path[7:]
            if os.path.isfile(fp):
                self.send_response(200)
                ct = 'image/png' if fp.endswith('.png') else 'text/css'
                self.send_header('Content-Type', ct)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(fp, 'rb') as f:
                    self.wfile.write(f.read())
                return
        try:
            url = f'http://127.0.0.1:{GATEWAY_PORT}{self.path}'
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(404)

    def do_POST(self):
        cl = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(cl) if cl else None
        ct = self.headers.get('Content-Type', 'application/json')
        if self.path.startswith('/v1/'):
            self._proxy('POST', body, ct)
            return
        try:
            url = f'http://127.0.0.1:{GATEWAY_PORT}{self.path}'
            req = urllib.request.Request(url, data=body, method='POST')
            if ct and body:
                req.add_header('Content-Type', ct)
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

if __name__ == '__main__':
    with socketserver.TCPServer(('127.0.0.1', PORT), H) as h:
        print(f'Wrapper proxy on http://127.0.0.1:{PORT}')
        h.serve_forever()
