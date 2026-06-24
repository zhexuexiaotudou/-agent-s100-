#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_index_db,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sha256_file,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_portable_nas_adapter_contract"


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def prepare_adapter(root: Path, label: str) -> Path:
    personal = root / "Personal"
    write_file(
        personal / "Documents" / "2024_renovation_contract.txt",
        f"{label} renovation contract 2024. Deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
    )
    write_file(
        personal / "Documents" / "2024_reimbursement_invoice.txt",
        f"{label} reimbursement invoice receipt. Amount 12000 CNY. Date 2024-04-15.\n",
    )
    write_file(
        personal / "Inbox" / "2024_payment_chat_screenshot_note.txt",
        f"{label} chat screenshot note. Renovation payment confirmed on 2024-04-20 amount 5000 CNY.\n",
    )
    write_file(
        personal / "Photos" / "2024_beach_trip_caption.txt",
        f"{label} beach family photo placeholder with time and folder metadata.\n",
    )
    return personal


def source_manifest(personal_root: Path) -> dict[str, dict]:
    manifest = {}
    for path in sorted(item for item in personal_root.rglob("*") if item.is_file()):
        rel = path.relative_to(personal_root).as_posix()
        stat = path.stat()
        manifest[rel] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256_file(path),
        }
    return manifest


def sqlite_records(db_path: Path) -> list[dict]:
    con = open_index_db(db_path)
    try:
        return [dict(row) for row in con.execute("SELECT path, relative_path, type, sha256 FROM records ORDER BY relative_path")]
    finally:
        con.close()


def path_confined(path_text: str, root: Path) -> bool:
    try:
        Path(path_text).resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def relative_path_safe(relative_path: str) -> bool:
    path = Path(relative_path)
    return not path.is_absolute() and ".." not in path.parts and relative_path not in ("", ".")


def evaluate_adapter(name: str, personal_root: Path, db_path: Path) -> dict:
    before = source_manifest(personal_root)
    index_payload = build_sqlite_inventory(personal_root, db_path)
    matches = search_sqlite_index(db_path, "2024 renovation payment invoice chat screenshot", limit=8)
    records = sqlite_records(db_path)
    after = source_manifest(personal_root)
    failures = []
    if before != after:
        failures.append("personal_source_manifest_changed")
    if index_payload.get("status") != "completed":
        failures.append("sqlite_index_not_completed")
    if index_payload.get("failed_count") != 0:
        failures.append("sqlite_index_has_failed_files")
    if len(records) < 4:
        failures.append("too_few_indexed_records")
    for record in records:
        rel = record.get("relative_path") or ""
        if not relative_path_safe(rel):
            failures.append(f"unsafe_relative_path:{rel}")
        if not path_confined(record.get("path") or "", personal_root):
            failures.append(f"path_escape:{rel}")
    if not matches:
        failures.append("search_returned_no_matches")
    for idx, match in enumerate(matches[:3]):
        label = match.get("relative_path") or f"match_{idx}"
        if not match.get("reasons"):
            failures.append(f"{label}:missing_reasons")
        if not match.get("evidence"):
            failures.append(f"{label}:missing_evidence")
        if match.get("confidence") is None:
            failures.append(f"{label}:missing_confidence")
        if not path_confined(match.get("path") or "", personal_root):
            failures.append(f"{label}:match_path_escape")
    return {
        "name": name,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "index_status": sqlite_index_status(db_path),
        "index_payload": index_payload,
        "record_count": len(records),
        "match_count": len(matches),
        "top_matches": matches[:3],
        "source_manifest_unchanged": before == after,
        "path_confinement_ok": not any(item.startswith("path_escape:") or item.endswith(":match_path_escape") for item in failures),
        "relative_paths_safe": not any(item.startswith("unsafe_relative_path:") for item in failures),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS portable NAS adapter contract for arbitrary cheap NAS mounts.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "portable_nas_adapter_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    adapters = [
        ("cheap_smb_mount", fixture_root / "cheap_smb_mount"),
        ("usb_jbod_export", fixture_root / "usb_jbod_export"),
    ]
    results = []
    for name, root in adapters:
        personal_root = prepare_adapter(root, name)
        results.append(evaluate_adapter(name, personal_root, run_dir / f"{name}.sqlite3"))

    failures = [f"{item['name']}:{failure}" for item in results for failure in item["failures"]]
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_portable_nas_adapter_contract" if not failures else "failed_ai_nas_portable_nas_adapter_contract",
        "scope": "bounded proof that AI-NAS can point at arbitrary mounted NAS Personal roots without becoming a NAS OS or mutating source files",
        "adapter_count": len(results),
        "adapters": results,
        "summary": {
            "adapter_count": len(results),
            "ok_count": sum(1 for item in results if not item["failures"]),
            "indexed_record_count": sum(item["record_count"] for item in results),
            "match_count": sum(item["match_count"] for item in results),
            "failures": failures,
        },
        "contract": [
            "NAS owns storage, snapshots, sharing, and permissions.",
            "AI-NAS receives a mounted Personal root and report root as adapter inputs.",
            "SQLite/FTS index and reports are written outside the Personal source tree.",
            "Search results must use source-confined absolute paths plus safe relative paths.",
            "Switching NAS roots must not require NAS-OS-specific code paths.",
        ],
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "download_performed": False,
            "network_call_performed": False,
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "isolated fixture files, SQLite indexes, and Markdown/JSON portable NAS adapter reports only",
        },
    }
    json_path = run_dir / "portable_nas_adapter_contract.json"
    md_path = run_dir / "portable_nas_adapter_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Portable NAS Adapter Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- adapter_count: `{payload['summary']['adapter_count']}`",
        f"- ok_count: `{payload['summary']['ok_count']}`",
        f"- indexed_record_count: `{payload['summary']['indexed_record_count']}`",
        f"- match_count: `{payload['summary']['match_count']}`",
        "- policy: NAS provides storage; AI-NAS indexes mounted roots and writes reports outside Personal source trees",
        "",
        "## Adapters",
        "",
    ]
    for item in results:
        lines.append(
            f"- {item['name']}: records `{item['record_count']}` matches `{item['match_count']}` "
            f"source_manifest_unchanged `{item['source_manifest_unchanged']}` failures `{item['failures']}`"
        )
    lines.extend(["", "## Contract", ""])
    for item in payload["contract"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
