# Expected S100P results

Required before upgrading the verdict:

- ARM64/S100P and required runtime are observed; NAS mount is real and writable only inside approved roots.
- 8765 and 18080 remain loopback; LAN exposes only the product HTTP entry. No NAS management/SMB/NFS/SSH port is newly public.
- `digua.local` and fallback IP open from phones; mDNS failure leaves fallback working.
- First claim works once, replay/remote claim fails, and no default password exists.
- Cookie/CSRF/logout/revoke and admin/operator/viewer matrix pass.
- 360x800, 390x844, 430x932 and 768x1024 browser checks pass without horizontal overflow.
- Service Worker contains no API/download/private responses.
- NAS-off and Internet-off drills show understandable degraded state and preserve LAN access.
- Network bad-config drill automatically rolls back.
- Tailscale authorized/denied/spoof/disable/restart tests pass with Funnel absent.
- Cloudflare Access deny/allow and wrong-audience/expired/bad-signature/disable tests pass when configured.
- Reboot restores the selected configuration.

Do not include credentials, claim text, cookies, Authorization values, private paths or user files in returned results.
