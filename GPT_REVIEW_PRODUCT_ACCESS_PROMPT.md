# GPT Review: Digua AI-NAS Product Access

Review this delivery as an adversarial product/security reviewer. Separate repository evidence, offline simulation and real S100P/NAS/external evidence. The current declared verdict is `product_access_code_complete_s100p_execution_bundle_ready`; do not upgrade it without raw device results.

Evaluate: no-computer daily operation; LAN/Tailscale/Cloudflare boundaries; public exposure; Tailscale header trust; Cloudflare JWT verification; claim race/takeover; session/CSRF/roles/rate limit; mDNS fallback; network rollback; PWA private caching; preservation of NAS/OpenClaw/Qwen policy/ACL; evidence sufficiency; demo/pilot readiness; and the next fixes.

Pay special attention to Python facade proxy correctness, body/stream limits, viewer read-like POST allowlist, Cloudflare JWKS and RSA implementation, systemd capability/sandbox paths, NetworkManager rollback timer cancellation, Avahi conflict handling, Wi-Fi secret flow, real mobile installability on LAN HTTP, and whether the validation bundle can prove each pending row without leaking secrets.
