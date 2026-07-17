# Cloudflare Access configuration checklist

1. Create a self-hosted Access application for the product hostname.
2. Create an explicit Allow policy for approved identities; leave default deny in place.
3. Record the application audience tag and team domain in the root-owned environment file.
4. Create a named tunnel whose only origin is `http://127.0.0.1:8781`.
5. Store the tunnel credential outside the repository at `/etc/cloudflared/digua-credentials.json`, mode `0600`.
6. Run `configure_remote_access.sh --provider cloudflare --dry-run` before enabling it.
7. Verify denied identity, allowed identity, wrong audience, expired JWT, bad signature, disable, and LAN continuity.

Never put a tunnel token or credential in this file, Git, SQLite, a URL, or a systemd unit.
