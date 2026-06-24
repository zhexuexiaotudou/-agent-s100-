#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ai_nas_case_packet_probe import (
    build_case_answer,
    build_copy_suggestions,
    collect_payment_nodes,
    filter_case_matches,
    infer_gaps,
    merge_match,
)
from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    search_photo_semantic_index,
    search_sqlite_index,
    sqlite_index_status,
)
from ai_nas_folder_rag_probe import build_answer, collect_payment_nodes as collect_folder_payment_nodes
from ai_nas_folder_rag_probe import folder_query_matches, load_folder_records


TOOL_ID = "ai_nas_user_facing_tail_latency"
CASE_QUERY = "2024 renovation payment contract invoice receipt chat screenshot"
FOLDER_QUESTION = "What payment dates, amounts, and invoice evidence are in this folder?"
DEFAULT_P95_MS = 1000.0
DEFAULT_P99_MS = 1500.0


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 4)


def latency_summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "min_ms": round(min(values), 3) if values else None,
        "max_ms": round(max(values), 3) if values else None,
        "avg_ms": round(statistics.mean(values), 3) if values else None,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
    }


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (720, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 700, 400), outline=(40, 40, 40), width=3)
    draw.text((40, 180), text, fill=(0, 0, 0))
    image.save(path)


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    photos = personal / "Photos"
    inbox = personal / "Inbox"
    docs.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    (docs / "2024_renovation_contract.txt").write_text(
        "Renovation contract 2024. Payment deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    (docs / "2024_renovation_invoice_receipt.txt").write_text(
        "Invoice receipt for renovation reimbursement. Amount 12000 CNY. Date 2024-04-15. Receipt RCPT-2024-0415.\n",
        encoding="utf-8",
    )
    (docs / "local_ai_nas_notes.txt").write_text(
        "Local AI NAS note about SQLite FTS, vector search, P95 P99 latency, and queue backpressure.\n",
        encoding="utf-8",
    )
    (inbox / "2024_payment_chat_note.txt").write_text(
        "Chat screenshot note: renovation payment receipt discussed on 2024-04-20, amount 5000 CNY.\n",
        encoding="utf-8",
    )
    write_fixture_image(
        photos / "2024_renovation_chat_invoice_screenshot.jpg",
        (245, 245, 238),
        "chat screenshot invoice paid 5000 CNY 2024-04-20",
    )
    write_fixture_image(photos / "2024_family_beach_meal_photo.jpg", (80, 170, 230), "family beach meal photo 2024")
    write_fixture_image(photos / "2024_white_car_photo.jpg", (245, 245, 245), "white car 2024")
    return personal


def grounded_matches(matches: list[dict]) -> tuple[bool, list[str]]:
    failures = []
    if not matches:
        failures.append("no_matches")
        return False, failures
    for idx, match in enumerate(matches[:5]):
        label = match.get("relative_path") or match.get("path") or f"match_{idx}"
        if not (match.get("path") or match.get("relative_path")):
            failures.append(f"{label}:missing_path")
        if not match.get("reasons"):
            failures.append(f"{label}:missing_reasons")
        if not (match.get("evidence") or match.get("evidence_fragments")):
            failures.append(f"{label}:missing_evidence")
        if match.get("confidence") is None:
            failures.append(f"{label}:missing_confidence")
    return not failures, failures


def case_packet(db_path: Path, query: str, limit: int) -> dict:
    merged: dict[str, dict] = {}
    for match in search_sqlite_index(db_path, query, limit):
        merge_match(merged, match, "sqlite_text_fts_metadata")
    for match in search_embedding_index(db_path, query, limit):
        merge_match(merged, match, "local_hash_embedding")
    for match in search_photo_semantic_index(db_path, f"{query} invoice screenshot receipt", limit):
        merge_match(merged, match, "photo_semantic_local_visual")
    candidates = sorted(
        merged.values(),
        key=lambda item: (item["confidence"], item["score"], item["relative_path"]),
        reverse=True,
    )
    matches, rejected = filter_case_matches(query, candidates)
    matches = matches[:limit]
    payment_nodes = collect_payment_nodes(matches)
    gaps = infer_gaps(query, matches)
    suggestions = build_copy_suggestions(matches, "2024_renovation_tail_latency")
    return {
        "matches": matches,
        "rejected": rejected,
        "answer": build_case_answer(matches, payment_nodes, gaps),
        "payment_nodes": payment_nodes,
        "gaps": gaps,
        "copy_suggestions": suggestions,
    }


