#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json
from ai_nas_media import MediaCenter

TOOL_ID = "ai_nas_media_center_gate"; OK = "ok_nas_media_center_gate"

def chk(msg, cond, fails): fails.append(msg) if not cond else None; print(f"  {'PASS' if cond else 'FAIL'}: {msg}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_media_gate_local"))
    args = parser.parse_args()
    rd = ensure_report_dir(args.report_root, "media_gate")
    photos_dir = rd / "Photos"; photos_dir.mkdir(parents=True, exist_ok=True)
    db = rd / "media.db"
    mc = MediaCenter(db)
    fails = []
    print("Goal 6 Media Center Gate Probe (direct)")

    # Create test photos (simulated)
    for i in range(5):
        p = photos_dir / f"photo_{i:03d}.jpg"
        p.write_bytes(b"\xFF\xD8\xFF\xE0" + bytes(i) * 100)
    # Duplicate
    (photos_dir/"photo_dup.jpg").write_bytes((photos_dir/"photo_000.jpg").read_bytes())

    # 1. Index
    print("\n--- Photo Indexing ---")
    r = mc.index_photos(photos_dir)
    chk("Index scanned 6 photos", r["scanned"] == 6, fails)
    chk(f"Indexed {r['indexed']} photos", r["indexed"] >= 5, fails)

    # 2. List
    photos = mc.list_photos()
    chk("List returns photos", len(photos) >= 5, fails)

    # 3. Timeline
    tl = mc.timeline()
    chk("Timeline has entries", len(tl) >= 1, fails)

    # 4. Duplicates
    dups = mc.find_duplicates()
    chk("Duplicate detected", len(dups) >= 1, fails)

    # 5. Albums
    print("\n--- Albums ---")
    r = mc.create_album("vacation", "Summer trip photos")
    chk("Create album", r["ok"], fails)
    albums = mc.list_albums()
    chk("List albums", len(albums) == 1, fails)
    # Add photo to album
    r = mc.add_to_album("vacation", photos[0]["id"])
    chk("Add photo to album", r.get("ok", r.get("error","?")), fails)
    r = mc.add_to_album("vacation", photos[1]["id"])
    album_photos = mc.get_album_photos("vacation")
    chk(f"Album has {len(album_photos)} photos", len(album_photos) == 2, fails)

    # 6. Search
    results = mc.search("photo")
    chk("Search returns results", len(results) >= 4, fails)

    # 7. Stats
    stats = mc.stats()
    chk(f"Stats: {stats['photo_count']} photos, {stats['album_count']} albums", stats["photo_count"] >= 5, fails)

    # DB integrity
    con = sqlite3.connect(str(db))
    chk("Media DB integrity", con.execute("PRAGMA integrity_check").fetchone()[0]=="ok", fails); con.close()

    passed = len(fails) == 0; verdict = OK if passed else "failed_nas_media_center_gate"
    total = 12
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {total-len(fails)}/{total}")
    if fails: print(f"  Failures: {len(fails)}"); [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"passed_count":total-len(fails),"failures":fails}
    safe_write_json(rd/"media_center_gate.json", payload)
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
