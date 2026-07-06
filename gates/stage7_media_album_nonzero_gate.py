from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "probes"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from ai_nas_media import MediaCenter  # noqa: E402
from product_demo_seed_data import create_images  # noqa: E402


NAME = "stage7_media_album_nonzero_gate"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Gate that NAS photos are indexed into non-empty media albums.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.personal_root:
        payload = _payload([check("personal_root configured", False, "missing")], {})
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 1

    photo_dir = Path(args.personal_root) / "Photos" / "stage7_smart_album_demo"
    photo_dir.mkdir(parents=True, exist_ok=True)
    create_images(photo_dir)

    media = MediaCenter(args.report_root / "media.sqlite3")
    index = media.index_photos(photo_dir, asset_root=Path(args.personal_root), source_id="stage7_media_album_nonzero_gate")
    album = media.create_album("智能分类验收相册", "Stage7 smart album acceptance records")
    photos = media.list_photos(limit=50)
    if photos:
        media.add_to_album("智能分类验收相册", int(photos[0]["id"]))
    status = media.status()
    timeline = media.timeline()
    albums = media.list_albums()
    public_payload = {"status": status, "photos": photos, "timeline": timeline, "albums": albums}
    encoded = json.dumps(public_payload, ensure_ascii=False)
    checks = [
        check("demo photos exist", len(list(photo_dir.glob("*"))) >= 8, len(list(photo_dir.glob("*")))),
        check("media index scanned >= 5", int(index.get("scanned") or 0) >= 5, index),
        check("photo_count >= 5", int(status.get("photo_count") or 0) >= 5, status.get("photo_count")),
        check("photos API has items", len(photos) >= 5, len(photos)),
        check("timeline non-empty", bool(timeline), timeline[:3]),
        check("album list available", bool(albums), albums[:3]),
        check("raw path not returned", all(marker not in encoded for marker in ["/mnt/nas/", "C:\\", "F:\\", "/home/", "/root/"]), "redacted"),
    ]
    payload = _payload(checks, {"index": index, **public_payload})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


def _payload(checks: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_media_album_nonzero_gate", "blocked_stage7_media_album_nonzero_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "evidence": evidence,
    }


if __name__ == "__main__":
    raise SystemExit(main())
