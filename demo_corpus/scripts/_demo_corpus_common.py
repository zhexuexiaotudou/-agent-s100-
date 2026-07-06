#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "demo_corpus"
ALLOWED_LICENSE_MARKERS = {
    "cc by",
    "cc-by",
    "cc by-sa",
    "cc-by-sa",
    "cc0",
    "public domain",
    "pd",
    "project-owned",
    "synthetic",
}
THIRD_PARTY_SOURCES = {"open_images", "wikimedia"}
RAW_PATH_MARKERS = ("/mnt/nas/", "/root/", "/home/", "C:\\", "F:\\")


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip().lower()).strip("._-")
    return slug or "asset"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid jsonl: {exc}") from exc
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_allowed_license(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return any(marker in normalized for marker in ALLOWED_LICENSE_MARKERS)


def relative_to_corpus(path: Path) -> str:
    return path.resolve().relative_to(CORPUS_ROOT.resolve()).as_posix()


def has_raw_path(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=False)
    return any(marker in encoded for marker in RAW_PATH_MARKERS)


def manifest_record(
    *,
    asset_id: str,
    local_rel: str,
    source: str,
    source_url: str,
    source_id: str,
    license_name: str,
    author: str,
    attribution: str,
    sha256: str,
    modality: str,
    target_categories: list[str] | None = None,
    expected_yolo_labels: list[str] | None = None,
    expected_person_attrs: list[str] | None = None,
    expected_ocr_terms: list[str] | None = None,
    expected_queries: list[str] | None = None,
    fixture_only_for_ci: bool = False,
    redistribution_allowed: bool = False,
    release_package_includes_file: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    third_party = source in THIRD_PARTY_SOURCES
    record: dict[str, Any] = {
        "asset_id": asset_id,
        "local_rel": local_rel,
        "source": source,
        "source_url": source_url,
        "source_id": source_id,
        "license": license_name,
        "author": author,
        "attribution": attribution,
        "downloaded_at": utc_now(),
        "sha256": sha256,
        "modality": modality,
        "target_categories": target_categories or [],
        "expected_yolo_labels": expected_yolo_labels or [],
        "expected_person_attrs": expected_person_attrs or [],
        "expected_ocr_terms": expected_ocr_terms or [],
        "expected_queries": expected_queries or [],
        "fixture_only_for_ci": fixture_only_for_ci,
        "redistribution_allowed": redistribution_allowed,
        "raw_path_returned": False,
        "license_verified": is_allowed_license(license_name),
        "attribution_required": third_party,
        "release_package_includes_file": release_package_includes_file,
        "release_package_includes_manifest_only": third_party and not release_package_includes_file,
    }
    if extra:
        record.update(extra)
    return record


def download_bytes(url: str, *, timeout: int = 30, max_bytes: int = 8_000_000) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "DiguaAI-NAS-DemoCorpus/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError(f"remote file too large: {length} > {max_bytes}")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"remote file too large: > {max_bytes}")
    return data


def write_attribution(records: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Attribution", ""]
    if not records:
        lines.append("No manifest records are present yet.")
    for record in records:
        lines.extend(
            [
                f"## {record.get('asset_id')}",
                "",
                f"- source: `{record.get('source')}`",
                f"- source_url: {record.get('source_url') or 'n/a'}",
                f"- license: `{record.get('license')}`",
                f"- author: `{record.get('author')}`",
                f"- attribution: {record.get('attribution')}",
                f"- sha256: `{record.get('sha256')}`",
                "",
            ]
        )
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))

