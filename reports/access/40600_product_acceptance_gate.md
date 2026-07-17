# 40600 Product Acceptance Gate

Offline acceptance passed: 146 Python tests (135 pre-existing plus 11 product-access), JS syntax, Python compile, HTTP integration, release contracts and Linux-container clean-install claim-mode simulation. Playwright rendered `/ui` and `/setup` with zero console errors; 360x800, 390x844, 430x932 and 768x1024 reported no horizontal overflow. No Dream7B tests or files were changed.

Hardware acceptance is intentionally open: reboot, LAN/mDNS, physical-phone checks, Internet-off, NAS-off, Qwen/OpenClaw degraded startup, network rollback, Tailscale and Cloudflare require powered hardware and external accounts. These rows are `pending_hardware`, not failed and not passed.

Verdict for this environment: `product_access_code_complete_s100p_execution_bundle_ready`.
