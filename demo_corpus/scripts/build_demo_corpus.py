#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from _demo_corpus_common import (
    CORPUS_ROOT,
    manifest_record,
    read_jsonl,
    relative_to_corpus,
    sha256_file,
    write_attribution,
    write_json,
    write_jsonl,
)


MANIFESTS = [
    CORPUS_ROOT / "manifests" / "open_images_manifest.jsonl",
    CORPUS_ROOT / "manifests" / "wikimedia_manifest.jsonl",
    CORPUS_ROOT / "manifests" / "synthetic_docs_manifest.jsonl",
    CORPUS_ROOT / "manifests" / "demo_video_manifest.jsonl",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Digua demo corpus manifest and optional Personal demo tree.")
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--report-root", type=Path, default=Path("reports"))
    parser.add_argument("--max-images", type=int, default=100)
    parser.add_argument("--write-to-personal", action="store_true")
    parser.add_argument("--fixture-ci", action="store_true", help="Generate project-owned fallback image fixtures.")
    parser.add_argument("--no-downloads", action="store_true", help="Do not call downloaders; merge existing manifests only.")
    parser.add_argument("--include-third-party-files", action="store_true", help="Copy downloaded third-party files into Personal DemoCorpus.")
    args = parser.parse_args()

    run([sys.executable, str(CORPUS_ROOT / "scripts" / "generate_synthetic_docs.py")])
    run([sys.executable, str(CORPUS_ROOT / "scripts" / "generate_demo_videos.py")])
    if args.fixture_ci:
        generate_fixture_images(CORPUS_ROOT / "samples_generated" / "ci_images", count=min(args.max_images, 40))

    records = merge_manifests()
    if args.fixture_ci:
        records.extend(fixture_image_records(CORPUS_ROOT / "samples_generated" / "ci_images"))
    image_records = [record for record in records if record.get("modality") == "image"]
    if len(image_records) > args.max_images:
        keep_images = {record["asset_id"] for record in image_records[: args.max_images]}
        records = [record for record in records if record.get("modality") != "image" or record.get("asset_id") in keep_images]
    manifest_path = CORPUS_ROOT / "manifests" / "demo_corpus_manifest.jsonl"
    write_jsonl(manifest_path, records)
    write_attribution(records, CORPUS_ROOT / "licenses" / "ATTRIBUTION.md")
    write_third_party_notices(records, CORPUS_ROOT / "licenses" / "THIRD_PARTY_NOTICES.md")

    personal_copy: dict[str, Any] = {"enabled": args.write_to_personal, "copied": 0, "skipped": 0, "root": None}
    if args.write_to_personal:
        if not args.personal_root:
            raise SystemExit("--personal-root is required with --write-to-personal")
        personal_copy = copy_to_personal(records, args.personal_root, include_third_party=args.include_third_party_files)
    report = {
        "ok": bool(records),
        "manifest": str(manifest_path),
        "record_count": len(records),
        "image_count": sum(1 for r in records if r.get("modality") == "image"),
        "document_count": sum(1 for r in records if r.get("modality") == "document"),
        "video_count": sum(1 for r in records if r.get("modality") == "video"),
        "audio_count": sum(1 for r in records if r.get("modality") == "audio"),
        "third_party_count": sum(1 for r in records if r.get("source") in {"open_images", "wikimedia"}),
        "fixture_only_count": sum(1 for r in records if r.get("fixture_only_for_ci")),
        "personal_copy": personal_copy,
    }
    args.report_root.mkdir(parents=True, exist_ok=True)
    write_json(args.report_root / "stage10_demo_corpus_build_report.json", report)
    print(manifest_path)
    print(args.report_root / "stage10_demo_corpus_build_report.json")
    return 0 if report["ok"] else 1


def run(cmd: list[str]) -> None:
    completed = subprocess.run(cmd, cwd=CORPUS_ROOT.parents[0], text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{completed.stdout}\n{completed.stderr}")


def merge_manifests() -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for manifest in MANIFESTS:
        for record in read_jsonl(manifest):
            asset_id = str(record.get("asset_id") or "")
            if not asset_id or asset_id in seen:
                continue
            seen.add(asset_id)
            merged.append(record)
    return merged


def generate_fixture_images(output_dir: Path, *, count: int) -> None:
    classes = [
        ("person", "人物照片", (230, 230, 230)),
        ("white_shirt_person", "白色上衣", (245, 245, 245)),
        ("cat", "猫咪照片", (220, 190, 130)),
        ("dog", "狗狗照片", (150, 110, 80)),
        ("laptop", "电子设备", (60, 80, 120)),
        ("book", "书本文具", (190, 40, 45)),
        ("cup", "书本文具", (80, 160, 220)),
        ("car", "车辆交通", (40, 70, 160)),
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        class_id, label, color = classes[(index - 1) % len(classes)]
        path = output_dir / f"IMG_{index:04d}_{class_id}.jpg"
        image = Image.new("RGB", (800, 600), color=(248, 248, 244))
        draw = ImageDraw.Draw(image)
        draw.rectangle((150, 150, 650, 450), fill=color, outline=(30, 40, 55), width=8)
        draw.text((180, 110), f"fixture {index}: {class_id}", fill=(10, 20, 30))
        image.save(path, quality=90)


def fixture_image_records(output_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, path in enumerate(sorted(output_dir.glob("*.jpg")), start=1):
        class_id = path.stem.split("_", 2)[-1]
        records.append(
            manifest_record(
                asset_id=f"fixture_ci_image_{index:03d}",
                local_rel=relative_to_corpus(path),
                source="synthetic",
                source_url="project://digua/demo_corpus/ci_fixture_images",
                source_id=path.stem,
                license_name="Synthetic Project-Owned",
                author="Digua AI-NAS project",
                attribution="Generated CI fallback image fixture.",
                sha256=sha256_file(path),
                modality="image",
                target_categories=fixture_categories(class_id),
                expected_yolo_labels=[class_id] if class_id in {"person", "cat", "dog", "laptop", "book", "cup", "car"} else [],
                expected_person_attrs=["upper_white"] if class_id == "white_shirt_person" else [],
                expected_queries=fixture_queries(class_id),
                fixture_only_for_ci=True,
                redistribution_allowed=True,
                release_package_includes_file=True,
                extra={"fixture_warning": "Synthetic fixture; not evidence of real YOLO detection."},
            )
        )
    return records


def fixture_categories(class_id: str) -> list[str]:
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


def fixture_queries(class_id: str) -> list[str]:
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


def copy_to_personal(records: list[dict[str, Any]], personal_root: Path, *, include_third_party: bool) -> dict[str, Any]:
    dest_root = personal_root / "DemoCorpus"
    copied = 0
    skipped = 0
    for record in records:
        source = record.get("source")
        if source in {"open_images", "wikimedia"} and not include_third_party:
            skipped += 1
            continue
        rel = str(record.get("local_rel") or "")
        src = CORPUS_ROOT / rel
        if not src.exists() or not src.is_file():
            skipped += 1
            continue
        modality = record.get("modality")
        if modality == "image":
            folder = "Photos"
        elif modality == "document":
            folder = "Documents"
        elif modality == "video":
            folder = "Videos"
        elif modality == "audio":
            folder = "Audio"
        else:
            folder = "Uploads"
        dest = dest_root / folder / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    return {"enabled": True, "root": str(dest_root), "copied": copied, "skipped": skipped}


def write_third_party_notices(records: list[dict[str, Any]], out_path: Path) -> None:
    lines = ["# Third-Party Notices", ""]
    third_party = [record for record in records if record.get("source") in {"open_images", "wikimedia"}]
    if not third_party:
        lines.append("No third-party media records are present in the current manifest.")
    for record in third_party:
        lines.extend(
            [
                f"## {record.get('asset_id')}",
                "",
                f"- source: `{record.get('source')}`",
                f"- source_url: {record.get('source_url')}",
                f"- license: `{record.get('license')}`",
                f"- author: `{record.get('author')}`",
                f"- attribution: {record.get('attribution')}",
                "- bundled in release: `false`",
                "",
            ]
        )
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
