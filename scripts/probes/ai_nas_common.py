#!/usr/bin/env python3
"""Shared helpers for the low-cost AI-NAS MVP probes.

The probes are intentionally deterministic and filesystem-bounded. Destructive
or mutating operations are available only through explicit storage helpers that
resolve paths under the configured Personal root and write audit records.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import base64
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Iterable

from ai_nas_vision_schema import ensure_vision_product_schema


_SQLITE_DEFAULT_ISOLATION = object()
_SQLITE_MODE_BY_PATH: dict[str, str] = {}


DEFAULT_PERSONAL_ROOT = Path(os.environ.get("AI_NAS_PERSONAL_ROOT", "/mnt/nas/openclaw/Personal"))
DEFAULT_REPORT_ROOT = Path(os.environ.get("AI_NAS_REPORT_ROOT", "/mnt/nas/openclaw/reports/ai_nas_mvp"))
DEFAULT_INDEX_PATH = DEFAULT_REPORT_ROOT / "personal_inventory_latest.json"
DEFAULT_SQLITE_INDEX_PATH = DEFAULT_REPORT_ROOT / "personal_inventory.sqlite3"
DEFAULT_PORTAL_LOCAL_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "openclaw_nas_portal.local.json"
EMBEDDING_MODEL_ID = "local_hash_embedding_v1"
EMBEDDING_DIM = 128
IMAGE_EMBEDDING_MODEL_ID = "local_visual_embedding_v1"
IMAGE_EMBEDDING_DIM = 48
IMAGE_CAPTION_SCHEMA_VERSION = "ai_nas_vision_caption_v1"
IMAGE_CAPTION_STATUS_COMPLETED = "llm_caption_completed"
SCAN_DIRS = ("Movies", "Documents", "Photos", "Inbox")
SKIP_DIRS = {"Sorted", "@Recycle", "@Recently-Snapshot", ".snapshot", "#recycle"}
STORAGE_STANDARD_DIRS = SCAN_DIRS
TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".log"}
DOC_EXTS = TEXT_EXTS | {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
MOVIE_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".bmp", ".tif", ".tiff", ".webp"}
GENERIC_SEARCH_TERMS = {"photo", "photos", "image", "images", "album", "file", "files"}
PHOTO_INTENT_TERMS = {
    "beach", "meal", "car", "white", "invoice", "screenshot", "child",
    "person", "people", "wearing", "clothing", "upper_clothing", "top", "shirt",
    "black", "red", "blue", "green", "yellow", "gray", "grey",
}
QUERY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in",
    "into", "is", "it", "me", "of", "on", "or", "please", "show", "that",
    "the", "this", "to", "was", "were", "what", "when", "where", "which",
    "who", "with", "folder", "folders", "evidence", "find", "help",
}

SEMANTIC_ALIASES = {
    "contract": ["contract", "agreement", "payment", "\u5408\u540c", "\u88c5\u4fee", "\u4ed8\u6b3e"],
    "invoice": ["invoice", "receipt", "bill", "reimbursement", "\u53d1\u7968", "\u7968\u636e", "\u62a5\u9500"],
    "photo": ["photo", "image", "album", "\u7167\u7247", "\u56fe\u7247"],
    "travel": ["travel", "trip", "hotel", "flight", "\u65c5\u884c", "\u9152\u5e97", "\u673a\u7968"],
    "beach": ["beach", "sea", "coast", "\u6d77\u8fb9", "\u6d77\u6ee9"],
    "meal": ["meal", "dinner", "lunch", "party", "restaurant", "\u805a\u9910", "\u5403\u996d", "\u9910\u5385"],
    "car": ["car", "vehicle", "auto", "\u6c7d\u8f66", "\u8f66"],
    "white": ["white", "\u767d\u8272"],
    "black": ["black", "\u9ed1\u8272"],
    "red": ["red", "\u7ea2\u8272"],
    "blue": ["blue", "\u84dd\u8272", "\u85cd\u8272"],
    "green": ["green", "\u7eff\u8272", "\u7da0\u8272"],
    "yellow": ["yellow", "\u9ec4\u8272", "\u9ec3\u8272"],
    "gray": ["gray", "grey", "\u7070\u8272"],
    "person": ["person", "people", "human", "\u4eba", "\u4eba\u50cf", "\u4eba\u7269"],
    "wearing": ["wearing", "wears", "dressed", "\u7a7f", "\u7a7f\u7740"],
    "clothing": ["clothing", "clothes", "apparel", "\u8863\u670d", "\u670d\u88c5"],
    "upper_clothing": ["upper clothing", "upper body clothing", "\u4e0a\u534a\u8eab\u8863\u670d"],
    "top": ["top", "upper garment", "\u4e0a\u8863", "\u5916\u5957", "\u4e0a\u88c5"],
    "shirt": ["shirt", "t-shirt", "tee", "blouse", "\u886c\u886b", "T\u6064", "t\u6064"],
    "child": ["child", "kid", "baby", "\u5b69\u5b50", "\u5c0f\u5b69", "\u5b9d\u5b9d"],
    "screenshot": ["screenshot", "screen", "\u622a\u56fe"],
    "paper": ["paper", "manuscript", "research", "\u8bba\u6587", "\u6587\u732e"],
    "crime": ["crime", "criminal", "detective", "\u72af\u7f6a"],
    "movies": ["movie", "movies", "film", "\u7535\u5f71"],
    "recent": ["recent", "latest", "\u6700\u8fd1"],
}

DOCUMENT_CLASS_ALIASES = {
    "contract": ["contract", "agreement", "payment schedule", "\u5408\u540c", "\u534f\u8bae", "\u4ed8\u6b3e", "\u88c5\u4fee"],
    "invoice": ["invoice", "receipt", "reimbursement", "taxi", "hotel", "flight", "\u53d1\u7968", "\u7968\u636e", "\u62a5\u9500", "\u6536\u636e"],
    "paper": ["paper", "manuscript", "research", "abstract", "references", "\u8bba\u6587", "\u6587\u732e", "\u6458\u8981"],
    "manual": ["manual", "guide", "instruction", "datasheet", "\u8bf4\u660e\u4e66", "\u624b\u518c", "\u6307\u5357"],
}


def default_official_manager_url(fallback: str = "http://nas.local:8080/") -> str:
    env_url = os.environ.get("OPENCLAW_OFFICIAL_MANAGER_URL", "").strip()
    if env_url:
        return env_url
    try:
        cfg = json.loads(DEFAULT_PORTAL_LOCAL_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    return str(cfg.get("official_manager_url") or cfg.get("nas_manager_url") or fallback).strip()


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def ensure_report_dir(report_root: Path, name: str) -> Path:
    base = report_root / f"{name}_{now_stamp()}"
    run_dir = base
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = Path(f"{base}_{suffix}")
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_write_json(path: Path, payload: dict) -> None:
    safe_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


class StoragePathError(ValueError):
    pass


def normalize_storage_relative_path(relative_path: str | os.PathLike[str] | None) -> str:
    text = "" if relative_path is None else str(relative_path)
    text = text.replace("\\", "/").strip()
    if text in {"", "."}:
        return ""
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise StoragePathError("absolute_paths_are_not_allowed")
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise StoragePathError("parent_traversal_is_not_allowed")
        if part in SKIP_DIRS:
            raise StoragePathError(f"reserved_path_component:{part}")
        parts.append(part)
    return "/".join(parts)


def resolve_storage_path(
    root: Path,
    relative_path: str | os.PathLike[str] | None,
    *,
    allow_root: bool = True,
) -> Path:
    root_resolved = root.resolve(strict=False)
    rel = normalize_storage_relative_path(relative_path)
    if not rel and not allow_root:
        raise StoragePathError("root_path_is_not_a_file_target")
    target = (root_resolved / rel).resolve(strict=False)
    try:
        inside = target == root_resolved or target.is_relative_to(root_resolved)
    except AttributeError:  # pragma: no cover - Python < 3.9 compatibility
        inside = str(target).startswith(str(root_resolved) + os.sep) or target == root_resolved
    if not inside:
        raise StoragePathError("resolved_path_escapes_personal_root")
    return target


def ensure_storage_root(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    created = []
    for dirname in STORAGE_STANDARD_DIRS:
        path = root / dirname
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(dirname)
    return {
        "root": str(root),
        "exists": root.exists(),
        "is_dir": root.is_dir(),
        "created_standard_dirs": created,
        "standard_dirs": list(STORAGE_STANDARD_DIRS),
    }


def storage_capacity(root: Path) -> dict:
    probe = root
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    return {
        "path": str(probe),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def storage_mount_info(root: Path) -> dict:
    payload = {
        "root": str(root),
        "platform": os.name,
        "is_mount": root.exists() and os.path.ismount(root),
        "mount_source": None,
        "filesystem": None,
    }
    mounts = Path("/proc/mounts")
    if mounts.exists():
        root_text = str(root.resolve(strict=False))
        best: tuple[int, list[str]] | None = None
        try:
            for line in mounts.read_text(encoding="utf-8", errors="replace").splitlines():
                fields = line.split()
                if len(fields) < 3:
                    continue
                mount_point = fields[1].replace("\\040", " ")
                if root_text == mount_point or root_text.startswith(mount_point.rstrip("/") + "/"):
                    score = len(mount_point)
                    if best is None or score > best[0]:
                        best = (score, fields)
            if best:
                payload["mount_source"] = best[1][0]
                payload["mount_point"] = best[1][1].replace("\\040", " ")
                payload["filesystem"] = best[1][2]
        except OSError:
            pass
    return payload


def log_file_operation(
    db_path: Path,
    action: str,
    source_relative_path: str | None,
    target_relative_path: str | None,
    status: str,
    detail: str | None = None,
    *,
    size_bytes: int | None = None,
    sha256: str | None = None,
) -> dict:
    con = open_index_db(db_path)
    created_at = iso_now()
    with con:
        cur = con.execute(
            """
            INSERT INTO file_operations(
                created_at, action, source_relative_path, target_relative_path,
                status, detail, size_bytes, sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (created_at, action, source_relative_path, target_relative_path, status, detail, size_bytes, sha256),
        )
        operation_id = int(cur.lastrowid)
    con.close()
    return {
        "id": operation_id,
        "created_at": created_at,
        "action": action,
        "source_relative_path": source_relative_path,
        "target_relative_path": target_relative_path,
        "status": status,
        "detail": detail,
        "size_bytes": size_bytes,
        "sha256": sha256,
    }


