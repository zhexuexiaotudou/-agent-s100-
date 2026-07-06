#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path
from typing import Any

from PIL import Image

from _demo_corpus_common import (
    CORPUS_ROOT,
    download_bytes,
    is_allowed_license,
    load_yaml,
    manifest_record,
    relative_to_corpus,
    safe_slug,
    sha256_file,
    write_json,
    write_jsonl,
)


SEARCH_TERMS = {
    "person": "person standing photo",
    "white_shirt_person": "person white shirt photo",
    "red_clothes": "person red shirt photo",
    "black_clothes": "person black shirt photo",
    "cat": "cat photo",
    "dog": "dog photo",
    "laptop": "laptop computer photo",
    "book": "book photo",
    "cup": "cup photo",
    "car": "car photo",
    "landscape": "landscape photo",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a small Wikimedia Commons subset with license metadata.")
    parser.add_argument("--recipe", type=Path, default=CORPUS_ROOT / "recipes" / "target_classes.yaml")
    parser.add_argument("--output-dir", type=Path, default=CORPUS_ROOT / "downloaded" / "wikimedia")
    parser.add_argument("--manifest-out", type=Path, default=CORPUS_ROOT / "manifests" / "wikimedia_manifest.jsonl")
    parser.add_argument("--max-per-class", type=int, default=4)
    parser.add_argument("--max-bytes", type=int, default=6_000_000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    recipe = load_yaml(args.recipe)
    image_classes = recipe.get("image_classes") or {}
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for class_id, config in image_classes.items():
        if "wikimedia" not in set(config.get("sources") or []):
            continue
        term = SEARCH_TERMS.get(class_id, class_id.replace("_", " "))
        try:
            candidates = search_commons(term, limit=max(args.max_per_class * 5, 10))
        except Exception as exc:
            failures.append({"class_id": class_id, "error": f"search:{type(exc).__name__}:{exc}"})
            continue
        accepted = 0
        for candidate in candidates:
            if accepted >= args.max_per_class:
                break
            try:
                info = fetch_image_info(candidate)
                license_name = str(info.get("license") or "")
                if not is_allowed_license(license_name):
                    continue
                file_url = str(info.get("url") or "")
                if not file_url:
                    continue
                suffix = Path(urllib.parse.urlparse(file_url).path).suffix.lower() or ".jpg"
                if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                    continue
                class_dir = args.output_dir / safe_slug(class_id)
                class_dir.mkdir(parents=True, exist_ok=True)
                dest = class_dir / f"{safe_slug(candidate)}{suffix}"
                thumb = class_dir / f"{safe_slug(candidate)}.thumb.jpg"
                if args.dry_run:
                    digest = "dry-run"
                    local_rel = f"downloaded/wikimedia/{safe_slug(class_id)}/{dest.name}"
                else:
                    if not dest.exists():
                        dest.write_bytes(download_bytes(file_url, max_bytes=args.max_bytes))
                    make_thumbnail(dest, thumb)
                    digest = sha256_file(dest)
                    local_rel = relative_to_corpus(dest)
                records.append(
                    manifest_record(
                        asset_id=f"wiki_{safe_slug(class_id)}_{accepted + 1:03d}",
                        local_rel=local_rel,
                        source="wikimedia",
                        source_url=str(info.get("description_url") or file_url),
                        source_id=candidate,
                        license_name=license_name,
                        author=str(info.get("artist") or "unknown"),
                        attribution=str(info.get("attribution") or info.get("artist") or candidate),
                        sha256=digest,
                        modality="image",
                        target_categories=target_categories(class_id),
                        expected_yolo_labels=list(config.get("expected_labels") or []),
                        expected_person_attrs=list(config.get("expected_person_attrs") or []),
                        expected_queries=queries_for_class(class_id),
                        fixture_only_for_ci=False,
                        redistribution_allowed=license_name.lower() in {"cc0", "public domain", "pd"},
                        release_package_includes_file=False,
                        extra={
                            "thumbnail_rel": relative_to_corpus(thumb) if thumb.exists() else None,
                            "download_skipped_dry_run": args.dry_run,
                        },
                    )
                )
                accepted += 1
            except Exception as exc:
                failures.append({"class_id": class_id, "candidate": candidate, "error": f"{type(exc).__name__}:{exc}"})
    write_jsonl(args.manifest_out, records)
    report = {
        "ok": bool(records) or args.dry_run,
        "dry_run": args.dry_run,
        "record_count": len(records),
        "failure_count": len(failures),
        "failures": failures[:50],
        "manifest": str(args.manifest_out),
    }
    write_json(args.manifest_out.with_name("wikimedia_download_report.json"), report)
    print(args.manifest_out)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


def search_commons(term: str, *, limit: int) -> list[str]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {term}",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|mime",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    payload = json.loads(download_bytes(url, max_bytes=2_000_000).decode("utf-8"))
    pages = payload.get("query", {}).get("pages", {})
    titles = [str(page.get("title")) for page in pages.values() if str(page.get("title", "")).startswith("File:")]
    return titles


def fetch_image_info(title: str) -> dict[str, Any]:
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    payload = json.loads(download_bytes(url, max_bytes=2_000_000).decode("utf-8"))
    page = next(iter((payload.get("query", {}).get("pages") or {}).values()))
    info = (page.get("imageinfo") or [{}])[0]
    ext = info.get("extmetadata") or {}
    return {
        "url": info.get("url"),
        "description_url": info.get("descriptionurl"),
        "license": (ext.get("LicenseShortName") or {}).get("value") or (ext.get("License") or {}).get("value"),
        "artist": strip_html((ext.get("Artist") or {}).get("value") or ""),
        "attribution": strip_html((ext.get("Credit") or {}).get("value") or (ext.get("Artist") or {}).get("value") or title),
    }


def strip_html(value: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", value or "").strip()


def make_thumbnail(source: Path, thumb: Path) -> None:
    try:
        image = Image.open(source)
        image.thumbnail((384, 384))
        image.convert("RGB").save(thumb, quality=86)
    except Exception:
        return


def target_categories(class_id: str) -> list[str]:
    mapping = {
        "person": ["人物照片"],
        "white_shirt_person": ["人物照片", "白色上衣"],
        "cat": ["宠物动物", "猫咪照片"],
        "dog": ["宠物动物", "狗狗照片"],
        "laptop": ["电子设备"],
        "book": ["书本文具"],
        "cup": ["书本文具"],
        "car": ["车辆交通"],
        "landscape": ["风景旅行"],
    }
    return mapping.get(class_id, [class_id])


def queries_for_class(class_id: str) -> list[str]:
    mapping = {
        "white_shirt_person": ["找穿白色上衣的人"],
        "cat": ["找猫咪照片", "找宠物照片"],
        "dog": ["找狗狗照片", "找宠物照片"],
        "laptop": ["找有电脑的照片"],
        "book": ["找有书和杯子的照片"],
        "cup": ["找有书和杯子的照片"],
        "car": ["找汽车照片"],
        "person": ["找视频里有人的片段"],
    }
    return mapping.get(class_id, [])


if __name__ == "__main__":
    raise SystemExit(main())

