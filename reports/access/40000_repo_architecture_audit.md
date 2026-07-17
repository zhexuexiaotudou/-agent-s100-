# 40000 Repository Architecture Audit

- Stack: native Python `ThreadingHTTPServer`, native HTML/CSS/JS, SQLite, systemd release path; no active Compose or reusable reverse proxy was found.
- Locked ports: portal 127.0.0.1:8765, Qwen 127.0.0.1:18080, Dream7B 18888/18889 excluded.
- Existing controls: bearer sessions hashed at rest, PBKDF2 password hashing, login rate limit, ACL-filtered storage, policy/allowlist and controlled write chains.
- Gaps: public bootstrap route, browser session token storage, no current-v2 PWA registration, no port-80/mDNS product entry, no first claim, no external identity mapping, no remote adapters, no transactional network layer.
- Choice: add one Python access facade on 80 and a separate loopback remote ingress on 8781. Preserve all business APIs and translate HttpOnly Cookie sessions to the existing bearer contract internally.
- Offline boundary: S100P/NAS unavailable; process, port, mount and hardware findings are repository facts, not live facts.

Gates: `architecture_understood=true`, `no_port_conflict=true`, `safe_change_plan=true`.