def latest_file_operations(db_path: Path, limit: int = 50) -> list[dict]:
    con = open_index_db(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, created_at, action, source_relative_path, target_relative_path,
                   status, detail, size_bytes, sha256
            FROM file_operations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def storage_entry_payload(path: Path, root: Path, *, include_hash: bool = False) -> dict:
    root = root.resolve(strict=False)
    path = path.resolve(strict=False)
    stat = path.stat()
    rel = path.relative_to(root).as_posix()
    payload = {
        "name": path.name,
        "relative_path": rel,
        "is_dir": path.is_dir(),
        "size_bytes": 0 if path.is_dir() else stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(),
        "extension": "" if path.is_dir() else path.suffix.lower(),
        "mime_type": "inode/directory" if path.is_dir() else mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "download_url": None,
    }
    if path.is_file():
        payload["download_url"] = "/api/storage/download?path=" + quote(rel, safe="")
        if include_hash:
            payload["sha256"] = sha256_file(path)
    return payload


def list_storage_directory(root: Path, relative_path: str | os.PathLike[str] | None = "") -> dict:
    root_resolved = root.resolve(strict=False)
    directory = resolve_storage_path(root_resolved, relative_path)
    if not directory.exists():
        raise FileNotFoundError(str(directory))
    if not directory.is_dir():
        raise NotADirectoryError(str(directory))
    entries = []
    for child in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name in SKIP_DIRS:
            continue
        entries.append(storage_entry_payload(child, root_resolved))
    rel = directory.relative_to(root_resolved).as_posix() if directory != root_resolved else ""
    parent = ""
    if rel:
        parent_path = Path(rel).parent
        parent = "" if str(parent_path) == "." else parent_path.as_posix()
    return {
        "root": str(root_resolved),
        "relative_path": rel,
        "parent": parent,
        "entry_count": len(entries),
        "entries": entries,
    }


def storage_status(root: Path, db_path: Path | None = None) -> dict:
    root_info = ensure_storage_root(root)
    writable = False
    write_error = None
    probe = root / ".ai_nas_storage_write_probe"
    try:
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        writable = True
    except OSError as exc:
        write_error = f"{type(exc).__name__}:{exc}"
    payload = {
        "generated_at": iso_now(),
        "personal_root": str(root),
        "root": root_info,
        "writable": writable,
        "write_error": write_error,
        "capacity": storage_capacity(root),
        "mount": storage_mount_info(root),
    }
    if db_path:
        payload["sqlite_index_path"] = str(db_path)
        payload["operation_log_count"] = len(latest_file_operations(db_path, limit=1000000))
    return payload


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


def _read_pdf_preview(path: Path, limit: int = 4000) -> tuple[str, str | None]:
    errors = []
    try:
        logging.getLogger("pypdf").setLevel(logging.CRITICAL)
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        chunks = []
        for page in reader.pages[:20]:
            chunks.append(page.extract_text() or "")
            if sum(len(chunk) for chunk in chunks) >= limit:
                break
        text = "\n".join(chunks).strip()
        if text:
            return text[:limit], None
        return "", "pdf_text_empty_or_scanned_ocr_required"
    except Exception as exc:  # pragma: no cover - dependency/pdf dependent
        errors.append(f"pypdf:{type(exc).__name__}:{exc}")

    try:
        import pdfplumber

        chunks = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:20]:
                chunks.append(page.extract_text() or "")
                if sum(len(chunk) for chunk in chunks) >= limit:
                    break
        text = "\n".join(chunks).strip()
        if text:
            return text[:limit], None
        return "", "pdf_text_empty_or_scanned_ocr_required"
    except Exception as exc:  # pragma: no cover - filesystem dependent
        errors.append(f"pdfplumber:{type(exc).__name__}:{exc}")
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        try:
            proc = subprocess.run(
                [pdftotext, "-f", "1", "-l", "20", "-layout", str(path), "-"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if proc.returncode == 0:
                text = proc.stdout.strip()
                if text:
                    return text[:limit], None
                return "", "pdf_text_empty_or_scanned_ocr_required"
            errors.append(f"pdftotext:exit_{proc.returncode}:{proc.stderr[:200]}")
        except Exception as exc:  # pragma: no cover - CLI/PDF dependent
            errors.append(f"pdftotext:{type(exc).__name__}:{exc}")
    else:
        errors.append("pdftotext:missing")
    return "", "pdf_extract_failed:" + " | ".join(errors)


def ocr_engine_status() -> dict:
    status = {
        "tesseract_cli": shutil.which("tesseract"),
        "pdftoppm_cli": shutil.which("pdftoppm"),
        "pytesseract_importable": False,
        "easyocr_importable": False,
        "fitz_importable": False,
        "cv2_importable": False,
        "pil_importable": False,
    }
    for module_name, key in [
        ("pytesseract", "pytesseract_importable"),
        ("easyocr", "easyocr_importable"),
        ("fitz", "fitz_importable"),
        ("cv2", "cv2_importable"),
        ("PIL", "pil_importable"),
    ]:
        try:
            __import__(module_name)
            status[key] = True
        except Exception:
            status[key] = False
    status["ocr_python_ready"] = bool(status["tesseract_cli"] and status["pytesseract_importable"])
    status["ocr_cli_ready"] = bool(status["tesseract_cli"])
    status["ocr_ready"] = bool(status["ocr_python_ready"] or status["ocr_cli_ready"])
    status["local_scan_detection_ready"] = bool(status["fitz_importable"] and status["pil_importable"])
    return status


def inspect_pdf_for_ocr(path: Path) -> dict:
    diagnostics = {
        "page_count": None,
        "text_char_count": 0,
        "embedded_image_count": 0,
        "renderable": False,
        "ocr_required": False,
        "ocr_engine_available": ocr_engine_status()["ocr_ready"],
        "diagnostic_error": None,
        "diagnostic_source": "fitz",
    }
    try:
        import fitz

        doc = fitz.open(str(path))
        diagnostics["page_count"] = doc.page_count
        for page in doc:
            text = page.get_text("text") or ""
            diagnostics["text_char_count"] += len(text.strip())
            diagnostics["embedded_image_count"] += len(page.get_images(full=True))
        if doc.page_count:
            page = doc.load_page(0)
            page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), alpha=False)
            diagnostics["renderable"] = True
        doc.close()
    except Exception as exc:  # pragma: no cover - PDF dependent
        diagnostics["diagnostic_error"] = f"{type(exc).__name__}:{exc}"
        try:
            logging.getLogger("pypdf").setLevel(logging.CRITICAL)
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            diagnostics["diagnostic_source"] = "pypdf_text_empty_fallback"
            diagnostics["page_count"] = len(reader.pages)
            diagnostics["text_char_count"] = sum(
                len((page.extract_text() or "").strip()) for page in reader.pages[:20]
            )
        except Exception as fallback_exc:  # pragma: no cover - dependency/pdf dependent
            diagnostics["diagnostic_source"] = "unavailable"
            diagnostics["diagnostic_error"] = (
                f"{diagnostics['diagnostic_error']} | "
                f"pypdf:{type(fallback_exc).__name__}:{fallback_exc}"
            )
            pdfinfo = shutil.which("pdfinfo")
            pdftoppm = shutil.which("pdftoppm")
            pdftotext = shutil.which("pdftotext")
            cli_errors = []
            if pdfinfo:
                try:
                    info = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, timeout=10, check=False)
                    if info.returncode == 0:
                        for line in info.stdout.splitlines():
                            if line.lower().startswith("pages:"):
                                try:
                                    diagnostics["page_count"] = int(line.split(":", 1)[1].strip())
                                except ValueError:
                                    pass
                                break
                        diagnostics["diagnostic_source"] = "pdf_cli"
                    else:
                        cli_errors.append(f"pdfinfo:exit_{info.returncode}:{info.stderr[:200]}")
                except Exception as cli_exc:  # pragma: no cover - CLI/PDF dependent
                    cli_errors.append(f"pdfinfo:{type(cli_exc).__name__}:{cli_exc}")
            else:
                cli_errors.append("pdfinfo:missing")
            if pdftotext:
                try:
                    text_proc = subprocess.run(
                        [pdftotext, "-f", "1", "-l", "20", "-layout", str(path), "-"],
                        capture_output=True,
                        text=True,
                        timeout=20,
                        check=False,
                    )
                    if text_proc.returncode == 0:
                        diagnostics["text_char_count"] = len(text_proc.stdout.strip())
                        diagnostics["diagnostic_source"] = "pdf_cli"
                    else:
                        cli_errors.append(f"pdftotext:exit_{text_proc.returncode}:{text_proc.stderr[:200]}")
                except Exception as cli_exc:  # pragma: no cover - CLI/PDF dependent
                    cli_errors.append(f"pdftotext:{type(cli_exc).__name__}:{cli_exc}")
            else:
                cli_errors.append("pdftotext:missing")
            if pdftoppm and diagnostics["page_count"]:
                try:
                    with tempfile.TemporaryDirectory(prefix="ai_nas_pdf_probe_") as tmp:
                        prefix = Path(tmp) / "page"
                        render = subprocess.run(
                            [pdftoppm, "-f", "1", "-l", "1", "-png", str(path), str(prefix)],
                            capture_output=True,
                            text=True,
                            timeout=20,
                            check=False,
                        )
                        diagnostics["renderable"] = render.returncode == 0 and bool(list(Path(tmp).glob("page-*.png")))
                        if render.returncode != 0:
                            cli_errors.append(f"pdftoppm:exit_{render.returncode}:{render.stderr[:200]}")
                except Exception as cli_exc:  # pragma: no cover - CLI/PDF dependent
                    cli_errors.append(f"pdftoppm:{type(cli_exc).__name__}:{cli_exc}")
            elif not pdftoppm:
                cli_errors.append("pdftoppm:missing")
            if cli_errors:
                diagnostics["diagnostic_error"] = f"{diagnostics['diagnostic_error']} | " + " | ".join(cli_errors)
    diagnostics["ocr_required"] = bool(
        diagnostics["page_count"]
        and diagnostics["text_char_count"] == 0
        and (diagnostics["embedded_image_count"] > 0 or diagnostics["renderable"])
    )
    if (
        not diagnostics["ocr_required"]
        and diagnostics["diagnostic_source"] == "pypdf_text_empty_fallback"
        and diagnostics["page_count"]
        and diagnostics["text_char_count"] == 0
    ):
        diagnostics["ocr_required"] = True
    return diagnostics


def ocr_candidate_record(record: dict, include_images: bool = True) -> bool:
    metadata = record.get("metadata") or {}
    ocr = metadata.get("ocr") or {}
    if ocr.get("required") is True:
        return True
    if not include_images or record.get("type") != "Photos":
        return False
    photo = metadata.get("photo") or {}
    labels = set(photo.get("labels") or [])
    return bool(labels & {"invoice", "screenshot"})


def _ocr_pdf_with_tesseract(path: Path, max_pages: int = 3) -> tuple[str, dict]:
    import fitz
    import pytesseract
    from PIL import Image

    chunks = []
    pages_processed = 0
    doc = fitz.open(str(path))
    try:
        for page_index in range(min(doc.page_count, max_pages)):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(image).strip()
            if text:
                chunks.append(text)
            pages_processed += 1
    finally:
        doc.close()
    return "\n".join(chunks).strip(), {"pages_processed": pages_processed, "max_pages": max_pages}


def _ocr_image_with_tesseract(path: Path) -> tuple[str, dict]:
    import pytesseract
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        text = pytesseract.image_to_string(image).strip()
    return text, {"pages_processed": 1, "max_pages": 1}


def _ocr_image_with_tesseract_cli(path: Path) -> tuple[str, dict]:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        raise RuntimeError("tesseract CLI not found")
    proc = subprocess.run([tesseract, str(path), "stdout"], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract CLI failed:{proc.stderr[:500]}")
    return proc.stdout.strip(), {"pages_processed": 1, "max_pages": 1, "backend": "tesseract_cli"}


def _ocr_pdf_with_tesseract_cli(path: Path, max_pages: int = 3) -> tuple[str, dict]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm CLI not found")
    chunks = []
    with tempfile.TemporaryDirectory(prefix="ai_nas_ocr_pdf_") as tmp:
        prefix = Path(tmp) / "page"
        proc = subprocess.run(
            [pdftoppm, "-f", "1", "-l", str(max_pages), "-png", str(path), str(prefix)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pdftoppm failed:{proc.stderr[:500]}")
        pages = sorted(Path(tmp).glob("page-*.png"))
        for page in pages:
            text, _ = _ocr_image_with_tesseract_cli(page)
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip(), {"pages_processed": len(pages), "max_pages": max_pages, "backend": "pdftoppm+tesseract_cli"}


def run_ocr_for_record(record: dict, max_pages: int = 3) -> dict:
    runtime = ocr_engine_status()
    path = Path(record["path"])
    if not runtime["ocr_ready"]:
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "status": "blocked_missing_ocr_engine",
            "engine": None,
            "text_preview": "",
            "error": "missing tesseract CLI",
            "metadata": {"runtime": runtime},
        }
    try:
        if path.suffix.lower() == ".pdf":
            if runtime["ocr_python_ready"]:
                text, metadata = _ocr_pdf_with_tesseract(path, max_pages=max_pages)
            else:
                text, metadata = _ocr_pdf_with_tesseract_cli(path, max_pages=max_pages)
        elif path.suffix.lower() in PHOTO_EXTS:
            if runtime["ocr_python_ready"]:
                text, metadata = _ocr_image_with_tesseract(path)
            else:
                text, metadata = _ocr_image_with_tesseract_cli(path)
        else:
            return {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "status": "skipped_unsupported_extension",
                "engine": "tesseract",
                "text_preview": "",
                "error": None,
                "metadata": {"extension": path.suffix.lower()},
            }
        if not text:
            return {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "status": "ocr_completed_no_text",
                "engine": "tesseract",
                "text_preview": "",
                "error": None,
                "metadata": metadata,
            }
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "status": "ocr_completed",
            "engine": "tesseract",
            "text_preview": text[:4000],
            "error": None,
            "metadata": metadata | {"text_char_count": len(text)},
        }
    except Exception as exc:  # pragma: no cover - OCR runtime dependent
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "status": "ocr_failed",
            "engine": "tesseract",
            "text_preview": "",
            "error": f"{type(exc).__name__}:{exc}",
            "metadata": {"runtime": runtime},
        }


def upsert_ocr_result(db_path: Path, result: dict) -> None:
    con = open_index_db(db_path)
    try:
        with con:
            con.execute(
                """
                INSERT INTO ocr_results(path, relative_path, status, engine, text_preview, error, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    relative_path=excluded.relative_path,
                    status=excluded.status,
                    engine=excluded.engine,
                    text_preview=excluded.text_preview,
                    error=excluded.error,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    result["path"],
                    result["relative_path"],
                    result["status"],
                    result.get("engine"),
                    result.get("text_preview") or "",
                    result.get("error"),
                    json.dumps(result.get("metadata") or {}, ensure_ascii=False),
                    iso_now(),
                ),
            )
    finally:
        con.close()


def ocr_results_summary(db_path: Path, limit: int = 20) -> dict:
    con = open_index_db(db_path)
    try:
        status_counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM ocr_results GROUP BY status")
        }
        recent = [
            {
                "relative_path": row["relative_path"],
                "status": row["status"],
                "engine": row["engine"],
                "error": row["error"],
                "updated_at": row["updated_at"],
                "text_preview": row["text_preview"][:240],
            }
            for row in con.execute(
                """
                SELECT relative_path, status, engine, error, updated_at, text_preview
                FROM ocr_results
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        ]
    finally:
        con.close()
    return {"status_counts": status_counts, "recent": recent}


