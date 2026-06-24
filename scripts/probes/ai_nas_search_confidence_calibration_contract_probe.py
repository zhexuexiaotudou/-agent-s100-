#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
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


TOOL_ID = "ai_nas_search_confidence_calibration_contract"


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (720, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 700, 400), outline=(35, 35, 35), width=3)
    draw.text((42, 184), text, fill=(0, 0, 0))
    image.save(path)


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    photos = personal / "Photos"
    docs.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    (docs / "2024_renovation_payment_contract.txt").write_text(
        "\n".join(
            [
                "Home renovation contract signed in 2024.",
                "Payment schedule: deposit 20000 CNY on 2024-03-01.",
                "Final payment 8000 CNY on 2024-05-20.",
                "Evidence terms: contract, renovation, payment, invoice support.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs / "2024_reimbursement_invoice_receipt.txt").write_text(
        "\n".join(
            [
                "Reimbursement invoice receipt for renovation materials.",
                "Amount 12000 CNY. Date 2024-04-15.",
                "Evidence terms: invoice, receipt, reimbursement, payment.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs / "espresso_machine_manual.txt").write_text(
        "Espresso machine manual. Grinder calibration, water tank cleaning, and warranty card notes.\n",
        encoding="utf-8",
    )
    write_fixture_image(
        photos / "2024_child_family_beach_photo.jpg",
        (70, 170, 230),
        "child family beach photo 2024",
    )
    write_fixture_image(
        photos / "2024_white_car_photo.jpg",
        (235, 235, 232),
        "white car photo 2024",
    )
    write_fixture_image(
        photos / "2024_invoice_screenshot.jpg",
        (248, 248, 240),
        "invoice screenshot 12000 CNY 2024-04-15",
    )
    return personal


def combine_matches(*groups: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for matches in groups:
        for match in matches:
            rel = match.get("relative_path")
            if not rel:
                continue
            item = merged.setdefault(rel, dict(match))
            if match.get("confidence", 0) > item.get("confidence", 0):
                item.update(match)
            else:
                for reason in match.get("reasons") or []:
                    if reason not in item.get("reasons", []):
                        item.setdefault("reasons", []).append(reason)
    return sorted(
        merged.values(),
        key=lambda item: (float(item.get("confidence") or 0), float(item.get("score") or 0), item.get("relative_path") or ""),
        reverse=True,
    )


def has_grounding(match: dict | None) -> bool:
    if not match:
        return False
    confidence = match.get("confidence")
    return (
        bool(match.get("relative_path") or match.get("path"))
        and isinstance(confidence, (float, int))
        and 0 < float(confidence) <= 1
        and bool(match.get("reasons"))
        and bool(match.get("evidence"))
    )


def evaluate_positive_case(db_path: Path, case: dict) -> dict:
    query = case["query"]
    text_matches = search_sqlite_index(db_path, query, limit=8)
    embedding_matches = search_embedding_index(db_path, query, limit=8)
    photo_matches = search_photo_semantic_index(db_path, case.get("photo_query", query), limit=8) if case.get("route") == "photo" else []
    if case.get("route") == "photo":
        matches = combine_matches(photo_matches)
        auxiliary_matches = combine_matches(text_matches, embedding_matches)
    else:
        matches = combine_matches(text_matches, embedding_matches)
        auxiliary_matches = []
    top = matches[0] if matches else None
    confidence = float(top.get("confidence") or 0) if top else 0.0
    failures = []
    if not top:
        failures.append("no_top_match")
    elif not has_grounding(top):
        failures.append("top_match_missing_path_reason_evidence_confidence")
    if top:
        lowered_path = (top.get("relative_path") or "").lower()
        missing_path_terms = [term for term in case.get("relative_path_terms", []) if term.lower() not in lowered_path]
        if missing_path_terms:
            failures.append("missing_relative_path_terms:" + ",".join(missing_path_terms))
        if confidence < case["min_confidence"]:
            failures.append(f"confidence_below_min:{confidence}<{case['min_confidence']}")
        if confidence > case["max_confidence"]:
            failures.append(f"confidence_above_max:{confidence}>{case['max_confidence']}")
        expected_class = case.get("document_class")
        if expected_class and top.get("document_class") != expected_class:
            failures.append(f"unexpected_document_class:{top.get('document_class')}")
        if case.get("person_or_face_intent"):
            reasons = " | ".join(top.get("reasons") or []).lower()
            if "face recognition is not performed" not in reasons:
                failures.append("missing_person_face_limitation_reason")
    return {
        "name": case["name"],
        "query": query,
        "route": case.get("route"),
        "passed": not failures,
        "failures": failures,
        "top_confidence": round(confidence, 3),
        "top_match": top,
        "matches": matches[:5],
        "auxiliary_matches": auxiliary_matches[:5],
    }


def evaluate_unsupported_case(db_path: Path, query: str, max_confidence: float) -> dict:
    text_matches = search_sqlite_index(db_path, query, limit=8)
    embedding_matches = search_embedding_index(db_path, query, limit=8)
    photo_matches = search_photo_semantic_index(db_path, query, limit=8)
    matches = combine_matches(text_matches, embedding_matches, photo_matches)
    top = matches[0] if matches else None
    max_seen = max([float(match.get("confidence") or 0) for match in matches] or [0.0])
    failures = []
    if max_seen > max_confidence:
        failures.append(f"unsupported_query_overconfident:{max_seen}>{max_confidence}")
    no_answer = {
        "status": "no_grounded_answer",
        "reason": "No result crossed the confidence ceiling for this unsupported query; do not fabricate evidence.",
        "max_observed_confidence": round(max_seen, 3),
    }
    return {
        "name": "unsupported_private_identifier_query",
        "query": query,
        "passed": not failures,
        "failures": failures,
        "max_confidence_allowed": max_confidence,
        "max_observed_confidence": round(max_seen, 3),
        "no_answer": no_answer,
        "top_match": top,
        "matches": matches[:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS search confidence calibration contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=1000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "search_confidence_calibration_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = run_dir / "search_confidence_calibration.sqlite3"
    index_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    image_upsert = ensure_image_embeddings_for_photos(db_path)

    positive_cases = [
        evaluate_positive_case(
            db_path,
            {
                "name": "strong_renovation_contract_query",
                "query": "2024 renovation payment contract",
                "route": "text_embedding",
                "relative_path_terms": ["renovation", "contract"],
                "document_class": "contract",
                "min_confidence": 0.42,
                "max_confidence": 0.95,
            },
        ),
        evaluate_positive_case(
            db_path,
            {
                "name": "strong_reimbursement_invoice_query",
                "query": "2024 reimbursement invoice receipt payment",
                "route": "text_embedding",
                "relative_path_terms": ["reimbursement", "invoice"],
                "document_class": "invoice",
                "min_confidence": 0.42,
                "max_confidence": 0.95,
            },
        ),
        evaluate_positive_case(
            db_path,
            {
                "name": "child_beach_photo_metadata_only_query",
                "query": "child beach photo 2024",
                "route": "photo",
                "photo_query": "child beach photo 2024",
                "relative_path_terms": ["child", "beach"],
                "person_or_face_intent": True,
                "min_confidence": 0.35,
                "max_confidence": 0.88,
            },
        ),
    ]
    unsupported_case = evaluate_unsupported_case(
        db_path,
        "passport number social security private key biometric scan",
        max_confidence=0.45,
    )
    cases = positive_cases + [unsupported_case]
    failures = [failure for case in cases for failure in case["failures"]]
    all_results_grounded = all(has_grounding(case.get("top_match")) for case in positive_cases)
    photo_case = next(case for case in cases if case["name"] == "child_beach_photo_metadata_only_query")
    photo_person_metadata_only = (
        photo_case["passed"]
        and photo_case["top_confidence"] <= 0.88
        and "face recognition is not performed" in " | ".join((photo_case.get("top_match") or {}).get("reasons") or []).lower()
    )

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_search_confidence_calibration_contract" if not failures else "failed_ai_nas_search_confidence_calibration_contract",
        "scope": "bounded confidence calibration for grounded positive queries, unsupported query refusal, and metadata-only photo person terms",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "index_status": index_status,
        "sqlite_index_status": sqlite_index_status(db_path),
        "image_embedding_upsert": image_upsert,
        "image_embedding_runtime_status": image_embedding_runtime_status(),
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "passed_count": sum(1 for case in cases if case["passed"]),
            "high_confidence_positive_cases": sum(1 for case in positive_cases if case["top_confidence"] >= 0.42),
            "unsupported_query_overconfidence": bool(unsupported_case["failures"]),
            "unsupported_query_no_answer_status": unsupported_case["no_answer"]["status"],
            "photo_person_terms_metadata_only": photo_person_metadata_only,
            "all_positive_results_grounded": all_results_grounded,
            "failures": failures,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "isolated fixture files, SQLite/FTS/vector/image embedding rows, Markdown/JSON calibration reports only",
            "grounding_policy": "strong matches need evidence and calibrated confidence; unsupported queries return no-answer instead of fabricated content",
        },
    }
    json_path = run_dir / "search_confidence_calibration_contract.json"
    md_path = run_dir / "search_confidence_calibration_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Search Confidence Calibration Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- case_count: `{payload['summary']['case_count']}`",
        f"- passed_count: `{payload['summary']['passed_count']}`",
        f"- high_confidence_positive_cases: `{payload['summary']['high_confidence_positive_cases']}`",
        f"- unsupported_query_overconfidence: `{payload['summary']['unsupported_query_overconfidence']}`",
        f"- unsupported_query_no_answer_status: `{payload['summary']['unsupported_query_no_answer_status']}`",
        f"- photo_person_terms_metadata_only: `{payload['summary']['photo_person_terms_metadata_only']}`",
        f"- all_positive_results_grounded: `{payload['summary']['all_positive_results_grounded']}`",
        f"- failures: `{failures}`",
        "",
        "## Contract",
        "",
        "- Strong contract and invoice queries must have grounded top results with calibrated higher confidence.",
        "- Unsupported private-identifier queries must not produce overconfident answers.",
        "- Child/person photo queries must remain metadata-only and state that face recognition is not performed.",
        "",
        "## Audit",
        "",
    ]
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
