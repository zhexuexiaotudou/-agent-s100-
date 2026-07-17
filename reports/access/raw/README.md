# Raw device evidence

This directory contains the secret-reviewed 2026-07-17 S100P/NAS summary and Playwright screenshots captured against the live LAN facade. It deliberately excludes credentials, cookies, claim codes, auth URLs, runtime databases, NAS files and private logs.

- `20260717_s100p_live_summary.json`: sanitized hardware, mount, service, socket and drill results.
- `20260717_s100p_tailscale_live_summary.json`: sanitized private-Serve, identity, reboot and rollback results after tailnet approval.
- `20260717_live_ui_390x844.png`: live anonymous mobile UI.
- `20260717_live_setup_390x844.png`: live first-setup layout after overflow correction.
- `20260717_live_ui_768x1024.png`: live tablet layout and navigation.

The full no-secret command sequence is summarized in `../command_execution_log.jsonl`. The earlier LAN summary preserves the pre-approval `NeedsLogin` snapshot; the later Tailscale summary records the approved `Running` state. No authorization URL, Cookie or session token is stored here.