def image_embedding_runtime_status() -> dict:
    status = {
        "torch_importable": False,
        "transformers_importable": False,
        "clip_importable": False,
        "open_clip_importable": False,
        "pil_importable": False,
        "module_errors": {},
    }
    for module_name, key in [
        ("torch", "torch_importable"),
        ("transformers", "transformers_importable"),
        ("clip", "clip_importable"),
        ("open_clip", "open_clip_importable"),
        ("PIL", "pil_importable"),
    ]:
        try:
            __import__(module_name)
            status[key] = True
            status["module_errors"][module_name] = None
        except Exception as exc:
            status[key] = False
            status["module_errors"][module_name] = f"{type(exc).__name__}:{exc}"
    status["production_clip_ready"] = bool(
        status["torch_importable"]
        and (status["clip_importable"] or status["open_clip_importable"] or status["transformers_importable"])
    )
    status["local_visual_embedding_ready"] = status["pil_importable"]
    return status


def local_visual_embedding(path: Path, bins: int = 4) -> tuple[list[float], dict]:
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB").resize((96, 96))
        pixels = list(image.getdata())
    hist = [0.0] * (bins * 3)
    brightness_values = []
    for red, green, blue in pixels:
        channels = (red, green, blue)
        brightness_values.append((red + green + blue) / 3.0)
        for channel_index, value in enumerate(channels):
            bucket = min(bins - 1, int(value / (256 / bins)))
            hist[channel_index * bins + bucket] += 1.0
    total = float(len(pixels)) or 1.0
    hist = [value / total for value in hist]
    mean_rgb = [sum(pixel[idx] for pixel in pixels) / total / 255.0 for idx in range(3)]
    mean_brightness = sum(brightness_values) / total / 255.0
    variance = sum((value / 255.0 - mean_brightness) ** 2 for value in brightness_values) / total
    edge_hint = math.sqrt(max(variance, 0.0))
    vector = hist + mean_rgb + [mean_brightness, edge_hint]
    while len(vector) < IMAGE_EMBEDDING_DIM:
        vector.append(0.0)
    vector = vector[:IMAGE_EMBEDDING_DIM]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [round(value / norm, 8) for value in vector]
    metadata = {
        "width": image.width,
        "height": image.height,
        "bins_per_channel": bins,
        "mean_rgb": [round(value, 4) for value in mean_rgb],
        "mean_brightness": round(mean_brightness, 4),
        "edge_hint": round(edge_hint, 4),
    }
    return vector, metadata


def run_image_embedding_for_record(record: dict) -> dict:
    runtime = image_embedding_runtime_status()
    path = Path(record["path"])
    if record.get("type") != "Photos":
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "model_id": IMAGE_EMBEDDING_MODEL_ID,
            "dim": IMAGE_EMBEDDING_DIM,
            "status": "skipped_not_photo",
            "engine": None,
            "vector": [],
            "error": None,
            "metadata": {"runtime": runtime},
        }
    if not runtime["local_visual_embedding_ready"]:
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "model_id": IMAGE_EMBEDDING_MODEL_ID,
            "dim": IMAGE_EMBEDDING_DIM,
            "status": "blocked_missing_local_image_runtime",
            "engine": None,
            "vector": [],
            "error": "missing PIL image runtime",
            "metadata": {"runtime": runtime},
        }
    try:
        vector, metadata = local_visual_embedding(path)
        production_status = "ready" if runtime["production_clip_ready"] else "blocked_missing_clip_runtime"
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "model_id": IMAGE_EMBEDDING_MODEL_ID,
            "dim": IMAGE_EMBEDDING_DIM,
            "status": "local_visual_embedding_completed",
            "engine": "PIL histogram",
            "vector": vector,
            "error": None,
            "metadata": metadata | {
                "runtime": runtime,
                "production_clip_status": production_status,
                "production_clip_or_transformer": False,
            },
        }
    except Exception as exc:  # pragma: no cover - image dependent
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "model_id": IMAGE_EMBEDDING_MODEL_ID,
            "dim": IMAGE_EMBEDDING_DIM,
            "status": "image_embedding_failed",
            "engine": "PIL histogram",
            "vector": [],
            "error": f"{type(exc).__name__}:{exc}",
            "metadata": {"runtime": runtime},
        }


def upsert_image_embedding_result(db_path: Path, result: dict) -> None:
    con = open_index_db(db_path)
    try:
        with con:
            con.execute(
                """
                INSERT INTO image_embeddings(path, relative_path, model_id, dim, status, engine, vector_json, error, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    relative_path=excluded.relative_path,
                    model_id=excluded.model_id,
                    dim=excluded.dim,
                    status=excluded.status,
                    engine=excluded.engine,
                    vector_json=excluded.vector_json,
                    error=excluded.error,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    result["path"],
                    result["relative_path"],
                    result["model_id"],
                    result["dim"],
                    result["status"],
                    result.get("engine"),
                    json.dumps(result.get("vector") or [], separators=(",", ":")),
                    result.get("error"),
                    json.dumps(result.get("metadata") or {}, ensure_ascii=False),
                    iso_now(),
                ),
            )
    finally:
        con.close()


def image_embedding_summary(db_path: Path, limit: int = 20) -> dict:
    photo_exts = tuple(sorted(PHOTO_EXTS))
    placeholders = ",".join("?" for _ in photo_exts)
    con = open_index_db(db_path)
    try:
        status_counts = {
            row["status"]: row["count"]
            for row in con.execute(
                f"""
                SELECT image_embeddings.status AS status, COUNT(*) AS count
                FROM image_embeddings
                JOIN records ON records.path = image_embeddings.path
                WHERE records.type = 'Photos'
                  AND lower(records.extension) IN ({placeholders})
                GROUP BY image_embeddings.status
                """,
                photo_exts,
            )
        }
        recent = [
            {
                "relative_path": row["relative_path"],
                "model_id": row["model_id"],
                "status": row["status"],
                "engine": row["engine"],
                "error": row["error"],
                "updated_at": row["updated_at"],
            }
            for row in con.execute(
                f"""
                SELECT image_embeddings.relative_path, image_embeddings.model_id, image_embeddings.status,
                       image_embeddings.engine, image_embeddings.error, image_embeddings.updated_at
                FROM image_embeddings
                JOIN records ON records.path = image_embeddings.path
                WHERE records.type = 'Photos'
                  AND lower(records.extension) IN ({placeholders})
                ORDER BY image_embeddings.updated_at DESC
                LIMIT ?
                """,
                (*photo_exts, limit),
            )
        ]
    finally:
        con.close()
    return {"status_counts": status_counts, "recent": recent}


def ensure_image_embeddings_for_photos(db_path: Path, limit: int = 500) -> dict:
    photo_exts = tuple(sorted(PHOTO_EXTS))
    placeholders = ",".join("?" for _ in photo_exts)
    con = open_index_db(db_path)
    try:
        rows = con.execute(
            f"""
            SELECT records.*
            FROM records
            LEFT JOIN image_embeddings
              ON image_embeddings.path = records.path
             AND image_embeddings.model_id = ?
             AND image_embeddings.dim = ?
            WHERE records.type = 'Photos'
              AND lower(records.extension) IN ({placeholders})
              AND image_embeddings.path IS NULL
            ORDER BY records.relative_path
            LIMIT ?
            """,
            (IMAGE_EMBEDDING_MODEL_ID, IMAGE_EMBEDDING_DIM, *photo_exts, limit),
        ).fetchall()
        records = [_record_from_sqlite_row(row) for row in rows]
    finally:
        con.close()

    results = []
    for record in records:
        result = run_image_embedding_for_record(record)
        upsert_image_embedding_result(db_path, result)
        results.append(result)
    return {
        "attempted": len(results),
        "completed": sum(1 for item in results if item.get("status") == "local_visual_embedding_completed"),
        "failed": sum(1 for item in results if item.get("status") == "image_embedding_failed"),
        "blocked": sum(1 for item in results if str(item.get("status", "")).startswith("blocked_")),
    }


def vision_caption_runtime_status() -> dict:
    endpoint = os.environ.get("AI_NAS_VISION_CAPTION_ENDPOINT", "").strip()
    base_url = os.environ.get("AI_NAS_VISION_CAPTION_BASE_URL", os.environ.get("OPENAI_BASE_URL", "")).strip()
    api_key = os.environ.get("AI_NAS_VISION_CAPTION_API_KEY", os.environ.get("OPENAI_API_KEY", "")).strip()
    model_id = os.environ.get("AI_NAS_VISION_CAPTION_MODEL", "").strip()
    if not endpoint and base_url:
        endpoint = base_url.rstrip("/") + "/chat/completions"
    if not endpoint and api_key:
        endpoint = "https://api.openai.com/v1/chat/completions"
    return {
        "provider": "openai_compatible_vision_caption",
        "configured": bool(endpoint and model_id),
        "endpoint_configured": bool(endpoint),
        "api_key_present": bool(api_key),
        "model_configured": bool(model_id),
        "model_id": model_id,
        "schema_version": IMAGE_CAPTION_SCHEMA_VERSION,
    }


def _vision_caption_settings() -> dict:
    status = vision_caption_runtime_status()
    endpoint = os.environ.get("AI_NAS_VISION_CAPTION_ENDPOINT", "").strip()
    base_url = os.environ.get("AI_NAS_VISION_CAPTION_BASE_URL", os.environ.get("OPENAI_BASE_URL", "")).strip()
    if not endpoint and base_url:
        endpoint = base_url.rstrip("/") + "/chat/completions"
    if not endpoint and os.environ.get("AI_NAS_VISION_CAPTION_API_KEY", os.environ.get("OPENAI_API_KEY", "")).strip():
        endpoint = "https://api.openai.com/v1/chat/completions"
    return {
        "endpoint": endpoint,
        "api_key": os.environ.get("AI_NAS_VISION_CAPTION_API_KEY", os.environ.get("OPENAI_API_KEY", "")).strip(),
        "model_id": status["model_id"],
        "timeout_seconds": int(os.environ.get("AI_NAS_VISION_CAPTION_TIMEOUT_SECONDS", "120") or "120"),
        "status": status,
    }


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_json_payload(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {"caption": str(loaded)}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if 0 <= start < end:
            loaded = json.loads(raw[start:end + 1])
            return loaded if isinstance(loaded, dict) else {"caption": str(loaded)}
    return {"caption": raw}


def _flatten_caption_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_caption_values(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for key, item in value.items():
            out.append(str(key))
            out.extend(_flatten_caption_values(item))
        return out
    return [str(value)]


def normalize_vision_caption_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {"caption": str(payload)}
    caption = str(payload.get("caption") or payload.get("description") or payload.get("summary") or "").strip()
    objects = payload.get("objects") if isinstance(payload.get("objects"), list) else []
    people = payload.get("people") if isinstance(payload.get("people"), list) else []
    attributes = payload.get("attributes") if isinstance(payload.get("attributes"), dict) else {}
    scene = payload.get("scene") if isinstance(payload.get("scene"), (str, list, dict)) else ""
    text_visible = payload.get("visible_text") or payload.get("text") or []
    normalized = {
        "caption": caption,
        "objects": objects,
        "people": people,
        "attributes": attributes,
        "scene": scene,
        "visible_text": text_visible,
        "privacy": {
            "face_recognition_performed": False,
            "person_identity_verified": False,
            "identity_claims_allowed": False,
        },
        "schema_version": IMAGE_CAPTION_SCHEMA_VERSION,
    }
    search_parts = _flatten_caption_values(normalized)
    normalized["search_text"] = " ".join(part.strip() for part in search_parts if str(part).strip())[:12000]
    return normalized


def request_vision_caption_with_openai_compatible(path: Path, settings: dict | None = None) -> dict:
    settings = settings or _vision_caption_settings()
    endpoint = str(settings.get("endpoint") or "")
    model_id = str(settings.get("model_id") or "")
    if not endpoint or not model_id:
        raise RuntimeError("vision_caption_provider_not_configured")
    prompt = (
        "Return JSON only. Describe the image for NAS photo search. "
        "Do not identify people by name. Do not perform face recognition. "
        "Include keys: caption, objects, people, attributes, scene, visible_text. "
        "For each generic person, include clothing with upper_color, upper_garment, lower_color, "
        "and evidence_terms. Be explicit about clothing colors, objects, documents, screenshots, "
        "vehicles, indoor/outdoor scene, and visible text."
    )
    payload = {
        "model": model_id,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are a privacy-aware image captioning worker for a local NAS index."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": _image_data_url(path), "detail": "high"}},
                ],
            },
        ],
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    api_key = str(settings.get("api_key") or "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    timeout = int(settings.get("timeout_seconds") or 120)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("vision_caption_empty_response")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        text_chunks = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                text_chunks.append(str(item.get("text") or ""))
        content = "\n".join(text_chunks)
    structured = _extract_json_payload(str(content or ""))
    structured.setdefault("model_id", parsed.get("model") or model_id)
    return structured


def run_image_caption_for_record(record: dict, caption_provider=None) -> dict:
    path = Path(record["path"])
    runtime = vision_caption_runtime_status()
    if record.get("type") != "Photos":
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "provider": "llm_vision_caption",
            "model_id": runtime.get("model_id") or "",
            "schema_version": IMAGE_CAPTION_SCHEMA_VERSION,
            "status": "skipped_not_photo",
            "caption": "",
            "structured": {},
            "search_text": "",
            "error": None,
            "metadata": {"runtime": runtime},
        }
    if caption_provider is None and not runtime["configured"]:
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "provider": "openai_compatible_vision_caption",
            "model_id": runtime.get("model_id") or "",
            "schema_version": IMAGE_CAPTION_SCHEMA_VERSION,
            "status": "blocked_missing_caption_provider",
            "caption": "",
            "structured": {},
            "search_text": "",
            "error": "AI_NAS_VISION_CAPTION_ENDPOINT and AI_NAS_VISION_CAPTION_MODEL are required, or set OPENAI_API_KEY plus AI_NAS_VISION_CAPTION_MODEL",
            "metadata": {"runtime": runtime},
        }
    try:
        if caption_provider is not None:
            raw_payload = caption_provider(record)
            provider_name = str(raw_payload.get("provider") or "injected_vision_caption_provider") if isinstance(raw_payload, dict) else "injected_vision_caption_provider"
            model_id = str(raw_payload.get("model_id") or raw_payload.get("model") or "injected-vision-caption") if isinstance(raw_payload, dict) else "injected-vision-caption"
        else:
            settings = _vision_caption_settings()
            raw_payload = request_vision_caption_with_openai_compatible(path, settings)
            provider_name = "openai_compatible_vision_caption"
            model_id = str(raw_payload.get("model_id") or settings.get("model_id") or "")
        structured = normalize_vision_caption_payload(raw_payload)
        caption = str(structured.get("caption") or "").strip()
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "provider": provider_name,
            "model_id": model_id,
            "schema_version": IMAGE_CAPTION_SCHEMA_VERSION,
            "status": IMAGE_CAPTION_STATUS_COMPLETED,
            "caption": caption,
            "structured": structured,
            "search_text": str(structured.get("search_text") or ""),
            "error": None,
            "metadata": {
                "runtime": runtime,
                "privacy": structured.get("privacy") or {},
            },
        }
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        return {
            "path": record["path"],
            "relative_path": record["relative_path"],
            "provider": "openai_compatible_vision_caption",
            "model_id": runtime.get("model_id") or "",
            "schema_version": IMAGE_CAPTION_SCHEMA_VERSION,
            "status": "caption_failed",
            "caption": "",
            "structured": {},
            "search_text": "",
            "error": f"{type(exc).__name__}:{exc}",
            "metadata": {"runtime": runtime},
        }


def upsert_image_caption_result(db_path: Path, result: dict) -> None:
    con = open_index_db(db_path)
    try:
        with con:
            con.execute(
                """
                INSERT INTO image_captions(
                    path, relative_path, provider, model_id, schema_version, status,
                    caption, structured_json, search_text, error, metadata_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    relative_path=excluded.relative_path,
                    provider=excluded.provider,
                    model_id=excluded.model_id,
                    schema_version=excluded.schema_version,
                    status=excluded.status,
                    caption=excluded.caption,
                    structured_json=excluded.structured_json,
                    search_text=excluded.search_text,
                    error=excluded.error,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    result["path"],
                    result["relative_path"],
                    result.get("provider") or "",
                    result.get("model_id") or "",
                    result.get("schema_version") or IMAGE_CAPTION_SCHEMA_VERSION,
                    result.get("status") or "",
                    result.get("caption") or "",
                    json.dumps(result.get("structured") or {}, ensure_ascii=False),
                    result.get("search_text") or "",
                    result.get("error"),
                    json.dumps(result.get("metadata") or {}, ensure_ascii=False),
                    iso_now(),
                ),
            )
    finally:
        con.close()


