from __future__ import annotations

import argparse
import base64
import html
import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBE_ROOT))

from ai_nas_identity import IdentityStore  # noqa: E402

from .network import apply_plan, connect_wifi, inspect_network, rollback_connection, scan_wifi, schedule_rollback, snapshot_connection, validate_plan
from .remote import CloudflareTunnelAdapter, TailscaleServeAdapter
from .store import ProductAccessStore


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="digua-access", description="Manage product access without exposing backend ports")
    root.add_argument("--access-db", type=Path, default=Path(os.environ.get("DIGUA_ACCESS_DB", "/var/lib/digua-ai-nas/product_access.sqlite3")))
    root.add_argument("--identity-db", type=Path, default=Path(os.environ.get("DIGUA_IDENTITY_DB", "/var/lib/digua-ai-nas/identity.sqlite3")))
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("device")
    sub.add_parser("status")
    sub.add_parser("endpoints")
    claim = sub.add_parser("claim-create"); claim.add_argument("--ttl-minutes", type=int, default=30); claim.add_argument("--qr-out", type=Path)
    endpoint = sub.add_parser("endpoint-set"); endpoint.add_argument("channel", choices=("lan_mdns", "tailscale", "cloudflare")); endpoint.add_argument("url"); endpoint.add_argument("--enabled", action="store_true"); endpoint.add_argument("--verified", action="store_true")
    mapping = sub.add_parser("identity-map"); mapping.add_argument("provider", choices=("tailscale", "cloudflare")); mapping.add_argument("subject"); mapping.add_argument("username")
    sub.add_parser("doctor")
    sub.add_parser("network-status")
    sub.add_parser("wifi-scan")
    wifi = sub.add_parser("wifi-connect"); wifi.add_argument("--ssid", required=True); wifi.add_argument("--password-stdin", action="store_true"); wifi.add_argument("--confirm", required=True)
    card = sub.add_parser("access-card"); card.add_argument("--url", default="http://digua.local/setup"); card.add_argument("--out", type=Path, required=True)
    qr = sub.add_parser("qr"); qr.add_argument("--mode", choices=("lan", "tailscale", "cloudflare"), default="lan"); qr.add_argument("--output", type=Path, required=True)
    printable = sub.add_parser("card"); printable.add_argument("--output", type=Path, required=True)
    network = sub.add_parser("network-plan"); network.add_argument("--connection", required=True); network.add_argument("--ipv4-method", choices=("auto", "manual"), default="auto"); network.add_argument("--ipv4-address"); network.add_argument("--ipv4-gateway"); network.add_argument("--dns")
    network_apply = sub.add_parser("network-apply"); network_apply.add_argument("--connection", required=True); network_apply.add_argument("--ipv4-method", choices=("auto", "manual"), default="auto"); network_apply.add_argument("--ipv4-address"); network_apply.add_argument("--ipv4-gateway"); network_apply.add_argument("--dns"); network_apply.add_argument("--confirm", required=True); network_apply.add_argument("--rollback-seconds", type=int, default=120)
    network_confirm = sub.add_parser("network-confirm"); network_confirm.add_argument("snapshot_id")
    network_rollback = sub.add_parser("network-rollback"); network_rollback.add_argument("snapshot_id"); network_rollback.add_argument("--confirm", required=True)
    tailscale = sub.add_parser("tailscale-plan"); tailscale.add_argument("--target", default="http://127.0.0.1:8781")
    cf = sub.add_parser("cloudflare-plan"); cf.add_argument("--hostname", required=True); cf.add_argument("--tunnel-id", required=True); cf.add_argument("--credentials-file", type=Path, default=Path("/etc/cloudflared/digua-credentials.json")); cf.add_argument("--target", default="http://127.0.0.1:8781")
    return root


