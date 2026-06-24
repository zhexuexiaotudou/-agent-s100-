#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    image_embedding_runtime_status,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    search_photo_semantic_index,
    search_sqlite_index,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_semantic_query_acceptance"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def copy_or_make_image(source: Path, target: Path, fallback_text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, target)
        return
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (320, 180), color=(235, 240, 245))
        draw = ImageDraw.Draw(image)
        draw.text((12, 80), fallback_text[:42], fill=(20, 30, 40))
        image.save(target)
    except Exception:
        target.write_bytes((fallback_text + "\n").encode("utf-8"))


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "semantic_fixture" / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    documents = personal / "Documents"
    photos = personal / "Photos"
    documents.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)

    last_year = datetime.now().year - 1
    (documents / f"{last_year}_home_renovation_contract.txt").write_text(
        "\n".join(
            [
                f"{last_year} home renovation contract.",
                "Chinese query hints: 去年 装修 合同.",
                "Payment nodes: deposit 20000 CNY on 2025-03-01; final payment 8000 CNY on 2025-05-20.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (documents / f"{last_year}_reimbursement_invoice.txt").write_text(
        "\n".join(
            [
                f"{last_year} reimbursement invoice for renovation materials.",
                "Chinese query hints: 报销 发票 票据.",
                "Amount: 12000 CNY. Date: 2025-04-15.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    fixture = repo_root() / "tmp" / "embedding_fixture" / "Personal"
    copy_or_make_image(
        fixture / "Photos" / "2024_family_beach_photo.jpg",
        photos / f"{last_year}_child_family_beach_photo.jpg",
        "child family beach photo",
    )
    copy_or_make_image(
        fixture / "Photos" / "2024_invoice_screenshot.png",
        photos / f"{last_year}_reimbursement_invoice_screenshot.png",
        "reimbursement invoice screenshot",
    )
    copy_or_make_image(
        fixture / "Photos" / "2024_white_car_photo.jpg",
        photos / f"{last_year}_white_car_photo.jpg",
        "white car photo",
    )
    return personal


def merge_sources(text_matches: list[dict], embedding_matches: list[dict], photo_matches: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for source_name, matches in [
        ("sqlite_fts_metadata", text_matches),
        ("local_hash_embedding", embedding_matches),
        ("photo_semantic_local_visual", photo_matches),
    ]:
        for match in matches:
            item = merged.setdefault(
                match["relative_path"],
                {
                    "relative_path": match["relative_path"],
                    "path": match.get("path"),
                    "type": match.get("type"),
                    "document_class": match.get("document_class"),
                    "confidence": 0.0,
                    "score": 0.0,
                    "sources": [],
                    "reasons": [],
                    "evidence": [],
                    "entities": {},
                    "photo": {},
                    "matched_intents": [],
                    "missing_intents": [],
                },
            )
            item["confidence"] = max(float(item["confidence"]), float(match.get("confidence") or 0.0))
            item["score"] = max(float(item["score"]), float(match.get("score") or 0.0))
            if source_name not in item["sources"]:
                item["sources"].append(source_name)
            for reason in match.get("reasons") or []:
                if reason not in item["reasons"]:
                    item["reasons"].append(reason)
            evidence = match.get("evidence")
            if evidence and evidence not in item["evidence"]:
                item["evidence"].append(evidence)
            if match.get("entities"):
                item["entities"] = match["entities"]
            if match.get("photo"):
                item["photo"] = match["photo"]
            for intent in match.get("matched_intents") or []:
                if intent not in item["matched_intents"]:
                    item["matched_intents"].append(intent)
            for intent in match.get("missing_intents") or []:
                if intent not in item["missing_intents"]:
                    item["missing_intents"].append(intent)
            if not item.get("document_class") and match.get("document_class"):
                item["document_class"] = match["document_class"]
    results = list(merged.values())
    for item in results:
        item["confidence"] = round(float(item["confidence"]), 2)
        item["score"] = round(float(item["score"]), 3)
    return sorted(results, key=lambda item: (item["confidence"], item["score"], item["relative_path"]), reverse=True)


def evaluate_case(db_path: Path, query: str, expected: dict) -> dict:
    text_matches = search_sqlite_index(db_path, query, limit=8)
    embedding_matches = search_embedding_index(db_path, query, limit=8)
    photo_query = expected.get("photo_query") or query
    photo_matches = search_photo_semantic_index(db_path, photo_query, limit=8) if expected.get("route") == "photo" else []
    matches = merge_sources(text_matches, embedding_matches, photo_matches)
    top = matches[0] if matches else None
    failures = []
    if not top:
        failures.append("no_match")
    if top:
        if not top.get("reasons"):
            failures.append("missing_reasons")
        if not top.get("evidence"):
            failures.append("missing_evidence")
        if not isinstance(top.get("confidence"), (float, int)) or top["confidence"] <= 0:
            failures.append("missing_confidence")
        expected_class = expected.get("document_class")
        if expected_class and top.get("document_class") != expected_class:
            failures.append(f"expected_document_class:{expected_class}")
        required_labels = set(expected.get("photo_labels") or [])
        actual_labels = set((top.get("photo") or {}).get("labels") or [])
        if required_labels and not required_labels.issubset(actual_labels):
            failures.append("missing_photo_labels:" + ",".join(sorted(required_labels - actual_labels)))
        required_terms = expected.get("relative_path_terms") or []
        lowered_path = (top.get("relative_path") or "").lower()
        missing_terms = [term for term in required_terms if term.lower() not in lowered_path]
        if missing_terms:
            failures.append("missing_relative_path_terms:" + ",".join(missing_terms))
    limitations = []
    if expected.get("person_or_face_intent"):
        limitations.append("child/person evidence is path/label metadata only; face recognition is intentionally not used")
    if expected.get("route") == "photo" and not image_embedding_runtime_status()["production_clip_ready"]:
        limitations.append("production CLIP/image-semantic model is not available; local metadata/PIL visual fallback is used")
    return {
        "query": query,
        "expected": expected,
        "passed": not failures,
        "failures": failures,
        "top_match": top,
        "match_count": len(matches),
        "matches": matches[:5],
        "limitations": limitations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS semantic fuzzy-query acceptance over a bounded fixture.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--sqlite-index-path", type=Path, default=None)
    parser.add_argument("--use-existing-personal", action="store_true")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "semantic_query_acceptance")
    personal_root = args.personal_root if args.use_existing_personal and args.personal_root else prepare_fixture(run_dir)
    sqlite_index_path = args.sqlite_index_path or (run_dir / "semantic_query_acceptance.sqlite3")
    build_sqlite_inventory(personal_root, sqlite_index_path)
    image_upsert = ensure_image_embeddings_for_photos(sqlite_index_path)

    last_year = datetime.now().year - 1
    cases = [
        evaluate_case(
            sqlite_index_path,
            "我去年签的那个装修合同",
            {
                "route": "text_embedding",
                "document_class": "contract",
                "relative_path_terms": [str(last_year), "renovation", "contract"],
            },
        ),
        evaluate_case(
            sqlite_index_path,
            "找孩子海边照片",
            {
                "route": "photo",
                "photo_query": "child beach photo",
                "photo_labels": ["beach", "child"],
                "relative_path_terms": ["child", "beach"],
                "person_or_face_intent": True,
            },
        ),
        evaluate_case(
            sqlite_index_path,
            "找报销用的发票",
            {
                "route": "text_embedding",
                "document_class": "invoice",
                "relative_path_terms": ["reimbursement", "invoice"],
            },
        ),
    ]
    passed_count = sum(1 for case in cases if case["passed"])
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_semantic_query_acceptance" if passed_count == len(cases) else "failed_ai_nas_semantic_query_acceptance",
        "scope": "bounded fixture acceptance for fuzzy contract, photo, and invoice queries",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "index_status": sqlite_index_status(sqlite_index_path),
        "image_embedding_upsert": image_upsert,
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "passed_count": passed_count,
            "failed_count": len(cases) - passed_count,
            "all_results_have_reason_evidence_confidence": all(
                case["top_match"]
                and case["top_match"].get("reasons")
                and case["top_match"].get("evidence")
                and case["top_match"].get("confidence") is not None
                for case in cases
            ),
        },
        "audit": {
            "source_files_modified": False,
            "real_personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "bounded fixture files, SQLite/FTS/vector rows, and Markdown/JSON semantic acceptance reports",
            "grounding_policy": "acceptance requires each top result to include reasons, evidence, confidence, and explicit limitations for unsupported visual/person semantics",
        },
    }

    json_path = run_dir / "semantic_query_acceptance.json"
    md_path = run_dir / "semantic_query_acceptance.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Semantic Query Acceptance",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- passed_count: `{passed_count}` / `{len(cases)}`",
        f"- sqlite_index_path: `{sqlite_index_path}`",
        "- policy: bounded fixture/index/report only; no real Personal delete, move, or overwrite",
        "",
        "## Cases",
        "",
    ]
    for case in cases:
        top = case.get("top_match") or {}
        lines.append(f"- query `{case['query']}` passed `{case['passed']}` match_count `{case['match_count']}`")
        if top:
            lines.append(
                f"  - top: `{top.get('relative_path')}` confidence `{top.get('confidence')}` "
                f"sources `{', '.join(top.get('sources', []))}`"
            )
            lines.append(f"  - evidence: {' | '.join(top.get('evidence', [])[:2])}")
            lines.append(f"  - reasons: {', '.join(top.get('reasons', [])[:8])}")
        if case["failures"]:
            lines.append(f"  - failures: `{', '.join(case['failures'])}`")
        for limitation in case["limitations"]:
            lines.append(f"  - limitation: {limitation}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if passed_count == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