def image_caption_summary(db_path: Path, limit: int = 20) -> dict:
    photo_exts = tuple(sorted(PHOTO_EXTS))
    placeholders = ",".join("?" for _ in photo_exts)
    con = open_index_db(db_path)
    try:
        status_counts = {
            row["status"]: row["count"]
            for row in con.execute(
                f"""
                SELECT image_captions.status AS status, COUNT(*) AS count
                FROM image_captions
                JOIN records ON records.path = image_captions.path
                WHERE records.type = 'Photos'
                  AND lower(records.extension) IN ({placeholders})
                GROUP BY image_captions.status
                """,
                photo_exts,
            )
        }
        recent = [
            {
                "relative_path": row["relative_path"],
                "provider": row["provider"],
                "model_id": row["model_id"],
                "status": row["status"],
                "caption": row["caption"][:240],
                "error": row["error"],
                "updated_at": row["updated_at"],
            }
            for row in con.execute(
                f"""
                SELECT image_captions.relative_path, image_captions.provider, image_captions.model_id,
                       image_captions.status, image_captions.caption, image_captions.error,
                       image_captions.updated_at
                FROM image_captions
                JOIN records ON records.path = image_captions.path
                WHERE records.type = 'Photos'
                  AND lower(records.extension) IN ({placeholders})
                ORDER BY image_captions.updated_at DESC
                LIMIT ?
                """,
                (*photo_exts, limit),
            )
        ]
    finally:
        con.close()
    return {"status_counts": status_counts, "recent": recent}


def ensure_image_captions_for_photos(db_path: Path, limit: int = 500, caption_provider=None) -> dict:
    target_model_id = "" if caption_provider is not None else str(vision_caption_runtime_status().get("model_id") or "")
    photo_exts = tuple(sorted(PHOTO_EXTS))
    placeholders = ",".join("?" for _ in photo_exts)
    con = open_index_db(db_path)
    try:
        rows = con.execute(
            f"""
            SELECT records.*
            FROM records
            LEFT JOIN image_captions
              ON image_captions.path = records.path
             AND image_captions.schema_version = ?
            WHERE records.type = 'Photos'
              AND lower(records.extension) IN ({placeholders})
              AND (
                image_captions.path IS NULL
                OR image_captions.status LIKE 'blocked_%'
                OR image_captions.status = 'caption_failed'
                OR (? != '' AND image_captions.model_id != ?)
              )
            ORDER BY records.relative_path
            LIMIT ?
            """,
            (IMAGE_CAPTION_SCHEMA_VERSION, *photo_exts, target_model_id, target_model_id, limit),
        ).fetchall()
        records = [_record_from_sqlite_row(row) for row in rows]
    finally:
        con.close()

    results = []
    for record in records:
        result = run_image_caption_for_record(record, caption_provider=caption_provider)
        upsert_image_caption_result(db_path, result)
        results.append(result)
    return {
        "attempted": len(results),
        "completed": sum(1 for item in results if item.get("status") == IMAGE_CAPTION_STATUS_COMPLETED),
        "failed": sum(1 for item in results if item.get("status") == "caption_failed"),
        "blocked": sum(1 for item in results if str(item.get("status", "")).startswith("blocked_")),
        "runtime": vision_caption_runtime_status(),
    }


def read_text_preview(path: Path, limit: int = 4000) -> tuple[str, str | None]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _read_pdf_preview(path, limit)
    if ext not in TEXT_EXTS and not path.name.lower().endswith(".movie.txt"):
        return "", "unsupported_binary_or_office_format"
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - filesystem dependent
        return "", f"read_failed:{type(exc).__name__}:{exc}"
    return data[:limit], None


def classify_document(path: Path, text: str, category: str) -> str | None:
    if category != "Documents" and path.suffix.lower() not in DOC_EXTS:
        return None
    haystack = f"{path.name} {path.parent} {text}".lower()
    scores = Counter()
    for doc_class, aliases in DOCUMENT_CLASS_ALIASES.items():
        for alias in aliases:
            if alias.lower() in haystack:
                scores[doc_class] += 1
    if not scores:
        return "unknown"
    return scores.most_common(1)[0][0]


def extract_document_entities(text: str) -> dict:
    compact = " ".join(text.split())
    date_patterns = [
        r"\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b",
        r"(?:19|20)\d{2}\u5e74(?:0?[1-9]|1[0-2])\u6708(?:0?[1-9]|[12]\d|3[01])?\u65e5?",
    ]
    amount_patterns = [
        r"\b(?:CNY|RMB|USD|EUR)\s*[\d,]+(?:\.\d{1,2})?\b",
        r"\b[\d,]+(?:\.\d{1,2})?\s*(?:CNY|RMB|USD|EUR|yuan|dollars?)\b",
        r"[\d,]+(?:\.\d{1,2})?\s*(?:\u5143|\u4e07\u5143)",
    ]
    dates = []
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, compact, flags=re.IGNORECASE))
    amounts = []
    for pattern in amount_patterns:
        amounts.extend(re.findall(pattern, compact, flags=re.IGNORECASE))
    payment_terms = []
    for sentence in re.split(r"(?<=[.!?。；;])\s+", compact):
        lowered = sentence.lower()
        if any(needle in lowered for needle in ["payment", "deposit", "final", "invoice", "\u4ed8\u6b3e", "\u5b9a\u91d1", "\u5c3e\u6b3e", "\u53d1\u7968"]):
            payment_terms.append(sentence[:240])
        if len(payment_terms) >= 5:
            break
    return {
        "dates": sorted(set(dates))[:20],
        "amounts": sorted(set(amounts))[:20],
        "payment_terms": payment_terms,
    }


def _rational_to_float(value) -> float:
    numerator = getattr(value, "numerator", None)
    denominator = getattr(value, "denominator", None)
    if numerator is not None and denominator:
        return float(numerator) / float(denominator)
    if isinstance(value, tuple) and len(value) == 2 and value[1]:
        return float(value[0]) / float(value[1])
    return float(value)


def _gps_to_decimal(values, ref: str | None) -> float | None:
    if not values or len(values) < 3:
        return None
    degrees = _rational_to_float(values[0])
    minutes = _rational_to_float(values[1])
    seconds = _rational_to_float(values[2])
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if ref in {"S", "W"}:
        decimal = -decimal
    return round(decimal, 6)


def _dct_coefficient(pixels: list[float], u: int, v: int, size: int = 32) -> float:
    total = 0.0
    for y in range(size):
        for x in range(size):
            total += (
                pixels[y * size + x]
                * math.cos(((2 * x + 1) * u * math.pi) / (2 * size))
                * math.cos(((2 * y + 1) * v * math.pi) / (2 * size))
            )
    cu = 1 / math.sqrt(2) if u == 0 else 1.0
    cv = 1 / math.sqrt(2) if v == 0 else 1.0
    return 0.25 * cu * cv * total


