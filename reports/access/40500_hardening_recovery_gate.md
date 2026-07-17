# 40500 Hardening and Recovery Gate

Implemented separate trust listeners, identity-header stripping, CSP/security headers, same-origin operation, body limit, viewer mutation boundary, secret-safe audit, NetworkManager discovery, non-secret IP/DNS snapshots, confirmation and timed rollback, strict deploy wrappers, upgrade rollback and data-preserving uninstall.

Threat model covers LAN claim theft, header/JWT spoofing, session/CSRF/XSS, path/NAS exposure, tokens, mDNS/QR replacement, network lockout, logs and degraded bypass. Real network rollback and service recovery remain destructive-device tests and are deferred.
