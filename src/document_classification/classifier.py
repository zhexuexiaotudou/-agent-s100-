from __future__ import annotations

import re
from pathlib import Path
from typing import Callable


DOCUMENT_CATEGORIES = {
    "PDF文档": {"extensions": {".pdf"}},
    "Word文档": {"extensions": {".doc", ".docx", ".dotx", ".docm", ".rtf"}},
    "表格文档": {"extensions": {".xls", ".xlsx", ".xlsm", ".xltx", ".csv", ".tsv"}},
    "演示文稿": {"extensions": {".ppt", ".pptx", ".pptm", ".ppsx", ".key"}},
    "文本笔记": {"extensions": {".txt", ".md", ".markdown", ".rst", ".tex", ".log", ".ini", ".cfg", ".yaml", ".yml", ".json", ".xml", ".toml"}},
    "数据文件": {"extensions": {".db", ".sqlite", ".sql", ".parquet", ".feather", ".hdf5", ".npy", ".npz"}},
    "代码文件": {"extensions": {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".ps1", ".bat"}},
    "图片文档": {"extensions": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"}},
    "压缩包": {"extensions": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".zst"}},
    "聊天记录": {"extensions": {".eml", ".msg", ".pst", ".mbox", ".vcf", ".ics"}},
}

DOCUMENT_EXTENSIONS = {extension for category in DOCUMENT_CATEGORIES.values() for extension in category["extensions"]}
FILENAME_RULES = (
    (re.compile(r"合同|协议|合约|agreement|contract|报告|report|总结|summary|review|分析", re.I), "合同资料"),
    (re.compile(r"发票|invoice|receipt|流水|账单|财务|报销|税|budget|salary|工资|付款|payment", re.I), "财务票据"),
    (re.compile(r"微信|聊天|chat|wechat|message|邮件|email|mail|inbox", re.I), "聊天记录"),
    (re.compile(r"源码|source|源代码|code|project|module|组件|函数", re.I), "代码文件"),
    (re.compile(r"备份|backup|archive|压缩|打包|export|导出", re.I), "压缩包"),
    (re.compile(r"手册|manual|guide|说明|教程|tutorial|指南|规格|spec", re.I), "文本笔记"),
)


def classify_file(name: str, extension: str) -> list[str]:
    categories = [category for category, config in DOCUMENT_CATEGORIES.items() if extension.lower() in config["extensions"]]
    for pattern, category in FILENAME_RULES:
        if pattern.search(name) and category not in categories:
            categories.append(category)
    return categories or ["待整理"]


def classify_directory(
    personal_root: Path,
    relative_root: str,
    *,
    can_read: Callable[[str], bool],
    max_files: int = 5000,
) -> dict:
    personal = personal_root.resolve(strict=True)
    root = (personal / relative_root).resolve(strict=True)
    try:
        root.relative_to(personal)
    except ValueError:
        return {"ok": False, "error": "path_outside_personal_root"}
    if not root.is_dir():
        return {"ok": False, "error": "directory_not_found"}

    items: list[dict] = []
    counts: dict[str, int] = {}
    scanned = 0
    for path in root.rglob("*"):
        if scanned >= max_files:
            break
        try:
            if path.is_symlink() or not path.is_file():
                continue
            extension = path.suffix.lower()
            if extension not in DOCUMENT_EXTENSIONS:
                continue
            resolved = path.resolve(strict=True)
            relative_path = resolved.relative_to(personal).as_posix()
            if not can_read(relative_path):
                continue
            stat = resolved.stat()
        except (OSError, ValueError):
            continue
        scanned += 1
        categories = classify_file(path.name, extension)
        item = {
            "relative_path": relative_path,
            "name": path.name,
            "ext": extension,
            "size_bytes": int(stat.st_size),
            "mtime": float(stat.st_mtime),
            "categories": categories,
            "primary_category": categories[0],
        }
        items.append(item)
        for category in categories:
            counts[category] = counts.get(category, 0) + 1
    items.sort(key=lambda item: (-float(item["mtime"]), str(item["name"]).casefold()))
    return {
        "ok": True,
        "schema": "digua_document_classification_v1",
        "path": relative_root,
        "scanned": scanned,
        "total_items": len(items),
        "items": items,
        "category_counts": counts,
        "categories": {name: {"name": name} for name in counts},
        "virtual_only": True,
        "physical_file_moved": False,
        "raw_path_returned": False,
        "truncated": scanned >= max_files,
    }