def main() -> int:
    args = parser().parse_args()
    store = ProductAccessStore(args.access_db)
    identity = IdentityStore(args.identity_db)
    if args.command in {"device", "status"}:
        result = {"ok": True, "device": store.device(), "endpoints": store.endpoints()}
    elif args.command == "endpoints":
        result = {"ok": True, "endpoints": store.endpoints()}
    elif args.command == "claim-create":
        if identity.list_users():
            result = {"ok": False, "error": "device_already_claimed"}
        else:
            token = store.create_claim(args.ttl_minutes)
            result = {"ok": True, "claim_token": token, "expires_in_minutes": max(5, min(args.ttl_minutes, 1440)), "warning": "display_once_do_not_log_or_store"}
            if args.qr_out:
                import qrcode
                from qrcode.image.svg import SvgPathImage
                claim_url = "http://digua.local/setup#claim=" + token
                args.qr_out.parent.mkdir(parents=True, exist_ok=True)
                qrcode.make(claim_url, image_factory=SvgPathImage).save(args.qr_out)
                result["claim_qr_svg"] = str(args.qr_out)
                result["claim_url_uses_fragment"] = True
    elif args.command == "endpoint-set":
        store.set_endpoint(args.channel, args.url, enabled=args.enabled, verified=args.verified)
        result = {"ok": True, "endpoints": store.endpoints()}
    elif args.command == "identity-map":
        if not any(row["username"] == args.username for row in identity.list_users()):
            result = {"ok": False, "error": "local_user_not_found"}
        else:
            store.map_identity(args.provider, args.subject, args.username); result = {"ok": True, "mappings": store.mappings()}
    elif args.command == "doctor":
        result = {"ok": True, "production_verified": False, "device_execution_pending": True, "network": inspect_network(), "tailscale": TailscaleServeAdapter().inspect(), "endpoints": store.endpoints()}
    elif args.command == "network-status":
        result = {"ok": True, "network": inspect_network()}
    elif args.command == "wifi-scan":
        result = scan_wifi()
    elif args.command == "wifi-connect":
        password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Wi-Fi password: ")
        result = connect_wifi(args.ssid, password, confirm=args.confirm)
        password = ""
    elif args.command == "access-card":
        import qrcode
        from qrcode.image.svg import SvgPathImage
        args.out.parent.mkdir(parents=True, exist_ok=True)
        image = qrcode.make(args.url, image_factory=SvgPathImage)
        image.save(args.out)
        result = {"ok": True, "url": args.url, "qr_svg": str(args.out), "contains_secret": False}
    elif args.command == "qr":
        channel = {"lan": "lan_mdns", "tailscale": "tailscale", "cloudflare": "cloudflare"}[args.mode]
        endpoint = next((item for item in store.endpoints() if item["channel"] == channel), None)
        if not endpoint:
            result = {"ok": False, "error": "endpoint_not_configured"}
        else:
            import qrcode
            from qrcode.image.svg import SvgPathImage
            args.output.parent.mkdir(parents=True, exist_ok=True)
            qrcode.make(endpoint["url"], image_factory=SvgPathImage).save(args.output)
            result = {"ok": True, "mode": args.mode, "url": endpoint["url"], "output": str(args.output), "contains_secret": False}
    elif args.command == "card":
        device = store.device(); endpoints = store.endpoints()
        rows = "".join(f"<tr><th>{html.escape(item['channel'])}</th><td>{html.escape(item['url'])}</td><td>{'已启用' if item['enabled'] else '未启用'}</td></tr>" for item in endpoints)
        import io, qrcode
        from qrcode.image.svg import SvgPathImage
        lan_url = next((item["url"] for item in endpoints if item["channel"] == "lan_mdns"), "http://digua.local/")
        qr_buffer = io.BytesIO(); qrcode.make(lan_url, image_factory=SvgPathImage).save(qr_buffer)
        qr_data = base64.b64encode(qr_buffer.getvalue()).decode("ascii")
        content = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>地瓜 AI-NAS 访问卡</title><style>body{{font-family:system-ui;max-width:720px;margin:40px auto;padding:24px}}h1{{font-size:36px}}img{{width:180px;height:180px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}@media print{{body{{margin:0}}}}</style></head><body><small>地瓜 AI-NAS</small><h1>{html.escape(device['device_name'])}</h1><p>设备编号：{html.escape(device['short_device_id'])}</p><img alt='本地访问二维码' src='data:image/svg+xml;base64,{qr_data}'><table>{rows}</table><p>手机与设备在同一局域网时打开 <strong>{html.escape(lan_url)}</strong>。远程入口只在管理员明确启用后可用。</p></body></html>"""
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(content, encoding="utf-8")
        result = {"ok": True, "output": str(args.output), "contains_secret": False}
    elif args.command == "network-plan":
        payload = {key: value for key, value in {"connection": args.connection, "ipv4_method": args.ipv4_method, "ipv4_address": args.ipv4_address, "ipv4_gateway": args.ipv4_gateway, "dns": args.dns}.items() if value}
        result = validate_plan(payload)
    elif args.command == "network-apply":
        payload = {key: value for key, value in {"connection": args.connection, "ipv4_method": args.ipv4_method, "ipv4_address": args.ipv4_address, "ipv4_gateway": args.ipv4_gateway, "dns": args.dns}.items() if value}
        state = snapshot_connection(args.connection)
        if not state.get("ok"):
            result = state
        else:
            snapshot_id = store.add_network_snapshot(state, payload)
            changed = apply_plan(payload, confirm=args.confirm)
            rollback = schedule_rollback(snapshot_id, str(args.access_db), args.rollback_seconds) if changed.get("ok") else {"ok": False, "error": "change_failed"}
            result = {"ok": bool(changed.get("ok") and rollback.get("ok")), "snapshot_id": snapshot_id, "change": changed, "automatic_rollback": rollback, "confirm_command": f"digua-access --access-db {args.access_db} network-confirm {snapshot_id}"}
    elif args.command == "network-confirm":
        updated = store.update_network_snapshot(args.snapshot_id, "confirmed")
        unit = f"digua-network-rollback-{args.snapshot_id[:12]}"
        timer_cancelled = False
        if updated and shutil.which("systemctl"):
            stopped = subprocess.run(["systemctl", "stop", unit + ".timer", unit + ".service"], capture_output=True, text=True, check=False)
            timer_cancelled = stopped.returncode == 0
        result = {"ok": updated, "snapshot_id": args.snapshot_id, "rollback_timer_cancelled": timer_cancelled}
    elif args.command == "network-rollback":
        snapshot = store.network_snapshot(args.snapshot_id)
        if not snapshot:
            result = {"ok": False, "error": "network_snapshot_not_found"}
        else:
            restored = rollback_connection(snapshot["state"], confirm=args.confirm)
            if restored.get("ok"): store.update_network_snapshot(args.snapshot_id, "rolled_back")
            result = {**restored, "snapshot_id": args.snapshot_id}
    elif args.command == "tailscale-plan":
        result = {"ok": True, "plan": TailscaleServeAdapter(args.target).plan()}
    elif args.command == "cloudflare-plan":
        adapter = CloudflareTunnelAdapter(args.hostname, args.tunnel_id, args.credentials_file, args.target)
        result = {"ok": True, "plan": adapter.plan(), "config": adapter.config_yaml()}
    else:
        result = {"ok": False, "error": "unknown_command"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
