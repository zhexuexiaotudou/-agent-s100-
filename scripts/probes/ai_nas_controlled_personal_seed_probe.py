#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import DEFAULT_PERSONAL_ROOT, DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text, sha256_file


TOOL_ID = "ai_nas_controlled_personal_seed"


def safe_join(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    root_resolved = root.resolve()
    if root_resolved not in path.parents and path != root_resolved:
        raise ValueError(f"Refusing path outside personal root: {relative}")
    return path


def text_payload(kind: str, index: int, year: int) -> str:
    amount = 1200 + index * 37
    month = (index % 12) + 1
    day = (index % 27) + 1
    vendor = ["Northlake Renovation", "Harbor Dental", "Metro Travel", "Qingdao Hotel", "Family Storage"][index % 5]
    if kind == "contract":
        return (
            f"Renovation contract {year}-{index:03d}\n"
            f"Vendor: {vendor}\n"
            f"Payment schedule: {year}-{month:02d}-{day:02d} amount USD {amount}.00\n"
            "Scope: kitchen cabinet repair, living room paint, and invoice-backed material purchase.\n"
            "Evidence keywords: renovation contract payment receipt invoice chat screenshot.\n"
        )
    if kind == "invoice":
        return (
            f"Invoice {year}-{index:03d}\n"
            f"Vendor: {vendor}\n"
            f"Total: USD {amount}.00\n"
            f"Service date: {year}-{month:02d}-{day:02d}\n"
            "Category: reimbursement invoice receipt tax record.\n"
        )
    if kind == "chat":
        return (
            f"Chat screenshot transcript {year}-{index:03d}\n"
            f"Sender: contractor\n"
            f"Message: paid USD {amount}.00 on {year}-{month:02d}-{day:02d}; please match this to the invoice and receipt.\n"
            "Privacy: local-only family finance message.\n"
        )
    if kind == "travel":
        return (
            f"Travel packet {year}-{index:03d}\n"
            f"Hotel and flight receipt total USD {amount}.00\n"
            "Tags: travel hotel flight reimbursement itinerary.\n"
        )
    return (
        f"Family photo note {year}-{index:03d}\n"
        "Scene labels: beach child family meal white car invoice screenshot.\n"
        "Privacy: no face recognition, metadata and path labels only.\n"
    )


def maybe_write_text(path: Path, content: str, execute: bool, overwrite: bool) -> dict:
    existed = path.exists()
    action = "would_create"
    if existed and not overwrite:
        action = "skipped_exists"
    elif execute:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        action = "created" if not existed else "overwritten"
    digest = sha256_file(path) if execute and path.exists() else None
    return {"path": str(path), "action": action, "exists_before": existed, "sha256": digest}


def maybe_write_image(path: Path, label: str, execute: bool, overwrite: bool) -> dict:
    existed = path.exists()
    action = "would_create"
    if existed and not overwrite:
        action = "skipped_exists"
    elif execute:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image, ImageDraw

            image = Image.new("RGB", (960, 540), (232, 238, 232))
            draw = ImageDraw.Draw(image)
            draw.rectangle((36, 36, 924, 504), outline=(72, 88, 96), width=3)
            draw.text((64, 72), label, fill=(30, 41, 59))
            draw.text((64, 118), "AI-NAS controlled seed image", fill=(69, 84, 94))
            image.save(path, quality=88)
            action = "created" if not existed else "overwritten"
        except Exception as exc:
            action = f"image_create_failed:{type(exc).__name__}:{exc}"
    digest = sha256_file(path) if execute and path.exists() else None
    return {"path": str(path), "action": action, "exists_before": existed, "sha256": digest}


def build_file_plan(root: Path, count: int) -> list[tuple[str, Path, str]]:
    plan: list[tuple[str, Path, str]] = []
    kinds = ["contract", "invoice", "chat", "travel", "photo_note"]
    years = [2024, 2025, 2026]
    for index in range(count):
        kind = kinds[index % len(kinds)]
        year = years[index % len(years)]
        if kind == "contract":
            rel = f"Documents/Renovation/{year}/renovation_contract_{index:03d}.md"
        elif kind == "invoice":
            rel = f"Documents/Invoices/{year}/renovation_invoice_{index:03d}.txt"
        elif kind == "chat":
            rel = f"Inbox/ChatScreenshots/{year}/contractor_payment_chat_{index:03d}.txt"
        elif kind == "travel":
            rel = f"Documents/Travel/{year}/travel_receipt_{index:03d}.csv"
        else:
            rel = f"Photos/Family/{year}/beach_child_meal_white_car_note_{index:03d}.md"
        plan.append(("text", safe_join(root, rel), text_payload(kind, index, year)))
    movie_count = max(6, count // 20)
    for index in range(movie_count):
        plan.append(
            (
                "text",
                safe_join(root, f"Movies/Controlled/movie_crime_family_archive_{index:03d}.movie.txt"),
                f"Movie placeholder {index:03d}\nGenre: crime family archive\nCopy-only sorting fixture.\n",
            )
        )
    image_count = max(6, count // 18)
    for index in range(image_count):
        plan.append(
            (
                "image",
                safe_join(root, f"Photos/Family/2024/beach_child_invoice_screenshot_{index:03d}.jpg"),
                f"beach child invoice screenshot {index:03d}",
            )
        )
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a controlled Personal corpus for AI-NAS production-scale soak tests.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--file-count", type=int, default=140)
    parser.add_argument("--execute", action="store_true", help="Create the planned files. Without this flag, the probe is a dry run.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing controlled seed files.")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "controlled_personal_seed")
    root = args.personal_root
    plan = build_file_plan(root, max(1, args.file_count))
    actions = []
    for kind, path, content in plan:
        if kind == "image":
            actions.append(maybe_write_image(path, content, args.execute, args.overwrite))
        else:
            actions.append(maybe_write_text(path, content, args.execute, args.overwrite))

    created_count = sum(1 for item in actions if item["action"] in {"created", "overwritten"})
    skipped_count = sum(1 for item in actions if item["action"] == "skipped_exists")
    dry_run_count = sum(1 for item in actions if item["action"] == "would_create")
    failures = [item for item in actions if "failed" in str(item["action"])]
    blockers = []
    if not args.execute:
        blockers.append("dry_run_only_execute_not_set")
    if failures:
        blockers.append("seed_file_creation_failures_present")
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_controlled_personal_seed" if args.execute and not blockers else "limited_ai_nas_controlled_personal_seed",
        "scope": "controlled but realistic Personal corpus for NAS-backed production soak and portal demos",
        "personal_root": str(root),
        "config": {
            "file_count_requested": args.file_count,
            "execute": args.execute,
            "overwrite": args.overwrite,
        },
        "summary": {
            "planned_count": len(plan),
            "created_or_overwritten_count": created_count,
            "skipped_existing_count": skipped_count,
            "dry_run_count": dry_run_count,
            "failure_count": len(failures),
            "blockers": blockers,
        },
        "actions": actions,
        "audit": {
            "delete_performed": False,
            "move_performed": False,
            "rename_performed": False,
            "source_files_outside_personal_root_modified": False,
            "writes": "new controlled seed files under the configured Personal root when --execute is set",
        },
    }
    json_path = run_dir / "controlled_personal_seed.json"
    md_path = run_dir / "controlled_personal_seed.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Controlled Personal Seed",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- personal_root: `{root}`",
        f"- planned_count: `{len(plan)}`",
        f"- created_or_overwritten_count: `{created_count}`",
        f"- skipped_existing_count: `{skipped_count}`",
        f"- dry_run_count: `{dry_run_count}`",
        f"- blockers: `{blockers}`",
        "- policy: create-only controlled seed files; no delete, move, rename, or overwrite unless --overwrite is explicit",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if args.execute and not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
