#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image

from _demo_corpus_common import (
    CORPUS_ROOT,
    download_bytes,
    load_yaml,
    manifest_record,
    relative_to_corpus,
    safe_slug,
    sha256_file,
    write_json,
    write_jsonl,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a bounded Open Images subset from a curated seed CSV.")
    parser.add_argument("--recipe", type=Path, default=CORPUS_ROOT / "recipes" / "target_classes.yaml")
    parser.add_argument("--seed-csv", type=Path, default=None, help="CSV with class_id,image_id,image_url,source_url,license,author.")
    parser.add_argument("--output-dir", type=Path, default=CORPUS_ROOT / "downloaded" / "open_images")
    parser.add_argument("--manifest-out", type=Path, default=CORPUS_ROOT / "manifests" / "open_images_manifest.jsonl")
    parser.add_argument("--max-per-class", type=int, default=8)
    parser.add_argument("--max-bytes", type=int, default=6_000_000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    recipe = load_yaml(args.recipe)
    image_classes = recipe.get("image_classes") or {}
    eligible = {class_id: config for class_id, config in image_classes.items() if "open_images" in set(config.get("sources") or [])}
    seed_rows = read_seed_csv(args.seed_csv) if args.seed_csv else []
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    counts = {class_id: 0 for class_id in eligible}
    for row in seed_rows:
        class_id = row.get("class_id") or ""
        if class_id not in eligible or counts[class_id] >= args.max_per_class:
            continue
        try:
            image_url = row["image_url"]
            suffix = Path(image_url.split("?", 1)[0]).suffix.lower() or ".jpg"
            if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            out_dir = args.output_dir / safe_slug(class_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            dest = out_dir / f"{safe_slug(row.get('image_id') or class_id)}{suffix}"
            if args.dry_run:
                digest = "dry-run"
                local_rel = f"downloaded/open_images/{safe_slug(class_id)}/{dest.name}"
            else:
                if not dest.exists():
                    dest.write_bytes(download_bytes(image_url, max_bytes=args.max_bytes))
                verify_image(dest)
                digest = sha256_file(dest)
                local_rel = relative_to_corpus(dest)
            config = eligible[class_id]
            records.append(
                manifest_record(
                    asset_id=f"openimg_{safe_slug(class_id)}_{counts[class_id] + 1:03d}",
                    local_rel=local_rel,
                    source="open_images",
                    source_url=row.get("source_url") or image_url,
                    source_id=row.get("image_id") or dest.stem,
                    license_name=row.get("license") or "CC BY 4.0",
                    author=row.get("author") or "Open Images contributor",
                    attribution=row.get("attribution") or f"{row.get('image_id') or dest.stem} via Open Images",
                    sha256=digest,
                    modality="image",
                    target_categories=target_categories(class_id),
                    expected_yolo_labels=list(config.get("expected_labels") or []),
                    expected_person_attrs=list(config.get("expected_person_attrs") or []),
                    expected_queries=queries_for_class(class_id),
                    fixture_only_for_ci=False,
                    redistribution_allowed=False,
                    release_package_includes_file=False,
                    extra={"download_skipped_dry_run": args.dry_run},
                )
            )
            counts[class_id] += 1
        except Exception as exc:
            failures.append({"row": row, "error": f"{type(exc).__name__}:{exc}"})

    missing_seed_classes = [class_id for class_id in eligible if counts[class_id] == 0]
    report = {
        "ok": bool(records) or args.dry_run,
        "dry_run": args.dry_run,
        "seed_csv": str(args.seed_csv) if args.seed_csv else None,
        "record_count": len(records),
        "counts": counts,
        "missing_seed_classes": missing_seed_classes,
        "failure_count": len(failures),
        "failures": failures[:50],
        "note": "Open Images download is seed-manifest based to avoid pulling unbounded upstream CSV files during release gates.",
    }
    write_jsonl(args.manifest_out, records)
    write_json(args.manifest_out.with_name("open_images_download_report.json"), report)
    print(args.manifest_out)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


def read_seed_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_image(path: Path) -> None:
    image = Image.open(path)
    image.verify()


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
    }
    return mapping.get(class_id, [])


if __name__ == "__main__":
    raise SystemExit(main())

