#!/usr/bin/env python3
"""Shared helpers for the low-cost AI-NAS MVP probes.

The probes are intentionally deterministic and filesystem-bounded. They never
delete, move, rename, or overwrite source files.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_PERSONAL_ROOT = Path(os.environ.get("AI_NAS_PERSONAL_ROOT", "/mnt/nas/openclaw/Personal"))
DEFAULT_REPORT_ROOT = Path(os.environ.get("AI_NAS_REPORT_ROOT", "/mnt/nas/openclaw/reports/ai_nas_mvp"))
DEFAULT_INDEX_PATH = DEFAULT_REPORT_ROOT / "personal_inventory_latest.json"
SCAN_DIRS = ("Movies", "Documents", "Photos", "Inbox")
SKIP_DIRS = {"Sorted", "@Recycle", "@Recently-Snapshot", ".snapshot", "#recycle"}
TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".log"}
DOC_EXTS = TEXT_EXTS | {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
MOVIE_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".bmp", ".tif", ".tiff", ".webp"}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def ensure_report_dir(report_root: Path, name: str) -> Path:
    run_dir = report_root / f"{name}_{now_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_write_json(path: Path, payload: dict) -> None:
    safe_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_file(path: Path, personal_root: Path | None = None) -> tuple[str, list[str]]:
    ext = path.suffix.lower()
    text = " ".join(path.parts).lower()
    tags: list[str] = []
    top_dir = ""
    if personal_root is not None:
        try:
            top_dir = path.relative_to(personal_root).parts[0]
        except (ValueError, IndexError):
            top_dir = ""
    if top_dir in SCAN_DIRS:
        category = top_dir
    elif ext in MOVIE_EXTS or path.name.lower().endswith(".movie.txt"):
        category = "Movies"
    elif ext in PHOTO_EXTS:
        category = "Photos"
    elif ext in DOC_EXTS:
        category = "Documents"
    else:
        category = "Other"

    keyword_tags = {
        "crime": ["crime", "criminal", "detective", "noir", "joker"],
        "sci-fi": ["sci-fi", "scifi", "science fiction", "matrix", "interstellar"],
        "contract": ["contract", "agreement", "合同", "付款", "payment"],
        "invoice": ["invoice", "receipt", "票据", "发票", "bill"],
        "travel": ["travel", "trip", "旅行", "hotel", "flight"],
        "paper": ["paper", "论文", "manuscript", "research"],
        "photo": ["photo", "image", "照片", "album"],
    }
    for tag, needles in keyword_tags.items():
        if any(needle in text for needle in needles):
            tags.append(tag)
    year = infer_year(path.name)
    if year:
        tags.append(str(year))
    return category, sorted(set(tags))


def infer_year(name: str) -> int | None:
    match = re.search(r"(19\d{2}|20\d{2})", name)
    if not match:
        return None
    year = int(match.group(1))
    if 1900 <= year <= 2100:
        return year
    return None


def read_text_preview(path: Path, limit: int = 4000) -> tuple[str, str | None]:
    if path.suffix.lower() not in TEXT_EXTS and not path.name.lower().endswith(".movie.txt"):
        return "", "unsupported_binary_or_office_format"
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - filesystem dependent
        return "", f"read_failed:{type(exc).__name__}:{exc}"
    return data[:limit], None


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower())
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "demo", "placeholder",
        "文件", "合同", "发票", "旅行", "摘要",
    }
    counts = Counter(token for token in tokens if token not in stop)
    return [word for word, _ in counts.most_common(limit)]


def summarize_text(text: str, fallback: str) -> str:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return fallback
    if len(normalized) <= 180:
        return normalized
    return normalized[:180] + "..."


def iter_personal_files(root: Path, include_sorted: bool = False) -> Iterable[Path]:
    for dirname in SCAN_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_dir():
                continue
            rel_parts = path.relative_to(root).parts
            if not include_sorted and any(part in SKIP_DIRS for part in rel_parts):
                continue
            yield path


def bootstrap_demo(root: Path) -> list[str]:
    samples = {
        "Movies/Joker.2019.Crime.movie.txt": "Crime film demo. Year: 2019. Theme: detective and criminal psychology.\n",
        "Movies/The.Matrix.1999.Sci-Fi.movie.txt": "Science fiction film demo. Year: 1999. Theme: AI and virtual reality.\n",
        "Documents/contract_payment_schedule_2026.txt": "Contract demo. Payment dates: 2026-07-01 deposit; 2026-09-15 final payment.\n",
        "Documents/invoice_travel_2026.txt": "Invoice demo. Travel reimbursement for hotel and flight. Total: 1280 CNY.\n",
        "Documents/paper_notes_ai_nas.txt": "Research notes demo. Topic: local AI NAS copilot, file search, summary, and audit logs.\n",
        "Photos/travel_shanghai_2026.jpg": "demo-photo-bytes-travel-shanghai\n",
        "Photos/travel_shanghai_2026_copy.jpg": "demo-photo-bytes-travel-shanghai\n",
        "Inbox/recent_receipt_2026.txt": "Receipt demo. Added recently. Taxi and meal invoice pending classification.\n",
    }
    created: list[str] = []
    for rel, content in samples.items():
        path = root / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            path.write_bytes(content.encode("utf-8"))
        else:
            path.write_text(content, encoding="utf-8")
        created.append(str(path))
    return created


def build_inventory(root: Path, max_files: int = 5000) -> dict:
    records = []
    failures = []
    for idx, path in enumerate(iter_personal_files(root)):
        if idx >= max_files:
            failures.append({"path": str(root), "reason": f"max_files_exceeded:{max_files}"})
            break
        rel = path.relative_to(root).as_posix()
        try:
            stat = path.stat()
            digest = sha256_file(path)
            category, tags = classify_file(path, root)
            preview, parse_error = read_text_preview(path)
            keywords = extract_keywords(preview)
            records.append(
                {
                    "path": str(path),
                    "relative_path": rel,
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(),
                    "sha256": digest,
                    "type": category,
                    "extension": path.suffix.lower(),
                    "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "year": infer_year(path.name),
                    "tags": tags,
                    "keywords": keywords,
                    "summary": summarize_text(preview, "content_not_extracted"),
                    "parse_error": parse_error,
                }
            )
        except Exception as exc:  # pragma: no cover - filesystem dependent
            failures.append({"path": str(path), "reason": f"{type(exc).__name__}:{exc}"})

    by_type = Counter(record["type"] for record in records)
    return {
        "generated_at": iso_now(),
        "personal_root": str(root),
        "scan_dirs": list(SCAN_DIRS),
        "safety_policy": {
            "delete": False,
            "move": False,
            "overwrite": False,
            "source_preserved": True,
            "writes": "reports_only_unless_bootstrap_demo_or_movie_copy_sort_is_explicit",
        },
        "file_count": len(records),
        "type_counts": dict(sorted(by_type.items())),
        "records": records,
        "failures": failures,
    }


def write_inventory_reports(payload: dict, run_dir: Path, latest_path: Path | None = None) -> tuple[Path, Path]:
    json_path = run_dir / "personal_inventory.json"
    md_path = run_dir / "personal_inventory.md"
    safe_write_json(json_path, payload)
    if latest_path:
        safe_write_json(latest_path, payload)
    lines = [
        "# AI-NAS Personal Inventory",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- personal_root: `{payload['personal_root']}`",
        f"- file_count: `{payload['file_count']}`",
        f"- type_counts: `{payload['type_counts']}`",
        "- safety: read-only scan; no delete, no move, no overwrite",
        "",
        "## Files",
        "",
    ]
    for record in payload["records"]:
        lines.append(
            f"- `{record['relative_path']}` | `{record['type']}` | "
            f"{record['size_bytes']} bytes | tags: `{', '.join(record['tags'])}`"
        )
    if payload["failures"]:
        lines.extend(["", "## Parse Or Scan Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure['path']}`: `{failure['reason']}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    return json_path, md_path


def load_index(index_path: Path, personal_root: Path, report_root: Path) -> dict:
    if index_path.exists():
        return json.loads(index_path.read_text(encoding="utf-8"))
    payload = build_inventory(personal_root)
    run_dir = ensure_report_dir(report_root, "personal_inventory")
    write_inventory_reports(payload, run_dir, index_path)
    return payload


def score_record(record: dict, query: str) -> tuple[float, list[str]]:
    q = query.lower()
    tokens = [token for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", q)]
    haystacks = {
        "name": record.get("name", "").lower(),
        "path": record.get("relative_path", "").lower(),
        "tags": " ".join(record.get("tags", [])).lower(),
        "keywords": " ".join(record.get("keywords", [])).lower(),
        "summary": record.get("summary", "").lower(),
        "type": record.get("type", "").lower(),
    }
    score = 0.0
    reasons: list[str] = []
    for token in tokens:
        matched = False
        for field, text in haystacks.items():
            if token in text:
                score += {"name": 4, "path": 3, "tags": 3, "keywords": 2, "summary": 2, "type": 2}.get(field, 1)
                matched = True
                reasons.append(f"{field} matches `{token}`")
        if token.isdigit() and record.get("year") == int(token):
            score += 4
            matched = True
            reasons.append(f"year matches `{token}`")
        if not matched:
            continue
    synonyms = {
        "犯罪": "crime", "电影": "movies", "合同": "contract", "票据": "invoice",
        "发票": "invoice", "旅行": "travel", "论文": "paper", "照片": "photos",
        "最近": "recent",
    }
    for cn, tag in synonyms.items():
        if cn in q and (tag in haystacks["tags"] or tag in haystacks["type"] or tag in haystacks["summary"]):
            score += 4
            reasons.append(f"semantic tag matches `{cn}->{tag}`")
    if "最近" in q or "recent" in q:
        score += 1
        reasons.append("recent query uses mtime as tie-breaker")
    return score, sorted(set(reasons))


def duplicate_groups(records: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[record["sha256"]].append(record)
    result = []
    for digest, items in groups.items():
        if len(items) <= 1:
            continue
        result.append(
            {
                "sha256": digest,
                "count": len(items),
                "size_bytes_each": items[0]["size_bytes"],
                "potential_reclaim_bytes": max(0, len(items) - 1) * items[0]["size_bytes"],
                "files": [{"path": item["path"], "relative_path": item["relative_path"]} for item in items],
            }
        )
    return sorted(result, key=lambda item: item["potential_reclaim_bytes"], reverse=True)


def copy_movies_non_destructive(records: list[dict], root: Path, report_dir: Path) -> dict:
    sorted_root = root / "Sorted" / "Movies"
    sorted_root.mkdir(parents=True, exist_ok=True)
    copied = []
    skipped = []
    for record in records:
        if record["type"] != "Movies":
            continue
        source = Path(record["path"])
        genre = "Unclassified"
        for tag in record.get("tags", []):
            if tag in {"crime", "sci-fi"}:
                genre = tag.title()
        year = record.get("year") or "UnknownYear"
        target_dir = sorted_root / str(year) / genre
        target = target_dir / source.name
        if target.exists():
            skipped.append({"source": str(source), "target": str(target), "reason": "target_exists_no_overwrite"})
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append({"source": str(source), "target": str(target), "sha256": record["sha256"], "year": year, "genre": genre})
    manifest = {
        "generated_at": iso_now(),
        "operation": "non_destructive_movie_copy_sort",
        "source_root": str(root / "Movies"),
        "target_root": str(sorted_root),
        "delete": False,
        "move": False,
        "overwrite": False,
        "copied": copied,
        "skipped": skipped,
    }
    safe_write_json(report_dir / "movie_sort_manifest.json", manifest)
    lines = ["# AI-NAS Movie Sort Manifest", "", "- policy: copy only; no delete, no move, no overwrite", ""]
    for item in copied:
        lines.append(f"- copied `{item['source']}` -> `{item['target']}`")
    for item in skipped:
        lines.append(f"- skipped `{item['source']}` -> `{item['reason']}`")
    safe_write_text(report_dir / "movie_sort_manifest.md", "\n".join(lines) + "\n")
    return manifest