def run_surface(surface: str, db_path: Path, limit: int) -> dict:
    started = time.perf_counter()
    try:
        if surface == "sqlite_text_search":
            matches = search_sqlite_index(db_path, CASE_QUERY, limit)
            grounded, failures = grounded_matches(matches)
            detail = {"match_count": len(matches), "top_results": matches[:3]}
        elif surface == "local_hash_embedding_search":
            matches = search_embedding_index(db_path, "last year renovation contract reimbursement invoice", limit)
            grounded, failures = grounded_matches(matches)
            detail = {"match_count": len(matches), "top_results": matches[:3]}
        elif surface == "photo_semantic_search":
            matches = search_photo_semantic_index(db_path, "beach white car invoice screenshot", limit)
            grounded, failures = grounded_matches(matches)
            detail = {"match_count": len(matches), "top_results": matches[:3]}
        elif surface == "folder_rag":
            records = load_folder_records(db_path, "Documents")
            matches = folder_query_matches(records, FOLDER_QUESTION, limit)
            payment_nodes = collect_folder_payment_nodes(matches)
            grounded, failures = grounded_matches(matches)
            detail = {
                "folder_file_count": len(records),
                "match_count": len(matches),
                "answer": build_answer("Documents", FOLDER_QUESTION, records, matches, [])[1],
                "payment_nodes": payment_nodes,
                "top_results": matches[:3],
            }
        elif surface == "case_packet":
            packet = case_packet(db_path, CASE_QUERY, limit)
            grounded, failures = grounded_matches(packet["matches"])
            if not packet["payment_nodes"]:
                failures.append("case_packet_missing_payment_nodes")
            if not packet["copy_suggestions"]:
                failures.append("case_packet_missing_copy_suggestions")
            detail = {
                "match_count": len(packet["matches"]),
                "answer": packet["answer"],
                "payment_nodes": packet["payment_nodes"],
                "copy_suggestion_count": len(packet["copy_suggestions"]),
                "top_results": packet["matches"][:3],
            }
        else:
            raise ValueError(f"unsupported_surface:{surface}")
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "surface": surface,
            "ok": grounded and not failures,
            "elapsed_ms": round(elapsed_ms, 3),
            "grounding_failures": failures,
            "detail": detail,
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "surface": surface,
            "ok": False,
            "elapsed_ms": round(elapsed_ms, 3),
            "error": f"{type(exc).__name__}:{exc}",
            "grounding_failures": ["surface_exception"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS user-facing P95/P99 tail latency and grounding contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--p95-ms", type=float, default=DEFAULT_P95_MS)
    parser.add_argument("--p99-ms", type=float, default=DEFAULT_P99_MS)
    args = parser.parse_args()

    args.iterations = max(1, args.iterations)
    args.workers = max(1, args.workers)
    run_dir = ensure_report_dir(args.report_root, "user_facing_tail_latency")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = run_dir / "user_facing_tail_latency.sqlite3"
    warmup_started = time.perf_counter()
    index_status = build_sqlite_inventory(personal_root, db_path)
    image_status = ensure_image_embeddings_for_photos(db_path)
    warmup_ms = (time.perf_counter() - warmup_started) * 1000

    surfaces = [
        "sqlite_text_search",
        "local_hash_embedding_search",
        "photo_semantic_search",
        "folder_rag",
        "case_packet",
    ]
    jobs = [surface for _ in range(args.iterations) for surface in surfaces]
    samples = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_surface, surface, db_path, args.limit) for surface in jobs]
        for future in as_completed(futures):
            samples.append(future.result())
    samples.sort(key=lambda item: (item["surface"], item["elapsed_ms"]))

    summaries = {}
    failures = []
    for surface in surfaces:
        surface_samples = [item for item in samples if item["surface"] == surface]
        latencies = [item["elapsed_ms"] for item in surface_samples]
        summary = latency_summary(latencies)
        failures_for_surface = [item for item in surface_samples if not item.get("ok")]
        if failures_for_surface:
            failures.append(f"{surface}:failure_count:{len(failures_for_surface)}")
        if summary["p95_ms"] is None or summary["p95_ms"] > args.p95_ms:
            failures.append(f"{surface}:p95_ms_gt_{args.p95_ms}")
        if summary["p99_ms"] is None or summary["p99_ms"] > args.p99_ms:
            failures.append(f"{surface}:p99_ms_gt_{args.p99_ms}")
        summaries[surface] = {
            **summary,
            "failure_count": len(failures_for_surface),
            "thresholds": {"p95_ms": args.p95_ms, "p99_ms": args.p99_ms},
            "sample_grounding_failures": [
                {
                    "elapsed_ms": item.get("elapsed_ms"),
                    "error": item.get("error"),
                    "grounding_failures": item.get("grounding_failures"),
                }
                for item in failures_for_surface[:5]
            ],
        }
    all_latencies = [item["elapsed_ms"] for item in samples]
    all_summary = latency_summary(all_latencies)
    failed_samples = [item for item in samples if not item.get("ok")]

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_user_facing_tail_latency" if not failures else "failed_ai_nas_user_facing_tail_latency",
        "scope": "bounded user-facing tail latency and grounding contract over SQLite/FTS, local embedding, photo search, folder RAG, and case packet surfaces",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "warmup": {
            "elapsed_ms": round(warmup_ms, 3),
            "index_status": index_status,
            "image_embedding_status": image_status,
        },
        "summary": {
            "surface_count": len(surfaces),
            "iterations_per_surface": args.iterations,
            "sample_count": len(samples),
            "failed_sample_count": len(failed_samples),
            "all_latency": all_summary,
            "surface_latency": summaries,
            "failures": failures,
        },
        "samples": samples,
        "final_index_status": sqlite_index_status(db_path),
        "audit": {
            "real_personal_source_modified": False,
            "fixture_only": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "isolated fixture files plus SQLite/FTS index and Markdown/JSON tail-latency reports",
        },
        "production_gap": "This is a bounded local fixture contract; production still needs the same user-facing tail-latency SLO under a mounted NAS root, real model runtimes, and long-duration load.",
    }

    json_path = run_dir / "user_facing_tail_latency.json"
    md_path = run_dir / "user_facing_tail_latency.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS User-Facing Tail Latency",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- iterations_per_surface: `{args.iterations}`",
        f"- sample_count: `{len(samples)}`",
        f"- failed_sample_count: `{len(failed_samples)}`",
        f"- all_p95_ms: `{all_summary['p95_ms']}`",
        f"- all_p99_ms: `{all_summary['p99_ms']}`",
        f"- failures: `{failures}`",
        "- policy: isolated fixture only; no real Personal mutation, network call, service start, delete, move, or overwrite",
        "",
        "## Surface Latency",
        "",
    ]
    for surface, summary in summaries.items():
        lines.append(
            f"- `{surface}` count `{summary['count']}` p95 `{summary['p95_ms']}` ms p99 `{summary['p99_ms']}` ms failures `{summary['failure_count']}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
