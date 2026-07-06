#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from _demo_corpus_common import CORPUS_ROOT, has_raw_path, is_allowed_license, read_jsonl, sha256_file, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify demo corpus manifest schema, checksums, licenses, and file readability.")
    parser.add_argument("--manifest", type=Path, default=CORPUS_ROOT / "manifests" / "demo_corpus_manifest.jsonl")
    parser.add_argument("--report-out", type=Path, default=CORPUS_ROOT / "manifests" / "verify_demo_corpus_report.json")
    parser.add_argument("--require-files", action="store_true", help="Require every manifest local file to exist.")
    args = parser.parse_args()
    records = read_jsonl(args.manifest)
    failures: list[str] = []
    warnings: list[str] = []
    required = ["asset_id", "local_rel", "source", "license", "author", "attribution", "sha256", "modality", "license_verified"]
    for index, record in enumerate(records, start=1):
        prefix = f"record[{index}]/{record.get('asset_id')}"
        for key in required:
            if record.get(key) in (None, ""):
                failures.append(f"{prefix}:missing:{key}")
        if has_raw_path(record):
            failures.append(f"{prefix}:raw_path_leak")
        if not is_allowed_license(str(record.get("license") or "")):
            failures.append(f"{prefix}:license_not_allowed:{record.get('license')}")
        if record.get("source") in {"open_images", "wikimedia"}:
            for key in ("source_url", "source_id"):
                if not record.get(key):
                    failures.append(f"{prefix}:third_party_missing:{key}")
            if record.get("release_package_includes_file") is True:
                failures.append(f"{prefix}:third_party_file_marked_for_release")
        local_rel = str(record.get("local_rel") or "")
        path = CORPUS_ROOT / local_rel
        if path.exists():
            if record.get("sha256") not in {"dry-run", sha256_file(path)}:
                failures.append(f"{prefix}:sha256_mismatch")
            if record.get("modality") == "image":
                try:
                    image = Image.open(path)
                    image.verify()
                except Exception as exc:
                    failures.append(f"{prefix}:image_unreadable:{type(exc).__name__}")
        elif args.require_files or not record.get("release_package_includes_manifest_only"):
            failures.append(f"{prefix}:file_missing:{local_rel}")
        else:
            warnings.append(f"{prefix}:manifest_only_file_not_present")
    modalities = {name: sum(1 for record in records if record.get("modality") == name) for name in ["image", "document", "video", "audio"]}
    payload = {
        "ok": bool(records) and not failures,
        "record_count": len(records),
        "modalities": modalities,
        "third_party_count": sum(1 for record in records if record.get("source") in {"open_images", "wikimedia"}),
        "fixture_only_count": sum(1 for record in records if record.get("fixture_only_for_ci")),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings[:100],
    }
    write_json(args.report_out, payload)
    print(args.report_out)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