def perceptual_hash(path: Path) -> str:
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        normalized = ImageOps.exif_transpose(image).convert("L").resize((32, 32))
        pixels = [float(value) for value in normalized.getdata()]
    coeffs = [_dct_coefficient(pixels, u, v) for v in range(8) for u in range(8)]
    low_freq = coeffs[1:]
    median = sorted(low_freq)[len(low_freq) // 2]
    bits = 0
    for coeff in coeffs:
        bits = (bits << 1) | int(coeff > median)
    return f"{bits:016x}"


def infer_photo_labels(path: Path) -> list[str]:
    haystack = " ".join(path.parts).lower()
    labels = []
    label_aliases = {
        "beach": ["beach", "sea", "coast", "ocean", "\u6d77\u8fb9", "\u6d77\u6ee9"],
        "meal": ["meal", "dinner", "lunch", "party", "restaurant", "\u805a\u9910", "\u5403\u996d"],
        "car": ["car", "vehicle", "auto", "\u6c7d\u8f66", "\u8f66"],
        "white": ["white", "\u767d\u8272"],
        "invoice": ["invoice", "receipt", "bill", "\u53d1\u7968", "\u7968\u636e"],
        "screenshot": ["screenshot", "screen", "\u622a\u56fe"],
        "child": ["child", "kid", "baby", "\u5b69\u5b50", "\u5c0f\u5b69"],
    }
    for label, aliases in label_aliases.items():
        if any(alias in haystack for alias in aliases):
            labels.append(label)
    return sorted(set(labels))


def extract_photo_metadata(path: Path) -> dict:
    metadata = {
        "photo": {
            "width": None,
            "height": None,
            "taken_at": None,
            "gps": None,
            "phash": None,
            "labels": infer_photo_labels(path),
            "exif_available": False,
        },
        "content_status": "metadata_only",
        "parse_error": None,
    }
    try:
        from PIL import ExifTags, Image, ImageOps

        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            metadata["photo"]["width"], metadata["photo"]["height"] = image.size
            exif = image.getexif()
            metadata["photo"]["exif_available"] = bool(exif)
            if exif:
                tag_names = {value: key for key, value in ExifTags.TAGS.items()}
                taken_at = exif.get(tag_names.get("DateTimeOriginal")) or exif.get(tag_names.get("DateTime"))
                if taken_at:
                    metadata["photo"]["taken_at"] = str(taken_at)
                gps_tag = tag_names.get("GPSInfo")
                gps_raw = None
                if gps_tag is not None:
                    try:
                        gps_raw = exif.get_ifd(gps_tag)
                    except Exception:
                        gps_raw = exif.get(gps_tag)
                if isinstance(gps_raw, dict) and gps_raw:
                    gps = {}
                    for key, value in gps_raw.items():
                        gps[ExifTags.GPSTAGS.get(key, key)] = value
                    lat = _gps_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
                    lon = _gps_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
                    if lat is not None and lon is not None:
                        metadata["photo"]["gps"] = {"latitude": lat, "longitude": lon}
        metadata["photo"]["phash"] = perceptual_hash(path)
    except Exception as exc:  # pragma: no cover - image/exif dependent
        metadata["content_status"] = "not_extracted"
        metadata["parse_error"] = f"photo_extract_failed:{type(exc).__name__}:{exc}"
    return metadata


def build_metadata(path: Path, category: str, preview: str, parse_error: str | None) -> dict:
    if category == "Photos":
        return extract_photo_metadata(path)
    metadata = {
        "content_status": "extracted" if preview else "not_extracted",
        "parse_error": parse_error,
    }
    if path.suffix.lower() == ".pdf":
        pdf_diagnostics = inspect_pdf_for_ocr(path)
        metadata["pdf"] = pdf_diagnostics
        if pdf_diagnostics.get("ocr_required"):
            metadata["ocr"] = {
                "required": True,
                "engine_available": pdf_diagnostics.get("ocr_engine_available", False),
                "status": "blocked_missing_ocr_engine"
                if not pdf_diagnostics.get("ocr_engine_available")
                else "ready_for_ocr_extraction",
            }
        elif parse_error:
            metadata["ocr"] = {
                "required": "unknown",
                "engine_available": pdf_diagnostics.get("ocr_engine_available", False),
                "status": "pdf_diagnostic_failed_or_not_scanned",
            }
    document_class = classify_document(path, preview, category)
    if document_class:
        metadata["document_class"] = document_class
        metadata["entities"] = extract_document_entities(preview) if preview else {"dates": [], "amounts": [], "payment_terms": []}
    return metadata


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


def build_record_for_path(path: Path, root: Path) -> dict:
    stat = path.stat()
    rel = path.relative_to(root).as_posix()
    digest = sha256_file(path)
    category, tags = classify_file(path, root)
    if category == "Photos":
        preview, parse_error = "", None
    else:
        preview, parse_error = read_text_preview(path)
    metadata = build_metadata(path, category, preview, parse_error)
    document_class = metadata.get("document_class")
    if document_class and document_class != "unknown":
        tags.append(document_class)
    photo = metadata.get("photo") or {}
    for label in photo.get("labels", []):
        tags.append(label)
    tags = sorted(set(tags))
    entity_text = " ".join(
        (metadata.get("entities") or {}).get("dates", [])
        + (metadata.get("entities") or {}).get("amounts", [])
        + (metadata.get("entities") or {}).get("payment_terms", [])
    )
    photo_text = " ".join(
        [
            " ".join(photo.get("labels", [])),
            str(photo.get("taken_at") or ""),
            str(photo.get("phash") or ""),
            str(photo.get("gps") or ""),
        ]
    )
    keywords = extract_keywords(f"{preview} {document_class or ''} {entity_text} {photo_text}")
    return {
        "path": str(path),
        "relative_path": rel,
        "name": path.name,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(),
        "sha256": digest,
        "type": category,
        "extension": path.suffix.lower(),
        "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "year": infer_year(path.name),
        "tags": tags,
        "keywords": keywords,
        "summary": summarize_text(preview, "content_not_extracted"),
        "parse_error": metadata.get("parse_error") or parse_error,
        "metadata": metadata,
    }


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def _record_from_sqlite_row(row: sqlite3.Row) -> dict:
    return {
        "path": row["path"],
        "relative_path": row["relative_path"],
        "name": row["name"],
        "size_bytes": row["size_bytes"],
        "mtime": row["mtime"],
        "sha256": row["sha256"],
        "type": row["type"],
        "extension": row["extension"],
        "mime_type": row["mime_type"],
        "year": row["year"],
        "tags": _json_list(row["tags_json"]),
        "keywords": _json_list(row["keywords_json"]),
        "summary": row["summary"],
        "parse_error": row["parse_error"],
        "metadata": json.loads(row["metadata_json"]) if "metadata_json" in row.keys() and row["metadata_json"] else {},
    }


def is_document_parse_failure(record: dict) -> bool:
    return bool(record.get("parse_error")) and record.get("type") == "Documents"


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
        try:
            records.append(build_record_for_path(path, root))
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
        metadata = record.get("metadata") or {}
        doc_class = metadata.get("document_class")
        doc_class_text = f" | doc_class: `{doc_class}`" if doc_class else ""
        lines.append(
            f"- `{record['relative_path']}` | `{record['type']}` | "
            f"{record['size_bytes']} bytes | tags: `{', '.join(record['tags'])}`{doc_class_text}"
        )
    if payload["failures"]:
        lines.extend(["", "## Parse Or Scan Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure['path']}`: `{failure['reason']}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    return json_path, md_path


def open_sqlite_connection(
    db_path: Path | str,
    *,
    timeout: float = 30.0,
    isolation_level: str | None | object = _SQLITE_DEFAULT_ISOLATION,
    row_factory: bool = False,
    prefer_wal: bool = True,
) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connect_kwargs = {"timeout": timeout}
    if isolation_level is not _SQLITE_DEFAULT_ISOLATION:
        connect_kwargs["isolation_level"] = isolation_level

    def connect() -> sqlite3.Connection:
        connection = sqlite3.connect(db_path, **connect_kwargs)
        if row_factory:
            connection.row_factory = sqlite3.Row
        return connection

    mode_key = str(db_path.resolve())
    cached_mode = _SQLITE_MODE_BY_PATH.get(mode_key)
    if cached_mode:
        last_error = None
        for _ in range(200):
            con = connect()
            try:
                if cached_mode == "wal" and prefer_wal:
                    con.execute("PRAGMA journal_mode=WAL")
                elif cached_mode == "delete":
                    con.execute("PRAGMA locking_mode=EXCLUSIVE")
                con.execute("PRAGMA synchronous=NORMAL")
                return con
            except sqlite3.OperationalError as exc:
                last_error = exc
                con.close()
                if "locked" not in str(exc).lower():
                    raise
                time.sleep(0.05)
        raise last_error or sqlite3.OperationalError("sqlite connection retry exhausted")

    con = connect()
    if prefer_wal:
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute("CREATE TABLE IF NOT EXISTS __ai_nas_sqlite_write_probe(id INTEGER)")
            con.execute("DROP TABLE IF EXISTS __ai_nas_sqlite_write_probe")
            con.commit()
            _SQLITE_MODE_BY_PATH[mode_key] = "wal"
        except sqlite3.OperationalError:
            # Some mounted/workspace filesystems used by the local probes
            # reject WAL sidecar locking with "disk I/O error". Keep the DB
            # in the requested report path and fall back to a single-writer
            # compatible mode instead of failing the whole acceptance probe.
            con.close()
            con = connect()
            con.execute("PRAGMA locking_mode=EXCLUSIVE")
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute("CREATE TABLE IF NOT EXISTS __ai_nas_sqlite_write_probe(id INTEGER)")
            con.execute("DROP TABLE IF EXISTS __ai_nas_sqlite_write_probe")
            con.commit()
            _SQLITE_MODE_BY_PATH[mode_key] = "delete"
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def open_index_db(db_path: Path | str) -> sqlite3.Connection:
    con = open_sqlite_connection(db_path, row_factory=True)
    try:
        journal_mode = con.execute("PRAGMA journal_mode").fetchone()
    except sqlite3.OperationalError:
        journal_mode = None
    if journal_mode and str(journal_mode[0]).lower() == "wal":
        pass
    else:
        try:
            con.execute("PRAGMA locking_mode=EXCLUSIVE")
        except sqlite3.OperationalError:
            pass
    try:
        con.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.OperationalError:
        con.close()
        raise
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            path TEXT PRIMARY KEY,
            relative_path TEXT NOT NULL,
            name TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            mtime TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            type TEXT NOT NULL,
            extension TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            year INTEGER,
            tags_json TEXT NOT NULL,
            keywords_json TEXT NOT NULL,
            summary TEXT NOT NULL,
            parse_error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            indexed_at TEXT NOT NULL
        )
        """
    )
    columns = {row["name"] for row in con.execute("PRAGMA table_info(records)")}
    if "metadata_json" not in columns:
        con.execute("ALTER TABLE records ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
    con.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS records_fts
        USING fts5(path UNINDEXED, relative_path, name, type, tags, keywords, summary)
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS index_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            personal_root TEXT NOT NULL,
            scan_dirs_json TEXT NOT NULL,
            max_files INTEGER NOT NULL,
            scanned_files INTEGER NOT NULL DEFAULT 0,
            added INTEGER NOT NULL DEFAULT 0,
            updated INTEGER NOT NULL DEFAULT 0,
            unchanged INTEGER NOT NULL DEFAULT 0,
            deleted INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            message TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT,
            reason TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            path TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            path TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            source_text TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model_id, dim)")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_results (
            path TEXT PRIMARY KEY,
            relative_path TEXT NOT NULL,
            status TEXT NOT NULL,
            engine TEXT,
            text_preview TEXT NOT NULL DEFAULT '',
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_ocr_results_status ON ocr_results(status)")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS image_embeddings (
            path TEXT PRIMARY KEY,
            relative_path TEXT NOT NULL,
            model_id TEXT NOT NULL,
            dim INTEGER NOT NULL,
            status TEXT NOT NULL,
            engine TEXT,
            vector_json TEXT NOT NULL DEFAULT '[]',
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_image_embeddings_status ON image_embeddings(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_image_embeddings_model ON image_embeddings(model_id, dim)")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS image_captions (
            path TEXT PRIMARY KEY,
            relative_path TEXT NOT NULL,
            provider TEXT NOT NULL,
            model_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            status TEXT NOT NULL,
            caption TEXT NOT NULL DEFAULT '',
            structured_json TEXT NOT NULL DEFAULT '{}',
            search_text TEXT NOT NULL DEFAULT '',
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_image_captions_status ON image_captions(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_image_captions_model ON image_captions(model_id, schema_version)")
    ensure_vision_product_schema(con)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS file_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            source_relative_path TEXT,
            target_relative_path TEXT,
            status TEXT NOT NULL,
            detail TEXT,
            size_bytes INTEGER,
            sha256 TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_file_operations_created ON file_operations(created_at)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_file_operations_action ON file_operations(action)")
    return con


def _tokenize_for_embedding(text: str) -> list[str]:
    normalized = text.lower()
    words = re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]", normalized)
    word_set = set(words)
    tokens: list[str] = []
    tokens.extend(words)
    for idx in range(len(words) - 1):
        if len(words[idx]) == 1 and len(words[idx + 1]) == 1:
            tokens.append(words[idx] + words[idx + 1])
    for canonical, aliases in SEMANTIC_ALIASES.items():
        matched_alias = False
        for alias in aliases:
            lowered = alias.lower()
            if " " in lowered or not lowered.isascii():
                matched_alias = matched_alias or lowered in normalized
            else:
                matched_alias = matched_alias or lowered in word_set
        if canonical in word_set or matched_alias:
            tokens.append(canonical)
            tokens.extend(alias.lower() for alias in aliases if alias.isascii())
    return tokens


def embed_text_local_hash(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    vector = [0.0] * dim
    for token, count in Counter(_tokenize_for_embedding(text)).items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign * (1.0 + math.log1p(count))
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [round(value / norm, 8) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def embedding_source_text(record: dict) -> str:
    metadata = record.get("metadata") or {}
    parts = [
        record.get("relative_path", ""),
        record.get("name", ""),
        record.get("type", ""),
        " ".join(record.get("tags", [])),
        " ".join(record.get("keywords", [])),
        record.get("summary", ""),
        metadata_search_text(metadata),
    ]
    if record.get("year"):
        parts.append(str(record["year"]))
    return " ".join(part for part in parts if part)


def _upsert_sqlite_embedding(con: sqlite3.Connection, record: dict, indexed_at: str) -> None:
    source_text = embedding_source_text(record)
    vector = embed_text_local_hash(source_text)
    con.execute(
        """
        INSERT INTO embeddings(path, model_id, dim, vector_json, source_text, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            model_id=excluded.model_id,
            dim=excluded.dim,
            vector_json=excluded.vector_json,
            source_text=excluded.source_text,
            updated_at=excluded.updated_at
        """,
        (
            record["path"],
            EMBEDDING_MODEL_ID,
            EMBEDDING_DIM,
            json.dumps(vector, separators=(",", ":")),
            source_text[:4000],
            indexed_at,
        ),
    )


def _upsert_sqlite_record(con: sqlite3.Connection, record: dict, indexed_at: str) -> None:
    con.execute(
        """
        INSERT INTO records (
            path, relative_path, name, size_bytes, mtime_ns, mtime, sha256, type,
            extension, mime_type, year, tags_json, keywords_json, summary,
            parse_error, metadata_json, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            relative_path=excluded.relative_path,
            name=excluded.name,
            size_bytes=excluded.size_bytes,
            mtime_ns=excluded.mtime_ns,
            mtime=excluded.mtime,
            sha256=excluded.sha256,
            type=excluded.type,
            extension=excluded.extension,
            mime_type=excluded.mime_type,
            year=excluded.year,
            tags_json=excluded.tags_json,
            keywords_json=excluded.keywords_json,
            summary=excluded.summary,
            parse_error=excluded.parse_error,
            metadata_json=excluded.metadata_json,
            indexed_at=excluded.indexed_at
        """,
        (
            record["path"],
            record["relative_path"],
            record["name"],
            record["size_bytes"],
            record["mtime_ns"],
            record["mtime"],
            record["sha256"],
            record["type"],
            record["extension"],
            record["mime_type"],
            record["year"],
            json.dumps(record["tags"], ensure_ascii=False),
            json.dumps(record["keywords"], ensure_ascii=False),
            record["summary"],
            record["parse_error"],
            json.dumps(record.get("metadata", {}), ensure_ascii=False),
            indexed_at,
        ),
    )
    con.execute("DELETE FROM records_fts WHERE path = ?", (record["path"],))
    metadata = record.get("metadata", {})
    entities = metadata.get("entities") or {}
    metadata_text = " ".join(
        [
            str(metadata.get("document_class") or ""),
            " ".join(entities.get("dates", [])),
            " ".join(entities.get("amounts", [])),
            " ".join(entities.get("payment_terms", [])),
        ]
    )
    con.execute(
        """
        INSERT INTO records_fts(path, relative_path, name, type, tags, keywords, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["path"],
            record["relative_path"],
            record["name"],
            record["type"],
            " ".join(record["tags"]),
            " ".join(record["keywords"]) + " " + metadata_text,
            record["summary"] + " " + metadata_text,
        ),
    )
    _upsert_sqlite_embedding(con, record, indexed_at)


def build_sqlite_inventory(root: Path, db_path: Path, max_files: int = 5000) -> dict:
    started_at = iso_now()
    con = open_index_db(db_path)
    with con:
        cur = con.execute(
            """
            INSERT INTO index_runs(started_at, personal_root, scan_dirs_json, max_files, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (started_at, str(root), json.dumps(list(SCAN_DIRS)), max_files, "running"),
        )
        run_id = int(cur.lastrowid)

    counters = Counter()
    failures: list[dict] = []
    existing_rows = {row["path"]: row for row in con.execute("SELECT * FROM records")}
    existing_embedding_paths = {
        row["path"]
        for row in con.execute(
            "SELECT path FROM embeddings WHERE model_id = ? AND dim = ?",
            (EMBEDDING_MODEL_ID, EMBEDDING_DIM),
        )
    }
    seen_paths: set[str] = set()

    try:
        with con:
            for idx, path in enumerate(iter_personal_files(root)):
                if idx >= max_files:
                    reason = f"max_files_exceeded:{max_files}"
                    failures.append({"path": str(root), "reason": reason})
                    con.execute(
                        "INSERT INTO failures(run_id, path, reason, created_at) VALUES (?, ?, ?, ?)",
                        (run_id, str(root), reason, iso_now()),
                    )
                    counters["failed"] += 1
                    break

                path_text = str(path)
                seen_paths.add(path_text)
                try:
                    stat = path.stat()
                    existing = existing_rows.get(path_text)
                    if existing and existing["size_bytes"] == stat.st_size and existing["mtime_ns"] == stat.st_mtime_ns:
                        if path_text not in existing_embedding_paths:
                            _upsert_sqlite_embedding(con, _record_from_sqlite_row(existing), iso_now())
                        counters["unchanged"] += 1
                        continue

                    record = build_record_for_path(path, root)
                    action = "updated" if existing else "added"
                    _upsert_sqlite_record(con, record, iso_now())
                    counters[action] += 1
                    if is_document_parse_failure(record):
                        failures.append({"path": path_text, "reason": record["parse_error"]})
                        counters["failed"] += 1
                        con.execute(
                            "INSERT INTO failures(run_id, path, reason, created_at) VALUES (?, ?, ?, ?)",
                            (run_id, path_text, record["parse_error"], iso_now()),
                        )
                    con.execute(
                        """
                        INSERT INTO change_log(run_id, action, path, relative_path, reason, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (run_id, action, path_text, record["relative_path"], "size_or_mtime_changed", iso_now()),
                    )
                except Exception as exc:  # pragma: no cover - filesystem dependent
                    reason = f"{type(exc).__name__}:{exc}"
                    failures.append({"path": path_text, "reason": reason})
                    counters["failed"] += 1
                    con.execute(
                        "INSERT INTO failures(run_id, path, reason, created_at) VALUES (?, ?, ?, ?)",
                        (run_id, path_text, reason, iso_now()),
                    )

            for old_path, old_row in existing_rows.items():
                if old_path in seen_paths:
                    continue
                con.execute("DELETE FROM records WHERE path = ?", (old_path,))
                con.execute("DELETE FROM records_fts WHERE path = ?", (old_path,))
                con.execute("DELETE FROM embeddings WHERE path = ?", (old_path,))
                con.execute("DELETE FROM ocr_results WHERE path = ?", (old_path,))
                con.execute("DELETE FROM image_embeddings WHERE path = ?", (old_path,))
                con.execute("DELETE FROM image_captions WHERE path = ?", (old_path,))
                counters["deleted"] += 1
                con.execute(
                    """
                    INSERT INTO change_log(run_id, action, path, relative_path, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, "deleted", old_path, old_row["relative_path"], "missing_from_scan", iso_now()),
                )

            scanned = counters["added"] + counters["updated"] + counters["unchanged"]
            status = "completed_with_failures" if counters["failed"] else "completed"
            finished_at = iso_now()
            con.execute(
                """
                UPDATE index_runs
                SET finished_at=?, scanned_files=?, added=?, updated=?, unchanged=?,
                    deleted=?, failed=?, status=?, message=?
                WHERE id=?
                """,
                (
                    finished_at,
                    scanned,
                    counters["added"],
                    counters["updated"],
                    counters["unchanged"],
                    counters["deleted"],
                    counters["failed"],
                    status,
                    None,
                    run_id,
                ),
            )
    except Exception as exc:
        with con:
            con.execute(
                "UPDATE index_runs SET finished_at=?, status=?, message=? WHERE id=?",
                (iso_now(), "failed", f"{type(exc).__name__}:{exc}", run_id),
            )
        raise
    finally:
        con.close()

    status_payload = sqlite_index_status(db_path)
    run_con = open_index_db(db_path)
    try:
        own_run = run_con.execute("SELECT * FROM index_runs WHERE id = ?", (run_id,)).fetchone()
    finally:
        run_con.close()
    if own_run:
        status_payload["status"] = own_run["status"]
        status_payload["last_scan_started_at"] = own_run["started_at"]
        status_payload["last_scan_finished_at"] = own_run["finished_at"]
        status_payload["last_run"] = {
            "id": own_run["id"],
            "scanned_files": own_run["scanned_files"],
            "added": own_run["added"],
            "updated": own_run["updated"],
            "unchanged": own_run["unchanged"],
            "deleted": own_run["deleted"],
            "failed": own_run["failed"],
            "message": own_run["message"],
        }
        processed = own_run["scanned_files"] + own_run["failed"]
        status_payload["queue_progress"] = {
            "processed": processed,
            "max_files": own_run["max_files"],
            "complete": own_run["status"] in {"completed", "completed_with_failures"},
        }

    return status_payload | {"run_id": run_id, "failures": failures}


def load_sqlite_inventory_payload(db_path: Path, root: Path) -> dict:
    con = open_index_db(db_path)
    try:
        records = [_record_from_sqlite_row(row) for row in con.execute("SELECT * FROM records ORDER BY relative_path")]
        run_failures = [
            {"path": row["path"], "reason": row["reason"]}
            for row in con.execute(
                """
                SELECT path, reason FROM failures
                WHERE run_id = COALESCE((SELECT MAX(id) FROM index_runs), -1)
                ORDER BY id
                """
            )
        ]
        parse_failures = [
            {"path": record["path"], "reason": record["parse_error"]}
            for record in records
            if is_document_parse_failure(record)
        ]
        latest = con.execute("SELECT * FROM index_runs ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        con.close()

    by_type = Counter(record["type"] for record in records)
    return {
        "generated_at": latest["finished_at"] if latest and latest["finished_at"] else iso_now(),
        "personal_root": str(root),
        "scan_dirs": list(SCAN_DIRS),
        "safety_policy": {
            "delete": False,
            "move": False,
            "overwrite": False,
            "source_preserved": True,
            "writes": "reports_and_sqlite_index_only_unless_bootstrap_demo_or_movie_copy_sort_is_explicit",
        },
        "index_engine": "sqlite_fts5",
        "file_count": len(records),
        "type_counts": dict(sorted(by_type.items())),
        "records": records,
        "failures": parse_failures + [failure for failure in run_failures if failure not in parse_failures],
    }


def sqlite_index_status(db_path: Path) -> dict:
    con = open_index_db(db_path)
    try:
        sqlite_runtime = {
            "journal_mode": con.execute("PRAGMA journal_mode").fetchone()[0],
            "locking_mode": con.execute("PRAGMA locking_mode").fetchone()[0],
        }
        latest = con.execute("SELECT * FROM index_runs ORDER BY id DESC LIMIT 1").fetchone()
        file_count = con.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"]
        failed_count = con.execute(
            "SELECT COUNT(*) AS count FROM records WHERE type = 'Documents' AND parse_error IS NOT NULL"
        ).fetchone()["count"]
        recent_failures = [
            {"path": row["path"], "relative_path": row["relative_path"], "reason": row["parse_error"]}
            for row in con.execute(
                """
                SELECT path, relative_path, parse_error FROM records
                WHERE type = 'Documents' AND parse_error IS NOT NULL
                ORDER BY indexed_at DESC
                LIMIT 20
                """
            )
        ]
        recent_changes = [
            dict(row)
            for row in con.execute(
                """
                SELECT action, relative_path, reason, created_at
                FROM change_log
                WHERE run_id = COALESCE((SELECT MAX(id) FROM index_runs), -1)
                ORDER BY id DESC
                LIMIT 20
                """
            )
        ]
        ocr_status_counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM ocr_results GROUP BY status")
        }
        recent_ocr_results = [
            {
                "relative_path": row["relative_path"],
                "status": row["status"],
                "engine": row["engine"],
                "error": row["error"],
                "updated_at": row["updated_at"],
            }
            for row in con.execute(
                """
                SELECT relative_path, status, engine, error, updated_at
                FROM ocr_results
                ORDER BY updated_at DESC
                LIMIT 10
                """
            )
        ]
        image_embedding_status_counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM image_embeddings GROUP BY status")
        }
        recent_image_embeddings = [
            {
                "relative_path": row["relative_path"],
                "model_id": row["model_id"],
                "status": row["status"],
                "engine": row["engine"],
                "error": row["error"],
                "updated_at": row["updated_at"],
            }
            for row in con.execute(
                """
                SELECT relative_path, model_id, status, engine, error, updated_at
                FROM image_embeddings
                ORDER BY updated_at DESC
                LIMIT 10
                """
            )
        ]
        image_caption_status_counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM image_captions GROUP BY status")
        }
        recent_image_captions = [
            {
                "relative_path": row["relative_path"],
                "provider": row["provider"],
                "model_id": row["model_id"],
                "status": row["status"],
                "caption": row["caption"][:240],
                "error": row["error"],
                "updated_at": row["updated_at"],
            }
            for row in con.execute(
                """
                SELECT relative_path, provider, model_id, status, caption, error, updated_at
                FROM image_captions
                ORDER BY updated_at DESC
                LIMIT 10
                """
            )
        ]
    finally:
        con.close()

    if not latest:
        return {
            "db_path": str(db_path),
            "sqlite_runtime": sqlite_runtime,
            "status": "not_built",
            "file_count": file_count,
            "failed_count": failed_count,
            "recent_failures": recent_failures,
            "recent_changes": [],
            "ocr": {"status_counts": ocr_status_counts, "recent": recent_ocr_results},
            "image_captions": {"status_counts": image_caption_status_counts, "recent": recent_image_captions},
            "image_embeddings": {"status_counts": image_embedding_status_counts, "recent": recent_image_embeddings},
            "queue_progress": {"processed": 0, "max_files": None, "complete": False},
        }

    processed = latest["scanned_files"] + latest["failed"]
    return {
        "db_path": str(db_path),
        "sqlite_runtime": sqlite_runtime,
        "status": latest["status"],
        "last_scan_started_at": latest["started_at"],
        "last_scan_finished_at": latest["finished_at"],
        "personal_root": latest["personal_root"],
        "scan_dirs": _json_list(latest["scan_dirs_json"]),
        "file_count": file_count,
        "failed_count": failed_count,
        "recent_failures": recent_failures,
        "last_run": {
            "id": latest["id"],
            "scanned_files": latest["scanned_files"],
            "added": latest["added"],
            "updated": latest["updated"],
            "unchanged": latest["unchanged"],
            "deleted": latest["deleted"],
            "failed": latest["failed"],
            "message": latest["message"],
        },
        "queue_progress": {
            "processed": processed,
            "max_files": latest["max_files"],
            "complete": latest["status"] in {"completed", "completed_with_failures"},
        },
        "ocr": {"status_counts": ocr_status_counts, "recent": recent_ocr_results},
        "image_captions": {"status_counts": image_caption_status_counts, "recent": recent_image_captions},
        "image_embeddings": {"status_counts": image_embedding_status_counts, "recent": recent_image_embeddings},
        "recent_changes": recent_changes,
    }


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


def expand_query_terms(query: str) -> list[str]:
    q = query.lower()
    terms = {term for term in re.findall(r"[\w\u4e00-\u9fff]{2,}", q) if term not in QUERY_STOPWORDS}
    if "\u53bb\u5e74" in q or "last year" in q:
        terms.add(str(datetime.now().year - 1))
    for canonical, aliases in SEMANTIC_ALIASES.items():
        if canonical in q or any(alias.lower() in q for alias in aliases):
            terms.add(canonical)
            for alias in aliases:
                if alias.isascii() and len(alias) >= 2:
                    terms.add(alias.lower())
    return sorted(terms)


def evidence_snippet(record: dict, query: str) -> str:
    metadata = record.get("metadata") or {}
    photo = metadata.get("photo") or {}
    if photo:
        bits = []
        if photo.get("labels"):
            bits.append("labels: " + ", ".join(photo["labels"]))
        if photo.get("taken_at"):
            bits.append("taken_at: " + str(photo["taken_at"]))
        if photo.get("gps"):
            gps = photo["gps"]
            bits.append(f"gps: {gps.get('latitude')},{gps.get('longitude')}")
        if photo.get("width") and photo.get("height"):
            bits.append(f"size: {photo['width']}x{photo['height']}")
        if photo.get("phash"):
            bits.append("phash: " + photo["phash"])
        if bits:
            return "; ".join(bits)[:320]
    entities = metadata.get("entities") or {}
    entity_bits = []
    if entities.get("dates"):
        entity_bits.append("dates: " + ", ".join(entities["dates"][:5]))
    if entities.get("amounts"):
        entity_bits.append("amounts: " + ", ".join(entities["amounts"][:5]))
    if entities.get("payment_terms"):
        entity_bits.append("payment: " + " | ".join(entities["payment_terms"][:2]))
    if entity_bits:
        return "; ".join(entity_bits)[:320]
    ocr = metadata.get("ocr") or {}
    pdf = metadata.get("pdf") or {}
    if ocr:
        bits = [
            f"ocr_required: {ocr.get('required')}",
            f"ocr_status: {ocr.get('status')}",
            f"engine_available: {ocr.get('engine_available')}",
        ]
        if pdf.get("page_count") is not None:
            bits.append(f"pages: {pdf.get('page_count')}")
        if pdf.get("embedded_image_count") is not None:
            bits.append(f"embedded_images: {pdf.get('embedded_image_count')}")
        return "; ".join(bits)[:320]
    summary = record.get("summary") or ""
    if summary and summary != "content_not_extracted":
        return summary[:240]
    fields = [
        record.get("relative_path", ""),
        " ".join(record.get("tags", [])),
        " ".join(record.get("keywords", [])),
    ]
    joined = " | ".join(part for part in fields if part)
    return joined[:240] if joined else "metadata_only_no_text_extract"


def metadata_search_text(metadata: dict) -> str:
    entities = metadata.get("entities") or {}
    photo = metadata.get("photo") or {}
    return " ".join(
        [
            str(metadata.get("document_class") or ""),
            " ".join(entities.get("dates", [])),
            " ".join(entities.get("amounts", [])),
            " ".join(entities.get("payment_terms", [])),
            " ".join(photo.get("labels", [])),
            str(photo.get("taken_at") or ""),
            str(photo.get("gps") or ""),
            str(photo.get("phash") or ""),
            str((metadata.get("ocr") or {}).get("status") or ""),
        ]
    )


def score_record(record: dict, query: str) -> tuple[float, list[str]]:
    q = query.lower()
    tokens = expand_query_terms(query)
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
    for tag, aliases in SEMANTIC_ALIASES.items():
        if tag in tokens and (tag in haystacks["tags"] or tag in haystacks["type"] or tag in haystacks["summary"]):
            score += 4
            reasons.append(f"semantic alias matches `{tag}`")
        for alias in aliases:
            if alias.lower() in q and tag in haystacks["tags"]:
                score += 3
                reasons.append(f"semantic alias matches `{alias}->{tag}`")
    if "recent" in tokens:
        score += 1
        reasons.append("recent query uses mtime as tie-breaker")
    return score, sorted(set(reasons))


def _fts_query_for_terms(terms: list[str]) -> str:
    safe_terms = []
    for term in terms:
        if len(term) < 2:
            continue
        escaped = term.replace('"', '""')
        safe_terms.append(f'"{escaped}"')
    return " OR ".join(safe_terms)


def search_sqlite_index(db_path: Path, query: str, limit: int = 10) -> list[dict]:
    con = open_index_db(db_path)
    terms = expand_query_terms(query)
    significant_terms = {term for term in terms if term.isascii() and not term.isdigit() and term != "recent"}
    specific_terms = significant_terms - GENERIC_SEARCH_TERMS
    fts_paths: set[str] = set()
    fts_query = _fts_query_for_terms(terms)
    try:
        if fts_query:
            for row in con.execute(
                "SELECT path FROM records_fts WHERE records_fts MATCH ? LIMIT 200",
                (fts_query,),
            ):
                fts_paths.add(row["path"])
    except sqlite3.Error:
        fts_paths = set()

    try:
        records = [_record_from_sqlite_row(row) for row in con.execute("SELECT * FROM records")]
    finally:
        con.close()

    matches = []
    for record in records:
        score, reasons = score_record(record, query)
        if record["path"] in fts_paths:
            score += 2
            reasons.append("sqlite fts matched query terms")
        if score <= 0:
            continue
        record_text = " ".join(
            [
                record.get("name", ""),
                record.get("relative_path", ""),
                record.get("type", ""),
                " ".join(record.get("tags", [])),
                " ".join(record.get("keywords", [])),
                record.get("summary", ""),
                metadata_search_text(record.get("metadata", {})),
            ]
        ).lower()
        required_terms = specific_terms or significant_terms
        if required_terms and not any(term in record_text for term in required_terms):
            continue
        matches.append(
            {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "type": record["type"],
                "score": round(score, 2),
                "confidence": min(0.95, round(0.25 + score / 50, 2)),
                "reasons": sorted(set(reasons))[:8],
                "evidence": evidence_snippet(record, query),
                "summary": record.get("summary", ""),
                "document_class": (record.get("metadata") or {}).get("document_class"),
                "entities": (record.get("metadata") or {}).get("entities", {}),
                "photo": (record.get("metadata") or {}).get("photo", {}),
                "source": "sqlite_fts5" if record["path"] in fts_paths else "sqlite_metadata",
            }
        )
    matches.sort(key=lambda item: (item["score"], item["relative_path"]), reverse=True)
    return matches[:limit]


def search_embedding_index(db_path: Path, query: str, limit: int = 10) -> list[dict]:
    con = open_index_db(db_path)
    terms = expand_query_terms(query)
    expanded_query = " ".join([query] + terms)
    query_vector = embed_text_local_hash(expanded_query)
    significant_terms = {term for term in terms if term.isascii() and not term.isdigit() and term != "recent"}
    specific_terms = significant_terms - GENERIC_SEARCH_TERMS
    rows = []
    try:
        for row in con.execute(
            """
            SELECT
                records.*,
                embeddings.vector_json AS embedding_vector_json,
                embeddings.source_text AS embedding_source_text
            FROM embeddings
            JOIN records ON records.path = embeddings.path
            WHERE embeddings.model_id = ? AND embeddings.dim = ?
            """,
            (EMBEDDING_MODEL_ID, EMBEDDING_DIM),
        ):
            rows.append(row)
    finally:
        con.close()

    matches = []
    for row in rows:
        record = _record_from_sqlite_row(row)
        try:
            record_vector = json.loads(row["embedding_vector_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        embedding_similarity = cosine_similarity(query_vector, record_vector)
        lexical_score, lexical_reasons = score_record(record, query)
        blended_score = embedding_similarity * 10 + min(lexical_score, 20) / 4
        record_text = " ".join(
            [
                record.get("name", ""),
                record.get("relative_path", ""),
                record.get("type", ""),
                " ".join(record.get("tags", [])),
                " ".join(record.get("keywords", [])),
                record.get("summary", ""),
                metadata_search_text(record.get("metadata", {})),
            ]
        ).lower()
        record_tokens = set(_tokenize_for_embedding(record_text))
        has_specific_term = bool(
            specific_terms
            and any(
                term in record_tokens
                or (" " in term and term in record_text)
                or (not term.isascii() and term in record_text)
                for term in specific_terms
            )
        )
        if embedding_similarity < 0.08 and lexical_score <= 0:
            continue
        if specific_terms and not has_specific_term:
            continue
        reasons = [
            f"{EMBEDDING_MODEL_ID} cosine similarity {embedding_similarity:.3f}",
        ]
        reasons.extend(lexical_reasons)
        confidence = max(0.05, min(0.92, 0.22 + max(embedding_similarity, 0.0) * 0.55 + min(lexical_score, 20) / 80))
        matches.append(
            {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "type": record["type"],
                "score": round(blended_score, 3),
                "embedding_similarity": round(embedding_similarity, 4),
                "lexical_score": round(lexical_score, 2),
                "confidence": round(confidence, 2),
                "reasons": sorted(set(reasons))[:10],
                "evidence": evidence_snippet(record, query),
                "summary": record.get("summary", ""),
                "document_class": (record.get("metadata") or {}).get("document_class"),
                "entities": (record.get("metadata") or {}).get("entities", {}),
                "photo": (record.get("metadata") or {}).get("photo", {}),
                "source": EMBEDDING_MODEL_ID,
                "embedding_source_preview": (row["embedding_source_text"] or "")[:240],
            }
        )
    matches.sort(key=lambda item: (item["score"], item["embedding_similarity"], item["relative_path"]), reverse=True)
    return matches[:limit]


def _query_years(query: str) -> set[int]:
    q = query.lower()
    years = {int(value) for value in re.findall(r"\b(19\d{2}|20\d{2})\b", q)}
    if "\u53bb\u5e74" in q or "last year" in q:
        years.add(datetime.now().year - 1)
    return years


def _dominant_white_hint(image_metadata: dict) -> bool:
    mean_rgb = image_metadata.get("mean_rgb") or []
    if len(mean_rgb) != 3:
        return False
    return min(mean_rgb) >= 0.68 and (max(mean_rgb) - min(mean_rgb)) <= 0.18


COLOR_INTENT_TERMS = {"white", "black", "red", "blue", "green", "yellow", "gray", "grey"}
CLOTHING_INTENT_TERMS = {"clothing", "upper_clothing", "top", "shirt"}


def _caption_text_matches_intent(caption_text: str, intent: str) -> bool:
    if not caption_text:
        return False
    aliases = [intent]
    aliases.extend(SEMANTIC_ALIASES.get(intent, []))
    if intent == "grey":
        aliases.extend(SEMANTIC_ALIASES.get("gray", []))
    for alias in aliases:
        needle = str(alias or "").lower().strip()
        if needle and needle in caption_text:
            return True
    return False


def _query_requires_clothing_caption(query: str, terms: set[str]) -> bool:
    q = str(query or "").lower()
    return bool(CLOTHING_INTENT_TERMS & terms or {"wearing"} & terms or "\u4e0a\u8863" in q or "\u8863\u670d" in q or "\u7a7f" in q)


def _caption_matches_clothing_query(caption_text: str, terms: set[str]) -> bool:
    if not caption_text:
        return False
    negated = any(
        phrase in caption_text
        for phrase in [
            "no person", "no people", "no human", "no visible person", "no visible people",
            "no clothing", "no clothes", "no visible clothing", "without a person", "without people",
        ]
    )
    explicit_wearing = any(phrase in caption_text for phrase in ["wearing", "wears", "dressed in", "upper_color", "upper_garment"])
    if negated and not explicit_wearing:
        return False
    has_clothing = any(_caption_text_matches_intent(caption_text, term) for term in CLOTHING_INTENT_TERMS)
    has_clothing = has_clothing or any(
        needle in caption_text
        for needle in ["upper_color", "upper_garment", "garment", "apparel", "jacket", "hoodie", "sweater", "blouse"]
    )
    requested_colors = (COLOR_INTENT_TERMS & terms) or ({"gray"} if "grey" in terms else set())
    has_requested_color = True
    if requested_colors:
        has_requested_color = any(_caption_text_matches_intent(caption_text, color) for color in requested_colors)
    return bool(has_clothing and has_requested_color)


def search_photo_semantic_index(db_path: Path, query: str, limit: int = 10) -> list[dict]:
    photo_exts = tuple(sorted(PHOTO_EXTS))
    placeholders = ",".join("?" for _ in photo_exts)
    con = open_index_db(db_path)
    rows = []
    try:
        for row in con.execute(
            f"""
            SELECT
                records.*,
                image_embeddings.status AS image_embedding_status,
                image_embeddings.engine AS image_embedding_engine,
                image_embeddings.metadata_json AS image_embedding_metadata_json,
                image_captions.status AS image_caption_status,
                image_captions.provider AS image_caption_provider,
                image_captions.model_id AS image_caption_model_id,
                image_captions.caption AS image_caption,
                image_captions.structured_json AS image_caption_structured_json,
                image_captions.search_text AS image_caption_search_text,
                image_captions.error AS image_caption_error,
                ocr_results.status AS ocr_status,
                ocr_results.engine AS ocr_engine,
                ocr_results.text_preview AS ocr_text_preview,
                ocr_results.error AS ocr_error
            FROM records
            LEFT JOIN image_embeddings
              ON image_embeddings.path = records.path
             AND image_embeddings.model_id = ?
             AND image_embeddings.dim = ?
            LEFT JOIN image_captions
              ON image_captions.path = records.path
             AND image_captions.schema_version = ?
            LEFT JOIN ocr_results
              ON ocr_results.path = records.path
            WHERE records.type = 'Photos'
              AND lower(records.extension) IN ({placeholders})
            """,
            (IMAGE_EMBEDDING_MODEL_ID, IMAGE_EMBEDDING_DIM, IMAGE_CAPTION_SCHEMA_VERSION, *photo_exts),
        ):
            rows.append(row)
    finally:
        con.close()

    terms = expand_query_terms(query)
    term_set = set(terms)
    requested_intents = sorted(set(terms) & PHOTO_INTENT_TERMS)
    requested_years = _query_years(query)
    requires_clothing_caption = _query_requires_clothing_caption(query, term_set)
    significant_terms = {
        term for term in terms
        if term not in GENERIC_SEARCH_TERMS and term != "recent" and len(term) >= 2
    }
    matches = []
    for row in rows:
        record = _record_from_sqlite_row(row)
        metadata = record.get("metadata") or {}
        photo = metadata.get("photo") or {}
        labels = set(photo.get("labels") or [])
        image_metadata = {}
        if row["image_embedding_metadata_json"]:
            try:
                image_metadata = json.loads(row["image_embedding_metadata_json"])
            except json.JSONDecodeError:
                image_metadata = {}
        caption_structured = {}
        if row["image_caption_structured_json"]:
            try:
                loaded = json.loads(row["image_caption_structured_json"])
                caption_structured = loaded if isinstance(loaded, dict) else {}
            except json.JSONDecodeError:
                caption_structured = {}
        caption_text = " ".join(
            [
                str(row["image_caption"] or ""),
                str(row["image_caption_search_text"] or ""),
                str(caption_structured.get("search_text") or ""),
            ]
        ).lower()
        caption_completed = row["image_caption_status"] == IMAGE_CAPTION_STATUS_COMPLETED
        caption_clothing_match = caption_completed and _caption_matches_clothing_query(caption_text, term_set)
        if requires_clothing_caption and not caption_clothing_match:
            continue
        searchable = " ".join(
            [
                record.get("name", ""),
                record.get("relative_path", ""),
                " ".join(record.get("tags", [])),
                " ".join(record.get("keywords", [])),
                " ".join(labels),
                str(row["image_caption"] or ""),
                str(row["image_caption_search_text"] or ""),
                str(photo.get("taken_at") or ""),
                str(row["ocr_text_preview"] or ""),
                str(row["ocr_status"] or ""),
            ]
        ).lower()
        score = 0.0
        reasons: list[str] = []
        matched_intents: list[str] = []
        missing_intents: list[str] = []
        caption_used = False

        if caption_completed:
            if caption_clothing_match:
                score += 12.0
                caption_used = True
                matched_intents.extend(sorted((CLOTHING_INTENT_TERMS | COLOR_INTENT_TERMS) & term_set))
                reasons.append("LLM vision caption matches requested clothing/color evidence")
            for intent in requested_intents:
                if intent in matched_intents:
                    continue
                if _caption_text_matches_intent(caption_text, intent):
                    score += 7.0 if intent in (CLOTHING_INTENT_TERMS | COLOR_INTENT_TERMS | {"person", "people", "wearing"}) else 5.0
                    matched_intents.append(intent)
                    caption_used = True
                    reasons.append(f"LLM vision caption matches `{intent}`")

        for intent in requested_intents:
            if intent in matched_intents:
                continue
            if intent in labels:
                score += 6.0
                matched_intents.append(intent)
                reasons.append(f"photo label matches `{intent}`")
                if intent == "child":
                    reasons.append("child/person label comes from path or metadata only; face recognition is not performed")
            elif intent == "white" and _dominant_white_hint(image_metadata) and not requires_clothing_caption:
                score += 3.0
                matched_intents.append(intent)
                reasons.append("local visual embedding suggests dominant light/white tones")
            elif intent in {"invoice", "screenshot"} and row["ocr_status"]:
                score += 2.0
                matched_intents.append(intent)
                reasons.append(f"OCR status exists for requested `{intent}` evidence: {row['ocr_status']}")
            else:
                missing_intents.append(intent)

        for year in requested_years:
            if record.get("year") == year or str(year) in str(photo.get("taken_at") or ""):
                score += 4.0
                reasons.append(f"year matches `{year}`")

        for term in significant_terms:
            if term in searchable:
                score += 2.0
                reasons.append(f"metadata/path/OCR text matches `{term}`")

        if row["image_embedding_status"] == "local_visual_embedding_completed":
            score += 0.5
            reasons.append(f"{IMAGE_EMBEDDING_MODEL_ID} row available")
        if caption_completed:
            score += 1.0
            reasons.append("LLM vision caption row available")

        if "child" in missing_intents:
            reasons.append("child/person intent is not verified without face/person model")
        if requires_clothing_caption and not caption_used:
            reasons.append("clothing/person visual query requires LLM caption evidence")
        if any(intent in missing_intents for intent in ("beach", "meal", "car", "invoice", "screenshot")):
            reasons.append("some requested visual concepts need CLIP/OCR evidence for stronger confidence")

        if requested_intents and not matched_intents and score < 3.0:
            continue
        if not requested_intents and significant_terms and score <= 0:
            continue
        if score <= 0:
            continue

        missing_penalty = min(0.25, 0.06 * len(missing_intents))
        confidence = max(0.08, min(0.88, 0.28 + score / 26 - missing_penalty))
        evidence_bits = []
        if photo.get("labels"):
            evidence_bits.append("labels: " + ", ".join(photo["labels"]))
        if photo.get("taken_at"):
            evidence_bits.append("taken_at: " + str(photo["taken_at"]))
        if photo.get("gps"):
            gps = photo["gps"]
            evidence_bits.append(f"gps: {gps.get('latitude')},{gps.get('longitude')}")
        if photo.get("width") and photo.get("height"):
            evidence_bits.append(f"size: {photo['width']}x{photo['height']}")
        if image_metadata.get("mean_rgb"):
            evidence_bits.append(f"mean_rgb: {image_metadata['mean_rgb']}")
        if row["image_caption"]:
            evidence_bits.append("caption: " + str(row["image_caption"])[:220])
        if row["ocr_status"]:
            evidence_bits.append(f"ocr_status: {row['ocr_status']}")
        visual_source = "sqlite_photo_llm_caption_semantic_search" if caption_used else "sqlite_photo_metadata_local_visual_embedding"
        matches.append(
            {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "type": record["type"],
                "score": round(score, 3),
                "confidence": round(confidence, 2),
                "matched_intents": sorted(set(matched_intents)),
                "missing_intents": sorted(set(missing_intents)),
                "reasons": sorted(set(reasons))[:12],
                "evidence": "; ".join(evidence_bits)[:360] if evidence_bits else evidence_snippet(record, query),
                "summary": record.get("summary", ""),
                "photo": photo,
                "image_embedding": {
                    "model_id": IMAGE_EMBEDDING_MODEL_ID,
                    "status": row["image_embedding_status"],
                    "engine": row["image_embedding_engine"],
                    "metadata": image_metadata,
                    "production_clip_or_transformer": False,
                },
                "image_caption": {
                    "schema_version": IMAGE_CAPTION_SCHEMA_VERSION,
                    "status": row["image_caption_status"],
                    "provider": row["image_caption_provider"],
                    "model_id": row["image_caption_model_id"],
                    "caption": row["image_caption"] or "",
                    "structured": caption_structured,
                    "error": row["image_caption_error"],
                },
                "privacy": {
                    "face_recognition_performed": False,
                    "person_identity_verified": False,
                    "person_or_child_terms_source": "llm_caption_generic_person_only" if caption_used else "path_metadata_labels_only",
                    "requires_privacy_review_before_face_model": True,
                    "limitations": [
                        "No face embedding, face clustering, or identity matching is performed.",
                        "Child/person terms are generic visual descriptions only unless separately authorized.",
                        "Person identity claims must stay unverified until a separate privacy and compliance review approves a face model.",
                    ],
                },
                "ocr": {
                    "status": row["ocr_status"],
                    "engine": row["ocr_engine"],
                    "text_preview": row["ocr_text_preview"],
                    "error": row["ocr_error"],
                },
                "source": visual_source,
            }
        )
    matches.sort(key=lambda item: (item["score"], item["confidence"], item["relative_path"]), reverse=True)
    return matches[:limit]


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


def hamming_distance_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def similar_photo_groups(records: list[dict], max_distance: int = 8) -> list[dict]:
    photos = []
    for record in records:
        photo = (record.get("metadata") or {}).get("photo") or {}
        phash = photo.get("phash")
        if record.get("type") == "Photos" and phash:
            photos.append((record, phash))

    parent = list(range(len(photos)))

    def find(idx: int) -> int:
        while parent[idx] != idx:
            parent[idx] = parent[parent[idx]]
            idx = parent[idx]
        return idx

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    edges = []
    for left in range(len(photos)):
        for right in range(left + 1, len(photos)):
            distance = hamming_distance_hex(photos[left][1], photos[right][1])
            if distance <= max_distance:
                union(left, right)
                edges.append(
                    {
                        "left": photos[left][0]["relative_path"],
                        "right": photos[right][0]["relative_path"],
                        "phash_distance": distance,
                    }
                )

    grouped: dict[int, list[dict]] = defaultdict(list)
    for idx, (record, phash) in enumerate(photos):
        grouped[find(idx)].append(
            {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "sha256": record["sha256"],
                "phash": phash,
                "labels": ((record.get("metadata") or {}).get("photo") or {}).get("labels", []),
            }
        )

    groups = []
    for items in grouped.values():
        if len(items) <= 1:
            continue
        group_edges = [
            edge
            for edge in edges
            if any(item["relative_path"] == edge["left"] for item in items)
            and any(item["relative_path"] == edge["right"] for item in items)
        ]
        groups.append({"count": len(items), "files": items, "edges": group_edges})
    return sorted(groups, key=lambda group: group["count"], reverse=True)


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
